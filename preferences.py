"""Add-on preferences and persistent root model."""

import random
import time

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)

from .constants import (
    ADDON_PACKAGE,
    DEFAULT_COMPACT_POPUP_WIDTH,
    DEFAULT_GROUP_DEFINITIONS,
    DEFAULT_ICON_COLOR_MODE,
    DISPLAY_MODE_ITEMS,
    ICON_COLOR_MODE_ITEMS,
    MAX_FAVORITES,
)
from .properties import QNP_PG_Favorite, QNP_PG_Group, QNP_PG_TargetSettings


def _icon_style_updated(_preferences, _context):
    from .core import icons

    icons.refresh_icon_previews()
    _preferences_updated(_preferences, _context)


def _preferences_updated(_preferences, _context):
    from . import persistence

    persistence.request_save()


class QNP_Preferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    targets: CollectionProperty(type=QNP_PG_TargetSettings)
    target_index: IntProperty(default=0, min=0, update=_preferences_updated)

    groups: CollectionProperty(type=QNP_PG_Group)
    group_index: IntProperty(default=0, min=0, update=_preferences_updated)
    default_groups_initialized: BoolProperty(
        default=False,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    default_group_icons_initialized: BoolProperty(
        default=False,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    icon_enum_schema_version: IntProperty(
        default=0,
        min=0,
        options={"HIDDEN"},
        update=_preferences_updated,
    )

    favorites: CollectionProperty(type=QNP_PG_Favorite)
    favorite_index: IntProperty(default=0, min=0, update=_preferences_updated)
    favorites_schema_version: IntProperty(
        default=0,
        min=0,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    favorite_1: StringProperty(
        name="Legacy Favorite 1",
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    favorite_2: StringProperty(
        name="Legacy Favorite 2",
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    favorite_3: StringProperty(
        name="Legacy Favorite 3",
        options={"HIDDEN"},
        update=_preferences_updated,
    )

    last_target_key: StringProperty(name="Recent Target", update=_preferences_updated)
    last_observed_target_key: StringProperty(
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    activity_schema_version: IntProperty(
        default=0,
        min=0,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    starter_recents_pending: BoolProperty(
        default=False,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    compact_popup_width: IntProperty(
        name="Compact Popup Width",
        description="Width of the launcher before Categories is expanded",
        default=DEFAULT_COMPACT_POPUP_WIDTH,
        min=360,
        max=700,
        update=_preferences_updated,
    )
    display_mode: EnumProperty(
        name="Access Labels",
        items=DISPLAY_MODE_ITEMS,
        default="BOTH",
        update=_preferences_updated,
    )
    icon_color_mode: EnumProperty(
        name="Custom Icon Color",
        description="Choose how included and imported PNG icons are colored",
        items=ICON_COLOR_MODE_ITEMS,
        default=DEFAULT_ICON_COLOR_MODE,
        update=_icon_style_updated,
    )
    icon_tint_color: FloatVectorProperty(
        name="Uniform Color",
        description="Color applied to every included and imported PNG icon",
        subtype="COLOR",
        size=3,
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=_icon_style_updated,
    )
    max_search_results: IntProperty(
        name="Search Index Limit",
        description="Maximum number of native search entries indexed at once",
        default=128,
        min=10,
        max=512,
        update=_preferences_updated,
    )
    include_builtin_tabs: BoolProperty(
        name="Include Blender Tabs",
        description="Include built-in Blender sidebar categories in the library",
        default=False,
        update=_preferences_updated,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Configuration is available in the 3D View sidebar.")

        layout.operator("quick_n_panel.refresh_catalog", icon="FILE_REFRESH")


def get_preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(ADDON_PACKAGE)
    return addon.preferences if addon else None


def ensure_default_groups(preferences):
    if not preferences.default_groups_initialized:
        groups_by_name = {
            group.display_name.strip().casefold(): group
            for group in preferences.groups
            if group.display_name.strip()
        }
        for group_id, display_name, icon_name, _bundled_icon in DEFAULT_GROUP_DEFINITIONS:
            group = preferences.groups.get(group_id)
            if group is None:
                group = groups_by_name.get(display_name.casefold())
            if group is None:
                group = preferences.groups.add()
                group.name = group_id
                group.group_id = group_id
                group.display_name = display_name
                group.icon_name = icon_name

        preferences.default_groups_initialized = True

    if not getattr(preferences, "default_group_icons_initialized", False):
        from .core import icons

        for group_id, _display_name, icon_name, bundled_icon in DEFAULT_GROUP_DEFINITIONS:
            group = preferences.groups.get(group_id)
            if (
                group is not None
                and bundled_icon != "NONE"
                and icons.has_bundled_icon(bundled_icon)
                and not getattr(group, "icon_path", "")
                and getattr(group, "bundled_icon", "NONE") in {"", "NONE"}
                and getattr(group, "icon_name", icon_name) == icon_name
            ):
                group.bundled_icon = bundled_icon
        preferences.default_group_icons_initialized = True


def ensure_favorites(preferences):
    if preferences.favorites_schema_version >= 1:
        return

    current = (item.target_key for item in preferences.favorites)
    legacy = (
        preferences.favorite_1,
        preferences.favorite_2,
        preferences.favorite_3,
    )
    keys = _merge_favorite_keys(current, legacy)

    preferences.favorites.clear()
    for target_key in keys:
        item = preferences.favorites.add()
        item.name = target_key
        item.target_key = target_key

    preferences.favorite_index = min(
        preferences.favorite_index,
        max(0, len(preferences.favorites) - 1),
    )
    preferences.favorites_schema_version = 1


def ensure_activity_history(preferences):
    if preferences.activity_schema_version >= 1:
        return

    target = preferences.targets.get(preferences.last_target_key)
    if target is not None and target.open_count == 0:
        timestamp = _timestamp_text(time.time())
        target.open_count = 1
        target.first_opened_at = timestamp
        target.last_opened_at = timestamp
        preferences.last_observed_target_key = preferences.last_target_key

    preferences.activity_schema_version = 1


def ensure_display_mode(preferences):
    try:
        display_mode = preferences.display_mode
    except (AttributeError, RuntimeError, TypeError, ValueError):
        display_mode = ""
    if display_mode not in {"BOTH", "NAME"}:
        preferences.display_mode = "BOTH"


def record_target_open(preferences, target_key: str, *, timestamp=None) -> bool:
    target = preferences.targets.get(target_key)
    if target is None:
        return False

    clear_starter_recents(preferences)
    timestamp = _timestamp_text(time.time() if timestamp is None else timestamp)
    target.open_count += 1
    if not target.first_opened_at:
        target.first_opened_at = timestamp
    target.last_opened_at = timestamp
    preferences.last_target_key = target_key
    preferences.last_observed_target_key = target_key
    return True


def ensure_starter_recents(
    preferences,
    context,
    snapshot,
    *,
    sample=random.sample,
    timestamp=None,
) -> bool:
    real_history = any(
        target.open_count > 0 and target.last_opened_at
        for target in preferences.targets
    )
    if real_history:
        changed = clear_starter_recents(preferences)
        preferences.starter_recents_pending = False
        return changed

    from .core import scanner

    available_keys = {descriptor.native_key for descriptor in snapshot.targets}
    starter_targets = [
        target
        for target in preferences.targets
        if target.open_count == 0 and not target.first_opened_at and target.last_opened_at
    ]
    changed = False
    for target in starter_targets:
        if (
            target.native_key not in available_keys
            or not scanner.target_is_context_available(target.native_key, context)
        ):
            target.last_opened_at = ""
            changed = True

    if any(target.last_opened_at for target in starter_targets):
        return changed
    if starter_targets:
        preferences.starter_recents_pending = True
    if not preferences.starter_recents_pending:
        return changed

    candidates = []
    for descriptor in snapshot.targets:
        settings = preferences.targets.get(descriptor.native_key)
        if (
            settings is not None
            and not settings.hidden
            and scanner.target_is_context_available(descriptor.native_key, context)
        ):
            candidates.append(descriptor.native_key)

    if not candidates:
        return False

    selected = sample(candidates, min(3, len(candidates)))
    base_time = time.time() if timestamp is None else float(timestamp)
    for index, target_key in enumerate(selected):
        target = preferences.targets.get(target_key)
        target.last_opened_at = _timestamp_text(base_time - index * 0.001)

    preferences.starter_recents_pending = False
    return True


def favorite_keys(preferences) -> tuple[str, ...]:
    return tuple(item.target_key for item in preferences.favorites if item.target_key)


def ordered_group_targets(preferences, group_id: str):
    targets = [target for target in preferences.targets if target.group_id == group_id]
    targets.sort(
        key=lambda target: (target.group_order, display_name_for(target).casefold())
    )
    return targets


def clear_starter_recents(preferences) -> bool:
    changed = False
    for target in preferences.targets:
        if target.open_count == 0 and not target.first_opened_at and target.last_opened_at:
            target.last_opened_at = ""
            changed = True
    return changed


def _merge_favorite_keys(*collections) -> tuple[str, ...]:
    result = []
    seen = set()
    for collection in collections:
        for target_key in collection:
            target_key = str(target_key or "")
            if not target_key or target_key in seen:
                continue
            seen.add(target_key)
            result.append(target_key)
            if len(result) == MAX_FAVORITES:
                return tuple(result)
    return tuple(result)


def _timestamp_text(timestamp) -> str:
    return f"{float(timestamp):.6f}"


def display_name_for(target) -> str:
    return target.display_name.strip() or target.native_category


CLASSES = (QNP_Preferences,)
