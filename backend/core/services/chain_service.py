from __future__ import annotations

from django.db import transaction

from core.models import Chain, ChainNode


DEFAULT_CHAIN_NAME = "Welcome"


def build_start_payload() -> dict:
    return {
        "text": "Вы даете согласие на обработку персональных данных?",
        "buttons": [
            {"text": "Да", "color": "green"},
            {"text": "Нет", "color": "red"},
        ],
    }


def get_or_create_chain(client) -> Chain:
    chain = Chain.objects.filter(tenant=client).first()
    if chain:
        return chain

    with transaction.atomic():
        chain = Chain.objects.select_for_update().filter(tenant=client).first()
        if chain:
            return chain

        chain = Chain.objects.create(
            tenant=client,
            name=DEFAULT_CHAIN_NAME,
            description="",
            status="draft",
        )
        node = ChainNode.objects.create(
            chain=chain,
            node_type="start",
            payload=build_start_payload(),
            delay_seconds=0,
            pos_x=0,
            pos_y=0,
        )
        chain.start_node_id = node.id
        chain.save(update_fields=["start_node_id"])
        return chain
