"""Ordered favorite configuration section."""

from ...constants import MAX_FAVORITES
from ...core import icons, scanner
from ...preferences import display_name_for


def draw(layout, _context, preferences):
    if not preferences.favorites:
        layout.label(text="No favorites configured", icon="INFO")

    for index, favorite in enumerate(preferences.favorites):
        target_key = favorite.target_key
        box = layout.box()
        row = box.row(align=True)
        index_row = row.row(align=True)
        index_row.alignment = "LEFT"
        index_row.ui_units_x = 1.0
        index_row.label(text=f"{index + 1}", icon="NONE")

        target = preferences.targets.get(target_key) if target_key else None
        open_row = row.row(align=True)
        open_row.alignment = "LEFT"
        if target is None:
            open_row.label(text="Empty", icon="RADIOBUT_OFF")
        else:
            target_exists = scanner.target_exists(target_key)
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
            operator = open_row.operator("quick_n_panel.open_target", **kwargs)
            operator.target_key = target_key

        actions = row.row(align=True)
        actions.alignment = "RIGHT"
        actions.ui_units_x = 4.0

        assign = actions.operator(
            "quick_n_panel.assign_favorite",
            text="",
            icon="EYEDROPPER",
        )
        assign.index = index

        up_row = actions.row(align=True)
        up_row.enabled = bool(target_key) and index > 0
        move_up = up_row.operator(
            "quick_n_panel.move_favorite",
            text="",
            icon="TRIA_UP",
        )
        move_up.index = index
        move_up.direction = -1

        down_row = actions.row(align=True)
        down_row.enabled = bool(target_key) and index < len(preferences.favorites) - 1
        move_down = down_row.operator(
            "quick_n_panel.move_favorite",
            text="",
            icon="TRIA_DOWN",
        )
        move_down.index = index
        move_down.direction = 1

        clear_row = actions.row(align=True)
        clear_row.alert = True
        clear = clear_row.operator(
            "quick_n_panel.clear_favorite",
            text="",
            icon="X",
        )
        clear.index = index

    layout.separator()
    add_row = layout.row(align=True)
    add_row.enabled = len(preferences.favorites) < MAX_FAVORITES
    add = add_row.operator(
        "quick_n_panel.assign_favorite",
        text="Add Favorite",
        icon="ADD",
    )
    add.index = -1
    if len(preferences.favorites) >= MAX_FAVORITES:
        layout.label(text=f"Maximum: {MAX_FAVORITES}", icon="INFO")
