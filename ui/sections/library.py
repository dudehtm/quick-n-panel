"""Detected sidebar tab library section."""

from ... import keymap
from ...core import scanner
from ...core.catalog import split_metadata
from ...core.memberships import target_group_ids
from .groups import _draw_external_icon_controls


def draw(layout, context, preferences):
    startup_row = layout.row(align=True)
    startup_row.prop(
        preferences,
        "auto_open_library",
        text=f"Also open Library with {keymap.shortcut_label(context)}",
    )

    snapshot = scanner.get_snapshot()
    summary = layout.row(align=True)
    summary.label(
        text=f"{len(snapshot.targets)} tabs / {snapshot.panel_count} panels",
        icon="BOOKMARKS",
    )
    summary.operator("quick_n_panel.refresh_catalog", text="", icon="FILE_REFRESH")

    layout.template_list(
        "QNP_UL_launcher_targets",
        "",
        preferences,
        "targets",
        preferences,
        "target_index",
        rows=8,
    )

    target = _active_target(preferences)
    if target is None:
        layout.label(text="No detected sidebar tabs", icon="INFO")
        return

    _draw_target_details(layout, preferences, target)


def _draw_target_details(layout, preferences, target):
    box = layout.box()
    exists = scanner.target_exists(target.native_key)
    state_row = box.row(align=True)
    state_row.label(text=f"Native tab: {target.native_category}")
    state_row.label(
        text="Available" if exists else "Unavailable",
        icon="CHECKMARK" if exists else "ERROR",
    )

    identity = box.row(align=True)
    identity.prop(target, "display_name")
    identity.template_icon_view(
        target,
        "bundled_icon",
        show_labels=False,
        scale=1.0,
        scale_popup=4.0,
    )
    box.prop(target, "hidden")
    box.prop(target, "icon_name")
    _draw_external_icon_controls(box, target, "TARGET", target.native_key)

    groups = [preferences.groups.get(group_id) for group_id in target_group_ids(target)]
    groups = [group for group in groups if group is not None]
    if groups:
        label = "Category" if len(groups) == 1 else "Categories"
        box.label(
            text=f"{label}: {', '.join(group.display_name for group in groups)}",
            icon="OUTLINER_COLLECTION",
        )

    action_row = box.row(align=True)
    open_row = action_row.row(align=True)
    open_row.enabled = exists
    open_target = open_row.operator(
        "quick_n_panel.open_target",
        text="Open",
        icon="FORWARD",
    )
    open_target.target_key = target.native_key
    reset = action_row.operator(
        "quick_n_panel.reset_target_customization",
        text="",
        icon="LOOP_BACK",
    )
    reset.target_key = target.native_key

    panels = split_metadata(target.panel_labels)
    if panels:
        header, details = layout.panel("QNP_detected_panels", default_closed=True)
        header.label(text=f"Detected Panels ({len(panels)})", icon="PANEL_CLOSE")
        if details:
            for panel_label in panels[:8]:
                details.label(text=panel_label)
            if len(panels) > 8:
                details.label(text=f"... and {len(panels) - 8} more")


def _active_target(preferences):
    if not preferences.targets:
        return None
    index = min(preferences.target_index, len(preferences.targets) - 1)
    return preferences.targets[index]
