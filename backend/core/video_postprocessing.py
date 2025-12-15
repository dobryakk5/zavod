import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SCENE_DURATION = 2.0
FADE_DURATION = 0.5
FONT_SIZE = 56
DEFAULT_MAX_CHARS = 22
MAX_LINES_PER_SCENE = 3

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FONT_RELATIVE = Path("backend/staticfiles/fonts/Inter/Inter-Regular.otf")
SYSTEM_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/System/Library/Fonts/SFNS.ttf"),
    Path("/System/Library/Fonts/SFNSText.ttf"),
    Path("/System/Library/Fonts/SFNSDisplay.ttf"),
]


def _normalize_manual_breaks(value: Optional[str]) -> str:
    if not value:
        return ""
    text = value.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.replace("\\r", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("=n", "\n").replace("=N", "\n")
    text = re.sub(r"([А-Яа-яЁё0-9])n([А-Яа-яЁё0-9])", r"\1\n\2", text)
    return text


def wrap_and_clamp(text: str, width_chars: int = DEFAULT_MAX_CHARS, max_lines: int = MAX_LINES_PER_SCENE) -> str:
    normalized = _normalize_manual_breaks(text)
    if not normalized:
        return ""

    cleaned = " ".join(normalized.split())
    if not cleaned:
        return ""

    words = cleaned.split(" ")
    lines: List[str] = []
    current_line = ""

    for word in words:
        segment = word
        while segment:
            if len(segment) <= width_chars:
                candidate = segment
                segment = ""
            else:
                candidate = segment[:width_chars]
                segment = segment[width_chars:]

            if not current_line:
                current_line = candidate
            else:
                tentative = f"{current_line} {candidate}"
                if len(tentative) <= width_chars:
                    current_line = tentative
                else:
                    lines.append(current_line)
                    if len(lines) >= max_lines:
                        current_line = candidate[: width_chars - 1] + "…"
                        return "\n".join(lines[: max_lines - 1] + [current_line])
                    current_line = candidate

            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break

    if current_line and len(lines) < max_lines:
        lines.append(current_line)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    total_words_text = " ".join(words)
    total_lines_text = " ".join(lines)
    if len(total_lines_text) < len(total_words_text):
        last_line = lines[-1]
        if len(last_line) >= 2:
            last_line = last_line[:-1].rstrip()
        lines[-1] = last_line + "…"

    return "\n".join(lines)


def build_overlay_scenes_from_post(title: Optional[str], body: Optional[str]) -> List[Dict[str, float]]:
    normalized_title = _normalize_manual_breaks(title or "")
    normalized_body = _normalize_manual_breaks(body or "")
    body_lines = [line.strip() for line in normalized_body.splitlines() if line.strip()][:3]

    scenes: List[Dict[str, float]] = [
        {"text": normalized_title, "start": 0.0, "end": SCENE_DURATION}
    ]

    start = SCENE_DURATION
    for line in body_lines:
        scenes.append({"text": line, "start": start, "end": start + SCENE_DURATION})
        start += SCENE_DURATION

    return scenes


def build_overlay_scenes_from_lines(lines: Sequence[str]) -> List[Dict[str, float]]:
    scenes: List[Dict[str, float]] = []
    start = 0.0
    for text in lines:
        normalized = _normalize_manual_breaks(text or "")
        scenes.append({"text": normalized, "start": start, "end": start + SCENE_DURATION})
        start += SCENE_DURATION
    return scenes


def _resolve_font_path(font_path: Optional[str] = None) -> Optional[str]:
    candidates: List[Path] = []
    if font_path:
        candidates.append(Path(font_path).expanduser())
    env_font = os.getenv("VIDEO_OVERLAY_FONT_PATH")
    if env_font:
        candidates.append(Path(env_font).expanduser())
    candidates.append(REPO_ROOT / DEFAULT_FONT_RELATIVE)
    candidates.extend(SYSTEM_FONT_CANDIDATES)

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return None


def _write_temp_textfile(content: str) -> Tuple[str, tempfile.NamedTemporaryFile]:
    temp = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False, encoding="utf-8")
    temp.write(content)
    temp.flush()
    return temp.name, temp


def apply_text_overlays_to_video(
    input_video_path: str,
    scenes: Sequence[Dict[str, float]],
    font_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    if not scenes:
        return {"success": False, "error": "Нет сцен для титров"}
    if not os.path.exists(input_video_path):
        return {"success": False, "error": f"Видео {input_video_path} не найдено"}

    resolved_font = _resolve_font_path(font_path)
    if not resolved_font:
        return {"success": False, "error": "Шрифт для титров не найден"}

    max_chars_per_line = DEFAULT_MAX_CHARS
    text_files: List[tempfile.NamedTemporaryFile] = []
    drawtext_filters: List[str] = []

    try:
        for scene in scenes:
            raw_text = scene.get("text") or ""
            wrapped_text = wrap_and_clamp(raw_text, width_chars=max_chars_per_line, max_lines=MAX_LINES_PER_SCENE)
            textfile_path, temp_file = _write_temp_textfile(wrapped_text)
            text_files.append(temp_file)
            start = scene["start"]
            end = scene["end"]
            alpha_expr = (
                f"if(lt(t,{start + FADE_DURATION}),"
                f"(t-{start})/{FADE_DURATION},"
                f"if(lt(t,{end - FADE_DURATION}),1,({end}-t)/{FADE_DURATION}))"
            )
            drawtext_filters.append(
                f"drawtext=fontfile={resolved_font}:"
                f"textfile='{textfile_path}':reload=1:"
                f"fontsize={FONT_SIZE}:"
                f"fontcolor=white:"
                f"borderw=2:"
                f"bordercolor=black:"
                f"x=(w-text_w)/2:"
                f"y=(h-text_h)*0.75:"
                f"alpha='{alpha_expr}':"
                f"enable='between(t,{start},{end})'"
            )

        filter_complex = ",".join(drawtext_filters)

        if output_path:
            dest_path = os.path.abspath(os.path.expanduser(output_path))
            dir_name = os.path.dirname(dest_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        else:
            fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            dest_path = temp_path

        command = [
            "ffmpeg",
            "-y",
            "-i",
            input_video_path,
            "-vf",
            filter_complex,
            "-c:v",
            "libx264",
            "-preset",
            os.getenv("VIDEO_OVERLAY_PRESET", "medium"),
            "-crf",
            os.getenv("VIDEO_OVERLAY_CRF", "18"),
            "-c:a",
            "copy",
            dest_path,
        ]

        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "FFmpeg drawtext failed: %s\nSTDERR: %s",
            exc,
            (exc.stderr or b"").decode(errors="ignore"),
        )
        if not output_path and 'dest_path' in locals() and os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return {"success": False, "error": "Не удалось наложить титры на видео"}
    except FileNotFoundError:
        if not output_path and 'dest_path' in locals() and os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return {"success": False, "error": "Команда ffmpeg не найдена"}
    finally:
        for temp_file in text_files:
            try:
                temp_file.close()
                os.unlink(temp_file.name)
            except OSError:
                pass

    return {"success": True, "video_path": dest_path}
