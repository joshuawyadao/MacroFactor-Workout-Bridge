import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from dataclasses import replace

from macrofactor_bridge.ooxml import file_sha256
from tests.comparison_fixture import comparison_inputs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from tests.gui_support import dispose_widget
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget
    from macrofactor_bridge.desktop import BridgeWindow
    from macrofactor_bridge.explorer_view import LIFT_COLORS

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class TimelineGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["timeline-test"])

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
        self.timeline = self.window.history_timeline

    def test_block_cards_focus_timeline_and_range_is_shared_both_directions(self):
        self.assertEqual(len(self.home.report_cards), 2)
        self.assertEqual(self.home.blocks.item(0, 5).text(), "1.3")
        self.home.report_cards[0].findChild(QPushButton).click()
        self.assertIs(self.window.history_analysis_tabs.currentWidget(), self.timeline)
        self.assertEqual(self.timeline.block.currentData(), "Training Block")
        self.assertEqual(len(self.timeline.weeks), 3)
        self.assertEqual(self.timeline.charts["Squat"].plot_values(), ((Decimal("233.3"), None, None),))
        self.home.period.setCurrentIndex(1)
        self.assertEqual(self.timeline.period.currentData(), 4)
        self.timeline.period.setCurrentIndex(2)
        self.assertEqual(self.home.period.currentData(), 12)

    def test_aligned_axes_colors_and_context_toggle(self):
        labels = self.timeline.workload.labels
        for family, chart in self.timeline.charts.items():
            self.assertEqual(chart.labels, labels)
            self.assertEqual(chart.series_colors, (LIFT_COLORS[family],))
        self.assertEqual(self.home.cards[1].chart.series_colors, (LIFT_COLORS["Bench"],))
        chart = self.timeline.charts["Squat"]
        self.assertIn("Return after travel", chart.annotations[1])
        before = chart.plot_values()
        self.timeline.show_context.setChecked(False)
        self.assertEqual(chart.annotations, ())
        self.assertEqual(chart.plot_values(), before)
        self.assertTrue(chart.context_bands())

    def test_mouse_chart_click_opens_original_sets_and_missing_rir_stays_unknown(self):
        self.window.history_analysis_tabs.setCurrentWidget(self.timeline)
        self.window.resize(1120, 820)
        self.window.show()
        self.app.processEvents()
        chart = self.timeline.charts["Squat"]
        # Five weeks; index 1 is Aug 3, which has two squat sets.
        x = 52 + (chart.width() - 80) / 4
        QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=QPoint(round(x), 60))
        self.app.processEvents()
        dialog = self.timeline.details_dialog
        self.assertIsNotNone(dialog)
        table = dialog.findChild(QTableWidget)
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 4).text(), "200")
        self.assertEqual(table.item(0, 6).text(), "—")
        dialog.close()

    def test_missing_week_does_not_open_other_exercise_sets(self):
        self.timeline._point(2, "Squat")
        dialog = self.timeline.details_dialog
        self.assertEqual(dialog.findChild(QTableWidget).rowCount(), 0)
        self.assertIn("Tempo Back Squat", dialog.windowTitle())
        dialog.close()
        self.timeline._point(3, "Squat")
        table = self.timeline.details_dialog.findChild(QTableWidget)
        self.assertEqual(table.item(0, 4).text(), "0")
        self.timeline.details_dialog.close()

    def test_nonfinite_source_weights_remain_inspectable_without_changing_metrics(self):
        original = self.export.read_text(encoding="utf-8")
        for weight in ("Infinity", "-Infinity", "sNaN", "NaN"):
            with self.subTest(weight=weight):
                self.export.write_text(original.replace("Standard Set,200,5", f"Standard Set,{weight},5"), encoding="utf-8")
                before = [file_sha256(p) for p in (self.export, self.coach, self.annotations)]
                self.window._load_history()
                trend = self.window._history_dashboard.trends_for("Tempo Back Squat")[0]
                self.assertEqual(trend.top_weight, Decimal(210))
                self.assertEqual(trend.set_count, 2)
                self.timeline.week_selector.setCurrentText("2026-08-03")
                self.timeline.detail_exercise.setCurrentText("Tempo Back Squat")
                self.timeline._open_details()
                table = self.timeline.details_dialog.findChild(QTableWidget)
                self.assertEqual(table.rowCount(), 2)
                self.assertEqual(table.item(0, 4).text(), f"Invalid ({weight})")
                self.assertEqual(table.item(1, 4).text(), "210")
                self.timeline.details_dialog.close()
                self.assertEqual(before, [file_sha256(p) for p in (self.export, self.coach, self.annotations)])

    def test_keyboard_accessible_week_and_set_controls(self):
        self.timeline.week_selector.setCurrentText("2026-08-03")
        self.timeline.show_context.setChecked(False)
        self.assertEqual(self.timeline.week_selector.currentData(), date(2026, 8, 3))
        self.timeline.detail_exercise.setCurrentText("Tempo Back Squat")
        self.timeline.details_button.click()
        self.assertEqual(self.timeline.details_dialog.findChild(QTableWidget).rowCount(), 2)
        self.timeline.details_dialog.close()

    def test_variation_changes_are_shared_but_never_combined(self):
        dashboard = self.window._history_dashboard
        example = dashboard.trends_for("Tempo Back Squat")[0]
        extra = replace(example, exercise="High Bar Back Squat", estimated_1rm=Decimal(900))
        summary = next(s for s in dashboard.exercises if s.exercise == "Tempo Back Squat")
        dashboard = replace(dashboard, exercises=dashboard.exercises + (replace(summary, exercise=extra.exercise),),
                            weekly_trends=dashboard.weekly_trends + (extra,))
        self.timeline.set_history(dashboard)
        self.home.set_history(dashboard)
        self.home.cards[0].exercise.setCurrentText(extra.exercise)
        self.assertEqual(self.timeline.selectors["Squat"].currentText(), extra.exercise)
        self.assertEqual(self.timeline.charts["Squat"].plot_values(), ((None, Decimal(900), None, None, None),))
        self.timeline.selectors["Squat"].setCurrentText("Tempo Back Squat")
        self.assertEqual(self.home.cards[0].exercise.currentText(), "Tempo Back Squat")
        self.assertNotIn(Decimal(900), self.timeline.charts["Squat"].plot_values()[0])

    def test_rebuilt_panels_hide_retired_widgets_before_deferred_deletion(self):
        retired = tuple(self.home.report_cards)
        self.home.period.setCurrentIndex(1)
        self.assertTrue(all(card.isHidden() for card in retired))
        self.assertEqual(len(self.home.report_cards), 2)

    def test_source_invalidation_closes_details_and_clears_all_data(self):
        before = [file_sha256(p) for p in (self.export, self.coach, self.annotations)]
        self.timeline.period.setCurrentIndex(2)
        self.timeline._point(1, "Squat")
        self.window._load_history()
        self.assertEqual(self.timeline.period.currentData(), 12)
        self.assertIsNone(self.timeline.details_dialog)
        self.assertEqual(before, [file_sha256(p) for p in (self.export, self.coach, self.annotations)])
        self.timeline._point(1, "Squat")
        self.window.history_export_path.setText("missing.csv")
        self.assertIsNone(self.timeline.details_dialog)
        self.assertEqual(self.timeline.charts["Squat"].plot_values(), ())
        self.assertEqual(self.timeline.workload.plot_values(), ())
        self.assertFalse(self.timeline.details_button.isEnabled())
        self.assertEqual(self.home.report_cards, [])

    def test_minimum_window_and_empty_family_render_without_expanding_window(self):
        self.window.resize(900, 680)
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.width(), 900)
        self.assertFalse(self.home.grab().isNull())
        self.home.cards[0].button.click()
        self.app.processEvents()
        self.assertEqual(self.window.width(), 900)
        self.assertFalse(self.timeline.grab().isNull())
        self.assertFalse(self.timeline.selectors["Bench"].isEnabled())
        self.assertTrue(all(value is None for value in self.timeline.charts["Bench"].plot_values()[0]))
        self.timeline.scroll.verticalScrollBar().setValue(self.timeline.scroll.verticalScrollBar().maximum())
        self.home.report_cards[0].findChild(QPushButton).click()
        self.assertEqual(self.timeline.scroll.verticalScrollBar().value(), 0)


if __name__ == "__main__":
    unittest.main()
