#!/usr/bin/env python3
"""
Utility script to test video overlays without regenerating clips every run.

Сценарий: 8 секунд / 4 сцены
1 сцена — заголовок
2–4 сцены — мини‑комментарии

Fade-in/fade-out 0.5 сек, локальный шрифт, совместимо с Mac/Ubuntu.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
import subprocess

FONT_PATH = "/Users/pavellebedev/Desktop/proj/zavod/backend/staticfiles/fonts/Inter/Inter-Regular.otf"
FADE_DURATION = 0.5  # seconds

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------

def normalize_text_for_ffmpeg(text: str) -> str:
    # Экранируем спецсимволы и пробелы для FFmpeg
    return (
        text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace(" ", "\\ ")
    )


def build_overlay_scenes(title: str, body: str):
    body_lines = [line.strip() for line in body.splitlines() if line.strip()][:3]

    scenes = []
    scenes.append({"text": normalize_text_for_ffmpeg(title), "start": 0.0, "end": 2.0})

    start = 2.0
    for line in body_lines:
        scenes.append({"text": normalize_text_for_ffmpeg(line), "start": start, "end": start + 2.0})
        start += 2.0

    return scenes


def apply_text_overlays_to_video(input_video_path: str, scenes: list, font_path: str = FONT_PATH) -> dict:
    if not os.path.exists(input_video_path):
        return {"success": False, "error": f"Input video not found: {input_video_path}"}
    if not os.path.exists(font_path):
        return {"success": False, "error": f"Font not found: {font_path}"}

    drawtext_filters = []
    for scene in scenes:
        text = scene['text']
        start = scene['start']
        end = scene['end']
        alpha_expr = f"if(lt(t,{start+FADE_DURATION}),(t-{start})/{FADE_DURATION},if(lt(t,{end-FADE_DURATION}),1,({end}-t)/{FADE_DURATION}))"
        drawtext_filters.append(
            f"drawtext=fontfile={font_path}:text={text}:fontsize=56:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)*0.75:alpha='{alpha_expr}':enable='between(t,{start},{end})'"
        )

    filter_complex = ','.join(drawtext_filters)

    base = Path(input_video_path)
    output_path = str(base.with_name(f"{base.stem}_captioned{base.suffix}"))

    cmd = [
        "ffmpeg", "-y", "-i", input_video_path,
        "-vf", filter_complex,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", output_path
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
    parser = argparse.ArgumentParser(description="Apply captions to an existing video for quick testing.")
    parser.add_argument("--video", default=None, help="Path to the base video")
    parser.add_argument("--output", help="Destination path for the processed video. Defaults to <video>_captioned.mp4")
    parser.add_argument("--title", default="Ты теряешь внимание зрителя", help="Title text for the first scene (0–2 сек).")
    parser.add_argument("--body", default=(
        "Первые 2 секунды решают всё.\n"
        "Статичный текст сразу пролистывают.\n"
        "Небольшое движение = больше удержания."), help="Body text split into 3 scenes (2–4, 4–6, 6–8 сек).")
    parser.add_argument("--text", action="append", help="Explicit scene text (4 раза — по сценам).")
    return parser.parse_args()

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

    if args.text:
        if len(args.text) != 4:
            raise SystemExit("При использовании --text нужно ровно 4 сцены")
        overlay_texts = []
        start = 0.0
        for text in args.text:
            overlay_texts.append({"text": normalize_text_for_ffmpeg(text), "start": start, "end": start + 2.0})
            start += 2.0
    else:
        overlay_texts = build_overlay_scenes(args.title, args.body)

    result = apply_text_overlays_to_video(input_video, overlay_texts)
    if not result.get("success"):
        raise SystemExit(f"Ошибка постобработки: {result.get('error')}")

    ffmpeg_output = result.get("video_path")
    if ffmpeg_output != output_path:
        shutil.move(ffmpeg_output, output_path)

    print(f"Готово! Видео с титрами сохранено в {output_path}")

if __name__ == "__main__":
    main()
