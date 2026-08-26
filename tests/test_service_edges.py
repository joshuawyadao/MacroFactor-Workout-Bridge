from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from macrofactor_bridge.models import BridgeConfig, ExerciseRule
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage
from macrofactor_bridge.service import build_preview

from tests.helpers import rewrite_xlsx, transform_cell


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
COACH = FIXTURES / "coach-template.xlsx"
LOG = FIXTURES / "macrofactor-log.xlsx"


def rule(
    source: str,
    coach: str,
    *,
    group: str | None = None,
    order: int = 0,
) -> ExerciseRule:
    return ExerciseRule(
        canonical=source,
        source_aliases=(source,),
        coach_aliases=(coach,),
        weight_multiplier=Decimal("1"),
        superset_group=group,
        superset_order=order,
    )


def config(*rules: ExerciseRule) -> BridgeConfig:
    return BridgeConfig(
        exercise_header_labels=("Variation", "Exercise"),
        week_header_pattern=r"^week\s*\d+(?:\s*\([^)]*\))?$",
        rules=rules,
    )


class PreviewEdgeTests(unittest.TestCase):
    def write_csv(self, directory: str, rows: str) -> Path:
        path = Path(directory) / "log.csv"
        path.write_text(
            "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n" + rows,
            encoding="utf-8",
        )
        return path

    def preview(self, export: Path, mapping: BridgeConfig, workbook: Path = COACH):
        return build_preview(
            export,
            workbook,
            mapping,
            "Training Block",
            "Week 1",
            date(2026, 8, 3),
            date(2026, 8, 9),
        )

    def test_rejects_invalid_date_ranges_and_workbook_selections(self) -> None:
        mapping = config(rule("Tempo Back Squat", "Tempo Squat"))
        with self.assertRaisesRegex(ValueError, "to-date must be"):
            build_preview(
                LOG,
                COACH,
                mapping,
                "Training Block",
                "Week 1",
                date(2026, 8, 9),
                date(2026, 8, 3),
            )
        with self.assertRaisesRegex(WorkbookError, "Worksheet not found"):
            build_preview(
                LOG,
                COACH,
                mapping,
                "Missing Sheet",
                "Week 1",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )
        with self.assertRaisesRegex(WorkbookError, "Week 'Week 99' was not found"):
            build_preview(
                LOG,
                COACH,
                mapping,
                "Training Block",
                "Week 99",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )

    def test_reports_missing_fields_and_excludes_rows_outside_the_range(self) -> None:
        rows = (
            "2026-07-01,Lower,Tempo Back Squat,Standard Set,100,8\n"
            "2026-08-03,Lower,,Standard Set,100,8\n"
            "2026-08-03,Lower,Tempo Back Squat,,100,8\n"
            "2026-08-03,Lower,Tempo Back Squat,Standard Set,100,\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            report = self.preview(
                self.write_csv(directory, rows),
                config(rule("Tempo Back Squat", "Tempo Squat")),
            )
        self.assertEqual((report.rows_read, report.rows_in_range), (4, 3))
        self.assertEqual(
            {entry["reason"] for entry in report.skipped_rows},
            {"missing exercise", "missing set type", "missing reps"},
        )
        self.assertEqual(report.proposed_writes, [])

    def test_reports_an_exercise_repeated_across_workout_sessions(self) -> None:
        rows = (
            "2026-08-03,Lower A,Tempo Back Squat,Standard Set,100,8\n"
            "2026-08-05,Lower B,Tempo Back Squat,Standard Set,100,8\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            report = self.preview(
                self.write_csv(directory, rows),
                config(rule("Tempo Back Squat", "Tempo Squat")),
            )
        self.assertEqual(report.proposed_writes, [])
        self.assertIn("multiple workout sessions", report.ambiguous_matches[0]["reason"])
        self.assertEqual(len(report.ambiguous_matches[0]["sessions"]), 2)

    def test_reports_configured_exercise_missing_from_the_coach_sheet(self) -> None:
        rows = "2026-08-03,Lower,Tempo Back Squat,Standard Set,100,8\n"
        with tempfile.TemporaryDirectory() as directory:
            report = self.preview(
                self.write_csv(directory, rows),
                config(rule("Tempo Back Squat", "Not In Workbook")),
            )
        self.assertEqual(report.proposed_writes, [])
        self.assertIn("no exact configured coach alias", report.unmatched_exercises[0]["reason"])

    def test_refuses_multiple_exercises_sharing_a_cell_without_a_superset_group(self) -> None:
        rows = (
            "2026-08-03,Arms,Cable Curl,Standard Set,50,10\n"
            "2026-08-03,Arms,Cable Pressdown,Standard Set,60,12\n"
        )
        mapping = config(
            rule("Cable Curl", "Arm Superset"),
            rule("Cable Pressdown", "Arm Superset"),
        )
        with tempfile.TemporaryDirectory() as directory:
            report = self.preview(self.write_csv(directory, rows), mapping)
        self.assertEqual(report.proposed_writes, [])
        self.assertIn("without one shared superset group", report.ambiguous_matches[0]["reason"])

    def test_skips_a_target_cell_that_is_absent_from_the_workbook_xml(self) -> None:
        rows = "2026-08-03,Lower,Tempo Back Squat,Standard Set,100,8\n"
        mapping = config(rule("Tempo Back Squat", "Tempo Squat"))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            sheet_path = XlsxPackage(COACH).sheet_by_name("Training Block").path
            workbook = rewrite_xlsx(
                COACH,
                base / "missing-target.xlsx",
                {sheet_path: transform_cell("J5", remove=True)},
            )
            report = self.preview(self.write_csv(directory, rows), mapping, workbook)
        self.assertEqual(report.proposed_writes, [])
        self.assertIn("does not exist", report.skipped_rows[0]["reason"])


if __name__ == "__main__":
    unittest.main()
