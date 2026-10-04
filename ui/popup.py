"""Theme-native compact and expanded launcher layouts."""

from ..constants import (
    FAVORITES_VISIBLE_ROWS,
    MAX_FAVORITE_RECORDS,
    MAX_NEW_ADDONS,
)
from ..core import icons, scanner
from ..core.catalog import module_display_name
from ..core.memberships import group_order_for, target_in_group
from ..preferences import (
    display_name_for,
    favorite_keys,
    get_preferences,
    new_addon_entries,
)


_EMPTY_CATEGORIES_EXPANDED_PROPERTY = "qnp_empty_categories_expanded"
_LAUNCHER_FAVORITE_INDEX_PROPERTY = "qnp_launcher_favorite_index"


def draw_launcher_popup(layout, context):
    preferences = get_preferences(context)
    if preferences is None:
        layout.label(text="Preferences unavailable", icon="ERROR")
        return

    snapshot = scanner.get_snapshot()
    draw_state = _popup_draw_state(preferences, snapshot)
    layout.separator(factor=0.2)
    content = layout.row(align=False)
    _draw_search(content, context, preferences, draw_state)
    previous_cache = scanner.set_active_availability_cache(draw_state["availability"])
    try:
        _draw_favorites(content, context, preferences)
    finally:
        scanner.set_active_availability_cache(previous_cache)
    layout.separator(factor=0.2)
    if _draw_direct_categories(
        layout,
        context,
        snapshot=snapshot,
        availability_cache=draw_state["availability"],
    ):
        layout.separator(factor=0.2)

    bottom = layout.row(align=True)
    bottom.scale_y = 1.2
    bottom.popover(
        panel="QNP_PT_launcher_library_popover",
        text="Library",
        icon="TRIA_DOWN",
    )
    bottom.popover(
        panel="QNP_PT_launcher_categories_popover",
        text="Categories",
        icon="TRIA_DOWN",
    )
    bottom.operator(
        "quick_n_panel.open_configuration",
        text="",
        icon="PREFERENCES",
    )


def _draw_direct_categories(
    layout,
    context,
    *,
    snapshot=None,
    availability_cache=None,
) -> bool:
    if snapshot is None and availability_cache is None:
        categories = scanner.available_direct_categories(context)
    else:
        categories = scanner.available_direct_categories(
            context,
            snapshot=snapshot,
            availability_cache=availability_cache,
        )
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


def draw_library_popover(layout, context):
    preferences = get_preferences(context)
    if preferences is None:
        layout.label(text="Preferences unavailable", icon="ERROR")
        return

    snapshot = scanner.get_snapshot()
    available_keys = snapshot.by_key
    draw_state = _popup_draw_state(preferences, snapshot)
    available_targets, _grouped = _library_contents(preferences, available_keys)
    layout.label(text=f"All Tabs ({len(available_targets)})", icon="BOOKMARKS")

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
            show_category_icon=True,
            draw_state=draw_state,
        )


def draw_categories_popover(layout, context):
    preferences = get_preferences(context)
    if preferences is None:
        layout.label(text="Preferences unavailable", icon="ERROR")
        return

    snapshot = scanner.get_snapshot()
    _draw_categories_grid(layout, context, preferences, snapshot=snapshot)


def reset_popup_state(context):
    window_manager = getattr(context, "window_manager", None)
    if window_manager is not None:
        window_manager.qnp_empty_categories_expanded = False
        setattr(window_manager, _LAUNCHER_FAVORITE_INDEX_PROPERTY, 0)


def _draw_categories_grid(layout, context, preferences, *, snapshot=None, draw_state=None):
    snapshot = snapshot or scanner.get_snapshot()
    draw_state = draw_state or _popup_draw_state(preferences, snapshot)
    available_keys = snapshot.by_key
    available_targets, grouped = _library_contents(preferences, available_keys)

    populated = [entry for entry in grouped if entry[1]]
    empty = [entry[0] for entry in grouped if not entry[1]]

    if populated:
        layout.label(text="Categories", icon="COLLECTION_NEW")
        _draw_populated_categories(
            layout,
            context,
            preferences,
            populated,
            available_count=len(available_targets),
            draw_state=draw_state,
        )

    if empty:
        if populated:
            layout.separator(factor=0.5)
        header = layout.row(align=True)
        header.scale_y = 1.1
        expanded = context.window_manager.qnp_empty_categories_expanded
        header.prop(
            context.window_manager,
            _EMPTY_CATEGORIES_EXPANDED_PROPERTY,
            text=f"Empty Categories ({len(empty)})",
            icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )
        if expanded:
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


def _library_contents(preferences, available_keys):
    available_targets = [
        target for target in preferences.targets if target.native_key in available_keys
    ]
    available_targets.sort(key=lambda target: display_name_for(target).casefold())

    grouped = []
    for group in preferences.groups:
        targets = [
            target for target in available_targets if target_in_group(target, group.group_id)
        ]
        targets.sort(
            key=lambda target: (
                group_order_for(target, group.group_id),
                display_name_for(target).casefold(),
            )
        )
        grouped.append((group, targets))
    return available_targets, grouped


def _draw_search(parent, context, preferences, draw_state=None):
    draw_state = draw_state or _popup_draw_state(preferences, scanner.get_snapshot())
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
    else:
        for recent in recent_targets[:3]:
            _draw_target_button(
                column,
                context,
                preferences,
                recent.native_key,
                draw_state=draw_state,
            )

    _draw_new_addons(column, context, preferences, draw_state)


def _draw_new_addons(parent, context, preferences, draw_state=None):
    draw_state = draw_state or _popup_draw_state(preferences, scanner.get_snapshot())
    available_keys = draw_state["snapshot"].by_key
    entries = []
    for entry in new_addon_entries(preferences):
        target = preferences.targets.get(entry.target_key)
        if (
            target is None
            or target.hidden
            or entry.target_key not in available_keys
        ):
            continue
        entries.append(entry)
    entries = entries[:MAX_NEW_ADDONS]
    if not entries:
        return

    parent.separator(factor=1.0)
    parent.label(text="New", icon="RECOVER_LAST")
    for entry in entries:
        _draw_target_button(
            parent,
            context,
            preferences,
            entry.target_key,
            compact=True,
            label_prefix=module_display_name(entry.addon_key),
            dismiss_addon_key=entry.addon_key,
            draw_state=draw_state,
        )


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
    add_row.enabled = len(preferences.favorites) < MAX_FAVORITE_RECORDS
    add = add_row.operator(
        "quick_n_panel.assign_favorite",
        text="",
        icon="ADD",
    )
    add.index = -1
    column.separator(factor=0.6)

    if not preferences.favorites:
        empty = column.row(align=True)
        empty.enabled = False
        empty.label(text="No favorites configured", icon="INFO")
    else:
        list_row = column.row(align=True)
        visible_rows = min(FAVORITES_VISIBLE_ROWS, len(preferences.favorites))
        list_row.template_list(
            "QNP_UL_launcher_favorites",
            "popup",
            preferences,
            "favorites",
            context.window_manager,
            _LAUNCHER_FAVORITE_INDEX_PROPERTY,
            rows=visible_rows,
            maxrows=FAVORITES_VISIBLE_ROWS,
        )


def _draw_populated_categories(
    layout,
    context,
    preferences,
    populated,
    *,
    available_count,
    draw_state=None,
):
    columns_row = layout.split(factor=0.5, align=True)
    columns = (
        columns_row.column(align=True),
        columns_row.column(align=True),
    )
    heights = [0.0, 0.0]

    for group, targets in populated:
        column_index = min(range(len(columns)), key=heights.__getitem__)
        _draw_group(
            columns[column_index],
            context,
            preferences,
            group,
            targets,
            can_add=len(targets) < available_count,
            draw_state=draw_state,
        )
        heights[column_index] += _estimated_group_height(len(targets))


def _estimated_group_height(target_count: int) -> float:
    return 2.0 + target_count


def _draw_group(
    parent,
    context,
    preferences,
    group,
    targets,
    *,
    can_add,
    draw_state=None,
):
    box = parent.box()
    column = box.column(align=True)
    icon_name, icon_value = _resolve_group_icon(group)
    header = column.row(align=True)
    header.scale_y = 1.2
    label = f"{group.display_name} ({len(targets)})"
    if icon_value:
        header.label(text=label, icon_value=icon_value)
    else:
        header.label(text=label, icon=icon_name)
    _draw_add_target_to_group(header, group.group_id, enabled=can_add)
    column.separator(factor=0.6)

    for target in targets:
        kwargs = {"compact": True, "show_favorite": True}
        if draw_state is not None:
            kwargs["draw_state"] = draw_state
        _draw_target_button(column, context, preferences, target.native_key, **kwargs)


def _draw_empty_group(parent, group, *, can_add):
    row = parent.row(align=True)
    icon_name, icon_value = _resolve_group_icon(group)
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
    show_category_icon=False,
    show_favorite=False,
    label_prefix="",
    dismiss_addon_key="",
    draw_state=None,
):
    target = preferences.targets.get(target_key)
    if target is None:
        row = parent.row()
        row.enabled = False
        row.label(text="Missing target", icon="ERROR")
        return

    draw_state = draw_state or _popup_draw_state(preferences, scanner.get_snapshot())
    snapshot = draw_state["snapshot"]
    availability_cache = draw_state["availability"]
    exists = target_key in snapshot.by_key
    available = exists and scanner.target_is_context_available(
        target_key,
        context,
        snapshot=snapshot,
        availability_cache=availability_cache,
    )
    row = parent.row(align=True)
    row.scale_y = 1.0 if compact else 1.35

    text = display_name_for(target)
    if label_prefix:
        text = f"{label_prefix}: {text}"
    if preferences.display_mode == "NAME":
        icon_name, icon_value = "NONE", 0
    else:
        icon_name, icon_value = icons.resolve_icon(
            target.icon_name,
            target.icon_path,
            target.bundled_icon,
        )
    if not exists:
        icon_name, icon_value = "ERROR", 0

    kwargs = {"text": text}
    if icon_value:
        kwargs["icon_value"] = icon_value
    elif icon_name != "NONE":
        kwargs["icon"] = icon_name

    open_row = row.row(align=True)
    open_row.enabled = available
    operator = open_row.operator("quick_n_panel.open_target", **kwargs)
    operator.target_key = target_key
    if show_category_icon:
        icon_name, icon_value = _category_icon_for_target(preferences, target)
        if icon_value:
            row.label(text="", icon_value=icon_value)
        else:
            row.label(text="", icon=icon_name)
    if show_favorite:
        is_favorite = target_key in draw_state["favorite_keys"]
        favorite = row.operator(
            "quick_n_panel.toggle_favorite",
            text="",
            icon="SOLO_ON" if is_favorite else "SOLO_OFF",
            depress=is_favorite,
        )
        favorite.target_key = target_key
    if dismiss_addon_key:
        dismiss = row.operator(
            "quick_n_panel.dismiss_new_addon",
            text="",
            icon="X",
        )
        dismiss.addon_key = dismiss_addon_key


def _resolve_group_icon(group):
    if group is None:
        return "OUTLINER_COLLECTION", 0
    return icons.resolve_icon(
        group.icon_name,
        group.icon_path,
        group.bundled_icon,
    )


def _category_icon_for_target(preferences, target):
    groups = getattr(preferences, "groups", None)
    group_id = getattr(target, "group_id", "")
    getter = getattr(groups, "get", None)
    group = getter(group_id) if group_id and callable(getter) else None
    return _resolve_group_icon(group)


def _last_opened_timestamp(target) -> float:
    try:
        return float(target.last_opened_at)
    except (TypeError, ValueError):
        return 0.0


def _popup_draw_state(preferences, snapshot):
    return {
        "snapshot": snapshot,
        "availability": {},
        "favorite_keys": frozenset(
            favorite_keys(preferences) if hasattr(preferences, "favorites") else ()
        ),
    }
