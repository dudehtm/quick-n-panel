"""Persistent RNA data structures."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)

from .constants import BUILTIN_ICON_ITEMS


def _bundled_icon_items(_owner, _context):
    from .core import icons

    return icons.bundled_icon_choices()


def _bundled_icon_updated(owner, _context):
    if owner.bundled_icon != "NONE":
        owner.icon_path = ""
    _persistent_value_updated(owner, _context)


def _persistent_value_updated(_owner, _context):
    from . import persistence

    persistence.request_save()


class QNP_PG_Favorite(bpy.types.PropertyGroup):
    __slots__ = ()

    name: StringProperty(
        name="Internal Name",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    target_key: StringProperty(name="Target Key", update=_persistent_value_updated)


class QNP_PG_TargetSettings(bpy.types.PropertyGroup):
    __slots__ = ()

    name: StringProperty(
        name="Internal Name",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    native_key: StringProperty(name="Target Key", update=_persistent_value_updated)
    native_category: StringProperty(name="Native Tab", update=_persistent_value_updated)
    origin_key: StringProperty(
        name="Origin Key",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    panel_identifiers: StringProperty(
        name="Panel IDs",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    display_name: StringProperty(
        name="Short Name",
        description="Optional name shown by the launcher",
        update=_persistent_value_updated,
    )
    panel_labels: StringProperty(name="Panels", update=_persistent_value_updated)
    source_modules: StringProperty(name="Sources", update=_persistent_value_updated)
    open_count: IntProperty(
        name="Open Count",
        default=0,
        min=0,
        update=_persistent_value_updated,
    )
    first_opened_at: StringProperty(
        name="First Opened",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    last_opened_at: StringProperty(
        name="Last Opened",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    group_id: StringProperty(name="Group", update=_persistent_value_updated)
    group_order: IntProperty(
        name="Group Order",
        default=0,
        min=0,
        update=_persistent_value_updated,
    )
    hidden: BoolProperty(
        name="Hide from Search",
        description="Keep this tab out of the search library",
        default=False,
        update=_persistent_value_updated,
    )
    icon_name: EnumProperty(
        name="Blender Icon",
        items=BUILTIN_ICON_ITEMS,
        default="PLUGIN",
        update=_persistent_value_updated,
    )
    bundled_icon: EnumProperty(
        name="Icon Library",
        description="Icon included with Quick N-panel",
        items=_bundled_icon_items,
        update=_bundled_icon_updated,
    )
    icon_path: StringProperty(
        name="External Icon",
        description="Optional external PNG used when no included icon is selected",
        subtype="FILE_PATH",
        update=_persistent_value_updated,
    )


class QNP_PG_Group(bpy.types.PropertyGroup):
    __slots__ = ()

    name: StringProperty(
        name="Internal Name",
        options={"HIDDEN"},
        update=_persistent_value_updated,
    )
    group_id: StringProperty(name="Group ID", update=_persistent_value_updated)
    display_name: StringProperty(
        name="Name",
        default="New Group",
        update=_persistent_value_updated,
    )
    icon_name: EnumProperty(
        name="Blender Icon",
        items=BUILTIN_ICON_ITEMS,
        default="PLUGIN",
        update=_persistent_value_updated,
    )
    bundled_icon: EnumProperty(
        name="Icon Library",
        description="Icon included with Quick N-panel",
        items=_bundled_icon_items,
        update=_bundled_icon_updated,
    )
    icon_path: StringProperty(
        name="External Icon",
        description="Optional external PNG used when no included icon is selected",
        subtype="FILE_PATH",
        update=_persistent_value_updated,
    )


CLASSES = (
    QNP_PG_Favorite,
    QNP_PG_TargetSettings,
    QNP_PG_Group,
)
