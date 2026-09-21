from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

if HAS_QT:
    from tests.gui_support import dispose_widget
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from macrofactor_bridge.desktop import BridgeWindow

from macrofactor_bridge.models import BridgeReport, ProposedWrite
from macrofactor_bridge.ooxml import file_sha256
from macrofactor_bridge.history import load_dashboard_annotations
from macrofactor_bridge.history import BlockAnnotation, DashboardAnnotations, save_dashboard_annotations
from tests.history_fixture import LAYOUT, irregular_workbook


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class DesktopGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["desktop-gui-test"])

    def test_anonymized_workflow_populates_preview_and_review_panels(self) -> None:
        window = BridgeWindow()
        self.addCleanup(dispose_widget, window)
        window.export_path.setText(str(ROOT / "tests" / "fixtures" / "macrofactor-log.xlsx"))
        window.workbook_path.setText(str(ROOT / "tests" / "fixtures" / "coach-template.xlsx"))
        window.config_path.setText(str(ROOT / "config" / "exercises.example.json"))
        window._use_latest_export_week()
        window.discover_button.click()
        window.preview_button.click()
        self.assertEqual(window.preview_table.rowCount(), 6)
        self.assertEqual(window.sheet_combo.currentText(), "Training Block")
        self.assertEqual(window.week_combo.currentText(), "Week 1")
        self.assertIn("Unmatched exercises: 1", window.review_panel.toPlainText())
        self.assertTrue(window.create_button.isEnabled())
        dispose_widget(window)

    def test_dashboard_is_first_with_clear_names_and_keyboard_navigation(self):
        window = BridgeWindow()
        self.addCleanup(dispose_widget, window)
        self.assertEqual([window.tabs.tabText(i) for i in range(window.tabs.count())],
                         ["Dashboard", "Update coach workbook"])
        self.assertEqual(window.tabs.currentIndex(), 0)
        self.assertIs(window.tabs.currentWidget(), window.dashboard_tab)
        views = window.history_analysis_tabs
        self.assertEqual([views.tabText(i) for i in range(views.count())],
                         ["Overview", "Training timeline", "Exercise trends", "Block summaries", "Compare blocks", "Training notes"])
        self.assertEqual([action.text() for action in views.secondary_actions.values()],
                         ["Block summaries", "Compare blocks", "Training notes"])
        self.assertEqual(window.history_save_annotation_button.text(), "Save training notes")
        window.resize(900, 680)
        window.show()
        self.app.processEvents()
        window.tabs.tabBar().setFocus()
        QTest.keyClick(window.tabs.tabBar(), Qt.Key.Key_Right)
        self.assertIs(window.tabs.currentWidget(), window.workbook_tab)
        self.assertTrue(window.discover_button.isVisible())
        self.assertEqual(window.discover_button.text(), "Load workbook weeks")
        self.assertEqual(window.width(), 900)
        self.assertEqual(window.height(), 680)
        self.assertFalse(window.create_button.isEnabled())
        QTest.keyClick(window.tabs.tabBar(), Qt.Key.Key_Left)
        self.assertIs(window.tabs.currentWidget(), window.dashboard_tab)
        views.secondary_actions[5].trigger()
        self.assertIs(views.currentWidget(), window.history_context_page)
        self.assertTrue(views.isTabVisible(5))

    def test_renamed_workbook_save_still_creates_only_a_new_copy(self):
        window = BridgeWindow()
        self.addCleanup(dispose_widget, window)
        window.tabs.setCurrentWidget(window.workbook_tab)
        export = ROOT / "tests/fixtures/macrofactor-log.xlsx"
        coach = ROOT / "tests/fixtures/coach-template.xlsx"
        before = [file_sha256(path) for path in (export, coach)]
        window.export_path.setText(str(export))
        window.workbook_path.setText(str(coach))
        window.config_path.setText(str(ROOT / "config/exercises.example.json"))
        window._use_latest_export_week()
        window.discover_button.click()
        window.preview_button.click()
        self.assertTrue(window.create_button.isEnabled())
        self.assertEqual(window.create_button.text(), "Save updated workbook copy…")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "updated-coach.xlsx"
            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(output), "")) as choose, \
                    patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Close), \
                    patch.object(window, "_show_error") as errors:
                window.create_button.click()
            errors.assert_not_called()
            self.assertEqual(choose.call_args.args[1], "Save updated workbook copy")
            self.assertTrue(output.is_file())
            self.assertNotEqual(file_sha256(output), before[1])
        self.assertEqual([file_sha256(path) for path in (export, coach)], before)

    def test_empty_day_marker_is_highlighted_yellow_in_preview(self) -> None:
        report = BridgeReport(
            "export.xlsx",
            "coach.xlsx",
            "Training Block",
            "Week 1",
            "2026-08-03",
            "2026-08-09",
        )
        review_note = "Day 3.5 has no matched MacroFactor session; review before sharing"
        report.proposed_writes.append(
            ProposedWrite(
                sheet="Training Block",
                week="Week 1",
                cell="J16",
                value="Skip",
                source_exercises=(),
                kind="empty_day_marker",
                fill_color="FFFFFF00",
                review_note=review_note,
            )
        )
        report.empty_day_markers.append(
            {"day": "Day 3.5", "cell": "J16", "reason": review_note}
        )

        window = BridgeWindow()
        self.addCleanup(dispose_widget, window)
        window._display_report(report)

        self.assertEqual(window.preview_table.rowCount(), 1)
        for column in range(window.preview_table.columnCount()):
            item = window.preview_table.item(0, column)
            self.assertIsNotNone(item)
            assert item is not None
            self.assertEqual(item.background().color().name(), "#ffff00")
            self.assertEqual(item.foreground().color().name(), "#101113")
        self.assertIn("Empty-day review markers: 1", window.review_panel.toPlainText())
        dispose_widget(window)

    def test_history_dashboard_loads_and_saves_private_week_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            annotations = Path(directory) / "annotations" / "history.json"
            window = BridgeWindow()
            self.addCleanup(dispose_widget, window)
            window.history_export_path.setText(
                str(ROOT / "tests" / "fixtures" / "macrofactor-log.xlsx")
            )
            window.history_workbook_path.setText(
                str(ROOT / "tests" / "fixtures" / "coach-template.xlsx")
            )
            window.history_config_path.setText(
                str(ROOT / "config" / "exercises.example.json")
            )
            window.history_annotations_path.setText(str(annotations))

            window._load_history()

            self.assertIn("sets", window.history_overview.text())
            self.assertGreater(window.history_block_table.rowCount(), 0)
            self.assertGreater(window.history_exercise_combo.count(), 0)
            self.assertGreater(window.history_trend_table.rowCount(), 0)
            self.assertTrue(window.history_save_annotation_button.isEnabled())
            self.assertEqual(window.history_block_combo.currentText(), "Training Block")

            window._set_combo_data(window.history_block_type_combo, "strength")
            window.history_start_known.setChecked(True)
            window.history_start_date.setDate(QDate(2026, 8, 3))
            window._set_combo_data(window.history_week_status_combo, "deload_reentry")
            window._set_combo_data(window.history_week_reason_combo, "vacation")
            window.history_affected_movements.setText("Squat, Deadlift")
            window._save_history_annotation()

            saved = load_dashboard_annotations(annotations)
            block = saved.blocks["Training Block"]
            week = block.weeks["Week 1"]
            self.assertEqual(block.block_type, "strength")
            self.assertEqual(week.reason, "vacation")
            self.assertEqual(week.affected_movements, ("Squat", "Deadlift"))
            self.assertIn("Saved private context", window.history_status.text())
            dispose_widget(window)

    def test_irregular_history_layout_survives_desktop_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coach = root / 'coach.xlsx'
            irregular_workbook(coach)
            path = root / 'history.json'
            save_dashboard_annotations(path, DashboardAnnotations({
                'Training Block': BlockAnnotation(week_layout=LAYOUT),
            }))
            window = BridgeWindow()
            self.addCleanup(dispose_widget, window)
            window.history_export_path.setText(str(ROOT / 'tests/fixtures/macrofactor-log.xlsx'))
            window.history_workbook_path.setText(str(coach))
            window.history_config_path.setText(str(ROOT / 'config/exercises.example.json'))
            window.history_annotations_path.setText(str(path))
            window._load_history()
            self.assertEqual([window.history_week_combo.itemText(i) for i in range(3)],
                             ['Week 10', 'Week 11', 'Week 12'])
            self.assertEqual(window.history_week_combo.count(), 3)
            window.history_week_combo.setCurrentText('Week 12')
            window.history_week_notes.setText('A synthetic date-labelled week')
            window._save_history_annotation()
            saved = load_dashboard_annotations(path).blocks['Training Block']
            self.assertEqual(saved.week_layout, LAYOUT)
            self.assertEqual(saved.weeks['Week 12'].notes, 'A synthetic date-labelled week')
            self.assertEqual(window.history_week_combo.currentText(), 'Week 12')

    def test_history_input_changes_invalidate_loaded_dashboard(self) -> None:
        fields = (
            "history_export_path",
            "history_workbook_path",
            "history_config_path",
            "history_annotations_path",
        )
        for field_name in fields:
            with self.subTest(field=field_name), tempfile.TemporaryDirectory() as directory:
                window = BridgeWindow()
                self.addCleanup(dispose_widget, window)
                window.history_export_path.setText(
                    str(ROOT / "tests" / "fixtures" / "macrofactor-log.xlsx")
                )
                window.history_workbook_path.setText(
                    str(ROOT / "tests" / "fixtures" / "coach-template.xlsx")
                )
                window.history_config_path.setText(
                    str(ROOT / "config" / "exercises.example.json")
                )
                window.history_annotations_path.setText(
                    str(Path(directory) / "history.json")
                )
                window._load_history()
                self.assertIsNotNone(window._history_dashboard)
                self.assertTrue(window.history_save_annotation_button.isEnabled())

                field = getattr(window, field_name)
                field.setText(f"{field.text()} ")

                self.assertIsNone(window._history_dashboard)
                self.assertFalse(window.history_save_annotation_button.isEnabled())
                self.assertEqual(window.history_block_table.rowCount(), 0)
                self.assertEqual(window.history_trend_table.rowCount(), 0)
                self.assertIn("inputs changed", window.history_status.text())
                dispose_widget(window)


if __name__ == "__main__":
    unittest.main()
