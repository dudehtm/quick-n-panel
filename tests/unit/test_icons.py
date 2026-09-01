from pathlib import Path
import struct
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ICON_DIRECTORY = PROJECT_ROOT / "icons" / "Custom"
EXPECTED_ICONS = {
    "QNP_Animation.png",
    "QNP_Cloth_Simulations.png",
    "QNP_Favorites.png",
    "QNP_Files.png",
    "QNP_Hair_Fur.png",
    "QNP_Lights.png",
    "QNP_Material.png",
    "QNP_Modeling.png",
    "QNP_Nodes.png",
    "QNP_Paint.png",
    "QNP_Render.png",
    "QNP_Rigging.png",
    "QNP_Sculpt.png",
    "QNP_Simulations.png",
    "QNP_UV.png",
    "QNP_Utils.png",
}


class IncludedIconTests(unittest.TestCase):
    def test_expected_icon_set_is_present(self):
        filenames = {path.name for path in ICON_DIRECTORY.glob("QNP_*.png")}
        self.assertEqual(filenames, EXPECTED_ICONS)

    def test_icons_are_96_pixel_rgba_png_files(self):
        for filepath in ICON_DIRECTORY.glob("QNP_*.png"):
            filename = filepath.name
            data = filepath.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", filename)
            self.assertEqual(data[12:16], b"IHDR", filename)
            self.assertEqual(struct.unpack(">II", data[16:24]), (96, 96), filename)
            self.assertEqual(data[24], 8, filename)
            self.assertEqual(data[25], 6, filename)

if __name__ == "__main__":
    unittest.main()
