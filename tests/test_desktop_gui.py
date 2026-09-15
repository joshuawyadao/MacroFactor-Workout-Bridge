from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

if HAS_QT:
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication

    from macrofactor_bridge.desktop import BridgeWindow

from macrofactor_bridge.models import BridgeReport, ProposedWrite
from macrofactor_bridge.history import load_dashboard_annotations


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class DesktopGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["desktop-gui-test"])

    def test_anonymized_workflow_populates_preview_and_review_panels(self) -> None:
        window = BridgeWindow()
        window.export_path.setText(str(ROOT / "tests" / "fixtures" / "macrofactor-log.xlsx"))
        window.workbook_path.setText(str(ROOT / "tests" / "fixtures" / "coach-template.xlsx"))
        window.config_path.setText(str(ROOT / "config" / "exercises.example.json"))
        window._use_latest_export_week()
        window._discover_targets()
        window._preview()
        self.assertEqual(window.preview_table.rowCount(), 6)
        self.assertEqual(window.sheet_combo.currentText(), "Training Block")
        self.assertEqual(window.week_combo.currentText(), "Week 1")
        self.assertIn("Unmatched exercises: 1", window.review_panel.toPlainText())
        self.assertTrue(window.create_button.isEnabled())
        window.close()

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
        window._display_report(report)

        self.assertEqual(window.preview_table.rowCount(), 1)
        for column in range(window.preview_table.columnCount()):
            item = window.preview_table.item(0, column)
            self.assertIsNotNone(item)
            assert item is not None
            self.assertEqual(item.background().color().name(), "#ffff00")
        self.assertIn("Empty-day review markers: 1", window.review_panel.toPlainText())
        window.close()

    def test_history_dashboard_loads_and_saves_private_week_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            annotations = Path(directory) / "annotations" / "history.json"
            window = BridgeWindow()
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
            window.close()

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
                window.close()


if __name__ == "__main__":
    unittest.main()
