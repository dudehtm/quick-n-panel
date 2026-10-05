import sys
from types import ModuleType, SimpleNamespace
import unittest

from package_bootstrap import ensure_source_package


def install_fake_bpy():
    bpy = ModuleType("bpy")
    bpy_props = ModuleType("bpy.props")

    def property_factory(**_kwargs):
        return object()

    for name in (
        "BoolProperty",
        "CollectionProperty",
        "EnumProperty",
        "FloatVectorProperty",
        "IntProperty",
        "StringProperty",
    ):
        setattr(bpy_props, name, property_factory)

    bpy.types = SimpleNamespace(
        AddonPreferences=type("AddonPreferences", (), {}),
        PropertyGroup=type("PropertyGroup", (), {}),
    )
    bpy.props = bpy_props
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy_props


ensure_source_package()
install_fake_bpy()

from quick_n_panel.constants import NEW_ADDON_RETENTION_SECONDS  # noqa: E402
from quick_n_panel.core.catalog import (  # noqa: E402
    PanelDescriptor,
    TargetDescriptor,
    make_target_key,
)
from quick_n_panel.preferences import (  # noqa: E402
    acknowledge_new_addons_for_target,
    dismiss_new_addon,
    new_addon_entries,
    reconcile_new_addons,
)


class FakeCollection(list):
    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def add(self):
        item = SimpleNamespace(**self.defaults())
        self.append(item)
        return item

    def get(self, key):
        for item in self:
            if getattr(item, "name", "") == key or getattr(item, "native_key", "") == key:
                return item
        return None

    def remove(self, index):
        del self[index]


def target_defaults():
    return {
        "name": "",
        "native_key": "",
        "native_category": "",
        "source_modules": "",
        "open_count": 0,
        "first_opened_at": "",
        "last_opened_at": "",
        "hidden": False,
    }


def new_addon_defaults():
    return {
        "name": "",
        "addon_key": "",
        "target_key": "",
        "discovered_at": "",
    }


def observed_addon_defaults():
    return {"name": "", "addon_key": ""}


class FakePreferences:
    def __init__(self):
        self.targets = FakeCollection(target_defaults)
        self.new_addons = FakeCollection(new_addon_defaults)
        self.observed_addons = FakeCollection(observed_addon_defaults)
        self.new_addons_initialized = False
        self.observed_addons_initialized = False


def descriptor(category, module):
    return TargetDescriptor(
        native_key=make_target_key("VIEW_3D", "UI", category),
        native_category=category,
        panels=(PanelDescriptor(f"{module}.PT_main", "Tools", module),),
    )


def add_target(preferences, source):
    target = preferences.targets.add()
    target.name = source.native_key
    target.native_key = source.native_key
    target.native_category = source.native_category
    target.source_modules = "\n".join(source.source_modules)
    return target


class NewAddonTests(unittest.TestCase):
    def test_first_scan_establishes_silent_baseline(self):
        preferences = FakePreferences()
        source = descriptor("Sample", "sample.panels")

        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=100.0,
            )
        )
        self.assertTrue(preferences.observed_addons_initialized)
        self.assertEqual(tuple(preferences.new_addons), ())

        self.assertFalse(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=101.0,
            )
        )
        self.assertEqual(tuple(preferences.new_addons), ())

    def test_new_addons_are_unique_by_owner(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        observed = preferences.observed_addons.add()
        observed.name = "existing"
        observed.addon_key = "existing"
        existing = descriptor("Existing", "existing.panels")
        first = descriptor("First", "new_addon.panels")
        second = descriptor("Second", "new_addon.tools")
        other = descriptor("Other", "other_addon.panels")

        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (existing, first, second, other),
                enabled_addon_keys={"existing", "new_addon", "other_addon"},
                timestamp=200.0,
            )
        )
        self.assertEqual(
            {entry.addon_key for entry in preferences.new_addons},
            {"new_addon", "other_addon"},
        )
        self.assertEqual(
            preferences.new_addons.get("new_addon").target_key,
            first.native_key,
        )

    def test_expired_entries_are_removed_without_reappearing(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        source = descriptor("Sample", "sample.panels")
        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=300.0,
            )
        )

        self.assertEqual(
            len(
                new_addon_entries(
                    preferences,
                    timestamp=300.0 + NEW_ADDON_RETENTION_SECONDS - 1,
                )
            ),
            1,
        )
        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=300.0 + NEW_ADDON_RETENTION_SECONDS,
            )
        )
        self.assertEqual(tuple(preferences.new_addons), ())

    def test_opening_target_acknowledges_new_addon(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        source = descriptor("Sample", "sample.panels")
        reconcile_new_addons(
            preferences,
            (source,),
            enabled_addon_keys={"sample"},
            timestamp=400.0,
        )
        add_target(preferences, source)

        self.assertTrue(acknowledge_new_addons_for_target(preferences, source.native_key))
        self.assertEqual(tuple(preferences.new_addons), ())

    def test_dismissal_removes_new_addon(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        source = descriptor("Sample", "sample.panels")
        reconcile_new_addons(
            preferences,
            (source,),
            enabled_addon_keys={"sample"},
            timestamp=500.0,
        )

        self.assertTrue(dismiss_new_addon(preferences, "sample"))
        self.assertFalse(dismiss_new_addon(preferences, "sample"))
        self.assertEqual(tuple(preferences.new_addons), ())

    def test_only_enabled_modules_can_own_a_new_addon(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        enabled = descriptor("Enabled", "bl_ext.user_default.sample.ui")
        unrelated = descriptor("Unrelated", "script_panels")

        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (enabled, unrelated),
                enabled_addon_keys={"bl_ext.user_default.sample"},
                timestamp=600.0,
            )
        )
        self.assertEqual(
            [entry.addon_key for entry in preferences.new_addons],
            ["bl_ext.user_default.sample"],
        )

    def test_reenabled_addon_refreshes_a_dismissed_entry(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        source = descriptor("Sample", "sample.panels")
        reconcile_new_addons(
            preferences,
            (source,),
            enabled_addon_keys={"sample"},
            timestamp=700.0,
        )
        self.assertTrue(dismiss_new_addon(preferences, "sample"))

        self.assertFalse(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=701.0,
            )
        )
        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                transitioned_addon_keys={"sample"},
                timestamp=702.0,
            )
        )
        self.assertEqual(len(preferences.new_addons), 1)
        self.assertEqual(preferences.new_addons[0].discovered_at, "702.000000")

    def test_disable_then_enable_is_detected_from_persistent_baseline(self):
        preferences = FakePreferences()
        preferences.observed_addons_initialized = True
        source = descriptor("Sample", "sample.panels")

        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=800.0,
            )
        )
        preferences.new_addons.clear()
        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (),
                enabled_addon_keys=set(),
                timestamp=801.0,
            )
        )
        self.assertTrue(
            reconcile_new_addons(
                preferences,
                (source,),
                enabled_addon_keys={"sample"},
                timestamp=802.0,
            )
        )
        self.assertEqual(len(preferences.new_addons), 1)


if __name__ == "__main__":
    unittest.main()
