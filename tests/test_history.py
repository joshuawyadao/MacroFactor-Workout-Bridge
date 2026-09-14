from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from macrofactor_bridge.config import load_config
from macrofactor_bridge.history import (
    BlockAnnotation,
    DashboardAnnotations,
    HistoryError,
    WeekAnnotation,
    build_history_dashboard,
    default_dashboard_annotations_path,
    load_dashboard_annotations,
    save_dashboard_annotations,
    update_block_annotation,
    update_week_annotation,
    _ordered_week_labels,
)
from macrofactor_bridge.importers import ImportError, load_exercise_log


ROOT = Path(__file__).resolve().parents[1]
COACH = ROOT / "tests" / "fixtures" / "coach-template.xlsx"
CONFIG = ROOT / "config" / "exercises.example.json"


def write_history_export(path: Path) -> None:
    rows = (
        {
            "Date": "2026-08-03",
            "Workout Duration": "3600",
            "Workout": "Day One",
            "Exercise": "Tempo Back Squat",
            "Set Type": "Standard Set",
            "Weight (lbs)": "200",
            "Reps": "5",
            "RIR": "2",
        },
        {
            "Date": "2026-08-03",
            "Workout Duration": "3600",
            "Workout": "Day One",
            "Exercise": "Tempo Back Squat",
            "Set Type": "Standard Set",
            "Weight (lbs)": "205",
            "Reps": "3",
            "RIR": "1",
        },
        {
            "Date": "2026-08-03",
            "Workout Duration": "3600",
            "Workout": "Day One",
            "Exercise": "Unmapped Carry",
            "Set Type": "Standard Set",
            "Weight (lbs)": "50",
            "Reps": "10",
            "RIR": "",
        },
        {
            "Date": "2026-08-10",
            "Workout Duration": "1:15:00",
            "Workout": "Day One",
            "Exercise": "Tempo Back Squat",
            "Set Type": "Standard Set",
            "Weight (lbs)": "210",
            "Reps": "2",
            "RIR": "",
        },
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class HistoryTests(unittest.TestCase):
    def test_numeric_coach_week_labels_are_ordered_chronologically(self) -> None:
        self.assertEqual(
            _ordered_week_labels(("Week 8", "Week 9", "Week 6", "Week 7")),
            ("Week 6", "Week 7", "Week 8", "Week 9"),
        )
        descriptive = ("Week 2 (heavy)", "Week 1 (volume)")
        self.assertEqual(
            _ordered_week_labels(descriptive),
            ("Week 1 (volume)", "Week 2 (heavy)"),
        )

    def test_optional_rir_and_workout_duration_are_imported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "history.csv"
            write_history_export(export)

            records = load_exercise_log(export)

        self.assertEqual(records[0].rir, Decimal("2"))
        self.assertEqual(records[0].workout_duration_seconds, Decimal("3600"))
        self.assertIsNone(records[2].rir)
        self.assertEqual(records[3].workout_duration_seconds, Decimal("4500"))

    def test_optional_history_columns_remain_optional_and_invalid_rir_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            minimal = root / "minimal.csv"
            minimal.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2026-08-03,Day One,Tempo Back Squat,Standard Set,200,5\n",
                encoding="utf-8",
            )
            record = load_exercise_log(minimal)[0]
            self.assertIsNone(record.rir)
            self.assertIsNone(record.workout_duration_seconds)

            invalid = root / "invalid.csv"
            invalid.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps,RIR\n"
                "2026-08-03,Day One,Tempo Back Squat,Standard Set,200,5,11\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ImportError, "RIR must be"):
                load_exercise_log(invalid)

    def test_dashboard_summarizes_calendar_trends_and_uses_session_duration_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "history.csv"
            write_history_export(export)
            annotations = DashboardAnnotations(
                blocks={
                    "Training Block": BlockAnnotation(
                        block_type="strength",
                        start_date=date(2026, 8, 3),
                        weeks={
                            "Week 1": WeekAnnotation(
                                status="deload_reentry", reason="vacation"
                            )
                        },
                    )
                }
            )

            dashboard = build_history_dashboard(
                export, COACH, load_config(CONFIG), annotations
            )

        self.assertEqual(
            (dashboard.first_workout, dashboard.last_workout),
            (date(2026, 8, 3), date(2026, 8, 10)),
        )
        self.assertEqual(dashboard.set_count, 4)
        self.assertEqual(dashboard.workout_count, 2)
        self.assertEqual(dashboard.training_day_count, 2)
        self.assertEqual(dashboard.rir_set_count, 2)
        self.assertEqual(dashboard.duration_session_count, 2)
        self.assertEqual(dashboard.total_duration_seconds, Decimal("8100"))
        block = next(item for item in dashboard.blocks if item.name == "Training Block")
        self.assertEqual(block.block_type, "strength")
        self.assertEqual(block.annotated_week_count, 1)
        self.assertEqual(block.mapped_set_count, 4)
        self.assertEqual(block.mapped_training_days, 2)
        trends = dashboard.trends_for("Tempo Back Squat")
        self.assertEqual(len(trends), 2)
        self.assertEqual(trends[0].estimated_1rm, Decimal("233.3"))
        self.assertEqual((trends[0].block_name, trends[0].block_week), ("Training Block", "Week 1"))
        self.assertEqual((trends[1].block_name, trends[1].block_week), ("Training Block", "Week 2"))
        summary = next(item for item in dashboard.exercises if item.exercise == "Tempo Back Squat")
        self.assertEqual(summary.set_count, 3)
        self.assertEqual(summary.rir_set_count, 2)
        self.assertNotEqual(summary.trend, "—")

    def test_unknown_block_dates_are_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "history.csv"
            write_history_export(export)
            dashboard = build_history_dashboard(
                export, COACH, load_config(CONFIG), DashboardAnnotations()
            )

        self.assertTrue(all(trend.block_name is None for trend in dashboard.weekly_trends))
        self.assertTrue(any("no confirmed start date" in item for item in dashboard.warnings))

    def test_estimated_1rm_uses_only_standard_sets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "history.csv"
            export.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2026-08-03,Day One,Tempo Back Squat,Warm Up Set,315,1\n"
                "2026-08-03,Day One,Tempo Back Squat,Standard Set,200,5\n",
                encoding="utf-8",
            )

            dashboard = build_history_dashboard(
                export, COACH, load_config(CONFIG), DashboardAnnotations()
            )

        trend = dashboard.trends_for("Tempo Back Squat")[0]
        self.assertEqual(trend.estimated_1rm, Decimal("233.3"))

    def test_annotations_round_trip_and_keep_vacation_separate_from_injury(self) -> None:
        annotations = update_block_annotation(
            DashboardAnnotations(),
            "Training Block",
            block_type="strength",
            start_date=date(2026, 8, 3),
            notes="Synthetic block note",
        )
        annotations = update_week_annotation(
            annotations,
            "Training Block",
            "Week 1",
            status="deload_reentry",
            reason="vacation",
            affected_movements=("Squat",),
            notes="Travel week",
        )
        annotations = update_week_annotation(
            annotations,
            "Training Block",
            "Week 2",
            status="modified",
            reason="injury",
            affected_movements=("Bench",),
            notes="Substitution",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotations" / "history.json"
            saved = save_dashboard_annotations(path, annotations)
            loaded = load_dashboard_annotations(saved)

        self.assertEqual(loaded, annotations)
        self.assertEqual(loaded.blocks["Training Block"].weeks["Week 1"].reason, "vacation")
        self.assertEqual(loaded.blocks["Training Block"].weeks["Week 2"].reason, "injury")

    def test_annotation_path_uses_private_workspace_and_refuses_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            workbook = root / "archive" / "coach" / "coach.xlsx"
            expected = root / "annotations" / "workout-history.json"
            self.assertEqual(default_dashboard_annotations_path(workbook), expected)

            target = root / "outside.json"
            target.parent.mkdir(parents=True)
            target.write_text("{}", encoding="utf-8")
            expected.parent.mkdir(parents=True)
            expected.symlink_to(target)
            with self.assertRaisesRegex(HistoryError, "symlinked"):
                save_dashboard_annotations(expected, DashboardAnnotations())

    def test_annotation_path_fallback_uses_ignored_private_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workbook = Path(directory) / "coach.xlsx"

            fallback = default_dashboard_annotations_path(workbook)

        self.assertEqual(fallback.name, "coach-workout-history.private.json")
        self.assertIn("*.private.json", (ROOT / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
