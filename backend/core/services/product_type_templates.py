from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.db import transaction

from core.models import Client, ProductType


def _normalize_name(value: str | None) -> str:
    return (value or "").strip().lower()


_REQUIREMENTS_FIELDS: tuple[str, ...] = (
    "requirements_name",
    "requirements_packages",
    "requirements_audience",
    "requirements_transformation",
    "requirements_metrics",
    "requirements_method",
    "requirements_lesson_format",
    "requirements_program_modules",
    "requirements_packaging",
)


def _default_product_type_requirements() -> dict[str, dict[str, str]]:
    """
    Default AI requirements for standard funnel product types.

    Notes:
    - `lesson_format` in the JSON structure is used by the UI as
      "Формат взаимодействия с клиентом" (not "формат урока").
    - Text is intentionally domain-agnostic and should be adapted by the model
      to the niche using client avatar/pains/desires/objections and Wordstat.
    """

    common_lesson_format_rules = """
Сгенерируй блок "lesson_format" как ФОРМАТ ВЗАИМОДЕЙСТВИЯ С КЛИЕНТОМ (customer journey / delivery), а не как "формат урока".
Верни список этапов взаимодействия (3–8 шт.), где каждый этап:
- короткое название (2–6 слов), отражающее реальный шаг/касание (онбординг, диагностика, выдача материала, сопровождение, проверка, Q&A, отчёт, апселл и т.п. — под нишу),
- "percent" — доля усилий/времени со стороны команды/клиента на этот этап (0–100, можно null).
Если уместно, сделай сумму процентов ≈ 100. Не используй слово "урок", если это не обучение.
""".strip()

    common_method_rules = """
Сгенерируй блок "method" как универсальные компоненты реализации продукта (не только обучение).
Компонент = элемент механики (например: Диагностика, Материалы, Практика/внедрение, Контроль качества, Поддержка, Комьюнити, Созвон, Личный кабинет, Автоматизация и т.п.).
Для каждого компонента дай "template" — универсальный шаблон, как этот компонент выглядит в любой нише (1 короткое предложение).
4–8 строк.
""".strip()

    common_program_rules = """
Сгенерируй "program_modules" как логические модули/этапы результата (не обязательно "уроки").
4–8 модулей. Для каждого: "module" (название) и "result" (измеримый результат/выход).
""".strip()

    common_packaging_rules = """
Сгенерируй "packaging" как упаковку предложения:
- name: короткое название оффера/программы,
- slogan: 5–10 слов, эмоционально и конкретно,
- promise: 1–2 предложения, обещание результата без необоснованных гарантий.
""".strip()

    common_audience_rules = """
Сгенерируй "audience" (4–7 строк): параметры сегментации ЦА (кто, ситуация, уровень, контекст) и конкретные значения под нишу.
""".strip()

    common_transformation_rules = """
Сгенерируй "transformation" (4–7 строк): "was" → "became" как понятные изменения для клиента (до/после), связанные с продуктом.
""".strip()

    common_metrics_rules = """
Сгенерируй "metrics" (4–7 строк): метрика/критерий успеха и обещание по ней (реалистично, без точных гарантий если нельзя).
""".strip()

    return {
        "lead": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа LEAD (лид-магнит).
- Название: конкретное и полезное, без "вода", 3–9 слов.
- short_description: обязательно начинается с "LEAD:" и описывает бесплатную/низкофрикционную ценность, ведущую к выявлению потребности.
""".strip(),
            "requirements_packages": """
Сгенерируй packages для LEAD.
- 1 пакет (обычно бесплатный) или 2 варианта (например, "Стандарт" и "Расширенный").
- description: что человек получает и за сколько времени; под нишу.
- price: null или 0.
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для LEAD сделай акцент на: выдача ценности → микро-результат → сегментация/опрос → приглашение на следующий шаг.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "tripwire": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа TRIPWIRE.
- Название: обещает быстрый ощутимый результат, 3–9 слов.
- short_description: обязательно начинается с "TRIPWIRE:" и отражает первый платёж (низкий чек) + быстрый результат ≤ 7 дней.
""".strip(),
            "requirements_packages": """
Сгенерируй packages для TRIPWIRE.
- 1–2 пакета (например, "Базовый" и "С поддержкой").
- description: конкретный результат и формат выдачи.
- price: укажи приблизительно в диапазоне 1000–3000 (или null, если по нише цена неуместна).
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для TRIPWIRE сделай акцент на: оплата/доступ → быстрый план → выполнение → проверка/обратная связь → лёгкий апселл.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "reactivation": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа REACTIVATION.
- Название: фокус на "вернуться/дожать/снять барьер", 3–9 слов.
- short_description: обязательно начинается с "REACTIVATION:" и описывает догрев "слетевших" после трипвайера (3–7 дней без покупки).
""".strip(),
            "requirements_packages": """
Сгенерируй packages для REACTIVATION.
- 1–2 пакета (например, "Возврат" и "Возврат + разбор").
- price: может быть null/0 (как акция) или небольшая стоимость — под тип и нишу.
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для REACTIVATION сделай акцент на: контакт → выявление причины \"почему не купил\" → снятие возражений → короткое предложение/созвон → решение.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "core": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа CORE (основной продукт).
- Название: отражает главный результат/систему, 3–9 слов.
- short_description: обязательно начинается с "CORE:" и обещает ключевую трансформацию (выручка/кейсы/NPS) без необоснованных гарантий.
""".strip(),
            "requirements_packages": """
Сгенерируй packages для CORE.
- 2–3 пакета (например, "Старт", "Стандарт", "Максимум") с понятными отличиями по поддержке/глубине/скорости.
- price: можно оставить null, если цена не задана.
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для CORE сделай акцент на: онбординг → диагностика → основной цикл внедрения/оказания услуги → контроль качества → сопровождение/поддержка → итоговый отчёт/кейсы.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "premium": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа PREMIUM.
- Название: персонализация/эксклюзив/скорость результата, 3–9 слов.
- short_description: обязательно начинается с "PREMIUM:" и отражает высокий чек + глубину/персональное сопровождение (рост LTV/маржинальности).
""".strip(),
            "requirements_packages": """
Сгенерируй packages для PREMIUM.
- 1–2 пакета (например, "1:1" и "1:1 + команда/доступы"), чётко различай объём личного участия.
- price: можно оставить null (или high-ticket ориентир, если уместно).
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для PREMIUM сделай акцент на: стратегия → персональный план → регулярные 1:1 синки/ревью → совместная реализация → контроль метрик → принятие решений.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "add-ons": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа ADD-ONS (доп. продажи).
- Название: конкретный доп. результат/улучшение, 3–9 слов.
- short_description: обязательно начинается с "ADD-ONS:" и описывает доп. ценность, увеличивающую ARPU (апселл/кросс-селл).
""".strip(),
            "requirements_packages": """
Сгенерируй packages для ADD-ONS.
- 2–4 пакета/позиции (как магазин доп. опций).
- description: чётко \"что добавляем\" и какой эффект.
- price: можно оставить null или указать ориентиры.
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для ADD-ONS сделай акцент на: выбор опции → оплата/доступ → быстрая доставка → внедрение/интеграция → саппорт/гарантия качества.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
        "мероприятие": {
            "requirements_name": """
Сгенерируй name и short_description для продукта типа МЕРОПРИЯТИЕ.
- Название: конкретная тема/формат события, 3–9 слов.
- short_description: обязательно начинается с "Мероприятие:" и отражает формат (вебинар/воркшоп/интенсив/офлайн) + ключевую пользу.
""".strip(),
            "requirements_packages": """
Сгенерируй packages для типа МЕРОПРИЯТИЕ.
- 1–3 пакета (например, "Онлайн", "Офлайн", "VIP/Запись").
- description: что включено в участие (доступ, материалы, Q&A, запись, бонусы).
- price: число или null, если цена ещё не определена.
""".strip(),
            "requirements_audience": common_audience_rules,
            "requirements_transformation": common_transformation_rules,
            "requirements_metrics": common_metrics_rules,
            "requirements_method": common_method_rules,
            "requirements_lesson_format": f"""{common_lesson_format_rules}
Для МЕРОПРИЯТИЯ сделай акцент на: анонс/регистрация → подготовка → проведение события → постматериалы/запись → follow-up и следующий шаг.
""".strip(),
            "requirements_program_modules": common_program_rules,
            "requirements_packaging": common_packaging_rules,
        },
    }


_DEFAULT_PRODUCT_TYPE_KEYS = frozenset(_default_product_type_requirements().keys())


def is_system_product_type_name(value: str | None) -> bool:
    if not value:
        return False
    return _normalize_name(value) in _DEFAULT_PRODUCT_TYPE_KEYS


def _generic_product_type_requirements(type_name: str) -> dict[str, str]:
    type_display = (type_name or "").strip() or "Тип продукта"

    common_lesson_format_rules = """
Сгенерируй блок "lesson_format" как ФОРМАТ ВЗАИМОДЕЙСТВИЯ С КЛИЕНТОМ (customer journey / delivery), а не как "формат урока".
Верни список этапов взаимодействия (3–8 шт.), где каждый этап:
- короткое название (2–6 слов), отражающее реальный шаг/касание (онбординг, диагностика, согласование, доставка, сопровождение, проверка, Q&A, отчёт и т.п. — под нишу),
- "percent" — доля усилий/времени на этот этап (0–100, можно null).
Если уместно, сделай сумму процентов ≈ 100. Не используй слово "урок", если это не обучение.
""".strip()

    return {
        "requirements_name": f"""
Сгенерируй name и short_description для продукта типа {type_display}.
- Название: 3–9 слов, конкретно и по делу.
- short_description: обязательно начинается с "{type_display}:" и объясняет ценность/результат без необоснованных гарантий.
""".strip(),
        "requirements_packages": f"""
Сгенерируй packages для продукта типа {type_display}.
- 1–3 пакета с понятными отличиями (по объёму/поддержке/скорости/доступам — под нишу).
- description: что получает клиент, в каком формате и за какой срок.
- price: число или null, если цена не задана.
""".strip(),
        "requirements_audience": """
Сгенерируй "audience" (4–7 строк): параметры сегментации ЦА (кто, ситуация, уровень, контекст) и конкретные значения под нишу.
""".strip(),
        "requirements_transformation": """
Сгенерируй "transformation" (4–7 строк): "was" → "became" как понятные изменения для клиента (до/после), связанные с продуктом.
""".strip(),
        "requirements_metrics": """
Сгенерируй "metrics" (4–7 строк): метрика/критерий успеха и обещание по ней (реалистично, без точных гарантий если нельзя).
""".strip(),
        "requirements_method": """
Сгенерируй "method" как универсальные компоненты реализации продукта (не только обучение).
4–8 строк. Для каждого компонента дай "template" — универсальный шаблон, как он выглядит в любой нише (1 короткое предложение).
""".strip(),
        "requirements_lesson_format": common_lesson_format_rules,
        "requirements_program_modules": """
Сгенерируй "program_modules" как логические модули/этапы результата (не обязательно "уроки").
4–8 модулей. Для каждого: "module" (название) и "result" (измеримый результат/выход).
""".strip(),
        "requirements_packaging": """
Сгенерируй "packaging" как упаковку предложения:
- name: короткое название оффера/программы,
- slogan: 5–10 слов, эмоционально и конкретно,
- promise: 1–2 предложения, обещание результата без необоснованных гарантий.
""".strip(),
    }


def ensure_system_product_type_requirements() -> int:
    """
    Fill missing requirements_* fields for system (global) product types.

    Returns the number of ProductType rows updated.
    """

    system_client = Client.get_system_client()
    templates = _default_product_type_requirements()
    updated = 0

    for product_type in ProductType.objects.filter(owner=system_client).order_by("id"):
        key = _normalize_name(product_type.name)
        template = templates.get(key) or _generic_product_type_requirements(product_type.name)

        changed_fields: list[str] = []
        for field in _REQUIREMENTS_FIELDS:
            current = getattr(product_type, field, None)
            if isinstance(current, str) and current.strip():
                continue
            value = template.get(field)
            if not value:
                continue
            setattr(product_type, field, value)
            changed_fields.append(field)

        if changed_fields:
            product_type.save(update_fields=changed_fields)
            updated += 1

    return updated


def get_fibonatty_client() -> Optional[Client]:
    slug = (getattr(settings, "FIBONATTY_TEMPLATE_CLIENT_SLUG", None) or "fibonatty").strip()
    if slug:
        client = Client.objects.filter(slug=slug).first()
        if client:
            return client

    client = Client.objects.filter(name__iexact="Fibonatty").first()
    if client:
        return client

    return Client.objects.filter(name__icontains="Fibonatty").order_by("id").first()


def sync_product_types(source: Client, target: Client) -> int:
    if source.pk == target.pk:
        return 0

    source_rows = list(
        ProductType.objects.filter(owner=source)
        .order_by("id")
        .values(
            "name",
            "value",
            "goal",
            "requirements_name",
            "requirements_packages",
            "requirements_audience",
            "requirements_transformation",
            "requirements_metrics",
            "requirements_method",
            "requirements_lesson_format",
            "requirements_program_modules",
            "requirements_packaging",
        )
    )
    if not source_rows:
        return 0

    existing_names = {
        _normalize_name(name)
        for name in ProductType.objects.filter(owner=target).values_list("name", flat=True)
    }

    to_create: list[ProductType] = []
    for row in source_rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        key = _normalize_name(name)
        if key in existing_names:
            continue
        existing_names.add(key)
        to_create.append(
            ProductType(
                owner=target,
                name=name,
                value=row.get("value"),
                goal=row.get("goal"),
                requirements_name=row.get("requirements_name"),
                requirements_packages=row.get("requirements_packages"),
                requirements_audience=row.get("requirements_audience"),
                requirements_transformation=row.get("requirements_transformation"),
                requirements_metrics=row.get("requirements_metrics"),
                requirements_method=row.get("requirements_method"),
                requirements_lesson_format=row.get("requirements_lesson_format"),
                requirements_program_modules=row.get("requirements_program_modules"),
                requirements_packaging=row.get("requirements_packaging"),
            )
        )

    if not to_create:
        return 0

    ProductType.objects.bulk_create(to_create)
    return len(to_create)


@transaction.atomic
def migrate_client_product_types_to_system(client: Client) -> int:
    """
    Move (and deduplicate) client-scoped product types into the system client.

    - Products that reference client-owned types are re-pointed to the system type by normalized name.
    - Client-owned ProductType rows are deleted afterwards.
    - If a client type name doesn't exist in system, it is created in system (including requirements_* fields).

    Returns the number of ClientProduct rows updated.
    """

    system_client = Client.get_system_client()
    if client.pk == system_client.pk:
        return 0

    from core.models import ClientProduct  # local import to avoid circulars in managed=False models

    client_types = list(ProductType.objects.filter(owner=client).order_by("id"))
    if not client_types:
        return 0

    ensure_system_product_type_templates()

    system_types = list(ProductType.objects.filter(owner=system_client).order_by("id"))
    system_by_name = {_normalize_name(t.name): t for t in system_types if (t.name or "").strip()}

    updated_products = 0

    for old_type in client_types:
        key = _normalize_name(old_type.name)
        if not key:
            continue

        system_type = system_by_name.get(key)
        if not system_type:
            system_type = ProductType.objects.create(
                owner=system_client,
                name=(old_type.name or "").strip() or "Type",
                value=old_type.value,
                goal=old_type.goal,
                requirements_name=getattr(old_type, "requirements_name", None),
                requirements_packages=getattr(old_type, "requirements_packages", None),
                requirements_audience=getattr(old_type, "requirements_audience", None),
                requirements_transformation=getattr(old_type, "requirements_transformation", None),
                requirements_metrics=getattr(old_type, "requirements_metrics", None),
                requirements_method=getattr(old_type, "requirements_method", None),
                requirements_lesson_format=getattr(old_type, "requirements_lesson_format", None),
                requirements_program_modules=getattr(old_type, "requirements_program_modules", None),
                requirements_packaging=getattr(old_type, "requirements_packaging", None),
            )
            system_by_name[key] = system_type

        updated_products += ClientProduct.objects.filter(owner=client, product_type=old_type).update(product_type=system_type)

    ProductType.objects.filter(owner=client).delete()
    return updated_products


def _dedupe_system_product_types(system_client: Client) -> int:
    from core.models import ClientProduct  # local import to avoid circulars in managed=False models

    removed = 0
    rows = list(ProductType.objects.filter(owner=system_client).order_by("id"))
    grouped: dict[str, list[ProductType]] = {}

    for row in rows:
        key = _normalize_name(row.name)
        if not key:
            continue
        grouped.setdefault(key, []).append(row)

    for items in grouped.values():
        if len(items) <= 1:
            continue
        keep = items[0]
        duplicates = items[1:]
        duplicate_ids = [item.id for item in duplicates]
        if not duplicate_ids:
            continue
        ClientProduct.objects.filter(product_type_id__in=duplicate_ids).update(product_type=keep)
        ProductType.objects.filter(id__in=duplicate_ids).delete()
        removed += len(duplicate_ids)

    return removed


@transaction.atomic
def ensure_system_product_type_templates() -> int:
    """
    Ensure system client contains product type templates.

    Currently seeds/syncs from the Fibonatty client (if present).
    Returns the number of ProductType rows added to the system client.
    """

    system_client = Client.get_system_client()
    source_client = get_fibonatty_client()
    added = 0
    if source_client and source_client.pk != system_client.pk:
        added = sync_product_types(source_client, system_client)

    event_name = "Мероприятие"
    existing_names = {
        _normalize_name(name)
        for name in ProductType.objects.filter(owner=system_client).values_list("name", flat=True)
    }
    event_key = _normalize_name(event_name)
    if event_key not in existing_names:
        event_template = _default_product_type_requirements().get(event_key) or _generic_product_type_requirements(event_name)
        ProductType.objects.create(
            owner=system_client,
            name=event_name,
            value="Событие с фиксированными датой/местом и продажей участия.",
            goal="Регистрация и продажа мест на мероприятие.",
            requirements_name=event_template.get("requirements_name"),
            requirements_packages=event_template.get("requirements_packages"),
            requirements_audience=event_template.get("requirements_audience"),
            requirements_transformation=event_template.get("requirements_transformation"),
            requirements_metrics=event_template.get("requirements_metrics"),
            requirements_method=event_template.get("requirements_method"),
            requirements_lesson_format=event_template.get("requirements_lesson_format"),
            requirements_program_modules=event_template.get("requirements_program_modules"),
            requirements_packaging=event_template.get("requirements_packaging"),
        )
        added += 1

    _dedupe_system_product_types(system_client)
    ensure_system_product_type_requirements()
    return added
