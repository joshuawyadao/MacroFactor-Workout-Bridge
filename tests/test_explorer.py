from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from macrofactor_bridge.config import load_config
from macrofactor_bridge.explorer import best_estimate, default_exercise, exercise_names, exercise_timeline, week_location
from macrofactor_bridge.history import build_history_dashboard, load_dashboard_annotations
from macrofactor_bridge.importers import ExerciseLogImport
from tests.comparison_fixture import comparison_inputs

ROOT = Path(__file__).resolve().parents[1]


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        export, coach, annotations = comparison_inputs(Path(temporary.name))
        self.dashboard = build_history_dashboard(export, coach, load_config(ROOT / "config/exercises.example.json"),
                                                 load_dashboard_annotations(annotations))

    def test_calendar_includes_gaps_and_unmapped_weeks_without_zero_filling(self):
        weeks = exercise_timeline(self.dashboard, "Tempo Back Squat")
        self.assertEqual([w.start for w in weeks], [date(2026, 7, 27), date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17), date(2026, 8, 24)])
        self.assertEqual([w.metric("top_weight") for w in weeks], [None, 210, None, 0, 500])
        self.assertEqual(week_location(self.dashboard, weeks[0]), ("Unmapped", "—"))
        self.assertEqual(week_location(self.dashboard, weeks[2]), ("Training Block", "Week 11"))
        self.assertIs(weeks[1].trend, self.dashboard.trends_for("Tempo Back Squat")[0])

    def test_recent_ranges_are_whole_weeks_anchored_to_export_not_today(self):
        weeks = exercise_timeline(self.dashboard, "Tempo Back Squat", 4)
        self.assertEqual(weeks[0].start, date(2026, 8, 3))
        self.assertEqual(weeks[-1].start, date(2026, 8, 24))
        self.assertEqual(len(exercise_timeline(self.dashboard, "Tempo Back Squat", 24)), 5)
        with self.assertRaises(ValueError):
            exercise_timeline(self.dashboard, "Tempo Back Squat", -1)

    def test_filters_and_missing_exercises(self):
        self.assertEqual(exercise_names(self.dashboard, "Squat", " TEMPO "), ("Tempo Back Squat",))
        self.assertEqual(exercise_names(self.dashboard, "Bench"), ())
        self.assertEqual(exercise_names(self.dashboard, query="carry"), ("Unmapped Carry",))
        self.assertEqual(exercise_timeline(self.dashboard, "Not an exercise"), ())
        self.assertEqual(default_exercise(self.dashboard, ()), "")

    def test_variations_are_not_combined_and_most_recent_one_is_default(self):
        example = self.dashboard.trends_for("Tempo Back Squat")[0]
        summary = self.dashboard.exercises[0]
        extra = replace(example, exercise="Barbell Back Squat", week_start=date(2026, 8, 31), estimated_1rm=Decimal(900))
        dashboard = replace(self.dashboard, last_workout=date(2026, 9, 1),
                            exercises=self.dashboard.exercises + (replace(summary, exercise="Barbell Back Squat"),),
                            weekly_trends=self.dashboard.weekly_trends + (extra,))
        self.assertEqual(default_exercise(dashboard, exercise_names(dashboard, "Squat")), "Barbell Back Squat")
        self.assertEqual(default_exercise(replace(dashboard, records=()), exercise_names(dashboard, "Squat")),
                         "Barbell Back Squat", "Summary-only dashboards retain weekly recency as a fallback")
        self.assertEqual(best_estimate(dashboard, "Tempo Back Squat", "Training Block"), Decimal("233.3"))
        self.assertEqual(best_estimate(dashboard, "Barbell Back Squat", "Training Block"), 900)
        self.assertIsNone(best_estimate(dashboard, "Not an exercise", "Training Block"))

    def test_default_variation_uses_actual_dates_and_alphabetical_same_day_ties(self):
        record = self.dashboard.records[1]
        for tempo_date, expected in ((date(2026, 8, 9), "Tempo Back Squat"),
                                     (date(2026, 8, 3), "Barbell Back Squat")):
            with self.subTest(tempo_date=tempo_date):
                records = (
                    replace(record, exercise="Tempo Back Squat", workout_date=tempo_date),
                    replace(record, source_row=record.source_row + 1,
                            exercise="Barbell Back Squat", workout_date=date(2026, 8, 3)),
                )
                dashboard = build_history_dashboard(
                    ROOT / "unused.csv", ROOT / "tests/fixtures/coach-template.xlsx",
                    load_config(ROOT / "config/exercises.example.json"),
                    imported=ExerciseLogImport(records, ()),
                )
                names = tuple(reversed(exercise_names(dashboard, "Squat")))
                self.assertEqual(default_exercise(dashboard, names), expected)

    def test_ambiguous_or_undated_blocks_do_not_supply_missing_week_context(self):
        week = exercise_timeline(self.dashboard, "Tempo Back Squat")[2]
        dashboard = replace(self.dashboard, overlapping_blocks=frozenset({"Training Block"}))
        self.assertEqual(week_location(dashboard, week), ("Unmapped", "—"))
        dashboard = replace(self.dashboard, blocks=tuple(replace(b, start_date=None) for b in self.dashboard.blocks))
        self.assertEqual(week_location(dashboard, week), ("Unmapped", "—"))


if __name__ == "__main__":
    unittest.main()
