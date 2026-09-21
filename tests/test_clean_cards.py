"""Interaction and disclosure regressions for the visual dashboard cards."""

from dataclasses import replace
from datetime import date
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from macrofactor_bridge.config import load_config
from macrofactor_bridge.history import build_history_dashboard, load_dashboard_annotations
from tests.comparison_fixture import comparison_inputs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from tests.gui_support import dispose_widget
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton
    from macrofactor_bridge.explorer_view import HistoryHome

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class CleanCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["clean-card-test"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        export, coach, annotation_path = comparison_inputs(Path(temporary.name))
        self.annotations = load_dashboard_annotations(annotation_path)
        self.dashboard = build_history_dashboard(export, coach, load_config(ROOT / "config/exercises.example.json"), self.annotations)
        self.home = HistoryHome()
        self.addCleanup(dispose_widget, self.home)
        self.home.set_history(self.dashboard, self.annotations)
        self.home.resize(860, 590)
        self.home.show()
        self.app.processEvents()

    def workload_widgets(self, widget_type):
        # Rebuilt widgets await Qt's deferred deletion; only the active layout
        # belongs to the currently displayed workload projection.
        layout = self.home.workload_layout
        return [layout.itemAt(index).widget() for index in range(layout.count())
                if isinstance(layout.itemAt(index).widget(), widget_type)]

    def test_quiet_lift_heading_is_the_only_button_and_opens_exact_variation(self):
        card = self.home.cards[0]
        selected = []
        self.home.explore.connect(selected.append)
        self.assertEqual(card.findChildren(QPushButton), [card.button])
        self.assertEqual(card.button.objectName(), "quietButton")
        self.assertEqual(card.exercise.objectName(), "quietSelector")
        self.assertIn("squat", card.button.accessibleName())
        card.button.setFocus()
        QTest.keyClick(card.button, Qt.Key.Key_Space)
        self.assertEqual(selected, ["Tempo Back Squat"])
        self.assertEqual(card.value.text(), "583.3 lb")
        self.assertIn("Est. 1RM", card.detail.text())
        self.assertIn("2026", card.detail.text())
        self.assertLess(card.button.geometry().bottom(), card.chart.geometry().top())

    def test_block_heading_preserves_navigation_coverage_and_average_denominator(self):
        card = self.home.report_cards[0]
        buttons = card.findChildren(QPushButton)
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].objectName(), "quietButton")
        self.assertEqual(buttons[0].accessibleName(), "Analyze block Training Block")
        selected = []
        self.home.focus_block.connect(selected.append)
        buttons[0].click()
        self.assertEqual(selected, ["Training Block"])
        labels = [label.text() for label in card.findChildren(QLabel)]
        self.assertIn("1.3", labels)
        self.assertIn("sets / week", labels)
        self.assertIn("1.3 days / week · 3 full weeks", labels)
        self.assertIn("Within export date range", labels)
        self.assertTrue(any("Partial" in label.text() for label in self.home.report_cards[1].findChildren(QLabel)))

    def test_notes_and_methodology_are_collapsed_but_keyboard_reachable(self):
        self.assertTrue(self.home.details_panel.isHidden())
        self.assertFalse(self.home.context.isVisible())
        self.assertFalse(self.home.averages_note.isVisible())
        self.assertFalse(self.home.blocks.isVisible())
        bars = self.workload_widgets(QProgressBar)
        self.assertTrue(bars)
        self.assertTrue(all(bar.isVisible() for bar in bars))
        original_values = [bar.value() for bar in bars]
        self.home.values_button.setFocus()
        QTest.keyClick(self.home.values_button, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertTrue(self.home.context.isVisible())
        self.assertTrue(self.home.averages_note.isVisible())
        self.assertTrue(self.home.blocks.isVisible())
        self.assertIn("Return after travel", self.home.context.text())
        self.assertIn("partial weeks are excluded", self.home.averages_note.text())
        self.assertEqual(original_values, [bar.value() for bar in bars])
        QTest.keyClick(self.home.values_button, Qt.Key.Key_Space)
        self.assertTrue(self.home.details_panel.isHidden())

    def test_accessory_drill_down_is_quiet_and_retains_workload_bars(self):
        buttons = self.workload_widgets(QPushButton)
        bars = self.workload_widgets(QProgressBar)
        self.assertEqual(len(buttons), len(bars))
        selected = []
        self.home.explore.connect(selected.append)
        for button in buttons:
            self.assertEqual(button.objectName(), "quietButton")
            self.assertIn("sets per week", button.accessibleName())
            button.click()
            self.assertEqual(selected[-1], button.toolTip())

    def test_missing_and_invalid_data_remain_explicit_without_zero_estimates(self):
        empty_card = self.home.cards[1]
        self.assertEqual(empty_card.value.text(), "—")
        self.assertIn("No supported variation", empty_card.detail.text())
        self.assertFalse(empty_card.button.isEnabled())
        undated = replace(self.dashboard.blocks[0], start_date=None)
        other = replace(self.dashboard.blocks[1], start_date=date(2025, 1, 6))
        self.home.set_history(replace(self.dashboard, blocks=(undated, other)), self.annotations)
        texts = [label.text() for card in self.home.report_cards for label in card.findChildren(QLabel)]
        self.assertIn("Needs a start date", texts)
        self.assertIn("Outside export date range", texts)
        self.assertEqual(texts.count("—"), 2)
        self.assertTrue(all(not card.findChild(QPushButton).isEnabled() for card in self.home.report_cards))

    def test_background_load_reflows_short_cards_without_overlap(self):
        self.home.set_history(None)
        self.app.processEvents()
        self.home.set_history(self.dashboard, self.annotations)
        QTest.qWait(100)
        self.app.processEvents()
        self.assertEqual(self.home.width(), 860)
        for first, second in zip(self.home.report_cards, self.home.report_cards[1:]):
            self.assertLess(first.geometry().right(), second.geometry().left())
        for card in self.home.report_cards:
            for label in card.findChildren(QLabel):
                self.assertLessEqual(label.geometry().bottom(), card.height())
        for card in self.home.cards:
            self.assertLess(card.button.geometry().bottom(), card.chart.geometry().top())


if __name__ == "__main__":
    unittest.main()
