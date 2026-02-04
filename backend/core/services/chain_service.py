from __future__ import annotations

from django.db import transaction

from core.models import Chain, ChainNode


DEFAULT_CHAIN_NAME = "Welcome"


def build_welcome_text(client) -> str:
    brand = (client.brand_name or client.name or "").strip()
    niche = (client.niche or "").strip()
    product = (client.product_service or "").strip()

    lines = ["Добро пожаловать!"]
    if brand:
        lines.append(f"Бренд: {brand}")
    if niche:
        lines.append(f"Ниша: {niche}")
    if product:
        lines.append(f"Продукт/услуга: {product}")
    return "\n".join(lines)


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
            node_type="text",
            payload={"text": build_welcome_text(client)},
            delay_seconds=0,
            pos_x=0,
            pos_y=0,
        )
        chain.start_node_id = node.id
        chain.save(update_fields=["start_node_id"])
        return chain
