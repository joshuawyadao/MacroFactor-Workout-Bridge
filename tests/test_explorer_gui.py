import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from macrofactor_bridge.ooxml import file_sha256
from tests.comparison_fixture import comparison_inputs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from tests.gui_support import dispose_widget
    from PySide6.QtWidgets import QApplication, QMessageBox
    from macrofactor_bridge.desktop import BridgeWindow

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class ExplorerGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["explorer-test"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.export, self.coach, self.annotations = comparison_inputs(Path(temporary.name))
        self.window = BridgeWindow()
        self.addCleanup(dispose_widget, self.window)
        self.window.history_export_path.setText(str(self.export))
        self.window.history_workbook_path.setText(str(self.coach))
        self.window.history_annotations_path.setText(str(self.annotations))
        self.window.history_config_path.setText(str(ROOT / "config/exercises.example.json"))
        self.window._load_history()
        self.home = self.window.history_home
        self.explorer = self.window.history_explorer

    def test_dashboard_is_default_and_cards_open_timeline_without_block_selection(self):
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.assertIs(self.window.tabs.currentWidget(), self.window.dashboard_tab)
        self.assertIs(self.window.history_analysis_tabs.currentWidget(), self.home)
        card = self.home.cards[0]
        self.assertEqual(card.exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(card.value.text(), "583.3 lb")
        self.assertFalse(self.home.cards[1].button.isEnabled())
        self.assertIn("No supported variation", self.home.cards[1].detail.text())
        self.assertEqual(self.home.blocks.item(0, 2).text(), "233.3")
        self.assertEqual(self.home.blocks.item(1, 2).text(), "583.3")
        card.button.click()
        self.assertIs(self.window.history_analysis_tabs.currentWidget(), self.window.history_timeline)
        self.assertEqual(self.window.history_timeline.selectors["Squat"].currentText(), "Tempo Back Squat")
        # The retained exercise explorer still supports standalone exact-exercise analysis.
        self.explorer.open_exercise("Tempo Back Squat")
        self.assertEqual(self.explorer.exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(self.explorer.period.currentData(), 0)
        self.assertEqual(self.explorer.table.rowCount(), 5)

    def test_filters_keep_missing_and_zero_distinct_and_show_saved_context(self):
        self.explorer.family.setCurrentText("Squat")
        self.explorer.period.setCurrentIndex(1)
        self.explorer.metric_selector.setCurrentIndex(1)
        self.assertEqual(self.explorer.table.rowCount(), 4)
        self.assertEqual(self.explorer.chart.plot_values(), ((210, None, 0, 500),))
        self.assertEqual(self.explorer.chart.context_bands(), ((0, 2, "Training Block"), (3, 3, "Archive")))
        self.assertIn("Confirmed skipped squat", self.explorer.table.item(2, 7).toolTip())
        self.assertIn("partial export", self.explorer.table.item(0, 7).text())
        self.assertEqual(self.explorer.table.item(0, 0).text(), "2026-08-24")
        self.explorer.search.setText("not present")
        self.assertEqual(self.explorer.table.rowCount(), 0)
        self.assertEqual(self.explorer.chart.plot_values(), ())
        self.assertIn("No exercises match", self.explorer.summary.text())
        self.explorer.search.clear()
        self.assertEqual(self.explorer.table.rowCount(), 4)
        self.explorer.family.setCurrentText("All exercises")
        self.explorer.search.setText("carry")
        self.assertEqual(self.explorer.exercise.currentText(), "Unmapped Carry")

    def test_reload_preserves_filters_and_source_changes_clear_every_view(self):
        paths = (self.export, self.coach, self.annotations)
        before = [file_sha256(p) for p in paths]
        self.explorer.search.setText("tempo")
        self.explorer.period.setCurrentIndex(2)
        self.explorer.metric_selector.setCurrentIndex(2)
        self.window._load_history()
        self.assertEqual(self.explorer.search.text(), "tempo")
        self.assertEqual(self.explorer.exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(self.explorer.period.currentData(), 12)
        self.assertEqual(self.explorer.metric_selector.currentData(), "set_count")
        self.assertEqual(before, [file_sha256(p) for p in paths])
        self.window.history_export_path.setText("missing.csv")
        self.assertEqual(self.home.blocks.rowCount(), 0)
        self.assertEqual(self.explorer.table.rowCount(), 0)
        self.assertFalse(self.explorer.search.isEnabled())
        self.assertEqual(self.home.cards[0].chart.plot_values(), ())
        with patch.object(QMessageBox, "critical"):
            self.window._load_history()
        self.assertEqual(self.home.cards[0].value.text(), "—")

    def test_minimum_window_keeps_dashboard_and_explorer_accessible(self):
        self.window.resize(900, 680)
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.size().width(), 900)
        self.assertGreater(self.home.viewport().height(), 100)
        self.assertFalse(self.home.grab().isNull())
        self.home.cards[0].button.click()
        self.window.history_analysis_tabs.setCurrentWidget(self.explorer)
        self.app.processEvents()
        self.assertGreaterEqual(self.explorer.table.viewport().height(), 70)
        self.assertGreaterEqual(self.explorer.chart.height(), 135)
        self.assertFalse(self.explorer.chart.grab().isNull())

    def test_short_exports_have_prominent_coverage_guidance(self):
        from dataclasses import replace
        dashboard = self.window._history_dashboard
        self.home.set_history(replace(dashboard, first_workout=dashboard.last_workout))
        self.assertIn("Short export", self.home.coverage.text())

    def test_card_variation_persists_on_reload(self):
        # The selected exercise remains exact through invalidation and reload.
        self.home.cards[0].exercise.setCurrentText("Tempo Back Squat")
        before = self.home.cards[0].chart.plot_values()
        self.window._load_history()
        self.assertEqual(self.home.cards[0].exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(self.home.cards[0].chart.plot_values(), before)


if __name__ == "__main__":
    unittest.main()
