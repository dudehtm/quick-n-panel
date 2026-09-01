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

        self.assertEqual(len(registration.CLASSES), 35)
        identifiers = [
            getattr(cls, "bl_idname", cls.__name__)
            for cls in registration.CLASSES
        ]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn("QNP_PT_launcher_categories_popover", identifiers)
        self.assertIn("quick_n_panel.open_direct_category", identifiers)
        self.assertIn("quick_n_panel.export_configuration", identifiers)
        self.assertIn("quick_n_panel.import_configuration", identifiers)
        self.assertNotIn("quick_n_panel.capture_shortcut", identifiers)
        self.assertNotIn("quick_n_panel.show_categories", identifiers)
        self.assertNotIn("QNP_PT_launcher_shortcuts", identifiers)
        self.assertEqual(
            set(persistence.ROOT_FIELDS),
            set(preferences.QNP_Preferences.__annotations__) - {"groups", "targets", "favorites"},
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

    def test_library_orders_categories_by_available_target_count(self):
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
            ["large", "small", "empty"],
        )
        self.assertEqual(
            [target.native_key for target in grouped[0][1]],
            ["B", "C"],
        )

    def test_popup_category_add_excludes_members_and_appends_moved_tab(self):
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
        self.assertEqual(targets.get("B").group_id, "destination")
        self.assertEqual(targets.get("B").group_order, 3)

    def test_popup_categories_stay_compact_without_reorder_controls(self):
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
            for key in ("A", "B", "C", "D", "E", "F")
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

        self.assertEqual([key for key, _kwargs in drawn], ["A", "B", "C", "D", "E"])
        self.assertEqual([kwargs for _key, kwargs in drawn], [{"compact": True}] * 5)
        self.assertIn("+1 more", labels)

    def test_all_tabs_collapses_at_five_populated_categories(self):
        popup_module = importlib.import_module("quick_n_panel.ui.popup")
        expansion_states = []
        drawn_targets = []
        populated_count = 4

        class FakeLayout:
            def label(self, *, text, **_kwargs):
                pass

            def grid_flow(self, **_kwargs):
                return self

            def separator(self, **_kwargs):
                pass

            def row(self, *, align=False):
                self.align = align
                return self

            def prop(self, owner, property_name, **_kwargs):
                expansion_states.append(getattr(owner, property_name))

        available_target = SimpleNamespace(native_key="A")

        def library_contents(_preferences, _available_keys):
            grouped = tuple(
                (
                    SimpleNamespace(group_id=f"group_{index}"),
                    (available_target,),
                )
                for index in range(populated_count)
            )
            return (available_target,), grouped

        original_snapshot = popup_module.scanner.get_snapshot
        original_contents = popup_module._library_contents
        original_group = popup_module._draw_group
        original_target = popup_module._draw_target_button
        popup_module.scanner.get_snapshot = lambda: SimpleNamespace(
            by_key={"A": available_target}
        )
        popup_module._library_contents = library_contents
        popup_module._draw_group = lambda *_args, **_kwargs: None
        popup_module._draw_target_button = (
            lambda _parent, _context, _preferences, target_key, **_kwargs: (
                drawn_targets.append(target_key)
            )
        )
        context = SimpleNamespace(
            window_manager=SimpleNamespace(qnp_all_tabs_expanded=True)
        )
        try:
            popup_module.reset_all_tabs_expansion(context, object(), {"A": object()})
            popup_module._draw_categories_grid(FakeLayout(), context, object())
            populated_count = 5
            popup_module.reset_all_tabs_expansion(context, object(), {"A": object()})
            popup_module._draw_categories_grid(FakeLayout(), context, object())
        finally:
            popup_module.scanner.get_snapshot = original_snapshot
            popup_module._library_contents = original_contents
            popup_module._draw_group = original_group
            popup_module._draw_target_button = original_target

        self.assertEqual(expansion_states, [True, False])
        self.assertEqual(drawn_targets, ["A"])

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
        preferences = SimpleNamespace(targets=tuple(targets))
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
        launcher_module.scanner.refresh_catalog = lambda _context: None
        launcher_module._search_target_items = lambda _operator, _context: [("target",)]
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

    def test_favorite_merge_deduplicates_and_stops_at_eight(self):
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        merged = preferences_module._merge_favorite_keys(
            ("A", "B", "A", ""),
            tuple("CDEFGHIJ"),
        )

        self.assertEqual(merged, tuple("ABCDEFGH"))

    def test_favorite_operators_append_swap_move_remove_and_limit(self):
        favorites_module = importlib.import_module("quick_n_panel.operators.favorites")
        preferences_module = importlib.import_module("quick_n_panel.preferences")
        preferences = SimpleNamespace(
            favorites=FakeCollection(),
            favorite_index=0,
        )
        original_get_preferences = favorites_module.get_preferences
        favorites_module.get_preferences = lambda _context: preferences
        try:
            for target_key in "ABCDEFGH":
                operator = favorites_module.QNP_OT_AssignFavorite()
                operator.index = -1
                operator.target_key = target_key
                self.assertEqual(operator.execute(None), {"FINISHED"})

            overflow = favorites_module.QNP_OT_AssignFavorite()
            overflow.index = -1
            overflow.target_key = "I"
            self.assertEqual(overflow.execute(None), {"CANCELLED"})

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
            toggle.target_key = "I"
            self.assertEqual(toggle.execute(None), {"FINISHED"})

            toggle_existing = favorites_module.QNP_OT_ToggleFavorite()
            toggle_existing.target_key = "B"
            self.assertEqual(toggle_existing.execute(None), {"FINISHED"})
            self.assertNotIn("B", preferences_module.favorite_keys(preferences))

            refill = favorites_module.QNP_OT_ToggleFavorite()
            refill.target_key = "J"
            self.assertEqual(refill.execute(None), {"FINISHED"})

            overflow = favorites_module.QNP_OT_ToggleFavorite()
            overflow.target_key = "K"
            overflow.report = lambda *_args: None
            self.assertEqual(overflow.execute(None), {"CANCELLED"})
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
