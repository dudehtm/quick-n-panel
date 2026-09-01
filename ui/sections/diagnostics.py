"""Runtime diagnostics configuration section."""

import time

from ...core import compatibility, scanner


def draw(layout, context, preferences):
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
