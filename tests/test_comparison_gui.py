import importlib.util
import os
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.comparison_fixture import comparison_inputs
from macrofactor_bridge.history import load_dashboard_annotations
from macrofactor_bridge.ooxml import file_sha256

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from macrofactor_bridge.desktop import BridgeWindow

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class ComparisonGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["comparison-test"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.export, self.coach, self.path = comparison_inputs(Path(temporary.name))
        self.window = BridgeWindow()
        self.addCleanup(self.window.close)
        self.window.history_export_path.setText(str(self.export))
        self.window.history_workbook_path.setText(str(self.coach))
        self.window.history_config_path.setText(str(ROOT / "config/exercises.example.json"))
        self.window.history_annotations_path.setText(str(self.path))
        self.window._load_history()
        self.panel = self.window.history_comparison
        self.panel.exercise.setCurrentText("Tempo Back Squat")
        self.panel.first_block.setCurrentText("Training Block")
        self.panel.second_block.setCurrentText("Archive")

    def test_paired_rows_context_and_shared_chart_scale(self):
        self.assertEqual(self.panel.table.rowCount(), 6)
        self.assertIn("2026-08-03", self.panel.table.item(0, 2).text())
        self.assertIn("2026-08-24", self.panel.table.item(1, 2).text())
        self.assertEqual(self.panel.table.item(2, 4).text(), "—")
        self.assertIn("Confirmed skipped squat", self.panel.table.item(2, 8).text())
        self.assertEqual(self.panel.table.item(3, 2).text(), "Outside this block")
        self.assertEqual(self.panel.chart.plot_values(), ((Decimal("233.3"), None, None), (Decimal("583.3"),)))
        self.assertEqual(self.panel.chart.value_range(), (0, Decimal("583.3")))
        self.panel.metric_selector.setCurrentIndex(1)
        self.assertEqual(self.panel.chart.plot_values(), ((Decimal(210), None, Decimal(0)), (Decimal(500),)))
        self.assertEqual(self.panel.chart.value_range(), (0, 500))
        self.window.tabs.setCurrentIndex(1)
        self.window.history_analysis_tabs.setCurrentWidget(self.panel)
        self.window.show()
        self.app.processEvents()
        self.assertFalse(self.panel.chart.grab().isNull(), "The chart must paint on the actual Qt surface")
        self.assertFalse(self.window.history_sources.isVisible(), "Loaded sources collapse to leave room for analysis")
        self.assertGreaterEqual(self.panel.table.viewport().height(), 40, "The loaded comparison must retain visible rows")
        self.window.history_sources_toggle.setChecked(True)
        self.assertTrue(self.window.history_sources.isVisible())

    def test_selection_survives_reload_and_context_save(self):
        self.panel.first_block.setCurrentText("Archive")
        self.panel.second_block.setCurrentText("Training Block")
        self.panel.metric_selector.setCurrentIndex(2)
        self.window._load_history()
        self.assertEqual(self.panel.first_block.currentText(), "Archive")
        self.assertEqual(self.panel.second_block.currentText(), "Training Block")
        self.assertEqual(self.panel.metric_selector.currentData(), "set_count")
        self.window.history_block_combo.setCurrentText("Training Block")
        self.window.history_week_combo.setCurrentText("Week 10")
        self.window.history_week_notes.setText("New saved travel context")
        source_hashes = [file_sha256(p) for p in (self.export, self.coach)]
        layout = load_dashboard_annotations(self.path).blocks["Training Block"].week_layout
        self.window._save_history_annotation()
        self.assertIn("New saved travel context", self.panel.table.item(1, 8).text())
        self.assertEqual(self.panel.first_block.currentText(), "Archive")
        self.assertEqual(load_dashboard_annotations(self.path).blocks["Training Block"].week_layout, layout)
        self.assertEqual(source_hashes, [file_sha256(p) for p in (self.export, self.coach)])

    def test_same_block_invalid_input_and_failed_reload_clear_stale_results(self):
        self.panel.second_block.setCurrentText("Training Block")
        self.assertEqual(self.panel.table.rowCount(), 0)
        self.assertIn("different blocks", self.panel.status.text())
        self.assertIsNone(self.panel.chart.comparison)
        self.panel.second_block.setCurrentText("Archive")
        self.window.history_export_path.setText(str(self.export) + ".missing")
        self.assertEqual(self.panel.table.rowCount(), 0)
        self.assertFalse(self.panel.first_block.isEnabled())
        with patch.object(QMessageBox, "critical"):
            self.window._load_history()
        self.assertIsNone(self.panel.chart.comparison)
        self.assertEqual(self.panel.table.rowCount(), 0)

    def test_exercise_without_values_has_a_gap_not_an_estimate(self):
        self.panel.exercise.setCurrentText("Unmapped Carry")
        self.assertEqual(self.panel.table.item(0, 4).text(), "—")
        self.assertEqual(self.panel.table.item(2, 4).text(), "1")
        self.assertIsNone(self.panel.chart.plot_values()[0][0])

    def test_long_context_stays_available_without_expanding_comparison_rows(self):
        note = "Synthetic context with a lot of detail. " * 50
        self.window.history_block_combo.setCurrentText("Training Block")
        self.window.history_week_combo.setCurrentText("Week 10")
        self.window.history_week_notes.setText(note)
        self.window._save_history_annotation()
        self.window.tabs.setCurrentIndex(1)
        self.window.history_analysis_tabs.setCurrentWidget(self.panel)
        self.window.show()
        self.app.processEvents()
        self.assertIn(note.strip(), self.panel.table.item(0, 8).toolTip())
        self.assertLess(self.panel.table.rowHeight(0), 80, "Long context must not hide the paired rows")


if __name__ == "__main__":
    unittest.main()
