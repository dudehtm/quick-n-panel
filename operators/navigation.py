"""Operators that expose the navigation service to Blender UI."""

import bpy
from bpy.props import StringProperty

from ..constants import DIRECT_CATEGORIES
from ..core import navigation, scanner
from ..preferences import display_name_for, get_preferences


class QNP_OT_OpenTarget(bpy.types.Operator):
    bl_idname = "quick_n_panel.open_target"
    bl_label = "Open Sidebar Tab"
    bl_description = "Open the 3D View sidebar and activate this native tab"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        preferences = get_preferences(context)
        target = preferences.targets.get(properties.target_key) if preferences else None
        if target is None:
            return cls.bl_description
        return f"Open the native '{target.native_category}' sidebar tab"

    def execute(self, context):
        result = navigation.open_target(context, self.target_key)
        if not result.success:
            self.report({"WARNING"}, result.message)
            return {"CANCELLED"}
        return {"FINISHED"}


class QNP_OT_OpenDirectCategory(bpy.types.Operator):
    bl_idname = "quick_n_panel.open_direct_category"
    bl_label = "Open Direct Sidebar Tab"
    bl_description = "Open this compact sidebar shortcut"
    bl_options = {"INTERNAL"}

    category: StringProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    @classmethod
    def description(cls, _context, properties):
        category = str(getattr(properties, "category", "") or "")
        return f"Open the native '{category}' sidebar tab" if category else cls.bl_description

    def execute(self, context):
        if (
            self.category not in DIRECT_CATEGORIES
            or self.category not in scanner.available_direct_categories(context)
        ):
            self.report({"WARNING"}, "The sidebar tab is unavailable in this context")
            return {"CANCELLED"}

        result = navigation.open_direct_category(context, self.category)
        if not result.success:
            self.report({"WARNING"}, result.message)
            return {"CANCELLED"}
        return {"FINISHED"}


class QNP_OT_OpenConfiguration(bpy.types.Operator):
    bl_idname = "quick_n_panel.open_configuration"
    bl_label = "Open Launcher Configuration"
    bl_description = "Open the Quick N-panel configuration tab in the sidebar"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def execute(self, context):
        result = navigation.open_configuration(context)
        if not result.success:
            self.report({"WARNING"}, result.message)
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    QNP_OT_OpenTarget,
    QNP_OT_OpenDirectCategory,
    QNP_OT_OpenConfiguration,
)
