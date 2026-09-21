import importlib.util
import os
from decimal import Decimal
from dataclasses import replace
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
    from tests.gui_support import dispose_widget
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
        self.addCleanup(dispose_widget, self.window)
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
        self.window.tabs.setCurrentWidget(self.window.dashboard_tab)
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

    def test_initial_exercise_prefers_data_in_both_default_blocks(self):
        self.export.write_text(
            self.export.read_text(encoding="utf-8")
            + "2026-07-27,Before,Aardvark Carry,Standard Set,50,10\n",
            encoding="utf-8",
        )
        window = BridgeWindow()
        self.addCleanup(window.close)
        window.history_export_path.setText(str(self.export))
        window.history_workbook_path.setText(str(self.coach))
        window.history_config_path.setText(str(ROOT / "config/exercises.example.json"))
        window.history_annotations_path.setText(str(self.path))
        window._load_history()
        panel = window.history_comparison
        self.assertEqual(panel.exercise.itemText(0), "Aardvark Carry")
        self.assertEqual(panel.exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(panel.first_block.currentText(), "Training Block")
        self.assertEqual(panel.second_block.currentText(), "Archive")
        self.assertTrue(all(any(week.trend for week in series.weeks)
                            for series in (panel.chart.comparison.first, panel.chart.comparison.second)))

    def test_explicit_exercise_without_both_block_values_survives_reload(self):
        self.export.write_text(
            self.export.read_text(encoding="utf-8")
            + "2026-07-27,Before,Aardvark Carry,Standard Set,50,10\n",
            encoding="utf-8",
        )
        self.window._load_history()
        self.panel.exercise.setCurrentText("Aardvark Carry")
        self.window._load_history()
        self.assertEqual(self.panel.exercise.currentText(), "Aardvark Carry")

    def test_swap_keeps_metric_and_exercise_and_is_disabled_without_history(self):
        self.panel.metric_selector.setCurrentIndex(1)
        before = self.panel.chart.plot_values()
        self.panel.swap_button.click()
        self.assertEqual(self.panel.first_block.currentText(), "Archive")
        self.assertEqual(self.panel.second_block.currentText(), "Training Block")
        self.assertEqual(self.panel.exercise.currentText(), "Tempo Back Squat")
        self.assertEqual(self.panel.metric_selector.currentData(), "top_weight")
        self.assertEqual(self.panel.chart.plot_values(), before[::-1])
        self.window.history_export_path.setText("changed.csv")
        self.assertFalse(self.panel.swap_button.isEnabled())

    def test_summary_cards_and_selected_block_context_shortcut(self):
        dashboard = self.window._history_dashboard
        self.assertEqual([card.value.text() for card in self.window.history_cards],
                         [str(dashboard.set_count), str(dashboard.training_day_count), "2", "0%"])
        self.assertIn("workouts", self.window.history_overview.toolTip())
        self.assertFalse(self.window.history_context_button.isEnabled())
        self.window.history_block_table.selectRow(1)
        self.window.history_context_button.click()
        self.assertEqual(self.window.history_block_combo.currentText(), "Archive")
        self.assertIs(self.window.history_analysis_tabs.currentWidget(), self.window.history_context_page)
        self.window.history_export_path.setText("changed.csv")
        self.assertEqual([card.value.text() for card in self.window.history_cards], ["—"] * 4)
        self.assertFalse(self.window.history_context_button.isEnabled())
        self.assertEqual(self.window.history_overview.toolTip(), "")

    def test_full_block_notes_open_on_demand_and_clear_with_inputs(self):
        self.window.show()
        self.panel.notes_button.click()
        self.app.processEvents()
        self.assertTrue(self.panel.notes_dialog.isVisible())
        self.assertIn("Synthetic strength block", self.panel.block_notes.toPlainText())
        self.panel.notes_dialog.accept()
        self.window.history_export_path.setText("changed.csv")
        self.assertEqual(self.panel.block_notes.toPlainText(), "")
        self.assertFalse(self.panel.notes_button.isEnabled())

    def test_sparse_rir_coverage_does_not_look_like_zero_or_complete_coverage(self):
        dashboard = self.window._history_dashboard
        self.window._display_history_dashboard(replace(dashboard, set_count=2000, rir_set_count=4))
        self.assertEqual(self.window.history_cards[3].value.text(), "<1%")
        self.window._display_history_dashboard(replace(dashboard, set_count=2000, rir_set_count=1999))
        self.assertEqual(self.window.history_cards[3].value.text(), ">99%")

    def test_minimum_window_keeps_chart_and_comparison_rows_visible(self):
        self.window.history_status.setText(
            "History loaded read-only; neither source file was changed. Estimated 1RM uses weighted standard "
            "sets of 1–12 reps. A training block is using a private history layout with 3 weeks. "
            "RIR is recorded for 4 sets; it remains descriptive and does not adjust estimated 1RM."
        )
        self.window.tabs.setCurrentWidget(self.window.dashboard_tab)
        self.window.history_analysis_tabs.setCurrentWidget(self.panel)
        self.window.resize(900, 680)
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.width(), 900)
        self.assertEqual(self.window.height(), 680)
        self.assertGreaterEqual(self.panel.table.viewport().height(), 70)
        self.assertGreaterEqual(self.panel.chart.height(), 135)
        self.assertLessEqual(self.panel.chart.geometry().bottom(), self.panel.table.geometry().top())
        self.assertFalse(self.window.grab().isNull())

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
        self.window.tabs.setCurrentWidget(self.window.dashboard_tab)
        self.window.history_analysis_tabs.setCurrentWidget(self.panel)
        self.window.show()
        self.app.processEvents()
        self.assertIn(note.strip(), self.panel.table.item(0, 8).toolTip())
        self.assertLess(self.panel.table.rowHeight(0), 80, "Long context must not hide the paired rows")


if __name__ == "__main__":
    unittest.main()
