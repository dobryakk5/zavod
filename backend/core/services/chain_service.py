from __future__ import annotations

from django.db import transaction

from core.models import Chain, ChainNode


DEFAULT_CHAIN_NAME = "Welcome"
WELCOME_CHAIN_KEY = "welcome"
POST_MEETING_CHAIN_KEY = "post_meeting"
RESCHEDULE_MEETING_CHAIN_KEY = "reschedule_meeting"
PAYMENT_PAID_CHAIN_KEY = "payment_paid"

CHAIN_DEFINITIONS = (
    {
        "key": WELCOME_CHAIN_KEY,
        "name": DEFAULT_CHAIN_NAME,
        "title": "Welcome серия",
        "description": "",
        "build_start_payload": lambda: build_start_payload(),
    },
    {
        "key": POST_MEETING_CHAIN_KEY,
        "name": "После встречи",
        "title": "После встречи",
        "description": "",
        "build_start_payload": lambda: build_empty_start_payload(),
    },
    {
        "key": RESCHEDULE_MEETING_CHAIN_KEY,
        "name": "Перенос встречи",
        "title": "Перенос встречи",
        "description": "",
        "build_start_payload": lambda: build_empty_start_payload(),
    },
    {
        "key": PAYMENT_PAID_CHAIN_KEY,
        "name": "После оплаты",
        "title": "После оплаты",
        "description": "",
        "build_start_payload": lambda: build_empty_start_payload(),
    },
)
CHAIN_DEFINITIONS_BY_KEY = {item["key"]: item for item in CHAIN_DEFINITIONS}


def build_start_payload() -> dict:
    return {
        "text": "Вы даете согласие на обработку персональных данных?",
        "buttons": [
            "Да",
            "Нет",
        ],
    }


def build_empty_start_payload() -> dict:
    return {
        "text": "",
        "buttons": [],
    }


def _ensure_start_node(chain: Chain, payload: dict) -> ChainNode:
    start_node = None
    if chain.start_node_id:
        start_node = ChainNode.objects.filter(chain=chain, id=chain.start_node_id).first()
    if not start_node:
        start_node = (
            ChainNode.objects
            .filter(chain=chain, node_type="start")
            .order_by("created_at", "id")
            .first()
        )
    if not start_node:
        start_node = ChainNode.objects.create(
            chain=chain,
            node_type="start",
            payload=payload,
            delay_seconds=0,
            pos_x=0,
            pos_y=0,
        )
    if chain.start_node_id != start_node.id:
        chain.start_node_id = start_node.id
        chain.save(update_fields=["start_node_id"])
    return start_node


def ensure_predefined_chains(client) -> dict[str, Chain]:
    chains_by_key: dict[str, Chain] = {}
    used_chain_ids: set[int] = set()

    with transaction.atomic():
        existing = list(Chain.objects.select_for_update().filter(tenant=client).order_by("created_at", "id"))
        existing_by_name = {chain.name: chain for chain in existing}
        reserved_names = {definition["name"] for definition in CHAIN_DEFINITIONS if definition["key"] != WELCOME_CHAIN_KEY}

        for definition in CHAIN_DEFINITIONS:
            chain = existing_by_name.get(definition["name"])
            if chain and chain.id in used_chain_ids:
                chain = None
            if not chain and definition["key"] == WELCOME_CHAIN_KEY and existing:
                # Миграционный fallback: исторически у tenant была одна цепочка.
                # Используем её как welcome, чтобы сохранить существующий граф.
                fallback = next(
                    (
                        item for item in existing
                        if item.id not in used_chain_ids and item.name not in reserved_names
                    ),
                    None,
                )
                if not fallback:
                    fallback = next((item for item in existing if item.id not in used_chain_ids), None)
                chain = fallback
            if not chain:
                chain = Chain.objects.create(
                    tenant=client,
                    name=definition["name"],
                    description=definition["description"],
                    status="draft",
                )
            _ensure_start_node(chain, definition["build_start_payload"]())
            used_chain_ids.add(chain.id)
            chains_by_key[definition["key"]] = chain

    return chains_by_key


def get_or_create_chain(client) -> Chain:
    chains = ensure_predefined_chains(client)
    return chains[WELCOME_CHAIN_KEY]


def get_or_create_chain_by_key(client, chain_key: str) -> Chain:
    chains = ensure_predefined_chains(client)
    normalized_key = str(chain_key or "").strip().lower()
    if normalized_key not in CHAIN_DEFINITIONS_BY_KEY:
        raise ValueError(f"Unknown chain key: {chain_key}")
    return chains[normalized_key]
