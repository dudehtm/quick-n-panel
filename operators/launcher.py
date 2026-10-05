"""Quick launcher and native search operators."""

import bpy
from bpy.props import EnumProperty, StringProperty

from .. import persistence
from ..core import icons, navigation, scanner
from ..preferences import (
    display_name_for,
    dismiss_new_addon,
    ensure_starter_recents,
    favorite_keys,
    get_preferences,
)


_search_item_cache = []
_auto_open_panel_callbacks = set()
_AUTO_OPEN_PANEL_ATTEMPTS = 10


def schedule_auto_open_panel(context, preferences, *, panel_name=None):
    if panel_name is None:
        panel_name = ""
        if getattr(preferences, "auto_open_library", False):
            panel_name = "QNP_PT_launcher_library_popover"
        elif getattr(preferences, "auto_open_categories", False):
            panel_name = "QNP_PT_launcher_categories_popover"
    if not panel_name:
        return False

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False

    window = getattr(context, "window", None)
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    attempts = 0

    def open_panel_after_launcher():
        nonlocal attempts
        attempts += 1
        try:
            current_context = bpy.context
            temp_override = getattr(current_context, "temp_override", None)
            if callable(temp_override) and window is not None and area is not None:
                override = {"window": window, "area": area}
                if region is not None:
                    override["region"] = region
                with temp_override(**override):
                    result = bpy.ops.wm.call_panel(
                        name=panel_name,
                        keep_open=True,
                    )
            else:
                result = bpy.ops.wm.call_panel(
                    name=panel_name,
                    keep_open=True,
                )
            if result in ({"FINISHED"}, {"RUNNING_MODAL"}, {"INTERFACE"}):
                _auto_open_panel_callbacks.discard(open_panel_after_launcher)
                return None
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            pass

        if attempts >= _AUTO_OPEN_PANEL_ATTEMPTS:
            _auto_open_panel_callbacks.discard(open_panel_after_launcher)
            return None
        return 0.05

    try:
        _auto_open_panel_callbacks.add(open_panel_after_launcher)
        timers.register(open_panel_after_launcher, first_interval=1.0)
    except (AttributeError, RuntimeError, ValueError):
        _auto_open_panel_callbacks.discard(open_panel_after_launcher)
        return False
    return True


def cancel_pending_auto_open():
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    for callback in tuple(_auto_open_panel_callbacks):
        try:
            if timers is not None and hasattr(timers, "unregister"):
                is_registered = getattr(timers, "is_registered", None)
                if not callable(is_registered) or is_registered(callback):
                    timers.unregister(callback)
        except (AttributeError, RuntimeError, ValueError):
            pass
        _auto_open_panel_callbacks.discard(callback)


def _search_target_items(_operator, context, *, snapshot=None):
    global _search_item_cache

    preferences = get_preferences(context)
    if preferences is None:
        _search_item_cache = []
        return _search_item_cache

    snapshot = snapshot or scanner.refresh_catalog(context)
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

    auto_open_panel: StringProperty(options={"HIDDEN"})

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
        if preferences.auto_open_library:
            self.auto_open_panel = "QNP_PT_launcher_library_popover"
        elif preferences.auto_open_categories:
            self.auto_open_panel = "QNP_PT_launcher_categories_popover"
        else:
            self.auto_open_panel = ""
        return context.window_manager.invoke_popup(
            self,
            width=preferences.compact_popup_width,
        )

    def draw(self, context):
        from ..ui.popup import draw_launcher_popup

        draw_launcher_popup(self.layout, context)
        if self.auto_open_panel:
            panel_name = self.auto_open_panel
            self.auto_open_panel = ""
            preferences = get_preferences(context)
            if preferences is not None:
                schedule_auto_open_panel(
                    context,
                    preferences,
                    panel_name=panel_name,
                )

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
        scanner.refresh_catalog(context, force=True)
        items = _search_target_items(self, context, snapshot=scanner.get_snapshot())
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


class QNP_OT_DismissNewAddon(bpy.types.Operator):
    bl_idname = "quick_n_panel.dismiss_new_addon"
    bl_label = "Dismiss New Add-on"
    bl_description = "Hide this newly detected add-on"
    bl_options = {"INTERNAL"}

    addon_key: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or not dismiss_new_addon(preferences, self.addon_key):
            return {"CANCELLED"}
        persistence.request_save()
        return {"FINISHED"}


CLASSES = (
    QNP_OT_ShowLauncher,
    QNP_OT_SearchTargets,
    QNP_OT_DismissNewAddon,
)
