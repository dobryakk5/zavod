from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from django.db.models import Q
from django.db import transaction

from core.models import Client, ClientProduct, MindEdge, MindMap, MindNode, MindNodePosition
from core.services.product_relations import merge_related_products, remove_related_product

logger = logging.getLogger(__name__)


def _normalize_type_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _product_ref(product: ClientProduct) -> Dict[str, Any]:
    product_type = getattr(product, "product_type", None)
    return {
        "id": product.id,
        "name": (product.name or "").strip(),
        "product_type_id": getattr(product_type, "id", None),
        "product_type_name": (getattr(product_type, "name", None) or "").strip() or None,
        "short_description": product.short_description,
    }


def _node_product_id(node: MindNode) -> Optional[int]:
    meta = node.meta if isinstance(node.meta, dict) else {}
    if meta.get("entity") != "product":
        return None
    value = meta.get("product_id")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _is_core(product: ClientProduct) -> bool:
    return _normalize_type_name(getattr(product.product_type, "name", None)) == "core"


def _extract_related_ids(structure: Any) -> list[int]:
    if not isinstance(structure, dict):
        return []
    raw = structure.get("related_products")
    if not isinstance(raw, list):
        return []

    ids: list[int] = []
    seen: set[int] = set()
    for item in raw:
        candidate: Any
        if isinstance(item, dict):
            candidate = item.get("id")
        else:
            candidate = item
        if isinstance(candidate, int):
            if candidate not in seen:
                ids.append(candidate)
                seen.add(candidate)
            continue
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                parsed = int(candidate)
                if parsed not in seen:
                    ids.append(parsed)
                    seen.add(parsed)
            except ValueError:
                continue
    return ids


def build_all_products_mind_map(client: Client) -> MindMap:
    """
    Create a mind map containing all client products laid out by product type.

    Layout rules:
    - Core products: center column
    - Tripwire/Lead/Reactivate: left column
    - Premium: right column (above)
    - Add-ons: right column (below)
    """

    products = list(ClientProduct.objects.select_related("product_type").filter(owner=client).order_by("id"))

    def is_type(product: ClientProduct, *expected: str) -> bool:
        name = _normalize_type_name(getattr(product.product_type, "name", None))
        expected_names = {_normalize_type_name(value) for value in expected}
        return name in expected_names

    core = sorted([p for p in products if is_type(p, "core")], key=lambda p: (p.name or "").strip().lower())
    tripwire = sorted([p for p in products if is_type(p, "tripwire")], key=lambda p: (p.name or "").strip().lower())
    lead = sorted([p for p in products if is_type(p, "lead")], key=lambda p: (p.name or "").strip().lower())
    reactivate = sorted(
        [p for p in products if is_type(p, "reactivate", "reactivation")],
        key=lambda p: (p.name or "").strip().lower(),
    )
    premium = sorted([p for p in products if is_type(p, "premium")], key=lambda p: (p.name or "").strip().lower())
    addons = sorted(
        [p for p in products if is_type(p, "add-ons", "addons")],
        key=lambda p: (p.name or "").strip().lower(),
    )

    categorized_ids = {p.id for p in core + tripwire + lead + reactivate + premium + addons}
    other = sorted([p for p in products if p.id not in categorized_ids], key=lambda p: (p.name or "").strip().lower())

    title = "Карта продуктов: все"
    description = f"Auto-generated products map ({len(products)} продуктов)"

    GAP_Y = 110.0
    GAP_X = 560.0
    CENTER_X = 0.0
    LEFT_X = -GAP_X
    RIGHT_X = GAP_X

    def _column_positions(items: list[ClientProduct], *, center_y: float) -> dict[int, float]:
        if not items:
            return {}
        start_y = center_y - ((len(items) - 1) / 2.0) * GAP_Y
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    def _positions_centered(items: list[ClientProduct], *, center_y: float = 0.0) -> dict[int, float]:
        if not items:
            return {}
        start_y = center_y - ((len(items) - 1) / 2.0) * GAP_Y
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    def _positions_above(items: list[ClientProduct]) -> dict[int, float]:
        if not items:
            return {}
        start_y = -GAP_Y * len(items)
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    def _positions_below(items: list[ClientProduct], *, start_y: float = GAP_Y) -> dict[int, float]:
        if not items:
            return {}
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    core_y = _column_positions(core, center_y=0.0)

    left_top = tripwire + lead
    left_main_y = _positions_centered(left_top, center_y=0.0)
    left_main_max = max(left_main_y.values(), default=0.0)

    reactivate_by_id = {p.id: p for p in reactivate}
    reactivate_positions: dict[int, float] = {}
    for core_product in core:
        related_ids = [rid for rid in _extract_related_ids(core_product.structure) if rid in reactivate_by_id]
        if not related_ids:
            continue
        core_y_pos = core_y.get(core_product.id, 0.0)
        related_products = sorted(
            [reactivate_by_id[rid] for rid in related_ids if rid in reactivate_by_id],
            key=lambda p: (p.name or "").strip().lower(),
        )
        for idx, product in enumerate(related_products, start=1):
            if product.id in reactivate_positions:
                continue
            reactivate_positions[product.id] = core_y_pos + GAP_Y * idx

    unlinked_reactivate = [p for p in reactivate if p.id not in reactivate_positions]
    left_unlinked_start = max(GAP_Y, left_main_max + GAP_Y) if unlinked_reactivate else 0.0
    left_unlinked_y = _positions_below(unlinked_reactivate, start_y=left_unlinked_start)
    left_items = left_top + unlinked_reactivate
    left_y = {
        **left_main_y,
        **left_unlinked_y,
    }

    premium_y = _positions_above(premium)
    addons_y = _positions_below(addons + other)

    with transaction.atomic():
        mind_map = MindMap.objects.create(
            owner=client,
            title=title,
            description=description,
            type="product",
            is_public=False,
        )

        node_by_product_id: dict[int, MindNode] = {}

        def _create_node(product: ClientProduct, x: float, y: float) -> None:
            pt = getattr(product, "product_type", None)
            pt_name = (getattr(pt, "name", None) or "").strip()
            meta: Dict[str, Any] = {
                "entity": "product",
                "product_id": product.id,
                "product_type_id": getattr(pt, "id", None),
                "product_type_name": pt_name or None,
                "metric_type": pt_name or "Product",
            }

            node = MindNode.objects.create(map_id=mind_map.id, text=(product.name or "").strip(), meta=meta)
            node_by_product_id[product.id] = node
            MindNodePosition.objects.create(node=node, layout_name="default", x=x, y=y)

        for product in core:
            _create_node(product, CENTER_X, core_y.get(product.id, 0.0))
        reactivate_ids = {p.id for p in reactivate}
        for product in left_items:
            _create_node(product, LEFT_X, left_y.get(product.id, 0.0))
        for product in reactivate:
            if product.id not in reactivate_positions:
                continue
            _create_node(product, CENTER_X, reactivate_positions.get(product.id, 0.0))
        for product in premium:
            _create_node(product, RIGHT_X, premium_y.get(product.id, 0.0))
        for product in addons + other:
            _create_node(product, RIGHT_X, addons_y.get(product.id, 0.0))

        left_ids = {p.id for p in left_items}

        # Materialize existing Core->related links as edges (best-effort).
        edges: list[MindEdge] = []
        seen_edges: set[tuple[str, str]] = set()
        for core_product in core:
            core_node = node_by_product_id.get(core_product.id)
            if not core_node:
                continue
            related_ids = _extract_related_ids(core_product.structure)
            for related_id in related_ids:
                related_node = node_by_product_id.get(related_id)
                if not related_node or related_node.id == core_node.id:
                    continue
                if related_id in reactivate_ids:
                    source_node = related_node
                    target_node = core_node
                    meta = {"arrow": "forward", "source_side": "top", "target_side": "bottom"}
                elif related_id in left_ids:
                    source_node = related_node
                    target_node = core_node
                    meta = {"arrow": "forward", "source_side": "right", "target_side": "left"}
                else:
                    source_node = core_node
                    target_node = related_node
                    meta = {"arrow": "forward", "source_side": "right", "target_side": "left"}
                edge_key = (str(source_node.id), str(target_node.id))
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append(
                    MindEdge(
                        map_id=mind_map.id,
                        from_node_id=source_node.id,
                        to_node_id=target_node.id,
                        type="default",
                        label=None,
                        meta=meta,
                    )
                )
        if edges:
            MindEdge.objects.bulk_create(edges)

        return mind_map


def build_related_products_mind_map(client: Client, core_product: ClientProduct) -> MindMap:
    if not _is_core(core_product):
        raise ValueError("Related map can be created only for Core product")

    related_ids = _extract_related_ids(core_product.structure)
    related_by_id = {
        p.id: p
        for p in ClientProduct.objects.select_related("product_type").filter(owner=client, id__in=related_ids)
    }
    related_products = [related_by_id[pid] for pid in related_ids if pid in related_by_id and pid != core_product.id]

    def is_type(product: ClientProduct, *expected: str) -> bool:
        name = _normalize_type_name(getattr(product.product_type, "name", None))
        expected_names = {_normalize_type_name(value) for value in expected}
        return name in expected_names

    tripwire = sorted([p for p in related_products if is_type(p, "tripwire")], key=lambda p: (p.name or "").strip().lower())
    lead = sorted([p for p in related_products if is_type(p, "lead")], key=lambda p: (p.name or "").strip().lower())
    reactivate = sorted(
        [p for p in related_products if is_type(p, "reactivate", "reactivation")],
        key=lambda p: (p.name or "").strip().lower(),
    )
    premium = sorted([p for p in related_products if is_type(p, "premium")], key=lambda p: (p.name or "").strip().lower())
    addons = sorted(
        [p for p in related_products if is_type(p, "add-ons", "addons")],
        key=lambda p: (p.name or "").strip().lower(),
    )

    categorized_ids = {p.id for p in tripwire + lead + reactivate + premium + addons}
    other = sorted([p for p in related_products if p.id not in categorized_ids], key=lambda p: (p.name or "").strip().lower())

    title = f"Core: {(core_product.name or '').strip() or core_product.id} — сопутствующие"
    description = f"Auto-generated related products map for Core #{core_product.id}"

    GAP_Y = 110.0
    GAP_X = 560.0
    CENTER_X = 0.0
    LEFT_X = -GAP_X
    RIGHT_X = GAP_X

    def _positions_centered(items: list[ClientProduct], *, center_y: float = 0.0) -> dict[int, float]:
        if not items:
            return {}
        start_y = center_y - ((len(items) - 1) / 2.0) * GAP_Y
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    def _positions_above(items: list[ClientProduct]) -> dict[int, float]:
        if not items:
            return {}
        start_y = -GAP_Y * len(items)
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    def _positions_below(items: list[ClientProduct], *, start_y: float = GAP_Y) -> dict[int, float]:
        if not items:
            return {}
        return {item.id: (start_y + idx * GAP_Y) for idx, item in enumerate(items)}

    left_top = tripwire + lead
    left_main_y = _positions_centered(left_top, center_y=0.0)

    reactivate_by_id = {p.id: p for p in reactivate}
    reactivate_positions = {
        p.id: GAP_Y * idx for idx, p in enumerate(reactivate, start=1)
    }

    left_items = left_top
    left_y = left_main_y
    premium_y = _positions_above(premium)
    addons_y = _positions_below(addons + other)

    with transaction.atomic():
        mind_map = MindMap.objects.create(
            owner=client,
            title=title,
            description=description,
            type="product",
            is_public=False,
        )

        def _create_node(product: ClientProduct, x: float, y: float) -> MindNode:
            pt = getattr(product, "product_type", None)
            pt_name = (getattr(pt, "name", None) or "").strip()
            meta: Dict[str, Any] = {
                "entity": "product",
                "product_id": product.id,
                "product_type_id": getattr(pt, "id", None),
                "product_type_name": pt_name or None,
                "metric_type": pt_name or "Product",
            }
            node = MindNode.objects.create(map_id=mind_map.id, text=(product.name or "").strip(), meta=meta)
            MindNodePosition.objects.create(node=node, layout_name="default", x=x, y=y)
            return node

        core_node = _create_node(core_product, CENTER_X, 0.0)

        edges: list[MindEdge] = []
        reactivate_ids = {p.id for p in reactivate}
        for product in left_items:
            related_node = _create_node(product, LEFT_X, left_y.get(product.id, 0.0))
            edges.append(
                MindEdge(
                    map_id=mind_map.id,
                    from_node_id=related_node.id,
                    to_node_id=core_node.id,
                    type="default",
                    label=None,
                    meta={"arrow": "forward", "source_side": "right", "target_side": "left"},
                )
            )
        for product in reactivate:
            related_node = _create_node(product, CENTER_X, reactivate_positions.get(product.id, 0.0))
            edges.append(
                MindEdge(
                    map_id=mind_map.id,
                    from_node_id=related_node.id,
                    to_node_id=core_node.id,
                    type="default",
                    label=None,
                    meta={"arrow": "forward", "source_side": "top", "target_side": "bottom"},
                )
            )
        for product in premium:
            related_node = _create_node(product, RIGHT_X, premium_y.get(product.id, 0.0))
            edges.append(
                MindEdge(
                    map_id=mind_map.id,
                    from_node_id=core_node.id,
                    to_node_id=related_node.id,
                    type="default",
                    label=None,
                    meta={"arrow": "forward", "source_side": "right", "target_side": "left"},
                )
            )
        for product in addons + other:
            related_node = _create_node(product, RIGHT_X, addons_y.get(product.id, 0.0))
            edges.append(
                MindEdge(
                    map_id=mind_map.id,
                    from_node_id=core_node.id,
                    to_node_id=related_node.id,
                    type="default",
                    label=None,
                    meta={"arrow": "forward", "source_side": "right", "target_side": "left"},
                )
            )

        if edges:
            MindEdge.objects.bulk_create(edges)

        return mind_map


def sync_core_related_for_edge_create(client: Client, mind_map: MindMap, from_node_id: str, to_node_id: str) -> None:
    if (mind_map.type or "").strip().lower() != "product":
        return

    nodes = list(MindNode.objects.filter(map=mind_map, id__in=[from_node_id, to_node_id]))
    if len(nodes) != 2:
        return

    by_id = {str(n.id): n for n in nodes}
    from_node = by_id.get(str(from_node_id))
    to_node = by_id.get(str(to_node_id))
    if not from_node or not to_node:
        return

    a_id = _node_product_id(from_node)
    b_id = _node_product_id(to_node)
    if not a_id or not b_id:
        return

    products = {
        p.id: p
        for p in ClientProduct.objects.select_related("product_type").filter(owner=client, id__in=[a_id, b_id])
    }
    if len(products) != 2:
        return

    a = products.get(a_id)
    b = products.get(b_id)
    if not a or not b:
        return

    if _is_core(a) and not _is_core(b):
        core_product, related_product = a, b
    elif _is_core(b) and not _is_core(a):
        core_product, related_product = b, a
    else:
        return

    structure = core_product.structure if isinstance(core_product.structure, dict) else {}
    existing = structure.get("related_products")
    structure["related_products"] = merge_related_products(existing, _product_ref(related_product))
    core_product.structure = structure
    core_product.save(update_fields=["structure"])


def sync_core_related_for_edge_delete(client: Client, mind_map: MindMap, from_node_id: str, to_node_id: str) -> None:
    if (mind_map.type or "").strip().lower() != "product":
        return

    # If there is still at least one remaining edge between these nodes, keep the relation.
    if MindEdge.objects.filter(map=mind_map).filter(
        Q(from_node_id=from_node_id, to_node_id=to_node_id) | Q(from_node_id=to_node_id, to_node_id=from_node_id)
    ).exists():
        return

    nodes = list(MindNode.objects.filter(map=mind_map, id__in=[from_node_id, to_node_id]))
    if len(nodes) != 2:
        return

    a_id = _node_product_id(nodes[0])
    b_id = _node_product_id(nodes[1])
    if not a_id or not b_id:
        return

    products = {
        p.id: p
        for p in ClientProduct.objects.select_related("product_type").filter(owner=client, id__in=[a_id, b_id])
    }
    if len(products) != 2:
        return

    a = products.get(a_id)
    b = products.get(b_id)
    if not a or not b:
        return

    if _is_core(a) and not _is_core(b):
        core_product, related_product = a, b
    elif _is_core(b) and not _is_core(a):
        core_product, related_product = b, a
    else:
        return

    structure = core_product.structure if isinstance(core_product.structure, dict) else {}
    existing = structure.get("related_products")
    structure["related_products"] = remove_related_product(existing, related_product.id)
    core_product.structure = structure
    core_product.save(update_fields=["structure"])


def sync_core_related_for_node_delete(client: Client, mind_map: MindMap, node: MindNode, edges: list[MindEdge]) -> None:
    if (mind_map.type or "").strip().lower() != "product":
        return

    node_product_id = _node_product_id(node)
    if not node_product_id:
        return

    node_id = str(node.id)
    other_node_ids: list[str] = []
    for edge in edges:
        from_id = str(edge.from_node_id)
        to_id = str(edge.to_node_id)
        if from_id == node_id and to_id != node_id:
            other_node_ids.append(to_id)
        elif to_id == node_id and from_id != node_id:
            other_node_ids.append(from_id)

    if not other_node_ids:
        return

    other_nodes = list(MindNode.objects.filter(map=mind_map, id__in=other_node_ids))
    other_product_ids = [pid for pid in (_node_product_id(n) for n in other_nodes) if pid]
    if not other_product_ids:
        return

    product_ids = {node_product_id, *other_product_ids}
    products = {
        p.id: p
        for p in ClientProduct.objects.select_related("product_type").filter(owner=client, id__in=product_ids)
    }
    node_product = products.get(node_product_id)
    if not node_product:
        return

    remove_map: Dict[int, set[int]] = {}
    for other_node in other_nodes:
        other_product_id = _node_product_id(other_node)
        if not other_product_id:
            continue
        other_product = products.get(other_product_id)
        if not other_product:
            continue

        if _is_core(node_product) and not _is_core(other_product):
            core_product, related_product = node_product, other_product
        elif _is_core(other_product) and not _is_core(node_product):
            core_product, related_product = other_product, node_product
        else:
            continue

        remove_map.setdefault(core_product.id, set()).add(related_product.id)

    for core_id, related_ids in remove_map.items():
        core_product = products.get(core_id)
        if not core_product:
            continue
        structure = core_product.structure if isinstance(core_product.structure, dict) else {}
        existing = structure.get("related_products")
        updated = existing
        changed = False
        for related_id in related_ids:
            next_list = remove_related_product(updated, related_id)
            if next_list != updated:
                updated = next_list
                changed = True
        if changed:
            structure["related_products"] = updated
            core_product.structure = structure
            core_product.save(update_fields=["structure"])
