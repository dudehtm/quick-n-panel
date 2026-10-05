"""Dynamic enum choices shared by organization operators."""

from ..core import icons, scanner
from ..core.memberships import target_in_group
from ..preferences import display_name_for, get_preferences


_target_choice_cache = []
_category_target_choice_cache = []
_group_choice_cache = []


def target_choices(_operator, context):
    global _target_choice_cache

    _target_choice_cache = _target_items(context)
    return _target_choice_cache


def category_target_choices(operator, context):
    global _category_target_choice_cache

    _category_target_choice_cache = _target_items(
        context,
        excluded_group_id=getattr(operator, "group_id", "") or None,
    )
    return _category_target_choice_cache


def _target_items(context, *, excluded_group_id=None):
    preferences = get_preferences(context)
    if preferences is None:
        return []

    snapshot = scanner.refresh_catalog(context)
    available_keys = snapshot.by_key
    targets = [
        target
        for target in preferences.targets
        if (
            target.native_key in available_keys
            and (
                excluded_group_id is None
                or not target_in_group(target, excluded_group_id)
            )
        )
    ]
    targets.sort(key=lambda target: display_name_for(target).casefold())

    items = []
    for index, target in enumerate(targets):
        icon_name, icon_value = icons.resolve_icon(
            target.icon_name,
            target.icon_path,
            target.bundled_icon,
        )
        icon = icon_value if icon_value else icon_name
        items.append(
            (
                target.native_key,
                display_name_for(target),
                f"Native tab: {target.native_category}",
                icon,
                index,
            )
        )

    return items


def group_choices(_operator, context):
    global _group_choice_cache

    preferences = get_preferences(context)
    if preferences is None:
        return []

    items = [
        ("__NONE__", "Unassigned", "Do not place this tab in a category", "X", 0)
    ]
    for index, group in enumerate(preferences.groups, start=1):
        icon_name, icon_value = icons.resolve_icon(
            group.icon_name,
            group.icon_path,
            group.bundled_icon,
        )
        icon = icon_value if icon_value else icon_name
        items.append(
            (
                group.group_id,
                group.display_name,
                "Assign to this category",
                icon,
                index,
            )
        )

    _group_choice_cache = items
    return _group_choice_cache
