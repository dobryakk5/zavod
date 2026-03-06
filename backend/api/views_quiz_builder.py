from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    ContactFact,
    MapContact,
    Quiz,
    QuizAnswer,
    QuizOption,
    QuizResultCondition,
    QuizResultRule,
    QuizScreen,
)

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .utils import get_active_client


QUIZ_KINDS = {"intro", "question", "lead", "result"}
QUESTION_TYPES = {"single", "multiple", "rating", "text", "date", "slider"}
RESULT_OPERATORS = {"includes", "not_includes", "gte", "lte", "equals"}
NEXT_SPECIALS = {"__lead", "__end"}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_smallint(value: Any) -> int | None:
    parsed = _safe_int(value)
    if parsed is None:
        return None
    if parsed < -32768 or parsed > 32767:
        return None
    return parsed


def _normalize_json_array(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _serialize_quiz(quiz: Quiz) -> dict[str, Any]:
    screens = list(
        QuizScreen.objects.filter(quiz=quiz)
        .prefetch_related("options")
        .order_by("position", "id")
    )
    screen_ids = [int(screen.id) for screen in screens]

    result_rules = list(
        QuizResultRule.objects.filter(screen_id__in=screen_ids)
        .order_by("position", "id")
    ) if screen_ids else []
    rule_ids = [int(rule.id) for rule in result_rules]
    result_conditions = list(
        QuizResultCondition.objects.filter(rule_id__in=rule_ids)
        .order_by("position", "id")
    ) if rule_ids else []

    rules_by_screen: dict[int, list[QuizResultRule]] = {}
    for rule in result_rules:
        rules_by_screen.setdefault(int(rule.screen_id), []).append(rule)

    conditions_by_rule: dict[int, list[QuizResultCondition]] = {}
    for condition in result_conditions:
        conditions_by_rule.setdefault(int(condition.rule_id), []).append(condition)

    payload_screens: list[dict[str, Any]] = []
    for screen in screens:
        options_qs = screen.options.all().order_by("position", "id")
        screen_rules = rules_by_screen.get(int(screen.id), [])
        payload_screens.append(
            {
                "id": int(screen.id),
                "kind": str(screen.kind),
                "title": str(screen.title or ""),
                "subtitle": str(screen.subtitle or ""),
                "questionType": str(screen.question_type) if screen.question_type else None,
                "placeholder": str(screen.placeholder) if screen.placeholder else None,
                "minVal": int(screen.min_val) if screen.min_val is not None else None,
                "maxVal": int(screen.max_val) if screen.max_val is not None else None,
                "maxRating": int(screen.max_rating) if screen.max_rating is not None else None,
                "required": bool(screen.is_required),
                "isDefaultResult": bool(screen.is_default_result),
                "options": [
                    {
                        "id": int(option.id),
                        "label": str(option.label or ""),
                        "emoji": str(option.emoji or ""),
                        "nextScreenId": int(option.next_screen_id) if option.next_screen_id is not None else None,
                        "nextSpecial": str(option.next_special) if option.next_special else None,
                    }
                    for option in options_qs
                ],
                "rules": [
                    {
                        "id": int(rule.id),
                        "position": int(rule.position),
                        "conditions": [
                            {
                                "id": int(condition.id),
                                "screenId": int(condition.screen_id),
                                "operator": str(condition.operator),
                                "value": _normalize_json_array(condition.value),
                            }
                            for condition in conditions_by_rule.get(int(rule.id), [])
                        ],
                    }
                    for rule in screen_rules
                ] if screen.kind == "result" else [],
            }
        )

    return {
        "id": int(quiz.id),
        "title": str(quiz.title or ""),
        "accentColor": str(quiz.accent_color or "#5b5ef4"),
        "isPublished": bool(quiz.is_published),
        "screens": payload_screens,
    }


def _create_default_screens(quiz: Quiz) -> None:
    intro = QuizScreen.objects.create(
        quiz=quiz,
        kind="intro",
        position=0,
        title="Подберем решение для вас",
        subtitle="Ответьте на несколько вопросов и получите персональное предложение",
        is_required=False,
    )
    _ = intro
    question = QuizScreen.objects.create(
        quiz=quiz,
        kind="question",
        position=1,
        title="Какая у вас главная цель?",
        subtitle="Выберите один вариант",
        question_type="single",
        is_required=True,
    )
    QuizOption.objects.create(screen=question, label="Увеличить продажи", emoji="", position=0)
    QuizOption.objects.create(screen=question, label="Собрать лиды", emoji="", position=1)
    QuizOption.objects.create(screen=question, label="Повысить узнаваемость", emoji="", position=2)

    QuizScreen.objects.create(
        quiz=quiz,
        kind="lead",
        position=2,
        title="Куда отправить результат?",
        subtitle="Мы свяжемся с вами в течение 15 минут",
        is_required=False,
    )
    QuizScreen.objects.create(
        quiz=quiz,
        kind="result",
        position=3,
        title="Заявка отправлена!",
        subtitle="Мы изучим ваши ответы и подготовим персональное предложение",
        is_required=False,
        is_default_result=True,
    )


def _get_or_create_tenant_quiz(client_id: int) -> Quiz:
    quiz = Quiz.objects.filter(tenant_id=client_id).order_by("id").first()
    if quiz:
        if not QuizScreen.objects.filter(quiz=quiz).exists():
            _create_default_screens(quiz)
        return quiz

    with transaction.atomic():
        quiz = Quiz.objects.create(
            tenant_id=client_id,
            title="Мой первый квиз",
            accent_color="#5b5ef4",
            is_published=False,
        )
        _create_default_screens(quiz)
    return quiz


class QuizBuilderCurrentView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH", "POST", "DELETE"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        client = get_active_client(request.user)
        quiz = _get_or_create_tenant_quiz(client.id)
        return Response(_serialize_quiz(quiz))

    def put(self, request):
        client = get_active_client(request.user)
        quiz = _get_or_create_tenant_quiz(client.id)
        payload = request.data if isinstance(request.data, dict) else {}

        next_title = str(payload.get("title") or quiz.title or "").strip() or "Мой квиз"
        raw_accent = payload.get("accentColor", payload.get("accent_color", quiz.accent_color))
        next_accent = str(raw_accent or "#5b5ef4").strip() or "#5b5ef4"
        if not HEX_COLOR_RE.match(next_accent):
            return Response(
                {"detail": "accentColor должен быть в формате HEX (#RRGGBB)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        next_published = bool(payload.get("isPublished", payload.get("is_published", quiz.is_published)))

        screens_payload = payload.get("screens")
        if screens_payload is not None and not isinstance(screens_payload, list):
            return Response(
                {"detail": "screens должен быть массивом."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_screens: list[dict[str, Any]] | None = None
        if isinstance(screens_payload, list):
            if not screens_payload:
                return Response(
                    {"detail": "Список экранов не может быть пустым."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_screens = []
            for position, raw_screen in enumerate(screens_payload):
                if not isinstance(raw_screen, dict):
                    return Response(
                        {"detail": f"Экран #{position + 1} должен быть объектом."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                kind = str(raw_screen.get("kind") or "").strip().lower()
                if kind not in QUIZ_KINDS:
                    return Response(
                        {"detail": f"Недопустимый kind у экрана #{position + 1}: {kind or '-'}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                question_type_raw = raw_screen.get("questionType", raw_screen.get("question_type"))
                question_type = str(question_type_raw).strip().lower() if question_type_raw else None
                if kind != "question":
                    question_type = None
                elif question_type not in QUESTION_TYPES:
                    return Response(
                        {"detail": f"Недопустимый questionType у экрана #{position + 1}."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                options_payload: list[dict[str, Any]] = []
                if kind == "question" and question_type in {"single", "multiple"}:
                    raw_options = raw_screen.get("options")
                    if isinstance(raw_options, list):
                        for raw_option in raw_options:
                            if not isinstance(raw_option, dict):
                                continue

                            raw_next_special = raw_option.get("nextSpecial", raw_option.get("next_special"))
                            next_special = str(raw_next_special).strip() if raw_next_special else None
                            if next_special and next_special not in NEXT_SPECIALS:
                                return Response(
                                    {"detail": f"Недопустимый nextSpecial у экрана #{position + 1}."},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )

                            raw_next_screen = raw_option.get("nextScreenId", raw_option.get("next_screen_id"))
                            next_screen_ref = str(raw_next_screen).strip() if raw_next_screen not in (None, "") else None

                            if next_screen_ref in NEXT_SPECIALS and not next_special:
                                next_special = next_screen_ref
                                next_screen_ref = None

                            if next_special and next_screen_ref:
                                return Response(
                                    {"detail": f"У option экрана #{position + 1} не может быть одновременно nextScreenId и nextSpecial."},
                                    status=status.HTTP_400_BAD_REQUEST,
                                )

                            options_payload.append(
                                {
                                    "label": str(raw_option.get("label") or ""),
                                    "emoji": str(raw_option.get("emoji") or ""),
                                    "next_screen_ref": next_screen_ref,
                                    "next_special": next_special,
                                }
                            )

                rules_payload: list[dict[str, Any]] = []
                if kind == "result":
                    raw_rules = raw_screen.get("rules")
                    if isinstance(raw_rules, list):
                        for rule_pos, raw_rule in enumerate(raw_rules):
                            if not isinstance(raw_rule, dict):
                                continue
                            raw_conditions = raw_rule.get("conditions")
                            conditions_payload: list[dict[str, Any]] = []
                            if isinstance(raw_conditions, list):
                                for raw_condition in raw_conditions:
                                    if not isinstance(raw_condition, dict):
                                        continue

                                    raw_condition_screen = raw_condition.get("screenId", raw_condition.get("screen_id"))
                                    condition_screen_ref = (
                                        str(raw_condition_screen).strip()
                                        if raw_condition_screen not in (None, "")
                                        else None
                                    )
                                    if not condition_screen_ref:
                                        continue

                                    operator = str(raw_condition.get("operator") or "includes").strip().lower()
                                    if operator not in RESULT_OPERATORS:
                                        return Response(
                                            {"detail": f"Недопустимый operator в правилах экрана #{position + 1}."},
                                            status=status.HTTP_400_BAD_REQUEST,
                                        )

                                    conditions_payload.append(
                                        {
                                            "screen_ref": condition_screen_ref,
                                            "operator": operator,
                                            "value": _normalize_json_array(raw_condition.get("value")),
                                        }
                                    )

                            rules_payload.append(
                                {
                                    "position": rule_pos,
                                    "conditions": conditions_payload,
                                }
                            )

                validated_screens.append(
                    {
                        "client_id": str(raw_screen.get("id") or raw_screen.get("clientId") or ""),
                        "position": position,
                        "kind": kind,
                        "title": str(raw_screen.get("title") or ""),
                        "subtitle": (str(raw_screen.get("subtitle") or "") or None),
                        "question_type": question_type,
                        "placeholder": (str(raw_screen.get("placeholder") or "") or None),
                        "min_val": _safe_smallint(raw_screen.get("minVal", raw_screen.get("min_val"))),
                        "max_val": _safe_smallint(raw_screen.get("maxVal", raw_screen.get("max_val"))),
                        "max_rating": _safe_smallint(raw_screen.get("maxRating", raw_screen.get("max_rating"))),
                        "is_required": bool(raw_screen.get("required", raw_screen.get("is_required", False))),
                        "is_default_result": bool(raw_screen.get("isDefaultResult", raw_screen.get("is_default_result", False)))
                        if kind == "result"
                        else False,
                        "options": options_payload,
                        "rules": rules_payload,
                    }
                )

        with transaction.atomic():
            quiz.title = next_title
            quiz.accent_color = next_accent
            quiz.is_published = next_published
            quiz.save(update_fields=["title", "accent_color", "is_published", "updated_at"])

            if validated_screens is not None:
                QuizScreen.objects.filter(quiz=quiz).delete()
                result_positions = [
                    int(screen_payload["position"])
                    for screen_payload in validated_screens
                    if screen_payload["kind"] == "result"
                ]
                explicit_default_positions = [
                    int(screen_payload["position"])
                    for screen_payload in validated_screens
                    if screen_payload["kind"] == "result" and screen_payload["is_default_result"]
                ]
                default_result_position = (
                    explicit_default_positions[-1]
                    if explicit_default_positions
                    else (result_positions[-1] if result_positions else None)
                )

                screen_refs: dict[str, QuizScreen] = {}
                created_screens: list[tuple[dict[str, Any], QuizScreen]] = []

                for screen_payload in validated_screens:
                    is_default_result = (
                        screen_payload["kind"] == "result"
                        and default_result_position is not None
                        and int(screen_payload["position"]) == int(default_result_position)
                    )

                    screen = QuizScreen.objects.create(
                        quiz=quiz,
                        kind=screen_payload["kind"],
                        position=screen_payload["position"],
                        title=screen_payload["title"],
                        subtitle=screen_payload["subtitle"],
                        question_type=screen_payload["question_type"],
                        placeholder=screen_payload["placeholder"],
                        min_val=screen_payload["min_val"],
                        max_val=screen_payload["max_val"],
                        max_rating=screen_payload["max_rating"],
                        is_required=screen_payload["is_required"],
                        is_default_result=is_default_result,
                    )
                    created_screens.append((screen_payload, screen))
                    if screen_payload["client_id"]:
                        screen_refs[screen_payload["client_id"]] = screen

                for screen_payload, screen in created_screens:
                    if screen_payload["kind"] == "question" and screen_payload["question_type"] in {"single", "multiple"}:
                        for option_pos, option_payload in enumerate(screen_payload["options"]):
                            target_screen = None
                            next_screen_ref = option_payload.get("next_screen_ref")
                            if next_screen_ref:
                                target_screen = screen_refs.get(str(next_screen_ref))

                            QuizOption.objects.create(
                                screen=screen,
                                label=option_payload["label"],
                                emoji=option_payload["emoji"],
                                next_screen=target_screen,
                                next_special=option_payload.get("next_special"),
                                position=option_pos,
                            )

                    if screen_payload["kind"] == "result":
                        for rule_pos, rule_payload in enumerate(screen_payload["rules"]):
                            rule = QuizResultRule.objects.create(
                                screen=screen,
                                position=rule_pos,
                            )
                            for condition_pos, condition_payload in enumerate(rule_payload["conditions"]):
                                condition_screen = screen_refs.get(str(condition_payload["screen_ref"]))
                                if condition_screen is None:
                                    continue
                                QuizResultCondition.objects.create(
                                    rule=rule,
                                    screen=condition_screen,
                                    operator=condition_payload["operator"],
                                    value=condition_payload["value"],
                                    position=condition_pos,
                                )

        refreshed = Quiz.objects.get(pk=quiz.id)
        return Response(_serialize_quiz(refreshed))


class QuizPublicSubmitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, quiz_id: int):
        quiz = Quiz.objects.filter(id=quiz_id, is_published=True).order_by("id").first()
        if quiz is None:
            return Response({"detail": "Квиз не найден или не опубликован."}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data if isinstance(request.data, dict) else {}
        name = str(payload.get("name") or "").strip()
        phone = str(payload.get("phone") or "").strip()
        email = str(payload.get("email") or "").strip()
        utm_source = str(payload.get("utm_source") or "").strip() or None
        utm_medium = str(payload.get("utm_medium") or "").strip() or None
        utm_campaign = str(payload.get("utm_campaign") or "").strip() or None
        answers_payload = payload.get("answers")
        if not isinstance(answers_payload, list):
            answers_payload = []

        contact: MapContact | None = None
        if phone or email:
            query = Q()
            if phone:
                query |= Q(phone=phone)
            if email:
                query |= Q(email__iexact=email)
            contact = MapContact.objects.filter(query).order_by("-updated_at", "-id").first()

        if contact is None:
            fallback_name = name or phone or email or f"Лид из квиза #{quiz.id}"
            contact = MapContact.objects.create(
                name=fallback_name,
                email=email,
                phone=phone,
                status="active",
                deal_stage="new_lead",
            )
        else:
            changed_fields: list[str] = []
            if name and not (contact.name or "").strip():
                contact.name = name
                changed_fields.append("name")
            if phone and not (contact.phone or "").strip():
                contact.phone = phone
                changed_fields.append("phone")
            if email and not (contact.email or "").strip():
                contact.email = email
                changed_fields.append("email")
            if str(contact.deal_stage or "").strip().lower() != "new_lead":
                contact.deal_stage = "new_lead"
                changed_fields.append("deal_stage")
            if changed_fields:
                changed_fields.append("updated_at")
                contact.save(update_fields=changed_fields)

        screens = list(QuizScreen.objects.filter(quiz=quiz).order_by("position", "id"))
        screens_by_id = {int(item.id): item for item in screens}
        options_by_screen: dict[int, dict[int, str]] = {}
        for option in QuizOption.objects.filter(screen_id__in=screens_by_id.keys()).order_by("position", "id"):
            sid = int(option.screen_id)
            options_by_screen.setdefault(sid, {})[int(option.id)] = str(option.label or "")
        lead_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
        user_agent = request.headers.get("User-Agent", "")

        with transaction.atomic():
            answers_stored = 0
            facts_added = 0

            for item in answers_payload:
                if not isinstance(item, dict):
                    continue

                raw_screen_id = item.get("screen_id", item.get("screenId"))
                screen_id = _safe_int(raw_screen_id)
                if screen_id is None:
                    continue
                screen = screens_by_id.get(screen_id)
                if screen is None:
                    continue

                value_text = item.get("value_text", item.get("valueText"))
                value_text = str(value_text).strip() if value_text not in (None, "") else None

                value_number = _safe_smallint(item.get("value_number", item.get("valueNumber")))

                raw_value_options = item.get("value_options", item.get("valueOptions"))
                value_options: list[int] | None = None
                if isinstance(raw_value_options, list):
                    normalized_options: list[int] = []
                    for option_id in raw_value_options:
                        parsed = _safe_int(option_id)
                        if parsed is not None:
                            normalized_options.append(parsed)
                    value_options = normalized_options or None

                QuizAnswer.objects.create(
                    tenant_id=int(quiz.tenant_id),
                    quiz_id=int(quiz.id),
                    contact_id=int(contact.id),
                    screen=screen,
                    value_text=value_text,
                    value_number=value_number,
                    value_options=value_options,
                )
                answers_stored += 1

                fact_chunks: list[str] = []
                if value_text:
                    fact_chunks.append(value_text)
                if value_number is not None:
                    fact_chunks.append(str(value_number))
                if value_options:
                    options_title_map = options_by_screen.get(screen_id, {})
                    labels = [options_title_map.get(option_id, str(option_id)) for option_id in value_options]
                    if labels:
                        fact_chunks.append(", ".join([label for label in labels if label]))

                if not fact_chunks:
                    continue

                question_title = str(screen.title or "Вопрос").strip()
                fact_value = f"{question_title}: {'; '.join(fact_chunks)}"
                fact_type = f"quiz_{str(screen.question_type or 'answer')[:48]}"

                _, created = ContactFact.objects.get_or_create(
                    contact_id=int(contact.id),
                    tenant_id=int(quiz.tenant_id),
                    category="context",
                    fact_type=fact_type,
                    fact_value=fact_value,
                    defaults={
                        "source": "quiz",
                        "confidence": 3,
                        "is_active": True,
                    },
                )
                if created:
                    facts_added += 1

            meta_fact_chunks = [
                chunk
                for chunk in (
                    f"utm_source={utm_source}" if utm_source else None,
                    f"utm_medium={utm_medium}" if utm_medium else None,
                    f"utm_campaign={utm_campaign}" if utm_campaign else None,
                    f"ip={lead_ip}" if lead_ip else None,
                    f"user_agent={user_agent}" if user_agent else None,
                )
                if chunk
            ]
            if meta_fact_chunks:
                ContactFact.objects.update_or_create(
                    contact_id=int(contact.id),
                    tenant_id=int(quiz.tenant_id),
                    category="context",
                    fact_type="quiz_meta",
                    defaults={
                        "fact_value": "; ".join(meta_fact_chunks)[:2000],
                        "source": "quiz",
                        "confidence": 3,
                        "is_active": True,
                    },
                )

        return Response(
            {
                "ok": True,
                "quiz_id": int(quiz.id),
                "contact_id": int(contact.id),
                "answers_stored": answers_stored,
                "facts_added": facts_added,
            },
            status=status.HTTP_201_CREATED,
        )


class QuizPublicDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, quiz_id: int):
        quiz = Quiz.objects.filter(id=quiz_id, is_published=True).order_by("id").first()
        if quiz is None:
            return Response({"detail": "Квиз не найден или не опубликован."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_quiz(quiz))
