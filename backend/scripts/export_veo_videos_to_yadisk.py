#!/usr/bin/env python3
"""
Экспортировать все видео из переписки с Telegram-ботом (например VEO) на Яндекс.Диск.

Требования:
  - TELEGRAM_API_ID, TELEGRAM_API_HASH (User API)
  - YADISK_TOKEN (OAuth токен Яндекс.Диск)
  - Telethon: pip install telethon

Пример:
  python backend/scripts/export_veo_videos_to_yadisk.py \\
    --bot @syntxaibot \\
    --session-path backend/telegram_sessions/session_collector_client_3.session \\
    --disk-dir disk/zavod/video
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    from telethon import TelegramClient
except Exception:  # pragma: no cover
    TelegramClient = None

import html as html_lib


URL_RE = re.compile(r'https?://[^\s<>"{}|\\^`[\]]+')
MP4_URL_RE = re.compile(r"https?://[^\s\"']+\.mp4(?:\?[^\s\"']*)?", re.I)


@dataclass(frozen=True)
class ExportStats:
    scanned_messages: int
    found_videos: int
    downloaded_videos: int
    uploaded_videos: int
    skipped_videos: int
    errors: int


@dataclass(frozen=True)
class VideoJob:
    msg_id: int
    msg_date: object
    index: int
    source_type: str  # "media" | "url"
    url: Optional[str]
    msg: object
    ext: str
    request_text: str


def _make_logger(log_file: Optional[str]) -> Tuple[Callable[[str], None], Callable[[], None]]:
    log_path: Optional[Path] = None
    handle = None
    if log_file:
        candidate = (log_file or "").strip()
        if candidate and candidate != "-":
            log_path = Path(candidate)
            if not log_path.is_absolute():
                log_path = (Path(__file__).resolve().parent / log_path).resolve()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(log_path, "a", encoding="utf-8")

    def _log(message: str) -> None:
        line = str(message)
        print(line)
        if handle:
            handle.write(line + "\n")
            handle.flush()

    def _close() -> None:
        nonlocal handle
        if handle:
            try:
                handle.close()
            finally:
                handle = None

    return _log, _close


def _extract_request_text(message_text: str) -> str:
    """
    Вернуть фрагмент от "Ваш запрос:" до "🎛️ Инструмент:".
    Если маркеры не найдены — вернуть пустую строку.
    """
    text = (message_text or "").replace("\r\n", "\n")
    match = re.search(
        r"(Ваш запрос:\s*.*?)(?:\n?\s*🎛️\s*Инструмент:)",
        text,
        flags=re.IGNORECASE | re.S,
    )
    if not match:
        return ""
    fragment = match.group(1)
    fragment = re.sub(r"^\s*(?:📍\s*)?Ваш запрос:\s*", "", fragment, flags=re.IGNORECASE)
    fragment = html_lib.unescape(fragment).strip()
    # Часто VEO возвращает формат "Scene 1: ... Scene 2: ..." — убираем только "Scene 1:" в начале.
    fragment = re.sub(r"^\s*scene\s*1\s*[:\-]\s*", "", fragment, flags=re.IGNORECASE)
    return fragment.strip()


def _setup_django(settings_module: str, repo_root: Path):
    """
    Ленивый setup Django для сохранения записей в БД.
    """
    backend_dir = repo_root / "backend"
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    import django  # type: ignore

    django.setup()
    from core.models import VeoVideoExport  # type: ignore

    return VeoVideoExport


def _load_local_yadisk_module() -> object:
    scripts_dir = Path(__file__).resolve().parent
    yadisk_path = scripts_dir / "yadisk.py"
    if not yadisk_path.exists():
        raise FileNotFoundError(f"Не найден модуль Яндекс.Диска: {yadisk_path}")

    spec = importlib.util.spec_from_file_location("yadisk_local", yadisk_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить backend/scripts/yadisk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_bot_username(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("@"):
        cleaned = "@" + cleaned
    return cleaned


def _resolve_session_base(
    *,
    session_path: Optional[str],
    session_name: Optional[str],
    repo_root: Path,
) -> Tuple[str, str]:
    """
    Вернуть (telethon_session_base, session_label).
    Telethon ожидает базовый путь без суффикса ".session".
    """
    if session_path:
        expanded = os.path.abspath(os.path.expanduser(session_path))
        if expanded.endswith(".session"):
            return expanded[:-8], expanded
        return expanded, expanded + ".session"

    if session_name:
        raw = session_name.strip()
        if not raw:
            raise ValueError("Пустое значение --session-name")

        # Попробуем найти сессию в backend/, если путь относительный.
        candidate_bases: List[Path] = []
        raw_path = Path(raw)
        if raw_path.is_absolute():
            candidate_bases.append(raw_path)
        else:
            candidate_bases.append(repo_root / "backend" / "telegram_sessions" / raw_path)
            candidate_bases.append(repo_root / "backend" / raw_path)
            candidate_bases.append(repo_root / raw_path)

        for base in candidate_bases:
            if base.with_suffix(".session").exists() or base.exists():
                base_str = str(base)
                if base_str.endswith(".session"):
                    return base_str[:-8], base_str
                return base_str, base_str + ".session"

        # Фолбэк: используем как есть (создаст новый файл рядом с cwd).
        return raw, f"{raw}.session"

    # Автовыбор: берем наиболее подходящую сессию из backend/telegram_sessions.
    sessions_dir = repo_root / "backend" / "telegram_sessions"
    if sessions_dir.exists():
        all_sessions = [
            p for p in sessions_dir.glob("*.session")
            if p.is_file() and "_thread_" not in p.name
        ]

        def newest(paths: Iterable[Path]) -> Optional[Path]:
            paths_list = list(paths)
            if not paths_list:
                return None
            return max(paths_list, key=lambda p: p.stat().st_mtime)

        # 1) Collector (обычно используется для ботов/сбора).
        candidate = newest([p for p in all_sessions if p.name.startswith("session_collector_client_")])
        # 2) Именованная veo-сессия, если есть.
        if candidate is None:
            candidate = newest([p for p in all_sessions if p.stem == "veo_generator"])
        # 3) Любая другая.
        if candidate is None:
            candidate = newest(all_sessions)

        if candidate is not None:
            return str(candidate)[:-8], str(candidate)

    raise ValueError(
        "Не задана Telegram-сессия и не найдены *.session в backend/telegram_sessions "
        "(используйте --session-path или --session-name)."
    )


def _extract_urls_from_message(msg) -> List[str]:
    candidates: List[str] = []
    text = (getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "") or ""
    for raw_url in URL_RE.findall(text):
        candidates.append(raw_url.strip("()[]<>., "))

    entities = getattr(msg, "entities", None) or []
    for ent in entities:
        direct_url = getattr(ent, "url", None)
        if direct_url:
            candidates.append(direct_url)
            continue

        try:
            offset = int(getattr(ent, "offset", 0))
            length = int(getattr(ent, "length", 0))
            if length > 0 and text:
                segment = text[offset : offset + length]
                if segment:
                    candidates.append(segment)
        except Exception:
            continue

    markup = getattr(msg, "reply_markup", None)
    if markup:
        for row in getattr(markup, "rows", []) or []:
            for button in getattr(row, "buttons", []) or []:
                button_url = getattr(button, "url", None)
                if button_url:
                    candidates.append(button_url)

    unique: List[str] = []
    seen = set()
    for item in candidates:
        url = (item or "").strip()
        if not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def _extract_mp4_urls_from_message(msg) -> List[str]:
    urls: List[str] = []
    text = (getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "") or ""
    for match in MP4_URL_RE.findall(text):
        urls.append(match.strip("()[]<>., "))

    for url in _extract_urls_from_message(msg):
        if ".mp4" in url.lower():
            urls.append(url)

    unique: List[str] = []
    seen = set()
    for url in urls:
        cleaned = url.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def _is_video_message(msg) -> bool:
    if not msg:
        return False
    if not getattr(msg, "media", None):
        return False
    if getattr(msg, "video", None):
        return True
    file_obj = getattr(msg, "file", None)
    mime = getattr(file_obj, "mime_type", None) or ""
    if isinstance(mime, str) and mime.lower().startswith("video/"):
        return True
    ext = getattr(file_obj, "ext", None) or ""
    if isinstance(ext, str) and ext.lower() in {".mp4", ".mov", ".m4v", ".webm"}:
        return True
    return False


def _extract_mp4_from_html(body: str) -> Tuple[Optional[str], str]:
    """
    Попробовать достать прямую mp4 ссылку из HTML/JS.
    Портировано из backend/core/foto_video_gen.py (без Django-зависимостей).
    """
    if not body:
        return None, "HTML body is empty"
    normalized = html_lib.unescape(body)
    normalized = normalized.replace("\\/", "/")
    match = MP4_URL_RE.search(normalized)
    if match:
        return match.group(0), f"MP4 matched: {match.group(0)}"
    src_match = re.search(
        r'id=["\\\']videoSource["\\\']\\s+src=["\\\']([^"\\\']+\.mp4[^"\\\']*)',
        normalized,
        flags=re.I,
    )
    if src_match:
        return src_match.group(1), f"videoSource src matched: {src_match.group(1)}"
    return None, "MP4 not found in HTML"


def _is_candidate_video_link(url: str, message_text: str) -> bool:
    lowered = (url or "").lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if ".mp4" in lowered:
        return True
    # Типичный формат ответа бота: "Вот прямая ссылка (...) на качественную версию."
    if "прямая ссылка" in (message_text or "").lower():
        return True
    # Основной домен, который встречался в ответах.
    if "getvideo.syntxai.net" in lowered:
        return True
    return False


def _download_video_from_link(url: str, timeout_s: int, _depth: int = 0) -> Optional[str]:
    try:
        with requests.get(url, timeout=timeout_s, stream=True) as resp:
            resp.raise_for_status()

            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "video" not in content_type and "octet-stream" not in content_type:
                if _depth >= 2:
                    print(f"  ! ссылка не выглядит как видео (Content-Type={content_type or 'unknown'}): {url}")
                    return None

                body = ""
                try:
                    body = resp.text or ""
                except Exception:
                    body = ""
                mp4_url, _reason = _extract_mp4_from_html(body)
                if mp4_url:
                    return _download_video_from_link(mp4_url, timeout_s=timeout_s, _depth=_depth + 1)

                print(f"  ! ссылка не выглядит как видео (Content-Type={content_type or 'unknown'}): {url}")
                return None

            fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
            try:
                with os.fdopen(fd, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 512):
                        if not chunk:
                            continue
                        f.write(chunk)
                if os.path.getsize(tmp_path) < 10 * 1024:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    print(f"  ! файл слишком маленький (не похоже на видео): {url}")
                    return None
                return tmp_path
            except Exception:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
    except Exception as exc:
        print(f"  ! не удалось скачать {url}: {exc}")
        return None


def _safe_disk_path_part(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = cleaned.replace("\\", "_").replace("/", "_")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    return cleaned.strip("_") or "unknown"


def _build_remote_path(
    *,
    disk_dir: str,
    bot_username: str,
    msg_id: int,
    msg_date,
    index: int,
    ext: str,
) -> str:
    day_part = "unknown_date"
    try:
        if msg_date:
            day_part = msg_date.strftime("%Y-%m-%d")
            time_part = msg_date.strftime("%H%M%S")
        else:
            time_part = "unknown_time"
    except Exception:
        time_part = "unknown_time"

    name = f"{time_part}_{msg_id}"
    if index:
        name = f"{name}_{index}"

    ext_clean = ext if ext.startswith(".") else f".{ext}"
    ext_clean = ext_clean.lower()
    if ext_clean not in {".mp4", ".mov", ".m4v", ".webm"}:
        ext_clean = ".mp4"

    base_dir = disk_dir.strip("/").strip()
    if not base_dir:
        base_dir = "disk/zavod/video"
    return f"{base_dir}/{day_part}/{name}{ext_clean}"


async def export_videos(args: argparse.Namespace) -> ExportStats:
    if TelegramClient is None:
        raise RuntimeError("telethon не установлен. Установите: pip install telethon")

    if load_dotenv:
        load_dotenv()

    if not os.getenv("YADISK_TOKEN"):
        raise RuntimeError("Нужен YADISK_TOKEN (OAuth токен Яндекс.Диск). Добавьте его в .env или окружение.")

    log, close_log = _make_logger(args.log_file)

    yadisk_mod = _load_local_yadisk_module()
    upload_file = getattr(yadisk_mod, "upload_file", None)
    if not callable(upload_file):
        raise RuntimeError("В backend/scripts/yadisk.py нет функции upload_file()")

    api_id = args.api_id or os.getenv("TELEGRAM_API_ID") or os.getenv("TG_API_ID") or os.getenv("API_ID")
    api_hash = args.api_hash or os.getenv("TELEGRAM_API_HASH") or os.getenv("TG_API_HASH") or os.getenv("API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Нужны TELEGRAM_API_ID и TELEGRAM_API_HASH (или передайте --api-id/--api-hash).")

    try:
        api_id_int = int(api_id)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_API_ID должен быть числом") from exc

    repo_root = Path(__file__).resolve().parents[2]
    session_base, session_label = _resolve_session_base(
        session_path=args.session_path,
        session_name=args.session_name,
        repo_root=repo_root,
    )

    bot_username = _normalize_bot_username(args.bot or os.getenv("VEO_BOT_USERNAME") or "@syntxaibot")
    if not bot_username:
        raise RuntimeError("Не задан бот (используйте --bot)")

    log("Telegram:")
    log(f"  bot: {bot_username}")
    log(f"  session: {session_label}")
    log("Yandex Disk:")
    log(f"  dir: {args.disk_dir}")

    resume_min_exported_id: Optional[int] = None
    resume_max_exported_id: Optional[int] = None
    resume_enabled = not bool(getattr(args, "no_resume", False))

    try:
        veo_export_model = _setup_django(args.django_settings, repo_root)
    except Exception as exc:
        raise RuntimeError(
            "Не удалось подключиться к Django/БД для сохранения экспорта. "
            "Проверьте, что вы запускаете из проекта и выполнены миграции: "
            "python backend/manage.py migrate"
        ) from exc

    log(f"DB: enabled (settings={args.django_settings})")
    if resume_enabled:
        base_dir = (args.disk_dir or "").strip("/").strip() or "disk/zavod/video"

        def _load_resume_bounds() -> Tuple[Optional[int], Optional[int]]:
            from django.db.models import Max, Min  # type: ignore

            agg = (
                veo_export_model.objects.filter(
                    bot_username=bot_username,
                    disk_path__startswith=f"{base_dir}/",
                )
                .exclude(telegram_message_id__isnull=True)
                .aggregate(min_id=Min("telegram_message_id"), max_id=Max("telegram_message_id"))
            )
            min_id = agg.get("min_id")
            max_id = agg.get("max_id")
            return (int(min_id) if min_id is not None else None, int(max_id) if max_id is not None else None)

        resume_min_exported_id, resume_max_exported_id = await asyncio.to_thread(_load_resume_bounds)
        if resume_min_exported_id is not None or resume_max_exported_id is not None:
            log(f"Resume: exported range telegram_message_id=[{resume_min_exported_id}..{resume_max_exported_id}]")
        else:
            log("Resume: no previous exports found")

    client = TelegramClient(session_base, api_id_int, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram-сессия не авторизована. "
                "Сначала выполните: python backend/scripts/authorize_telegram.py --session-type collector"
            )

        bot = await client.get_entity(bot_username)
        try:
            latest_list = await client.get_messages(bot, limit=1)
            latest = latest_list[0] if latest_list else None
            if latest is not None:
                latest_id = getattr(latest, "id", None)
                latest_date = getattr(latest, "date", None)
                log(f"Chat latest message: id={latest_id}, date={latest_date}")
        except Exception:
            pass

        stats_lock = asyncio.Lock()
        stats = {
            "scanned_messages": 0,
            "found_videos": 0,
            "downloaded_videos": 0,
            "uploaded_videos": 0,
            "skipped_videos": 0,
            "errors": 0,
        }

        queue: asyncio.Queue[Optional[VideoJob]] = asyncio.Queue(maxsize=max(10, int(args.workers) * 5))

        async def _worker(worker_id: int) -> None:
            while True:
                job = await queue.get()
                try:
                    if job is None:
                        return

                    remote_path = _build_remote_path(
                        disk_dir=args.disk_dir,
                        bot_username=bot_username,
                        msg_id=job.msg_id,
                        msg_date=job.msg_date,
                        index=job.index,
                        ext=job.ext,
                    )

                    if resume_enabled:
                        def _already_exported() -> bool:
                            return veo_export_model.objects.filter(disk_path=remote_path).exists()

                        if await asyncio.to_thread(_already_exported):
                            log(f"  - already exported: {remote_path}")
                            async with stats_lock:
                                stats["skipped_videos"] += 1
                            continue

                    if args.dry_run:
                        log(f"  - dry-run: {job.source_type} -> {remote_path}")
                        async with stats_lock:
                            stats["skipped_videos"] += 1
                        continue

                    local_path: Optional[str] = None
                    try:
                        if job.source_type == "media":
                            fd, tmp_path = tempfile.mkstemp(suffix=job.ext if job.ext.startswith(".") else ".mp4")
                            os.close(fd)
                            downloaded = await client.download_media(job.msg, file=tmp_path)
                            if not downloaded or not os.path.exists(downloaded):
                                log("  ! не удалось скачать медиа из сообщения")
                                async with stats_lock:
                                    stats["errors"] += 1
                                continue
                            local_path = str(downloaded)
                        else:
                            if not job.url:
                                async with stats_lock:
                                    stats["errors"] += 1
                                continue
                            local_path = await asyncio.to_thread(
                                _download_video_from_link,
                                job.url,
                                int(args.url_timeout),
                            )
                            if not local_path:
                                async with stats_lock:
                                    stats["errors"] += 1
                                continue

                        async with stats_lock:
                            stats["downloaded_videos"] += 1

                        def _upload() -> None:
                            try:
                                upload_file(local_path=local_path, disk_path=remote_path, logger=log)
                            except TypeError:
                                upload_file(local_path=local_path, disk_path=remote_path)
                                log(f"Файл загружен: {remote_path}")

                        await asyncio.to_thread(_upload)
                        async with stats_lock:
                            stats["uploaded_videos"] += 1

                        def _save() -> None:
                            veo_export_model.objects.update_or_create(
                                disk_path=remote_path,
                                defaults={
                                    "request_text": job.request_text or "",
                                    "telegram_message_id": job.msg_id,
                                    "telegram_message_date": job.msg_date,
                                    "bot_username": bot_username,
                                    "source_url": job.url or "",
                                },
                            )

                        await asyncio.to_thread(_save)
                    except Exception as exc:
                        log(f"  ! ошибка при обработке видео: {exc}")
                        async with stats_lock:
                            stats["errors"] += 1
                    finally:
                        if local_path and os.path.exists(local_path):
                            try:
                                os.remove(local_path)
                            except OSError:
                                pass

                    if args.sleep and args.sleep > 0:
                        await asyncio.sleep(args.sleep)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(_worker(i + 1)) for i in range(int(args.workers))]

        limit = args.limit if args.limit and args.limit > 0 else None
        oldest_first = bool(args.oldest_first)
        only_incoming = bool(args.only_incoming)

        scan_min_id = int(args.min_id) if args.min_id else 0
        scan_max_id = int(args.max_id) if args.max_id else 0

        # Resume semantics:
        # - Default direction (newest -> oldest): continue further into history (older than already exported).
        #   That means: start from message_id < resume_min_exported_id.
        # - oldest_first (oldest -> newest): continue forward (newer than already exported).
        #   That means: start from message_id > resume_max_exported_id.
        if resume_enabled and resume_min_exported_id is not None and not oldest_first:
            resume_cap = max(0, resume_min_exported_id - 1)
            scan_max_id = resume_cap if scan_max_id <= 0 else min(scan_max_id, resume_cap)
            log(f"Resume: scanning older messages with id <= {scan_max_id}")
        if resume_enabled and resume_max_exported_id is not None and oldest_first:
            scan_min_id = max(scan_min_id, resume_max_exported_id)
            log(f"Resume: scanning newer messages with id > {scan_min_id}")

        async for msg in client.iter_messages(
            bot,
            limit=limit,
            reverse=oldest_first,
            min_id=scan_min_id,
            max_id=scan_max_id,
        ):
            async with stats_lock:
                stats["scanned_messages"] += 1

            msg_id = getattr(msg, "id", None)
            msg_date = getattr(msg, "date", None)

            if msg_id is None:
                continue
            if args.min_id and msg_id < args.min_id:
                continue
            if args.max_id and msg_id > args.max_id:
                continue
            if only_incoming and getattr(msg, "out", False):
                continue

            sources: List[Tuple[str, str, Optional[str]]] = []

            if _is_video_message(msg):
                ext = ".mp4"
                file_obj = getattr(msg, "file", None)
                msg_ext = getattr(file_obj, "ext", None)
                if isinstance(msg_ext, str) and msg_ext:
                    ext = msg_ext
                sources.append(("media", ext, None))

            msg_text = (getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "") or ""
            request_text = _extract_request_text(msg_text)
            candidate_urls: List[str] = []
            for url in _extract_urls_from_message(msg):
                if _is_candidate_video_link(url, msg_text):
                    candidate_urls.append(url)

            # Исторический случай: прямые .mp4 в тексте.
            for mp4_url in _extract_mp4_urls_from_message(msg):
                if mp4_url not in candidate_urls:
                    candidate_urls.append(mp4_url)

            for url in candidate_urls:
                sources.append(("url", ".mp4", url))

            if not sources:
                continue

            per_message_jobs: List[VideoJob] = []
            total_sources = len(sources)
            for i, (source_type, ext, url) in enumerate(sources):
                suffix_index = 0
                if total_sources > 1 and i > 0:
                    suffix_index = i + 1  # 2,3,... (первый файл без суффикса)
                per_message_jobs.append(
                    VideoJob(
                        msg_id=int(msg_id),
                        msg_date=msg_date,
                        index=suffix_index,
                        source_type=source_type,
                        url=url,
                        msg=msg,
                        ext=ext,
                        request_text=request_text,
                    )
                )

            log(f"[{msg_id}] найдено источников видео: {len(per_message_jobs)}")
            async with stats_lock:
                stats["found_videos"] += len(per_message_jobs)

            for job in per_message_jobs:
                await queue.put(job)

            if args.max_videos:
                async with stats_lock:
                    already_uploaded = stats["uploaded_videos"]
                if already_uploaded >= args.max_videos:
                    log(f"Достигнут лимит --max-videos={args.max_videos}, остановка.")
                    break

        await queue.join()
        for _ in workers:
            await queue.put(None)
        await asyncio.gather(*workers, return_exceptions=True)

        async with stats_lock:
            return ExportStats(
                scanned_messages=int(stats["scanned_messages"]),
                found_videos=int(stats["found_videos"]),
                downloaded_videos=int(stats["downloaded_videos"]),
                uploaded_videos=int(stats["uploaded_videos"]),
                skipped_videos=int(stats["skipped_videos"]),
                errors=int(stats["errors"]),
            )
    finally:
        await client.disconnect()
        close_log()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Экспорт видео из переписки с ботом на Яндекс.Диск")
    parser.add_argument("--bot", default=None, help="Username бота (например @syntxaibot)")

    parser.add_argument("--api-id", dest="api_id", default=None, help="TELEGRAM_API_ID (если не из env)")
    parser.add_argument("--api-hash", dest="api_hash", default=None, help="TELEGRAM_API_HASH (если не из env)")

    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument("--session-path", default=None, help="Путь к .session файлу (или к базе без .session)")
    session_group.add_argument("--session-name", default=None, help="Имя/путь сессии Telethon (без .session)")

    parser.add_argument("--disk-dir", default="disk/zavod/video", help="Папка на Яндекс.Диске")
    parser.add_argument(
        "--log-file",
        default="export_veo_videos_to_yadisk.log",
        help="Файл текстового лога (относительно backend/scripts; '-' отключает запись)",
    )
    parser.add_argument("--workers", type=int, default=4, help="Количество параллельных воркеров (скачивание/загрузка)")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Не продолжать с последнего сохраненного сообщения (сканировать заново)",
    )
    parser.add_argument(
        "--django-settings",
        default="config.settings.dev",
        help="DJANGO_SETTINGS_MODULE для сохранения в БД (по умолчанию config.settings.dev)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Лимит сообщений (0 = без лимита)")
    parser.add_argument("--min-id", type=int, default=0, help="Обрабатывать сообщения с id >= min-id")
    parser.add_argument("--max-id", type=int, default=0, help="Обрабатывать сообщения с id <= max-id")
    parser.add_argument("--max-videos", type=int, default=0, help="Остановиться после N загруженных видео (0 = без лимита)")
    parser.add_argument("--oldest-first", action="store_true", help="Идти от старых к новым (reverse=True)")
    parser.add_argument("--only-incoming", action="store_true", help="Пропускать исходящие сообщения (out=True)")
    parser.add_argument("--dry-run", action="store_true", help="Ничего не скачивать/не загружать, только вывести план")
    parser.add_argument("--url-timeout", type=int, default=120, help="Таймаут скачивания видео по ссылке (сек)")
    parser.add_argument("--sleep", type=float, default=0.0, help="Пауза между загрузками (сек)")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    stats = asyncio.run(export_videos(args))
    print()
    print("Готово:")
    print(f"  messages scanned: {stats.scanned_messages}")
    print(f"  videos found:     {stats.found_videos}")
    print(f"  downloaded:       {stats.downloaded_videos}")
    print(f"  uploaded:         {stats.uploaded_videos}")
    print(f"  skipped:          {stats.skipped_videos}")
    print(f"  errors:           {stats.errors}")
    return 0 if stats.errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
