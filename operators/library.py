"""Operators for catalog refresh and target customization."""

import bpy
from bpy.props import EnumProperty, StringProperty

from .. import persistence
from ..core import icons, scanner
from ..preferences import get_preferences


class QNP_OT_RefreshCatalog(bpy.types.Operator):
    bl_idname = "quick_n_panel.refresh_catalog"
    bl_label = "Refresh Detection"
    bl_description = "Scan registered 3D View sidebar panels again"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        snapshot = scanner.refresh_catalog(context, force=True)
        self.report(
            {"INFO"},
            f"Detected {len(snapshot.targets)} tabs from {snapshot.panel_count} panels",
        )
        return {"FINISHED"}


class QNP_OT_ResetTargetCustomization(bpy.types.Operator):
    bl_idname = "quick_n_panel.reset_target_customization"
    bl_label = "Reset Tab Customization"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        target = preferences.targets.get(self.target_key) if preferences else None
        if target is None:
            return {"CANCELLED"}

        target.display_name = ""
        target.icon_name = "PLUGIN"
        target.bundled_icon = "NONE"
        icons.remove_managed_icon(target.icon_path)
        target.icon_path = ""
        target.hidden = False
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_ImportIcon(bpy.types.Operator):
    bl_idname = "quick_n_panel.import_icon"
    bl_label = "Import External Icon"
    bl_description = "Import a managed 96 px copy so the source file can be moved or deleted"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.png", options={"HIDDEN"})
    owner_type: EnumProperty(
        items=(("TARGET", "Library Tab", ""), ("GROUP", "Category", "")),
        options={"HIDDEN"},
    )
    owner_key: StringProperty(options={"HIDDEN"})

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        owner = _icon_owner(context, self.owner_type, self.owner_key)
        if owner is None:
            self.report({"ERROR"}, "The icon owner no longer exists")
            return {"CANCELLED"}

        try:
            managed_path = icons.import_external_icon(self.filepath)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        previous_path = owner.icon_path
        owner.bundled_icon = "NONE"
        owner.icon_path = managed_path
        icons.remove_managed_icon(previous_path)
        persistence.request_save()
        self.report({"INFO"}, "Imported a managed 96 x 96 icon copy")
        return {"FINISHED"}


class QNP_OT_RemoveExternalIcon(bpy.types.Operator):
    bl_idname = "quick_n_panel.remove_external_icon"
    bl_label = "Remove External Icon"
    bl_description = "Stop using the imported icon and fall back to the selected Blender icon"
    bl_options = {"INTERNAL"}

    owner_type: EnumProperty(
        items=(("TARGET", "Library Tab", ""), ("GROUP", "Category", "")),
        options={"HIDDEN"},
    )
    owner_key: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        owner = _icon_owner(context, self.owner_type, self.owner_key)
        if owner is None:
            return {"CANCELLED"}
        icons.remove_managed_icon(owner.icon_path)
        owner.icon_path = ""
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_ExportConfiguration(bpy.types.Operator):
    bl_idname = "quick_n_panel.export_configuration"
    bl_label = "Export Configuration"
    bl_description = "Save settings and imported icons as a portable ZIP backup"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(subtype="FILE_PATH")
    filename_ext = ".zip"
    filter_glob: StringProperty(default="*.zip", options={"HIDDEN"})

    def invoke(self, context, _event):
        self.filepath = "quick-n-panel-configuration.zip"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        filepath = self.filepath
        if not filepath.lower().endswith(self.filename_ext):
            filepath += self.filename_ext
        try:
            icon_count = persistence.export_configuration(preferences, filepath)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, f"Could not export configuration: {error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Configuration exported with {icon_count} custom icons")
        return {"FINISHED"}


class QNP_OT_ImportConfiguration(bpy.types.Operator):
    bl_idname = "quick_n_panel.import_configuration"
    bl_label = "Import Configuration"
    bl_description = "Replace current settings from a Quick N-panel ZIP backup"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(default="*.zip", options={"HIDDEN"})

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        try:
            icon_count = persistence.import_configuration(preferences, self.filepath)
        except Exception as error:
            self.report({"ERROR"}, f"Could not import configuration: {error}")
            return {"CANCELLED"}
        icons.refresh_icon_previews()
        scanner.refresh_catalog(context, force=True)
        self.report({"INFO"}, f"Configuration imported with {icon_count} custom icons")
        return {"FINISHED"}


def _icon_owner(context, owner_type: str, owner_key: str):
    preferences = get_preferences(context)
    if preferences is None:
        return None
    collection = preferences.targets if owner_type == "TARGET" else preferences.groups
    return collection.get(owner_key)


CLASSES = (
    QNP_OT_RefreshCatalog,
    QNP_OT_ResetTargetCustomization,
    QNP_OT_ImportIcon,
    QNP_OT_RemoveExternalIcon,
    QNP_OT_ExportConfiguration,
    QNP_OT_ImportConfiguration,
)
