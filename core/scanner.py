"""Discovery and runtime catalog cache for VIEW_3D sidebar tabs."""

from dataclasses import dataclass
import time

import bpy
from bpy.app.handlers import persistent

from ..constants import ADDON_PACKAGE, DIRECT_CATEGORIES
from .catalog import (
    PanelDescriptor,
    TargetDescriptor,
    make_target_key,
)
from .reconciliation import reconcile_catalog_targets


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    targets: tuple[TargetDescriptor, ...] = ()
    scanned_at: float = 0.0
    warnings: tuple[str, ...] = ()

    @property
    def by_key(self) -> dict[str, TargetDescriptor]:
        return {target.native_key: target for target in self.targets}

    @property
    def panel_count(self) -> int:
        return sum(len(target.panels) for target in self.targets)


_snapshot = CatalogSnapshot()
_last_include_builtin = None

_NATIVE_DIRECT_PANEL_IDS = {
    "View": "VIEW3D_PT_view3d_properties",
    "Tool": "VIEW3D_PT_active_tool",
}

_PANEL_CONTEXTS_BY_MODE = {
    "OBJECT": {"objectmode"},
    "EDIT_MESH": {"mesh_edit"},
    "EDIT_CURVE": {"curve_edit"},
    "EDIT_SURFACE": {"curve_edit"},
    "EDIT_TEXT": {"text_edit"},
    "EDIT_ARMATURE": {"armature_edit"},
    "EDIT_METABALL": {"mball_edit"},
    "EDIT_LATTICE": {"lattice_edit"},
    "EDIT_CURVES": {"curves_edit"},
    "EDIT_POINT_CLOUD": {"pointcloud_edit"},
    "POSE": {"posemode"},
    "SCULPT": {"sculpt_mode", "paint_common"},
    "SCULPT_CURVES": {"curves_sculpt", "paint_common"},
    "PAINT_WEIGHT": {"weightpaint", "paint_common"},
    "PAINT_VERTEX": {"vertexpaint", "paint_common"},
    "PAINT_TEXTURE": {"imagepaint", "paint_common"},
    "PARTICLE": {"particlemode"},
}


def refresh_catalog(context=None, *, force=False, sync_preferences=True) -> CatalogSnapshot:
    global _snapshot, _last_include_builtin

    context = context or bpy.context
    preferences = _preferences_or_none(context)
    include_builtin = bool(preferences and preferences.include_builtin_tabs)

    cache_is_fresh = time.time() - _snapshot.scanned_at < 1.0
    if (
        not force
        and _snapshot.scanned_at
        and cache_is_fresh
        and include_builtin == _last_include_builtin
    ):
        return _snapshot

    targets = scan_sidebar_targets(include_builtin=include_builtin)
    scanned_at = time.time()
    _snapshot = CatalogSnapshot(targets=targets, scanned_at=scanned_at)
    _last_include_builtin = include_builtin

    if sync_preferences and preferences is not None:
        warnings = sync_catalog_to_preferences(_snapshot, preferences)
        _snapshot = CatalogSnapshot(
            targets=targets,
            scanned_at=scanned_at,
            warnings=warnings,
        )

    return _snapshot


def scan_sidebar_targets(*, include_builtin=False) -> tuple[TargetDescriptor, ...]:
    grouped_panels: dict[str, list[PanelDescriptor]] = {}

    for panel_type in _registered_panel_types():
        if getattr(panel_type, "bl_space_type", "") != "VIEW_3D":
            continue
        if getattr(panel_type, "bl_region_type", "") != "UI":
            continue

        category = str(getattr(panel_type, "bl_category", "") or "").strip()
        if not category:
            continue

        module = str(getattr(panel_type, "__module__", "") or "")
        if _is_own_module(module):
            continue
        if not include_builtin and _is_builtin_module(module):
            continue

        identifier = str(
            getattr(panel_type, "bl_idname", "") or panel_type.__name__
        )
        label = str(getattr(panel_type, "bl_label", "") or category).strip()
        parent_id = str(getattr(panel_type, "bl_parent_id", "") or "")
        order = int(getattr(panel_type, "bl_order", 0) or 0)

        grouped_panels.setdefault(category, []).append(
            PanelDescriptor(
                identifier=identifier,
                label=label,
                module=module,
                parent_id=parent_id,
                order=order,
            )
        )

    targets = []
    for category, panels in grouped_panels.items():
        panels.sort(key=lambda panel: (panel.order, panel.label.casefold(), panel.identifier))
        targets.append(
            TargetDescriptor(
                native_key=make_target_key("VIEW_3D", "UI", category),
                native_category=category,
                panels=tuple(panels),
            )
        )

    targets.sort(key=lambda target: target.native_category.casefold())
    return tuple(targets)


def sync_catalog_to_preferences(snapshot: CatalogSnapshot, preferences):
    result = reconcile_catalog_targets(snapshot.targets, preferences)
    if result.changed:
        from .. import persistence

        persistence.request_save()
    return result.warnings


def get_snapshot() -> CatalogSnapshot:
    return _snapshot


def get_target(target_key: str) -> TargetDescriptor | None:
    return _snapshot.by_key.get(target_key)


def target_exists(target_key: str) -> bool:
    return target_key in _snapshot.by_key


def target_is_context_available(target_key: str, context) -> bool:
    target = get_target(target_key)
    if target is None:
        return False
    if target.native_category == "Item" and getattr(context, "active_object", None) is not None:
        return True
    return _target_has_visible_root_panel(target, context)


def available_direct_categories(context) -> tuple[str, ...]:
    """Return the requested compact shortcuts that exist in this 3D View."""

    area = getattr(context, "area", None)
    if area is None or area.type != "VIEW_3D":
        return ()

    snapshot = refresh_catalog(context)
    available = []
    for category in DIRECT_CATEGORIES:
        if category in _NATIVE_DIRECT_PANEL_IDS:
            is_available = _native_direct_category_available(category, context)
        elif category == "Edit":
            target = snapshot.by_key.get(make_target_key("VIEW_3D", "UI", category))
            is_available = bool(
                target
                and _target_has_visible_root_panel(target, context, extensions_only=True)
            )
        else:
            # Blender's primary Item/Transform panel is implemented in C.
            is_available = getattr(context, "active_object", None) is not None

        if is_available:
            available.append(category)
    return tuple(available)


def invalidate_catalog():
    global _snapshot, _last_include_builtin
    _snapshot = CatalogSnapshot()
    _last_include_builtin = None


@persistent
def _load_post_handler(_unused):
    invalidate_catalog()


def register_handlers():
    if _load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post_handler)


def unregister_handlers():
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
    invalidate_catalog()


def _registered_panel_types():
    seen = set()
    pending = list(bpy.types.Panel.__subclasses__())

    while pending:
        panel_type = pending.pop()
        if panel_type in seen:
            continue
        seen.add(panel_type)
        pending.extend(panel_type.__subclasses__())

        identifier = str(
            getattr(panel_type, "bl_idname", "") or panel_type.__name__
        )
        if bpy.types.Panel.bl_rna_get_subclass_py(identifier, None) is panel_type:
            yield panel_type


def _preferences_or_none(context):
    from ..preferences import get_preferences

    try:
        return get_preferences(context)
    except (AttributeError, KeyError, RuntimeError):
        return None


def _native_direct_category_available(category: str, context) -> bool:
    identifier = _NATIVE_DIRECT_PANEL_IDS[category]
    panel_type = bpy.types.Panel.bl_rna_get_subclass_py(identifier, None)
    if panel_type is None:
        return False
    if str(getattr(panel_type, "bl_category", "") or "") != category:
        return False
    if not _is_builtin_module(str(getattr(panel_type, "__module__", "") or "")):
        return False
    return _panel_is_visible(panel_type, context)


def _target_has_visible_root_panel(
    target: TargetDescriptor,
    context,
    *,
    extensions_only=False,
) -> bool:
    for panel in target.panels:
        if panel.parent_id:
            continue
        panel_type = bpy.types.Panel.bl_rna_get_subclass_py(panel.identifier, None)
        if panel_type is None:
            continue
        module = str(getattr(panel_type, "__module__", "") or "")
        if _is_own_module(module) or (extensions_only and _is_builtin_module(module)):
            continue
        if _panel_is_visible(panel_type, context):
            return True
    return False


def _panel_is_visible(panel_type, context) -> bool:
    panel_context = str(getattr(panel_type, "bl_context", "") or "").lstrip(".")
    if panel_context:
        valid_contexts = _PANEL_CONTEXTS_BY_MODE.get(
            str(getattr(context, "mode", "") or "")
        )
        if not valid_contexts or panel_context not in valid_contexts:
            return False

    workspace = getattr(context, "workspace", None)
    owner_id = str(getattr(panel_type, "bl_owner_id", "") or "")
    if workspace is not None and getattr(workspace, "use_filter_by_owner", False) and owner_id:
        visible_owners = {
            str(getattr(owner, "name", "") or "")
            for owner in getattr(workspace, "owner_ids", ())
        }
        if owner_id not in visible_owners:
            return False

    has_custom_poll = any(
        base is not bpy.types.Panel and "poll" in vars(base)
        for base in getattr(panel_type, "__mro__", ())
    )
    if not has_custom_poll:
        return True

    area = getattr(context, "area", None)
    ui_region = None
    if area is not None:
        ui_region = next(
            (region for region in getattr(area, "regions", ()) if region.type == "UI"),
            None,
        )

    try:
        if ui_region is not None:
            with context.temp_override(area=area, region=ui_region):
                return bool(panel_type.poll(context))
        return bool(panel_type.poll(context))
    except Exception:
        # Third-party panels must not be able to break popup drawing.
        return False


def _is_builtin_module(module: str) -> bool:
    return module == "bl_ui" or module.startswith("bl_ui.")


def _is_own_module(module: str) -> bool:
    return module == ADDON_PACKAGE or module.startswith(f"{ADDON_PACKAGE}.")
