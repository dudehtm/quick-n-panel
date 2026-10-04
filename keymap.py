"""Default shortcut registration and cleanup."""

import bpy

from .constants import (
    DEFAULT_SHORTCUT_ALT,
    DEFAULT_SHORTCUT_CTRL,
    DEFAULT_SHORTCUT_SHIFT,
    DEFAULT_SHORTCUT_TYPE,
)


OPERATOR_ID = "quick_n_panel.show_launcher"
_addon_keymaps = []


def shortcut_label(context=None):
    """Return the currently configured launcher shortcut for UI labels."""
    context = context or bpy.context
    window_manager = getattr(context, "window_manager", None)
    keyconfigs = getattr(window_manager, "keyconfigs", None)
    if keyconfigs is not None:
        for config_name in ("user", "addon"):
            key_config = getattr(keyconfigs, config_name, None)
            keymap = _find_keymap(key_config)
            if keymap is None:
                continue
            keymap_item = next(
                (
                    item
                    for item in getattr(keymap, "keymap_items", ())
                    if getattr(item, "idname", "") == OPERATOR_ID
                ),
                None,
            )
            if keymap_item is None:
                continue
            if not getattr(keymap_item, "active", True):
                return "No shortcut"
            to_string = getattr(keymap_item, "to_string", None)
            if callable(to_string):
                try:
                    label = to_string(compact=True)
                except TypeError:
                    label = to_string()
                if label:
                    return label
            return _fallback_shortcut_label(keymap_item)

    return _fallback_shortcut_label(None)


def _find_keymap(key_config):
    if key_config is None:
        return None
    keymaps = getattr(key_config, "keymaps", None)
    if keymaps is None:
        return None
    try:
        keymap = keymaps.get("3D View")
    except (AttributeError, TypeError):
        keymap = None
    if keymap is not None:
        return keymap
    for candidate in keymaps:
        if (
            getattr(candidate, "name", "") == "3D View"
            and getattr(candidate, "space_type", "") == "VIEW_3D"
        ):
            return candidate
    return None


def _fallback_shortcut_label(keymap_item):
    if keymap_item is None:
        key_type = DEFAULT_SHORTCUT_TYPE
        ctrl = DEFAULT_SHORTCUT_CTRL
        shift = DEFAULT_SHORTCUT_SHIFT
        alt = DEFAULT_SHORTCUT_ALT
    else:
        key_type = getattr(keymap_item, "type", DEFAULT_SHORTCUT_TYPE)
        ctrl = getattr(keymap_item, "ctrl", False)
        shift = getattr(keymap_item, "shift", False)
        alt = getattr(keymap_item, "alt", False)
    modifiers = [
        name
        for name, enabled in (("Ctrl", ctrl), ("Shift", shift), ("Alt", alt))
        if enabled
    ]
    return "+".join((*modifiers, key_type))


def register():
    window_manager = bpy.context.window_manager
    key_config = window_manager.keyconfigs.addon if window_manager else None
    if key_config is None:
        return

    keymap = key_config.keymaps.new(name="3D View", space_type="VIEW_3D")
    keymap_item = keymap.keymap_items.new(
        OPERATOR_ID,
        DEFAULT_SHORTCUT_TYPE,
        "PRESS",
        ctrl=DEFAULT_SHORTCUT_CTRL,
        shift=DEFAULT_SHORTCUT_SHIFT,
        alt=DEFAULT_SHORTCUT_ALT,
    )
    _addon_keymaps.append((keymap, keymap_item))


def unregister():
    while _addon_keymaps:
        keymap, keymap_item = _addon_keymaps.pop()
        try:
            keymap.keymap_items.remove(keymap_item)
        except (ReferenceError, RuntimeError):
            pass


CLASSES = ()
