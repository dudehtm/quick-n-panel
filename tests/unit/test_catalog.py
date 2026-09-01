import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from quick_n_panel.core.catalog import (  # noqa: E402
    PanelDescriptor,
    TargetDescriptor,
    make_target_key,
    module_owner_key,
    module_display_name,
)


class CatalogTests(unittest.TestCase):
    def test_target_key_contains_native_location(self):
        self.assertEqual(
            make_target_key("VIEW_3D", "UI", "Hard Ops"),
            "VIEW_3D|UI|Hard Ops",
        )

    def test_extension_module_name_is_readable(self):
        self.assertEqual(
            module_display_name("bl_ext.user_default.hard_ops.ui.panels"),
            "Hard Ops",
        )

    def test_legacy_module_name_is_readable(self):
        self.assertEqual(module_display_name("mesh_machine.panels"), "Mesh Machine")

    def test_target_deduplicates_source_modules(self):
        target = TargetDescriptor(
            native_key="key",
            native_category="Tools",
            panels=(
                PanelDescriptor("A_PT_one", "One", "sample.panels"),
                PanelDescriptor("A_PT_two", "Two", "sample.panels"),
            ),
        )
        self.assertEqual(target.source_modules, ("sample.panels",))
        self.assertEqual(target.panel_labels, ("One", "Two"))

    def test_origin_identity_does_not_depend_on_visible_category(self):
        panels = (
            PanelDescriptor("SAMPLE_PT_main", "Sample", "sample.panels"),
            PanelDescriptor(
                "SAMPLE_PT_options",
                "Options",
                "sample.panels",
                parent_id="SAMPLE_PT_main",
            ),
        )
        original = TargetDescriptor(
            native_key=make_target_key("VIEW_3D", "UI", "Sample"),
            native_category="Sample",
            panels=panels,
        )
        renamed = TargetDescriptor(
            native_key=make_target_key("VIEW_3D", "UI", "My Tools"),
            native_category="My Tools",
            panels=panels,
        )

        self.assertEqual(original.origin_key, renamed.origin_key)
        self.assertEqual(original.identity_panel_identifiers, ("SAMPLE_PT_main",))

    def test_distinct_tabs_from_same_addon_have_distinct_origins(self):
        first = TargetDescriptor(
            native_key="first",
            native_category="First",
            panels=(PanelDescriptor("SAMPLE_PT_first", "First", "sample.panels"),),
        )
        second = TargetDescriptor(
            native_key="second",
            native_category="Second",
            panels=(PanelDescriptor("SAMPLE_PT_second", "Second", "sample.panels"),),
        )

        self.assertNotEqual(first.origin_key, second.origin_key)

    def test_extension_owner_ignores_internal_module_path(self):
        self.assertEqual(
            module_owner_key("bl_ext.user_default.sample.ui.panels"),
            "bl_ext.user_default.sample",
        )


if __name__ == "__main__":
    unittest.main()
