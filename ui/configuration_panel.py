"""3D View sidebar administration panel."""

import bpy

from ..constants import CONFIG_CATEGORY
from ..core import icons
from ..preferences import get_preferences
from .sections.appearance import draw as draw_appearance
from .sections.diagnostics import draw as draw_diagnostics
from .sections.favorites import draw as draw_favorites
from .sections.groups import draw as draw_groups
from .sections.library import draw as draw_library


class QNP_PT_Configuration(bpy.types.Panel):
    bl_idname = "QNP_PT_configuration"
    bl_label = "Quick N-panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CONFIG_CATEGORY

    def draw(self, context):
        layout = self.layout
        preferences = get_preferences(context)
        if preferences is None:
            layout.label(text="Preferences unavailable", icon="ERROR")
            return

        header = layout.row(align=True)
        header.operator("quick_n_panel.show_launcher", text="Open Launcher", icon="PLUGIN")
        header.operator("quick_n_panel.refresh_catalog", text="", icon="FILE_REFRESH")


class _QNP_PT_ConfigurationSection:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CONFIG_CATEGORY
    bl_parent_id = "QNP_PT_configuration"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return get_preferences(context) is not None


class QNP_PT_Favorites(_QNP_PT_ConfigurationSection, bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_favorites"
    bl_label = "Favorites"
    bl_order = 0
    bl_options = set()

    def draw_header(self, _context):
        icon_value = icons.bundled_icon_value("QNP_Favorites")
        if icon_value:
            self.layout.label(text="", icon_value=icon_value)
        else:
            self.layout.label(text="", icon="SOLO_ON")

    def draw(self, context):
        draw_favorites(self.layout, context, get_preferences(context))


class QNP_PT_Categories(_QNP_PT_ConfigurationSection, bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_categories"
    bl_label = "Categories"
    bl_order = 1

    def draw_header(self, _context):
        self.layout.label(text="", icon="COLLECTION_NEW")

    def draw(self, context):
        draw_groups(self.layout, context, get_preferences(context))


class QNP_PT_Library(_QNP_PT_ConfigurationSection, bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_library"
    bl_label = "Library"
    bl_order = 2

    def draw_header(self, _context):
        self.layout.label(text="", icon="BOOKMARKS")

    def draw(self, context):
        draw_library(self.layout, context, get_preferences(context))


class QNP_PT_Appearance(_QNP_PT_ConfigurationSection, bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_appearance"
    bl_label = "Appearance"
    bl_order = 3

    def draw_header(self, _context):
        self.layout.label(text="", icon="COLOR")

    def draw(self, context):
        draw_appearance(self.layout, context, get_preferences(context))


class QNP_PT_Diagnostics(_QNP_PT_ConfigurationSection, bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_diagnostics"
    bl_label = "Diagnostics"
    bl_order = 4

    def draw_header(self, _context):
        self.layout.label(text="", icon="INFO")

    def draw(self, context):
        draw_diagnostics(self.layout, context, get_preferences(context))


class QNP_PT_LibraryPopover(bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_library_popover"
    bl_label = "Library"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 24

    def draw(self, context):
        from .popup import draw_library_popover

        draw_library_popover(self.layout, context)


class QNP_PT_CategoriesPopover(bpy.types.Panel):
    bl_idname = "QNP_PT_launcher_categories_popover"
    bl_label = "Categories"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 24

    def draw(self, context):
        from .popup import draw_categories_popover

        draw_categories_popover(self.layout, context)


CLASSES = (
    QNP_PT_Configuration,
    QNP_PT_Favorites,
    QNP_PT_Categories,
    QNP_PT_Library,
    QNP_PT_Appearance,
    QNP_PT_Diagnostics,
    QNP_PT_LibraryPopover,
    QNP_PT_CategoriesPopover,
)
