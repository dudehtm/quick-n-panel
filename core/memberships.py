"""Category membership helpers independent of the Blender API."""

import json


def group_memberships_for(target) -> dict[str, int]:
    """Return the categories containing a target and their local order."""
    raw = str(getattr(target, "group_memberships", "") or "")
    if raw:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            decoded = None
        if isinstance(decoded, dict):
            memberships = {}
            for group_id, order in decoded.items():
                group_id = str(group_id or "")
                if not group_id:
                    continue
                try:
                    order = max(0, int(order))
                except (TypeError, ValueError):
                    order = 0
                memberships[group_id] = order
            return memberships

    group_id = str(getattr(target, "group_id", "") or "")
    if not group_id:
        return {}
    try:
        order = max(0, int(getattr(target, "group_order", 0)))
    except (TypeError, ValueError):
        order = 0
    return {group_id: order}


def target_group_ids(target) -> tuple[str, ...]:
    return tuple(sorted(group_memberships_for(target)))


def target_in_group(target, group_id: str) -> bool:
    return str(group_id or "") in group_memberships_for(target)


def group_order_for(target, group_id: str) -> int:
    return group_memberships_for(target).get(str(group_id or ""), 0)


def set_group_memberships(target, memberships) -> None:
    normalized = {}
    for group_id, order in dict(memberships or {}).items():
        group_id = str(group_id or "")
        if not group_id:
            continue
        try:
            order = max(0, int(order))
        except (TypeError, ValueError):
            order = 0
        normalized[group_id] = order

    target.group_memberships = _serialize_memberships(normalized)

    primary_group_id = str(getattr(target, "group_id", "") or "")
    if primary_group_id not in normalized:
        primary_group_id = min(
            normalized,
            key=lambda group_id: (normalized[group_id], group_id),
            default="",
        )
    target.group_id = primary_group_id
    target.group_order = normalized.get(primary_group_id, 0)


def set_group_membership_order(target, group_id: str, order: int) -> bool:
    group_id = str(group_id or "")
    memberships = group_memberships_for(target)
    if group_id not in memberships:
        return False
    order = max(0, int(order))
    if memberships[group_id] == order:
        return False
    memberships[group_id] = order
    set_group_memberships(target, memberships)
    return True


def _serialize_memberships(memberships) -> str:
    normalized = {
        str(group_id): max(0, int(order))
        for group_id, order in dict(memberships or {}).items()
        if str(group_id or "")
    }
    if not normalized:
        return ""
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))
