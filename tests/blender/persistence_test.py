"""Installed-extension persistence and portable-backup integration test."""

import importlib
import json
from pathlib import Path
import tempfile

import bpy


def addon_package_name():
    for addon in bpy.context.preferences.addons:
        if addon.module.rsplit(".", 1)[-1] == "quick_n_panel":
            return addon.module
    raise AssertionError("Enable Quick N-panel before running this test")


def main():
    package_name = addon_package_name()
    persistence = importlib.import_module(f"{package_name}.persistence")
    preferences_module = importlib.import_module(f"{package_name}.preferences")
    preferences = preferences_module.get_preferences(bpy.context)
    assert preferences is not None

    original_width = preferences.compact_popup_width
    try:
        preferences.compact_popup_width = 611
        persistence.cancel_pending_save(clear_dirty=False)
        assert persistence._save_timer_callback() is None

        sidecar = persistence.sidecar_path()
        assert sidecar.is_file()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["version"] == persistence.FORMAT_VERSION
        assert payload["root"]["compact_popup_width"] == 611

        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "quick-n-panel-configuration.zip"
            persistence.export_configuration(preferences, archive)
            preferences.compact_popup_width = 620
            assert persistence.flush_pending_save(preferences)
            persistence.import_configuration(preferences, archive)

        assert preferences.compact_popup_width == 611
        assert persistence._backup_path(sidecar).is_file()
    finally:
        preferences.compact_popup_width = original_width
        assert persistence.flush_pending_save(preferences)

    print("Quick N-panel persistence test: OK")


if __name__ == "__main__":
    main()
