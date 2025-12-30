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
from typing import Iterable, List, Optional, Sequence, Tuple

import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    from telethon import TelegramClient
except Exception:  # pragma: no cover
    TelegramClient = None


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


def _download_video_url(url: str, timeout_s: int) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=timeout_s)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  ! не удалось скачать {url}: {exc}")
        return None

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "video" not in content_type and "octet-stream" not in content_type:
        body = ""
        try:
            body = resp.text or ""
        except Exception:
            body = ""
        mp4 = MP4_URL_RE.search(body)
        if mp4:
            return _download_video_url(mp4.group(0), timeout_s=timeout_s)
        print(f"  ! ссылка не выглядит как видео (Content-Type={content_type or 'unknown'}): {url}")
        return None

    fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(resp.content)
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

    print("Telegram:")
    print(f"  bot: {bot_username}")
    print(f"  session: {session_label}")
    print("Yandex Disk:")
    print(f"  dir: {args.disk_dir}")

    client = TelegramClient(session_base, api_id_int, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram-сессия не авторизована. "
                "Сначала выполните: python backend/scripts/authorize_telegram.py --session-type collector"
            )

        bot = await client.get_entity(bot_username)

        scanned_messages = 0
        found_videos = 0
        downloaded_videos = 0
        uploaded_videos = 0
        skipped_videos = 0
        errors = 0

        limit = args.limit if args.limit and args.limit > 0 else None
        oldest_first = bool(args.oldest_first)
        only_incoming = bool(args.only_incoming)

        async for msg in client.iter_messages(bot, limit=limit, reverse=oldest_first):
            scanned_messages += 1

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

            per_message_sources: List[Tuple[str, str]] = []
            if _is_video_message(msg):
                ext = ".mp4"
                file_obj = getattr(msg, "file", None)
                msg_ext = getattr(file_obj, "ext", None)
                if isinstance(msg_ext, str) and msg_ext:
                    ext = msg_ext
                per_message_sources.append(("media", ext))

            for mp4_url in _extract_mp4_urls_from_message(msg):
                per_message_sources.append((mp4_url, ".mp4"))

            if not per_message_sources:
                continue

            print(f"[{msg_id}] найдено источников видео: {len(per_message_sources)}")

            for idx, (source, ext) in enumerate(per_message_sources, start=1):
                found_videos += 1
                remote_path = _build_remote_path(
                    disk_dir=args.disk_dir,
                    bot_username=bot_username,
                    msg_id=msg_id,
                    msg_date=msg_date,
                    index=(idx if len(per_message_sources) > 1 else 0),
                    ext=ext,
                )

                if args.dry_run:
                    print(f"  - dry-run: {source} -> {remote_path}")
                    skipped_videos += 1
                    continue

                local_path: Optional[str] = None
                try:
                    if source == "media":
                        fd, tmp_path = tempfile.mkstemp(suffix=ext if ext.startswith(".") else ".mp4")
                        os.close(fd)
                        downloaded = await client.download_media(msg, file=tmp_path)
                        if not downloaded or not os.path.exists(downloaded):
                            print("  ! не удалось скачать медиа из сообщения")
                            errors += 1
                            continue
                        local_path = str(downloaded)
                    else:
                        local_path = _download_video_url(source, timeout_s=args.url_timeout)
                        if not local_path:
                            errors += 1
                            continue

                    downloaded_videos += 1
                    upload_file(local_path=local_path, disk_path=remote_path)
                    uploaded_videos += 1
                except Exception as exc:
                    errors += 1
                    print(f"  ! ошибка при обработке видео: {exc}")
                finally:
                    if local_path and os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except OSError:
                            pass

                if args.sleep and args.sleep > 0:
                    await asyncio.sleep(args.sleep)

            if args.max_videos and uploaded_videos >= args.max_videos:
                print(f"Достигнут лимит --max-videos={args.max_videos}, остановка.")
                break

        return ExportStats(
            scanned_messages=scanned_messages,
            found_videos=found_videos,
            downloaded_videos=downloaded_videos,
            uploaded_videos=uploaded_videos,
            skipped_videos=skipped_videos,
            errors=errors,
        )
    finally:
        await client.disconnect()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Экспорт видео из переписки с ботом на Яндекс.Диск")
    parser.add_argument("--bot", default=None, help="Username бота (например @syntxaibot)")

    parser.add_argument("--api-id", dest="api_id", default=None, help="TELEGRAM_API_ID (если не из env)")
    parser.add_argument("--api-hash", dest="api_hash", default=None, help="TELEGRAM_API_HASH (если не из env)")

    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument("--session-path", default=None, help="Путь к .session файлу (или к базе без .session)")
    session_group.add_argument("--session-name", default=None, help="Имя/путь сессии Telethon (без .session)")

    parser.add_argument("--disk-dir", default="disk/zavod/video", help="Папка на Яндекс.Диске")
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
