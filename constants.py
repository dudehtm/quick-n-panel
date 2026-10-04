"""Shared constants with no Blender API dependency."""

ADDON_PACKAGE = __package__
ADDON_ID = "quick_n_panel"
CONFIG_CATEGORY = "Quick N-panel"
TARGET_KEY_SEPARATOR = "|"
MAX_FAVORITES = 8
MAX_NEW_ADDONS = 3
NEW_ADDON_RETENTION_SECONDS = 7 * 24 * 60 * 60
DIRECT_CATEGORIES = ("View", "Tool", "Edit", "Item")
DEFAULT_COMPACT_POPUP_WIDTH = 400
DEFAULT_ICON_COLOR_MODE = "ORIGINAL"

DEFAULT_SHORTCUT_TYPE = "F5"
DEFAULT_SHORTCUT_CTRL = False
DEFAULT_SHORTCUT_SHIFT = False
DEFAULT_SHORTCUT_ALT = False

DEFAULT_GROUP_DEFINITIONS = (
    ("default_modeling", "Modeling", "OBJECT_DATA", "QNP_Modeling"),
    ("default_sculpt_paint", "Sculpt & Paint", "TOOL_SETTINGS", "NONE"),
    ("default_materials_nodes", "Materials & Nodes", "MATERIAL", "QNP_Material"),
    ("default_animation_rigging", "Animation & Rigging", "MODIFIER", "QNP_Rigging"),
    ("default_render_output", "Render & Output", "SCENE_DATA", "QNP_Render"),
    ("default_utilities", "Utilities", "PLUGIN", "QNP_Utils"),
)

DISPLAY_MODE_ITEMS = (
    ("BOTH", "Icon and Name", "Show an icon and a short name"),
    ("NAME", "Name", "Show only the short name"),
)

ICON_COLOR_MODE_ITEMS = (
    ("ORIGINAL", "Original", "Preserve each custom icon's source colors"),
    ("WHITE", "White", "Render every custom icon in neutral white"),
    ("CUSTOM", "Custom", "Render every custom icon with one selected color"),
)

BUILTIN_ICON_ITEMS = (
    ("PLUGIN", "Plug-in", "Generic add-on icon", "PLUGIN", 0),
    ("TOOL_SETTINGS", "Tools", "Tool settings", "TOOL_SETTINGS", 1),
    ("MODIFIER", "Modifier", "Modifier tools", "MODIFIER", 2),
    ("NODETREE", "Nodes", "Node tools", "NODETREE", 3),
    ("MATERIAL", "Material", "Material tools", "MATERIAL", 4),
    ("ASSET_MANAGER", "Assets", "Asset tools", "ASSET_MANAGER", 5),
    ("SCENE_DATA", "Scene", "Scene tools", "SCENE_DATA", 6),
    ("OBJECT_DATA", "Object", "Object tools", "OBJECT_DATA", 7),
    ("PREFERENCES", "Settings", "Configuration tools", "PREFERENCES", 8),
)
