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
    MAX_FAVORITE_RECORDS,
    NEW_ADDON_RETENTION_SECONDS,
)
from .core.catalog import addon_key_for_module
from .core.memberships import (
    group_memberships_for,
    group_order_for,
    set_group_membership_order,
    set_group_memberships,
    target_in_group,
)
from .properties import (
    QNP_PG_Favorite,
    QNP_PG_Group,
    QNP_PG_NewAddon,
    QNP_PG_ObservedAddon,
    QNP_PG_TargetSettings,
)


def _icon_style_updated(_preferences, _context):
    from .core import icons

    icons.refresh_icon_previews()
    _preferences_updated(_preferences, _context)


def _preferences_updated(_preferences, _context):
    from . import persistence

    persistence.request_save()


def _auto_open_panel_updated(preferences, context):
    if preferences.auto_open_library:
        if preferences.auto_open_categories:
            preferences.auto_open_categories = False
    elif preferences.auto_open_categories:
        if preferences.auto_open_library:
            preferences.auto_open_library = False
    _preferences_updated(preferences, context)


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
    new_addons: CollectionProperty(type=QNP_PG_NewAddon)
    new_addons_initialized: BoolProperty(
        default=False,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
    observed_addons: CollectionProperty(type=QNP_PG_ObservedAddon)
    observed_addons_initialized: BoolProperty(
        default=False,
        options={"HIDDEN"},
        update=_preferences_updated,
    )
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
        description="Width of the compact launcher",
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
    auto_open_library: BoolProperty(
        name="Also open Library with the launcher shortcut",
        description="Experimental: also open the existing Library popover when the configured launcher shortcut opens the launcher",
        default=False,
        update=_auto_open_panel_updated,
    )
    auto_open_categories: BoolProperty(
        name="Also open Categories with the launcher shortcut",
        description="Experimental: also open the existing Categories popover when the configured launcher shortcut opens the launcher",
        default=False,
        update=_auto_open_panel_updated,
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


def ensure_group_memberships(preferences) -> bool:
    """Migrate legacy single-category targets to the multi-category model."""
    changed = False
    for target in preferences.targets:
        before = (
            getattr(target, "group_memberships", ""),
            getattr(target, "group_id", ""),
            getattr(target, "group_order", 0),
        )
        set_group_memberships(target, group_memberships_for(target))
        after = (
            getattr(target, "group_memberships", ""),
            getattr(target, "group_id", ""),
            getattr(target, "group_order", 0),
        )
        changed |= before != after
    return changed


def reconcile_new_addons(
    preferences,
    descriptors,
    *,
    enabled_addon_keys=None,
    transitioned_addon_keys=(),
    timestamp=None,
) -> bool:
    """Track add-ons that become enabled and expose a sidebar target."""
    entries = getattr(preferences, "new_addons", None)
    observed = getattr(preferences, "observed_addons", None)
    if (
        entries is None
        or observed is None
        or not hasattr(preferences, "observed_addons_initialized")
    ):
        return False

    timestamp = time.time() if timestamp is None else float(timestamp)
    changed = _prune_new_addons(preferences, timestamp)
    if enabled_addon_keys is None:
        return changed

    enabled_addon_keys = {
        str(addon_key)
        for addon_key in enabled_addon_keys
        if addon_key and str(addon_key) != ADDON_PACKAGE
    }
    descriptors_by_owner = {}
    for descriptor in descriptors:
        for addon_key in _descriptor_addon_keys(descriptor, enabled_addon_keys):
            descriptors_by_owner.setdefault(addon_key, descriptor)

    for entry in entries:
        descriptor = descriptors_by_owner.get(entry.addon_key)
        if descriptor is not None and entry.target_key != descriptor.native_key:
            entry.target_key = descriptor.native_key
            changed = True

    if not preferences.observed_addons_initialized:
        changed |= _replace_observed_addons(preferences, enabled_addon_keys)
        preferences.observed_addons_initialized = True
        return True

    previous_addons = _observed_addon_keys(preferences)
    transitioned = (enabled_addon_keys - previous_addons) | {
        addon_key
        for addon_key in transitioned_addon_keys
        if addon_key in enabled_addon_keys
    }
    changed |= _replace_observed_addons(preferences, enabled_addon_keys)

    for addon_key in sorted(transitioned):
        descriptor = descriptors_by_owner.get(addon_key)
        if descriptor is None:
            continue

        entry = next(
            (entry for entry in entries if entry.addon_key == addon_key),
            None,
        )
        if entry is None:
            entry = entries.add()
            entry.name = addon_key
            entry.addon_key = addon_key
            changed = True
        if entry.target_key != descriptor.native_key:
            entry.target_key = descriptor.native_key
            changed = True
        discovered_at = _timestamp_text(timestamp)
        if entry.discovered_at != discovered_at:
            entry.discovered_at = discovered_at
            changed = True
    return changed


def new_addon_entries(preferences, *, timestamp=None):
    entries = getattr(preferences, "new_addons", ())
    timestamp = time.time() if timestamp is None else float(timestamp)
    active = []
    for entry in entries:
        discovered_at = _timestamp_value(getattr(entry, "discovered_at", ""))
        if discovered_at is None:
            continue
        if timestamp - discovered_at < NEW_ADDON_RETENTION_SECONDS:
            active.append(entry)
    active.sort(
        key=lambda entry: (
            _timestamp_value(getattr(entry, "discovered_at", "")) or 0.0,
            str(getattr(entry, "addon_key", "")),
        ),
        reverse=True,
    )
    return tuple(active)


def dismiss_new_addon(preferences, addon_key: str) -> bool:
    addon_key = str(addon_key or "")
    entries = getattr(preferences, "new_addons", ())
    for index, entry in enumerate(entries):
        if entry.addon_key == addon_key:
            entries.remove(index)
            return True
    return False


def acknowledge_new_addons_for_target(preferences, target_key: str) -> bool:
    entries = getattr(preferences, "new_addons", None)
    if entries is None:
        return False
    changed = False
    for index in reversed(range(len(entries))):
        entry = entries[index]
        if entry.target_key == target_key:
            entries.remove(index)
            changed = True
    return changed


def _prune_new_addons(preferences, timestamp: float) -> bool:
    entries = getattr(preferences, "new_addons", ())
    changed = False
    for index in reversed(range(len(entries))):
        discovered_at = _timestamp_value(getattr(entries[index], "discovered_at", ""))
        if (
            discovered_at is None
            or timestamp - discovered_at >= NEW_ADDON_RETENTION_SECONDS
        ):
            entries.remove(index)
            changed = True
    return changed


def _observed_addon_keys(preferences) -> set[str]:
    return {
        item.addon_key
        for item in getattr(preferences, "observed_addons", ())
        if item.addon_key
    }


def _replace_observed_addons(preferences, addon_keys: set[str]) -> bool:
    observed = preferences.observed_addons
    current = _observed_addon_keys(preferences)
    if current == addon_keys and len(observed) == len(addon_keys):
        return False

    observed.clear()
    for addon_key in sorted(addon_keys):
        item = observed.add()
        item.name = addon_key
        item.addon_key = addon_key
    return True


def _descriptor_addon_keys(descriptor, addon_keys: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                addon_key
                for module in getattr(descriptor, "source_modules", ())
                if (addon_key := addon_key_for_module(module, addon_keys))
            }
        )
    )


def ensure_favorites(preferences):
    if preferences.favorites_schema_version >= 1:
        preferences.favorite_index = min(
            preferences.favorite_index,
            max(0, len(preferences.favorites) - 1),
        )
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
    if acknowledge_new_addons_for_target(preferences, target_key):
        from . import persistence

        persistence.request_save()
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


def add_target_to_group(preferences, target, group_id: str) -> bool:
    group_id = str(group_id or "")
    if not group_id:
        return False

    memberships = group_memberships_for(target)
    if group_id in memberships:
        return False

    orders = [
        group_order_for(item, group_id)
        for item in preferences.targets
        if target_in_group(item, group_id) and item.native_key != target.native_key
    ]
    memberships[group_id] = max(orders, default=-1) + 1
    set_group_memberships(target, memberships)
    return True


def remove_target_from_group(preferences, target, group_id: str) -> bool:
    group_id = str(group_id or "")
    memberships = group_memberships_for(target)
    if group_id not in memberships:
        return False

    del memberships[group_id]
    set_group_memberships(target, memberships)
    for index, item in enumerate(ordered_group_targets(preferences, group_id)):
        set_group_membership_order(item, group_id, index)
    return True


def clear_target_groups(target) -> bool:
    memberships = group_memberships_for(target)
    if not memberships:
        return False
    set_group_memberships(target, {})
    return True


def ordered_group_targets(preferences, group_id: str):
    targets = [
        target for target in preferences.targets if target_in_group(target, group_id)
    ]
    targets.sort(
        key=lambda target: (
            group_order_for(target, group_id),
            display_name_for(target).casefold(),
        )
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
            if len(result) == MAX_FAVORITE_RECORDS:
                return tuple(result)
    return tuple(result)


def _timestamp_text(timestamp) -> str:
    return f"{float(timestamp):.6f}"


def _timestamp_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def display_name_for(target) -> str:
    return target.display_name.strip() or target.native_category


CLASSES = (QNP_Preferences,)
