#!/usr/bin/env python3
"""
8 секунд / 4 сцены
1 сцена — заголовок
2–4 сцены — мини-комментарии

Fade-in/fade-out 0.5 сек.
Автоперенос по ширине — через libass (.ass) + subtitles filter.
Совместимо с Mac/Ubuntu (важно указать fontsdir).
"""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

FADE_DURATION = 0.5  # seconds

DEFAULT_FONT_MAC = "/Users/pavellebedev/Desktop/proj/zavod/backend/staticfiles/fonts/Inter/Inter-Regular.otf"
DEFAULT_FONT_UBUNTU_HINTS = [
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def build_overlay_scenes(title: str, body: str):
    body_lines = [line.strip() for line in body.splitlines() if line.strip()][:3]

    scenes = [{"text": title, "start": 0.0, "end": 2.0}]
    start = 2.0
    for line in body_lines:
        scenes.append({"text": line, "start": start, "end": start + 2.0})
        start += 2.0
    return scenes

def pick_default_font() -> str:
    if os.path.exists(DEFAULT_FONT_MAC):
        return DEFAULT_FONT_MAC
    for p in DEFAULT_FONT_UBUNTU_HINTS:
        if os.path.exists(p):
            return p
    return DEFAULT_FONT_MAC

def ass_time(t: float) -> str:
    # ASS time: H:MM:SS.cs (centiseconds)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def escape_ass_text(text: str) -> str:
    # ASS: спецсимволы
    # перенос строки — \N
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("{", r"\{").replace("}", r"\}")
    text = text.replace("\n", r"\N")
    return text

def generate_ass(
    scenes: list,
    ass_path: Path,
    play_res_x: int = 720,
    play_res_y: int = 1280,
    font_name: str = "Inter",
    font_size: int = 56,
    margin_lr: int = 60,   # поля слева/справа для переноса
    margin_v: int = 220,   # отступ от низа
    outline: int = 3,
    shadow: int = 0,
    fade_ms: int = 500,
):
    """
    WrapStyle: 2 = smart wrapping (обычно самое адекватное)
    Alignment: 2 = bottom-center
    PrimaryColour: &H00FFFFFF (BGR + alpha), white
    OutlineColour: &H00000000 black
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    for scene in scenes:
        start = ass_time(scene["start"])
        end = ass_time(scene["end"])
        txt = escape_ass_text(scene["text"])
        # \fad(in, out) в миллисекундах
        text_with_fx = rf"{{\fad({fade_ms},{fade_ms})}}{txt}"
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text_with_fx}\n")

    ass_path.write_text("".join(lines), encoding="utf-8")

def apply_ass_subtitles(
    input_video_path: str,
    output_path: str,
    ass_path: str,
    fontsdir: str,
) -> dict:
    if not os.path.exists(input_video_path):
        return {"success": False, "error": f"Input video not found: {input_video_path}"}
    if not os.path.exists(ass_path):
        return {"success": False, "error": f"ASS not found: {ass_path}"}
    if not os.path.isdir(fontsdir):
        return {"success": False, "error": f"fontsdir not found/dir: {fontsdir}"}

    # subtitles filter любит экранирование ':' в путях (через \:)
    def esc(p: str) -> str:
        return p.replace("\\", "\\\\").replace(":", "\\:")

    vf = f"subtitles={esc(ass_path)}:fontsdir={esc(fontsdir)}"

    cmd = [
        "ffmpeg", "-y", "-i", input_video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",
        output_path
    ]

    print("FFMPEG CMD:\n", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"FFmpeg failed: {e}"}

    return {"success": True, "video_path": output_path}

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Apply captions to an existing video (ASS/libass, with auto-wrap).")
    p.add_argument("--video", default=None, help="Path to the base video")
    p.add_argument("--output", default=None, help="Output path. Defaults to <video>_captioned.mp4")
    p.add_argument("--font", default=None, help="Path to font file (ttf/otf).")
    p.add_argument("--title", default="Ты теряешь внимание зрителя", help="Title (0–2 сек).")
    p.add_argument("--body", default=(
        "Первые 2 секунды решают всё.\n"
        "Статичный текст сразу пролистывают.\n"
        "Небольшое движение = больше удержания."
    ), help="3 lines -> scenes (2–4, 4–6, 6–8).")
    p.add_argument("--text", action="append", help="Explicit scene text (4 раза — по сценам).")

    # параметры переноса/позиции
    p.add_argument("--margin_lr", type=int, default=60, help="Left/right margins for wrapping.")
    p.add_argument("--margin_v", type=int, default=220, help="Bottom margin.")
    p.add_argument("--fontsize", type=int, default=56, help="Font size.")
    return p.parse_args()

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    args = parse_args()

    input_video = args.video or "/Users/pavellebedev/Desktop/proj/zavod/backend/media/post_videos/790165462.mp4"
    input_video = os.path.abspath(os.path.expanduser(input_video))
    if not os.path.exists(input_video):
        raise SystemExit(f"Видео {input_video} не найдено")

    if args.output:
        output_path = os.path.abspath(os.path.expanduser(args.output))
    else:
        base = Path(input_video)
        output_path = str(base.with_name(f"{base.stem}_captioned{base.suffix}"))

    font_path = os.path.abspath(os.path.expanduser(args.font)) if args.font else pick_default_font()
    if not os.path.exists(font_path):
        raise SystemExit(
            "Шрифт не найден. Укажи явно --font /path/to/font.ttf\n"
            f"Текущий: {font_path}"
        )

    # fontsdir должен быть директорией, где лежит файл шрифта
    fontsdir = str(Path(font_path).parent)

    if args.text:
        if len(args.text) != 4:
            raise SystemExit("При использовании --text нужно ровно 4 сцены")
        scenes = []
        start = 0.0
        for t in args.text:
            scenes.append({"text": t, "start": start, "end": start + 2.0})
            start += 2.0
    else:
        scenes = build_overlay_scenes(args.title, args.body)

    with tempfile.TemporaryDirectory(prefix="ffmpeg_ass_") as tmpdir:
        ass_path = Path(tmpdir) / "captions.ass"

        # Важно: font_name должен совпадать с реальным именем шрифта.
        # Для Inter чаще всего "Inter". Если вдруг не подхватится — скажешь, подстроим.
        generate_ass(
            scenes=scenes,
            ass_path=ass_path,
            play_res_x=720,
            play_res_y=1280,
            font_name="Inter",
            font_size=args.fontsize,
            margin_lr=args.margin_lr,
            margin_v=args.margin_v,
            outline=3,
            shadow=0,
            fade_ms=int(FADE_DURATION * 1000),
        )

        result = apply_ass_subtitles(
            input_video_path=input_video,
            output_path=output_path,
            ass_path=str(ass_path),
            fontsdir=fontsdir,
        )

    if not result.get("success"):
        raise SystemExit(f"Ошибка постобработки: {result.get('error')}")

    print(f"Готово! Видео с титрами сохранено в {output_path}")

if __name__ == "__main__":
    main()
