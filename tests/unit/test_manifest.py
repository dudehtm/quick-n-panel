from pathlib import Path
import tomllib
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ManifestTests(unittest.TestCase):
    def test_extension_contract(self):
        manifest = tomllib.loads(
            (PROJECT_ROOT / "blender_manifest.toml").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["schema_version"], "1.0.0")
        self.assertEqual(manifest["id"], "quick_n_panel")
        self.assertEqual(manifest["version"], "1.1.0")
        self.assertEqual(manifest["name"], "Quick N-panel")
        self.assertEqual(manifest["maintainer"], "Dudehtm")
        self.assertEqual(manifest["type"], "add-on")
        self.assertEqual(manifest["blender_version_min"], "5.0.0")
        self.assertEqual(
            manifest["license"],
            ["SPDX:GPL-3.0-or-later", "SPDX:CC0-1.0"],
        )
        self.assertEqual(manifest["copyright"], ["2026 Dudehtm"])
        self.assertEqual(
            manifest["website"],
            "https://github.com/dudehtm/quick-n-panel",
        )
        self.assertEqual(manifest["tags"], ["User Interface"])
        self.assertIn("files", manifest["permissions"])
        self.assertLessEqual(len(manifest["permissions"]["files"]), 64)
        self.assertIn("settings", manifest["permissions"]["files"])
        self.assertFalse((PROJECT_ROOT / "icons" / "DudehtmLogob.png").exists())
        self.assertIn(
            "/EXPORTACION_Y_DISTRIBUCION.md",
            manifest["build"]["paths_exclude_pattern"],
        )
        self.assertIn(
            "/FUTURE_FEATURES.md",
            manifest["build"]["paths_exclude_pattern"],
        )
        self.assertIn(
            "/.gitattributes",
            manifest["build"]["paths_exclude_pattern"],
        )
        self.assertIn(
            "/.gitignore",
            manifest["build"]["paths_exclude_pattern"],
        )

    def test_complete_license_texts_are_included(self):
        gpl = (PROJECT_ROOT / "LICENSES" / "GPL-3.0.txt").read_text(encoding="utf-8")
        cc0 = (PROJECT_ROOT / "LICENSES" / "CC0-1.0.txt").read_text(encoding="utf-8")
        notice = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("GNU GENERAL PUBLIC LICENSE", gpl)
        self.assertIn("END OF TERMS AND CONDITIONS", gpl)
        self.assertIn("CC0 1.0 Universal", cc0)
        self.assertIn("Public License Fallback", cc0)
        self.assertIn("icons under icons/Custom", notice)
        self.assertIn("Photopea", notice)
        self.assertIn("GIMP", notice)

    def test_production_source_has_no_funding_link_or_keymap_editor(self):
        production_files = tuple(PROJECT_ROOT.glob("*.py")) + tuple(
            (PROJECT_ROOT / "ui").rglob("*.py")
        )
        source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

        self.assertNotIn("ko-fi.com", source.casefold())
        self.assertNotIn("quick_n_panel.capture_shortcut", source)
        self.assertNotIn("draw_preferences_keymap", source)
        self.assertNotIn('"wm.url_open"', source)
        self.assertNotIn('icon="EVENT_F5"', source)


if __name__ == "__main__":
    unittest.main()
