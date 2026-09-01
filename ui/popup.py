"""Theme-native compact and expanded launcher layouts."""

from ..constants import MAX_FAVORITES
from ..core import icons, scanner
from ..preferences import display_name_for, favorite_keys, get_preferences


_CATEGORY_TARGET_LIMIT = 5
_ALL_TABS_COLLAPSE_CATEGORY_COUNT = 5


def draw_launcher_popup(layout, context):
    preferences = get_preferences(context)
    if preferences is None:
        layout.label(text="Preferences unavailable", icon="ERROR")
        return

    scanner.refresh_catalog(context)
    layout.separator(factor=0.2)
    content = layout.row(align=False)
    _draw_search(content, context, preferences)
    _draw_favorites(content, context, preferences)
    layout.separator(factor=0.2)
    if _draw_direct_categories(layout, context):
        layout.separator(factor=0.2)

    bottom = layout.row(align=True)
    bottom.scale_y = 1.2
    bottom.popover(
        panel="QNP_PT_launcher_categories_popover",
        text="Library",
        icon="TRIA_DOWN",
    )
    bottom.operator(
        "quick_n_panel.open_configuration",
        text="",
        icon="PREFERENCES",
    )


def _draw_direct_categories(layout, context) -> bool:
    categories = scanner.available_direct_categories(context)
    if not categories:
        return False

    row = layout.row(align=True)
    row.scale_y = 1.1
    for category in categories:
        operator = row.operator(
            "quick_n_panel.open_direct_category",
            text=category,
        )
        operator.category = category
    return True


def draw_categories_popover(layout, context):
    preferences = get_preferences(context)
    if preferences is None:
        layout.label(text="Preferences unavailable", icon="ERROR")
        return

    scanner.refresh_catalog(context)
    _draw_categories_grid(layout, context, preferences)


def reset_all_tabs_expansion(context, preferences, available_keys):
    _available_targets, grouped = _library_contents(preferences, available_keys)
    populated_count = sum(bool(targets) for _group, targets in grouped)
    context.window_manager.qnp_all_tabs_expanded = (
        populated_count < _ALL_TABS_COLLAPSE_CATEGORY_COUNT
    )


def _draw_categories_grid(layout, context, preferences):
    available_keys = scanner.get_snapshot().by_key
    available_targets, grouped = _library_contents(preferences, available_keys)

    populated = [entry for entry in grouped if entry[1]]
    empty = [entry[0] for entry in grouped if not entry[1]]

    if populated:
        layout.label(text="Categories", icon="COLLECTION_NEW")
        grid = layout.grid_flow(
            row_major=True,
            columns=2,
            even_columns=True,
            even_rows=True,
            align=True,
        )
        for group, targets in populated:
            _draw_group(
                grid,
                context,
                preferences,
                group,
                targets,
                can_add=len(targets) < len(available_targets),
            )

    if empty:
        layout.label(text="Empty Categories", icon="OUTLINER_COLLECTION")
        empty_grid = layout.grid_flow(
            row_major=True,
            columns=3,
            even_columns=True,
            align=True,
        )
        for group in empty:
            _draw_empty_group(
                empty_grid,
                group,
                can_add=bool(available_targets),
            )

    layout.separator(factor=0.5)
    expanded = context.window_manager.qnp_all_tabs_expanded
    header = layout.row(align=True)
    header.scale_y = 1.1
    # UILayout.panel crashes inside this nested popover in Blender 5.2.
    header.prop(
        context.window_manager,
        "qnp_all_tabs_expanded",
        text=f"All Tabs ({len(available_targets)})",
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
        toggle=True,
    )
    if not expanded:
        return

    if not available_targets:
        layout.label(text="No tabs available", icon="INFO")
        return

    library = layout.grid_flow(
        row_major=True,
        columns=2,
        even_columns=True,
        align=True,
    )
    for target in available_targets:
        _draw_target_button(
            library,
            context,
            preferences,
            target.native_key,
            compact=True,
        )


def _library_contents(preferences, available_keys):
    available_targets = [
        target for target in preferences.targets if target.native_key in available_keys
    ]
    available_targets.sort(key=lambda target: display_name_for(target).casefold())

    grouped = []
    for group in preferences.groups:
        targets = [
            target for target in available_targets if target.group_id == group.group_id
        ]
        targets.sort(
            key=lambda target: (target.group_order, display_name_for(target).casefold())
        )
        grouped.append((group, targets))
    grouped.sort(key=lambda entry: (-len(entry[1]), entry[0].display_name.casefold()))
    return available_targets, grouped


def _draw_search(parent, context, preferences):
    box = parent.box()
    box.ui_units_x = 8.0
    column = box.column(align=True)

    accent = icons.search_accent_icon_value()
    if accent:
        bar = column.row(align=True)
        bar.alignment = "CENTER"
        bar.scale_y = 0.35
        bar.label(text="", icon_value=accent)
        column.separator(factor=0.15)

    action = column.column(align=True)
    action.scale_y = 2.2
    action.operator(
        "quick_n_panel.search_targets",
        text="Search",
        icon="VIEWZOOM",
    )

    column.separator(factor=1.0)
    column.label(text="Recent", icon="RECOVER_LAST")
    recent_targets = [
        target for target in preferences.targets if target.last_opened_at
    ]
    recent_targets.sort(key=_last_opened_timestamp, reverse=True)
    if not recent_targets:
        empty = column.row()
        empty.enabled = False
        empty.label(text="No recent tab")
        return

    for recent in recent_targets[:3]:
        _draw_target_button(column, context, preferences, recent.native_key)


def _draw_favorites(parent, context, preferences):
    box = parent.box()
    column = box.column(align=True)
    favorites_icon = icons.bundled_icon_value("QNP_Favorites")
    header = column.row(align=True)
    header.scale_y = 1.2
    if favorites_icon:
        header.label(text="Favorites", icon_value=favorites_icon)
    else:
        header.label(text="Favorites", icon="SOLO_ON")
    add_row = header.row(align=True)
    add_row.alignment = "RIGHT"
    add_row.enabled = len(preferences.favorites) < MAX_FAVORITES
    add = add_row.operator(
        "quick_n_panel.assign_favorite",
        text="",
        icon="ADD",
    )
    add.index = -1
    column.separator(factor=0.6)

    keys = favorite_keys(preferences)
    if not keys:
        empty = column.row(align=True)
        empty.enabled = False
        empty.label(text="No favorites configured", icon="INFO")
    else:
        for target_key in keys:
            _draw_target_button(column, context, preferences, target_key)


def _draw_group(parent, context, preferences, group, targets, *, can_add):
    box = parent.box()
    column = box.column(align=True)
    icon_name, icon_value = icons.resolve_icon(
        group.icon_name,
        group.icon_path,
        group.bundled_icon,
    )
    header = column.row(align=True)
    header.scale_y = 1.2
    label = f"{group.display_name} ({len(targets)})"
    if icon_value:
        header.label(text=label, icon_value=icon_value)
    else:
        header.label(text=label, icon=icon_name)
    _draw_add_target_to_group(header, group.group_id, enabled=can_add)
    column.separator(factor=0.6)

    for target in targets[:_CATEGORY_TARGET_LIMIT]:
        _draw_target_button(
            column,
            context,
            preferences,
            target.native_key,
            compact=True,
        )

    remaining = len(targets) - _CATEGORY_TARGET_LIMIT
    if remaining > 0:
        more = column.row()
        more.alignment = "CENTER"
        more.enabled = False
        more.label(text=f"+{remaining} more")


def _draw_empty_group(parent, group, *, can_add):
    row = parent.row(align=True)
    icon_name, icon_value = icons.resolve_icon(
        group.icon_name,
        group.icon_path,
        group.bundled_icon,
    )
    if icon_value:
        row.label(text=group.display_name, icon_value=icon_value)
    else:
        row.label(text=group.display_name, icon=icon_name)
    _draw_add_target_to_group(row, group.group_id, enabled=can_add)


def _draw_add_target_to_group(parent, group_id: str, *, enabled: bool):
    add_row = parent.row(align=True)
    add_row.alignment = "RIGHT"
    add_row.enabled = enabled
    add = add_row.operator(
        "quick_n_panel.add_target_to_group",
        text="",
        icon="ADD",
    )
    add.group_id = group_id


def _draw_target_button(
    parent,
    context,
    preferences,
    target_key: str,
    *,
    compact=False,
):
    target = preferences.targets.get(target_key)
    if target is None:
        row = parent.row()
        row.enabled = False
        row.label(text="Missing target", icon="ERROR")
        return

    exists = scanner.target_exists(target_key)
    available = exists and scanner.target_is_context_available(target_key, context)
    row = parent.row(align=True)
    row.scale_y = 1.0 if compact else 1.35
    row.enabled = available

    text = display_name_for(target)
    icon_name, icon_value = icons.resolve_icon(
        target.icon_name,
        target.icon_path,
        target.bundled_icon,
    )
    if preferences.display_mode == "NAME":
        icon_name, icon_value = "NONE", 0
    if not exists:
        icon_name, icon_value = "ERROR", 0

    kwargs = {"text": text}
    if icon_value:
        kwargs["icon_value"] = icon_value
    elif icon_name != "NONE":
        kwargs["icon"] = icon_name

    operator = row.operator("quick_n_panel.open_target", **kwargs)
    operator.target_key = target_key


def _last_opened_timestamp(target) -> float:
    try:
        return float(target.last_opened_at)
    except (TypeError, ValueError):
        return 0.0
