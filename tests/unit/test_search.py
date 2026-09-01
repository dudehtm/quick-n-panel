import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT.parent))

from quick_n_panel.core.search import (  # noqa: E402
    SearchDocument,
    normalize_text,
    rank_documents,
    score_document,
)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.machine_tools = SearchDocument(
            key="machine",
            name="Machine Tools",
            category="Machin3",
            panel_labels=("Asset Browser Tools", "Modeling"),
            source_names=("Machin3 Tools",),
            group_name="Modeling",
        )
        self.geometry_nodes = SearchDocument(
            key="geometry",
            name="Geometry Nodes",
            category="Node Tools",
            panel_labels=("Geometry Node Utilities",),
        )

    def test_normalize_text_removes_accents_and_punctuation(self):
        self.assertEqual(normalize_text("  Geometría-NODOS  "), "geometria nodos")

    def test_partial_name_scores_highly(self):
        self.assertGreater(score_document("machin", self.machine_tools), 0.9)

    def test_minor_typo_remains_searchable(self):
        self.assertGreater(score_document("machien tools", self.machine_tools), 0.5)

    def test_panel_label_is_searchable(self):
        self.assertGreater(score_document("asset browser", self.machine_tools), 0.8)

    def test_ranking_prefers_relevant_document(self):
        ranked = rank_documents(
            "geo nod",
            [self.machine_tools, self.geometry_nodes],
        )
        self.assertEqual(ranked[0].key, "geometry")


if __name__ == "__main__":
    unittest.main()
