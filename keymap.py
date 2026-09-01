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
