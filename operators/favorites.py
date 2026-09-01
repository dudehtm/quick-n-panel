"""Operators for the ordered favorite collection."""

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from .. import persistence
from ..constants import MAX_FAVORITES
from ..preferences import favorite_keys, get_preferences
from .choices import target_choices


class QNP_OT_AssignFavorite(bpy.types.Operator):
    bl_idname = "quick_n_panel.assign_favorite"
    bl_label = "Assign Favorite"
    bl_property = "target_key"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=-1, min=-1, max=MAX_FAVORITES - 1, options={"HIDDEN"})
    target_key: EnumProperty(name="Sidebar Tab", items=target_choices)

    def invoke(self, context, _event):
        preferences = get_preferences(context)
        if preferences is None:
            return {"CANCELLED"}
        if self.index < 0 and len(preferences.favorites) >= MAX_FAVORITES:
            self.report({"WARNING"}, f"A maximum of {MAX_FAVORITES} favorites is allowed")
            return {"CANCELLED"}
        if not target_choices(self, context):
            self.report({"INFO"}, "No sidebar tabs are available")
            return {"CANCELLED"}
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or not self.target_key:
            return {"CANCELLED"}

        keys = favorite_keys(preferences)
        try:
            existing_index = keys.index(self.target_key)
        except ValueError:
            existing_index = None

        if self.index < 0:
            if len(preferences.favorites) >= MAX_FAVORITES:
                return {"CANCELLED"}
            if existing_index is not None:
                self.report({"INFO"}, "This tab is already a favorite")
                return {"CANCELLED"}
            item = preferences.favorites.add()
            _set_item(item, self.target_key)
            preferences.favorite_index = len(preferences.favorites) - 1
            persistence.request_save()
            return {"FINISHED"}

        if self.index >= len(preferences.favorites):
            return {"CANCELLED"}

        destination = preferences.favorites[self.index]
        old_target_key = destination.target_key
        if existing_index is not None and existing_index != self.index:
            _set_item(preferences.favorites[existing_index], old_target_key)
        _set_item(destination, self.target_key)
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_ClearFavorite(bpy.types.Operator):
    bl_idname = "quick_n_panel.clear_favorite"
    bl_label = "Remove Favorite"
    bl_options = {"INTERNAL"}

    index: IntProperty(min=0, max=MAX_FAVORITES - 1, options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or self.index >= len(preferences.favorites):
            return {"CANCELLED"}
        preferences.favorites.remove(self.index)
        preferences.favorite_index = min(
            preferences.favorite_index,
            max(0, len(preferences.favorites) - 1),
        )
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_MoveFavorite(bpy.types.Operator):
    bl_idname = "quick_n_panel.move_favorite"
    bl_label = "Move Favorite"
    bl_options = {"INTERNAL"}

    index: IntProperty(min=0, max=MAX_FAVORITES - 1, options={"HIDDEN"})
    direction: IntProperty(default=1, min=-1, max=1, options={"HIDDEN"})

    def execute(self, context):
        preferences = get_preferences(context)
        if (
            preferences is None
            or self.direction not in {-1, 1}
            or self.index >= len(preferences.favorites)
        ):
            return {"CANCELLED"}

        destination = self.index + self.direction
        if destination < 0 or destination >= len(preferences.favorites):
            return {"CANCELLED"}
        preferences.favorites.move(self.index, destination)
        preferences.favorite_index = destination
        persistence.request_save()
        return {"FINISHED"}


class QNP_OT_ToggleFavorite(bpy.types.Operator):
    bl_idname = "quick_n_panel.toggle_favorite"
    bl_label = "Toggle Favorite"
    bl_description = "Add this tab to favorites or remove it if already present"
    bl_options = {"INTERNAL"}

    target_key: StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        preferences = get_preferences(context)
        if preferences and properties.target_key in favorite_keys(preferences):
            return "Remove this tab from favorites"
        return "Add this tab to favorites"

    def execute(self, context):
        preferences = get_preferences(context)
        if preferences is None or not self.target_key:
            return {"CANCELLED"}

        keys = favorite_keys(preferences)
        if self.target_key in keys:
            preferences.favorites.remove(keys.index(self.target_key))
            preferences.favorite_index = min(
                preferences.favorite_index,
                max(0, len(preferences.favorites) - 1),
            )
            persistence.request_save()
            return {"FINISHED"}

        if len(preferences.favorites) >= MAX_FAVORITES:
            self.report({"WARNING"}, f"A maximum of {MAX_FAVORITES} favorites is allowed")
            return {"CANCELLED"}

        item = preferences.favorites.add()
        _set_item(item, self.target_key)
        preferences.favorite_index = len(preferences.favorites) - 1
        persistence.request_save()
        return {"FINISHED"}


def _set_item(item, target_key: str):
    item.name = target_key
    item.target_key = target_key


CLASSES = (
    QNP_OT_AssignFavorite,
    QNP_OT_ClearFavorite,
    QNP_OT_MoveFavorite,
    QNP_OT_ToggleFavorite,
)
