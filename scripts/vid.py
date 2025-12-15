#!/usr/bin/env python3
"""
Utility script to test video overlays without regenerating clips every run.

Сценарий: 8 секунд / 4 сцены
1 сцена — заголовок
2–4 сцены — мини‑комментарии
"""

import argparse
import os
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.video_postprocessing import (
    apply_text_overlays_to_video,
    build_overlay_scenes_from_lines,
    build_overlay_scenes_from_post,
)

DEFAULT_VIDEO = PROJECT_ROOT / "backend" / "media" / "post_videos" / "post_66_a68c34d8.mp4"


def parse_args():
    parser = argparse.ArgumentParser(description="Apply captions to an existing video for quick testing.")
    parser.add_argument("--video", default=str(DEFAULT_VIDEO), help="Path to the base video")
    parser.add_argument(
        "--output",
        help="Destination path for the processed video. Defaults to <video>_captioned.mp4",
    )
    parser.add_argument(
        "--title",
        default="Ты теряешь внимание зрителя",
        help="Title text for the first scene (0–2 сек).",
    )
    parser.add_argument(
        "--body",
        default=(
            "Первые 2 секунды решают всё.\n"
            "Статичный текст сразу пролистывают.\n"
            "Небольшое движение = больше удержания."
        ),
        help="Body text split into 3 scenes (2–4, 4–6, 6–8 сек).",
    )
    parser.add_argument(
        "--text",
        action="append",
        help="Explicit scene text (4 раза — по сценам).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    input_video = os.path.abspath(os.path.expanduser(args.video))
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
        overlay_scenes = build_overlay_scenes_from_lines(args.text)
    else:
        overlay_scenes = build_overlay_scenes_from_post(args.title, args.body)

    if not overlay_scenes:
        raise SystemExit("Нет текста для титров – проверьте ввод.")

    result = apply_text_overlays_to_video(input_video, overlay_scenes, output_path=output_path)
    if not result.get("success"):
        raise SystemExit(f"Ошибка постобработки: {result.get('error')}")

    print(f"Готово! Видео с титрами сохранено в {result.get('video_path')}")


if __name__ == "__main__":
    main()
