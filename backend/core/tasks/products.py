from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from celery import shared_task
from django.db import IntegrityError, connection
from django.db import transaction

from core.models import Client, ClientProduct, ProductType, WordstatResult
from core.services.product_relations import merge_related_products
from core.services.product_type_templates import ensure_system_product_type_templates

logger = logging.getLogger(__name__)


def _new_ai_generator():
    from core.ai_generator import AIContentGenerator

    return AIContentGenerator()


def _attach_related_product_to_core_structure(core_product: ClientProduct, related_product: ClientProduct) -> None:
    structure = core_product.structure if isinstance(core_product.structure, dict) else {}
    raw_related = structure.get("related_products")
    existing_items = raw_related if isinstance(raw_related, list) else []

    related_id = getattr(related_product, "id", None)
    if related_id is None:
        return

    product_type = getattr(related_product, "product_type", None)
    ref: Dict[str, Any] = {
        "id": related_id,
        "name": str(getattr(related_product, "name", "") or "").strip(),
        "product_type_id": getattr(product_type, "id", None),
        "product_type_name": str(getattr(product_type, "name", "") or "").strip() or None,
        "short_description": getattr(related_product, "short_description", None),
    }

    structure["related_products"] = merge_related_products(existing_items, ref)
    core_product.structure = structure
    core_product.save(update_fields=["structure"])


def _collect_wordstat_favorites(client: Client) -> List[str]:
    favorites_qs = (
        WordstatResult.objects.filter(query__client=client, result_type="favorite")
        .order_by("-count", "phrase")
        .values_list("phrase", flat=True)
    )
    favorites: List[str] = []
    for phrase in favorites_qs[:200]:
        value = (phrase or "").strip()
        if value and value not in favorites:
            favorites.append(value)
        if len(favorites) >= 40:
            break
    return favorites


def _format_core_context(core_product: ClientProduct) -> str:
    structure = core_product.structure if isinstance(core_product.structure, dict) else {}
    packages = core_product.packages if isinstance(core_product.packages, list) else []

    summary = {
        "core": {
            "id": core_product.id,
            "name": core_product.name,
            "short_description": core_product.short_description,
        },
        "packages": packages,
        "structure": structure,
    }

    return json.dumps(summary, ensure_ascii=False)


def _requirements_payload(product_type: ProductType) -> Dict[str, str]:
    candidate = {
        "name": getattr(product_type, "requirements_name", None),
        "packages": getattr(product_type, "requirements_packages", None),
        "audience": getattr(product_type, "requirements_audience", None),
        "transformation": getattr(product_type, "requirements_transformation", None),
        "metrics": getattr(product_type, "requirements_metrics", None),
        "method": getattr(product_type, "requirements_method", None),
        "lesson_format": getattr(product_type, "requirements_lesson_format", None),
        "program_modules": getattr(product_type, "requirements_program_modules", None),
        "packaging": getattr(product_type, "requirements_packaging", None),
    }
    missing = [k for k, v in candidate.items() if not isinstance(v, str) or not v.strip()]
    if missing:
        raise ValueError(f"Missing requirements for product type '{product_type.name}': {', '.join(missing)}")
    return {k: str(v).strip() for k, v in candidate.items()}  # type: ignore[return-value]


def _extra_context_for_client(client: Client) -> str:
    parts: List[str] = []
    niche = (client.niche or "").strip()
    if niche:
        parts.append(f"Ниша: {niche}")
    product_service = (client.product_service or "").strip()
    if product_service:
        parts.append(f"Продукт/услуга: {product_service}")
    return "\n".join(parts).strip()


def _create_client_product_with_sequence_retry(create_fn):
    try:
        with transaction.atomic():
            return create_fn()
    except IntegrityError as exc:
        # map.products is managed outside Django migrations; occasionally the ID sequence can drift.
        if "products_pkey" not in str(exc):
            raise
        logger.warning("ClientProduct insert failed due to primary key conflict; resetting sequence and retrying")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT setval(
                  pg_get_serial_sequence('map.products','id'),
                  COALESCE((SELECT MAX(id) FROM map.products), 1)
                )
                """
            )
        with transaction.atomic():
            return create_fn()


@shared_task(bind=True, max_retries=0)
def generate_client_product_for_type_task(
    self,
    client_id: int,
    product_type_id: int,
    *,
    language: str = "ru",
    name: Optional[str] = None,
    short_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate and create a ClientProduct for the given system ProductType.

    Returns:
      {"success": True, "product_id": int} on success
      {"success": False, "error": "..."} on failure
    """

    try:
        ensure_system_product_type_templates()
        client = Client.objects.get(pk=client_id)
        system_client = Client.get_system_client()
        product_type = ProductType.objects.select_related("owner").get(pk=product_type_id)
        if product_type.owner_id != system_client.id:
            raise ValueError("Product type must be system/global")

        favorites = _collect_wordstat_favorites(client)
        if not favorites:
            return {"success": False, "error": "В Wordstat нет избранных фраз. Отметьте нужные фразы как «избранное» и повторите."}

        requirements_override = _requirements_payload(product_type)
        requested_name = (name or "").strip()
        requested_short_description = (short_description or "").strip()
        if requested_name or requested_short_description:
            extra_name_rules = ["ДОПОЛНИТЕЛЬНО ДЛЯ ЭТОГО ПРОДУКТА"]
            if requested_name:
                extra_name_rules.append(f"- Название строго: '{requested_name}'.")
            else:
                extra_name_rules.append("- Придумай название сам(а): 2–6 слов, конкретно и по типу продукта.")

            if requested_short_description:
                extra_name_rules.append(
                    f"- short_description максимально близко по смыслу к: '{requested_short_description}'."
                )
            extra_name_rules.append(f"- short_description должен начинаться с '{product_type.name}:'.")
            requirements_override["name"] = f"{requirements_override['name']}\n\n" + "\n".join(extra_name_rules)

        extra_context = _extra_context_for_client(client)

        generator = _new_ai_generator()
        result = generator.generate_client_product_from_type(
            product_type_name=product_type.name,
            product_type_value=product_type.value or "",
            product_type_goal=product_type.goal or "",
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=favorites,
            brand=client.get_brand_display_name(),
            language=language,
            requirements_override=requirements_override,
            additional_context=extra_context,
        )
        if not result.get("success"):
            return {"success": False, "error": result.get("error") or "Не удалось сгенерировать продукт", "raw_response": result.get("raw_response")}

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return {"success": False, "error": "Некорректный ответ генератора", "raw_response": result.get("raw_response")}

        generated_name = str(product_data.get("name") or "").strip()
        final_name = requested_name or generated_name or product_type.name

        generated_short_description = str(product_data.get("short_description") or "").strip()
        if requested_short_description:
            final_short_description = requested_short_description
        elif generated_short_description:
            final_short_description = generated_short_description
        else:
            final_short_description = f"{product_type.name}: {final_name}"

        def _normalize_typed_description(type_name: str, value: str) -> str:
            cleaned = (value or "").strip()
            prefix = f"{(type_name or '').strip()}:".strip()
            if not prefix or prefix == ":":
                return cleaned
            if cleaned.lower().startswith(prefix.lower()):
                return cleaned
            return f"{prefix} {cleaned}".strip()

        def _create_product():
            return ClientProduct.objects.create(
                owner=client,
                product_type=product_type,
                name=final_name,
                short_description=_normalize_typed_description(product_type.name, final_short_description) or None,
                packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
                structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
            )
        created = _create_client_product_with_sequence_retry(_create_product)

        return {"success": True, "product_id": created.id}

    except Exception as exc:
        logger.exception("Failed to generate product for type %s (client=%s): %s", product_type_id, client_id, exc)
        return {"success": False, "error": str(exc)}


@shared_task(bind=True, max_retries=0)
def generate_core_product_task(
    self,
    client_id: int,
    *,
    name: str,
    short_description: str,
    language: str = "ru",
) -> Dict[str, Any]:
    """
    Generate and create a CORE ClientProduct with AI.
    """

    try:
        ensure_system_product_type_templates()
        client = Client.objects.get(pk=client_id)
        system_client = Client.get_system_client()
        core_type = ProductType.objects.filter(owner=system_client, name__iexact="Core").first()
        if not core_type:
            core_type = ProductType.objects.create(owner=system_client, name="Core", value=None, goal=None)
            ensure_system_product_type_templates()

        requirements_override = _requirements_payload(core_type)
        requirements_override["name"] = (
            f"{requirements_override['name']}\n\n"
            "ДОПОЛНИТЕЛЬНО ДЛЯ ЭТОГО ПРОДУКТА\n"
            f"- Название строго: '{name}'.\n"
            f"- short_description должен начинаться с 'Core:' и передавать смысл: {short_description}.\n"
        ).strip()

        extra_context = _extra_context_for_client(client)

        generator = _new_ai_generator()
        result = generator.generate_client_product_from_type(
            product_type_name=core_type.name,
            product_type_value=core_type.value or "",
            product_type_goal=short_description,
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=[],
            brand=client.get_brand_display_name(),
            language=language,
            requirements_override=requirements_override,
            additional_context=extra_context,
        )
        if not result.get("success"):
            return {"success": False, "error": result.get("error") or "Не удалось сгенерировать core-продукт", "raw_response": result.get("raw_response")}

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return {"success": False, "error": "Некорректный ответ генератора", "raw_response": result.get("raw_response")}

        def _normalize_core_description(value: str) -> str:
            cleaned = (value or "").strip()
            prefix = "Core:"
            if cleaned.lower().startswith(prefix.lower()):
                return cleaned
            return f"{prefix} {cleaned}".strip()

        def _create_product():
            return ClientProduct.objects.create(
                owner=client,
                product_type=core_type,
                name=name,
                short_description=_normalize_core_description(short_description),
                packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
                structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
            )
        created = _create_client_product_with_sequence_retry(_create_product)

        return {"success": True, "product_id": created.id}

    except Exception as exc:
        logger.exception("Failed to generate CORE product (client=%s): %s", client_id, exc)
        return {"success": False, "error": str(exc)}


@shared_task(bind=True, max_retries=0)
def generate_related_product_task(
    self,
    client_id: int,
    core_product_id: int,
    product_type_id: int,
    *,
    name: Optional[str] = None,
    hint: str = "",
    language: str = "ru",
) -> Dict[str, Any]:
    """
    Generate and create a related ClientProduct inside a Core product using Core context.
    """

    try:
        ensure_system_product_type_templates()
        client = Client.objects.get(pk=client_id)
        core_product = ClientProduct.objects.select_related("product_type").get(pk=core_product_id, owner=client)
        core_type_name = (getattr(core_product.product_type, "name", None) or "").strip().lower()
        if core_type_name != "core":
            raise ValueError("Related products can be created only inside a Core product")

        system_client = Client.get_system_client()
        product_type = ProductType.objects.select_related("owner").get(pk=product_type_id)
        if product_type.owner_id != system_client.id:
            raise ValueError("Product type must be system/global")
        if (product_type.name or "").strip().lower() == "core":
            raise ValueError("Cannot create Core as a related product")

        requirements_override = _requirements_payload(product_type)

        extra_name_rules = ["ДОПОЛНИТЕЛЬНО ДЛЯ ЭТОГО ПРОДУКТА"]
        if name and name.strip():
            final_requested_name = name.strip()
            extra_name_rules.append(f"- Название строго: '{final_requested_name}'.")
        else:
            final_requested_name = ""
            extra_name_rules.append("- Придумай название сам(а): 2–6 слов, конкретно, связано с Core и выбранным типом продукта.")
        extra_name_rules.append(f"- short_description должен начинаться с '{product_type.name}:' и быть связан с Core.")
        if hint.strip():
            extra_name_rules.append(f"- Уточнение от пользователя: {hint.strip()}")

        requirements_override["name"] = f"{requirements_override['name']}\n\n" + "\n".join(extra_name_rules)

        core_context = _format_core_context(core_product)
        extra_context = _extra_context_for_client(client)
        additional_context = "\n\n".join([x for x in [core_context, extra_context] if x]).strip()

        generator = _new_ai_generator()
        result = generator.generate_client_product_from_type(
            product_type_name=product_type.name,
            product_type_value=product_type.value or "",
            product_type_goal=product_type.goal or "",
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=[],
            brand=client.get_brand_display_name(),
            language=language,
            requirements_override=requirements_override,
            additional_context=additional_context,
        )
        if not result.get("success"):
            return {"success": False, "error": result.get("error") or "Не удалось сгенерировать сопутствующий продукт", "raw_response": result.get("raw_response")}

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return {"success": False, "error": "Некорректный ответ генератора", "raw_response": result.get("raw_response")}

        generated_name = str(product_data.get("name") or "").strip()
        final_name = final_requested_name or generated_name or f"{product_type.name} — сопутствующий продукт"

        generated_short_description = str(product_data.get("short_description") or "").strip()
        if not generated_short_description:
            base = final_requested_name or hint.strip() or "сопутствующий продукт"
            generated_short_description = f"{product_type.name}: {base}"

        def _normalize_typed_description(type_name: str, value: str) -> str:
            cleaned = (value or "").strip()
            prefix = f"{(type_name or '').strip()}:".strip()
            if not prefix or prefix == ":":
                return cleaned
            if cleaned.lower().startswith(prefix.lower()):
                return cleaned
            return f"{prefix} {cleaned}".strip()

        def _create_product():
            core_for_update = ClientProduct.objects.select_for_update().get(pk=core_product_id, owner=client)
            created_product = ClientProduct.objects.create(
                owner=client,
                product_type=product_type,
                name=final_name,
                short_description=_normalize_typed_description(product_type.name, generated_short_description) or None,
                packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
                structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
            )
            _attach_related_product_to_core_structure(core_for_update, created_product)
            return created_product

        created = _create_client_product_with_sequence_retry(_create_product)

        return {"success": True, "product_id": created.id}

    except Exception as exc:
        logger.exception(
            "Failed to generate related product (client=%s, core=%s, type=%s): %s",
            client_id,
            core_product_id,
            product_type_id,
            exc,
        )
        return {"success": False, "error": str(exc)}
