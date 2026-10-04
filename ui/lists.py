"""Reusable UIList implementations for configuration."""

import bpy

from ..core import icons, scanner
from ..core.search import normalize_text
from ..preferences import display_name_for, favorite_keys, get_preferences


class QNP_UL_Groups(bpy.types.UIList):
    bl_idname = "QNP_UL_launcher_groups"

    def draw_item(
        self,
        _context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_property,
        _index,
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            icon_name, icon_value = icons.resolve_icon(
                item.icon_name,
                item.icon_path,
                item.bundled_icon,
            )
            if icon_value:
                layout.label(text=item.display_name, icon_value=icon_value)
            else:
                layout.label(text=item.display_name, icon=icon_name)
        else:
            layout.alignment = "CENTER"
            layout.label(text="", icon=item.icon_name)


class QNP_UL_Targets(bpy.types.UIList):
    bl_idname = "QNP_UL_launcher_targets"

    def draw_item(
        self,
        context,
        layout,
        _data,
        item,
        _icon,
        _active_data,
        _active_property,
        _index,
    ):
        preferences = get_preferences(context)
        favorites = favorite_keys(preferences) if preferences else ()
        exists = scanner.target_exists(item.native_key)

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            icon_name, icon_value = icons.resolve_icon(
                item.icon_name,
                item.icon_path,
                item.bundled_icon,
            )
            if not exists:
                icon_name, icon_value = "ERROR", 0

            if icon_value:
                row.label(text=display_name_for(item), icon_value=icon_value)
            else:
                row.label(text=display_name_for(item), icon=icon_name)

            is_favorite = item.native_key in favorites
            favorite = row.operator(
                "quick_n_panel.toggle_favorite",
                text="",
                icon="SOLO_ON" if is_favorite else "SOLO_OFF",
                depress=is_favorite,
            )
            favorite.target_key = item.native_key

            group = preferences.groups.get(item.group_id) if item.group_id else None
            group_icon_name, group_icon_value = _group_icon(group)
            group_kwargs = {"text": "", "depress": group is not None}
            if group_icon_value:
                group_kwargs["icon_value"] = group_icon_value
            else:
                group_kwargs["icon"] = group_icon_name
            assign = row.operator(
                "quick_n_panel.assign_target_group",
                **group_kwargs,
            )
            assign.target_key = item.native_key

            if item.hidden:
                row.label(text="", icon="HIDE_ON")
        else:
            layout.alignment = "CENTER"
            layout.label(text="", icon="PLUGIN" if exists else "ERROR")

    def draw_filter(self, _context, layout):
        row = layout.row(align=True)
        row.prop(self, "filter_name", text="", icon="VIEWZOOM")
        row.prop(self, "use_filter_sort_alpha", text="")

    def filter_items(self, _context, data, property_name):
        items = getattr(data, property_name)
        if not self.filter_name:
            flags = []
        else:
            query = normalize_text(self.filter_name)
            flags = []
            for item in items:
                searchable = normalize_text(
                    " ".join(
                        (
                            display_name_for(item),
                            item.native_category,
                            item.panel_labels,
                            item.source_modules,
                        )
                    )
                )
                flags.append(self.bitflag_filter_item if query in searchable else 0)

        order = []
        if self.use_filter_sort_alpha:
            sortable = [display_name_for(item).casefold() for item in items]
            order = bpy.types.UI_UL_list.sort_items_helper(
                list(enumerate(sortable)),
                key=lambda entry: entry[1],
            )
        return flags, order


class QNP_UL_LauncherFavorites(bpy.types.UIList):
    bl_idname = "QNP_UL_launcher_favorites"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        _icon,
        _active_data,
        _active_property,
        _index,
    ):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon="SOLO_ON" if item.target_key else "RADIOBUT_OFF")
            return

        preferences = data
        row = layout.row(align=True)
        row.scale_y = 1.25
        _draw_favorite_target(row, context, preferences, item.target_key, contextual=True)


class QNP_UL_FavoriteConfig(bpy.types.UIList):
    bl_idname = "QNP_UL_launcher_favorite_config"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        _icon,
        _active_data,
        _active_property,
        index,
    ):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon="SOLO_ON" if item.target_key else "RADIOBUT_OFF")
            return

        preferences = data
        target_key = item.target_key
        row = layout.row(align=True)
        row.scale_y = 1.1

        number = row.row(align=True)
        number.alignment = "LEFT"
        number.ui_units_x = 1.0
        number.label(text=str(index + 1), icon="NONE")

        _draw_favorite_target(row, context, preferences, target_key, contextual=False)

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


def _draw_favorite_target(parent, context, preferences, target_key, *, contextual):
    target = preferences.targets.get(target_key) if target_key else None
    if target is None:
        row = parent.row(align=True)
        row.enabled = False
        row.label(text="Missing target" if target_key else "Empty", icon="ERROR")
        return

    exists = scanner.target_exists(target_key)
    available = exists
    if contextual:
        available = available and scanner.target_is_context_available(target_key, context)

    icon_name, icon_value = icons.resolve_icon(
        target.icon_name,
        target.icon_path,
        target.bundled_icon,
    )
    if not exists:
        icon_name, icon_value = "ERROR", 0
    if getattr(preferences, "display_mode", "BOTH") == "NAME":
        icon_name, icon_value = "NONE", 0

    kwargs = {"text": display_name_for(target)}
    if icon_value:
        kwargs["icon_value"] = icon_value
    elif icon_name != "NONE":
        kwargs["icon"] = icon_name

    open_row = parent.row(align=True)
    open_row.enabled = available
    operator = open_row.operator("quick_n_panel.open_target", **kwargs)
    operator.target_key = target_key


def _group_icon(group):
    if group is None:
        return "OUTLINER_COLLECTION", 0
    return icons.resolve_icon(
        group.icon_name,
        group.icon_path,
        group.bundled_icon,
    )


CLASSES = (
    QNP_UL_Groups,
    QNP_UL_Targets,
    QNP_UL_LauncherFavorites,
    QNP_UL_FavoriteConfig,
)
