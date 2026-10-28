"""Synthetic desktop coverage for explicit rep-count confirmation."""

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
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    from tests.gui_support import dispose_widget
    from macrofactor_bridge.desktop import BridgeWindow
    from macrofactor_bridge.rep_counts_view import RepCountsDialog

from macrofactor_bridge.models import BridgeReport, ProposedWrite
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.ooxml import file_sha256
from macrofactor_bridge.rep_counts import apply_rep_counts, rep_count_entry, save_rep_counts


def _entry(row: int, exported: str, *, full=None, partial=None) -> dict:
    return {
        "source_row": row,
        "workout_date": "2026-10-19",
        "workout": "Day 1",
        "exercise": "Rear Fly",
        "set_type": "Normal",
        "weight": "50",
        "exported_reps": exported,
        "full_reps": full,
        "partial_reps": partial,
    }


def _report(export: Path, counts_path: Path) -> BridgeReport:
    report = BridgeReport(
        str(export), "coach.xlsx", "Training Block", "Week 4",
        "2026-10-19", "2026-10-25",
    )
    report.rep_count_sets = [_entry(2, "9.33"), _entry(3, "10")]
    report.rep_counts_path = str(counts_path)
    report.preview_export_hash = file_sha256(export)
    report.proposed_writes.append(
        ProposedWrite("Training Block", "Week 4", "J2", "50 × 10", ("Rear Fly",))
    )
    return report


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class RepCountsGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication(["rep-count-gui-test"])

    def test_editor_requires_explicit_confirmation_and_supports_integer_override(self) -> None:
        dialog = RepCountsDialog([_entry(2, "9.33"), _entry(3, "10", full=8, partial=2)])
        self.addCleanup(dispose_widget, dialog)
        self.assertFalse(dialog.rows[0][1].isChecked())
        self.assertEqual(dialog.rows[0][2].value(), 0)
        self.assertEqual(dialog.rows[0][3].value(), 0)
        self.assertTrue(dialog.rows[1][1].isChecked())
        self.assertEqual((dialog.rows[1][2].value(), dialog.rows[1][3].value()), (8, 2))
        dialog.rows[0][1].setChecked(True)
        dialog.rows[0][2].setValue(8)
        dialog.rows[0][3].setValue(4)
        dialog.rows[1][2].setValue(10)
        dialog.rows[1][3].setValue(5)
        saved = dialog.entries()
        self.assertEqual((saved[0]["full_reps"], saved[0]["partial_reps"]), (8, 4))
        self.assertEqual((saved[1]["full_reps"], saved[1]["partial_reps"]), (10, 5))
        dialog.rows[0][1].setChecked(False)
        self.assertEqual((dialog.entries()[0]["full_reps"], dialog.entries()[0]["partial_reps"]), (None, None))
        dialog.rows[1][2].setValue(0)
        dialog.rows[1][3].setValue(0)
        with self.assertRaisesRegex(ValueError, "at least one"):
            dialog.entries()

    def test_invalid_save_keeps_editor_and_other_unsaved_edits(self) -> None:
        dialog = RepCountsDialog([_entry(2, "9.33"), _entry(3, "10")])
        self.addCleanup(dispose_widget, dialog)
        first, second = dialog.rows
        first[1].setChecked(True)
        second[1].setChecked(True)
        second[2].setValue(10)
        second[3].setValue(5)
        save = dialog.findChild(QPushButton, "saveCountsButton")
        # The named button is clicked directly so validation runs as it does in the UI.
        self.assertIsNotNone(save)
        save.click()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIn("at least one", dialog.validation_error.text())
        self.assertEqual((second[2].value(), second[3].value()), (10, 5))
        first[2].setValue(8)
        first[3].setValue(4)
        save.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(
            [(entry["full_reps"], entry["partial_reps"]) for entry in dialog.entries()],
            [(8, 4), (10, 5)],
        )

    def test_saved_count_outside_spinbox_range_is_rejected_without_clamping(self) -> None:
        with self.assertRaisesRegex(ValueError, "saved rep count exceeds"):
            RepCountsDialog([_entry(2, "9.33", full=2_147_483_648, partial=1)])

    def test_save_refresh_cancel_and_failed_refresh_invalidate_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / "export.csv"
            export.write_text("synthetic export", encoding="utf-8")
            expected = root.resolve() / "annotations" / "rep-counts" / f"{file_sha256(export)}.json"
            window = BridgeWindow(workspace_root=root)
            self.addCleanup(dispose_widget, window)
            self.assertEqual(window._rep_counts_path(str(export)), expected)
            window.export_path.setText(str(export))
            window.workbook_path.setText("coach.xlsx")
            window.sheet_combo.addItem("Training Block")
            window.week_combo.addItem("Week 4")
            report = _report(export, expected)
            with patch("macrofactor_bridge.desktop.build_preview", return_value=report):
                window._preview()
            self.assertTrue(window.rep_counts_button.isEnabled())
            self.assertTrue(window.create_button.isEnabled())
            self.assertIn("1 fractional set(s) awaiting confirmation", window.review_panel.toPlainText())

            with patch.object(RepCountsDialog, "exec", return_value=QDialog.DialogCode.Rejected), \
                    patch("macrofactor_bridge.desktop.save_rep_counts") as save:
                window._open_rep_counts_editor()
            save.assert_not_called()
            self.assertIs(window._report, report)

            def accept(dialog):
                dialog.rows[0][1].setChecked(True)
                dialog.rows[0][2].setValue(8)
                dialog.rows[0][3].setValue(4)
                return QDialog.DialogCode.Accepted

            with patch.object(RepCountsDialog, "exec", accept), \
                    patch("macrofactor_bridge.desktop.save_rep_counts") as save, \
                    patch("macrofactor_bridge.desktop.build_preview", return_value=report) as preview:
                window._open_rep_counts_editor()
            self.assertEqual(save.call_args.args[0:2], (str(expected), str(export)))
            self.assertEqual(save.call_args.args[2][0]["full_reps"], 8)
            self.assertEqual(save.call_args.args[2][0]["partial_reps"], 4)
            self.assertEqual(save.call_args.kwargs["expected_export_hash"], file_sha256(export))
            self.assertEqual(preview.call_args.kwargs["rep_counts_path"], expected)

            with patch.object(RepCountsDialog, "exec", accept), \
                    patch("macrofactor_bridge.desktop.save_rep_counts", side_effect=ValueError("stale counts")), \
                    patch.object(window, "_show_error") as errors:
                window._open_rep_counts_editor()
            self.assertIn("stale counts", str(errors.call_args.args[1]))
            self.assertIsNone(window._report)
            self.assertFalse(window.create_button.isEnabled())

            with patch("macrofactor_bridge.desktop.build_preview", return_value=report):
                window._preview()

            with patch("macrofactor_bridge.desktop.build_preview", side_effect=ValueError("broken")), \
                    patch.object(window, "_show_error"):
                window._preview()
            self.assertIsNone(window._report)
            self.assertFalse(window.rep_counts_button.isEnabled())
            self.assertFalse(window.create_button.isEnabled())
            self.assertFalse(window.save_report_button.isEnabled())

    def test_fallback_storage_uses_app_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / "export.csv"
            export.write_text("synthetic export", encoding="utf-8")
            window = BridgeWindow()
            self.addCleanup(dispose_widget, window)
            with patch("macrofactor_bridge.desktop.QStandardPaths") as paths:
                paths.writableLocation.return_value = str(root / "app")
                path = window._rep_counts_path(str(export))
            self.assertEqual(path, root / "app" / "rep-counts" / f"{file_sha256(export)}.json")
            with patch("macrofactor_bridge.desktop.QStandardPaths") as paths:
                paths.writableLocation.return_value = ""
                with self.assertRaisesRegex(ValueError, "managed workspace"):
                    window._rep_counts_path(str(export))

    def test_reopen_keeps_saved_counts_until_user_explicitly_removes_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = root / "log.csv"
            export.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2026-10-19,Day 1,Rear Fly,Standard Set,50,9.33\n",
                encoding="utf-8",
            )
            path = root / "counts.json"
            original = rep_count_entry(load_exercise_log(export)[0])
            save_rep_counts(
                path, export, [{**original, "full_reps": 8, "partial_reps": 4}],
                expected_export_hash=file_sha256(export),
            )
            reopened = rep_count_entry(
                apply_rep_counts(load_exercise_log(export), path, file_sha256(export))[0]
            )
            dialog = RepCountsDialog([reopened])
            self.addCleanup(dispose_widget, dialog)
            self.assertTrue(dialog.rows[0][1].isChecked())
            self.assertEqual((dialog.rows[0][2].value(), dialog.rows[0][3].value()), (8, 4))
            self.assertEqual((dialog.entries()[0]["full_reps"], dialog.entries()[0]["partial_reps"]), (8, 4))
            dialog.rows[0][1].setChecked(False)
            save_rep_counts(path, export, dialog.entries(), expected_hash=file_sha256(path))
            removed = rep_count_entry(
                apply_rep_counts(load_exercise_log(export), path, file_sha256(export))[0]
            )
            self.assertIsNone(removed["full_reps"])
            self.assertIsNone(removed["partial_reps"])
            again = RepCountsDialog([removed])
            self.addCleanup(dispose_widget, again)
            self.assertFalse(again.rows[0][1].isChecked())
            self.assertEqual((again.rows[0][2].value(), again.rows[0][3].value()), (0, 0))


if __name__ == "__main__":
    unittest.main()
