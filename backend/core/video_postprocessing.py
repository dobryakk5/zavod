import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

SCENE_DURATION = 2.0
FADE_DURATION = 0.5

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
    """Convert escaped sequences (\\n, =n, кириллическое n) to actual newlines."""
    if not value:
        return ""
    text = value.replace("\\r\\n", "\n").replace("\\n", "\n")
    text = text.replace("\\r", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("=n", "\n").replace("=N", "\n")
    text = re.sub(r"([А-Яа-яЁё0-9])n([А-Яа-яЁё0-9])", r"\1\n\2", text)
    return text


def normalize_text_for_ffmpeg(text: str) -> str:
    value = (text or "").strip()
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace(" ", "\\ ")
    )


def build_overlay_scenes_from_post(title: Optional[str], body: Optional[str]) -> List[Dict[str, float]]:
    normalized_title = _normalize_manual_breaks(title or "")
    normalized_body = _normalize_manual_breaks(body or "")
    body_lines = [line.strip() for line in normalized_body.splitlines() if line.strip()][:3]

    scenes: List[Dict[str, float]] = [
        {"text": normalize_text_for_ffmpeg(normalized_title), "start": 0.0, "end": SCENE_DURATION}
    ]

    start = SCENE_DURATION
    for line in body_lines:
        scenes.append({"text": normalize_text_for_ffmpeg(line), "start": start, "end": start + SCENE_DURATION})
        start += SCENE_DURATION

    return scenes


def build_overlay_scenes_from_lines(lines: Sequence[str]) -> List[Dict[str, float]]:
    scenes: List[Dict[str, float]] = []
    start = 0.0
    for text in lines:
        normalized = _normalize_manual_breaks(text or "")
        scenes.append({"text": normalize_text_for_ffmpeg(normalized), "start": start, "end": start + SCENE_DURATION})
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

    drawtext_filters: List[str] = []
    for scene in scenes:
        text = scene["text"]
        start = scene["start"]
        end = scene["end"]
        alpha_expr = (
            f"if(lt(t,{start + FADE_DURATION}),"
            f"(t-{start})/{FADE_DURATION},"
            f"if(lt(t,{end - FADE_DURATION}),1,({end}-t)/{FADE_DURATION}))"
        )
        # Экранируем специальные символы в тексте для FFmpeg
        escaped_text = text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
        drawtext_filters.append(
            f"drawtext=fontfile={resolved_font}:"
            f"text='{escaped_text}':"
            f"fontsize=56:"
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

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "FFmpeg drawtext failed: %s\nSTDERR: %s",
            exc,
            (exc.stderr or b"").decode(errors="ignore"),
        )
        if not output_path and dest_path and os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return {"success": False, "error": "Не удалось наложить титры на видео"}
    except FileNotFoundError:
        if not output_path and dest_path and os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return {"success": False, "error": "Команда ffmpeg не найдена"}

    return {"success": True, "video_path": dest_path}
