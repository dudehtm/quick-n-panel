"""Launcher group configuration section."""

from ...core import icons, scanner
from ...preferences import display_name_for, favorite_keys, ordered_group_targets


def draw(layout, context, preferences):
    startup_box = layout.box()
    startup_box.label(text="F5 Startup (Experimental)", icon="INFO")
    startup_box.prop(preferences, "auto_open_categories")
    startup_box.label(
        text="Open this popover with the launcher.",
        icon="INFO",
    )

    list_row = layout.row()
    list_row.template_list(
        "QNP_UL_launcher_groups",
        "",
        preferences,
        "groups",
        preferences,
        "group_index",
        rows=4,
    )
    controls = list_row.column(align=True)
    controls.operator("quick_n_panel.add_group", text="", icon="ADD")
    controls.operator("quick_n_panel.remove_group", text="", icon="REMOVE")
    controls.separator()
    up = controls.operator("quick_n_panel.move_group", text="", icon="TRIA_UP")
    up.direction = -1
    down = controls.operator("quick_n_panel.move_group", text="", icon="TRIA_DOWN")
    down.direction = 1

    group = _active_group(preferences)
    if group is None:
        layout.label(text="Create a group to organize tabs", icon="INFO")
        return

    box = layout.box()
    identity = box.row(align=True)
    identity.prop(group, "display_name")
    identity.template_icon_view(
        group,
        "bundled_icon",
        show_labels=False,
        scale=1.0,
        scale_popup=4.0,
    )
    box.prop(group, "icon_name")
    _draw_external_icon_controls(box, group, "GROUP", group.group_id)

    _draw_group_targets(box, context, preferences, group)


def _draw_group_targets(layout, _context, preferences, group):
    targets = ordered_group_targets(preferences, group.group_id)
    layout.separator(factor=0.5)

    header = layout.row(align=True)
    header.label(text=f"Tabs ({len(targets)})", icon="BOOKMARKS")
    add_row = header.row(align=True)
    add_row.alignment = "RIGHT"
    add = add_row.operator(
        "quick_n_panel.add_target_to_group",
        text="",
        icon="ADD",
    )
    add.group_id = group.group_id

    if not targets:
        empty = layout.row()
        empty.enabled = False
        empty.label(text="No tabs assigned", icon="INFO")
        return

    column = layout.column(align=True)
    favorites = favorite_keys(preferences)
    for index, target in enumerate(targets):
        row = column.row(align=True)
        number = row.row(align=True)
        number.alignment = "LEFT"
        number.ui_units_x = 1.0
        number.label(text=str(index + 1))

        target_exists = scanner.target_exists(target.native_key)
        open_row = row.row(align=True)
        open_row.alignment = "LEFT"
        open_row.enabled = target_exists
        icon_name, icon_value = icons.resolve_icon(
            target.icon_name,
            target.icon_path,
            target.bundled_icon,
        )
        if not target_exists:
            icon_name, icon_value = "ERROR", 0
        kwargs = {"text": display_name_for(target)}
        if icon_value:
            kwargs["icon_value"] = icon_value
        else:
            kwargs["icon"] = icon_name
        open_target = open_row.operator("quick_n_panel.open_target", **kwargs)
        open_target.target_key = target.native_key

        actions = row.row(align=True)
        actions.alignment = "RIGHT"
        actions.ui_units_x = 4.0

        is_favorite = target.native_key in favorites
        favorite = actions.operator(
            "quick_n_panel.toggle_favorite",
            text="",
            icon="SOLO_ON" if is_favorite else "SOLO_OFF",
            depress=is_favorite,
        )
        favorite.target_key = target.native_key

        up_row = actions.row(align=True)
        up_row.enabled = index > 0
        move_up = up_row.operator(
            "quick_n_panel.move_target_in_group",
            text="",
            icon="TRIA_UP",
        )
        move_up.target_key = target.native_key
        move_up.group_id = group.group_id
        move_up.direction = -1

        down_row = actions.row(align=True)
        down_row.enabled = index < len(targets) - 1
        move_down = down_row.operator(
            "quick_n_panel.move_target_in_group",
            text="",
            icon="TRIA_DOWN",
        )
        move_down.target_key = target.native_key
        move_down.group_id = group.group_id
        move_down.direction = 1

        remove_row = actions.row(align=True)
        remove_row.alert = True
        remove = remove_row.operator(
            "quick_n_panel.remove_target_from_group",
            text="",
            icon="X",
        )
        remove.target_key = target.native_key
        remove.group_id = group.group_id


def _active_group(preferences):
    if not preferences.groups:
        return None
    index = min(preferences.group_index, len(preferences.groups) - 1)
    return preferences.groups[index]


def _draw_external_icon_controls(layout, owner, owner_type, owner_key):
    row = layout.row(align=True)
    import_icon = row.operator(
        "quick_n_panel.import_icon",
        text="Replace External Icon" if owner.icon_path else "Import External Icon",
        icon="FILE_IMAGE",
    )
    import_icon.owner_type = owner_type
    import_icon.owner_key = owner_key
    if owner.icon_path:
        remove = row.operator("quick_n_panel.remove_external_icon", text="", icon="X")
        remove.owner_type = owner_type
        remove.owner_key = owner_key
