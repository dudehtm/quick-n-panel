"""Interactive/background smoke test for an installed Quick N-panel extension.

Run from a Blender 5.x installation after installing and enabling the extension:

    blender --background --python tests/blender/smoke_test.py

Run without --background to include the actual sidebar activation assertion.
"""

import importlib

import bpy


TEST_CATEGORY = "Quick N-panel Test Target"


class QNPTEST_PT_probe(bpy.types.Panel):
    bl_idname = "QNPTEST_PT_probe"
    bl_label = "Launcher Probe"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = TEST_CATEGORY

    def draw(self, _context):
        self.layout.label(text="Probe")


def addon_package_name():
    for addon in bpy.context.preferences.addons:
        if addon.module.rsplit(".", 1)[-1] == "quick_n_panel":
            operator = getattr(getattr(bpy.ops, "quick_n_panel", None), "show_launcher", None)
            if operator is not None:
                return addon.module
    raise AssertionError("Enable Quick N-panel before running this test")


def test_scan_and_recovery(package_name):
    scanner = importlib.import_module(f"{package_name}.core.scanner")
    preferences_module = importlib.import_module(f"{package_name}.preferences")

    bpy.utils.register_class(QNPTEST_PT_probe)
    try:
        snapshot = scanner.refresh_catalog(bpy.context, force=True)
        matches = [target for target in snapshot.targets if target.native_category == TEST_CATEGORY]
        assert len(matches) == 1, "The scanner did not group the test panel into one target"
        assert matches[0].panel_labels == ("Launcher Probe",)

        preferences = preferences_module.get_preferences(bpy.context)
        assert preferences.targets.get(matches[0].native_key) is not None
        target_key = matches[0].native_key

        if not bpy.app.background:
            test_navigation(package_name, target_key)
    finally:
        bpy.utils.unregister_class(QNPTEST_PT_probe)

    scanner.refresh_catalog(bpy.context, force=True)
    assert not scanner.target_exists(target_key), "Unregistered panel remained available"
    preferences = preferences_module.get_preferences(bpy.context)
    assert preferences.targets.get(target_key) is not None, "Missing target metadata was deleted"

    saved_target = preferences.targets.get(target_key)
    saved_target.display_name = "Recovered Probe"
    bpy.utils.register_class(QNPTEST_PT_probe)
    try:
        scanner.refresh_catalog(bpy.context, force=True)
        assert scanner.target_exists(target_key), "Re-registered panel was not recovered"
        assert preferences.targets.get(target_key).display_name == "Recovered Probe"
    finally:
        bpy.utils.unregister_class(QNPTEST_PT_probe)


def test_navigation(package_name, target_key):
    navigation = importlib.import_module(f"{package_name}.core.navigation")
    preferences_module = importlib.import_module(f"{package_name}.preferences")
    preferences = preferences_module.get_preferences(bpy.context)
    settings = preferences.targets.get(target_key)
    previous_count = settings.open_count

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            window_region = next(
                (region for region in area.regions if region.type == "WINDOW"),
                None,
            )
            ui_region = next(
                (region for region in area.regions if region.type == "UI"),
                None,
            )
            if window_region is None or ui_region is None:
                continue

            with bpy.context.temp_override(window=window, area=area, region=window_region):
                result = navigation.open_target(bpy.context, target_key)
                assert result.success, result.message
                assert area.spaces.active.show_region_ui
                assert ui_region.active_panel_category == TEST_CATEGORY
                assert preferences.last_target_key == target_key
                assert settings.open_count == previous_count + 1
                assert settings.first_opened_at
                assert settings.last_opened_at
                return

    raise AssertionError("No 3D View was available for navigation testing")


def main():
    package_name = addon_package_name()
    test_scan_and_recovery(package_name)
    print("Quick N-panel smoke test: OK")


if __name__ == "__main__":
    main()
