import importlib
import sys
from types import ModuleType, SimpleNamespace
import unittest

from package_bootstrap import PROJECT_ROOT, ensure_source_package


ensure_source_package()


def install_fake_bpy():
    bpy = ModuleType("bpy")
    bpy_props = ModuleType("bpy.props")

    def property_factory(**_kwargs):
        return object()

    for name in (
        "BoolProperty",
        "CollectionProperty",
        "EnumProperty",
        "FloatProperty",
        "FloatVectorProperty",
        "IntProperty",
        "StringProperty",
    ):
        setattr(bpy_props, name, property_factory)

    class FakeRNA:
        pass

    class FakePanel(FakeRNA):
        pass

    bpy.types = SimpleNamespace(
        AddonPreferences=FakeRNA,
        Context=FakeRNA,
        Operator=FakeRNA,
        Panel=FakePanel,
        PropertyGroup=FakeRNA,
        Region=FakeRNA,
        UIList=FakeRNA,
        UI_UL_list=FakeRNA,
        WindowManager=FakeRNA,
    )
    bpy.props = bpy_props
    bpy.context = SimpleNamespace()
    bpy.utils = SimpleNamespace()

    bpy_app = ModuleType("bpy.app")
    bpy_handlers = ModuleType("bpy.app.handlers")
    bpy_handlers.load_post = []
    bpy_handlers.persistent = lambda function: function
    bpy_app.handlers = bpy_handlers
    bpy_app.version = (5, 2, 0)
    bpy.app = bpy_app

    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = bpy_props
    sys.modules["bpy.app"] = bpy_app
    sys.modules["bpy.app.handlers"] = bpy_handlers


class FakeCollection(list):
    def add(self):
        item = SimpleNamespace(name="", target_key="")
        self.append(item)
        return item

    def remove(self, index):
        del self[index]

    def move(self, source, destination):
        self.insert(destination, self.pop(source))


class ImportGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_fake_bpy()

    def test_all_registration_modules_import_without_cycles(self):
        registration = importlib.import_module("quick_n_panel.registration")
        persistence = importlib.import_module("quick_n_panel.persistence")
        preferences = importlib.import_module("quick_n_panel.preferences")
        properties = importlib.import_module("quick_n_panel.properties")

        self.assertEqual(len(registration.CLASSES), 41)
        identifiers = [
            getattr(cls, "bl_idname", cls.__name__)
            for cls in registration.CLASSES
        ]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn("QNP_PT_launcher_categories_popover", identifiers)
        self.assertIn("QNP_PT_launcher_library_popover", identifiers)
        self.assertIn("quick_n_panel.open_direct_category", identifiers)
        self.assertIn("quick_n_panel.export_configuration", identifiers)
        self.assertIn("quick_n_panel.import_configuration", identifiers)
        self.assertIn("QNP_UL_launcher_favorites", identifiers)
        self.assertIn("QNP_UL_launcher_favorite_config", identifiers)
        self.assertNotIn("quick_n_panel.capture_shortcut", identifiers)
        self.assertNotIn("quick_n_panel.show_categories", identifiers)
        self.assertNotIn("QNP_PT_launcher_shortcuts", identifiers)
        self.assertEqual(
            set(persistence.ROOT_FIELDS),
            set(preferences.QNP_Preferences.__annotations__)
            - {
                "groups",
                "targets",
                "favorites",
                "new_addons",
                "observed_addons",
            },
        )
        self.assertEqual(
            set(persistence.COLLECTION_FIELDS["groups"]),
            set(properties.QNP_PG_Group.__annotations__),
        )
        self.assertEqual(
            set(persistence.COLLECTION_FIELDS["targets"]),
            set(properties.QNP_PG_TargetSettings.__annotations__),
        )
        self.assertEqual(
            set(persistence.COLLECTION_FIELDS["favorites"]),
            set(properties.QNP_PG_Favorite.__annotations__),
        )
        self.assertEqual(
            set(persistence.COLLECTION_FIELDS["new_addons"]),
            set(properties.QNP_PG_NewAddon.__annotations__),
        )
        self.assertEqual(
            set(persistence.COLLECTION_FIELDS["observed_addons"]),
            set(properties.QNP_PG_ObservedAddon.__annotations__),
        )

    def test_scanner_detects_same_key_addon_reincarnation(self):
        scanner = importlib.import_module("quick_n_panel.core.scanner")

        class FakeAddon:
            def __init__(self, module, pointer):
                self.module = module
                self.pointer = pointer

            def as_pointer(self):
                return self.pointer

        addon = FakeAddon("bl_ext.user_default.sample", 10)
        context = SimpleNamespace(
            preferences=SimpleNamespace(addons=(addon,)),
        )
        scanner.invalidate_catalog()
        try:
            keys, incarnations = scanner._enabled_addon_state(context)
            self.assertEqual(keys, {"bl_ext.user_default.sample"})
            scanner._remember_addon_state(keys, incarnations)

            addon.pointer = 20
            keys, incarnations = scanner._enabled_addon_state(context)
            self.assertEqual(
                scanner._transitioned_addon_keys(keys, incarnations),
                {"bl_ext.user_default.sample"},
            )
            scanner._remember_addon_state(
                keys,
                incarnations,
                {"bl_ext.user_default.sample": (("SAMPLE_PT_main", object()),)},
            )
            self.assertEqual(
                scanner._transitioned_addon_keys(
                    keys,
                    incarnations,
                    {"bl_ext.user_default.sample": (("SAMPLE_PT_main", object()),)},
                ),
                {"bl_ext.user_default.sample"},
            )
        finally:
            scanner.invalidate_catalog()

    def test_catalog_snapshot_materializes_indexes(self):
        scanner = importlib.import_module("quick_n_panel.core.scanner")
        catalog = importlib.import_module("quick_n_panel.core.catalog")
        target = catalog.TargetDescriptor(
            native_key="sample",
            native_category="Sample",
            panels=(catalog.PanelDescriptor("SAMPLE_PT_main", "Main", "sample"),),
        )

        snapshot = scanner.CatalogSnapshot(targets=(target,))

        self.assertIs(snapshot.by_key, snapshot.by_key)
        self.assertIs(snapshot.by_key["sample"], target)
        self.assertEqual(snapshot.panel_count, 1)

    def test_refresh_catalog_returns_fresh_snapshot_before_global_state_checks(self):
        scanner = importlib.import_module("quick_n_panel.core.scanner")
        snapshot = scanner.CatalogSnapshot(
            targets=(),
            scanned_at=scanner.time.monotonic(),
        )
        original_snapshot = scanner._snapshot
        original_include = scanner._last_include_builtin
        original_preferences = scanner._preferences_or_none
        original_enabled = scanner._enabled_addon_state
        original_panels = scanner._panel_incarnation_state
        original_scan = scanner.scan_sidebar_targets
        scanner._snapshot = snapshot
        scanner._last_include_builtin = False
        scanner._preferences_or_none = lambda _context: SimpleNamespace(
            include_builtin_tabs=False
        )
        scanner._enabled_addon_state = lambda _context: self.fail(
            "fresh cache should return before addon enumeration"
        )
        scanner._panel_incarnation_state = lambda _keys: self.fail(
            "fresh cache should return before panel enumeration"
        )
        scanner.scan_sidebar_targets = lambda **_kwargs: self.fail(
            "fresh cache should return before scanning"
        )
        try:
            self.assertIs(scanner.refresh_catalog(SimpleNamespace()), snapshot)
        finally:
            scanner._snapshot = original_snapshot
            scanner._last_include_builtin = original_include
            scanner._preferences_or_none = original_preferences
            scanner._enabled_addon_state = original_enabled
            scanner._panel_incarnation_state = original_panels
            scanner.scan_sidebar_targets = original_scan

    def test_direct_category_availability_uses_shared_cache(self):
        scanner = importlib.import_module("quick_n_panel.core.scanner")
        catalog = importlib.import_module("quick_n_panel.core.catalog")
        target = catalog.TargetDescriptor(
            native_key="VIEW_3D|UI|Edit",
            native_category="Edit",
            panels=(catalog.PanelDescriptor("EDIT_PT_main", "Main", "sample"),),
        )
        context = SimpleNamespace(
            area=SimpleNamespace(type="VIEW_3D"),
            active_object=object(),
        )
        cache = {}
        calls = []
        original_direct = scanner.DIRECT_CATEGORIES
        original_visible = scanner._target_has_visible_root_panel
        scanner.DIRECT_CATEGORIES = ("Edit",)
        scanner._target_has_visible_root_panel = lambda *_args, **_kwargs: calls.append(
            True
        ) or True
        try:
            first = scanner.available_direct_categories(
                context,
                snapshot=scanner.CatalogSnapshot(targets=(target,)),
                availability_cache=cache,
            )
            second = scanner.available_direct_categories(
                context,
                snapshot=scanner.CatalogSnapshot(targets=(target,)),
                availability_cache=cache,
            )
        finally:
            scanner.DIRECT_CATEGORIES = original_direct
            scanner._target_has_visible_root_panel = original_visible

        self.assertEqual(first, ("Edit",))
        self.assertEqual(second, ("Edit",))
        self.assertEqual(len(calls), 1)

    def test_keymap_only_registers_and_unregisters_the_default_shortcut(self):
        keymap_module = importlib.import_module("quick_n_panel.keymap")
        calls = []
        removed = []
        keymap_item = object()

        class FakeItems:
            def new(self, *args, **kwargs):
                calls.append(("item", args, kwargs))
                return keymap_item

            def remove(self, item):
                removed.append(item)

        keymap = SimpleNamespace(keymap_items=FakeItems())

        class FakeKeymaps:
            def new(self, **kwargs):
                calls.append(("keymap", kwargs))
                return keymap

        original_context = keymap_module.bpy.context
        previous_keymaps = keymap_module._addon_keymaps[:]
        keymap_module._addon_keymaps.clear()
        keymap_module.bpy.context = SimpleNamespace(
            window_manager=SimpleNamespace(
                keyconfigs=SimpleNamespace(
                    addon=SimpleNamespace(keymaps=FakeKeymaps()),
                )
            )
        )
        try:
            keymap_module.register()
            self.assertEqual(keymap_module._addon_keymaps, [(keymap, keymap_item)])
            keymap_module.unregister()
        finally:
            keymap_module.bpy.context = original_context
            keymap_module._addon_keymaps[:] = previous_keymaps

        self.assertEqual(calls[0], ("keymap", {"name": "3D View", "space_type": "VIEW_3D"}))
        self.assertEqual(
            calls[1],
            (
                "item",
                (keymap_module.OPERATOR_ID, "F5", "PRESS"),
                {"ctrl": False, "shift": False, "alt": False},
            ),
        )
        self.assertEqual(removed, [keymap_item])
        self.assertEqual(keymap_module.CLASSES, ())
        for removed_feature in (
            "CAPTURE_OPERATOR_ID",
            "draw_preferences_keymap",
            "shortcut_conflicts",
            "shortcut_status",
            "_resolve_keymap_item",
            "_set_shortcut_event",
        ):
            self.assertFalse(hasattr(keymap_module, removed_feature), removed_feature)

    def test_default_shortcut_is_plain_f5(self):
        constants = importlib.import_module("quick_n_panel.constants")

        self.assertEqual(constants.DEFAULT_SHORTCUT_TYPE, "F5")
        self.assertFalse(constants.DEFAULT_SHORTCUT_CTRL)
        self.assertFalse(constants.DEFAULT_SHORTCUT_SHIFT)
        self.assertFalse(constants.DEFAULT_SHORTCUT_ALT)

    def test_new_install_uses_compact_original_icon_defaults(self):
        constants = importlib.import_module("quick_n_panel.constants")
        persistence = importlib.import_module("quick_n_panel.persistence")

        self.assertEqual(constants.DEFAULT_COMPACT_POPUP_WIDTH, 400)
        self.assertEqual(constants.DEFAULT_ICON_COLOR_MODE, "ORIGINAL")
        self.assertEqual(persistence._ROOT_DEFAULTS["compact_popup_width"], 400)
        self.assertEqual(persistence._ROOT_DEFAULTS["icon_color_mode"], "ORIGINAL")

    def test_invalid_preview_ids_are_treated_as_cache_misses(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")

        self.assertEqual(
            icons_module._preview_icon_id(SimpleNamespace(icon_id=0)),
            0,
        )
        self.assertEqual(
            icons_module._preview_icon_id(SimpleNamespace(icon_id=42)),
            42,
        )

    def test_favorite_lists_do_not_draw_default_filter_controls(self):
        lists_module = importlib.import_module("quick_n_panel.ui.lists")

        for list_class in (
            lists_module.QNP_UL_LauncherFavorites,
            lists_module.QNP_UL_FavoriteConfig,
        ):
            self.assertIsNone(list_class.draw_filter(None, None, None))
            self.assertEqual(
                list_class.filter_items(None, None, None, "favorites"),
                ([], []),
            )

    def test_experimental_startup_popovers_are_mutually_exclusive(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        preferences = SimpleNamespace(
            auto_open_library=True,
            auto_open_categories=True,
        )
        original_updated = preferences_module._preferences_updated
        updates = []
        preferences_module._preferences_updated = (
            lambda *_args: updates.append(True)
        )
        try:
            preferences_module._auto_open_panel_updated(preferences, None)
        finally:
            preferences_module._preferences_updated = original_updated

        self.assertTrue(preferences.auto_open_library)
        self.assertFalse(preferences.auto_open_categories)
        self.assertEqual(updates, [True])

    def test_f5_startup_popover_reuses_existing_panel(self):
        launcher_module = importlib.import_module("quick_n_panel.operators.launcher")
        bpy = importlib.import_module("bpy")

        class FakeTimers:
            def __init__(self):
                self.callback = None

            def register(self, callback, *, first_interval):
                self.callback = callback
                self.first_interval = first_interval

            def unregister(self, callback):
                if self.callback is callback:
                    self.callback = None

        timers = FakeTimers()
        calls = []
        original_timers = getattr(bpy.app, "timers", None)
        original_ops = getattr(bpy, "ops", None)
        bpy.app.timers = timers
        bpy.ops = SimpleNamespace(
            wm=SimpleNamespace(
                call_panel=lambda **kwargs: calls.append(kwargs) or {"FINISHED"}
            )
        )
        try:
            scheduled = launcher_module.schedule_auto_open_panel(
                SimpleNamespace(window=None, area=None),
                SimpleNamespace(auto_open_library=True, auto_open_categories=False),
            )
            self.assertTrue(scheduled)
            self.assertIsNotNone(timers.callback)
            self.assertIsNone(timers.callback())
        finally:
            launcher_module.cancel_pending_auto_open()
            bpy.app.timers = original_timers
            bpy.ops = original_ops

        self.assertEqual(
            calls,
            [{"name": "QNP_PT_launcher_library_popover", "keep_open": True}],
        )

    def test_bundled_icon_value_uses_cached_preview_id(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        original_values = dict(icons_module._bundled_icon_values)
        original_custom_value = icons_module.custom_icon_value
        icons_module._bundled_icon_values.clear()
        icons_module._bundled_icon_values["QNP_Test"] = 42
        icons_module.custom_icon_value = lambda _filepath: self.fail(
            "cached bundled icons must not resolve the file again"
        )
        try:
            self.assertEqual(icons_module.bundled_icon_value("QNP_Test"), 42)
        finally:
            icons_module.custom_icon_value = original_custom_value
            icons_module._bundled_icon_values.clear()
            icons_module._bundled_icon_values.update(original_values)

    def test_retired_previews_survive_a_redraw_cycle_before_cleanup(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        first = object()
        second = object()
        removed = []
        redraws = []
        original_retired = icons_module._retired_preview_collections[:]
        original_registered = icons_module._preview_cleanup_timer_registered
        original_waiting = icons_module._preview_cleanup_waiting_for_redraw
        original_remove = icons_module._remove_preview_collections
        original_redraw = icons_module._tag_redraw_all
        icons_module._retired_preview_collections[:] = [first, second]
        icons_module._preview_cleanup_timer_registered = True
        icons_module._preview_cleanup_waiting_for_redraw = True
        icons_module._remove_preview_collections = (
            lambda collections: removed.extend(collections)
        )
        icons_module._tag_redraw_all = lambda: redraws.append(True)
        try:
            self.assertEqual(icons_module._cleanup_retired_previews(), 0.05)
            self.assertEqual(removed, [])
            self.assertEqual(icons_module._cleanup_retired_previews(), None)
        finally:
            icons_module._retired_preview_collections[:] = original_retired
            icons_module._preview_cleanup_timer_registered = original_registered
            icons_module._preview_cleanup_waiting_for_redraw = original_waiting
            icons_module._remove_preview_collections = original_remove
            icons_module._tag_redraw_all = original_redraw

        self.assertEqual(removed, [first, second])
        self.assertEqual(redraws, [True, True])

    def test_library_preserves_manual_category_order(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        groups = (
            SimpleNamespace(group_id="empty", display_name="Empty"),
            SimpleNamespace(group_id="large", display_name="Large"),
            SimpleNamespace(group_id="small", display_name="Small"),
        )
        targets = (
            SimpleNamespace(
                native_key="C",
                group_id="large",
                group_order=1,
                display_name="Charlie",
                native_category="Charlie",
            ),
            SimpleNamespace(
                native_key="A",
                group_id="small",
                group_order=0,
                display_name="Alpha",
                native_category="Alpha",
            ),
            SimpleNamespace(
                native_key="B",
                group_id="large",
                group_order=0,
                display_name="Bravo",
                native_category="Bravo",
            ),
            SimpleNamespace(
                native_key="missing",
                group_id="large",
                group_order=2,
                display_name="Missing",
                native_category="Missing",
            ),
        )
        preferences = SimpleNamespace(groups=groups, targets=targets)

        available, grouped = popup_module._library_contents(
            preferences,
            {"A": object(), "B": object(), "C": object()},
        )

        self.assertEqual([target.native_key for target in available], ["A", "B", "C"])
        self.assertEqual(
            [group.group_id for group, _targets in grouped],
            ["empty", "large", "small"],
        )
        self.assertEqual(
            [target.native_key for target in grouped[1][1]],
            ["B", "C"],
        )

    def test_popup_category_add_keeps_memberships_in_other_categories(self):
        choices_module = importlib.import_module("quick_n_panel.operators.choices")
        groups_module = importlib.import_module("quick_n_panel.operators.groups")

        class FakeNamedCollection(list):
            def get(self, name):
                return next((item for item in self if item.name == name), None)

        destination = SimpleNamespace(name="destination", group_id="destination")
        targets = FakeNamedCollection(
            (
                SimpleNamespace(
                    name="A",
                    native_key="A",
                    native_category="Alpha",
                    display_name="Alpha",
                    group_id="destination",
                    group_order=2,
                    icon_name="PLUGIN",
                    icon_path="",
                    bundled_icon="NONE",
                ),
                SimpleNamespace(
                    name="B",
                    native_key="B",
                    native_category="Bravo",
                    display_name="Bravo",
                    group_id="other",
                    group_order=4,
                    icon_name="PLUGIN",
                    icon_path="",
                    bundled_icon="NONE",
                ),
                SimpleNamespace(
                    name="C",
                    native_key="C",
                    native_category="Charlie",
                    display_name="Charlie",
                    group_id="",
                    group_order=0,
                    icon_name="PLUGIN",
                    icon_path="",
                    bundled_icon="NONE",
                ),
            )
        )
        preferences = SimpleNamespace(
            groups=FakeNamedCollection((destination,)),
            targets=targets,
        )
        context = SimpleNamespace()
        snapshot = SimpleNamespace(by_key={target.native_key: target for target in targets})

        original_choices_preferences = choices_module.get_preferences
        original_refresh = choices_module.scanner.refresh_catalog
        original_groups_preferences = groups_module.get_preferences
        choices_module.get_preferences = lambda _context: preferences
        choices_module.scanner.refresh_catalog = lambda _context: snapshot
        groups_module.get_preferences = lambda _context: preferences
        try:
            all_items = choices_module.target_choices(None, context)
            items = choices_module.category_target_choices(
                SimpleNamespace(group_id="destination"),
                context,
            )
            operator = groups_module.QNP_OT_AddTargetToGroup()
            operator.group_id = "destination"
            operator.target_key = "B"
            result = operator.execute(context)
        finally:
            choices_module.get_preferences = original_choices_preferences
            choices_module.scanner.refresh_catalog = original_refresh
            groups_module.get_preferences = original_groups_preferences

        self.assertEqual([item[0] for item in all_items], ["A", "B", "C"])
        self.assertEqual([item[0] for item in items], ["B", "C"])
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(targets.get("B").group_id, "other")
        self.assertEqual(targets.get("B").group_order, 4)
        self.assertEqual(
            [
                target.native_key
                for target in groups_module.ordered_group_targets(
                    preferences,
                    "destination",
                )
            ],
            ["A", "B"],
        )
        self.assertEqual(
            [
                target.native_key
                for target in groups_module.ordered_group_targets(preferences, "other")
            ],
            ["B"],
        )

    def test_popup_category_draws_all_targets_without_overflow_controls(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        drawn = []
        labels = []

        class FakeLayout:
            scale_y = 1.0

            def box(self):
                return self

            def column(self, *, align):
                self.align = align
                return self

            def row(self, *, align=False):
                self.align = align
                return self

            def label(self, *, text, **_kwargs):
                labels.append(text)

            def separator(self, **_kwargs):
                pass

        targets = tuple(
            SimpleNamespace(native_key=key)
            for key in (
                "A",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "I",
                "J",
                "K",
                "L",
            )
        )
        group = SimpleNamespace(
            group_id="group",
            display_name="Group",
            icon_name="PLUGIN",
            icon_path="",
            bundled_icon="NONE",
        )
        original_resolve = popup_module.icons.resolve_icon
        original_add = popup_module._draw_add_target_to_group
        original_target = popup_module._draw_target_button
        popup_module.icons.resolve_icon = lambda *_args: ("PLUGIN", 0)
        popup_module._draw_add_target_to_group = lambda *_args, **_kwargs: None
        popup_module._draw_target_button = (
            lambda _parent, _context, _preferences, key, **kwargs: drawn.append(
                (key, kwargs)
            )
        )
        try:
            popup_module._draw_group(
                FakeLayout(),
                object(),
                object(),
                group,
                targets,
                can_add=True,
            )
        finally:
            popup_module.icons.resolve_icon = original_resolve
            popup_module._draw_add_target_to_group = original_add
            popup_module._draw_target_button = original_target

        self.assertEqual([key for key, _kwargs in drawn], list("ABCDEFGHIJKL"))
        self.assertEqual(
            [kwargs for _key, kwargs in drawn],
            [{"compact": True, "show_favorite": True}] * 12,
        )
        self.assertNotIn("more", " ".join(labels))

    def test_populated_categories_use_the_shortest_column(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")

        class FakeColumn:
            def __init__(self, index):
                self.index = index

        class FakeColumnsRow:
            def __init__(self):
                self.next_index = 0

            def column(self, *, align):
                column = FakeColumn(self.next_index)
                self.next_index += 1
                return column

        class FakeLayout:
            def split(self, *, factor, align):
                return FakeColumnsRow()

        populated = tuple(
            (
                SimpleNamespace(group_id=group_id),
                tuple(SimpleNamespace(native_key=f"{group_id}_{index}") for index in range(size)),
            )
            for group_id, size in (("three", 3), ("ten", 10), ("one_a", 1), ("one_b", 1))
        )
        drawn = []
        original_group = popup_module._draw_group
        popup_module._draw_group = (
            lambda parent, _context, _preferences, group, _targets, **_kwargs: drawn.append(
                (group.group_id, parent.index)
            )
        )
        try:
            popup_module._draw_populated_categories(
                FakeLayout(),
                object(),
                object(),
                populated,
                available_count=20,
            )
        finally:
            popup_module._draw_group = original_group

        self.assertEqual(
            drawn,
            [("three", 0), ("ten", 1), ("one_a", 0), ("one_b", 0)],
        )

    def test_empty_categories_start_collapsed_and_can_expand(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        props = []
        grid_options = []
        drawn_empty = []

        class FakeLayout:
            def label(self, *, text, **_kwargs):
                pass

            def row(self, *, align=False):
                return self

            def prop(self, _owner, property_name, **kwargs):
                props.append((property_name, kwargs))

            def separator(self, **_kwargs):
                pass

            def grid_flow(self, **kwargs):
                grid_options.append(kwargs)
                return self

        target = SimpleNamespace(native_key="A")
        populated_group = SimpleNamespace(group_id="populated")
        empty_group = SimpleNamespace(group_id="empty")
        grouped = ((populated_group, (target,)), (empty_group, ()))
        context = SimpleNamespace(
            window_manager=SimpleNamespace(qnp_empty_categories_expanded=False)
        )
        original_snapshot = popup_module.scanner.get_snapshot
        original_contents = popup_module._library_contents
        original_populated = popup_module._draw_populated_categories
        original_empty = popup_module._draw_empty_group
        popup_module.scanner.get_snapshot = lambda: SimpleNamespace(by_key={"A": target})
        popup_module._library_contents = lambda _preferences, _available_keys: (
            (target,),
            grouped,
        )
        popup_module._draw_populated_categories = lambda *_args, **_kwargs: None
        popup_module._draw_empty_group = (
            lambda _parent, group, **_kwargs: drawn_empty.append(group.group_id)
        )
        try:
            popup_module._draw_categories_grid(FakeLayout(), context, object())
            collapsed_props = list(props)
            context.window_manager.qnp_empty_categories_expanded = True
            popup_module._draw_categories_grid(FakeLayout(), context, object())
        finally:
            popup_module.scanner.get_snapshot = original_snapshot
            popup_module._library_contents = original_contents
            popup_module._draw_populated_categories = original_populated
            popup_module._draw_empty_group = original_empty

        self.assertEqual(collapsed_props[-1][0], "qnp_empty_categories_expanded")
        self.assertEqual(collapsed_props[-1][1]["text"], "Empty Categories (1)")
        self.assertEqual(collapsed_props[-1][1]["icon"], "TRIA_RIGHT")
        self.assertEqual(grid_options[-1]["columns"], 3)
        self.assertEqual(drawn_empty, ["empty"])

    def test_reset_popup_state_closes_empty_categories(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        context = SimpleNamespace(
            window_manager=SimpleNamespace(
                qnp_empty_categories_expanded=True,
                qnp_launcher_favorite_index=7,
            )
        )

        popup_module.reset_popup_state(context)

        self.assertFalse(context.window_manager.qnp_empty_categories_expanded)
        self.assertEqual(context.window_manager.qnp_launcher_favorite_index, 0)

    def test_launcher_favorites_use_a_scrollable_ten_row_list(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        template_lists = []

        class FakeLayout:
            enabled = True

            def box(self):
                return self

            def column(self, *, align):
                return self

            def row(self, *, align=False):
                return self

            def label(self, *, text, **_kwargs):
                pass

            def separator(self, **_kwargs):
                pass

            def operator(self, _identifier, **_kwargs):
                return SimpleNamespace()

            def template_list(self, *args, **kwargs):
                template_lists.append((args, kwargs))

        class FakeFavorites(list):
            pass

        favorites = FakeFavorites(
            SimpleNamespace(target_key=f"target_{index}") for index in range(30)
        )
        preferences = SimpleNamespace(favorites=favorites)
        context = SimpleNamespace(
            window_manager=SimpleNamespace(qnp_launcher_favorite_index=0)
        )
        original_icon = popup_module.icons.bundled_icon_value
        popup_module.icons.bundled_icon_value = lambda _name: 0
        try:
            popup_module._draw_favorites(FakeLayout(), context, preferences)
        finally:
            popup_module.icons.bundled_icon_value = original_icon

        self.assertEqual(len(template_lists), 1)
        args, kwargs = template_lists[0]
        self.assertEqual(args[:6], (
            "QNP_UL_launcher_favorites",
            "popup",
            preferences,
            "favorites",
            context.window_manager,
            "qnp_launcher_favorite_index",
        ))
        self.assertEqual(kwargs["rows"], 10)
        self.assertEqual(kwargs["maxrows"], 10)

    def test_favorite_configuration_uses_the_same_scrollable_row_count(self):
        favorites_ui = importlib.import_module("quick_n_panel.ui.sections.favorites")
        template_lists = []

        class FakeLayout:
            def label(self, *, text, **_kwargs):
                pass

            def template_list(self, *args, **kwargs):
                template_lists.append((args, kwargs))

            def separator(self, **_kwargs):
                pass

            def row(self, *, align=False):
                return self

            def operator(self, _identifier, **_kwargs):
                return SimpleNamespace()

        preferences = SimpleNamespace(
            favorites=[SimpleNamespace(target_key=f"target_{index}") for index in range(30)],
            favorite_index=0,
        )
        favorites_ui.draw(FakeLayout(), None, preferences)

        self.assertEqual(len(template_lists), 1)
        args, kwargs = template_lists[0]
        self.assertEqual(args[:6], (
            "QNP_UL_launcher_favorite_config",
            "configuration",
            preferences,
            "favorites",
            preferences,
            "favorite_index",
        ))
        self.assertEqual(kwargs["rows"], 10)
        self.assertEqual(kwargs["maxrows"], 10)

    def test_new_addon_block_shows_only_available_three_with_dismissal(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        labels = []
        drawn = []

        class FakeLayout:
            def separator(self, **_kwargs):
                pass

            def label(self, *, text, **_kwargs):
                labels.append(text)

        class FakeTargets(list):
            def get(self, target_key):
                return next(
                    (target for target in self if target.native_key == target_key),
                    None,
                )

        targets = FakeTargets(
            SimpleNamespace(
                native_key=f"target_{index}",
                hidden=False,
            )
            for index in range(4)
        )
        preferences = SimpleNamespace(targets=targets)
        entries = tuple(
            SimpleNamespace(
                target_key=f"target_{index}",
                addon_key=f"addon_{index}",
            )
            for index in range(4)
        )
        original_entries = popup_module.new_addon_entries
        original_snapshot = popup_module.scanner.get_snapshot
        original_button = popup_module._draw_target_button
        popup_module.new_addon_entries = lambda _preferences: entries
        popup_module.scanner.get_snapshot = lambda: SimpleNamespace(
            by_key={target.native_key: target for target in targets}
        )
        popup_module._draw_target_button = (
            lambda _parent, _context, _preferences, target_key, **kwargs: drawn.append(
                (target_key, kwargs)
            )
        )
        try:
            popup_module._draw_new_addons(FakeLayout(), SimpleNamespace(), preferences)
        finally:
            popup_module.new_addon_entries = original_entries
            popup_module.scanner.get_snapshot = original_snapshot
            popup_module._draw_target_button = original_button

        self.assertEqual(labels, ["New"])
        self.assertEqual(len(drawn), 3)
        self.assertEqual(drawn[0][0], "target_0")
        self.assertEqual(drawn[0][1]["compact"], True)
        self.assertEqual(drawn[0][1]["dismiss_addon_key"], "addon_0")

    def test_library_popover_draws_all_tabs_with_category_context(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        labels = []
        drawn = []

        class FakeLayout:
            def label(self, *, text, **_kwargs):
                labels.append(text)

            def grid_flow(self, **_kwargs):
                return self

        targets = tuple(
            SimpleNamespace(
                native_key=key,
                display_name=key,
                native_category=key,
                group_id="",
                group_order=0,
            )
            for key in ("A", "B")
        )
        preferences = SimpleNamespace(groups=(), targets=targets)
        context = SimpleNamespace()
        original_preferences = popup_module.get_preferences
        original_refresh = popup_module.scanner.refresh_catalog
        original_snapshot = popup_module.scanner.get_snapshot
        original_target = popup_module._draw_target_button
        refresh_calls = []
        popup_module.get_preferences = lambda _context: preferences
        popup_module.scanner.refresh_catalog = lambda _context: refresh_calls.append(True)
        popup_module.scanner.get_snapshot = lambda: SimpleNamespace(
            by_key={target.native_key: target for target in targets}
        )
        popup_module._draw_target_button = (
            lambda _parent, _context, _preferences, target_key, **kwargs: drawn.append(
                (target_key, kwargs)
            )
        )
        try:
            popup_module.draw_library_popover(FakeLayout(), context)
        finally:
            popup_module.get_preferences = original_preferences
            popup_module.scanner.refresh_catalog = original_refresh
            popup_module.scanner.get_snapshot = original_snapshot
            popup_module._draw_target_button = original_target

        self.assertEqual(labels, ["All Tabs (2)"])
        self.assertEqual(refresh_calls, [])
        self.assertEqual(
            [
                (
                    key,
                    {
                        name: value
                        for name, value in kwargs.items()
                        if name != "draw_state"
                    },
                )
                for key, kwargs in drawn
            ],
            [
                ("A", {"compact": True, "show_category_icon": True}),
                ("B", {"compact": True, "show_category_icon": True}),
            ],
        )
        self.assertTrue(all(kwargs.get("draw_state") for _key, kwargs in drawn))

    def test_launcher_draws_library_and_categories_popovers(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        popovers = []
        operators = []
        refresh_calls = []

        class FakeLayout:
            def separator(self, **_kwargs):
                pass

            def row(self, **_kwargs):
                return self

            def popover(self, **kwargs):
                popovers.append(kwargs)

            def operator(self, operator_id, **kwargs):
                operators.append((operator_id, kwargs))
                return SimpleNamespace()

        preferences = SimpleNamespace()
        original_preferences = popup_module.get_preferences
        original_refresh = popup_module.scanner.refresh_catalog
        original_search = popup_module._draw_search
        original_favorites = popup_module._draw_favorites
        original_direct = popup_module._draw_direct_categories
        popup_module.get_preferences = lambda _context: preferences
        popup_module.scanner.refresh_catalog = (
            lambda _context: refresh_calls.append(True)
        )
        popup_module._draw_search = lambda *_args: None
        popup_module._draw_favorites = lambda *_args: None
        popup_module._draw_direct_categories = lambda *_args, **_kwargs: False
        try:
            popup_module.draw_launcher_popup(FakeLayout(), SimpleNamespace())
        finally:
            popup_module.get_preferences = original_preferences
            popup_module.scanner.refresh_catalog = original_refresh
            popup_module._draw_search = original_search
            popup_module._draw_favorites = original_favorites
            popup_module._draw_direct_categories = original_direct

        self.assertEqual(
            [popover["panel"] for popover in popovers],
            ["QNP_PT_launcher_library_popover", "QNP_PT_launcher_categories_popover"],
        )
        self.assertEqual(operators[0][0], "quick_n_panel.open_configuration")
        self.assertEqual(refresh_calls, [])

    def test_all_tabs_category_icon_uses_group_and_unassigned_fallbacks(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")

        class FakeGroups(list):
            def get(self, group_id):
                return next((group for group in self if group.group_id == group_id), None)

        group = SimpleNamespace(
            group_id="group",
            icon_name="PLUGIN",
            icon_path="",
            bundled_icon="QNP_Modeling",
        )
        preferences = SimpleNamespace(groups=FakeGroups([group]))
        assigned = SimpleNamespace(group_id="group")
        unassigned = SimpleNamespace(group_id="")
        original_resolve = popup_module.icons.resolve_icon
        popup_module.icons.resolve_icon = lambda *_args: ("PLUGIN", 42)
        try:
            assigned_icon = popup_module._category_icon_for_target(preferences, assigned)
            unassigned_icon = popup_module._category_icon_for_target(preferences, unassigned)
        finally:
            popup_module.icons.resolve_icon = original_resolve

        self.assertEqual(assigned_icon, ("PLUGIN", 42))
        self.assertEqual(unassigned_icon, ("OUTLINER_COLLECTION", 0))

    def test_group_operator_moves_directionally_and_normalizes_order(self):
        groups_module = importlib.import_module("quick_n_panel.operators.groups")

        class FakeNamedCollection(list):
            def get(self, name):
                return next((item for item in self if item.native_key == name), None)

        targets = FakeNamedCollection(
            SimpleNamespace(
                native_key=key,
                native_category=key,
                display_name=key,
                group_id="group",
                group_order=index * 10,
            )
            for index, key in enumerate(("A", "B", "C"))
        )
        preferences = SimpleNamespace(targets=targets)
        original_get_preferences = groups_module.get_preferences
        groups_module.get_preferences = lambda _context: preferences
        try:
            operator = groups_module.QNP_OT_MoveTargetInGroup()
            operator.target_key = "C"
            operator.direction = -1
            self.assertEqual(operator.execute(None), {"FINISHED"})
        finally:
            groups_module.get_preferences = original_get_preferences

        ordered = sorted(targets, key=lambda target: target.group_order)
        self.assertEqual([target.native_key for target in ordered], ["A", "C", "B"])
        self.assertEqual([target.group_order for target in ordered], [0, 1, 2])

    def test_remove_target_from_group_unassigns_and_closes_order_gap(self):
        groups_module = importlib.import_module("quick_n_panel.operators.groups")

        class FakeNamedCollection(list):
            def get(self, name):
                return next((item for item in self if item.native_key == name), None)

        targets = FakeNamedCollection(
            (
                SimpleNamespace(
                    native_key="A",
                    native_category="A",
                    display_name="A",
                    group_id="group",
                    group_order=0,
                ),
                SimpleNamespace(
                    native_key="B",
                    native_category="B",
                    display_name="B",
                    group_id="group",
                    group_order=1,
                ),
                SimpleNamespace(
                    native_key="C",
                    native_category="C",
                    display_name="C",
                    group_id="group",
                    group_order=2,
                ),
            )
        )
        preferences = SimpleNamespace(targets=targets)
        original_get_preferences = groups_module.get_preferences
        groups_module.get_preferences = lambda _context: preferences
        try:
            operator = groups_module.QNP_OT_RemoveTargetFromGroup()
            operator.target_key = "B"
            self.assertEqual(operator.execute(None), {"FINISHED"})
        finally:
            groups_module.get_preferences = original_get_preferences

        self.assertEqual(targets.get("B").group_id, "")
        self.assertEqual(targets.get("B").group_order, 0)
        self.assertEqual(targets.get("C").group_order, 1)

    def test_category_details_draw_compact_member_management_rows(self):
        groups_ui = importlib.import_module("quick_n_panel.ui.sections.groups")
        operators = []
        labels = []

        class FakeLayout:
            enabled = True
            alert = False
            alignment = ""
            ui_units_x = 0.0

            def row(self, *, align=False):
                self.align = align
                return self

            def column(self, *, align=False):
                self.align = align
                return self

            def separator(self, **_kwargs):
                pass

            def label(self, *, text, **_kwargs):
                labels.append(text)

            def operator(self, identifier, **_kwargs):
                properties = SimpleNamespace()
                operators.append((identifier, properties))
                return properties

        targets = (
            SimpleNamespace(
                native_key=key,
                native_category=key,
                display_name=key,
                group_id="group",
                group_order=index,
                icon_name="PLUGIN",
                icon_path="",
                bundled_icon="NONE",
            )
            for index, key in enumerate(("A", "B"))
        )
        preferences = SimpleNamespace(targets=tuple(targets), favorites=())
        group = SimpleNamespace(group_id="group")
        original_exists = groups_ui.scanner.target_exists
        original_resolve = groups_ui.icons.resolve_icon
        groups_ui.scanner.target_exists = lambda _key: True
        groups_ui.icons.resolve_icon = lambda *_args: ("PLUGIN", 0)
        try:
            groups_ui._draw_group_targets(FakeLayout(), None, preferences, group)
        finally:
            groups_ui.scanner.target_exists = original_exists
            groups_ui.icons.resolve_icon = original_resolve

        identifiers = [identifier for identifier, _properties in operators]
        self.assertEqual(identifiers.count("quick_n_panel.add_target_to_group"), 1)
        self.assertEqual(identifiers.count("quick_n_panel.open_target"), 2)
        self.assertEqual(identifiers.count("quick_n_panel.toggle_favorite"), 2)
        self.assertEqual(identifiers.count("quick_n_panel.move_target_in_group"), 4)
        self.assertEqual(identifiers.count("quick_n_panel.remove_target_from_group"), 2)
        self.assertIn("Tabs (2)", labels)

    def test_library_uses_collapsed_panel_details_without_order_arrows(self):
        library_module = importlib.import_module("quick_n_panel.ui.sections.library")
        operators = []
        panels = []
        labels = []

        class FakeLayout:
            enabled = True

            def box(self):
                return self

            def row(self, *, align):
                self.align = align
                return self

            def label(self, *, text, **_kwargs):
                labels.append(text)

            def prop(self, *_args, **_kwargs):
                pass

            def template_icon_view(self, *_args, **_kwargs):
                pass

            def operator(self, identifier, **_kwargs):
                operators.append(identifier)
                return SimpleNamespace()

            def panel(self, identifier, *, default_closed):
                panels.append((identifier, default_closed))
                return self, None

        class FakeGroups(list):
            def get(self, group_id):
                return next((group for group in self if group.group_id == group_id), None)

        target = SimpleNamespace(
            native_key="target",
            native_category="Target",
            group_id="group",
            panel_labels="First\nSecond",
        )
        preferences = SimpleNamespace(
            groups=FakeGroups((SimpleNamespace(group_id="group", display_name="Group"),))
        )
        original_exists = library_module.scanner.target_exists
        original_icons = library_module._draw_external_icon_controls
        library_module.scanner.target_exists = lambda _key: True
        library_module._draw_external_icon_controls = lambda *_args: None
        try:
            library_module._draw_target_details(FakeLayout(), preferences, target)
        finally:
            library_module.scanner.target_exists = original_exists
            library_module._draw_external_icon_controls = original_icons

        self.assertNotIn("quick_n_panel.move_target_in_group", operators)
        self.assertEqual(panels, [("QNP_detected_panels", True)])
        self.assertIn("Category: Group", labels)
        self.assertIn("Detected Panels (2)", labels)

    def test_direct_categories_keep_requested_order_and_hide_missing_entries(self):
        scanner_module = importlib.import_module("quick_n_panel.core.scanner")
        edit_target = object()
        snapshot = SimpleNamespace(by_key={"VIEW_3D|UI|Edit": edit_target})
        context = SimpleNamespace(
            area=SimpleNamespace(type="VIEW_3D"),
            active_object=object(),
        )

        original_refresh = scanner_module.refresh_catalog
        original_native = scanner_module._native_direct_category_available
        original_visible = scanner_module._target_has_visible_root_panel
        scanner_module.refresh_catalog = lambda _context: snapshot
        scanner_module._native_direct_category_available = (
            lambda category, _context: category == "View"
        )
        scanner_module._target_has_visible_root_panel = (
            lambda target, _context, **_kwargs: target is edit_target
        )
        try:
            categories = scanner_module.available_direct_categories(context)
            context.active_object = None
            without_object = scanner_module.available_direct_categories(context)
        finally:
            scanner_module.refresh_catalog = original_refresh
            scanner_module._native_direct_category_available = original_native
            scanner_module._target_has_visible_root_panel = original_visible

        self.assertEqual(categories, ("View", "Edit", "Item"))
        self.assertEqual(without_object, ("View", "Edit"))

    def test_direct_category_row_draws_only_available_text_buttons(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")

        class FakeRow:
            def __init__(self):
                self.scale_y = 1.0
                self.buttons = []

            def operator(self, identifier, *, text):
                properties = SimpleNamespace(category="")
                self.buttons.append((identifier, text, properties))
                return properties

        class FakeLayout:
            def __init__(self):
                self.rows = []

            def row(self, *, align):
                row = FakeRow()
                row.align = align
                self.rows.append(row)
                return row

        layout = FakeLayout()
        original_available = popup_module.scanner.available_direct_categories
        popup_module.scanner.available_direct_categories = (
            lambda _context: ("View", "Edit", "Item")
        )
        try:
            drawn = popup_module._draw_direct_categories(layout, object())
        finally:
            popup_module.scanner.available_direct_categories = original_available

        self.assertTrue(drawn)
        self.assertEqual(len(layout.rows), 1)
        self.assertEqual(
            [(identifier, text) for identifier, text, _properties in layout.rows[0].buttons],
            [
                ("quick_n_panel.open_direct_category", "View"),
                ("quick_n_panel.open_direct_category", "Edit"),
                ("quick_n_panel.open_direct_category", "Item"),
            ],
        )
        self.assertEqual(
            [properties.category for _identifier, _text, properties in layout.rows[0].buttons],
            ["View", "Edit", "Item"],
        )

    def test_direct_open_records_available_target_and_retires_starter_recents(self):
        navigation_module = importlib.import_module("quick_n_panel.core.navigation")
        target_key = "VIEW_3D|UI|Edit"
        target = SimpleNamespace(
            name=target_key,
            native_key=target_key,
            open_count=0,
            first_opened_at="",
            last_opened_at="",
        )
        starter = SimpleNamespace(
            name="starter",
            native_key="starter",
            open_count=0,
            first_opened_at="",
            last_opened_at="10.000000",
        )

        class FakeTargets(list):
            def get(self, name):
                return next((item for item in self if item.name == name), None)

        preferences = SimpleNamespace(
            targets=FakeTargets((target, starter)),
            last_target_key="",
            last_observed_target_key="",
        )
        original_activate = navigation_module.activate_category
        original_get_preferences = navigation_module.get_preferences
        original_exists = navigation_module.scanner.target_exists
        navigation_module.activate_category = lambda _context, _category: (
            navigation_module.NavigationResult(True)
        )
        navigation_module.get_preferences = lambda _context: preferences
        navigation_module.scanner.target_exists = lambda key: key == target_key
        try:
            result = navigation_module.open_direct_category(SimpleNamespace(), "Edit")
        finally:
            navigation_module.activate_category = original_activate
            navigation_module.get_preferences = original_get_preferences
            navigation_module.scanner.target_exists = original_exists

        self.assertTrue(result.success)
        self.assertEqual(target.open_count, 1)
        self.assertTrue(target.last_opened_at)
        self.assertFalse(starter.last_opened_at)

    def test_sidebar_activation_can_retry_after_first_redraw(self):
        navigation_module = importlib.import_module("quick_n_panel.core.navigation")
        callbacks = []

        class FakeTimers:
            def register(self, callback, first_interval=0.0):
                self.first_interval = first_interval
                callbacks.append(callback)

        class FakeRegion:
            def __init__(self):
                self.attempts = 0
                self.value = ""
                self.redraws = 0

            @property
            def active_panel_category(self):
                return self.value

            @active_panel_category.setter
            def active_panel_category(self, value):
                self.attempts += 1
                if self.attempts == 1:
                    raise AttributeError("temporarily read-only")
                self.value = value

            def tag_redraw(self):
                self.redraws += 1

        area = SimpleNamespace(
            spaces=SimpleNamespace(active=SimpleNamespace(show_region_ui=False)),
            redraws=0,
        )
        area.tag_redraw = lambda: setattr(area, "redraws", area.redraws + 1)
        region = FakeRegion()
        original_app = navigation_module.bpy.app
        navigation_module.bpy.app = SimpleNamespace(timers=FakeTimers())
        try:
            self.assertTrue(
                navigation_module._schedule_category_activation(area, region, "Tools")
            )
            self.assertEqual(callbacks[0](), 0.05)
            self.assertIsNone(callbacks[0]())
        finally:
            navigation_module.bpy.app = original_app

        self.assertEqual(region.value, "Tools")
        self.assertTrue(area.spaces.active.show_region_ui)
        self.assertEqual((region.redraws, area.redraws), (1, 1))

    def test_sidebar_activation_timer_is_cancelled_during_cleanup(self):
        navigation_module = importlib.import_module("quick_n_panel.core.navigation")
        callbacks = []

        class FakeTimers:
            def register(self, callback, first_interval=0.0):
                callbacks.append(callback)

            def is_registered(self, callback):
                return callback in callbacks

            def unregister(self, callback):
                callbacks.remove(callback)

        area = SimpleNamespace(
            spaces=SimpleNamespace(active=SimpleNamespace(show_region_ui=False)),
            regions=[],
        )
        region = SimpleNamespace()
        original_app = navigation_module.bpy.app
        navigation_module.bpy.app = SimpleNamespace(timers=FakeTimers())
        try:
            self.assertTrue(
                navigation_module._schedule_category_activation(area, region, "Tools")
            )
            self.assertEqual(len(callbacks), 1)
            navigation_module.cancel_pending_activations()
        finally:
            navigation_module.bpy.app = original_app

        self.assertEqual(callbacks, [])

    def test_reported_search_operators_return_modal_state(self):
        launcher_module = importlib.import_module("quick_n_panel.operators.launcher")
        groups_module = importlib.import_module("quick_n_panel.operators.groups")
        invoked = []
        context = SimpleNamespace(
            window_manager=SimpleNamespace(
                invoke_search_popup=lambda operator: invoked.append(operator)
            )
        )

        original_refresh = launcher_module.scanner.refresh_catalog
        original_items = launcher_module._search_target_items
        launcher_module.scanner.refresh_catalog = lambda _context, **_kwargs: None
        launcher_module._search_target_items = (
            lambda _operator, _context, **_kwargs: [("target",)]
        )
        try:
            search_result = launcher_module.QNP_OT_SearchTargets().invoke(context, None)
            group_result = groups_module.QNP_OT_AssignTargetGroup().invoke(context, None)
        finally:
            launcher_module.scanner.refresh_catalog = original_refresh
            launcher_module._search_target_items = original_items

        self.assertEqual(search_result, {"RUNNING_MODAL"})
        self.assertEqual(group_result, {"RUNNING_MODAL"})
        self.assertEqual(len(invoked), 2)

    def test_default_groups_are_created_only_once(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")

        class FakeGroups(list):
            def get(self, name):
                return next((group for group in self if group.name == name), None)

            def add(self):
                group = SimpleNamespace(
                    name="",
                    group_id="",
                    display_name="",
                    icon_name="PLUGIN",
                )
                self.append(group)
                return group

        preferences = SimpleNamespace(
            groups=FakeGroups(),
            default_groups_initialized=False,
        )

        preferences_module.ensure_default_groups(preferences)
        first_ids = [group.group_id for group in preferences.groups]
        preferences_module.ensure_default_groups(preferences)

        self.assertEqual(len(preferences.groups), 6)
        self.assertEqual(first_ids, [group.group_id for group in preferences.groups])

    def test_favorite_migration_is_ordered_unique_and_one_time(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        preferences = SimpleNamespace(
            favorites=FakeCollection(),
            favorite_index=0,
            favorites_schema_version=0,
            favorite_1="A",
            favorite_2="",
            favorite_3="A",
        )

        preferences_module.ensure_favorites(preferences)
        self.assertEqual(preferences_module.favorite_keys(preferences), ("A",))
        self.assertEqual(preferences.favorites_schema_version, 1)

        preferences.favorites.clear()
        preferences_module.ensure_favorites(preferences)
        self.assertEqual(preferences_module.favorite_keys(preferences), ())

    def test_favorite_merge_deduplicates_without_a_small_ui_limit(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        merged = preferences_module._merge_favorite_keys(
            ("A", "B", "A", ""),
            tuple("CDEFGHIJKLMNOPQRSTUVWXYZ"),
        )

        self.assertEqual(merged, tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

    def test_favorite_operators_append_swap_move_remove_beyond_ten(self):
        favorites_module = importlib.import_module("quick_n_panel.operators.favorites")
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        preferences = SimpleNamespace(
            favorites=FakeCollection(),
            favorite_index=0,
        )
        original_get_preferences = favorites_module.get_preferences
        favorites_module.get_preferences = lambda _context: preferences
        try:
            for target_key in "ABCDEFGHIJKLMNOPQRST":
                operator = favorites_module.QNP_OT_AssignFavorite()
                operator.index = -1
                operator.target_key = target_key
                self.assertEqual(operator.execute(None), {"FINISHED"})

            self.assertEqual(len(preferences.favorites), 20)

            swap = favorites_module.QNP_OT_AssignFavorite()
            swap.index = 0
            swap.target_key = "B"
            self.assertEqual(swap.execute(None), {"FINISHED"})
            self.assertEqual(preferences_module.favorite_keys(preferences)[:2], ("B", "A"))

            move = favorites_module.QNP_OT_MoveFavorite()
            move.index = 0
            move.direction = 1
            self.assertEqual(move.execute(None), {"FINISHED"})
            self.assertEqual(preferences_module.favorite_keys(preferences)[:2], ("A", "B"))

            remove = favorites_module.QNP_OT_ClearFavorite()
            remove.index = 0
            self.assertEqual(remove.execute(None), {"FINISHED"})
            self.assertEqual(preferences_module.favorite_keys(preferences)[0], "B")

            toggle = favorites_module.QNP_OT_ToggleFavorite()
            toggle.target_key = "U"
            self.assertEqual(toggle.execute(None), {"FINISHED"})

            toggle_existing = favorites_module.QNP_OT_ToggleFavorite()
            toggle_existing.target_key = "B"
            self.assertEqual(toggle_existing.execute(None), {"FINISHED"})
            self.assertNotIn("B", preferences_module.favorite_keys(preferences))

            refill = favorites_module.QNP_OT_ToggleFavorite()
            refill.target_key = "V"
            self.assertEqual(refill.execute(None), {"FINISHED"})

            beyond_ten = favorites_module.QNP_OT_ToggleFavorite()
            beyond_ten.target_key = "W"
            self.assertEqual(beyond_ten.execute(None), {"FINISHED"})
            self.assertGreater(len(preferences.favorites), 20)
        finally:
            favorites_module.get_preferences = original_get_preferences

    def test_activity_history_preserves_legacy_recent_target(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        target = SimpleNamespace(
            name="target",
            native_key="target",
            open_count=0,
            first_opened_at="",
            last_opened_at="",
        )

        class FakeTargets(list):
            def get(self, name):
                return next((item for item in self if item.name == name), None)

        preferences = SimpleNamespace(
            targets=FakeTargets((target,)),
            last_target_key="target",
            last_observed_target_key="",
            activity_schema_version=0,
        )
        preferences_module.ensure_activity_history(preferences)

        self.assertEqual(target.open_count, 1)
        self.assertGreater(float(target.first_opened_at), 0.0)
        self.assertEqual(target.first_opened_at, target.last_opened_at)
        self.assertEqual(preferences.last_observed_target_key, "target")

    def test_starter_recents_are_replaced_by_first_real_open(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        scanner_module = importlib.import_module("quick_n_panel.core.scanner")

        class FakeTargets(list):
            def get(self, name):
                return next((item for item in self if item.name == name), None)

        targets = FakeTargets(
            SimpleNamespace(
                name=key,
                native_key=key,
                hidden=False,
                open_count=0,
                first_opened_at="",
                last_opened_at="",
            )
            for key in ("A", "B", "C", "D")
        )
        preferences = SimpleNamespace(
            targets=targets,
            starter_recents_pending=True,
            last_target_key="",
            last_observed_target_key="",
        )
        snapshot = SimpleNamespace(
            targets=tuple(SimpleNamespace(native_key=key) for key in ("A", "B", "C", "D"))
        )
        original_available = scanner_module.target_is_context_available
        scanner_module.target_is_context_available = lambda _key, _context: True
        try:
            seeded = preferences_module.ensure_starter_recents(
                preferences,
                object(),
                snapshot,
                sample=lambda candidates, count: candidates[-count:],
                timestamp=100.0,
            )
        finally:
            scanner_module.target_is_context_available = original_available

        self.assertTrue(seeded)
        self.assertFalse(preferences.starter_recents_pending)
        self.assertEqual(
            [target.native_key for target in targets if target.last_opened_at],
            ["B", "C", "D"],
        )
        self.assertTrue(all(target.open_count == 0 for target in targets))

        preferences_module.record_target_open(preferences, "A", timestamp=200.0)

        self.assertEqual(
            [target.native_key for target in targets if target.last_opened_at],
            ["A"],
        )
        self.assertEqual(targets.get("A").open_count, 1)

    def test_manual_recent_capture_does_not_double_count_same_tab(self):
        navigation_module = importlib.import_module("quick_n_panel.core.navigation")
        target_key = "VIEW_3D|UI|Hair"
        target = SimpleNamespace(
            name=target_key,
            native_key=target_key,
            open_count=0,
            first_opened_at="",
            last_opened_at="",
        )

        class FakeTargets(list):
            def get(self, name):
                return next((item for item in self if item.name == name), None)

        preferences = SimpleNamespace(
            targets=FakeTargets((target,)),
            last_target_key="",
            last_observed_target_key="",
        )
        context = SimpleNamespace(
            area=SimpleNamespace(
                type="VIEW_3D",
                regions=(SimpleNamespace(type="UI", active_panel_category="Hair"),),
            )
        )
        snapshot = SimpleNamespace(by_key={target_key: SimpleNamespace(native_key=target_key)})
        original_get_preferences = navigation_module.get_preferences
        navigation_module.get_preferences = lambda _context: preferences
        try:
            first = navigation_module.remember_active_target(context, snapshot)
            second = navigation_module.remember_active_target(context, snapshot)
        finally:
            navigation_module.get_preferences = original_get_preferences

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(target.open_count, 1)
        self.assertEqual(preferences.last_target_key, target_key)

    def test_native_search_result_uses_only_the_display_name(self):
        launcher_module = importlib.import_module("quick_n_panel.operators.launcher")
        target_key = "VIEW_3D|UI|Hair"
        target = SimpleNamespace(
            native_key=target_key,
            native_category="Hair",
            display_name="Hair Tools",
            hidden=False,
            panel_labels="Panel One|Panel Two",
            source_modules="sample.panels",
            group_id="group",
            icon_name="PLUGIN",
            icon_path="",
            bundled_icon="NONE",
        )
        preferences = SimpleNamespace(
            targets=(target,),
            favorites=(),
            last_target_key="",
            max_search_results=128,
        )
        snapshot = SimpleNamespace(by_key={target_key: target})
        original_get_preferences = launcher_module.get_preferences
        original_refresh = launcher_module.scanner.refresh_catalog
        launcher_module.get_preferences = lambda _context: preferences
        launcher_module.scanner.refresh_catalog = lambda _context: snapshot
        try:
            items = launcher_module._search_target_items(None, SimpleNamespace())
        finally:
            launcher_module.get_preferences = original_get_preferences
            launcher_module.scanner.refresh_catalog = original_refresh

        self.assertEqual(items[0][1], "Hair Tools")
        self.assertEqual(items[0][2], "Open the 'Hair' sidebar tab")
        self.assertNotIn("Panel One", items[0][1])

    def test_default_icon_migration_preserves_a_custom_blender_icon(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        modeling = SimpleNamespace(
            name="default_modeling",
            group_id="default_modeling",
            display_name="Modeling",
            icon_name="NODETREE",
            bundled_icon="NONE",
            icon_path="",
        )

        class FakeGroups(list):
            def get(self, name):
                return next((group for group in self if group.name == name), None)

        preferences = SimpleNamespace(
            groups=FakeGroups((modeling,)),
            default_groups_initialized=True,
            default_group_icons_initialized=False,
        )
        original_has_icon = icons_module.has_bundled_icon
        icons_module.has_bundled_icon = lambda _identifier: True
        try:
            preferences_module.ensure_default_groups(preferences)
        finally:
            icons_module.has_bundled_icon = original_has_icon

        self.assertEqual(modeling.bundled_icon, "NONE")

    def test_bundled_icon_numbers_are_stable_and_unique(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        identifiers = [path.stem for path in icons_module._bundled_icon_files()]
        numbers = [icons_module._stable_icon_number(identifier) for identifier in identifiers]

        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertTrue(all(0 < number < 2**24 for number in numbers))
        self.assertEqual(
            numbers,
            [icons_module._stable_icon_number(identifier) for identifier in identifiers],
        )

    def test_managed_png_validation_checks_complete_rgba_image(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        files = icons_module._bundled_icon_files()

        self.assertTrue(files)
        self.assertTrue(
            all(
                icons_module._is_managed_png_bytes(path.read_bytes())
                for path in files
            )
        )
        self.assertFalse(icons_module._is_managed_png_bytes(files[0].read_bytes()[:24]))

    def test_typoed_files_icon_identifier_migrates(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")

        self.assertEqual(
            icons_module.canonical_bundled_icon("QNP_FIles"),
            "QNP_Files",
        )

    def test_bundled_icon_migration_repairs_exact_and_rounded_legacy_values(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        identifiers = [path.stem for path in icons_module._bundled_icon_files()]
        first_identifier, second_identifier = identifiers[:2]

        class FakeOwner(dict):
            bundled_icon = "NONE"

        exact = FakeOwner(
            bundled_icon=icons_module._legacy_icon_number(first_identifier)
        )
        rounded = FakeOwner(
            bundled_icon=icons_module._float32_rounded_int(
                icons_module._legacy_icon_number(second_identifier)
            )
        )
        preferences = SimpleNamespace(
            groups=(exact,),
            targets=(rounded,),
            icon_enum_schema_version=0,
        )

        icons_module.migrate_bundled_icon_values(preferences)

        self.assertEqual(exact.bundled_icon, first_identifier)
        self.assertEqual(rounded.bundled_icon, second_identifier)
        self.assertEqual(
            preferences.icon_enum_schema_version,
            icons_module.ICON_ENUM_SCHEMA_VERSION,
        )

    def test_uniform_icon_styles_replace_rgb_and_preserve_transparency(self):
        icons_module = importlib.import_module("quick_n_panel.core.icons")
        pixels = [
            0.2,
            0.4,
            0.8,
            1.0,
            0.9,
            0.1,
            0.3,
            0.4,
            0.7,
            0.6,
            0.5,
            0.0,
        ]

        white = icons_module._style_pixels(
            pixels,
            "WHITE",
            (0.2, 0.3, 0.4),
        )
        custom = icons_module._style_pixels(
            pixels,
            "CUSTOM",
            (0.15, 0.5, 0.75),
        )

        self.assertEqual(white[:3], [1.0, 1.0, 1.0])
        self.assertEqual(white[4:7], [1.0, 1.0, 1.0])
        self.assertEqual(custom[:3], [0.15, 0.5, 0.75])
        self.assertEqual(custom[4:7], [0.15, 0.5, 0.75])
        self.assertEqual(white[3], 1.0)
        self.assertEqual(white[7], 0.4)
        self.assertEqual(white[8:], [0.0, 0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
