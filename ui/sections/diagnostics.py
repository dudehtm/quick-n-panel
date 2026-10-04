"""Runtime diagnostics configuration section."""

import time

from ...core import compatibility, scanner, update_status


def draw(layout, context, preferences):
    _draw_update_status(layout, context)

    snapshot = scanner.get_snapshot()
    version = ".".join(str(part) for part in compatibility.blender_version())
    layout.label(text=f"Blender: {version}", icon="BLENDER")
    layout.label(text=f"Persistent library records: {len(preferences.targets)}")
    layout.label(text=f"Currently available tabs: {len(snapshot.targets)}")
    layout.label(text=f"Detected panel classes: {snapshot.panel_count}")

    if snapshot.scanned_at:
        scanned = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(snapshot.scanned_at))
        layout.label(text=f"Last scan: {scanned}")
    else:
        layout.label(text="Last scan: Not run", icon="INFO")

    if snapshot.warnings:
        warning = layout.box()
        warning.label(text="Catalog identity warnings", icon="ERROR")
        for message in snapshot.warnings[:3]:
            warning.label(text=message)
        if len(snapshot.warnings) > 3:
            warning.label(text=f"... and {len(snapshot.warnings) - 3} more")

    for name, supported in compatibility.capability_report().items():
        layout.label(
            text=f"{name.replace('_', ' ').title()}: {'Yes' if supported else 'No'}",
            icon="CHECKMARK" if supported else "ERROR",
        )

    layout.separator()
    layout.label(text="Configuration Backup", icon="FILE_BACKUP")
    backup_row = layout.row(align=True)
    backup_row.operator(
        "quick_n_panel.export_configuration",
        text="Export",
        icon="EXPORT",
    )
    backup_row.operator(
        "quick_n_panel.import_configuration",
        text="Import",
        icon="IMPORT",
    )


def _draw_update_status(layout, context):
    status = update_status.get_update_status(context)
    box = layout.box()
    box.label(text="Extension Updates", icon="FILE_REFRESH")
    box.label(text=f"Installed version: {status.local_version or 'Unknown'}")

    if status.remote_version:
        box.label(text=f"Latest cached version: {status.remote_version}")
    if status.repository_name:
        box.label(text=f"Repository: {status.repository_name}")

    if status.status == update_status.STATUS_UPDATE_AVAILABLE:
        box.label(text="Update available", icon="INFO")
    elif status.status == update_status.STATUS_CURRENT:
        box.label(text="Up to date", icon="CHECKMARK")
    elif status.status == update_status.STATUS_MANUAL:
        box.label(text="Manual installation", icon="INFO")
    elif status.status == update_status.STATUS_UNAVAILABLE:
        box.label(text="Update status unavailable", icon="INFO")
    elif status.status == update_status.STATUS_ERROR:
        box.label(text="Update status error", icon="ERROR")
    else:
        box.label(text="Update status not checked", icon="INFO")

    if status.message:
        box.label(text=status.message, icon="INFO")
    box.label(
        text=f"Online access: {'Enabled' if update_status.online_access_enabled() else 'Disabled'}",
        icon="CHECKMARK" if update_status.online_access_enabled() else "INFO",
    )
    if status.index_mtime:
        box.label(
            text=f"Blender index: {update_status.format_index_time(status.index_mtime)}",
        )
