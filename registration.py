"""Centralized and reversible Blender registration."""

import bpy
from bpy.props import BoolProperty

from . import keymap, persistence
from .core import icons, navigation, scanner
from .operators.launcher import CLASSES as LAUNCHER_CLASSES
from .operators.navigation import CLASSES as NAVIGATION_CLASSES
from .operators.organization import CLASSES as ORGANIZATION_CLASSES
from .preferences import (
    CLASSES as PREFERENCE_CLASSES,
    ensure_activity_history,
    ensure_default_groups,
    ensure_display_mode,
    ensure_favorites,
    get_preferences,
)
from .properties import CLASSES as PROPERTY_CLASSES
from .ui.configuration_panel import CLASSES as PANEL_CLASSES
from .ui.lists import CLASSES as LIST_CLASSES


CLASSES = (
    *PROPERTY_CLASSES,
    *keymap.CLASSES,
    *PREFERENCE_CLASSES,
    *NAVIGATION_CLASSES,
    *LAUNCHER_CLASSES,
    *ORGANIZATION_CLASSES,
    *LIST_CLASSES,
    *PANEL_CLASSES,
)

_registered_classes = []
_is_registered = False
_ALL_TABS_EXPANDED_PROPERTY = "qnp_all_tabs_expanded"


def _all_tabs_expansion_updated(_window_manager, context):
    region = getattr(context, "region", None)
    if region is not None:
        region.tag_redraw()


def register_addon():
    global _is_registered

    if _is_registered:
        return

    try:
        # Dynamic icon enums must exist before their RNA properties are registered.
        icons.register()
        _register_runtime_properties()
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)

        scanner.register_handlers()
        preferences = get_preferences(bpy.context)
        if preferences is not None:
            preferences_were_fresh = persistence.preferences_are_fresh(preferences)
            restored = persistence.restore_preferences_if_fresh(preferences)
            if preferences_were_fresh and not restored:
                preferences.starter_recents_pending = True
            ensure_display_mode(preferences)
            icons.migrate_managed_icon_paths(preferences)
            icons.refresh_icon_previews()
            icons.migrate_bundled_icon_values(preferences)
            ensure_default_groups(preferences)
            ensure_favorites(preferences)
        scanner.refresh_catalog(bpy.context, force=True)
        if preferences is not None:
            ensure_activity_history(preferences)
        keymap.register()
        _is_registered = True
    except Exception:
        _rollback_registration()
        raise


def unregister_addon():
    global _is_registered

    try:
        preferences = get_preferences(bpy.context)
        if preferences is not None:
            if not persistence.flush_pending_save(preferences):
                print(
                    "Quick N-panel: final preference backup failed; "
                    "a pending snapshot may be available"
                )
    finally:
        _cleanup_runtime()
        _unregister_classes()
        _unregister_runtime_properties()
        _is_registered = False


def _rollback_registration():
    global _is_registered

    _cleanup_runtime()
    _unregister_classes()
    _unregister_runtime_properties()
    _is_registered = False


def _cleanup_runtime():
    for cleanup in (
        persistence.cancel_pending_save,
        navigation.cancel_pending_activations,
        keymap.unregister,
        scanner.unregister_handlers,
        icons.unregister,
    ):
        try:
            cleanup()
        except Exception:
            # Cleanup must continue so Blender is not left partially registered.
            pass


def _unregister_classes():
    while _registered_classes:
        cls = _registered_classes.pop()
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass


def _register_runtime_properties():
    if not hasattr(bpy.types.WindowManager, _ALL_TABS_EXPANDED_PROPERTY):
        setattr(
            bpy.types.WindowManager,
            _ALL_TABS_EXPANDED_PROPERTY,
            BoolProperty(
                name="Show All Tabs",
                description="Show every available tab in the Library popover",
                default=True,
                options={"HIDDEN", "SKIP_SAVE"},
                update=_all_tabs_expansion_updated,
            ),
        )


def _unregister_runtime_properties():
    if hasattr(bpy.types.WindowManager, _ALL_TABS_EXPANDED_PROPERTY):
        delattr(bpy.types.WindowManager, _ALL_TABS_EXPANDED_PROPERTY)
