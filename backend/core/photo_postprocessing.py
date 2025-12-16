import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONT_SIZE = 64
YELLOW_COLOR = "#FFFF00"  # Желтый цвет
WHITE_COLOR = "#FFFFFF"  # Белый цвет
DEFAULT_MAX_CHARS = 20

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FONT_RELATIVE = Path("backend/staticfiles/fonts/Gotham/gotham_medium.otf")
SYSTEM_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/System/Library/Fonts/SFNSBold.ttf"),
    Path("/System/Library/Fonts/SFNSText-Bold.otf"),
    Path("/System/Library/Fonts/SFNSDisplay-Bold.otf"),
]


def _resolve_font_path(font_path: Optional[str] = None) -> Optional[str]:
    """Найти подходящий шрифт для текста."""
    candidates: list[Path] = []
    if font_path:
        candidates.append(Path(font_path).expanduser())
    candidates.append(REPO_ROOT / DEFAULT_FONT_RELATIVE)
    candidates.extend(SYSTEM_FONT_CANDIDATES)

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return None


def wrap_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Обернуть текст по словам с учетом максимальной длины строки."""
    if not text:
        return ""

    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        if len(current_line + " " + word) <= max_chars:
            current_line = (current_line + " " + word).strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


def apply_text_overlay_to_image(
    input_image_path: str,
    text: str,
    font_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Нанести текст на изображение (все слова в CAPS LOCK, одно желтое, остальные белые).

    Args:
        input_image_path: Путь к входному изображению
        text: Текст для нанесения (все слова будут нанесены)
        font_path: Путь к шрифту (опционально)
        output_path: Путь для сохранения результата (опционально)

    Returns:
        Dict с результатом обработки
    """
    if not text or not text.strip():
        return {"success": False, "error": "Текст для нанесения не указан"}

    if not os.path.exists(input_image_path):
        return {"success": False, "error": f"Изображение {input_image_path} не найдено"}

    resolved_font = _resolve_font_path(font_path)
    if not resolved_font:
        return {"success": False, "error": "Шрифт для текста не найден"}

    try:
        # Открыть изображение
        image = Image.open(input_image_path)
        draw = ImageDraw.Draw(image)

        # Загрузить шрифт
        font = ImageFont.truetype(resolved_font, FONT_SIZE)

        # Получить все слова и преобразовать в верхний регистр
        words = [word.upper() for word in text.strip().split() if word.strip()]
        if not words:
            return {"success": False, "error": "Текст не содержит слов"}

        # Ограничить до 3 слов максимум
        if len(words) > 3:
            words = words[:3]

        logger.info(f"Нанесение слов на изображение: {words}")

        # Выбрать случайное слово для желтого цвета
        import random
        yellow_word_index = random.randint(0, len(words) - 1)
        logger.info(f"Желтое слово: '{words[yellow_word_index]}' (индекс {yellow_word_index})")

        # Создать строку для отображения (слова через пробел или перенос)
        display_text = " ".join(words)
        wrapped_text = wrap_text(display_text, max_chars=DEFAULT_MAX_CHARS)

        # Разделить обернутый текст на строки
        lines = wrapped_text.split('\n')

        # Получить размеры всего блока текста
        total_bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
        block_width = total_bbox[2] - total_bbox[0]
        block_height = total_bbox[3] - total_bbox[1]

        # Вычислить позицию блока (центр по горизонтали, 75% высоты)
        image_width, image_height = image.size
        block_x = (image_width - block_width) // 2
        block_y = int(image_height * 0.75) - block_height // 2
        block_y = max(0, min(block_y, image_height - block_height))  # <-- важно

        # Нанести каждую строку
        current_y = block_y
        for line in lines:
            line_bbox = draw.textbbox((0, 0), line, font=font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = (image_width - line_width) // 2  # Центрировать строку

            # Разделить строку на слова для индивидуального окрашивания
            line_words = line.split()
            word_x = line_x

            for word_idx, word in enumerate(line_words):
                # Определить цвет слова
                global_word_idx = sum(len(lines[j].split()) for j in range(lines.index(line))) + word_idx
                if global_word_idx == yellow_word_index:
                    text_color = YELLOW_COLOR
                    logger.info(f"Нанесение желтого слова: '{word}' на позиции ({word_x}, {current_y})")
                else:
                    text_color = WHITE_COLOR

                # Получить размеры слова
                word_bbox = draw.textbbox((0, 0), word, font=font)
                word_width = word_bbox[2] - word_bbox[0]

                # Нанести черную обводку для слова
                for offset_x in [-1, 0, 1]:
                    for offset_y in [-1, 0, 1]:
                        if offset_x == 0 and offset_y == 0:
                            continue
                        draw.text((word_x + offset_x, current_y + offset_y), word, font=font, fill="black")

                # Нанести слово с выбранным цветом
                draw.text((word_x, current_y), word, font=font, fill=text_color)

                # Перейти к следующему слову
                word_x += word_width + draw.textbbox((0, 0), " ", font=font)[2]

            line_h = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
            current_y += line_h + 10

        # Сохранить результат
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            image.save(output_path)
            result_path = output_path
        else:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            image.save(temp_path)
            result_path = temp_path

        logger.info(f"Текст нанесен на изображение: {result_path}")
        return {
            "success": True,
            "image_path": result_path,
            "words_used": words,
            "yellow_word": words[yellow_word_index],
            "yellow_word_index": yellow_word_index
        }

    except Exception as exc:
        logger.error(f"Ошибка при нанесении текста на изображение: {exc}", exc_info=True)
        return {"success": False, "error": f"Не удалось нанести текст: {str(exc)}"}
