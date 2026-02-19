from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChunkType = Literal["text", "table", "formula", "code"]


@dataclass
class ParsedChunk:
    content: str
    chunk_type: ChunkType


def _extract_text(node: object) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    content = node.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(_extract_text(item) for item in content)


def _parse_table(node: dict) -> str:
    rows: list[list[str]] = []
    for row in node.get("content", []):
        if not isinstance(row, dict):
            continue
        cells: list[str] = []
        for cell in row.get("content", []):
            if not isinstance(cell, dict):
                continue
            cells.append(_extract_text(cell).strip())
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    header = rows[0]
    header_row = "| " + " | ".join(header) + " |"
    separator_row = "| " + " | ".join(["---"] * len(header)) + " |"
    data_rows = ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join([header_row, separator_row] + data_rows)


def _parse_list(node: dict, ordered: bool) -> str:
    lines: list[str] = []
    for index, item in enumerate(node.get("content", []), start=1):
        text = _extract_text(item).strip()
        if not text:
            continue
        prefix = f"{index}." if ordered else "-"
        lines.append(f"{prefix} {text}")
    return "\n".join(lines)


def parse_tiptap(doc: dict) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    text_buffer: list[str] = []

    def flush_text() -> None:
        text = "\n\n".join(line for line in text_buffer if line).strip()
        text_buffer.clear()
        if text:
            chunks.append(ParsedChunk(content=text, chunk_type="text"))

    for node in doc.get("content", []):
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")

        if node_type in {"paragraph", "heading", "blockquote"}:
            text = _extract_text(node).strip()
            if text:
                text_buffer.append(text)
            continue

        if node_type in {"bulletList", "taskList"}:
            flush_text()
            content = _parse_list(node, ordered=False)
            if content:
                chunks.append(ParsedChunk(content=content, chunk_type="text"))
            continue

        if node_type == "orderedList":
            flush_text()
            content = _parse_list(node, ordered=True)
            if content:
                chunks.append(ParsedChunk(content=content, chunk_type="text"))
            continue

        if node_type == "table":
            flush_text()
            table_md = _parse_table(node)
            if table_md:
                chunks.append(ParsedChunk(content=table_md, chunk_type="table"))
            continue

        if node_type == "math":
            flush_text()
            latex = str(node.get("attrs", {}).get("latex", "")).strip()
            if latex:
                chunks.append(ParsedChunk(content=latex, chunk_type="formula"))
            continue

        if node_type == "codeBlock":
            flush_text()
            code = _extract_text(node).strip()
            if not code:
                continue
            lang = str(node.get("attrs", {}).get("language", "")).strip()
            content = f"```{lang}\n{code}\n```" if lang else f"```\n{code}\n```"
            chunks.append(ParsedChunk(content=content, chunk_type="code"))
            continue

    flush_text()
    return chunks

