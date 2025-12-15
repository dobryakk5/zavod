#!/usr/bin/env python3
"""
Utility script to test video overlays without regenerating clips every run.

Usage:
    python scripts/test_video_overlay.py --title "My title" --body "long text"
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.video_postprocessing import (
    apply_text_overlays_to_video,
    build_overlay_scenes_from_lines,
    build_overlay_scenes_from_post,
)

DEFAULT_VIDEO = str(PROJECT_ROOT / "backend" / "media" / "post_videos" / "post_66_a68c34d8.mp4")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply captions to an existing video for quick testing.")
    parser.add_argument(
        "--video",
        default=DEFAULT_VIDEO,
        help=f"Path to the base video (default: {DEFAULT_VIDEO})",
    )
    parser.add_argument(
        "--output",
        help="Destination path for the processed video. Defaults to <video>_captioned.mp4",
    )
    parser.add_argument(
        "--title",
        default="Тестовый заголовок",
        help="Title text for the first scene.",
    )
    parser.add_argument(
        "--body",
        default="Первая мысль о продукте.\nКороткий call-to-action в конце.",
        help="Body text that will fill the remaining scenes.",
    )
    parser.add_argument(
        "--text",
        action="append",
        help="Explicit scene text. Provide multiple --text flags to override auto generation.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_video = os.path.abspath(os.path.expanduser(args.video))
    if not os.path.exists(input_video):
        raise SystemExit(f"Видео {input_video} не найдено. Укажите корректный путь через --video.")

    output_path = args.output
    if not output_path:
        base = Path(input_video)
        output_path = str(base.with_name(f"{base.stem}_captioned{base.suffix}"))
    output_path = os.path.abspath(os.path.expanduser(output_path))

    if args.text:
        scenes = build_overlay_scenes_from_lines(args.text)
    else:
        scenes = build_overlay_scenes_from_post(args.title, args.body)

    result = apply_text_overlays_to_video(input_video, scenes, output_path=output_path)
    if not result.get("success"):
        raise SystemExit(f"Ошибка постобработки: {result.get('error')}")

    final_path = result.get("video_path")
    print(f"Готово! Видео с титрами сохранено в {final_path}")


if __name__ == "__main__":
    main()
