from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from core.ai_generator import AIContentGenerator

from .config import config

logger = logging.getLogger(__name__)

_generator: Optional[AIContentGenerator] = None

PROMPT_TEXT = """Ты помогаешь улучшить поиск в RAG системе.
Дан документ и его фрагмент. Напиши краткий контекст (2-3 предложения) для этого фрагмента,
который поможет понять его место и смысл в документе.
Отвечай только контекстом, без вводных слов.

Документ:
{document}

Фрагмент:
{chunk}"""

PROMPT_TABLE = """Ты помогаешь улучшить поиск в RAG системе.
Дана таблица из документа. Напиши краткое описание (2-3 предложения):
что содержит таблица, какие данные, какой смысл несёт.
Отвечай только описанием, без вводных слов.

Документ:
{document}

Таблица (markdown):
{chunk}"""

PROMPT_FORMULA = """Ты помогаешь улучшить поиск в RAG системе.
Дана формула из документа. Напиши:
1. Словесный перевод формулы (что она вычисляет, что означают обозначения)
2. Зачем эта формула используется в контексте документа (1-2 предложения)
Отвечай только переводом и контекстом, без вводных слов.

Документ:
{document}

Формула (LaTeX):
{chunk}"""


def _get_generator() -> Optional[AIContentGenerator]:
    global _generator
    if _generator is not None:
        return _generator
    try:
        _generator = AIContentGenerator()
        return _generator
    except Exception as exc:  # pragma: no cover - network/env dependent
        logger.warning("RAG context generation disabled: failed to init AI generator: %s", exc)
        return None


def _build_prompt(document: str, chunk: str, chunk_type: str) -> str:
    if chunk_type == "table":
        return PROMPT_TABLE.format(document=document[:3000], chunk=chunk)
    if chunk_type == "formula":
        return PROMPT_FORMULA.format(document=document[:3000], chunk=chunk)
    return PROMPT_TEXT.format(document=document[:3000], chunk=chunk)


def generate_context(document: str, chunk: str, chunk_type: str = "text") -> str:
    if not config.context_enabled:
        return ""

    generator = _get_generator()
    if generator is None:
        return ""

    prompt = _build_prompt(document=document, chunk=chunk, chunk_type=chunk_type)
    try:
        # Uses default model first and falls back automatically only when needed.
        response = generator.get_ai_response(
            prompt,
            max_tokens=config.context_max_tokens,
            temperature=config.context_temperature,
            allow_fallback=True,
            timeout_seconds=config.context_timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - network/env dependent
        logger.warning("RAG context generation failed: %s", exc)
        return ""
    return (response or "").strip()


def generate_context_batch(
    document: str,
    chunks: list[str],
    chunk_types: list[str],
    concurrency: int | None = None,
) -> list[str]:
    if not chunks:
        return []

    worker_count = max(1, int(concurrency or config.context_concurrency))
    worker_count = min(worker_count, 16)
    if worker_count == 1:
        return [generate_context(document, chunk, ctype) for chunk, ctype in zip(chunks, chunk_types)]

    indexed_tasks = list(enumerate(zip(chunks, chunk_types)))
    results = [""] * len(indexed_tasks)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            (
                index,
                executor.submit(generate_context, document, chunk, chunk_type),
            )
            for index, (chunk, chunk_type) in indexed_tasks
        ]
        for index, future in futures:
            try:
                results[index] = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("RAG context generation future failed: %s", exc)
                results[index] = ""

    return results

