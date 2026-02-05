from __future__ import annotations

import json
import logging
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Coalesce, Lower
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.celery import app as celery_app

from core import tasks
from core.ai_generator import AIContentGenerator
from core.ai_generator_seo import (
    analyze_seo_text,
    generate_wordstat_seed_groups,
    normalize_phrase,
    normalize_wordstat_phrases_ai,
    select_wordstat_association_seeds,
)
from core.generation_events import (
    build_limit_error_payload,
    get_trial_limit,
    is_trial_client,
    record_generation_event,
)
from core.models import (
    Article,
    ArticleBlock,
    Client,
    GenerationEvent,
    ProjectSemanticSet,
    SemanticCluster,
    SemanticGroup,
    SemanticPhrase,
    WordstatPhrase,
    SEOKeywordSet,
    WordstatCluster,
    WordstatQuery,
    WordstatResult,
    ClusterPhrase,
)
from core.services.article_blocks import get_system_block_prompt_template, sync_blocks_from_seo_blocks
from core.services.seo_article_analysis import analyze_text_against_wordstat, extract_text_from_url
from core.services.seo_generation import cancel_active_generation, has_active_generation
from core.wordstat import WordstatError, get_wordstat_client

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ArticleBlockSerializer,
    ArticleListSerializer,
    ArticleSerializer,
    ProjectSemanticSetSerializer,
    SemanticClusterSerializer,
    SemanticGroupSerializer,
    SemanticPhraseSerializer,
    SEOKeywordSetSerializer,
    WordstatClusterSerializer,
    WordstatQuerySerializer,
    WordstatResultSerializer,
)
from .utils import enforce_generation_limit, get_active_client

logger = logging.getLogger(__name__)
WORDSTAT_MIN_FREQUENCY = 50


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    if value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _escape_newlines_in_strings(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                continue
            if ch == '"':
                result.append(ch)
                in_string = False
                continue
            if ch == "\n":
                result.append("\\n")
                continue
            if ch == "\r":
                result.append("\\r")
                continue
            result.append(ch)
        else:
            result.append(ch)
            if ch == '"':
                in_string = True
                escaped = False
    return "".join(result)


def _parse_ai_json_object(raw_response: str):
    if not raw_response:
        return None
    candidates: list[str] = []
    cleaned = _strip_code_fences(raw_response)
    if cleaned:
        candidates.append(cleaned)
    if raw_response.strip() and raw_response.strip() not in candidates:
        candidates.append(raw_response.strip())

    for candidate in candidates:
        variants = [candidate]
        repaired = _escape_newlines_in_strings(candidate)
        if repaired and repaired != candidate:
            variants.append(repaired)
        for variant in variants:
            try:
                parsed = json.loads(variant)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _parse_optional_positive_int(value):
    if value in (None, "", 0):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _get_wordstat_phrase_map(phrases: list[str]) -> dict[str, WordstatPhrase]:
    normalized_map: dict[str, str] = {}
    for phrase in phrases or []:
        normalized = normalize_phrase(phrase)
        if not normalized:
            continue
        normalized_map[normalized] = normalized

    if not normalized_map:
        return {}

    existing = WordstatPhrase.objects.filter(
        phrase__in=normalized_map.values(),
        frequency__gte=WORDSTAT_MIN_FREQUENCY,
    )
    return {row.phrase: row for row in existing}


def _upsert_wordstat_phrases(
    counts: dict[str, int],
    *,
    min_frequency: int = WORDSTAT_MIN_FREQUENCY,
) -> dict[str, WordstatPhrase]:
    normalized_counts: dict[str, int] = {}
    for phrase, count in (counts or {}).items():
        normalized = normalize_phrase(phrase)
        if not normalized:
            continue
        try:
            parsed = int(count or 0)
        except (TypeError, ValueError):
            parsed = 0
        if parsed < min_frequency:
            continue
        current = normalized_counts.get(normalized)
        if current is None or parsed > current:
            normalized_counts[normalized] = parsed

    if not normalized_counts:
        return {}

    existing = WordstatPhrase.objects.filter(phrase__in=normalized_counts.keys())
    phrase_map = {row.phrase: row for row in existing}
    to_create: list[WordstatPhrase] = []
    to_update: list[WordstatPhrase] = []
    now = timezone.now()
    for phrase, count in normalized_counts.items():
        row = phrase_map.get(phrase)
        if row:
            if row.frequency is None or count > row.frequency:
                row.frequency = count
                row.updated_at = now
                to_update.append(row)
        else:
            to_create.append(WordstatPhrase(phrase=phrase, frequency=count))

    if to_create:
        WordstatPhrase.objects.bulk_create(to_create)
        created = WordstatPhrase.objects.filter(phrase__in=[row.phrase for row in to_create])
        for row in created:
            phrase_map[row.phrase] = row

    if to_update:
        WordstatPhrase.objects.bulk_update(to_update, ["frequency", "updated_at"])

    return phrase_map


def _assign_wordstat_phrases(client: Client, wordstat_map: dict[str, WordstatPhrase]) -> None:
    if not wordstat_map:
        return
    normalized_values = list(wordstat_map.keys())
    candidates = SemanticPhrase.objects.filter(
        client=client,
        phrase_id__isnull=True,
        normalized_phrase__in=normalized_values,
    )
    updates: list[SemanticPhrase] = []
    for row in candidates:
        normalized_value = normalize_phrase(row.normalized_phrase or "")
        wordstat_phrase = wordstat_map.get(normalized_value)
        if not wordstat_phrase:
            continue
        row.phrase_id = wordstat_phrase.id
        row.updated_at = timezone.now()
        updates.append(row)
    if updates:
        SemanticPhrase.objects.bulk_update(updates, ["phrase", "updated_at"])


def _build_article_outline(
    wordstat: str,
    why_now: list[str],
    solution: list[str],
    *,
    lead_product_name: str = "",
    tripwire_product_name: str = "",
    level3: dict | None = None,
) -> str:
    safe_wordstat = (wordstat or "").strip()
    why_now_items = [str(item).strip() for item in (why_now or []) if str(item).strip()]
    solution_items = [str(item).strip() for item in (solution or []) if str(item).strip()]

    lines: list[str] = []
    lines.append(f"# {safe_wordstat}")
    lines.append("")
    lines.append("SEO-H1 (чётко по запросу)")
    lines.append("")
    lines.append("## Вступление:")
    lines.append("")
    lines.append("### боль")
    if why_now_items:
        for item in why_now_items:
            lines.append(f"- {item}")
    else:
        lines.append("- (какая боль/срочность у пользователя)")
    lines.append("")
    lines.append("### узнавание")
    lines.append("- (как пользователь узнаёт себя в ситуации)")
    lines.append("- (признаки/симптомы, по которым он понимает, что это про него)")
    lines.append("")
    lines.append("### обещание")
    if solution_items:
        for item in solution_items:
            lines.append(f"- {item}")
    else:
        lines.append("- (к какому решению/логике подводим)")
    lines.append("")

    def _append_level3(block_title: str, answer_hint: str) -> bool:
        if not isinstance(level3, dict):
            return False
        entry = level3.get(block_title)
        if not isinstance(entry, dict):
            return False
        h2_title = str(entry.get("h2_title") or entry.get("subquery_h2") or "").strip()
        subquery = str(entry.get("subquery") or "").strip()
        if h2_title:
            lines.append(f"## {h2_title}")
        elif subquery:
            lines.append(f"## {subquery}")
        keywords = entry.get("keywords") if isinstance(entry.get("keywords"), list) else []
        keyword_values = [str(item).strip() for item in keywords if str(item).strip()]
        if keyword_values:
            lines.append(f"- ключи: {', '.join(keyword_values)}")
        if subquery:
            lines.append(f"- подзапрос: {subquery}")
        micro_intent = str(entry.get("intent") or entry.get("micro_intent") or "").strip()
        if micro_intent:
            lines.append(f"- интент: {micro_intent}")
        raw_key_points = entry.get("key_points")
        if isinstance(raw_key_points, list):
            key_points = [str(item).strip() for item in raw_key_points if str(item).strip()]
            if key_points:
                lines.append(f"- ключевые смыслы: {', '.join(key_points)}")
        elif isinstance(raw_key_points, str) and raw_key_points.strip():
            lines.append(f"- ключевые смыслы: {raw_key_points.strip()}")
        lines.append(f"- ответ: {answer_hint}")
        return True

    def _append_level3_placeholder(answer_hint: str):
        lines.append("## (H2 заголовок)")
        lines.append("- подзапрос: (конкретный вопрос пользователя)")
        lines.append("- ключи: (1–2 ключа из Wordstat избранного)")
        lines.append("- интент: (какой когнитивный запрос закрываем)")
        lines.append("- ключевые смыслы: (3–6 пунктов)")
        lines.append(f"- ответ: {answer_hint}")

    lines.append("## Блок «Почему проблема возникает»")
    if not _append_level3("Блок «Почему проблема возникает»", "(причины/механика проблемы: от простого к сложному)"):
        _append_level3_placeholder("(причины/механика проблемы: от простого к сложному)")
    lines.append("")
    lines.append("## Блок «Типичные ошибки»")
    if not _append_level3("Блок «Типичные ошибки»", "(что обычно делают неправильно и почему не работает)"):
        _append_level3_placeholder("(что обычно делают неправильно и почему не работает)")
    lines.append("")
    lines.append("## Блок «Правильная логика / система»")
    if not _append_level3("Блок «Правильная логика / система»", "(правильный принцип/система мышления)"):
        _append_level3_placeholder("(правильный принцип/система мышления)")
    lines.append("")
    lines.append("## Блок «Пошаговая модель»")
    if not _append_level3("Блок «Пошаговая модель»", "(какие шаги и в каком порядке)"):
        _append_level3_placeholder("(какие шаги и в каком порядке)")
    lines.append("- Шаг 1: (что сделать)")
    lines.append("- Шаг 2: (что сделать)")
    lines.append("- Шаг 3: (что сделать)")
    lines.append("")
    lines.append("## Блок «Пример / кейс / сценарий»")
    if not _append_level3("Блок «Пример / кейс / сценарий»", "(короткий сценарий применения шагов)"):
        _append_level3_placeholder("(короткий сценарий применения шагов)")
    lines.append("")
    lines.append("## Блок «Что делать дальше»")
    if not _append_level3("Блок «Что делать дальше»", "(варианты следующего шага и когда нужен специалист/инструмент)"):
        _append_level3_placeholder("(варианты следующего шага и когда нужен специалист/инструмент)")
    lines.append("- (варианты следующего шага)")
    lines.append("- (когда стоит обратиться к специалисту/инструменту)")
    lines.append("")
    lines.append("## Мягкий переход к продукту:")
    if not _append_level3("Мягкий переход к продукту:", "(как связать решение с продуктом без давления)"):
        _append_level3_placeholder("(как связать решение с продуктом без давления)")
    if lead_product_name.strip():
        lines.append(f"- Lead: {lead_product_name.strip()}")
    if tripwire_product_name.strip():
        lines.append(f"- Tripwire: {tripwire_product_name.strip()}")
    lines.append("- (мягко связать решение с продуктом/услугой без давления)")
    lines.append("")

    lines.append("## Закрывающее утверждение")
    lines.append("- (2–3 предложения: ясность, структура, без CTA)")
    lines.append("")
    return "\n".join(lines)


def _split_wordstat_phrases(value) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    phrases: list[str] = []
    for item in items:
        if item is None:
            continue
        for part in str(item).replace("\r", "\n").split("\n"):
            cleaned = part.strip()
            if cleaned:
                phrases.append(cleaned)
    return phrases


def _normalize_wordstat_phrases(phrases: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for phrase in phrases:
        normalized = normalize_phrase(phrase)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(str(phrase).strip())
    return cleaned


def _merge_wordstat_phrases(primary: list[str], extra: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for phrase in primary + extra:
        normalized = normalize_phrase(phrase)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(str(phrase).strip())
    return merged


def _resolve_cluster_phrases(client: Client, phrases: list[str]) -> tuple[list[str], str | None]:
    if not phrases:
        return [], None
    matches = list(
        WordstatResult.objects.filter(
            query__client=client,
            result_type="favorite",
            phrase__in=phrases,
        ).select_related("cluster")
    )
    cluster = next((row.cluster for row in matches if row.cluster_id), None)
    if not cluster:
        return [], None

    cluster_rows = WordstatResult.objects.filter(
        query__client=client,
        result_type="favorite",
        cluster=cluster,
    ).order_by("-count", "phrase")
    cluster_phrases = _normalize_wordstat_phrases([row.phrase for row in cluster_rows])
    return cluster_phrases, cluster.name


class ArticleViewSet(viewsets.ModelViewSet):
    """Статьи (скелеты) по Wordstat запросам."""

    permission_classes = [IsTenantMember]
    http_method_names = ["get", "post", "delete", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return Article.objects.filter(client=client).order_by("-created_at")

    def get_permissions(self):
        if self.action in {
            "start",
            "generate_context",
            "save_choices",
            "save_seo_blocks",
            "generate_seo_blocks",
            "generate_blocks",
            "update_outline",
            "update_wordstat",
            "update_audience",
            "generate_outline",
            "blocks_update",
            "blocks_generate",
            "evaluate",
            "update_result",
            "destroy",
        }:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        return ArticleSerializer

    def _get_block_queryset(self, article: Article):
        return ArticleBlock.objects.filter(article=article).order_by("order", "id")

    def _get_system_block_prompt_template(self, block_key: str) -> str:
        """
        Системный промпт для блока (общий для всех клиентов/статей).
        Редактируется в Django Admin в модели GeneratorPrompt (группа "Статьи").
        """
        return get_system_block_prompt_template(block_key)

    def _sync_blocks_from_seo_blocks(self, article: Article):
        sync_blocks_from_seo_blocks(article)

    def _generate_context_options(self, article: Article, force: bool = False):
        has_options = bool(article.options_why_now) and bool(article.options_solution)
        if has_options and not force:
            if article.status in {"wordstat", "failed"}:
                article.status = "context_suggested"
                article.save(update_fields=["status", "updated_at"])
            return True, None, None

        try:
            generator = AIContentGenerator()
        except Exception:
            article.status = "failed"
            article.save(update_fields=["status", "updated_at"])
            return False, "AI генератор не настроен (нет ключа/доступа)", status.HTTP_503_SERVICE_UNAVAILABLE

        phrases = _normalize_wordstat_phrases(article.wordstat_phrases or [article.wordstat])
        cluster_block = ""
        if len(phrases) > 1:
            cluster_block = "\nФразы из кластера (учти все при генерации):\n" + "\n".join(
                [f"- {phrase}" for phrase in phrases]
            )

        prompt = f"""
Ты помощник редактора. По поисковому запросу (Wordstat) нужно сгенерировать варианты для двух списков.

Запрос: "{article.wordstat}"
{cluster_block}

1) Почему пользователь это ищет именно сейчас?
2) К какому решению его можно подвести?

Требования:
- Верни строго JSON-объект.
- Ключи: "why_now" и "solution".
- Значения: массивы строк (каждая строка 4-12 слов), по 6-10 вариантов.
- Не пиши статьи и объяснения, только варианты.
"""

        ai_raw = generator.get_ai_response(
            prompt,
            max_tokens=700,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        parsed = _parse_ai_json_object(ai_raw or "")
        why_now = parsed.get("why_now") if isinstance(parsed, dict) else None
        solution = parsed.get("solution") if isinstance(parsed, dict) else None

        if not isinstance(why_now, list) or not isinstance(solution, list):
            article.status = "failed"
            article.save(update_fields=["status", "updated_at"])
            return False, "Не удалось получить варианты от AI", status.HTTP_502_BAD_GATEWAY

        article.options_why_now = [str(item).strip() for item in why_now if str(item).strip()]
        article.options_solution = [str(item).strip() for item in solution if str(item).strip()]
        if article.status in {"wordstat", "failed"}:
            article.status = "context_suggested"
        article.save(update_fields=["options_why_now", "options_solution", "status", "updated_at"])

        return True, None, None

    @action(detail=True, methods=["get"])
    def blocks(self, request, pk=None):
        article = self.get_object()
        self._sync_blocks_from_seo_blocks(article)
        serializer = ArticleBlockSerializer(self._get_block_queryset(article), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def blocks_update(self, request, pk=None):
        article = self.get_object()
        block_id = request.data.get("block_id")
        try:
            block_id_int = int(str(block_id))
        except (TypeError, ValueError):
            return Response({"error": "block_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        block = get_object_or_404(ArticleBlock, id=block_id_int, article=article)

        if "h2_title" in request.data:
            block.h2_title = str(request.data.get("h2_title") or "")[:300]
        if "subquery" in request.data:
            block.subquery = str(request.data.get("subquery") or "")[:300]
        if "micro_intent" in request.data or "intent" in request.data:
            block.micro_intent = str(request.data.get("micro_intent") or request.data.get("intent") or "")[:300]
        if "keywords" in request.data:
            raw_keywords = request.data.get("keywords")
            if isinstance(raw_keywords, list):
                block.keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
            else:
                return Response({"error": "keywords должен быть массивом"}, status=status.HTTP_400_BAD_REQUEST)
        if "key_points" in request.data:
            raw_key_points = request.data.get("key_points")
            if isinstance(raw_key_points, list):
                block.key_points = "\n".join([str(item).strip() for item in raw_key_points if str(item).strip()])[:1500]
            else:
                block.key_points = str(raw_key_points or "")[:1500]
        if "prompt_is_custom" in request.data:
            block.prompt_is_custom = bool(request.data.get("prompt_is_custom"))
        if "content" in request.data:
            block.content = str(request.data.get("content") or "")
        if "prompt_template" in request.data:
            block.prompt_template = str(request.data.get("prompt_template") or "")

        if block.content.strip():
            block.status = "ready"
        elif block.status != "failed":
            block.status = "blueprint_ready"

        block.save(
            update_fields=[
                "h2_title",
                "subquery",
                "micro_intent",
                "keywords",
                "key_points",
                "prompt_template",
                "prompt_is_custom",
                "content",
                "status",
                "updated_at",
            ]
        )
        seo_blocks = article.seo_blocks if isinstance(article.seo_blocks, dict) else {}
        if not isinstance(seo_blocks, dict):
            seo_blocks = {}
        seo_entry = seo_blocks.get(block.block_key) if isinstance(seo_blocks, dict) else None
        if not isinstance(seo_entry, dict):
            seo_entry = {}
        seo_entry.update(
            {
                "h2_title": block.h2_title,
                "subquery": block.subquery,
                "micro_intent": block.micro_intent,
                "key_points": block.key_points,
                "keywords": block.keywords,
            }
        )
        seo_blocks[block.block_key] = seo_entry
        article.seo_blocks = seo_blocks
        article.save(update_fields=["seo_blocks", "updated_at"])
        serializer = ArticleBlockSerializer(block)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def blocks_generate(self, request, pk=None):
        article = self.get_object()
        block_id = request.data.get("block_id")
        try:
            block_id_int = int(str(block_id))
        except (TypeError, ValueError):
            return Response({"error": "block_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(ArticleBlock, id=block_id_int, article=article)

        task = tasks.generate_article_block_task.delay(article.id, block_id_int)
        return Response(
            {
                "success": True,
                "message": "Генерация блока запущена",
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["post"])
    def start(self, request):
        client = get_active_client(request.user)
        raw_phrase = request.data.get("phrase") or request.data.get("wordstat") or ""
        raw_phrases = request.data.get("phrases")
        phrases = _normalize_wordstat_phrases(
            _split_wordstat_phrases(raw_phrases) or _split_wordstat_phrases(raw_phrase)
        )
        if not phrases:
            return Response({"error": "Укажите Wordstat фразу"}, status=status.HTTP_400_BAD_REQUEST)

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_ARTICLE_WRITE)
        if limit_response:
            return limit_response

        main_phrase = phrases[0]
        cluster_phrases, _cluster_name = _resolve_cluster_phrases(client, phrases)
        wordstat_phrases = _merge_wordstat_phrases(cluster_phrases, phrases)

        article = Article.objects.create(
            client=client,
            wordstat=main_phrase[:500],
            wordstat_phrases=wordstat_phrases,
            status="wordstat",
            created_by=request.user,
        )
        self._sync_blocks_from_seo_blocks(article)

        record_generation_event(
            client,
            GenerationEvent.EVENT_ARTICLE_WRITE,
            meta={"article_id": article.id},
        )

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_context(self, request, pk=None):
        article = self.get_object()
        raw_force = request.data.get("force")
        force = False
        if isinstance(raw_force, bool):
            force = raw_force
        elif raw_force is not None:
            force = str(raw_force).strip().lower() in {"1", "true", "yes", "y", "on"}

        ok, error, status_code = self._generate_context_options(article, force=force)
        if not ok:
            return Response({"error": error}, status=status_code)

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def save_choices(self, request, pk=None):
        article = self.get_object()
        selected_why_now = request.data.get("selected_why_now") or request.data.get("why_now") or []
        selected_solution = request.data.get("selected_solution") or request.data.get("solution") or []
        lead_product_id = request.data.get("lead_product_id")
        lead_product_name = request.data.get("lead_product_name") or ""
        tripwire_product_id = request.data.get("tripwire_product_id")
        tripwire_product_name = request.data.get("tripwire_product_name") or ""

        if not isinstance(selected_why_now, list) or not isinstance(selected_solution, list):
            return Response(
                {"error": "selected_why_now и selected_solution должны быть массивами строк"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.selected_why_now = [str(item).strip() for item in selected_why_now if str(item).strip()]
        article.selected_solution = [str(item).strip() for item in selected_solution if str(item).strip()]
        article.lead_product_id = _parse_optional_positive_int(lead_product_id)
        article.lead_product_name = str(lead_product_name)[:255]
        article.tripwire_product_id = _parse_optional_positive_int(tripwire_product_id)
        article.tripwire_product_name = str(tripwire_product_name)[:255]

        article.status = "context_selected"

        article.save(
            update_fields=[
                "selected_why_now",
                "selected_solution",
                "lead_product_id",
                "lead_product_name",
                "tripwire_product_id",
                "tripwire_product_name",
                "status",
                "updated_at",
            ]
        )

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_wordstat(self, request, pk=None):
        article = self.get_object()
        raw_wordstat = request.data.get("wordstat") or request.data.get("phrase") or ""
        wordstat = str(raw_wordstat).strip()
        if not wordstat:
            return Response({"error": "Укажите wordstat"}, status=status.HTTP_400_BAD_REQUEST)

        raw_phrases = request.data.get("phrases")
        phrases = _normalize_wordstat_phrases(
            _split_wordstat_phrases(raw_phrases) or _split_wordstat_phrases(wordstat)
        )
        cluster_phrases, _cluster_name = _resolve_cluster_phrases(article.client, phrases)
        wordstat_phrases = _merge_wordstat_phrases(cluster_phrases, phrases)

        article.wordstat = wordstat[:500]
        article.wordstat_phrases = wordstat_phrases
        raw_audience = request.data.get("audience")
        if raw_audience is not None:
            article.audience = str(raw_audience or "")

        if article.outline_markdown:
            lines = (article.outline_markdown or "").splitlines()
            if lines:
                first = lines[0].strip()
                if first.startswith("#"):
                    lines[0] = f"# {article.wordstat}"
                    article.outline_markdown = "\n".join(lines)

        article.save(
            update_fields=["wordstat", "wordstat_phrases", "audience", "outline_markdown", "updated_at"]
        )
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_result(self, request, pk=None):
        article = self.get_object()
        result_html = str(request.data.get("result_html") or "").strip()
        article.result_html = result_html
        article.status = "result_edited"
        article.save(update_fields=["result_html", "status", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_audience(self, request, pk=None):
        article = self.get_object()
        raw = request.data.get("audience")
        if raw is None:
            return Response({"error": "audience обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        article.audience = str(raw or "")
        article.save(update_fields=["audience", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_outline(self, request, pk=None):
        article = self.get_object()
        outline = request.data.get("outline_markdown")
        if outline is None:
            return Response({"error": "outline_markdown обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        article.outline_markdown = str(outline)
        # Status is updated only by the blueprint generator.
        article.save(update_fields=["outline_markdown", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def save_seo_blocks(self, request, pk=None):
        article = self.get_object()
        raw = request.data.get("seo_blocks")
        if not isinstance(raw, dict):
            return Response({"error": "seo_blocks должен быть объектом"}, status=status.HTTP_400_BAD_REQUEST)
        article.seo_blocks = raw
        article.save(update_fields=["seo_blocks", "updated_at"])
        self._sync_blocks_from_seo_blocks(article)
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_seo_blocks(self, request, pk=None):
        article = self.get_object()
        task = tasks.generate_article_blueprint_task.delay(article.id)
        return Response(
            {
                "success": True,
                "message": "Генерация blueprint запущена",
                "task_id": task.id,
            }
        )

    @action(detail=True, methods=["post"])
    def generate_blocks(self, request, pk=None):
        article = self.get_object()
        task = tasks.generate_article_blocks_task.delay(article.id)
        return Response(
            {
                "success": True,
                "message": "Генерация всех блоков запущена",
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["post"])
    def evaluate(self, request):
        client = get_active_client(request.user)
        raw_text = request.data.get("text")
        raw_url = request.data.get("url")
        main_query = request.data.get("wordstat") or request.data.get("query") or ""
        action_name = str(request.data.get("action") or "analyze").strip().lower()

        if action_name not in {"analyze", "recommend", "rewrite"}:
            return Response({"error": "Некорректный action"}, status=status.HTTP_400_BAD_REQUEST)

        source: dict[str, object] = {}
        if raw_text:
            text = str(raw_text)
            if raw_url:
                source["url"] = str(raw_url).strip()
        elif raw_url:
            try:
                text, source = extract_text_from_url(str(raw_url))
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Передайте text или url"}, status=status.HTTP_400_BAD_REQUEST)

        text = (text or "").strip()
        if not text:
            return Response({"error": "Пустой текст"}, status=status.HTTP_400_BAD_REQUEST)

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_ARTICLE_EVALUATE)
        if limit_response:
            return limit_response

        results = list(
            WordstatResult.objects.filter(query__client=client, result_type="favorite")
            .select_related("cluster")
            .order_by("-count", "phrase")[:250]
        )
        if not results:
            return Response(
                {"error": "Нет избранных фраз Wordstat для анализа"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        analysis = analyze_text_against_wordstat(text, results, max_ngram=3)

        payload: dict[str, object] = {"success": True, "analysis": analysis}
        if source:
            payload["source"] = source
        if main_query:
            payload["main_query"] = str(main_query).strip()

        if action_name in {"recommend", "rewrite"}:
            ai_result = analyze_seo_text(
                text=text,
                main_query=str(main_query).strip() or None,
                found_keywords=analysis.get("found_keywords") if isinstance(analysis, dict) else None,
                missing_keywords=analysis.get("missing_keywords") if isinstance(analysis, dict) else None,
                cluster_coverage=analysis.get("cluster_coverage") if isinstance(analysis, dict) else None,
                include_rewrite=action_name == "rewrite",
            )
            if not ai_result.get("success"):
                error_payload = {"error": ai_result.get("error") or "ai_error"}
                if ai_result.get("raw_response"):
                    error_payload["raw_response"] = ai_result.get("raw_response")
                return Response(error_payload, status=status.HTTP_502_BAD_GATEWAY)
            payload["ai"] = ai_result.get("result")

        record_generation_event(
            client,
            GenerationEvent.EVENT_ARTICLE_EVALUATE,
            meta={"action": action_name},
        )

        return Response(payload)

    @action(detail=False, methods=["get"], url_path="generation-status")
    def generation_status(self, request):
        """Вернуть состояние задачи генерации статьи по task_id."""
        task_id = request.query_params.get("task_id")
        if not task_id:
            return Response({"success": False, "error": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            async_result = celery_app.AsyncResult(task_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to fetch generation status for %s: %s", task_id, exc, exc_info=True)
            return Response(
                {"success": False, "error": "Не удалось получить статус задачи"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        state = (async_result.state or "").lower()
        payload = {"success": state == "success", "status": state, "task_id": task_id}

        if state == "success" and isinstance(async_result.result, dict):
            payload["result"] = async_result.result
        elif state in ("failure", "revoked"):
            error_info = getattr(async_result, "info", None)
            payload["error"] = str(error_info) if error_info else "Задача завершилась с ошибкой"

        return Response(payload)

    @action(detail=True, methods=["post"])
    def generate_outline(self, request, pk=None):
        article = self.get_object()
        selected_why_now = request.data.get("selected_why_now") or request.data.get("why_now") or []
        selected_solution = request.data.get("selected_solution") or request.data.get("solution") or []
        lead_product_id = request.data.get("lead_product_id")
        lead_product_name = request.data.get("lead_product_name") or ""
        tripwire_product_id = request.data.get("tripwire_product_id")
        tripwire_product_name = request.data.get("tripwire_product_name") or ""

        if not isinstance(selected_why_now, list) or not isinstance(selected_solution, list):
            return Response(
                {"error": "selected_why_now и selected_solution должны быть массивами строк"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.selected_why_now = [str(item).strip() for item in selected_why_now if str(item).strip()]
        article.selected_solution = [str(item).strip() for item in selected_solution if str(item).strip()]
        article.lead_product_id = _parse_optional_positive_int(lead_product_id)
        article.lead_product_name = str(lead_product_name)[:255]
        article.tripwire_product_id = _parse_optional_positive_int(tripwire_product_id)
        article.tripwire_product_name = str(tripwire_product_name)[:255]

        block_titles = [
            "Вступление",
            "Блок «Почему проблема возникает»",
            "Блок «Типичные ошибки»",
            "Блок «Правильная логика / система»",
            "Блок «Пошаговая модель»",
            "Блок «Пример / кейс / сценарий»",
            "Блок «Что делать дальше»",
            "Мягкий переход к продукту:",
        ]

        level3 = article.seo_blocks if isinstance(article.seo_blocks, dict) else {}
        if not level3:
            try:
                response = self.generate_seo_blocks(request, pk=pk)
                if isinstance(response.data, dict) and isinstance(response.data.get("seo_blocks"), dict):
                    level3 = response.data.get("seo_blocks")  # type: ignore[assignment]
            except Exception:
                logger.exception("Failed to auto-generate seo blocks for article %s", article.id)

        filtered_level3: dict[str, dict[str, object]] = {}
        if isinstance(level3, dict):
            for key, value in level3.items():
                if key in block_titles and isinstance(value, dict):
                    filtered_level3[key] = value
        article.seo_blocks = filtered_level3
        self._sync_blocks_from_seo_blocks(article)

        article.outline_markdown = _build_article_outline(
            article.wordstat,
            article.selected_why_now,
            article.selected_solution,
            lead_product_name=article.lead_product_name,
            tripwire_product_name=article.tripwire_product_name,
            level3=article.seo_blocks,
        )
        article.status = "outline_ready"
        article.save(
            update_fields=[
                "selected_why_now",
                "selected_solution",
                "lead_product_id",
                "lead_product_name",
                "tripwire_product_id",
                "tripwire_product_name",
                "seo_blocks",
                "outline_markdown",
                "status",
                "updated_at",
            ]
        )

        serializer = self.get_serializer(article)
        return Response(serializer.data)



class SEOKeywordSetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing and generating SEO keyword sets."""

    permission_classes = [IsTenantMember]
    serializer_class = SEOKeywordSetSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = SEOKeywordSet.objects.filter(client=client).order_by('-created_at')
        group_type = self.request.query_params.get('group_type')
        if group_type:
            queryset = queryset.filter(group_type=group_type)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=False, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate(self, request):
        client = get_active_client(request.user)
        if has_active_generation(client):
            return Response(
                {
                    'success': False,
                    'message': 'SEO генерация уже выполняется. Дождитесь завершения текущего запуска.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_SEO_GROUP)
        if limit_response:
            return limit_response
        task = tasks.generate_seo_keywords_for_client.delay(client.id)
        record_generation_event(
            client,
            GenerationEvent.EVENT_SEO_GROUP,
            meta={"source": "seo_keywords"},
        )
        return Response({
            'success': True,
            'message': f"Генерация SEO-фраз запущена для клиента: {client.name}",
            'task_id': task.id,
        })


class SemanticGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for semantic group CRUD operations."""

    serializer_class = SemanticGroupSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = (
            SemanticGroup.objects.filter(client=client)
            .annotate(clusters_count=Count("clusters", distinct=True))
            .order_by("-created_at")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        source_filter = self.request.query_params.get("source")
        if source_filter:
            queryset = queryset.filter(source=source_filter)
        return queryset

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)

    @action(detail=True, methods=["post"], url_path="generate-clusters", permission_classes=[IsTenantOwnerOrEditor])
    def generate_clusters(self, request, pk=None):
        client = get_active_client(request.user)
        group = get_object_or_404(SemanticGroup.objects.filter(client=client), pk=pk)

        existing_clusters = SemanticCluster.objects.filter(client=client, semantic_group=group)
        if existing_clusters.exists():
            serializer = SemanticClusterSerializer(existing_clusters.order_by("-created_at"), many=True)
            return Response(
                {
                    "success": True,
                    "message": "Кластеры уже созданы",
                    "clusters_count": existing_clusters.count(),
                    "clusters": serializer.data,
                }
            )

        niche = (client.niche or "").strip()
        product_service = (client.product_service or "").strip()
        audience = (client.avatar or "").strip()

        missing_fields: list[str] = []
        if not niche:
            missing_fields.append("niche")
        if not product_service:
            missing_fields.append("product_service")
        if not audience:
            missing_fields.append("avatar")

        if missing_fields:
            return Response(
                {"error": "Введите данные проекта", "missing_fields": missing_fields},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_SEMANTIC_CLUSTERS)
        if limit_response:
            return limit_response

        generator = AIContentGenerator()
        result = generator.generate_semantic_clusters_from_group(
            niche=niche,
            audience=audience,
            product=product_service,
            group_name=group.name,
            group_description=group.description or "",
            group_scope=group.scope or "normal",
            expected_clusters=group.expected_clusters,
            examples=None,
            source_books=group.source_books or [],
            language="ru",
        )
        if not result.get("success"):
            return Response(
                {
                    "error": "Не удалось сформировать кластеры",
                    "details": result.get("error"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        clusters_payload = result.get("clusters") or []
        if not isinstance(clusters_payload, list):
            clusters_payload = []

        whitespace_re = re.compile(r"\s+")
        seen_names: set[str] = set()
        to_create: list[SemanticCluster] = []
        for cluster in clusters_payload:
            if not isinstance(cluster, dict):
                continue
            name = whitespace_re.sub(" ", str(cluster.get("name") or "").strip())
            if not name:
                continue
            normalized = name.lower()
            if normalized in seen_names:
                continue
            seen_names.add(normalized)
            description = whitespace_re.sub(" ", str(cluster.get("description") or "").strip())
            main_keyword = whitespace_re.sub(" ", str(cluster.get("main_keyword") or "").strip())
            intent = str(cluster.get("intent") or "").strip().lower()
            if intent not in {"info", "commercial", "navigational", "brand"}:
                intent = ""
            user_goal = whitespace_re.sub(" ", str(cluster.get("user_goal") or "").strip())
            cta = whitespace_re.sub(" ", str(cluster.get("cta") or "").strip())
            priority = cluster.get("priority")
            priority_value = None
            if isinstance(priority, (int, float)):
                priority_value = int(priority)
            elif isinstance(priority, str):
                priority_value = {"high": 3, "medium": 2, "low": 1}.get(priority.strip().lower())
            if priority_value is not None and priority_value <= 0:
                priority_value = None

            to_create.append(
                SemanticCluster(
                    client=client,
                    semantic_group=group,
                    name=name[:255],
                    description=description,
                    main_keyword=main_keyword[:255],
                    intent=intent,
                    user_goal=user_goal,
                    cta=cta[:255],
                    priority=priority_value,
                )
            )

        if not to_create:
            return Response(
                {"error": "AI не вернул валидные кластеры"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            SemanticCluster.objects.bulk_create(to_create)
            record_generation_event(
                client,
                GenerationEvent.EVENT_SEMANTIC_CLUSTERS,
                meta={"semantic_group_id": group.id, "clusters_count": len(to_create)},
            )

        created = SemanticCluster.objects.filter(client=client, semantic_group=group).order_by("-created_at")
        serializer = SemanticClusterSerializer(created, many=True)
        return Response(
            {
                "success": True,
                "message": f"Создано кластеров: {len(to_create)}",
                "clusters_count": len(to_create),
                "clusters": serializer.data,
            }
        )

    @action(detail=False, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def restart(self, request):
        client = get_active_client(request.user)
        cancel_active_generation(client, reason="Canceled by user")
        task = tasks.generate_seo_keywords_for_client.delay(client.id)
        record_generation_event(
            client,
            GenerationEvent.EVENT_SEO_GROUP,
            meta={"source": "seo_keywords", "restart": True},
        )
        return Response({
            'success': True,
            'message': f"SEO генерация перезапущена для клиента: {client.name}",
            'task_id': task.id,
        })


class SemanticClusterViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    """ViewSet for semantic cluster list/detail operations."""

    permission_classes = [IsTenantMember]
    serializer_class = SemanticClusterSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsTenantOwnerOrEditor()]
        if self.action == "phrases" and self.request.method in ("DELETE", "POST"):
            return [IsTenantOwnerOrEditor()]
        if self.action == "remove_phrase":
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = SemanticCluster.objects.filter(client=client).annotate(
            phrases_count=Count("phrases", distinct=True)
        )
        group_id = self.request.query_params.get("semantic_group")
        if group_id:
            try:
                group_id_int = int(str(group_id))
            except (TypeError, ValueError):
                group_id_int = None
            if group_id_int:
                queryset = queryset.filter(semantic_group_id=group_id_int)
        return queryset.order_by("-priority", "name", "id")

    @action(detail=True, methods=["get", "post", "delete"], url_path="phrases")
    def phrases(self, request, pk=None):
        client = get_active_client(request.user)
        cluster = get_object_or_404(SemanticCluster.objects.filter(client=client), pk=pk)
        if request.method == "POST":
            raw_phrases = (
                request.data.get("phrases")
                or request.data.get("group")
                or request.data.get("phrase")
            )
            incoming = _parse_phrases(raw_phrases)
            if not incoming:
                return Response(
                    {"error": "Введите фразы для кластера"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            whitespace_re = re.compile(r"\s+")
            cleaned: list[str] = []
            seen_norms: set[str] = set()
            for phrase in incoming:
                phrase_value = whitespace_re.sub(" ", str(phrase or "").strip())
                if not phrase_value:
                    continue
                normalized = normalize_phrase(phrase_value)
                if not normalized or normalized in seen_norms:
                    continue
                seen_norms.add(normalized)
                cleaned.append(phrase_value)

            if not cleaned:
                return Response(
                    {"error": "Введите фразы для кластера"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            existing_norms: set[str] = set()
            for phrase_obj in cluster.phrases.all():
                normalized_value = (
                    phrase_obj.normalized_phrase
                    or phrase_obj.raw_phrase
                    or (phrase_obj.phrase.phrase if phrase_obj.phrase_id else "")
                )
                normalized = normalize_phrase(normalized_value)
                if normalized:
                    existing_norms.add(normalized)

            new_phrases: list[str] = []
            new_norms: list[str] = []
            for phrase_value in cleaned:
                normalized = normalize_phrase(phrase_value)
                if normalized in existing_norms:
                    continue
                new_phrases.append(phrase_value)
                new_norms.append(normalized)

            if not new_phrases:
                return Response(
                    {"error": "Новых фраз для добавления нет"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            existing_rows = SemanticPhrase.objects.filter(
                client=client,
                normalized_phrase__in=new_norms,
            )
            existing_map: dict[str, SemanticPhrase] = {}
            for row in existing_rows:
                normalized_value = row.normalized_phrase or normalize_phrase(row.raw_phrase or "")
                if normalized_value:
                    existing_map[normalize_phrase(normalized_value)] = row

            to_create: list[SemanticPhrase] = []
            to_update: list[SemanticPhrase] = []
            now = timezone.now()
            for phrase_value in new_phrases:
                normalized = normalize_phrase(phrase_value)
                existing = existing_map.get(normalized)
                if existing:
                    changed = False
                    if not existing.raw_phrase:
                        existing.raw_phrase = phrase_value
                        changed = True
                    if not existing.normalized_phrase:
                        existing.normalized_phrase = normalized
                        changed = True
                    if changed:
                        existing.updated_at = now
                        to_update.append(existing)
                    continue
                to_create.append(
                    SemanticPhrase(
                        client=client,
                        raw_phrase=phrase_value,
                        normalized_phrase=normalized,
                        type="key",
                        intent=cluster.intent or "",
                        source="manual",
                    )
                )

            with transaction.atomic():
                if to_create:
                    SemanticPhrase.objects.bulk_create(to_create)
                if to_update:
                    SemanticPhrase.objects.bulk_update(
                        to_update,
                        ["raw_phrase", "normalized_phrase", "updated_at"],
                    )

                phrase_rows = SemanticPhrase.objects.filter(
                    client=client,
                    normalized_phrase__in=new_norms,
                )
                phrase_map: dict[str, SemanticPhrase] = {}
                for row in phrase_rows:
                    if row.normalized_phrase:
                        phrase_map[normalize_phrase(row.normalized_phrase)] = row

                main_keyword_norm = normalize_phrase(cluster.main_keyword) if cluster.main_keyword else ""
                to_link: list[ClusterPhrase] = []
                for normalized_value in new_norms:
                    phrase_obj = phrase_map.get(normalized_value)
                    if not phrase_obj:
                        continue
                    role = "main" if main_keyword_norm and normalized_value == main_keyword_norm else "support"
                    to_link.append(
                        ClusterPhrase(
                            cluster=cluster,
                            phrase=phrase_obj,
                            role=role,
                            added_by="manual",
                        )
                    )
                if to_link:
                    ClusterPhrase.objects.bulk_create(to_link, ignore_conflicts=True)

            wordstat_error: str | None = None
            wordstat_counts: dict[str, int] = {}

            wordstat_existing = WordstatPhrase.objects.filter(
                phrase__in=new_norms,
                frequency__gte=WORDSTAT_MIN_FREQUENCY,
            )
            wordstat_map_existing: dict[str, WordstatPhrase] = {}
            for row in wordstat_existing:
                wordstat_map_existing[row.phrase] = row

            phrase_updates: list[SemanticPhrase] = []
            for normalized_value, phrase_obj in phrase_map.items():
                if phrase_obj.phrase_id:
                    continue
                wordstat_phrase = wordstat_map_existing.get(normalized_value)
                if wordstat_phrase:
                    phrase_obj.phrase_id = wordstat_phrase.id
                    phrase_obj.updated_at = now
                    phrase_updates.append(phrase_obj)
            if phrase_updates:
                SemanticPhrase.objects.bulk_update(phrase_updates, ["phrase", "updated_at"])

            to_check = [
                phrase_value
                for phrase_value in new_phrases
                if normalize_phrase(phrase_value) not in wordstat_map_existing
            ]

            if to_check:
                limit_response = _check_wordstat_generation_limit(client, len(to_check))
                if limit_response:
                    wordstat_error = str(limit_response.data.get("error") or "Wordstat лимит исчерпан")
                else:
                    try:
                        ws_client = get_wordstat_client()

                        def record_wordstat_count(phrase_text: str, count_value) -> None:
                            normalized = normalize_phrase(phrase_text)
                            if not normalized:
                                return
                            try:
                                parsed = int(count_value or 0)
                            except (TypeError, ValueError):
                                parsed = 0
                            if parsed <= 0:
                                return
                            current = wordstat_counts.get(normalized)
                            if current is None or parsed > current:
                                wordstat_counts[normalized] = parsed

                        for phrase_value in to_check:
                            api_response = ws_client.fetch_top_requests(
                                phrase=phrase_value,
                                regions=None,
                                devices=None,
                                include_parent=False,
                            )
                            base_norm = normalize_phrase(phrase_value)
                            base_count = None
                            for item in api_response.get("topRequests") or []:
                                phrase_text = str(item.get("phrase") or "").strip()
                                if not phrase_text:
                                    continue
                                record_wordstat_count(phrase_text, item.get("count"))
                                if base_norm and normalize_phrase(phrase_text) == base_norm and base_count is None:
                                    try:
                                        base_count = int(item.get("count") or 0)
                                    except (TypeError, ValueError):
                                        base_count = 0

                            for item in api_response.get("associations") or []:
                                phrase_text = str(item.get("phrase") or "").strip()
                                if not phrase_text:
                                    continue
                                record_wordstat_count(phrase_text, item.get("count"))

                            if base_count is None:
                                try:
                                    base_count = int(api_response.get("totalCount") or 0)
                                except (TypeError, ValueError):
                                    base_count = 0
                            if base_norm and base_count and base_count > 0:
                                record_wordstat_count(base_norm, base_count)

                            record_generation_event(
                                client,
                                GenerationEvent.EVENT_WORDSTAT_QUERY,
                                meta={"phrases_count": 1, "source": "semantic_cluster_manual"},
                            )
                    except WordstatError as exc:
                        wordstat_error = str(exc)
                    except Exception:
                        logger.exception("Wordstat request failed for manual cluster add")
                        wordstat_error = "Не удалось получить данные Wordstat"

            if wordstat_counts:
                wordstat_map = _upsert_wordstat_phrases(wordstat_counts)
                _assign_wordstat_phrases(client, wordstat_map)

            phrases = cluster.phrases.annotate(freq=Coalesce("phrase__frequency", 0)).order_by(
                "-freq", "normalized_phrase", "id"
            )
            serializer = SemanticPhraseSerializer(phrases, many=True)
            payload = {
                "success": True,
                "added": len(new_phrases),
                "message": f"Добавлено фраз: {len(new_phrases)}",
                "phrases": serializer.data,
            }
            if wordstat_error:
                payload["wordstat_error"] = wordstat_error
            return Response(payload)

        if request.method == "DELETE":
            deleted = cluster.cluster_phrases.count()
            if deleted:
                cluster.cluster_phrases.all().delete()
            return Response(
                {
                    "success": True,
                    "deleted": deleted,
                    "message": f"Удалено фраз: {deleted}",
                }
        )
        phrases = cluster.phrases.annotate(freq=Coalesce("phrase__frequency", 0)).order_by(
            "-freq", "normalized_phrase", "id"
        )
        serializer = SemanticPhraseSerializer(phrases, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"phrases/(?P<phrase_id>\d+)",
    )
    def remove_phrase(self, request, pk=None, phrase_id=None):
        client = get_active_client(request.user)
        cluster = get_object_or_404(SemanticCluster.objects.filter(client=client), pk=pk)
        try:
            phrase_id_int = int(phrase_id)
        except (TypeError, ValueError):
            return Response({"error": "Некорректная фраза"}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = cluster.cluster_phrases.filter(phrase_id=phrase_id_int).delete()
        if not deleted:
            return Response({"error": "Фраза не найдена"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"success": True, "message": "Фраза удалена"})

    @action(detail=True, methods=["post"], url_path="generate-phrases", permission_classes=[IsTenantOwnerOrEditor])
    def generate_phrases(self, request, pk=None):
        client = get_active_client(request.user)
        cluster = get_object_or_404(SemanticCluster.objects.filter(client=client), pk=pk)

        group = cluster.semantic_group
        if not group:
            return Response(
                {"error": "Кластер не привязан к смысловой группе"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_SEMANTIC_PHRASES)
        if limit_response:
            return limit_response

        generator = AIContentGenerator()
        raw_books = group.source_books or []
        if isinstance(raw_books, list):
            source_books = raw_books
        else:
            source_books = [str(raw_books)] if str(raw_books).strip() else []

        result = generator.generate_semantic_phrases_from_cluster(
            niche=client.niche or "",
            product=client.product_service or "",
            group_name=group.name,
            group_description=group.description or "",
            group_source_books=source_books,
            cluster_name=cluster.name,
            cluster_description=cluster.description or "",
            cluster_main_keyword=cluster.main_keyword or "",
            cluster_intent=cluster.intent or "",
            cluster_user_goal=cluster.user_goal or "",
            cluster_cta=cluster.cta or "",
            language="ru",
        )

        if not result.get("success"):
            return Response(
                {
                    "error": "Не удалось сформировать фразы",
                    "details": result.get("error"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        phrases_payload = result.get("phrases") or []
        if not isinstance(phrases_payload, list):
            phrases_payload = []

        whitespace_re = re.compile(r"\s+")
        seen: set[str] = set()
        cleaned: list[dict[str, str]] = []
        for item in phrases_payload:
            if isinstance(item, dict):
                raw_phrase = item.get("phrase") or item.get("keyword") or item.get("name") or ""
                raw_intent = item.get("intent") or ""
            else:
                raw_phrase = item
                raw_intent = ""
            phrase_text = whitespace_re.sub(" ", str(raw_phrase or "").strip())
            if not phrase_text:
                continue
            normalized = normalize_phrase(phrase_text)
            if normalized in seen:
                continue
            seen.add(normalized)
            intent_value = str(raw_intent or "").strip().lower()
            if intent_value not in {"info", "commercial", "navigational", "brand"}:
                intent_value = cluster.intent or ""
            cleaned.append(
                {
                    "phrase": phrase_text,
                    "intent": intent_value,
                }
            )

        if not cleaned:
            return Response(
                {"error": "AI не вернул валидные фразы"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        normalized_phrases = {normalize_phrase(item["phrase"]) for item in cleaned}
        existing_rows = SemanticPhrase.objects.filter(
            client=client, normalized_phrase__in=normalized_phrases
        )
        existing_map: dict[str, SemanticPhrase] = {}
        for row in existing_rows:
            normalized_value = row.normalized_phrase or normalize_phrase(row.raw_phrase or "")
            if normalized_value:
                existing_map[normalized_value] = row

        to_create: list[SemanticPhrase] = []
        existing_updates: list[SemanticPhrase] = []
        now = timezone.now()
        for item in cleaned:
            normalized = normalize_phrase(item["phrase"])
            existing = existing_map.get(normalized)
            if existing:
                changed = False
                if not existing.raw_phrase:
                    existing.raw_phrase = item.get("phrase") or ""
                    changed = True
                if not existing.normalized_phrase:
                    existing.normalized_phrase = normalized
                    changed = True
                if changed:
                    existing.updated_at = now
                    existing_updates.append(existing)
                continue
            to_create.append(
                SemanticPhrase(
                    client=client,
                    raw_phrase=item.get("phrase") or "",
                    normalized_phrase=normalized,
                    type="key",
                    intent=item.get("intent") or cluster.intent or "",
                    source="ai",
                )
            )

        phrase_map: dict[str, SemanticPhrase] = {}
        with transaction.atomic():
            if to_create:
                SemanticPhrase.objects.bulk_create(to_create)
            if existing_updates:
                SemanticPhrase.objects.bulk_update(
                    existing_updates, ["raw_phrase", "normalized_phrase", "updated_at"]
                )

            rows = SemanticPhrase.objects.filter(client=client, normalized_phrase__in=normalized_phrases)
            for row in rows:
                if row.normalized_phrase:
                    phrase_map[row.normalized_phrase] = row

            main_keyword_norm = normalize_phrase(cluster.main_keyword) if cluster.main_keyword else ""
            to_link: list[ClusterPhrase] = []
            for item in cleaned:
                normalized = normalize_phrase(item["phrase"])
                phrase_obj = phrase_map.get(normalized)
                if not phrase_obj:
                    continue
                role = "main" if main_keyword_norm and normalized == main_keyword_norm else "support"
                to_link.append(
                    ClusterPhrase(
                        cluster=cluster,
                        phrase=phrase_obj,
                        role=role,
                        added_by="ai",
                    )
                )
            if to_link:
                ClusterPhrase.objects.bulk_create(to_link, ignore_conflicts=True)

            record_generation_event(
                client,
                GenerationEvent.EVENT_SEMANTIC_PHRASES,
                meta={"semantic_cluster_id": cluster.id, "phrases_count": len(cleaned)},
            )

        phrase_map_by_raw = {
            normalize_phrase(row.raw_phrase): row
            for row in phrase_map.values()
            if row.raw_phrase
        }

        try:
            normalization = normalize_wordstat_phrases_ai(
                phrases=[item["phrase"] for item in cleaned],
                language="ru",
            )
        except Exception as exc:
            logger.exception("Wordstat normalization failed for cluster %s: %s", cluster.id, exc)
            normalization = {"success": False, "error": "exception"}

        normalized_queue: list[str] = []
        if normalization.get("success"):
            normalized_items = normalization.get("phrases") or []
            for item in normalized_items:
                if not isinstance(item, dict):
                    continue
                normalized_value = item.get("normalized_phrase")
                if normalized_value is None:
                    continue
                normalized_value = whitespace_re.sub(" ", str(normalized_value).strip())
            updates: list[SemanticPhrase] = []
            seen_norms: set[str] = set()
            for item in normalized_items:
                if not isinstance(item, dict):
                    continue
                raw_phrase = str(item.get("raw_phrase") or "").strip()
                if not raw_phrase:
                    continue
                normalized_value = item.get("normalized_phrase")
                if normalized_value is not None:
                    normalized_value = whitespace_re.sub(" ", str(normalized_value).strip())
                else:
                    normalized_value = ""
                normalized_value = normalize_phrase(normalized_value) if normalized_value else ""
                comment_value = str(item.get("comment") or "").strip()
                phrase_obj = phrase_map_by_raw.get(normalize_phrase(raw_phrase)) or phrase_map.get(
                    normalize_phrase(raw_phrase)
                )
                if not phrase_obj:
                    continue
                changed = False
                if raw_phrase and not phrase_obj.raw_phrase:
                    phrase_obj.raw_phrase = raw_phrase
                    changed = True
                if normalized_value and phrase_obj.normalized_phrase != normalized_value:
                    phrase_obj.normalized_phrase = normalized_value
                    changed = True
                if comment_value and phrase_obj.comment != comment_value:
                    phrase_obj.comment = comment_value
                    changed = True
                if changed:
                    phrase_obj.updated_at = now
                    updates.append(phrase_obj)
                normalized_queue_value = normalized_value or phrase_obj.normalized_phrase or ""
                if normalized_queue_value:
                    norm_key = normalize_phrase(normalized_queue_value)
                    if norm_key and norm_key not in seen_norms:
                        normalized_queue.append(norm_key)
                        seen_norms.add(norm_key)
            if updates:
                SemanticPhrase.objects.bulk_update(
                    updates,
                    ["raw_phrase", "normalized_phrase", "comment", "updated_at"],
                )
        else:
            logger.warning(
                "Wordstat normalization failed for cluster %s: %s",
                cluster.id,
                normalization.get("error"),
            )

        if normalized_queue:
            normalized_norms = {normalize_phrase(item) for item in normalized_queue if item}
            cutoff = timezone.now() - timedelta(days=3)
            recent_results = (
                WordstatResult.objects.filter(
                    query__client=client,
                    query__created_at__gte=cutoff,
                    result_type="top_request",
                )
                .annotate(norm=Lower("phrase"))
                .filter(norm__in=normalized_norms)
                .order_by("-query__created_at")
            )
            recent_map: dict[str, WordstatResult] = {}
            for row in recent_results:
                norm_key = getattr(row, "norm", None)
                if norm_key and norm_key not in recent_map:
                    recent_map[str(norm_key)] = row

            needed_queries = sum(1 for norm in normalized_norms if norm and norm not in recent_map)
            limit_response = _check_wordstat_generation_limit(client, needed_queries)
            limit_reached = limit_response is not None
            if limit_reached:
                logger.warning(
                    "Wordstat limit reached for cluster %s: needed=%s",
                    cluster.id,
                    needed_queries,
                )

            ws_client = None
            user_info_data: dict[str, object] = {}
            if not limit_reached:
                try:
                    ws_client = get_wordstat_client()
                    user_info = ws_client.fetch_user_info()
                    user_info_data = user_info.get("userInfo") if isinstance(user_info, dict) else {}
                except Exception as exc:
                    logger.exception(
                        "Failed to init Wordstat client for cluster %s: %s",
                        cluster.id,
                        exc,
                    )
                    ws_client = None
                    user_info_data = {}

            existing_phrases = list(cluster.phrases.all())
            existing_phrase_by_norm: dict[str, SemanticPhrase] = {
                normalize_phrase(item.normalized_phrase or ""): item
                for item in existing_phrases
                if item.normalized_phrase
            }
            existing_norms: set[str] = set(existing_phrase_by_norm)

            wordstat_candidates: dict[str, int] = {}

            def record_wordstat_candidate(phrase_value: str, count_value) -> None:
                try:
                    parsed = int(count_value or 0)
                except (TypeError, ValueError):
                    parsed = 0
                if parsed < WORDSTAT_MIN_FREQUENCY:
                    return
                normalized = normalize_phrase(phrase_value)
                if not normalized:
                    return
                current = wordstat_candidates.get(normalized)
                if current is None or parsed > current:
                    wordstat_candidates[normalized] = parsed

            for normalized_value in normalized_queue:
                norm_key = normalize_phrase(normalized_value)
                if not norm_key:
                    continue

                base_count: int | None = None
                cached_row = recent_map.get(norm_key)
                if cached_row:
                    base_count = int(cached_row.count or 0)
                    cached_results = WordstatResult.objects.filter(
                        query=cached_row.query,
                        result_type__in=["top_request", "association"],
                    )

                    to_create_phrases: list[SemanticPhrase] = []
                    result_candidates: list[tuple[str, str, int]] = []
                    seen_result_norms: set[str] = set()
                    for row in cached_results:
                        phrase_value = str(row.phrase or "").strip()
                        if not phrase_value:
                            continue
                        result_norm = normalize_phrase(phrase_value)
                        if not result_norm or result_norm in seen_result_norms:
                            continue
                        seen_result_norms.add(result_norm)

                        if result_norm == norm_key:
                            continue

                        if result_norm in existing_norms:
                            existing_phrase = existing_phrase_by_norm.get(result_norm)
                            if existing_phrase:
                                record_wordstat_candidate(phrase_value, row.count)
                            continue

                        phrase_type = "association" if row.result_type == "association" else "wordstat"
                        result_candidates.append((phrase_value, phrase_type, int(row.count or 0)))

                    if result_candidates:
                        for phrase_value, phrase_type, count_value in result_candidates:
                            record_wordstat_candidate(phrase_value, count_value)
                            to_create_phrases.append(
                                SemanticPhrase(
                                    client=client,
                                    raw_phrase=phrase_value,
                                    normalized_phrase=normalize_phrase(phrase_value),
                                    type=phrase_type,
                                    source="wordstat",
                                )
                            )

                    if to_create_phrases:
                        SemanticPhrase.objects.bulk_create(to_create_phrases)
                        created_norms = {
                            normalize_phrase(item.normalized_phrase or "")
                            for item in to_create_phrases
                            if item.normalized_phrase
                        }
                        created_rows = SemanticPhrase.objects.filter(
                            client=client, normalized_phrase__in=created_norms
                        )
                        created_map = {
                            row.normalized_phrase: row
                            for row in created_rows
                            if row.normalized_phrase
                        }
                        existing_phrase_by_norm.update(created_map)
                        existing_norms.update(created_map.keys())

                        to_link: list[ClusterPhrase] = []
                        for phrase_obj in created_map.values():
                            to_link.append(
                                ClusterPhrase(
                                    cluster=cluster,
                                    phrase=phrase_obj,
                                    role="support",
                                    added_by="ai",
                                )
                            )
                        if to_link:
                            ClusterPhrase.objects.bulk_create(to_link, ignore_conflicts=True)
                elif ws_client:
                    try:
                        aggregated, total_count, responses = _collect_wordstat_data(
                            ws_client=ws_client,
                            phrases=[normalized_value],
                            regions=[],
                            devices=[],
                            include_parent=False,
                        )
                    except WordstatError as exc:
                        logger.warning("Wordstat request failed for '%s': %s", normalized_value, exc)
                        continue
                    except Exception:
                        logger.exception("Wordstat request failed for '%s'", normalized_value)
                        continue

                    request_phrase_value = normalized_value[:255]
                    raw_response_data = (
                        responses[0]["response"]
                        if len(responses) == 1
                        else {"group_phrases": [normalized_value], "responses": responses}
                    )
                    query = WordstatQuery.objects.create(
                        client=client,
                        group_name=request_phrase_value,
                        phrases=[normalized_value],
                        request_phrase=request_phrase_value,
                        total_count=total_count,
                        include_parent=False,
                        regions=[],
                        devices=[],
                        user_login=user_info_data.get("login", ""),
                        limit_per_second=user_info_data.get("limitPerSecond"),
                        daily_limit=user_info_data.get("dailyLimit"),
                        daily_limit_remaining=user_info_data.get("dailyLimitRemaining"),
                        raw_response=raw_response_data,
                    )

                    results_to_create: list[WordstatResult] = []
                    for (phrase_text, result_type), count in sorted(
                        aggregated.items(), key=lambda item: (-item[1], item[0][0])
                    ):
                        results_to_create.append(
                            WordstatResult(
                                query=query,
                                phrase=phrase_text,
                                count=int(count or 0),
                                result_type=result_type,
                            )
                        )

                    if results_to_create:
                        WordstatResult.objects.bulk_create(results_to_create)

                    record_generation_event(
                        client,
                        GenerationEvent.EVENT_WORDSTAT_QUERY,
                        meta={"phrases_count": 1, "source": "semantic_cluster"},
                    )

                    to_create_phrases: list[SemanticPhrase] = []
                    result_candidates: list[tuple[str, str, int]] = []
                    seen_result_norms: set[str] = set()
                    for (phrase_text, result_type), count in aggregated.items():
                        phrase_value = str(phrase_text or "").strip()
                        if not phrase_value:
                            continue
                        result_norm = normalize_phrase(phrase_value)
                        if not result_norm or result_norm in seen_result_norms:
                            continue
                        seen_result_norms.add(result_norm)

                        if result_norm == norm_key:
                            base_count = int(count or 0)
                            continue

                        if result_norm in existing_norms:
                            existing_phrase = existing_phrase_by_norm.get(result_norm)
                            if existing_phrase:
                                record_wordstat_candidate(phrase_value, count)
                            continue

                        phrase_type = "association" if result_type == "association" else "wordstat"
                        result_candidates.append((phrase_value, phrase_type, int(count or 0)))

                    if result_candidates:
                        for phrase_value, phrase_type, count_value in result_candidates:
                            record_wordstat_candidate(phrase_value, count_value)
                            to_create_phrases.append(
                                SemanticPhrase(
                                    client=client,
                                    raw_phrase=phrase_value,
                                    normalized_phrase=normalize_phrase(phrase_value),
                                    type=phrase_type,
                                    source="wordstat",
                                )
                            )

                    if to_create_phrases:
                        SemanticPhrase.objects.bulk_create(to_create_phrases)
                        created_norms = {
                            normalize_phrase(item.normalized_phrase or "")
                            for item in to_create_phrases
                            if item.normalized_phrase
                        }
                        created_rows = SemanticPhrase.objects.filter(
                            client=client, normalized_phrase__in=created_norms
                        )
                        created_map = {
                            row.normalized_phrase: row
                            for row in created_rows
                            if row.normalized_phrase
                        }
                        existing_phrase_by_norm.update(created_map)
                        existing_norms.update(created_map.keys())

                        to_link: list[ClusterPhrase] = []
                        for phrase_obj in created_map.values():
                            to_link.append(
                                ClusterPhrase(
                                    cluster=cluster,
                                    phrase=phrase_obj,
                                    role="support",
                                    added_by="ai",
                                )
                            )
                        if to_link:
                            ClusterPhrase.objects.bulk_create(to_link, ignore_conflicts=True)

                    if base_count is None:
                        base_count = int(total_count or 0)
                else:
                    continue

                if base_count is not None:
                    record_wordstat_candidate(norm_key, base_count)

            if wordstat_candidates:
                wordstat_map = _upsert_wordstat_phrases(wordstat_candidates)
                _assign_wordstat_phrases(client, wordstat_map)

        created = cluster.phrases.annotate(freq=Coalesce("phrase__frequency", 0)).order_by(
            "-freq", "normalized_phrase", "id"
        )
        serializer = SemanticPhraseSerializer(created, many=True)
        return Response(
            {
                "success": True,
                "message": f"Создано фраз: {len(cleaned)}",
                "phrases_count": len(cleaned),
                "phrases": serializer.data,
            }
        )

    @action(detail=True, methods=["post"], url_path="generate-context", permission_classes=[IsTenantOwnerOrEditor])
    def generate_context(self, request, pk=None):
        client = get_active_client(request.user)
        cluster = get_object_or_404(SemanticCluster.objects.filter(client=client), pk=pk)

        existing_lsi_links = cluster.cluster_phrases.filter(role="lsi")
        if existing_lsi_links.exists():
            phrases = cluster.phrases.annotate(freq=Coalesce("phrase__frequency", 0)).order_by(
                "-freq", "normalized_phrase", "id"
            )
            serializer = SemanticPhraseSerializer(phrases, many=True)
            return Response(
                {
                    "success": True,
                    "message": "Контекст уже создан",
                    "phrases_count": existing_lsi_links.count(),
                    "phrases": serializer.data,
                }
            )

        group = cluster.semantic_group
        if not group:
            return Response(
                {"error": "Кластер не привязан к смысловой группе"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_SEMANTIC_PHRASES)
        if limit_response:
            return limit_response

        generator = AIContentGenerator()
        raw_books = group.source_books or []
        if isinstance(raw_books, list):
            source_books = raw_books
        else:
            source_books = [str(raw_books)] if str(raw_books).strip() else []

        result = generator.generate_semantic_lsi_from_cluster(
            niche=client.niche or "",
            product=client.product_service or "",
            group_name=group.name,
            group_description=group.description or "",
            group_source_books=source_books,
            cluster_name=cluster.name,
            cluster_description=cluster.description or "",
            cluster_main_keyword=cluster.main_keyword or "",
            cluster_intent=cluster.intent or "",
            cluster_user_goal=cluster.user_goal or "",
            language="ru",
        )

        if not result.get("success"):
            return Response(
                {
                    "error": "Не удалось сформировать контекст",
                    "details": result.get("error"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        phrases_payload = result.get("phrases") or []
        if not isinstance(phrases_payload, list):
            phrases_payload = []

        whitespace_re = re.compile(r"\s+")
        seen: set[str] = set()
        cleaned: list[dict[str, str]] = []
        for item in phrases_payload:
            if isinstance(item, dict):
                raw_phrase = item.get("phrase") or item.get("keyword") or item.get("name") or ""
            else:
                raw_phrase = item
            phrase_text = whitespace_re.sub(" ", str(raw_phrase or "").strip())
            if not phrase_text:
                continue
            normalized = normalize_phrase(phrase_text)
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append({"phrase": phrase_text})

        if not cleaned:
            return Response(
                {"error": "AI не вернул валидные фразы"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        existing_key_norms: set[str] = set()
        for link in cluster.cluster_phrases.exclude(role="lsi").select_related("phrase"):
            phrase_obj = getattr(link, "phrase", None)
            if phrase_obj:
                normalized_value = phrase_obj.normalized_phrase or normalize_phrase(
                    phrase_obj.raw_phrase or ""
                )
                if normalized_value:
                    existing_key_norms.add(normalize_phrase(normalized_value))
        main_keyword_norm = normalize_phrase(cluster.main_keyword) if cluster.main_keyword else ""
        if main_keyword_norm:
            existing_key_norms.add(main_keyword_norm)
        candidate_norms = {normalize_phrase(item["phrase"]) for item in cleaned}
        if candidate_norms:
            key_rows = (
                SemanticPhrase.objects.filter(client=client, type="key")
                .filter(normalized_phrase__in=candidate_norms)
            )
            for row in key_rows:
                if row.normalized_phrase:
                    existing_key_norms.add(normalize_phrase(row.normalized_phrase))

        filtered: list[dict[str, str]] = []
        for item in cleaned:
            normalized = normalize_phrase(item["phrase"])
            if normalized in existing_key_norms:
                continue
            filtered.append(item)

        if not filtered:
            return Response(
                {"error": "AI вернул только SEO-ключи или дубли"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        normalized_phrases = {normalize_phrase(item["phrase"]) for item in filtered}
        existing_map: dict[str, SemanticPhrase] = {}
        if normalized_phrases:
            existing_rows = (
                SemanticPhrase.objects.filter(client=client)
                .filter(normalized_phrase__in=normalized_phrases)
            )
            for row in existing_rows:
                normalized_value = row.normalized_phrase or normalize_phrase(row.raw_phrase or "")
                if normalized_value:
                    existing_map[normalize_phrase(normalized_value)] = row

        to_create: list[SemanticPhrase] = []
        existing_updates: list[SemanticPhrase] = []
        now = timezone.now()
        for item in filtered:
            normalized = normalize_phrase(item["phrase"])
            existing = existing_map.get(normalized)
            if existing:
                changed = False
                if not existing.raw_phrase:
                    existing.raw_phrase = item.get("phrase") or ""
                    changed = True
                if not existing.normalized_phrase:
                    existing.normalized_phrase = normalized
                    changed = True
                if changed:
                    existing.updated_at = now
                    existing_updates.append(existing)
                continue
            to_create.append(
                SemanticPhrase(
                    client=client,
                    raw_phrase=item.get("phrase") or "",
                    normalized_phrase=normalized,
                    type="lsi",
                    intent=cluster.intent or "",
                    source="ai",
                )
            )

        with transaction.atomic():
            if to_create:
                SemanticPhrase.objects.bulk_create(to_create)
            if existing_updates:
                SemanticPhrase.objects.bulk_update(
                    existing_updates, ["raw_phrase", "normalized_phrase", "updated_at"]
                )

            phrase_map: dict[str, SemanticPhrase] = {}
            if normalized_phrases:
                rows = (
                    SemanticPhrase.objects.filter(client=client)
                    .filter(normalized_phrase__in=normalized_phrases)
                )
                for row in rows:
                    if row.normalized_phrase:
                        phrase_map[normalize_phrase(row.normalized_phrase)] = row

            to_link: list[ClusterPhrase] = []
            for item in filtered:
                normalized = normalize_phrase(item["phrase"])
                phrase_obj = phrase_map.get(normalized)
                if not phrase_obj:
                    continue
                to_link.append(
                    ClusterPhrase(
                        cluster=cluster,
                        phrase=phrase_obj,
                        role="lsi",
                        added_by="ai",
                    )
                )
            if to_link:
                ClusterPhrase.objects.bulk_create(to_link, ignore_conflicts=True)

            record_generation_event(
                client,
                GenerationEvent.EVENT_SEMANTIC_PHRASES,
                meta={"semantic_cluster_id": cluster.id, "phrases_count": len(filtered), "lsi": True},
            )

        if normalized_phrases:
            wordstat_map = _get_wordstat_phrase_map(list(normalized_phrases))
            _assign_wordstat_phrases(client, wordstat_map)

        created = cluster.phrases.annotate(freq=Coalesce("phrase__frequency", 0)).order_by(
            "-freq", "normalized_phrase", "id"
        )
        serializer = SemanticPhraseSerializer(created, many=True)
        return Response(
            {
                "success": True,
                "message": f"Создано фраз: {len(filtered)}",
                "phrases_count": len(filtered),
                "phrases": serializer.data,
            }
        )


class ProjectSemanticSetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing project semantic sets generated from expert books."""

    permission_classes = [IsTenantMember]
    serializer_class = ProjectSemanticSetSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = ProjectSemanticSet.objects.filter(client=client).order_by('-created_at')
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


def _parse_int_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    result = []
    for part in parts:
        try:
            number = int(str(part).strip())
        except (ValueError, TypeError):
            continue
        result.append(number)
    return result


def _parse_str_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    result = []
    for part in parts:
        part_str = str(part).strip()
        if part_str:
            result.append(part_str)
    return result


def _parse_phrases(value):
    """Вернуть уникальный список фраз из списка или многострочной строки."""
    if value is None:
        return []
    phrases: list[str] = []
    seen: set[str] = set()

    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value).replace("\r", "\n").split("\n")

    for raw in raw_items:
        if raw is None:
            continue
        for part in str(raw).replace("\r", "\n").split("\n"):
            phrase = part.strip()
            if phrase and phrase not in seen:
                seen.add(phrase)
                phrases.append(phrase)
    return phrases


def _collect_wordstat_data(
    ws_client,
    phrases: list[str],
    regions: list[int],
    devices: list[str],
    include_parent: bool,
):
    aggregated: dict[tuple[str, str], int] = {}
    total_count = 0
    responses: list[dict[str, object]] = []

    for phrase_value in phrases:
        try:
            api_response = ws_client.fetch_top_requests(
                phrase=phrase_value,
                regions=regions or None,
                devices=devices or None,
                include_parent=include_parent,
            )
        except WordstatError as exc:
            raise WordstatError(f"{phrase_value}: {exc}") from exc

        responses.append({"phrase": phrase_value, "response": api_response})
        total_count += int(api_response.get("totalCount") or 0)

        for item in api_response.get("topRequests") or []:
            phrase_text = str(item.get("phrase") or "").strip()
            if not phrase_text:
                continue
            key = (phrase_text, "top_request")
            aggregated[key] = aggregated.get(key, 0) + int(item.get("count") or 0)

        for item in api_response.get("associations") or []:
            phrase_text = str(item.get("phrase") or "").strip()
            if not phrase_text:
                continue
            key = (phrase_text, "association")
            aggregated[key] = aggregated.get(key, 0) + int(item.get("count") or 0)

    return aggregated, total_count, responses


def _build_wordstat_request_phrase(phrases: list[str]) -> str:
    label = phrases[0] if phrases else ""
    if len(phrases) > 1:
        label = f"{label} (+{len(phrases) - 1})"
    return label[:255]


def _build_association_group_name(base_group: str, association_phrase: str) -> str:
    base_value = (base_group or "").strip()
    phrase_value = (association_phrase or "").strip()
    if base_value and phrase_value:
        return f"{base_value} - {phrase_value}"[:255]
    return (phrase_value or base_value)[:255]


def _extract_top_association_candidates(
    aggregated: dict[tuple[str, str], int],
    base_phrases: list[str],
    limit: int = 50,
) -> list[dict[str, object]]:
    base_norms = {normalize_phrase(phrase) for phrase in base_phrases if phrase}
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    for (phrase_text, result_type), count in aggregated.items():
        if result_type != "association":
            continue
        phrase_value = str(phrase_text or "").strip()
        if not phrase_value:
            continue
        normalized = normalize_phrase(phrase_value)
        if not normalized or normalized in seen or normalized in base_norms:
            continue
        try:
            count_value = int(count or 0)
        except (TypeError, ValueError):
            count_value = 0
        if count_value <= 0:
            continue
        seen.add(normalized)
        items.append({"phrase": phrase_value, "count": count_value, "norm": normalized})

    items.sort(key=lambda item: (-int(item["count"]), str(item["phrase"])))
    trimmed = items[:limit]
    return [{"phrase": item["phrase"], "count": item["count"]} for item in trimmed]


def _check_wordstat_generation_limit(client, needed: int):
    if not is_trial_client(client):
        return None
    limit = get_trial_limit(GenerationEvent.EVENT_WORDSTAT_QUERY)
    used = GenerationEvent.objects.filter(client=client, event_type=GenerationEvent.EVENT_WORDSTAT_QUERY).count()
    if used + needed > limit:
        payload = build_limit_error_payload(GenerationEvent.EVENT_WORDSTAT_QUERY, used, limit)
        payload["needed"] = needed
        return Response(payload, status=status.HTTP_403_FORBIDDEN)
    return None


class WordstatQueryViewSet(viewsets.ModelViewSet):
    """Получение и сохранение Wordstat-результатов для клиента."""

    permission_classes = [IsTenantMember]
    serializer_class = WordstatQuerySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "append_phrases", "partial_update", "destroy", "seed_from_settings"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WordstatQuery.objects.filter(client=client)
            .prefetch_related(
                Prefetch("results", queryset=WordstatResult.objects.order_by("-count", "phrase"))
            )
            .order_by("-created_at")
        )

    @action(detail=False, methods=["post"], url_path="seed-from-settings")
    def seed_from_settings(self, request):
        client_obj = get_active_client(request.user)
        niche = (client_obj.niche or "").strip()
        product_service = (client_obj.product_service or "").strip()
        audience = (client_obj.avatar or "").strip()

        missing_fields: list[str] = []
        if not niche:
            missing_fields.append("niche")
        if not product_service:
            missing_fields.append("product_service")
        if not audience:
            missing_fields.append("avatar")

        if missing_fields:
            return Response(
                {"error": "Введите данные проекта", "missing_fields": missing_fields},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seed_result = generate_wordstat_seed_groups(
            niche=niche,
            product_service=product_service,
            audience=audience,
        )
        if not seed_result.get("success"):
            return Response(
                {
                    "error": "Не удалось сгенерировать seed-запросы",
                    "details": seed_result.get("error"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        seed_groups = seed_result.get("groups") or {}
        group_order = [
            "Коммерческие",
            "Категорийные",
            "Проблемные",
            "Альтернативные формулировки",
        ]

        prepared: list[tuple[str, list[str]]] = []
        missing_groups: list[str] = []
        for group_name in group_order:
            phrases = _parse_phrases(seed_groups.get(group_name, []))
            if len(phrases) < 3:
                missing_groups.append(group_name)
            prepared.append((group_name, phrases[:3]))

        if missing_groups:
            return Response(
                {
                    "error": "Недостаточно seed-фраз для групп",
                    "missing_groups": missing_groups,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        extra_queries_per_group = 3
        limit_response = _check_wordstat_generation_limit(
            client_obj,
            len(prepared) * (1 + extra_queries_per_group),
        )
        if limit_response:
            return limit_response

        try:
            ws_client = get_wordstat_client()
            user_info = ws_client.fetch_user_info()
            user_info_data = user_info.get("userInfo") if isinstance(user_info, dict) else {}
            payloads: list[dict[str, object]] = []

            for group_name, phrases in prepared:
                aggregated, total_count, responses = _collect_wordstat_data(
                    ws_client=ws_client,
                    phrases=phrases,
                    regions=[],
                    devices=[],
                    include_parent=False,
                )
                raw_response_data = (
                    responses[0]["response"]
                    if len(responses) == 1
                    else {"group_phrases": phrases, "responses": responses}
                )
                payloads.append(
                    {
                        "group_name": group_name,
                        "phrases": phrases,
                        "aggregated": aggregated,
                        "total_count": total_count,
                        "raw_response": raw_response_data,
                        "seed_group": group_name,
                    }
                )

            association_payloads: list[dict[str, object]] = []
            for payload in payloads:
                group_name = str(payload.get("group_name") or "").strip()
                phrases = payload.get("phrases") or []
                aggregated = payload.get("aggregated") or {}
                candidates = _extract_top_association_candidates(aggregated, phrases)
                if not candidates:
                    continue
                selection = select_wordstat_association_seeds(
                    niche=niche,
                    product_service=product_service,
                    audience=audience,
                    group_name=group_name,
                    associations=candidates,
                )
                association_phrases = selection.get("phrases") or []
                for association_phrase in association_phrases:
                    phrase_value = str(association_phrase or "").strip()
                    if not phrase_value:
                        continue
                    aggregated, total_count, responses = _collect_wordstat_data(
                        ws_client=ws_client,
                        phrases=[phrase_value],
                        regions=[],
                        devices=[],
                        include_parent=False,
                    )
                    raw_response_data = (
                        responses[0]["response"]
                        if len(responses) == 1
                        else {"group_phrases": [phrase_value], "responses": responses}
                    )
                    association_payloads.append(
                        {
                            "group_name": _build_association_group_name(group_name, phrase_value),
                            "phrases": [phrase_value],
                            "aggregated": aggregated,
                            "total_count": total_count,
                            "raw_response": raw_response_data,
                            "seed_group": group_name,
                            "association_seed": phrase_value,
                        }
                    )

            payloads.extend(association_payloads)
        except WordstatError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wordstat seed request failed")
            return Response(
                {"error": "Не удалось получить данные Wordstat"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        created_queries: list[WordstatQuery] = []
        with transaction.atomic():
            for payload in payloads:
                phrases = payload["phrases"]
                request_phrase_value = _build_wordstat_request_phrase(phrases)
                group_name = str(payload.get("group_name") or "").strip() or request_phrase_value
                group_name = group_name[:255]
                query = WordstatQuery.objects.create(
                    client=client_obj,
                    group_name=group_name,
                    phrases=phrases,
                    request_phrase=request_phrase_value,
                    total_count=payload["total_count"],
                    include_parent=False,
                    regions=[],
                    devices=[],
                    user_login=user_info_data.get("login", ""),
                    limit_per_second=user_info_data.get("limitPerSecond"),
                    daily_limit=user_info_data.get("dailyLimit"),
                    daily_limit_remaining=user_info_data.get("dailyLimitRemaining"),
                    raw_response=payload["raw_response"],
                )

                results_to_create = []
                for (phrase_text, result_type), count in sorted(
                    payload["aggregated"].items(), key=lambda item: (-item[1], item[0][0])
                ):
                    results_to_create.append(
                        WordstatResult(
                            query=query,
                            phrase=phrase_text,
                            count=int(count or 0),
                            result_type=result_type,
                        )
                    )

                if results_to_create:
                    WordstatResult.objects.bulk_create(results_to_create)

                meta = {"phrases_count": len(phrases)}
                seed_group = payload.get("seed_group")
                association_seed = payload.get("association_seed")
                if seed_group:
                    meta["seed_group"] = seed_group
                if association_seed:
                    meta["association_seed"] = association_seed

                record_generation_event(
                    client_obj,
                    GenerationEvent.EVENT_WORDSTAT_QUERY,
                    meta=meta,
                )

                created_queries.append(query)

        serializer = self.get_serializer(created_queries, many=True)
        return Response(
            {
                "success": True,
                "queries": serializer.data,
                "seed_groups": seed_groups,
            }
        )

    def create(self, request, *args, **kwargs):
        client_obj = get_active_client(request.user)
        phrase = (request.data.get("phrase") or "").strip()
        group_raw = request.data.get("group") or request.data.get("phrases")
        phrases = _parse_phrases(group_raw)

        if phrase:
            if phrase not in phrases:
                phrases.insert(0, phrase)
        if not phrases:
            return Response(
                {"error": "Введите фразу или группу фраз для запроса Wordstat"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client_obj, GenerationEvent.EVENT_WORDSTAT_QUERY)
        if limit_response:
            return limit_response

        regions = _parse_int_list(request.data.get("regions"))
        devices = _parse_str_list(request.data.get("devices"))
        include_parent_raw = request.data.get("include_parent", False)
        include_parent = str(include_parent_raw).lower() in {"1", "true", "yes", "on"}

        try:
            ws_client = get_wordstat_client()
            user_info = ws_client.fetch_user_info()
            aggregated, total_count, responses = _collect_wordstat_data(
                ws_client=ws_client,
                phrases=phrases,
                regions=regions,
                devices=devices,
                include_parent=include_parent,
            )
        except WordstatError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wordstat request failed")
            return Response(
                {"error": "Не удалось получить данные Wordstat"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        user_info_data = user_info.get("userInfo") if isinstance(user_info, dict) else {}
        request_phrase_value = phrase or phrases[0]
        if len(phrases) > 1:
            request_phrase_value = f"{phrases[0]} (+{len(phrases) - 1})"
        request_phrase_value = request_phrase_value[:255]
        group_name = (request.data.get("group_name") or "").strip() or request_phrase_value
        group_name = group_name[:255]
        raw_response_data = (
            responses[0]["response"] if len(responses) == 1 else {"group_phrases": phrases, "responses": responses}
        )
        query = WordstatQuery.objects.create(
            client=client_obj,
            group_name=group_name,
            phrases=phrases,
            request_phrase=request_phrase_value,
            total_count=total_count,
            include_parent=include_parent,
            regions=regions,
            devices=devices,
            user_login=user_info_data.get("login", ""),
            limit_per_second=user_info_data.get("limitPerSecond"),
            daily_limit=user_info_data.get("dailyLimit"),
            daily_limit_remaining=user_info_data.get("dailyLimitRemaining"),
            raw_response=raw_response_data,
        )

        results_to_create = []
        for (phrase_text, result_type), count in sorted(
            aggregated.items(), key=lambda item: (-item[1], item[0][0])
        ):
            results_to_create.append(
                WordstatResult(
                    query=query,
                    phrase=phrase_text,
                    count=int(count or 0),
                    result_type=result_type,
                )
            )

        if results_to_create:
            WordstatResult.objects.bulk_create(results_to_create)

        record_generation_event(
            client_obj,
            GenerationEvent.EVENT_WORDSTAT_QUERY,
            meta={"phrases_count": len(phrases)},
        )

        serializer = self.get_serializer(query)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        query: WordstatQuery = self.get_object()
        group_name = (request.data.get("group_name") or "").strip()[:255]
        query.group_name = group_name
        query.save(update_fields=["group_name"])
        serializer = self.get_serializer(query)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="append")
    def append_phrases(self, request, pk=None):
        """Добавить новые фразы в существующую группу Wordstat и объединить результаты."""
        query: WordstatQuery = self.get_object()
        new_phrases_raw = request.data.get("phrases") or request.data.get("group")
        new_phrases = _parse_phrases(new_phrases_raw)

        if not new_phrases:
            return Response({"error": "Введите фразы для запроса Wordstat"}, status=status.HTTP_400_BAD_REQUEST)

        existing_phrases = query.phrases or []
        existing_set = {p.strip() for p in existing_phrases if p}
        to_fetch = [p for p in new_phrases if p not in existing_set]

        if not to_fetch:
            return Response({"error": "Новых фраз не найдено"}, status=status.HTTP_400_BAD_REQUEST)

        limit_response = enforce_generation_limit(query.client, GenerationEvent.EVENT_WORDSTAT_QUERY)
        if limit_response:
            return limit_response

        try:
            ws_client = get_wordstat_client()
            user_info = ws_client.fetch_user_info()
            aggregated, total_count, responses = _collect_wordstat_data(
                ws_client=ws_client,
                phrases=to_fetch,
                regions=query.regions or [],
                devices=query.devices or [],
                include_parent=query.include_parent,
            )
        except WordstatError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wordstat append request failed")
            return Response(
                {"error": "Не удалось получить данные Wordstat"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Обновляем агрегированные результаты: либо увеличиваем счетчик, либо создаем новые строки.
        existing_results = WordstatResult.objects.filter(query=query)
        result_map = {(r.phrase, r.result_type): r for r in existing_results}
        to_update: list[WordstatResult] = []
        to_create: list[WordstatResult] = []

        for (phrase_text, result_type), count in aggregated.items():
            found = result_map.get((phrase_text, result_type))
            if found:
                found.count = int(found.count) + int(count or 0)
                to_update.append(found)
            else:
                to_create.append(
                    WordstatResult(
                        query=query,
                        phrase=phrase_text,
                        count=int(count or 0),
                        result_type=result_type,
                    )
                )

        if to_create:
            WordstatResult.objects.bulk_create(to_create)
        if to_update:
            WordstatResult.objects.bulk_update(to_update, ["count"])

        # Обновляем метаданные запроса
        updated_phrases = existing_phrases + to_fetch
        label = updated_phrases[0]
        if len(updated_phrases) > 1:
            label = f"{label} (+{len(updated_phrases) - 1})"
        label = label[:255]

        existing_raw = query.raw_response or {}
        if isinstance(existing_raw, dict) and "responses" in existing_raw:
            combined_responses = list(existing_raw.get("responses") or [])
        else:
            base_response = existing_raw if isinstance(existing_raw, dict) else {}
            base_phrase = query.request_phrase or (existing_phrases[0] if existing_phrases else "")
            combined_responses = []
            if base_response:
                combined_responses.append({"phrase": base_phrase, "response": base_response})

        combined_responses.extend(responses)
        raw_response_data = {"group_phrases": updated_phrases, "responses": combined_responses}

        query.phrases = updated_phrases
        query.request_phrase = label
        query.total_count = int(query.total_count) + total_count
        query.user_login = (user_info.get("userInfo") or {}).get("login", query.user_login)
        query.limit_per_second = (user_info.get("userInfo") or {}).get("limitPerSecond", query.limit_per_second)
        query.daily_limit = (user_info.get("userInfo") or {}).get("dailyLimit", query.daily_limit)
        query.daily_limit_remaining = (user_info.get("userInfo") or {}).get("dailyLimitRemaining", query.daily_limit_remaining)
        query.raw_response = raw_response_data
        query.save(
            update_fields=[
                "phrases",
                "request_phrase",
                "total_count",
                "user_login",
                "limit_per_second",
                "daily_limit",
                "daily_limit_remaining",
                "raw_response",
            ]
        )

        record_generation_event(
            query.client,
            GenerationEvent.EVENT_WORDSTAT_QUERY,
            meta={"phrases_count": len(to_fetch), "append": True},
        )

        query = self.get_queryset().get(pk=query.pk)
        serializer = self.get_serializer(query)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WordstatClusterViewSet(mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Список кластеров Wordstat для клиента."""

    permission_classes = [IsTenantMember]
    serializer_class = WordstatClusterSerializer
    pagination_class = None
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WordstatCluster.objects.filter(client=client)
            .annotate(phrases_count=Count("results", filter=Q(results__result_type="favorite")))
            .order_by("name", "id")
        )


class WordstatResultViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Обновление отдельных строк Wordstat (например, смена метки)."""

    permission_classes = [IsTenantOwnerOrEditor]
    serializer_class = WordstatResultSerializer
    http_method_names = ["patch", "put", "post", "head", "options"]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return WordstatResult.objects.filter(query__client=client)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)

        if "cluster" in data:
            client = get_active_client(request.user)
            raw_cluster = data.get("cluster")
            if raw_cluster in (None, "", "null"):
                data["cluster"] = None
            else:
                try:
                    cluster_id = int(raw_cluster)
                except (TypeError, ValueError):
                    return Response({"error": "Некорректный кластер"}, status=status.HTTP_400_BAD_REQUEST)
                if not WordstatCluster.objects.filter(client=client, id=cluster_id).exists():
                    return Response({"error": "Кластер не найден"}, status=status.HTTP_400_BAD_REQUEST)
                data["cluster"] = cluster_id

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
