from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from macrofactor_bridge.desktop import BridgeWindow

from macrofactor_bridge.models import BridgeReport, ProposedWrite


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


if __name__ == "__main__":
    unittest.main()
