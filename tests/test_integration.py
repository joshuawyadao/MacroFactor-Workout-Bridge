from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import load_config
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.ooxml import XlsxPackage, file_sha256
from macrofactor_bridge.service import apply_changes, build_preview
from macrofactor_bridge.workbook import discover_workbook


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = ROOT / "config" / "exercises.example.json"
COACH = FIXTURES / "coach-template.xlsx"
LOG = FIXTURES / "macrofactor-log.xlsx"


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG)

    def preview(self):
        return build_preview(
            LOG,
            COACH,
            self.config,
            "Training Block",
            "Week 1",
            date(2026, 8, 3),
            date(2026, 8, 9),
        )

    def test_discovers_sheet_week_and_result_column_from_labels(self) -> None:
        sheets = discover_workbook(COACH, self.config)
        training = next(sheet for sheet in sheets if sheet.name == "Training Block")
        self.assertEqual(training.exercise_header_cell, "D3")
        self.assertEqual([(week.label, week.result_column) for week in training.weeks], [("Week 1", 10), ("Week 2", 12)])

    def test_preview_formats_proposals_and_reports_conservative_exceptions(self) -> None:
        report = self.preview()
        proposals = {proposal.cell: proposal.value for proposal in report.proposed_writes}
        self.assertEqual(proposals["J5"], "200 x 8, 7; 180 x 10")
        self.assertEqual(proposals["J6"], "0 x 10, 9")
        self.assertEqual(proposals["J7"], "160 x 10+3+2")
        self.assertEqual(proposals["J8"], "100 x 8→70 x 10")
        self.assertEqual(proposals["J9"], "50 x 10/60 x 12")
        self.assertEqual(proposals["J10"], "45s x 12")
        self.assertEqual(len(report.zero_rep_rows), 1)
        self.assertEqual(len(report.unmatched_exercises), 1)
        self.assertEqual(len(report.ambiguous_matches), 1)
        self.assertEqual(len(report.occupied_cells), 1)
        self.assertEqual(len(report.skipped_rows), 1)
        self.assertNotIn("skipped workout", json.dumps(report.to_dict()).lower())

    def test_apply_changes_only_target_sheet_and_keeps_source_unchanged(self) -> None:
        before_hash = file_sha256(COACH)
        export_before_hash = file_sha256(LOG)
        before = XlsxPackage(COACH).sheet_snapshot("Training Block")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coach-output.xlsx"
            report = apply_changes(self.preview(), self.config, output)
            self.assertTrue(output.exists())
            self.assertEqual(file_sha256(COACH), before_hash)
            self.assertEqual(file_sha256(LOG), export_before_hash)
            self.assertEqual(report.source_hash_before, report.source_hash_after)
            self.assertEqual(report.export_hash_before, report.export_hash_after)
            self.assertEqual(report.validation["unrelated_members_changed"], [])
            self.assertTrue(report.validation["zip_members_identical"])

            after = XlsxPackage(output).sheet_snapshot("Training Block")
            self.assertEqual(after.cells["J5"].value, "200 x 8, 7; 180 x 10")
            self.assertEqual(after.cells["J5"].style, before.cells["J5"].style)
            self.assertEqual(after.cells["J13"].value, "existing result")
            self.assertEqual(after.cells["J14"].formula, before.cells["J14"].formula)
            self.assertEqual(after.cells["N5"].formula, before.cells["N5"].formula)
            self.assertEqual(after.merges, before.merges)

            source_package = XlsxPackage(COACH)
            with zipfile.ZipFile(COACH) as source_zip, zipfile.ZipFile(output) as output_zip:
                changed_path = source_package.sheet_by_name("Training Block").path
                differences = [
                    name
                    for name in source_zip.namelist()
                    if source_zip.read(name) != output_zip.read(name)
                ]
                self.assertEqual(differences, [changed_path])

    def test_apply_refuses_to_overwrite_an_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "already-there.xlsx"
            output.write_bytes(b"do not replace")
            with self.assertRaisesRegex(ValueError, "Output already exists"):
                apply_changes(self.preview(), self.config, output)
            self.assertEqual(output.read_bytes(), b"do not replace")

    def test_accepts_csv_and_xlsx_exports(self) -> None:
        xlsx_records = load_exercise_log(LOG)
        self.assertGreater(len(xlsx_records), 10)
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "export.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Date": "2026-08-03",
                        "Workout": "Example",
                        "Exercise": "Tempo Back Squat",
                        "Set Type": "Standard Set",
                        "Weight (lbs)": "200",
                        "Reps": "8",
                    }
                )
            csv_records = load_exercise_log(csv_path)
            self.assertEqual(len(csv_records), 1)
            self.assertEqual(csv_records[0].exercise, "Tempo Back Squat")

    def test_cli_writes_machine_readable_preview_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "preview.json"
            exit_code = main(
                [
                    "preview",
                    "--export",
                    str(LOG),
                    "--workbook",
                    str(COACH),
                    "--config",
                    str(CONFIG),
                    "--sheet",
                    "Training Block",
                    "--week",
                    "Week 1",
                    "--from-date",
                    "2026-08-03",
                    "--to-date",
                    "2026-08-09",
                    "--report",
                    str(report_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["sheet"], "Training Block")
            self.assertEqual(len(payload["proposed_writes"]), 6)


if __name__ == "__main__":
    unittest.main()
