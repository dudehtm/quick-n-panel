"""Factory-startup lifecycle test that does not touch the user's sidecar."""

import sys
from pathlib import Path
import tempfile

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))


TEST_CATEGORY = "Edit"


class QNPLIFECYCLE_PT_probe(bpy.types.Panel):
    bl_idname = "QNPLIFECYCLE_PT_probe"
    bl_label = "Lifecycle Probe"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = TEST_CATEGORY

    def draw(self, _context):
        self.layout.label(text="Probe")


def _new_addon_record():
    addon = bpy.context.preferences.addons.new()
    addon.module = "quick_n_panel"
    return addon


def _test_direct_categories(scanner):
    if bpy.app.background:
        return
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            window_region = next(
                (region for region in area.regions if region.type == "WINDOW"),
                None,
            )
            if window_region is None:
                continue
            with bpy.context.temp_override(window=window, area=area, region=window_region):
                categories = scanner.available_direct_categories(bpy.context)
                assert categories == (
                    "View",
                    "Tool",
                    "Edit",
                    "Item",
                ), categories
            return
    raise AssertionError("No 3D View was available for direct-category testing")


def _assert_configuration(preferences, target_key):
    assert preferences.compact_popup_width == 611
    assert preferences.groups.get("lifecycle_group") is not None
    assert preferences.targets.get(target_key).display_name == "Restored Probe"
    assert preferences.targets.get(target_key).group_id == "lifecycle_group"
    assert preferences.favorites.get(target_key) is not None


def _test_category_member_management(preferences, target, group):
    dummy_key = "VIEW_3D|UI|Lifecycle Dummy"
    dummy = preferences.targets.add()
    dummy.name = dummy_key
    dummy.native_key = dummy_key
    dummy.native_category = "Lifecycle Dummy"
    dummy.group_id = group.group_id
    dummy.group_order = 1
    target.group_order = 0

    result = bpy.ops.quick_n_panel.move_target_in_group(
        target_key=dummy_key,
        direction=-1,
    )
    assert result == {"FINISHED"}, result
    ordered = sorted(
        (item for item in preferences.targets if item.group_id == group.group_id),
        key=lambda item: item.group_order,
    )
    assert [item.native_key for item in ordered] == [dummy_key, target.native_key]

    result = bpy.ops.quick_n_panel.remove_target_from_group(target_key=dummy_key)
    assert result == {"FINISHED"}, result
    assert dummy.group_id == ""
    assert dummy.group_order == 0
    assert target.group_order == 0


def _test_icon_preview_recovery(icons):
    icon_value = icons.bundled_icon_value("QNP_Favorites")
    if bpy.app.background:
        preview = icons._load_styled_preview(
            "__lifecycle_preview__",
            str(icons._bundled_icon_paths["QNP_Favorites"]),
            "WHITE",
            (1.0, 1.0, 1.0),
        )
    else:
        assert icon_value > 0
        preview = next(
            preview
            for preview in icons._custom_previews.values()
            if preview.icon_id == icon_value
        )
    assert tuple(preview.icon_size) == (96, 96)
    assert tuple(preview.image_size) == (96, 96)

    previous_collection = icons._custom_previews
    icons.refresh_icon_previews()
    assert icons._custom_previews is not previous_collection
    assert any(
        collection is previous_collection
        for collection in icons._retired_preview_collections
    )
    if not bpy.app.background:
        assert icons.bundled_icon_value("QNP_Favorites") > 0


def main():
    from quick_n_panel import keymap, persistence, registration
    from quick_n_panel.core import icons, scanner
    from quick_n_panel.preferences import get_preferences

    original_sidecar_path = persistence.sidecar_path
    bpy.utils.register_class(QNPLIFECYCLE_PT_probe)
    try:
        with tempfile.TemporaryDirectory() as directory:
            test_sidecar = Path(directory) / persistence.SIDECAR_FILENAME
            persistence.sidecar_path = lambda *, create=False: test_sidecar

            addon = _new_addon_record()
            registration.register_addon()
            preferences = get_preferences(bpy.context)
            assert preferences is not None
            assert preferences.starter_recents_pending
            assert preferences.compact_popup_width == 400
            assert preferences.icon_color_mode == "ORIGINAL"
            assert "panel" in bpy.types.UILayout.bl_rna.functions
            assert hasattr(bpy.types.WindowManager, "qnp_all_tabs_expanded")
            registered_ids = {
                getattr(cls, "bl_idname", "") for cls in registration._registered_classes
            }
            assert "quick_n_panel.remove_target_from_group" in registered_ids
            assert len(keymap._addon_keymaps) == 1
            assert keymap._addon_keymaps[0][1].idname == keymap.OPERATOR_ID
            _test_icon_preview_recovery(icons)
            _test_direct_categories(scanner)

            target_key = f"VIEW_3D|UI|{TEST_CATEGORY}"
            target = preferences.targets.get(target_key)
            assert target is not None

            custom_group = preferences.groups.add()
            custom_group.name = "lifecycle_group"
            custom_group.group_id = "lifecycle_group"
            custom_group.display_name = "Lifecycle Group"
            result = bpy.ops.quick_n_panel.add_target_to_group(
                group_id=custom_group.group_id,
                target_key=target.native_key,
            )
            assert result == {"FINISHED"}, result
            target.display_name = "Restored Probe"

            favorite = preferences.favorites.add()
            favorite.name = target_key
            favorite.target_key = target_key
            _test_category_member_management(preferences, target, custom_group)
            preferences.compact_popup_width = 611

            # Extension updates unregister and register without removing the add-on record.
            registration.unregister_addon()
            assert not keymap._addon_keymaps
            assert not hasattr(bpy.types.WindowManager, "qnp_all_tabs_expanded")
            assert icons._custom_previews is None
            assert icons._accent_previews is None
            assert not icons._retired_preview_collections
            assert not icons._preview_cleanup_timer_registered
            assert not icons._preview_cleanup_waiting_for_redraw
            assert test_sidecar.is_file()
            registration.register_addon()
            updated = get_preferences(bpy.context)
            assert updated is not None
            _assert_configuration(updated, target_key)

            registration.unregister_addon()
            bpy.context.preferences.addons.remove(addon)

            addon = _new_addon_record()
            registration.register_addon()
            restored = get_preferences(bpy.context)
            assert restored is not None
            _assert_configuration(restored, target_key)

            registration.unregister_addon()
            bpy.context.preferences.addons.remove(addon)
    finally:
        if registration._is_registered:
            registration.unregister_addon()
        persistence.sidecar_path = original_sidecar_path
        bpy.utils.unregister_class(QNPLIFECYCLE_PT_probe)

    print("Quick N-panel lifecycle test: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        if not bpy.app.background:
            def quit_blender():
                bpy.ops.wm.quit_blender()
                return None

            bpy.app.timers.register(quit_blender, first_interval=0.0)
