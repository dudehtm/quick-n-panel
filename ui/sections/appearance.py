"""Popup appearance configuration section."""


def draw(layout, _context, preferences):
    column = layout.column(align=True)
    column.prop(preferences, "compact_popup_width")
    column.prop(preferences, "display_mode")
    column.prop(preferences, "max_search_results")
    column.prop(preferences, "include_builtin_tabs")

    layout.separator()
    icon_box = layout.box()
    icon_box.label(text="Custom Icon Style", icon="IMAGE_DATA")
    icon_box.prop(preferences, "icon_color_mode", expand=True)
    if preferences.icon_color_mode == "CUSTOM":
        icon_box.prop(preferences, "icon_tint_color")
    icon_box.label(text="Affects included and imported PNG icons.", icon="INFO")

    layout.separator()
    layout.label(
        text="Blender icons, popup colors, and hover follow the theme.",
        icon="INFO",
    )
