"""Quick launcher and native search operators."""

import bpy
from bpy.props import EnumProperty

from ..core import icons, navigation, scanner
from ..preferences import (
    display_name_for,
    ensure_starter_recents,
    favorite_keys,
    get_preferences,
)


_search_item_cache = []


def _search_target_items(_operator, context):
    global _search_item_cache

    preferences = get_preferences(context)
    if preferences is None:
        _search_item_cache = []
        return _search_item_cache

    snapshot = scanner.refresh_catalog(context)
    available_keys = snapshot.by_key
    favorite_order = {
        key: index for index, key in enumerate(favorite_keys(preferences)) if key
    }

    targets = [
        target
        for target in preferences.targets
        if target.native_key in available_keys and not target.hidden
    ]
    targets.sort(
        key=lambda target: (
            0 if target.native_key in favorite_order else 1,
            favorite_order.get(target.native_key, 99),
            0 if target.native_key == preferences.last_target_key else 1,
            display_name_for(target).casefold(),
        )
    )
    targets = targets[: preferences.max_search_results]

    items = []
    for index, target in enumerate(targets):
        search_label = display_name_for(target)
        description = f"Open the '{target.native_category}' sidebar tab"
        icon_name, icon_value = icons.resolve_icon(
            target.icon_name,
            target.icon_path,
            target.bundled_icon,
        )
        icon = icon_value if icon_value else icon_name
        items.append((target.native_key, search_label, description, icon, index))

    _search_item_cache = items
    return _search_item_cache


class QNP_OT_ShowLauncher(bpy.types.Operator):
    bl_idname = "quick_n_panel.show_launcher"
    bl_label = "Quick N-panel"
    bl_description = "Open the quick sidebar tab launcher"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def invoke(self, context, _event):
        preferences = get_preferences(context)
        if preferences is None:
            self.report({"ERROR"}, "Quick N-panel preferences are unavailable")
            return {"CANCELLED"}

        # Tab managers can re-register panels without notifying other add-ons.
        snapshot = scanner.refresh_catalog(context, force=True)
        navigation.remember_active_target(context, snapshot)
        ensure_starter_recents(preferences, context, snapshot)
        from ..ui.popup import reset_popup_state

        reset_popup_state(context)
        return context.window_manager.invoke_popup(
            self,
            width=preferences.compact_popup_width,
        )

    def draw(self, context):
        from ..ui.popup import draw_launcher_popup

        draw_launcher_popup(self.layout, context)

    def execute(self, _context):
        return {"FINISHED"}


class QNP_OT_SearchTargets(bpy.types.Operator):
    bl_idname = "quick_n_panel.search_targets"
    bl_label = "Search Sidebar Tabs"
    bl_description = "Search detected sidebar tabs by name"
    bl_property = "target_key"
    bl_options = {"INTERNAL"}

    target_key: EnumProperty(name="Sidebar Tab", items=_search_target_items)

    def invoke(self, context, _event):
        scanner.refresh_catalog(context)
        items = _search_target_items(self, context)
        if not items:
            self.report({"INFO"}, "No searchable sidebar tabs were detected")
            return {"CANCELLED"}
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..core.navigation import open_target

        result = open_target(context, self.target_key)
        if not result.success:
            self.report({"WARNING"}, result.message)
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    QNP_OT_ShowLauncher,
    QNP_OT_SearchTargets,
)
