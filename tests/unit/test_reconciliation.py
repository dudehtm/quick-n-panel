import sys
from pathlib import Path
from types import SimpleNamespace
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from quick_n_panel.core.catalog import (  # noqa: E402
    PanelDescriptor,
    TargetDescriptor,
    join_metadata,
    make_target_key,
)
from quick_n_panel.core.reconciliation import reconcile_catalog_targets  # noqa: E402


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


class FakeCollection(list):
    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def add(self):
        item = SimpleNamespace(**self.defaults())
        self.append(item)
        return item

    def remove(self, index):
        del self[index]


class InvalidatingItem:
    """Model Blender wrappers that become stale after collection reallocation."""

    def __init__(self, collection, index, generation):
        object.__setattr__(self, "_collection", collection)
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_generation", generation)

    def _data(self):
        collection = object.__getattribute__(self, "_collection")
        generation = object.__getattribute__(self, "_generation")
        if generation != collection.generation:
            raise ReferenceError("stale RNA wrapper")
        return collection.records[object.__getattribute__(self, "_index")]

    def __getattr__(self, name):
        try:
            return self._data()[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name, value):
        self._data()[name] = value


class InvalidatingCollection:
    def __init__(self, defaults):
        self.defaults = defaults
        self.records = []
        self.generation = 0

    def __len__(self):
        return len(self.records)

    def __iter__(self):
        return (
            InvalidatingItem(self, index, self.generation)
            for index in range(len(self.records))
        )

    def __getitem__(self, index):
        return InvalidatingItem(self, index, self.generation)

    def add(self):
        self.generation += 1
        self.records.append(self.defaults())
        return InvalidatingItem(self, len(self.records) - 1, self.generation)

    def remove(self, index):
        self.generation += 1
        del self.records[index]


class FakePreferences:
    def __init__(self):
        self.targets = FakeCollection(target_defaults)
        self.favorites = FakeCollection(favorite_defaults)
        self.target_index = 0
        self.favorite_index = 0
        self.favorite_1 = ""
        self.favorite_2 = ""
        self.favorite_3 = ""
        self.last_target_key = ""
        self.last_observed_target_key = ""


def descriptor(category, identifier, label="Tools", module="sample.panels"):
    return TargetDescriptor(
        native_key=make_target_key("VIEW_3D", "UI", category),
        native_category=category,
        panels=(PanelDescriptor(identifier, label, module),),
    )


def populate_metadata(target, source: TargetDescriptor):
    target.name = source.native_key
    target.native_key = source.native_key
    target.native_category = source.native_category
    target.origin_key = source.origin_key
    target.panel_identifiers = join_metadata(source.panel_identifiers)
    target.panel_labels = join_metadata(source.panel_labels)
    target.source_modules = join_metadata(source.source_modules)


class ReconciliationTests(unittest.TestCase):
    def test_category_rename_preserves_settings_and_references(self):
        preferences = FakePreferences()
        original = descriptor("Sample", "SAMPLE_PT_main")
        renamed = descriptor("My Tools", "SAMPLE_PT_main")
        target = preferences.targets.add()
        populate_metadata(target, original)
        target.display_name = "Favorite Tool"
        target.group_id = "utilities"
        target.group_order = 4
        target.open_count = 3
        target.first_opened_at = "10.000000"
        target.last_opened_at = "20.000000"

        favorite = preferences.favorites.add()
        favorite.name = original.native_key
        favorite.target_key = original.native_key
        preferences.favorite_1 = original.native_key
        preferences.last_target_key = original.native_key
        preferences.last_observed_target_key = original.native_key

        result = reconcile_catalog_targets((renamed,), preferences)

        self.assertTrue(result.changed)
        self.assertEqual(result.warnings, ())
        self.assertEqual(len(preferences.targets), 1)
        self.assertEqual(target.native_key, renamed.native_key)
        self.assertEqual(target.native_category, "My Tools")
        self.assertEqual(target.display_name, "Favorite Tool")
        self.assertEqual(target.group_id, "utilities")
        self.assertEqual(target.group_order, 4)
        self.assertEqual(preferences.favorites[0].target_key, renamed.native_key)
        self.assertEqual(preferences.favorite_1, renamed.native_key)
        self.assertEqual(preferences.last_target_key, renamed.native_key)
        self.assertEqual(preferences.last_observed_target_key, renamed.native_key)

    def test_existing_legacy_duplicate_is_merged_into_live_target(self):
        preferences = FakePreferences()
        current = descriptor("My Tools", "SAMPLE_PT_main")

        stale = preferences.targets.add()
        stale.name = make_target_key("VIEW_3D", "UI", "Sample")
        stale.native_key = stale.name
        stale.native_category = "Sample"
        stale.panel_labels = join_metadata(current.panel_labels)
        stale.source_modules = join_metadata(current.source_modules)
        stale.display_name = "Configured Name"
        stale.group_id = "utilities"
        stale.group_order = 2
        stale.hidden = True
        stale.open_count = 3
        stale.first_opened_at = "1.000000"
        stale.last_opened_at = "5.000000"

        live = preferences.targets.add()
        populate_metadata(live, current)
        live.open_count = 2
        live.first_opened_at = "6.000000"
        live.last_opened_at = "10.000000"

        for key in (stale.native_key, live.native_key):
            favorite = preferences.favorites.add()
            favorite.name = key
            favorite.target_key = key
        preferences.last_target_key = stale.native_key

        result = reconcile_catalog_targets((current,), preferences)

        self.assertTrue(result.changed)
        self.assertEqual(result.warnings, ())
        self.assertEqual(len(preferences.targets), 1)
        self.assertIs(preferences.targets[0], live)
        self.assertEqual(live.display_name, "Configured Name")
        self.assertEqual(live.group_id, "utilities")
        self.assertEqual(live.group_order, 2)
        self.assertTrue(live.hidden)
        self.assertEqual(live.open_count, 5)
        self.assertEqual(live.first_opened_at, "1.000000")
        self.assertEqual(live.last_opened_at, "10.000000")
        self.assertEqual(len(preferences.favorites), 1)
        self.assertEqual(preferences.favorites[0].target_key, current.native_key)
        self.assertEqual(preferences.last_target_key, current.native_key)

    def test_same_module_with_distinct_panel_ids_stays_separate(self):
        preferences = FakePreferences()
        first = descriptor("First", "SAMPLE_PT_first", label="First")
        second = descriptor("Second", "SAMPLE_PT_second", label="Second")

        first_result = reconcile_catalog_targets((first, second), preferences)
        second_result = reconcile_catalog_targets((first, second), preferences)

        self.assertTrue(first_result.changed)
        self.assertFalse(second_result.changed)
        self.assertEqual(len(preferences.targets), 2)
        self.assertEqual(
            {target.native_key for target in preferences.targets},
            {first.native_key, second.native_key},
        )

    def test_ambiguous_legacy_match_is_reported_without_merging(self):
        preferences = FakePreferences()
        stale = preferences.targets.add()
        stale.name = make_target_key("VIEW_3D", "UI", "Old")
        stale.native_key = stale.name
        stale.native_category = "Old"
        stale.panel_labels = "Tools"
        stale.source_modules = "sample.panels"

        first = descriptor("First", "SAMPLE_PT_first")
        second = descriptor("Second", "SAMPLE_PT_second")

        result = reconcile_catalog_targets((first, second), preferences)

        self.assertEqual(len(preferences.targets), 3)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("was not merged", result.warnings[0])

    def test_missing_builtin_is_added_after_existing_rna_records_are_updated(self):
        preferences = FakePreferences()
        preferences.targets = InvalidatingCollection(target_defaults)
        old_tool = descriptor("Tool", "ADDON_PT_tool", module="sample.panels")
        existing = preferences.targets.add()
        populate_metadata(existing, old_tool)

        animation = descriptor(
            "Animation",
            "VIEW3D_PT_animation",
            label="Animation",
            module="bl_ui.space_view3d",
        )
        combined_tool = TargetDescriptor(
            native_key=old_tool.native_key,
            native_category="Tool",
            panels=(
                *old_tool.panels,
                PanelDescriptor(
                    "VIEW3D_PT_tools",
                    "Tools",
                    "bl_ui.space_toolsystem_common",
                ),
            ),
        )

        result = reconcile_catalog_targets((animation, combined_tool), preferences)

        self.assertTrue(result.changed)
        self.assertEqual(len(preferences.targets), 2)
        live_tool = next(
            target
            for target in preferences.targets
            if target.native_key == combined_tool.native_key
        )
        self.assertEqual(
            live_tool.panel_identifiers,
            join_metadata(combined_tool.panel_identifiers),
        )


if __name__ == "__main__":
    unittest.main()
