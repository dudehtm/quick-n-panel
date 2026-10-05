"""Reconcile persistent tab settings with the current runtime catalog."""

from dataclasses import dataclass

from .catalog import (
    TargetDescriptor,
    join_metadata,
    module_owner_key,
    split_metadata,
)
from .memberships import group_memberships_for, set_group_memberships


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    changed: bool = False
    warnings: tuple[str, ...] = ()


def reconcile_catalog_targets(
    descriptors: tuple[TargetDescriptor, ...],
    preferences,
) -> ReconciliationResult:
    """Preserve settings when registered panels move to another category."""

    records = list(preferences.targets)
    descriptors_by_key = {descriptor.native_key: descriptor for descriptor in descriptors}
    assigned_indices = {descriptor.native_key: [] for descriptor in descriptors}
    warnings = []

    selected_key = ""
    if records:
        selected_index = min(int(preferences.target_index), len(records) - 1)
        selected_key = _record_key(records[selected_index])

    for index, record in enumerate(records):
        key = _record_key(record)
        if key in descriptors_by_key:
            assigned_indices[key].append(index)
            continue

        matches = _best_descriptor_matches(record, descriptors)
        if len(matches) == 1:
            assigned_indices[matches[0].native_key].append(index)
        elif len(matches) > 1:
            categories = ", ".join(
                sorted(descriptor.native_category for descriptor in matches)
            )
            label = str(getattr(record, "native_category", "") or key)
            warnings.append(
                f"Possible duplicate '{label}' was not merged; matches: {categories}"
            )

    favorite_keys = {
        str(getattr(item, "target_key", "") or "")
        for item in preferences.favorites
    }
    aliases = {}
    remove_indices = set()
    missing_descriptors = []
    changed = False

    for descriptor in descriptors:
        indices = assigned_indices[descriptor.native_key]
        direct_indices = [
            index
            for index in indices
            if _record_key(records[index]) == descriptor.native_key
        ]

        if direct_indices:
            primary_index = direct_indices[0]
        elif indices:
            primary_index = max(
                indices,
                key=lambda index: _preservation_score(
                    records[index],
                    index,
                    favorite_keys,
                ),
            )
        else:
            missing_descriptors.append(descriptor)
            continue

        primary = records[primary_index]
        for index in indices:
            if index == primary_index:
                continue
            secondary = records[index]
            changed |= _merge_target_settings(primary, secondary)
            old_key = _record_key(secondary)
            if old_key and old_key != descriptor.native_key:
                aliases[old_key] = descriptor.native_key
            remove_indices.add(index)

        old_key = _record_key(primary)
        if old_key and old_key != descriptor.native_key:
            aliases[old_key] = descriptor.native_key
        changed |= _update_descriptor_metadata(primary, descriptor)

    if aliases or remove_indices:
        changed |= _remap_target_references(preferences, aliases)

    for index in sorted(remove_indices, reverse=True):
        preferences.targets.remove(index)
        changed = True

    # CollectionProperty.add/remove can invalidate every existing RNA wrapper.
    # Add missing records only after all work using the original wrappers is done.
    for descriptor in missing_descriptors:
        target = preferences.targets.add()
        changed |= _update_descriptor_metadata(target, descriptor)

    if preferences.targets:
        desired_key = _resolve_alias(selected_key, aliases)
        target_index = next(
            (
                index
                for index, target in enumerate(preferences.targets)
                if _record_key(target) == desired_key
            ),
            min(int(preferences.target_index), len(preferences.targets) - 1),
        )
    else:
        target_index = 0
    changed |= _assign(preferences, "target_index", target_index)

    return ReconciliationResult(
        changed=changed,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def target_match_rank(record, descriptor: TargetDescriptor) -> int:
    """Return a conservative confidence rank for a persisted/current pair."""

    origin_key = str(getattr(record, "origin_key", "") or "")
    if origin_key and origin_key == descriptor.origin_key:
        return 3

    stored_identifiers = set(
        split_metadata(str(getattr(record, "panel_identifiers", "") or ""))
    )
    if stored_identifiers.intersection(descriptor.panel_identifiers):
        stored_owners = {
            module_owner_key(module)
            for module in split_metadata(
                str(getattr(record, "source_modules", "") or "")
            )
        }
        stored_owners.discard("")
        current_owners = set(descriptor.source_owners)
        if (
            not stored_owners
            or not current_owners
            or stored_owners.intersection(current_owners)
        ):
            return 2

    stored_modules = _normalized_metadata(
        getattr(record, "source_modules", ""),
        casefold=False,
    )
    stored_labels = _normalized_metadata(
        getattr(record, "panel_labels", ""),
        casefold=True,
    )
    current_modules = frozenset(descriptor.source_modules)
    current_labels = frozenset(
        label.strip().casefold() for label in descriptor.panel_labels if label.strip()
    )
    if (
        stored_modules
        and stored_labels
        and stored_modules == current_modules
        and stored_labels == current_labels
    ):
        return 1
    return 0


def _best_descriptor_matches(record, descriptors):
    ranked = [
        (target_match_rank(record, descriptor), descriptor)
        for descriptor in descriptors
    ]
    best_rank = max((rank for rank, _descriptor in ranked), default=0)
    if best_rank == 0:
        return ()
    return tuple(
        descriptor for rank, descriptor in ranked if rank == best_rank
    )


def _update_descriptor_metadata(target, descriptor: TargetDescriptor) -> bool:
    values = {
        "name": descriptor.native_key,
        "native_key": descriptor.native_key,
        "native_category": descriptor.native_category,
        "origin_key": descriptor.origin_key,
        "panel_identifiers": join_metadata(descriptor.panel_identifiers),
        "panel_labels": join_metadata(descriptor.panel_labels),
        "source_modules": join_metadata(descriptor.source_modules),
    }
    changed = False
    for field, value in values.items():
        changed |= _assign(target, field, value)
    return changed


def _merge_target_settings(primary, secondary) -> bool:
    changed = False

    if not str(getattr(primary, "display_name", "") or "").strip():
        changed |= _assign(
            primary,
            "display_name",
            str(getattr(secondary, "display_name", "") or ""),
        )

    primary_memberships = group_memberships_for(primary)
    secondary_memberships = group_memberships_for(secondary)
    merged_memberships = dict(primary_memberships)
    for group_id, order in secondary_memberships.items():
        merged_memberships.setdefault(group_id, order)
    before_memberships = (
        getattr(primary, "group_memberships", None),
        getattr(primary, "group_id", ""),
        getattr(primary, "group_order", 0),
    )
    set_group_memberships(primary, merged_memberships)
    changed |= before_memberships != (
        getattr(primary, "group_memberships", None),
        getattr(primary, "group_id", ""),
        getattr(primary, "group_order", 0),
    )

    if bool(getattr(secondary, "hidden", False)):
        changed |= _assign(primary, "hidden", True)

    if not _has_custom_icon(primary) and _has_custom_icon(secondary):
        bundled_icon = str(getattr(secondary, "bundled_icon", "NONE") or "NONE")
        changed |= _assign(
            primary,
            "icon_name",
            str(getattr(secondary, "icon_name", "PLUGIN") or "PLUGIN"),
        )
        changed |= _assign(primary, "bundled_icon", bundled_icon)
        changed |= _assign(
            primary,
            "icon_path",
            str(getattr(secondary, "icon_path", "") or "")
            if bundled_icon in {"", "NONE"}
            else "",
        )

    open_count = _safe_int(getattr(primary, "open_count", 0)) + _safe_int(
        getattr(secondary, "open_count", 0)
    )
    changed |= _assign(primary, "open_count", open_count)
    changed |= _assign(
        primary,
        "first_opened_at",
        _timestamp_choice(
            getattr(primary, "first_opened_at", ""),
            getattr(secondary, "first_opened_at", ""),
            earliest=True,
        ),
    )
    changed |= _assign(
        primary,
        "last_opened_at",
        _timestamp_choice(
            getattr(primary, "last_opened_at", ""),
            getattr(secondary, "last_opened_at", ""),
            earliest=False,
        ),
    )
    return changed


def _remap_target_references(preferences, aliases) -> bool:
    changed = False
    duplicate_favorites = []
    seen_favorites = set()

    for index, favorite in enumerate(preferences.favorites):
        old_key = str(getattr(favorite, "target_key", "") or "")
        target_key = _resolve_alias(old_key, aliases)
        if target_key and target_key in seen_favorites:
            duplicate_favorites.append(index)
            continue
        if target_key:
            seen_favorites.add(target_key)
        changed |= _assign(favorite, "target_key", target_key)
        changed |= _assign(favorite, "name", target_key)

    for index in reversed(duplicate_favorites):
        preferences.favorites.remove(index)
        changed = True

    favorite_index = min(
        int(preferences.favorite_index),
        max(0, len(preferences.favorites) - 1),
    )
    changed |= _assign(preferences, "favorite_index", favorite_index)

    for field in (
        "favorite_1",
        "favorite_2",
        "favorite_3",
        "last_target_key",
        "last_observed_target_key",
    ):
        old_key = str(getattr(preferences, field, "") or "")
        changed |= _assign(preferences, field, _resolve_alias(old_key, aliases))
    return changed


def _preservation_score(record, index: int, favorite_keys: set[str]):
    key = _record_key(record)
    customization = sum(
        (
            bool(str(getattr(record, "display_name", "") or "").strip()),
            bool(group_memberships_for(record)),
            bool(getattr(record, "hidden", False)),
            _has_custom_icon(record),
        )
    )
    return (
        key in favorite_keys,
        customization,
        _safe_int(getattr(record, "open_count", 0)),
        -index,
    )


def _record_key(record) -> str:
    return str(
        getattr(record, "native_key", "")
        or getattr(record, "name", "")
        or ""
    )


def _normalized_metadata(value, *, casefold: bool) -> frozenset[str]:
    values = []
    for part in split_metadata(str(value or "")):
        part = part.strip()
        if part:
            values.append(part.casefold() if casefold else part)
    return frozenset(values)


def _resolve_alias(target_key: str, aliases) -> str:
    resolved = str(target_key or "")
    seen = set()
    while resolved in aliases and resolved not in seen:
        seen.add(resolved)
        resolved = aliases[resolved]
    return resolved


def _has_custom_icon(target) -> bool:
    return bool(
        str(getattr(target, "icon_name", "PLUGIN") or "PLUGIN") != "PLUGIN"
        or str(getattr(target, "bundled_icon", "NONE") or "NONE") not in {"", "NONE"}
        or str(getattr(target, "icon_path", "") or "")
    )


def _timestamp_choice(left, right, *, earliest: bool) -> str:
    left = str(left or "")
    right = str(right or "")
    if not left:
        return right
    if not right:
        return left
    try:
        values = ((float(left), left), (float(right), right))
        return (min if earliest else max)(values)[1]
    except (TypeError, ValueError):
        return (min if earliest else max)(left, right)


def _safe_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _assign(owner, field: str, value) -> bool:
    if getattr(owner, field) == value:
        return False
    setattr(owner, field, value)
    return True
