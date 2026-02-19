# RAG Package

## Структура

```
myproject/
├── manage.py
├── myproject/
│   └── settings.py
└── rag/                        # ← папка пакета
    ├── __init__.py
    ├── config.py
    ├── db.py
    ├── embedder.py
    ├── context.py
    ├── tiptap_parser.py        # ← парсер TipTap JSON
    ├── ingestion.py
    ├── retrieval.py
    └── django_integration/
        ├── __init__.py
        ├── views.py
        ├── serializers.py
        └── urls.py
```

---

## Установка зависимостей

```bash
pip install asyncpg pgvector sentence-transformers openai
```

В `settings.py` добавь:

```python
RAG_CONFIG = {
    "PG_DSN": "postgresql://user:pass@localhost:5432/rag",
    "DEEPSEEK_API_KEY": "your_key",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "DEEPSEEK_MODEL": "deepseek-chat",
    "E5_MODEL": "intfloat/multilingual-e5-small",
    "CHUNK_SIZE": 512,
    "CHUNK_OVERLAP": 64,
    "RRF_K": 60,
    "TOP_K": 10,
}
```

---

## SQL — инициализация БД

Выполни один раз перед запуском:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE documents (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chunks (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    prev_chunk_id   INTEGER REFERENCES chunks(id),
    next_chunk_id   INTEGER REFERENCES chunks(id),
    content         TEXT NOT NULL,
    context         TEXT,
    chunk_type      TEXT NOT NULL DEFAULT 'text', -- text | table | formula | code
    content_vector  vector(384),
    ts_content      TSVECTOR,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_vector ON chunks
    USING hnsw (content_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_ts ON chunks USING GIN(ts_content);

CREATE OR REPLACE FUNCTION update_ts_content() RETURNS trigger AS $$
BEGIN
    NEW.ts_content := to_tsvector('russian', NEW.content || ' ' || COALESCE(NEW.context, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ts_content
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW EXECUTE FUNCTION update_ts_content();

-- Таблица источника для миграции
CREATE TABLE source_documents (
    id        SERIAL PRIMARY KEY,
    title     TEXT NOT NULL,
    content   TEXT NOT NULL,
    migrated  BOOLEAN DEFAULT FALSE
);
```

---

## rag/config.py

```python
from django.conf import settings

cfg = settings.RAG_CONFIG

class Config:
    pg_dsn          = cfg["PG_DSN"]
    deepseek_api_key = cfg["DEEPSEEK_API_KEY"]
    deepseek_base_url = cfg["DEEPSEEK_BASE_URL"]
    deepseek_model  = cfg["DEEPSEEK_MODEL"]
    e5_model        = cfg["E5_MODEL"]
    chunk_size      = cfg["CHUNK_SIZE"]
    chunk_overlap   = cfg["CHUNK_OVERLAP"]
    rrf_k           = cfg["RRF_K"]
    top_k           = cfg["TOP_K"]

config = Config()
```

---

## rag/db.py

```python
import asyncpg
from .config import config

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.pg_dsn)
    return _pool
```

---

## rag/embedder.py

```python
from sentence_transformers import SentenceTransformer
from .config import config

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(config.e5_model)
    return _model

def embed(texts: list[str]) -> list[list[float]]:
    prefixed = [f"passage: {t}" for t in texts]
    return get_model().encode(prefixed, normalize_embeddings=True).tolist()

def embed_query(text: str) -> list[float]:
    return get_model().encode(f"query: {text}", normalize_embeddings=True).tolist()
```

---

## rag/context.py

```python
import asyncio
from openai import AsyncOpenAI
from .config import config

client = AsyncOpenAI(
    api_key=config.deepseek_api_key,
    base_url=config.deepseek_base_url
)

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


async def _call_llm(prompt: str) -> str:
    resp = await client.chat.completions.create(
        model=config.deepseek_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.0
    )
    return resp.choices[0].message.content.strip()


async def generate_context(document: str, chunk: str, chunk_type: str = "text") -> str:
    if chunk_type == "table":
        prompt = PROMPT_TABLE.format(document=document[:3000], chunk=chunk)
    elif chunk_type == "formula":
        prompt = PROMPT_FORMULA.format(document=document[:3000], chunk=chunk)
    else:
        prompt = PROMPT_TEXT.format(document=document[:3000], chunk=chunk)

    return await _call_llm(prompt)


async def generate_context_batch(
    document: str,
    chunks: list[str],
    chunk_types: list[str],
    concurrency: int = 5
) -> list[str]:
    sem = asyncio.Semaphore(concurrency)

    async def _one(chunk, chunk_type):
        async with sem:
            return await generate_context(document, chunk, chunk_type)

    return await asyncio.gather(*[_one(c, t) for c, t in zip(chunks, chunk_types)])
```

---

## rag/tiptap_parser.py

```python
from dataclasses import dataclass
from typing import Literal

ChunkType = Literal["text", "table", "formula", "code"]

@dataclass
class ParsedChunk:
    content: str
    chunk_type: ChunkType


def _extract_text(node: dict) -> str:
    if node.get("type") == "text":
        return node.get("text", "")
    return "".join(_extract_text(c) for c in node.get("content", []))


def _parse_table(node: dict) -> str:
    rows = []
    for row in node.get("content", []):
        cells = []
        for cell in row.get("content", []):
            cells.append(_extract_text(cell).strip())
        rows.append("| " + " | ".join(cells) + " |")

    if not rows:
        return ""

    separator = "| " + " | ".join(["---"] * rows[0].count("|")) + " |"
    rows.insert(1, separator)
    return "\n".join(rows)


def _parse_list(node: dict, ordered: bool = False) -> str:
    items = []
    for i, item in enumerate(node.get("content", [])):
        text = _extract_text(item).strip()
        prefix = f"{i + 1}." if ordered else "-"
        items.append(f"{prefix} {text}")
    return "\n".join(items)


def parse_tiptap(doc: dict) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    text_buffer: list[str] = []

    def flush_text():
        text = "\n\n".join(text_buffer).strip()
        if text:
            chunks.append(ParsedChunk(content=text, chunk_type="text"))
        text_buffer.clear()

    for node in doc.get("content", []):
        t = node.get("type")

        if t in ("paragraph", "heading", "blockquote"):
            text = _extract_text(node).strip()
            if text:
                text_buffer.append(text)

        elif t in ("bulletList", "taskList"):
            flush_text()
            md = _parse_list(node, ordered=False)
            if md:
                chunks.append(ParsedChunk(content=md, chunk_type="text"))

        elif t == "orderedList":
            flush_text()
            md = _parse_list(node, ordered=True)
            if md:
                chunks.append(ParsedChunk(content=md, chunk_type="text"))

        elif t == "table":
            flush_text()
            md = _parse_table(node)
            if md:
                chunks.append(ParsedChunk(content=md, chunk_type="table"))

        elif t == "math":
            flush_text()
            latex = node.get("attrs", {}).get("latex", "")
            if latex:
                chunks.append(ParsedChunk(content=latex, chunk_type="formula"))

        elif t == "codeBlock":
            flush_text()
            code = _extract_text(node).strip()
            lang = node.get("attrs", {}).get("language", "")
            content = f"```{lang}\n{code}\n```" if lang else f"```\n{code}\n```"
            if code:
                chunks.append(ParsedChunk(content=content, chunk_type="code"))

    flush_text()
    return chunks
```

---

## rag/ingestion.py

```python
import json
from .db import get_pool
from .embedder import embed
from .context import generate_context_batch
from .tiptap_parser import parse_tiptap, ParsedChunk
from .config import config


def split_text_chunk(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + config.chunk_size
        chunks.append(text[start:end])
        start += config.chunk_size - config.chunk_overlap
    return chunks


def prepare_chunks(parsed: list[ParsedChunk]) -> list[ParsedChunk]:
    """
    Текстовые чанки дополнительно режем по chunk_size.
    Таблицы, формулы, код — всегда один чанк целиком.
    """
    result = []
    for p in parsed:
        if p.chunk_type == "text":
            for part in split_text_chunk(p.content):
                result.append(ParsedChunk(content=part, chunk_type="text"))
        else:
            result.append(p)
    return result


async def ingest_document(title: str, source: str, tiptap_json: dict) -> int:
    pool = await get_pool()

    parsed   = parse_tiptap(tiptap_json)
    chunks   = prepare_chunks(parsed)
    raw_text = " ".join(p.content for p in parsed if p.chunk_type == "text")

    contents    = [c.content for c in chunks]
    chunk_types = [c.chunk_type for c in chunks]
    contexts    = await generate_context_batch(raw_text, contents, chunk_types)

    # таблицы и формулы эмбеддим через context (summary/перевод), остальные через context + content
    combined = [
        ctx if ct in ("table", "formula") else f"{ctx}\n{ch}"
        for ch, ctx, ct in zip(contents, contexts, chunk_types)
    ]
    vectors  = embed(combined)

    async with pool.acquire() as conn:
        async with conn.transaction():
            doc_id = await conn.fetchval(
                "INSERT INTO documents(title, source) VALUES($1,$2) RETURNING id",
                title, source
            )

            chunk_ids = []
            for i, (chunk, ctx, vec) in enumerate(zip(chunks, contexts, vectors)):
                cid = await conn.fetchval(
                    """INSERT INTO chunks(document_id, chunk_index, content, context, content_vector, chunk_type)
                       VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",
                    doc_id, i, chunk.content, ctx, vec, chunk.chunk_type
                )
                chunk_ids.append(cid)

            for i, cid in enumerate(chunk_ids):
                prev_id = chunk_ids[i - 1] if i > 0 else None
                next_id = chunk_ids[i + 1] if i < len(chunk_ids) - 1 else None
                await conn.execute(
                    "UPDATE chunks SET prev_chunk_id=$1, next_chunk_id=$2 WHERE id=$3",
                    prev_id, next_id, cid
                )

    return doc_id


async def migrate_from_postgres():
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, tiptap_content
            FROM source_documents
            WHERE migrated = false
        """)

        for row in rows:
            tiptap = row['tiptap_content']
            if isinstance(tiptap, str):
                tiptap = json.loads(tiptap)

            await ingest_document(
                title=row['title'],
                source=str(row['id']),
                tiptap_json=tiptap
            )
            await conn.execute(
                "UPDATE source_documents SET migrated = true WHERE id = $1",
                row['id']
            )
```

---

## rag/retrieval.py

```python
from .db import get_pool
from .embedder import embed_query
from .config import config


async def search(query: str, top_k: int = None) -> list[dict]:
    top_k = top_k or config.top_k
    k = config.rrf_k
    pool = await get_pool()
    vec = embed_query(query)

    sql = """
    WITH vector_search AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY content_vector <=> $1::vector) AS rank
        FROM chunks
        ORDER BY content_vector <=> $1::vector
        LIMIT $2
    ),
    bm25_search AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(ts_content, query) DESC) AS rank
        FROM chunks, to_tsquery('russian', $3) query
        WHERE ts_content @@ query
        LIMIT $2
    ),
    rrf AS (
        SELECT
            COALESCE(v.id, b.id) AS id,
            COALESCE(1.0/(v.rank + $4), 0) + COALESCE(1.0/(b.rank + $4), 0) AS score
        FROM vector_search v
        FULL OUTER JOIN bm25_search b ON v.id = b.id
    )
    SELECT
        c.id,
        c.content,
        c.context,
        c.chunk_index,
        c.prev_chunk_id,
        c.next_chunk_id,
        d.title,
        d.source,
        r.score
    FROM rrf r
    JOIN chunks c ON c.id = r.id
    JOIN documents d ON d.id = c.document_id
    ORDER BY r.score DESC
    LIMIT $2
    """

    bm25_query = " & ".join(query.split())

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, vec, top_k, bm25_query, k)

    return [dict(r) for r in rows]
```

---

## rag/django_integration/serializers.py

```python
from rest_framework import serializers


class SearchRequestSerializer(serializers.Serializer):
    query   = serializers.CharField()
    top_k   = serializers.IntegerField(required=False, default=10)


class ChunkSerializer(serializers.Serializer):
    id            = serializers.IntegerField()
    content       = serializers.CharField()
    context       = serializers.CharField()
    chunk_index   = serializers.IntegerField()
    prev_chunk_id = serializers.IntegerField(allow_null=True)
    next_chunk_id = serializers.IntegerField(allow_null=True)
    title         = serializers.CharField()
    source        = serializers.CharField()
    score         = serializers.FloatField()


class MigrateResponseSerializer(serializers.Serializer):
    status  = serializers.CharField()
    message = serializers.CharField()
```

---

## rag/django_integration/views.py

```python
from adrf.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..retrieval import search
from ..ingestion import migrate_from_postgres
from .serializers import SearchRequestSerializer, ChunkSerializer, MigrateResponseSerializer


class SearchView(APIView):
    async def post(self, request):
        s = SearchRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        results = await search(
            query=s.validated_data["query"],
            top_k=s.validated_data["top_k"]
        )

        return Response(ChunkSerializer(results, many=True).data)


class MigrateView(APIView):
    async def post(self, request):
        try:
            await migrate_from_postgres()
            out = {"status": "ok", "message": "Миграция завершена"}
        except Exception as e:
            out = {"status": "error", "message": str(e)}
            return Response(
                MigrateResponseSerializer(out).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(MigrateResponseSerializer(out).data)
```

---

## rag/django_integration/urls.py

```python
from django.urls import path
from .views import SearchView, MigrateView

urlpatterns = [
    path("search/",  SearchView.as_view(),  name="rag-search"),
    path("migrate/", MigrateView.as_view(), name="rag-migrate"),
]
```

---

## Подключение в основной urls.py проекта

```python
# myproject/urls.py
from django.urls import path, include

urlpatterns = [
    ...
    path("api/rag/", include("rag.django_integration.urls")),
]
```

---

## Эндпоинты

### POST /api/rag/search/

```json
// Request
{
  "query": "как оформить отпуск",
  "top_k": 5
}

// Response
[
  {
    "id": 1,
    "content": "...",
    "context": "...",
    "chunk_index": 3,
    "prev_chunk_id": 2,
    "next_chunk_id": 4,
    "title": "Документ HR",
    "source": "42",
    "score": 0.031
  }
]
```

### POST /api/rag/migrate/

```json
// Response
{
  "status": "ok",
  "message": "Миграция завершена"
}
```
