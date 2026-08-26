from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import load_config
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.models import BridgeReport
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.service import apply_changes, build_preview
from macrofactor_bridge.workbook import discover_workbook

from tests.helpers import rewrite_xlsx, transform_cell


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

    def test_apply_refuses_when_preview_has_no_proposed_writes(self) -> None:
        report = BridgeReport(
            str(LOG),
            str(COACH),
            "Training Block",
            "Week 1",
            "2026-08-03",
            "2026-08-09",
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "unused.xlsx"
            with self.assertRaisesRegex(WorkbookError, "no proposed writes"):
                apply_changes(report, self.config, output)
            self.assertFalse(output.exists())

    def test_write_copy_rejects_unsafe_output_paths_and_stale_targets(self) -> None:
        package = XlsxPackage(COACH)
        sheet = package.sheet_by_name("Training Block")
        with self.assertRaisesRegex(WorkbookError, "different from the source"):
            package.write_copy(COACH, sheet, {})

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(WorkbookError, "must end in .xlsx"):
                package.write_copy(base / "output.txt", sheet, {})
            with self.assertRaisesRegex(WorkbookError, "does not exist"):
                package.write_copy(base / "missing-cell.xlsx", sheet, {"ZZ999": "value"})
            with self.assertRaisesRegex(WorkbookError, "no longer empty"):
                package.write_copy(base / "occupied-cell.xlsx", sheet, {"J13": "value"})

    def test_apply_refuses_when_a_previewed_target_becomes_occupied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            workbook = base / "coach.xlsx"
            workbook.write_bytes(COACH.read_bytes())
            report = build_preview(
                LOG,
                workbook,
                self.config,
                "Training Block",
                "Week 1",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )
            sheet_path = XlsxPackage(workbook).sheet_by_name("Training Block").path
            changed = rewrite_xlsx(
                workbook,
                base / "changed.xlsx",
                {sheet_path: transform_cell("J5", text="entered after preview")},
            )
            changed.replace(workbook)

            output = base / "output.xlsx"
            with self.assertRaisesRegex(WorkbookError, "no longer empty"):
                apply_changes(report, self.config, output)
            self.assertFalse(output.exists())

    def test_apply_detects_source_workbook_or_export_mutation_during_write(self) -> None:
        original_write_copy = XlsxPackage.write_copy
        for changed_input in ("workbook", "export"):
            with self.subTest(changed_input=changed_input):
                with tempfile.TemporaryDirectory() as directory:
                    base = Path(directory)
                    workbook = base / "coach.xlsx"
                    export = base / "log.xlsx"
                    workbook.write_bytes(COACH.read_bytes())
                    export.write_bytes(LOG.read_bytes())
                    report = build_preview(
                        export,
                        workbook,
                        self.config,
                        "Training Block",
                        "Week 1",
                        date(2026, 8, 3),
                        date(2026, 8, 9),
                    )

                    def write_then_mutate(
                        package: XlsxPackage,
                        output_path: str | Path,
                        sheet,
                        changes: dict[str, str],
                    ) -> None:
                        original_write_copy(package, output_path, sheet, changes)
                        changed_path = package.path if changed_input == "workbook" else export
                        changed_path.write_bytes(changed_path.read_bytes() + b"changed-during-apply")

                    message = "Source workbook changed" if changed_input == "workbook" else "export changed"
                    with patch.object(XlsxPackage, "write_copy", write_then_mutate):
                        with self.assertRaisesRegex(WorkbookError, message):
                            apply_changes(report, self.config, base / "output.xlsx")

    def test_apply_rejects_integrity_validation_failures(self) -> None:
        failures = (
            (
                {
                    "unrelated_members_changed": ["xl/styles.xml"],
                    "zip_members_identical": True,
                },
                "unrelated changed ZIP members",
            ),
            (
                {"unrelated_members_changed": [], "zip_members_identical": False},
                "changed ZIP member list",
            ),
        )
        for index, (validation, message) in enumerate(failures):
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / f"integrity-{index}.xlsx"
                    with patch(
                        "macrofactor_bridge.service.validate_copy_integrity",
                        return_value=validation,
                    ):
                        with self.assertRaisesRegex(WorkbookError, message):
                            apply_changes(self.preview(), self.config, output)

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
