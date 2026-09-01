import json
import io
from pathlib import Path
import struct
from types import SimpleNamespace
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

from package_bootstrap import ensure_source_package


ensure_source_package()

from quick_n_panel import persistence


class FakeCollection(list):
    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def add(self):
        item = SimpleNamespace(**self.defaults())
        self.append(item)
        return item


def group_defaults():
    return {
        "name": "",
        "group_id": "",
        "display_name": "New Group",
        "icon_name": "PLUGIN",
        "bundled_icon": "NONE",
        "icon_path": "",
    }


def target_defaults():
    return {
        "name": "",
        "native_key": "",
        "native_category": "",
        "origin_key": "",
        "panel_identifiers": "",
        "display_name": "",
        "panel_labels": "",
        "source_modules": "",
        "open_count": 0,
        "first_opened_at": "",
        "last_opened_at": "",
        "group_id": "",
        "group_order": 0,
        "hidden": False,
        "icon_name": "PLUGIN",
        "bundled_icon": "NONE",
        "icon_path": "",
    }


def favorite_defaults():
    return {"name": "", "target_key": ""}


class FakePreferences:
    def __init__(self):
        self.target_index = 0
        self.group_index = 0
        self.default_groups_initialized = False
        self.default_group_icons_initialized = False
        self.icon_enum_schema_version = 0
        self.favorite_index = 0
        self.favorites_schema_version = 0
        self.favorite_1 = ""
        self.favorite_2 = ""
        self.favorite_3 = ""
        self.last_target_key = ""
        self.last_observed_target_key = ""
        self.activity_schema_version = 0
        self.starter_recents_pending = False
        self.compact_popup_width = 400
        self.display_mode = "BOTH"
        self.icon_color_mode = "ORIGINAL"
        self.icon_tint_color = (1.0, 1.0, 1.0)
        self.max_search_results = 128
        self.include_builtin_tabs = False
        self.groups = FakeCollection(group_defaults)
        self.targets = FakeCollection(target_defaults)
        self.favorites = FakeCollection(favorite_defaults)
        self._stored_keys = set()

    def keys(self):
        return tuple(self._stored_keys)


def configured_preferences():
    preferences = FakePreferences()
    preferences.default_groups_initialized = True
    preferences.default_group_icons_initialized = True
    preferences.icon_enum_schema_version = 2
    preferences.favorites_schema_version = 1
    preferences.activity_schema_version = 1
    preferences.compact_popup_width = 611
    preferences.display_mode = "NAME"
    preferences.icon_color_mode = "CUSTOM"
    preferences.icon_tint_color = (0.2, 0.4, 0.8)
    preferences.max_search_results = 64
    preferences.include_builtin_tabs = True

    group = preferences.groups.add()
    group.name = "custom"
    group.group_id = "custom"
    group.display_name = "Custom Group"
    group.icon_name = "NODETREE"
    group.icon_path = "C:/icons/custom.png"

    target = preferences.targets.add()
    target.name = "VIEW_3D|UI|Example"
    target.native_key = target.name
    target.native_category = "Example"
    target.origin_key = "panel:example"
    target.panel_identifiers = "EXAMPLE_PT_main"
    target.display_name = "Example Tools"
    target.panel_labels = "Example Panel"
    target.source_modules = "example.panels"
    target.open_count = 4
    target.first_opened_at = "10.000000"
    target.last_opened_at = "20.000000"
    target.group_id = group.group_id
    target.hidden = True
    target.icon_name = "MATERIAL"
    target.icon_path = "C:/icons/example.png"

    favorite = preferences.favorites.add()
    favorite.name = target.native_key
    favorite.target_key = target.native_key
    preferences.last_target_key = target.native_key
    preferences.last_observed_target_key = target.native_key
    return preferences


class PersistenceTests(unittest.TestCase):
    def test_fresh_preferences_allow_blender_float_rounding(self):
        preferences = FakePreferences()
        preferences.icon_tint_color = (0.999999976158142, 1.0, 1.0)

        self.assertTrue(persistence.preferences_are_fresh(preferences))

    def test_full_round_trip_preserves_configuration(self):
        source = configured_preferences()
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            self.assertTrue(persistence.save_preferences(source, path=path))
            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(
            persistence.snapshot_preferences(destination),
            persistence.snapshot_preferences(source),
        )

    def test_saved_white_icon_style_is_preserved(self):
        source = configured_preferences()
        source.icon_color_mode = "WHITE"
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            self.assertTrue(persistence.save_preferences(source, path=path))
            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(destination.icon_color_mode, "WHITE")

    def test_existing_live_configuration_wins_over_sidecar(self):
        source = configured_preferences()
        destination = FakePreferences()
        group = destination.groups.add()
        group.name = "live"
        group.group_id = "live"

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            persistence.save_preferences(source, path=path)
            restored = persistence.restore_preferences_if_fresh(destination, path=path)

        self.assertFalse(restored)
        self.assertEqual(destination.groups[0].group_id, "live")

    def test_previous_schema_ignores_removed_fields_and_uses_new_defaults(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["root"]["icon_intensity"] = 1.8
        payload["root"]["accent_strength"] = 0.4
        payload["groups"][0]["color"] = [0.1, 0.2, 0.3, 1.0]
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(destination.groups[0].display_name, "Custom Group")
        self.assertEqual(destination.favorites[0].target_key, "VIEW_3D|UI|Example")
        self.assertFalse(hasattr(destination, "icon_intensity"))

    def test_missing_root_field_resets_to_default_when_replacing_configuration(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["root"].pop("icon_tint_color")
        destination = configured_preferences()
        destination.icon_tint_color = (0.9, 0.1, 0.2)

        persistence._apply_payload(
            destination,
            persistence._validate_payload(payload),
        )

        self.assertEqual(destination.icon_tint_color, (1.0, 1.0, 1.0))

    def test_v1_snapshot_migrates_to_current_format(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["version"] = 1
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences-v1.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(destination.compact_popup_width, 611)
        self.assertEqual(destination.groups[0].group_id, "custom")

    def test_v2_snapshot_adds_empty_panel_identity_metadata(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["version"] = 2
        payload["targets"][0].pop("origin_key")
        payload["targets"][0].pop("panel_identifiers")

        migrated = persistence._validate_payload(payload)

        self.assertEqual(migrated["version"], persistence.FORMAT_VERSION)
        self.assertEqual(migrated["targets"][0]["origin_key"], "")
        self.assertEqual(migrated["targets"][0]["panel_identifiers"], "")

    def test_v3_snapshot_adds_default_icon_color_style(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["version"] = 3
        payload["root"].pop("icon_color_mode")
        payload["root"].pop("icon_tint_color")

        migrated = persistence._validate_payload(payload)

        self.assertEqual(migrated["version"], persistence.FORMAT_VERSION)
        self.assertEqual(migrated["root"]["icon_color_mode"], "ORIGINAL")
        self.assertEqual(migrated["root"]["icon_tint_color"], [1.0, 1.0, 1.0])

    def test_v4_snapshot_removes_icon_intensity(self):
        payload = persistence.snapshot_preferences(configured_preferences())
        payload["version"] = 4
        payload["root"]["icon_intensity"] = 2.0

        migrated = persistence._validate_payload(payload)

        self.assertEqual(migrated["version"], persistence.FORMAT_VERSION)
        self.assertNotIn("icon_intensity", migrated["root"])

    def test_invalid_uniform_icon_color_is_rejected(self):
        payload = persistence.snapshot_preferences(configured_preferences())
        payload["root"]["icon_tint_color"] = [1.0, -0.1, 0.5]

        with self.assertRaisesRegex(ValueError, "icon_tint_color"):
            persistence._validate_payload(payload)

    def test_legacy_filename_is_discovered_automatically(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["version"] = 1
        destination = FakePreferences()
        original_sidecar_path = persistence.sidecar_path

        with tempfile.TemporaryDirectory() as directory:
            current_path = Path(directory) / persistence.SIDECAR_FILENAME
            legacy_path = Path(directory) / persistence.LEGACY_SIDECAR_FILENAMES[0]
            legacy_path.write_text(json.dumps(payload), encoding="utf-8")
            persistence.sidecar_path = lambda *, create=False: current_path
            try:
                self.assertTrue(persistence.restore_preferences_if_fresh(destination))
            finally:
                persistence.sidecar_path = original_sidecar_path

        self.assertEqual(destination.compact_popup_width, 611)

    def test_downgrade_does_not_overwrite_a_newer_snapshot(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["version"] = persistence.FORMAT_VERSION + 1

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            encoded = json.dumps(payload)
            path.write_text(encoded, encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertFalse(persistence.save_preferences(source, path=path))

            self.assertEqual(path.read_text(encoding="utf-8"), encoded)
            self.assertEqual(tuple(Path(directory).glob("*.corrupt-*")), ())

    def test_corrupt_current_snapshot_falls_back_to_backup(self):
        source = configured_preferences()
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            self.assertTrue(persistence.save_preferences(source, path=path))
            source.compact_popup_width = 620
            self.assertTrue(persistence.save_preferences(source, path=path))
            path.write_text("not json", encoding="utf-8")

            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(destination.compact_popup_width, 611)

    def test_save_quarantines_a_corrupt_current_snapshot(self):
        source = configured_preferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            path.write_text("not json", encoding="utf-8")
            self.assertTrue(persistence.save_preferences(source, path=path))

            quarantined = tuple(Path(directory).glob("preferences.json.corrupt-*"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(
                persistence._read_payload(path)["root"]["compact_popup_width"],
                611,
            )

    def test_alternate_sidecar_save_does_not_clean_real_icon_storage(self):
        from quick_n_panel.core import icons

        source = configured_preferences()
        original_cleanup = icons.cleanup_managed_icons
        cleanup_calls = []
        icons.cleanup_managed_icons = lambda paths: cleanup_calls.append(paths)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "preferences.json"
                self.assertTrue(persistence.save_preferences(source, path=path))
        finally:
            icons.cleanup_managed_icons = original_cleanup

        self.assertEqual(cleanup_calls, [])

    def test_collection_limits_reject_resource_exhaustion(self):
        payload = persistence.snapshot_preferences(configured_preferences())
        record = dict(payload["groups"][0])
        payload["groups"] = []
        for index in range(persistence.MAX_GROUP_RECORDS + 1):
            item = dict(record)
            item["group_id"] = f"group-{index}"
            payload["groups"].append(item)

        with self.assertRaisesRegex(ValueError, "too many groups"):
            persistence._validate_payload(payload)

    def test_clean_flush_replaces_a_corrupt_snapshot_from_live_preferences(self):
        source = configured_preferences()
        original_sidecar_path = persistence.sidecar_path
        original_dirty = persistence._preferences_dirty

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / persistence.SIDECAR_FILENAME
            path.write_text("not json", encoding="utf-8")
            persistence.sidecar_path = lambda *, create=False: path
            persistence._preferences_dirty = False
            try:
                self.assertTrue(persistence.flush_pending_save(source))
            finally:
                persistence.sidecar_path = original_sidecar_path
                persistence._preferences_dirty = original_dirty

            restored = persistence._read_payload(path)

        self.assertEqual(restored["root"]["compact_popup_width"], 611)

    def test_clean_flush_replaces_a_valid_but_stale_snapshot(self):
        source = configured_preferences()
        original_sidecar_path = persistence.sidecar_path
        original_dirty = persistence._preferences_dirty

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / persistence.SIDECAR_FILENAME
            self.assertTrue(persistence.save_preferences(source, path=path))
            source.compact_popup_width = 620
            persistence.sidecar_path = lambda *, create=False: path
            persistence._preferences_dirty = False
            try:
                self.assertTrue(persistence.flush_pending_save(source))
            finally:
                persistence.sidecar_path = original_sidecar_path
                persistence._preferences_dirty = original_dirty

            current = persistence._read_payload(path)
            backup = persistence._read_payload(persistence._backup_path(path))

        self.assertEqual(current["root"]["compact_popup_width"], 620)
        self.assertEqual(backup["root"]["compact_popup_width"], 611)

    def test_zip_entry_limit_is_checked_before_zipfile_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(persistence.PORTABLE_PREFERENCES_FILENAME, "{}")
            encoded = bytearray(path.read_bytes())
            offset = encoded.rfind(b"PK\x05\x06")
            excessive = persistence.MAX_PORTABLE_ARCHIVE_ENTRIES + 1
            encoded[offset + 8 : offset + 12] = struct.pack("<HH", excessive, excessive)
            path.write_bytes(encoded)

            with self.assertRaisesRegex(ValueError, "too many files"):
                persistence._preflight_portable_archive(path)

    def test_zip_preflight_rejects_an_underreported_entry_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(persistence.PORTABLE_PREFERENCES_FILENAME, "{}")
                archive.writestr("icons/icon-1.png", b"one")
                archive.writestr("icons/icon-2.png", b"two")
            encoded = bytearray(path.read_bytes())
            offset = encoded.rfind(b"PK\x05\x06")
            encoded[offset + 8 : offset + 12] = struct.pack("<HH", 1, 1)
            path.write_bytes(encoded)

            with self.assertRaisesRegex(ValueError, "entry count is inconsistent"):
                persistence._preflight_portable_archive(path)

    def test_export_fails_instead_of_silently_dropping_a_custom_icon(self):
        from quick_n_panel.core import icons

        source = configured_preferences()
        original_read_icon = icons.read_portable_icon
        icons.read_portable_icon = lambda _path: None
        try:
            with tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / "configuration.zip"
                with self.assertRaisesRegex(ValueError, "custom icon"):
                    persistence.export_configuration(source, archive)
        finally:
            icons.read_portable_icon = original_read_icon

    def test_portable_archive_round_trip_includes_custom_icons(self):
        from quick_n_panel.core import icons

        source = configured_preferences()
        destination = FakePreferences()
        original_read_icon = icons.read_portable_icon
        original_install_icon = icons.install_managed_icon_bytes
        original_flush = persistence.flush_pending_save
        installed = []

        icons.read_portable_icon = lambda _path: b"portable png"

        def install_icon(_data):
            path = f"C:/managed/icon-{len(installed) + 1}.png"
            installed.append(path)
            return path

        icons.install_managed_icon_bytes = install_icon
        persistence.flush_pending_save = lambda _preferences: True
        try:
            with tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / "configuration.zip"
                self.assertEqual(
                    persistence.export_configuration(source, archive),
                    2,
                )
                self.assertEqual(
                    persistence.import_configuration(destination, archive),
                    2,
                )
        finally:
            icons.read_portable_icon = original_read_icon
            icons.install_managed_icon_bytes = original_install_icon
            persistence.flush_pending_save = original_flush

        self.assertEqual(destination.compact_popup_width, 611)
        self.assertEqual(destination.groups[0].icon_path, installed[0])
        self.assertEqual(destination.targets[0].icon_path, installed[1])

    def test_invalid_sidecar_does_not_partially_restore(self):
        source = configured_preferences()
        payload = persistence.snapshot_preferences(source)
        payload["targets"][0]["open_count"] = "invalid"
        destination = FakePreferences()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                restored = persistence.restore_preferences_if_fresh(destination, path=path)

        self.assertFalse(restored)
        self.assertEqual(destination.groups, [])
        self.assertEqual(destination.targets, [])
        self.assertEqual(destination.favorites, [])

    def test_failed_replace_keeps_a_restorable_pending_snapshot(self):
        source = configured_preferences()
        destination = FakePreferences()
        original_replace = persistence._replace_with_retry

        def fail_replace(_source, _target):
            raise PermissionError("locked")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            persistence._replace_with_retry = fail_replace
            try:
                with redirect_stdout(io.StringIO()):
                    saved = persistence.save_preferences(source, path=path)
            finally:
                persistence._replace_with_retry = original_replace

            self.assertFalse(saved)
            self.assertTrue(persistence._pending_path(path).is_file())
            self.assertTrue(
                persistence.restore_preferences_if_fresh(destination, path=path)
            )

        self.assertEqual(destination.compact_popup_width, 611)
        self.assertEqual(destination.groups[0].name, destination.groups[0].group_id)


if __name__ == "__main__":
    unittest.main()
