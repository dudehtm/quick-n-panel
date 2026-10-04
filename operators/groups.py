"""Operators for launcher groups and their ordered memberships."""

import uuid

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from .. import persistence
from ..core import icons
from ..core.memberships import (
    group_order_for,
    set_group_membership_order,
    target_group_ids,
    target_in_group,
)
from ..preferences import (
    add_target_to_group,
    clear_target_groups,
    get_preferences,
    ordered_group_targets,
    remove_target_from_group,
)
from .choices import category_target_choices, group_choices


class QNP_OT_AddGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.add_group"
    bl_label = "Add Group"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}

        group_id = uuid.uuid4().hex
        group = preferences.groups.add()
        group.name = group_id
        group.group_id = group_id
        group.display_name = f"Group {len(preferences.groups)}"
        preferences.group_index = len(preferences.groups) - 1
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_RemoveGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.remove_group"
    bl_label = "Remove Group"
    bl_description = "Remove the selected group without deleting library tabs"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        preferences = get_preferences(context)
        if preferences is None or not preferences.groups:
            return {"CANCELLED"}
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or not preferences.groups:
            return {"CANCELLED"}

        index = min(preferences.group_index, len(preferences.groups) - 1)
        group_id = preferences.groups[index].group_id

        for target in preferences.targets:
            if target_in_group(target, group_id):
                remove_target_from_group(preferences, target, group_id)

        icons.remove_managed_icon(preferences.groups[index].icon_path)
        preferences.groups.remove(index)
        preferences.group_index = max(0, min(index, len(preferences.groups) - 1))
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_MoveGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.move_group"
    bl_label = "Move Group"
    bl_options = {"INTERNAL"}

    direction: IntProperty(default=1, min=-1, max=1, options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or not preferences.groups or self.direction not in {-1, 1}:
            return {"CANCELLED"}

        source = min(preferences.group_index, len(preferences.groups) - 1)
        destination = source + self.direction
        if destination < 0 or destination >= len(preferences.groups):
            return {"CANCELLED"}

        preferences.groups.move(source, destination)
        preferences.group_index = destination
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_AssignTargetGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.assign_target_group"
    bl_label = "Assign Category"
    bl_description = "Assign this tab to a launcher category"
    bl_property = "group_id"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})
    group_id: EnumProperty(name="Category", items=group_choices)

    @classmethod
    def description(cls, context, properties):
        preferences = get_preferences(context)
        target = (
            preferences.targets.get(properties.target_key)
            if preferences and properties.target_key
            else None
        )
        if target is None:
            return "Unassigned. Click to choose a category"
        group_names = []
        for group_id in target_group_ids(target):
            group = preferences.groups.get(group_id)
            if group is not None:
                group_names.append(group.display_name)
        if group_names:
            return f"Categories: {', '.join(group_names)}. Click to add another"
        return "Unassigned. Click to choose a category"

    def invoke(self, context, _event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        target = preferences.targets.get(self.target_key) if preferences else None
        if target is None:
            return {"CANCELLED"}

        if self.group_id == "__NONE__":
            clear_target_groups(target)
        else:
            add_target_to_group(preferences, target, self.group_id)
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_AddTargetToGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.add_target_to_group"
    bl_label = "Add Tab to Category"
    bl_description = "Choose a sidebar tab to add to this category"
    bl_property = "target_key"
    bl_options = {"INTERNAL"}

    group_id: StringProperty(options={"HIDDEN"})
    target_key: EnumProperty(name="Sidebar Tab", items=category_target_choices)

    def invoke(self, context, _event):
        preferences = get_preferences(context)
        group = preferences.groups.get(self.group_id) if preferences else None
        if group is None:
            return {"CANCELLED"}
        if not category_target_choices(self, context):
            self.report({"INFO"}, "No other sidebar tabs are available")
            return {"CANCELLED"}

        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        group = preferences.groups.get(self.group_id) if preferences else None
        target = preferences.targets.get(self.target_key) if preferences else None
        if group is None or target is None or target_in_group(target, group.group_id):
            return {"CANCELLED"}

        add_target_to_group(preferences, target, group.group_id)
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_MoveTargetInGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.move_target_in_group"
    bl_label = "Move Tab in Category"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})
    group_id: StringProperty(options={"HIDDEN"})
    direction: IntProperty(default=1, min=-1, max=1, options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        target = preferences.targets.get(self.target_key) if preferences else None
        group_id = (
            getattr(self, "group_id", "") or getattr(target, "group_id", "")
            if target
            else ""
        )
        if target is None or not group_id or not target_in_group(target, group_id):
            return {"CANCELLED"}
        if self.direction not in {-1, 1}:
            return {"CANCELLED"}

        grouped = ordered_group_targets(preferences, group_id)
        source = next(
            index for index, item in enumerate(grouped) if item.native_key == target.native_key
        )
        destination = source + self.direction
        if destination < 0 or destination >= len(grouped):
            return {"CANCELLED"}

        grouped.insert(destination, grouped.pop(source))
        changed = any(
            group_order_for(item, group_id) != index
            for index, item in enumerate(grouped)
        )
        if changed:
            for index, item in enumerate(grouped):
                set_group_membership_order(item, group_id, index)
            persistence.request_save()
        return {"FINISHED"}


class QNP_OT_RemoveTargetFromGroup(bpy.types.Operator):
    bl_idname = "quick_n_panel.remove_target_from_group"
    bl_label = "Remove Tab from Category"
    bl_description = "Remove this tab from its category without deleting it"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})
    group_id: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        target = preferences.targets.get(self.target_key) if preferences else None
        group_id = (
            getattr(self, "group_id", "") or getattr(target, "group_id", "")
            if target
            else ""
        )
        if target is None or not group_id:
            return {"CANCELLED"}

        if not remove_target_from_group(preferences, target, group_id):
            return {"CANCELLED"}
        persistence.request_save()
        return {"FINISHED"}
CLASSES = (
    QNP_OT_AddGroup,
    QNP_OT_RemoveGroup,
    QNP_OT_MoveGroup,
    QNP_OT_AssignTargetGroup,
    QNP_OT_AddTargetToGroup,
    QNP_OT_MoveTargetInGroup,
    QNP_OT_RemoveTargetFromGroup,
)
