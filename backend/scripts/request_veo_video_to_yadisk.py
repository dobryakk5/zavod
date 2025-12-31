#!/usr/bin/env python3
"""
Сделать серию запросов в Telegram-бот VEO и выгрузить полученные видео на Яндекс.Диск с записью в БД.

Сценарий (по умолчанию):
  - для каждой фразы из backend/scripts/word_gen.txt:
      1) отправить картинку (backend/scripts/open.png) в бот
      2) следующим сообщением отправить тему ролика + уточнение для модели
      3) ждать ответы до 10 минут, найти видео (файл или ссылка), скачать, загрузить на Я.Диск,
         сохранить запись в core.models.VeoVideoExport (как в export_veo_videos_to_yadisk.py)
         В request_text сохраняется фрагмент ответа бота ("Ваш запрос:" …).

Требования:
  - TELEGRAM_API_ID, TELEGRAM_API_HASH (User API)
  - YADISK_TOKEN (OAuth токен Яндекс.Диск)
  - telethon: pip install telethon

Пример:
  python backend/scripts/request_veo_video_to_yadisk.py
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
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

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
class ExportedItem:
    disk_path: str
    telegram_message_id: Optional[int]
    telegram_message_date: Any
    source_url: str
    request_text: str


@dataclass(frozen=True)
class ExportJob:
    source_type: str  # "url" | "media"
    remote_path: str
    msg: Any
    msg_id: int
    msg_date: Any
    url: str
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


def _setup_django(settings_module: str, repo_root: Path):
    backend_dir = repo_root / "backend"
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    import django  # type: ignore

    django.setup()
    from core.models import VeoVideoExport  # type: ignore

    return VeoVideoExport


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

        candidate = newest([p for p in all_sessions if p.name.startswith("session_collector_client_")])
        if candidate is None:
            candidate = newest([p for p in all_sessions if p.stem == "veo_generator"])
        if candidate is None:
            candidate = newest(all_sessions)

        if candidate is not None:
            return str(candidate)[:-8], str(candidate)

    raise ValueError(
        "Не задана Telegram-сессия и не найдены *.session в backend/telegram_sessions "
        "(используйте --session-path или --session-name)."
    )


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
    fragment = re.sub(r"^\s*scene\s*1\s*[:\-]\s*", "", fragment, flags=re.IGNORECASE)
    return fragment.strip()


def _extract_urls_from_message(msg) -> List[str]:
    if not msg:
        return []

    candidates: List[str] = []
    text = (getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "") or ""
    if text:
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
    if "прямая ссылка" in (message_text or "").lower():
        return True
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


def _build_remote_path(
    *,
    disk_dir: str,
    msg_id: int,
    msg_date: Any,
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


def _resolve_image_path(value: Optional[str]) -> str:
    if value:
        candidate = os.path.abspath(os.path.expanduser(value))
        if os.path.exists(candidate):
            return candidate
        raise FileNotFoundError(f"Не найден файл изображения: {candidate}")
    default_path = (Path(__file__).resolve().parent / "open.png").resolve()
    if not default_path.exists():
        raise FileNotFoundError(f"Не найден open.png рядом со скриптом: {default_path}")
    return str(default_path)


def _load_prompts_from_file(path: str) -> List[str]:
    prompts: List[str] = []
    candidate = Path(os.path.expanduser(path))
    if not candidate.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        candidates = [
            (repo_root / candidate).resolve(),
            (Path(__file__).resolve().parent / candidate).resolve(),
            candidate.resolve(),
        ]
        resolved = next((p for p in candidates if p.exists()), None)
        if resolved is None:
            raise FileNotFoundError(f"Не найден файл с фразами: {path}")
        candidate = resolved
    else:
        candidate = candidate.resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Не найден файл с фразами: {candidate}")

    with open(candidate, "r", encoding="utf-8") as f:
        for raw in f:
            line = (raw or "").strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("**") or line.startswith("---"):
                continue
            if line.startswith(("* ", "- ")):
                line = line[2:].strip()
            else:
                continue
            if not line:
                continue
            prompts.append(line)

    # unique preserving order
    unique: List[str] = []
    seen = set()
    for item in prompts:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


async def request_and_export(args: argparse.Namespace) -> List[ExportedItem]:
    if TelegramClient is None:
        raise RuntimeError("telethon не установлен. Установите: pip install telethon")

    if load_dotenv:
        load_dotenv()

    if not os.getenv("YADISK_TOKEN"):
        raise RuntimeError("Нужен YADISK_TOKEN (OAuth токен Яндекс.Диск). Добавьте его в .env или окружение.")

    log, close_log = _make_logger(args.log_file)

    try:
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
            raise RuntimeError("Не задан бот (используйте --bot или VEO_BOT_USERNAME)")

        image_path = _resolve_image_path(args.image)
        prompt_text = (args.prompt or "").strip()

        prompts: List[str] = []
        if args.prompts_file:
            prompts = _load_prompts_from_file(args.prompts_file)
            if args.prompts_skip and int(args.prompts_skip) > 0:
                prompts = prompts[int(args.prompts_skip) :]
            if args.prompts_limit and int(args.prompts_limit) > 0:
                prompts = prompts[: int(args.prompts_limit)]
        else:
            if not prompt_text:
                raise ValueError("Пустой --prompt")
            prompts = [prompt_text]

        if not prompts:
            raise RuntimeError("Список фраз пустой (проверьте --prompts-file или --prompt)")

        try:
            veo_export_model = _setup_django(args.django_settings, repo_root)
        except Exception as exc:
            raise RuntimeError(
                "Не удалось подключиться к Django/БД для сохранения экспорта. "
                "Проверьте, что выполнены миграции: python backend/manage.py migrate"
            ) from exc

        log("Telegram:")
        log(f"  bot: {bot_username}")
        log(f"  session: {session_label}")
        log("Request:")
        log(f"  image: {image_path}")
        if args.prompts_file:
            log(f"  prompts_file: {args.prompts_file} (count={len(prompts)})")
        else:
            log(f"  prompt: {prompt_text}")
        log(f"  order: {args.order}")
        log(f"  send_image: {args.send_image}")
        log("Yandex Disk:")
        log(f"  dir: {args.disk_dir}")
        log(f"DB: enabled (settings={args.django_settings})")

        client = TelegramClient(session_base, api_id_int, api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Telegram-сессия не авторизована. "
                    "Сначала выполните: python backend/scripts/authorize_telegram.py --session-type collector"
                )

            bot = await client.get_entity(bot_username)
            exported: List[ExportedItem] = []
            errors: List[str] = []
            sent_image_msg_id: int = 0
            exported_lock = asyncio.Lock()
            telethon_lock = asyncio.Lock()
            worker_sem = asyncio.Semaphore(max(1, int(args.workers)))
            pending_tasks: List[asyncio.Task[None]] = []

            async def _process_job(job: ExportJob) -> None:
                async with worker_sem:
                    local_path: Optional[str] = None
                    try:
                        if job.source_type == "media":
                            async with telethon_lock:
                                fd, tmp_path = tempfile.mkstemp(
                                    suffix=job.ext if job.ext and job.ext.startswith(".") else ".mp4"
                                )
                                os.close(fd)
                                downloaded = await client.download_media(job.msg, file=tmp_path)
                                if not downloaded or not os.path.exists(downloaded):
                                    raise RuntimeError("не удалось скачать медиа из сообщения")
                                local_path = str(downloaded)
                        else:
                            local_path = await asyncio.to_thread(
                                _download_video_from_link,
                                job.url,
                                int(args.url_timeout),
                            )
                            if not local_path:
                                raise RuntimeError("не удалось скачать видео по ссылке")

                        def _upload() -> None:
                            try:
                                upload_file(local_path=local_path, disk_path=job.remote_path, logger=log)
                            except TypeError:
                                upload_file(local_path=local_path, disk_path=job.remote_path)
                                log(f"Файл загружен: {job.remote_path}")

                        await asyncio.to_thread(_upload)

                        def _save() -> None:
                            veo_export_model.objects.update_or_create(
                                disk_path=job.remote_path,
                                defaults={
                                    "request_text": job.request_text or "",
                                    "telegram_message_id": job.msg_id,
                                    "telegram_message_date": job.msg_date,
                                    "bot_username": bot_username,
                                    "source_url": job.url or "",
                                },
                            )

                        await asyncio.to_thread(_save)

                        async with exported_lock:
                            exported.append(
                                ExportedItem(
                                    disk_path=job.remote_path,
                                    telegram_message_id=job.msg_id,
                                    telegram_message_date=job.msg_date,
                                    source_url=job.url or "",
                                    request_text=job.request_text or "",
                                )
                            )
                        log(f"✅ exported: {job.remote_path}")
                    except Exception as exc:
                        msg = f"export failed (msg_id={job.msg_id}): {exc}"
                        errors.append(msg)
                        log(f"⚠️ {msg}")
                    finally:
                        if local_path and os.path.exists(local_path):
                            try:
                                os.remove(local_path)
                            except OSError:
                                pass

            def _track_task(task: asyncio.Task[None]) -> None:
                pending_tasks.append(task)

                def _done(_t: asyncio.Task[None]) -> None:
                    try:
                        pending_tasks.remove(_t)
                    except ValueError:
                        pass

                task.add_done_callback(_done)

            pre_command = (args.pre_command or "").strip()
            if pre_command:
                async with telethon_lock:
                    await client.send_message(bot, pre_command)

            max_videos_per_prompt = (
                int(args.max_videos_per_prompt)
                if args.max_videos_per_prompt and int(args.max_videos_per_prompt) > 0
                else 1
            )
            topics = [(p or "").strip() for p in prompts if (p or "").strip()]
            prompt_suffix = (args.prompt_suffix or "").strip()
            prompts_to_send = [
                f"{topic}\n\n{prompt_suffix}" if prompt_suffix else topic
                for topic in topics
            ]
            scheduled_paths: set[str] = set()

            async def _get_new_incoming(bot_entity, *, last_seen_id: int) -> Tuple[int, List[Any]]:
                batch: List[Any] = []
                new_last_seen_id = last_seen_id
                async with telethon_lock:
                    async for msg in client.iter_messages(bot_entity, min_id=last_seen_id, reverse=True):
                        mid = int(getattr(msg, "id", 0) or 0)
                        if mid <= new_last_seen_id:
                            continue
                        new_last_seen_id = mid
                        if getattr(msg, "out", False):
                            continue
                        batch.append(msg)
                return new_last_seen_id, batch

            for idx, current_prompt in enumerate(prompts_to_send, start=1):
                image_msg_id = int(sent_image_msg_id or 0)
                prompt_msg_id = 0
                need_send_image = args.send_image == "per_prompt" or (
                    args.send_image == "once" and not sent_image_msg_id
                )

                try:
                    async with telethon_lock:
                        if args.order == "image_first":
                            if need_send_image:
                                image_caption = (args.image_caption or "").strip() or None
                                image_msg = await client.send_file(bot, image_path, caption=image_caption)
                                image_msg_id = int(getattr(image_msg, "id", 0) or 0)
                                if args.send_image == "once" and image_msg_id:
                                    sent_image_msg_id = image_msg_id
                            prompt_msg = await client.send_message(bot, current_prompt)
                            prompt_msg_id = int(getattr(prompt_msg, "id", 0) or 0)
                        else:
                            prompt_msg = await client.send_message(bot, current_prompt)
                            prompt_msg_id = int(getattr(prompt_msg, "id", 0) or 0)
                            if need_send_image:
                                image_caption = (args.image_caption or "").strip() or None
                                image_msg = await client.send_file(bot, image_path, caption=image_caption)
                                image_msg_id = int(getattr(image_msg, "id", 0) or 0)
                                if args.send_image == "once" and image_msg_id:
                                    sent_image_msg_id = image_msg_id
                except Exception as exc:
                    raise RuntimeError(f"Не удалось отправить запрос: {exc}") from exc

                start_id = max(image_msg_id, prompt_msg_id)
                log(f"[{idx}/{len(prompts_to_send)}] Sent. start_message_id={start_id or 'unknown'} prompt={current_prompt}")

                deadline = time.time() + float(args.wait_seconds)
                last_seen_id = int(start_id or 0)
                found_for_prompt = 0
                last_extracted_request_text = ""

                while time.time() < deadline and found_for_prompt < max_videos_per_prompt:
                    last_seen_id, incoming = await _get_new_incoming(bot, last_seen_id=last_seen_id)
                    for msg in incoming:
                        msg_id = getattr(msg, "id", None)
                        if msg_id is None:
                            continue
                        msg_id_int = int(msg_id)
                        msg_date = getattr(msg, "date", None)
                        msg_text = (getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "") or ""

                        extracted_request_text = _extract_request_text(msg_text).strip()
                        if extracted_request_text:
                            last_extracted_request_text = extracted_request_text

                        candidate_urls: List[str] = []
                        for url in _extract_urls_from_message(msg):
                            if _is_candidate_video_link(url, msg_text):
                                candidate_urls.append(url)
                        for mp4_url in _extract_mp4_urls_from_message(msg):
                            if mp4_url not in candidate_urls:
                                candidate_urls.append(mp4_url)

                        sources: List[Tuple[str, str, Optional[str]]] = []
                        for url in candidate_urls:
                            sources.append(("url", ".mp4", url))

                        if args.allow_media and _is_video_message(msg):
                            ext = ".mp4"
                            file_obj = getattr(msg, "file", None)
                            msg_ext = getattr(file_obj, "ext", None)
                            if isinstance(msg_ext, str) and msg_ext:
                                ext = msg_ext
                            sources.append(("media", ext, None))

                        if not sources:
                            continue

                        request_text = (last_extracted_request_text or extracted_request_text or "").strip()
                        total_sources = len(sources)
                        for i, (source_type, ext, url) in enumerate(sources):
                            if found_for_prompt >= max_videos_per_prompt:
                                break

                            index_suffix = 0 if i == 0 or total_sources == 1 else i + 1
                            remote_path = _build_remote_path(
                                disk_dir=args.disk_dir,
                                msg_id=msg_id_int,
                                msg_date=msg_date,
                                index=index_suffix,
                                ext=ext,
                            )
                            if remote_path in scheduled_paths:
                                continue
                            if source_type != "media" and not url:
                                continue
                            scheduled_paths.add(remote_path)
                            job = ExportJob(
                                source_type=source_type,
                                remote_path=remote_path,
                                msg=msg,
                                msg_id=msg_id_int,
                                msg_date=msg_date,
                                url=url or "",
                                ext=ext,
                                request_text=request_text or "",
                            )
                            _track_task(asyncio.create_task(_process_job(job)))
                            found_for_prompt += 1
                            log(f"↳ got video source (msg_id={msg_id_int}) -> {remote_path}")
                            if found_for_prompt >= max_videos_per_prompt:
                                break

                    if found_for_prompt < max_videos_per_prompt:
                        await asyncio.sleep(max(0.2, float(args.poll_interval)))

                if found_for_prompt < max_videos_per_prompt:
                    raise RuntimeError(
                        f"Не получена ссылка на видео для промпта за {int(args.wait_seconds)} секунд: {current_prompt}"
                    )

                interval = float(args.sleep_between_prompts or 0.0)
                if interval > 0:
                    await asyncio.sleep(interval)

            if pending_tasks:
                log(f"Waiting for {len(pending_tasks)} export task(s) (workers={int(args.workers)})…")
                await asyncio.gather(*list(pending_tasks))

            if not exported:
                raise RuntimeError("Не удалось найти видео/ссылки в ответах бота за отведённое время")
            if errors:
                log(f"Done with errors: {len(errors)}")
                for item in errors[:10]:
                    log(f"  - {item}")

            return exported
        finally:
            await client.disconnect()
    finally:
        close_log()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Серия запросов VEO и выгрузка результатов на Яндекс.Диск")
    parser.add_argument(
        "--bot",
        default=None,
        help="Username бота (опционально; по умолчанию VEO_BOT_USERNAME или @syntxaibot)",
    )

    parser.add_argument("--api-id", dest="api_id", default=None, help="TELEGRAM_API_ID (если не из env)")
    parser.add_argument("--api-hash", dest="api_hash", default=None, help="TELEGRAM_API_HASH (если не из env)")

    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument("--session-path", default=None, help="Путь к .session файлу (или к базе без .session)")
    session_group.add_argument("--session-name", default=None, help="Имя/путь сессии Telethon (без .session)")

    parser.add_argument("--image", default=None, help="Путь к картинке (по умолчанию backend/scripts/open.png)")
    parser.add_argument(
        "--prompts-file",
        default="backend/scripts/word_gen.txt",
        help="Путь к файлу со списком фраз (берутся строки вида '* ...' или '- ...')",
    )
    parser.add_argument("--prompts-skip", type=int, default=0, help="Пропустить первые N фраз из prompts-file")
    parser.add_argument("--prompts-limit", type=int, default=0, help="Ограничить количество фраз (0 = без лимита)")
    parser.add_argument(
        "--prompt",
        default="Зачем бизнесу контент-стратегия?",
        help="Текст запроса, который отправляется после картинки",
    )
    parser.add_argument(
        "--prompt-suffix",
        default="не используй титров и текстов в видео",
        help="Уточнение, добавляемое к каждой теме ролика",
    )
    parser.add_argument(
        "--order",
        choices=("image_first", "text_first"),
        default="image_first",
        help="Порядок отправки (по умолчанию: сначала картинка, затем текст)",
    )
    parser.add_argument(
        "--send-image",
        choices=("per_prompt", "once"),
        default="per_prompt",
        help="Отправлять картинку перед каждой фразой или один раз в начале",
    )
    parser.add_argument("--image-caption", default="", help="Подпись к изображению (если нужна)")
    parser.add_argument("--pre-command", default="", help="Команда перед запросом (например /video)")

    parser.add_argument("--disk-dir", default="disk/zavod/video", help="Папка на Яндекс.Диске")
    parser.add_argument(
        "--log-file",
        default="request_veo_video_to_yadisk.log",
        help="Файл текстового лога (относительно backend/scripts; '-' отключает запись)",
    )
    parser.add_argument(
        "--django-settings",
        default="config.settings.dev",
        help="DJANGO_SETTINGS_MODULE для сохранения в БД (по умолчанию config.settings.dev)",
    )

    parser.add_argument("--wait-seconds", type=int, default=600, help="Максимальное ожидание ответа бота (сек)")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Интервал поллинга истории (сек)")
    parser.add_argument("--max-videos-per-prompt", type=int, default=1, help="Сколько видео сохранять на одну фразу")
    parser.add_argument("--url-timeout", type=int, default=300, help="Таймаут скачивания видео по ссылке (сек)")
    parser.add_argument(
        "--sleep-between-prompts",
        type=float,
        default=1.0,
        help="Пауза перед следующим промптом после получения ссылки, сек",
    )
    parser.add_argument("--stop-on-error", action="store_true", help="Остановиться, если на фразу не пришло видео")
    parser.add_argument("--workers", type=int, default=2, help="Параллельная обработка скачивания/загрузки/БД")
    parser.add_argument(
        "--allow-media",
        action="store_true",
        help="Разрешить сохранять видео-файлы, присланные ботом как media (по умолчанию ждём ссылку)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    exported = asyncio.run(request_and_export(args))
    print()
    print("Готово, выгружено:")
    for item in exported:
        print(f"  - {item.disk_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
