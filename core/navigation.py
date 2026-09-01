"""Supported sidebar navigation using Region.active_panel_category."""

from dataclasses import dataclass

import bpy

from ..constants import CONFIG_CATEGORY
from ..preferences import clear_starter_recents, get_preferences, record_target_open
from . import scanner
from .catalog import make_target_key
from .compatibility import supports_sidebar_activation


_category_activation_callbacks = set()


@dataclass(frozen=True, slots=True)
class NavigationResult:
    success: bool
    message: str = ""


def open_target(context, target_key: str) -> NavigationResult:
    snapshot = scanner.refresh_catalog(context)
    target = snapshot.by_key.get(target_key)
    if target is None:
        return NavigationResult(False, "The sidebar tab is no longer available")

    if not scanner.target_is_context_available(target_key, context):
        return NavigationResult(False, "The sidebar tab is unavailable in this context")

    result = activate_category(context, target.native_category)
    if not result.success:
        return result

    preferences = get_preferences(context)
    if preferences is not None:
        record_target_open(preferences, target_key)

    _refresh_launcher_region(context)
    return result


def open_direct_category(context, category: str) -> NavigationResult:
    result = activate_category(context, category)
    if not result.success:
        return result

    preferences = get_preferences(context)
    changed = False
    if preferences is not None:
        target_key = make_target_key("VIEW_3D", "UI", category)
        if scanner.target_exists(target_key):
            changed = record_target_open(preferences, target_key)
        else:
            changed = clear_starter_recents(preferences)
    if changed:
        _refresh_launcher_region(context)
    return result


def _refresh_launcher_region(context):
    # The launcher stays open, so rebuild its temporary region after Recent changes.
    try:
        source_region = getattr(context, "region", None)
        if source_region is not None and source_region.type == "TEMPORARY":
            source_region.tag_refresh_ui()
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def open_configuration(context) -> NavigationResult:
    return activate_category(context, CONFIG_CATEGORY)


def remember_active_target(context, snapshot=None) -> bool:
    preferences = get_preferences(context)
    category = active_sidebar_category(context)
    if preferences is None or not category:
        return False

    snapshot = snapshot or scanner.refresh_catalog(context)
    target_key = make_target_key("VIEW_3D", "UI", category)
    if target_key not in snapshot.by_key:
        preferences.last_observed_target_key = ""
        return False
    if target_key == preferences.last_observed_target_key:
        return False
    return record_target_open(preferences, target_key)


def active_sidebar_category(context) -> str:
    area = getattr(context, "area", None)
    if area is None or area.type != "VIEW_3D":
        return ""
    space = getattr(getattr(area, "spaces", None), "active", None)
    if space is not None and hasattr(space, "show_region_ui") and not space.show_region_ui:
        return ""
    ui_region = _ui_region(area)
    if ui_region is None:
        return ""
    try:
        return str(ui_region.active_panel_category or "")
    except (AttributeError, ReferenceError, RuntimeError):
        return ""


def activate_category(context, category: str) -> NavigationResult:
    area = getattr(context, "area", None)
    if area is None or area.type != "VIEW_3D":
        return NavigationResult(False, "Run Quick N-panel from a 3D View")

    space = area.spaces.active
    if not hasattr(space, "show_region_ui"):
        return NavigationResult(False, "The active editor has no sidebar")

    ui_region = _ui_region(area)
    if ui_region is None:
        return NavigationResult(False, "The 3D View sidebar region was not found")
    if not supports_sidebar_activation(ui_region):
        return NavigationResult(False, "This Blender version cannot activate sidebar tabs")

    try:
        space.show_region_ui = True
        ui_region.active_panel_category = category
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        # A newly opened sidebar has no runtime category enum until its first redraw.
        if not _schedule_category_activation(area, ui_region, category):
            return NavigationResult(False, f"Could not activate the sidebar tab: {error}")

    for redraw_target in (ui_region, area):
        try:
            redraw_target.tag_redraw()
        except (AttributeError, ReferenceError, RuntimeError):
            pass

    return NavigationResult(True)


def _schedule_category_activation(area, ui_region, category: str) -> bool:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return False

    attempts = 0

    def activate_after_redraw():
        nonlocal attempts
        attempts += 1
        try:
            area.spaces.active.show_region_ui = True
            ui_region.active_panel_category = category
            ui_region.tag_redraw()
            area.tag_redraw()
            _category_activation_callbacks.discard(activate_after_redraw)
            return None
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            if attempts >= 10:
                _category_activation_callbacks.discard(activate_after_redraw)
                return None
            return 0.05

    try:
        _category_activation_callbacks.add(activate_after_redraw)
        timers.register(activate_after_redraw, first_interval=0.0)
    except (AttributeError, RuntimeError, ValueError):
        _category_activation_callbacks.discard(activate_after_redraw)
        return False
    return True


def cancel_pending_activations() -> None:
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    for callback in tuple(_category_activation_callbacks):
        try:
            if timers is not None and hasattr(timers, "unregister"):
                is_registered = getattr(timers, "is_registered", None)
                if not callable(is_registered) or is_registered(callback):
                    timers.unregister(callback)
        except (AttributeError, RuntimeError, ValueError):
            pass
        _category_activation_callbacks.discard(callback)


def _ui_region(area):
    return next(
        (region for region in area.regions if region.type == "UI"),
        None,
    )
