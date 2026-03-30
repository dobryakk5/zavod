from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Client,
    ClientProduct,
    CoachingGoal,
    CoachingGoalCompetency,
    ContactCoachingProfile,
    CRMTask,
    CRMTaskHistory,
    MapContact,
    MapContactTag,
    MapCRMCategory,
    MapCRMDeal,
    MapCRMEvent,
    MapCRMEventType,
    MapCRMNote,
    MapCRMPayment,
    MapCRMTag,
    ProductType,
    UserTenantBinding,
)


DEMO_SOURCE_PREFIX = "demo-fibonatty"
COMPETENCY_COLORS = {
    "confidence": "#2F8F7A",
    "communication": "#7C70E8",
    "boundaries": "#D67646",
    "focus": "#4B8EF5",
    "energy": "#C2922D",
}


@dataclass(frozen=True)
class DemoContactSpec:
    key: str
    name: str
    email: str
    phone: str
    source: str
    category: str | None
    deal_stage: str
    deal_amount: Decimal
    notes: str
    intention: str
    focus: str
    competency_base: dict[str, tuple[str, int, int]]
    goals: list[dict]
    milestones: list[dict]
    notes_items: list[tuple[str, str, bool]]
    payment_status: str
    payment_method: str
    payment_description: str
    event_title: str
    status_badge: str
    tags: list[tuple[str, str, str]]


class Command(BaseCommand):
    help = "Seeds demo coaching/CRM data for a tenant so it can be used for product demonstrations."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, default=3)
        parser.add_argument(
            "--no-reset",
            action="store_false",
            dest="reset_demo",
            help="Keep previously seeded demo entities instead of recreating them.",
        )

    def handle(self, *args, **options):
        tenant_id = int(options["tenant_id"])
        reset_demo = bool(options["reset_demo"])

        tenant = Client.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise CommandError(f"Tenant {tenant_id} not found")

        with transaction.atomic():
            if reset_demo:
                self._clear_demo_data(tenant_id=tenant_id)

            category_ids = {
                item.name.lower(): int(item.id)
                for item in MapCRMCategory.objects.all()
            }
            event_type = self._get_or_create_event_type()
            product = self._get_or_create_demo_product(tenant_id=tenant_id)
            now = timezone.now()
            demo_specs = self._demo_specs(now=now)

            created_contacts = []
            for index, spec in enumerate(demo_specs):
                contact = self._upsert_contact(spec=spec, category_ids=category_ids)
                self._ensure_binding(tenant_id=tenant_id, contact_id=int(contact.id), key=spec.key)
                self._seed_contact_tags(contact_id=int(contact.id), tags=spec.tags)
                self._seed_coaching_profile(
                    tenant_id=tenant_id,
                    contact_id=int(contact.id),
                    spec=spec,
                    now=now,
                    index=index,
                )
                self._seed_crm_notes(contact_id=int(contact.id), notes_items=spec.notes_items)
                self._seed_deal_and_payment(
                    contact_id=int(contact.id),
                    spec=spec,
                    product_id=int(product.id),
                    payment_index=index,
                    now=now,
                )
                self._seed_events(
                    contact_id=int(contact.id),
                    spec=spec,
                    event_type_id=int(event_type.id),
                    now=now,
                    index=index,
                )
                created_contacts.append(contact)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded demo for tenant {tenant_id}: "
                f"{len(created_contacts)} contacts, "
                f"{ContactCoachingProfile.objects.filter(tenant_id=tenant_id).count()} coaching profiles."
            )
        )

    def _clear_demo_data(self, *, tenant_id: int) -> None:
        binding_prefix = self._binding_prefix(tenant_id)
        demo_contact_ids = list(
            UserTenantBinding.objects
            .filter(
                tenant_id=tenant_id,
                provider=UserTenantBinding.PROVIDER_CONTACT,
                provider_user_id__startswith=binding_prefix,
                contact_id__isnull=False,
            )
            .values_list("contact_id", flat=True)
            .distinct()
        )
        if not demo_contact_ids:
            return

        MapCRMPayment.objects.filter(contact_id__in=demo_contact_ids).delete()
        MapCRMDeal.objects.filter(contact_id__in=demo_contact_ids).delete()
        MapCRMEvent.objects.filter(contact_id__in=demo_contact_ids).delete()
        MapCRMNote.objects.filter(contact_id__in=demo_contact_ids).delete()
        MapContactTag.objects.filter(contact_id__in=demo_contact_ids).delete()
        ContactCoachingProfile.objects.filter(tenant_id=tenant_id, contact_id__in=demo_contact_ids).delete()
        UserTenantBinding.objects.filter(
            tenant_id=tenant_id,
            provider=UserTenantBinding.PROVIDER_CONTACT,
            provider_user_id__startswith=binding_prefix,
        ).delete()

        remaining_bound_ids = set(
            UserTenantBinding.objects
            .filter(contact_id__in=demo_contact_ids, contact_id__isnull=False)
            .values_list("contact_id", flat=True)
        )
        safe_delete_ids = [contact_id for contact_id in demo_contact_ids if contact_id not in remaining_bound_ids]
        if safe_delete_ids:
            MapContact.objects.filter(id__in=safe_delete_ids, source__startswith=DEMO_SOURCE_PREFIX).delete()

    def _get_or_create_event_type(self) -> MapCRMEventType:
        event_type = MapCRMEventType.objects.filter(name="Индивидуальная сессия").first()
        if event_type is not None:
            return event_type
        return MapCRMEventType.objects.create(
            name="Индивидуальная сессия",
            description="Демо-тип сессии для коучинговых клиентов",
            duration_minutes=60,
            color="#5C52E0",
        )

    def _get_or_create_demo_product(self, *, tenant_id: int) -> ClientProduct:
        product_type, _ = ProductType.objects.get_or_create(
            owner_id=tenant_id,
            name="Коучинговая программа",
            defaults={
                "value": "Сопровождение клиента с видимым прогрессом",
                "goal": "Показать, как Fibonatty ведет длительную работу с клиентом",
            },
        )
        product, _ = ClientProduct.objects.update_or_create(
            owner_id=tenant_id,
            name="Демо: коучинговое сопровождение",
            defaults={
                "product_type_id": int(product_type.id),
                "status": ClientProduct.STATUS_ACTIVE,
                "short_description": "Демо-продукт для презентации клиентского сопровождения, прогресса и оплат.",
                "packages": [
                    {
                        "id": "demo-coaching-package",
                        "name": "Пакет из 6 сессий",
                        "price": 25000,
                        "kind": "service_package",
                        "service_unit": "sessions",
                        "service_quantity": 6,
                    }
                ],
                "structure": {
                    "format": "one-to-one",
                    "focus": "progress-demo",
                },
            },
        )
        return product

    def _upsert_contact(self, *, spec: DemoContactSpec, category_ids: dict[str, int]) -> MapContact:
        defaults = {
            "name": spec.name,
            "phone": spec.phone,
            "source": spec.source,
            "deal_stage": spec.deal_stage,
            "deal_amount": spec.deal_amount,
            "category_id": category_ids.get((spec.category or "").lower()),
            "status": "active",
            "notes": spec.notes,
        }
        contact, _ = MapContact.objects.update_or_create(
            email=spec.email,
            defaults=defaults,
        )
        return contact

    def _ensure_binding(self, *, tenant_id: int, contact_id: int, key: str) -> None:
        UserTenantBinding.objects.update_or_create(
            tenant_id=tenant_id,
            provider=UserTenantBinding.PROVIDER_CONTACT,
            provider_user_id=f"{self._binding_prefix(tenant_id)}{key}",
            defaults={
                "contact_id": contact_id,
                "is_active": True,
            },
        )

    def _seed_contact_tags(self, *, contact_id: int, tags: list[tuple[str, str, str]]) -> None:
        for tag_type, tag_value, description in tags:
            tag, _ = MapCRMTag.objects.get_or_create(type=tag_type, value=tag_value)
            MapContactTag.objects.update_or_create(
                contact_id=contact_id,
                tag_id=int(tag.id),
                defaults={"description": description},
            )

    def _seed_coaching_profile(
        self,
        *,
        tenant_id: int,
        contact_id: int,
        spec: DemoContactSpec,
        now,
        index: int,
    ) -> None:
        competencies = []
        for comp_id, (name, start_score, score) in spec.competency_base.items():
            competencies.append(
                {
                    "id": comp_id,
                    "name": name,
                    "startScore": start_score,
                    "score": score,
                    "color": COMPETENCY_COLORS.get(comp_id, "#5C52E0"),
                }
            )

        goals = []
        for goal_index, goal in enumerate(spec.goals, start=1):
            goals.append(
                {
                    "id": f"{spec.key}-goal-{goal_index}",
                    "title": goal["title"],
                    "progress": int(goal["progress"]),
                    "horizon": goal.get("horizon", "quarter"),
                    "status": goal.get("status", "active"),
                    "sortOrder": goal_index - 1,
                    "competencyLinks": [
                        {
                            "competencyId": link["competencyId"],
                            "competencyName": link["competencyName"],
                            "weight": float(link["weight"]),
                        }
                        for link in goal["competencyLinks"]
                    ],
                    "steps": goal["steps"],
                    "createdAt": (now - timedelta(days=80 - (index * 9) - (goal_index * 6))).isoformat(),
                }
            )

        milestones = [
            {
                "id": f"{spec.key}-milestone-{item_index}",
                "clientId": contact_id,
                "goalId": f"{spec.key}-goal-{item.get('goalIndex', 1)}",
                "text": item["text"],
                "note": item.get("note", ""),
                "createdAt": (now - timedelta(days=item.get("daysAgo", 0))).isoformat(),
            }
            for item_index, item in enumerate(spec.milestones, start=1)
        ]

        sessions = []
        for session_index in range(4):
            session_dt = now - timedelta(days=(28 - index * 2) - session_index * 14)
            sessions.append(
                {
                    "id": f"{spec.key}-session-{session_index + 1}",
                    "clientId": contact_id,
                    "number": 4 - session_index,
                    "date": session_dt.isoformat(),
                    "notes": [
                        "Зафиксировали новый рабочий паттерн и обсудили, что уже получилось удержать.",
                        "Разобрали сопротивление, которое мешает переходу к следующему шагу.",
                        "Уточнили цель и перевели размышления в конкретные действия на неделю.",
                        "Провели стартовую диагностику и выделили главную точку роста.",
                    ][session_index],
                    "coachNotes": [
                        "Клиент лучше выдерживает напряжение и не уходит в избегание.",
                        "Нужно поддержать ритм выполнения заданий между встречами.",
                        "Полезно вернуться к теме границ в следующей сессии.",
                        "Запрос хорошо формулируется, мотивация высокая.",
                    ][session_index],
                }
            )

        if index < 3:
            sessions.insert(
                0,
                {
                    "id": f"{spec.key}-session-upcoming",
                    "clientId": contact_id,
                    "number": len(sessions) + 1,
                    "date": (now + timedelta(hours=3 + index * 2)).isoformat(),
                    "notes": "Плановая сессия на этой неделе",
                    "coachNotes": "Подготовить обзор прогресса и следующий milestone",
                },
            )

        wheel = [
            {"id": "confidence", "label": "Уверенность", "score": competencies[0]["score"]},
            {"id": "communication", "label": "Коммуникация", "score": competencies[1]["score"]},
            {"id": "boundaries", "label": "Границы", "score": competencies[2]["score"]},
            {"id": "focus", "label": "Фокус", "score": competencies[3]["score"]},
        ]

        ContactCoachingProfile.objects.update_or_create(
            tenant_id=tenant_id,
            contact_id=contact_id,
            defaults={
                "intention": spec.intention,
                "wheel": wheel,
                "competencies": competencies,
                "sessions": sessions,
            },
        )
        profile = ContactCoachingProfile.objects.get(tenant_id=tenant_id, contact_id=contact_id)
        CoachingGoal.objects.filter(profile=profile, goal_type=CoachingGoal.TYPE_PERSONAL).delete()
        CRMTask.objects.filter(source="coaching", contact_id=contact_id).delete()

        for goal in goals:
            goal_row = CoachingGoal.objects.create(
                profile=profile,
                public_id=str(goal["id"]),
                goal_type=CoachingGoal.TYPE_PERSONAL,
                title=str(goal["title"]),
                progress=int(goal["progress"]),
                horizon=str(goal["horizon"]),
                status=str(goal["status"]),
                sort_order=int(goal["sortOrder"]),
                created_at=datetime.fromisoformat(str(goal["createdAt"]).replace("Z", "+00:00")),
            )
            CoachingGoalCompetency.objects.bulk_create(
                [
                    CoachingGoalCompetency(
                        goal=goal_row,
                        competency_id=str(link["competencyId"]),
                        competency_name=str(link["competencyName"]),
                        weight=float(link["weight"]),
                        sort_order=link_index,
                    )
                    for link_index, link in enumerate(goal["competencyLinks"])
                ]
            )
            for step in goal["steps"]:
                done_at = step.get("doneAt")
                done_at_value = datetime.fromisoformat(str(done_at).replace("Z", "+00:00")) if done_at else None
                task = CRMTask.objects.create(
                    source="coaching",
                    contact_id=contact_id,
                    goal_id=goal_row.public_id,
                    title=str(step["text"]),
                    description=None,
                    status="done" if step.get("done") else "open",
                    priority=2,
                    due_at=None,
                    is_milestone=bool(step.get("isMilestone")),
                    milestone_note=str(step.get("milestoneNote") or ""),
                    done_at=done_at_value,
                    created_by=0,
                    created_at=done_at_value or now,
                    updated_at=done_at_value or now,
                )
                CRMTaskHistory.objects.create(
                    task=task,
                    note="Создано коучем",
                    status=task.status,
                    created_by=0,
                    created_at=task.created_at,
                )
        for milestone in milestones:
            created_at = datetime.fromisoformat(str(milestone["createdAt"]).replace("Z", "+00:00"))
            task = CRMTask.objects.create(
                source="coaching",
                contact_id=contact_id,
                goal_id=str(milestone.get("goalId") or "") or None,
                title=str(milestone["text"]),
                description=None,
                status="done",
                priority=2,
                due_at=None,
                is_milestone=True,
                milestone_note=str(milestone.get("note") or ""),
                done_at=created_at,
                created_by=0,
                created_at=created_at,
                updated_at=created_at,
            )
            CRMTaskHistory.objects.create(
                task=task,
                note="Создано коучем",
                status=task.status,
                created_by=0,
                created_at=created_at,
            )

    def _seed_crm_notes(self, *, contact_id: int, notes_items: list[tuple[str, str, bool]]) -> None:
        for title, content, is_important in notes_items:
            MapCRMNote.objects.update_or_create(
                contact_id=contact_id,
                title=title,
                defaults={
                    "content": content,
                    "is_important": is_important,
                },
            )

    def _seed_deal_and_payment(self, *, contact_id: int, spec: DemoContactSpec, product_id: int, payment_index: int, now) -> None:
        deal, _ = MapCRMDeal.objects.update_or_create(
            contact_id=contact_id,
            product_id=product_id,
            defaults={
                "stage": spec.deal_stage,
                "amount": spec.deal_amount,
                "currency": "RUB",
                "description": f"Демо-предложение: {spec.focus}",
                "lost_reason_code": "timing" if spec.deal_stage == "lost" else "",
                "lost_reason_text": "Клиент отложил решение на несколько месяцев" if spec.deal_stage == "lost" else "",
                "lost_at": now - timedelta(days=9) if spec.deal_stage == "lost" else None,
            },
        )

        payment_defaults = {
            "deal_id": int(deal.id),
            "product_id": product_id,
            "event_id": None,
            "amount": spec.deal_amount,
            "currency": "RUB",
            "status": spec.payment_status,
            "payment_method": spec.payment_method,
            "transaction_id": f"demo-{spec.key}-payment",
            "description": spec.payment_description,
            "planned_at": now + timedelta(days=3 - payment_index),
            "paid_at": now - timedelta(days=15 - payment_index) if spec.payment_status == "paid" else None,
        }
        MapCRMPayment.objects.update_or_create(
            contact_id=contact_id,
            transaction_id=f"demo-{spec.key}-payment",
            defaults=payment_defaults,
        )

    def _seed_events(self, *, contact_id: int, spec: DemoContactSpec, event_type_id: int, now, index: int) -> None:
        completed_start = now - timedelta(days=21 - index * 2)
        planned_start = now + timedelta(days=index + 1, hours=11 - index)

        events = [
            {
                "title": f"{spec.event_title} · Разбор прогресса",
                "description": "Подведение итогов, фиксация сдвига и подготовка следующих действий.",
                "start_time": completed_start,
                "end_time": completed_start + timedelta(minutes=60),
                "status": "completed",
                "location": "Zoom",
                "notes": f"После встречи клиент отмечает: {spec.status_badge.lower()}",
                "price": spec.deal_amount if spec.payment_status == "paid" else None,
            },
            {
                "title": f"{spec.event_title} · Следующий шаг",
                "description": "Плановая встреча, где смотрим на цели, выполненные шаги и зону сопротивления.",
                "start_time": planned_start,
                "end_time": planned_start + timedelta(minutes=60),
                "status": "scheduled",
                "location": "Zoom",
                "notes": "Встреча уже видна в расписании клиента.",
                "price": spec.deal_amount if spec.payment_status == "pending" else None,
            },
        ]

        for item in events:
            MapCRMEvent.objects.update_or_create(
                contact_id=contact_id,
                title=item["title"],
                defaults={
                    "event_type_id": event_type_id,
                    "description": item["description"],
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "location": item["location"],
                    "status": item["status"],
                    "notes": item["notes"],
                    "price": item["price"],
                },
            )

    def _binding_prefix(self, tenant_id: int) -> str:
        return f"demo:tenant:{tenant_id}:"

    def _demo_specs(self, *, now) -> list[DemoContactSpec]:
        recent_day = (now - timedelta(days=3)).date().isoformat()
        mid_day = (now - timedelta(days=10)).date().isoformat()
        older_day = (now - timedelta(days=22)).date().isoformat()

        return [
            DemoContactSpec(
                key="olga-smirnova",
                name="Ольга Смирнова",
                email="demo.olga@fibonatty.test",
                phone="+7 900 100-10-10",
                source=f"{DEMO_SOURCE_PREFIX}-tenant-3",
                category="VIP",
                deal_stage="paid",
                deal_amount=Decimal("25000.00"),
                notes="Показывает сильный отклик на работу с уверенностью и границами.",
                intention="Перестать зависеть от одобрения руководства и спокойно отстаивать свою позицию.",
                focus="Уверенность в себе",
                competency_base={
                    "confidence": ("Уверенность", 38, 82),
                    "communication": ("Коммуникация", 42, 71),
                    "boundaries": ("Границы", 28, 58),
                    "focus": ("Цели и фокус", 55, 90),
                },
                goals=[
                    {
                        "title": "Свободно говорить о повышении и роли в команде",
                        "progress": 84,
                        "competencyLinks": [
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.45},
                            {"competencyId": "communication", "competencyName": "Коммуникация", "weight": 0.3},
                            {"competencyId": "boundaries", "competencyName": "Границы", "weight": 0.25},
                        ],
                        "steps": [
                            {"text": "Подготовить тезисы для разговора", "done": True, "doneAt": older_day},
                            {"text": "Провести разговор с руководителем", "done": True, "isMilestone": True, "doneAt": mid_day},
                            {"text": "Зафиксировать новую роль и ожидания", "done": False},
                        ],
                    },
                    {
                        "title": "Стабильно удерживать фокус на личных целях без срывов",
                        "progress": 76,
                        "competencyLinks": [
                            {"competencyId": "focus", "competencyName": "Цели и фокус", "weight": 0.7},
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.3},
                        ],
                        "steps": [
                            {"text": "Вести утренний ритуал 5 дней подряд", "done": True, "doneAt": recent_day},
                            {"text": "Пересобрать календарь недели", "done": False},
                        ],
                    },
                ],
                milestones=[
                    {"goalIndex": 1, "text": "Первый разговор без избегания", "note": "Клиент сама назвала это прорывом", "daysAgo": 9},
                    {"goalIndex": 2, "text": "Неделя без хаотичных переработок", "note": "Лучше удерживает границы", "daysAgo": 4},
                ],
                notes_items=[
                    ("Демо: сильный инсайт", "После встречи клиент впервые заметила, что спокойно выдерживает напряжение в разговоре.", True),
                    ("Демо: что поддержать", "Нужно закрепить новый стиль коммуникации через короткие действия между сессиями.", False),
                ],
                payment_status="paid",
                payment_method="bank_card",
                payment_description="Оплачен пакет сопровождения на 6 встреч",
                event_title="Индивидуальная сессия",
                status_badge="Прорыв",
                tags=[
                    ("goal", "Свобода", "Хочет чувствовать больше опоры на себя."),
                    ("pain", "Низкая самооценка", "Сильно зависит от внешней оценки."),
                ],
            ),
            DemoContactSpec(
                key="mikhail-kovalev",
                name="Михаил Ковалев",
                email="demo.mikhail@fibonatty.test",
                phone="+7 900 100-10-20",
                source=f"{DEMO_SOURCE_PREFIX}-tenant-3",
                category="Стандарт",
                deal_stage="payment_expected",
                deal_amount=Decimal("18000.00"),
                notes="Фокус на карьерном переходе и уверенной самопрезентации.",
                intention="Собрать новый карьерный трек и перестать откладывать активные отклики.",
                focus="Карьерный рост",
                competency_base={
                    "confidence": ("Уверенность", 32, 61),
                    "communication": ("Коммуникация", 35, 57),
                    "boundaries": ("Границы", 44, 62),
                    "focus": ("Цели и фокус", 41, 75),
                },
                goals=[
                    {
                        "title": "Обновить позиционирование и выйти на 5 релевантных откликов",
                        "progress": 68,
                        "competencyLinks": [
                            {"competencyId": "focus", "competencyName": "Цели и фокус", "weight": 0.5},
                            {"competencyId": "communication", "competencyName": "Коммуникация", "weight": 0.3},
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.2},
                        ],
                        "steps": [
                            {"text": "Обновить резюме", "done": True, "doneAt": mid_day},
                            {"text": "Собрать 5 вакансий для отклика", "done": True, "doneAt": recent_day},
                            {"text": "Отправить отклики и запросить обратную связь", "done": False},
                        ],
                    },
                    {
                        "title": "Говорить о своей ценности без зажатости",
                        "progress": 54,
                        "competencyLinks": [
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.55},
                            {"competencyId": "communication", "competencyName": "Коммуникация", "weight": 0.45},
                        ],
                        "steps": [
                            {"text": "Записать ответы на частые вопросы", "done": True, "doneAt": older_day},
                            {"text": "Потренировать самопрезентацию", "done": False},
                        ],
                    },
                ],
                milestones=[
                    {"goalIndex": 1, "text": "Резюме собрано в новой логике", "note": "Ушел от расплывчатой формулировки роли", "daysAgo": 10},
                ],
                notes_items=[
                    ("Демо: карьерный паттерн", "Часто занижает собственный вклад в результат.", True),
                    ("Демо: опора", "Хорошо реагирует на формат коротких отчетов между сессиями.", False),
                ],
                payment_status="pending",
                payment_method="invoice",
                payment_description="Ожидается оплата следующего блока из 4 встреч",
                event_title="Карьерная сессия",
                status_badge="Завтра",
                tags=[
                    ("goal", "Деньги", "Нужен рост дохода и новая роль."),
                    ("pain", "Нет времени", "Застревает в рутине и не доходит до активных действий."),
                ],
            ),
            DemoContactSpec(
                key="alina-lesenko",
                name="Алина Лесенко",
                email="demo.alina@fibonatty.test",
                phone="+7 900 100-10-30",
                source=f"{DEMO_SOURCE_PREFIX}-tenant-3",
                category="Новички",
                deal_stage="call",
                deal_amount=Decimal("15000.00"),
                notes="Запрос про отношения и устойчивость в коммуникации.",
                intention="Научиться говорить о потребностях без вины и не срываться в молчание.",
                focus="Отношения",
                competency_base={
                    "confidence": ("Уверенность", 29, 52),
                    "communication": ("Коммуникация", 31, 49),
                    "boundaries": ("Границы", 22, 44),
                    "focus": ("Цели и фокус", 34, 57),
                },
                goals=[
                    {
                        "title": "Говорить о границах без отложенных конфликтов",
                        "progress": 48,
                        "competencyLinks": [
                            {"competencyId": "boundaries", "competencyName": "Границы", "weight": 0.5},
                            {"competencyId": "communication", "competencyName": "Коммуникация", "weight": 0.3},
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.2},
                        ],
                        "steps": [
                            {"text": "Отследить три ситуации, где промолчала", "done": True, "doneAt": older_day},
                            {"text": "Подготовить одну фразу для спокойного отказа", "done": True, "doneAt": recent_day},
                            {"text": "Проговорить границу в важном разговоре", "done": False, "isMilestone": True},
                        ],
                    },
                    {
                        "title": "Перестать откатываться в чувство вины после честного диалога",
                        "progress": 36,
                        "competencyLinks": [
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.6},
                            {"competencyId": "boundaries", "competencyName": "Границы", "weight": 0.4},
                        ],
                        "steps": [
                            {"text": "Вести журнал реакции после разговора", "done": False},
                        ],
                    },
                ],
                milestones=[
                    {"goalIndex": 1, "text": "Первый спокойный отказ без оправданий", "note": "Даже при волнении смогла удержать границу", "daysAgo": 5},
                ],
                notes_items=[
                    ("Демо: эмоциональная динамика", "После честных разговоров быстро откатывается в чувство вины.", True),
                ],
                payment_status="pending",
                payment_method="bank_card",
                payment_description="Предоплата за стартовый пакет после диагностической встречи",
                event_title="Сессия по отношениям",
                status_badge="Сегодня",
                tags=[
                    ("goal", "Свобода", "Хочет свободнее говорить о себе."),
                    ("pain", "Страх проявленности", "Сложно проявляться в важном разговоре."),
                ],
            ),
            DemoContactSpec(
                key="dmitriy-novikov",
                name="Дмитрий Новиков",
                email="demo.dmitriy@fibonatty.test",
                phone="+7 900 100-10-40",
                source=f"{DEMO_SOURCE_PREFIX}-tenant-3",
                category="Потенциальные",
                deal_stage="interest",
                deal_amount=Decimal("12000.00"),
                notes="Работает с темой баланса и перегрузки.",
                intention="Выйти из режима постоянного напряжения и вернуть ощущение, что жизнь управляется осознанно.",
                focus="Баланс жизни",
                competency_base={
                    "confidence": ("Уверенность", 24, 39),
                    "communication": ("Коммуникация", 40, 53),
                    "boundaries": ("Границы", 26, 41),
                    "focus": ("Цели и фокус", 28, 46),
                },
                goals=[
                    {
                        "title": "Собрать рабочую неделю без постоянного перегруза",
                        "progress": 34,
                        "competencyLinks": [
                            {"competencyId": "focus", "competencyName": "Цели и фокус", "weight": 0.45},
                            {"competencyId": "boundaries", "competencyName": "Границы", "weight": 0.35},
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.2},
                        ],
                        "steps": [
                            {"text": "Заполнить колесо жизни", "done": True, "doneAt": older_day},
                            {"text": "Отметить 3 главных источника перегруза", "done": True, "doneAt": mid_day},
                            {"text": "Сделать одно изменение в календаре", "done": False},
                        ],
                    },
                ],
                milestones=[],
                notes_items=[
                    ("Демо: стартовая картина", "Пока лучше всего работает через визуализацию недели и ограничение хаоса.", False),
                ],
                payment_status="pending",
                payment_method="invoice",
                payment_description="Запланирован переход из диагностики в регулярную работу",
                event_title="Сессия по балансу",
                status_badge="Новый",
                tags=[
                    ("pain", "Нет времени", "Высокая перегрузка и мало пространства на восстановление."),
                    ("experience", "Новичек", "Только входит в регулярную практику сопровождения."),
                ],
            ),
            DemoContactSpec(
                key="elena-orlova",
                name="Елена Орлова",
                email="demo.elena@fibonatty.test",
                phone="+7 900 100-10-50",
                source=f"{DEMO_SOURCE_PREFIX}-tenant-3",
                category="Стандарт",
                deal_stage="lost",
                deal_amount=Decimal("9000.00"),
                notes="Пример клиента, который отложил решение, но сохранил прогресс и историю диагностики.",
                intention="Понять, как вернуться к собственным целям после периода сильной усталости.",
                focus="Возврат к целям",
                competency_base={
                    "confidence": ("Уверенность", 35, 47),
                    "communication": ("Коммуникация", 37, 45),
                    "boundaries": ("Границы", 30, 38),
                    "focus": ("Цели и фокус", 22, 35),
                },
                goals=[
                    {
                        "title": "Вернуть себе ощущение движения и опоры",
                        "progress": 28,
                        "competencyLinks": [
                            {"competencyId": "focus", "competencyName": "Цели и фокус", "weight": 0.55},
                            {"competencyId": "confidence", "competencyName": "Уверенность", "weight": 0.45},
                        ],
                        "steps": [
                            {"text": "Сформулировать одну достижимую цель на месяц", "done": True, "doneAt": mid_day},
                            {"text": "Вернуться к ритму коротких шагов", "done": False},
                        ],
                    },
                ],
                milestones=[
                    {"goalIndex": 1, "text": "Сформулировала ясную цель без давления", "note": "Полезный ориентир для возможного возврата", "daysAgo": 12},
                ],
                notes_items=[
                    ("Демо: причина паузы", "Клиент временно заморозил работу из-за перегрузки, но сохранил теплый контакт.", True),
                ],
                payment_status="failed",
                payment_method="bank_card",
                payment_description="Не завершила оплату, но в системе сохранился контекст и точка возврата",
                event_title="Поддерживающая сессия",
                status_badge="Пауза",
                tags=[
                    ("goal", "Путешествия", "Хочет вернуть долгосрочную перспективу и вкус к планам."),
                    ("experience", "Купил базу", "Уже был первый вход в продукт и первичная диагностика."),
                ],
            ),
        ]
