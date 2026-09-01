"""Feature probes isolating Blender API compatibility checks."""

import bpy


def blender_version() -> tuple[int, int, int]:
    return tuple(bpy.app.version[:3])


def supports_sidebar_activation(region=None) -> bool:
    region_type = type(region) if region is not None else bpy.types.Region
    return hasattr(region_type, "active_panel_category") or hasattr(
        region, "active_panel_category"
    )


def supports_native_search() -> bool:
    return hasattr(bpy.types.WindowManager, "invoke_search_popup")


def capability_report() -> dict[str, bool]:
    return {
        "sidebar_activation": supports_sidebar_activation(),
        "native_search": supports_native_search(),
        "custom_previews": hasattr(bpy.utils, "previews"),
        "context_override": hasattr(bpy.types.Context, "temp_override"),
    }
