from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from macrofactor_bridge.config import load_config
from macrofactor_bridge.history import build_history_dashboard, load_dashboard_annotations
from macrofactor_bridge.progress import (
    block_reports, calendar_weeks, exercise_workload, full_weeks,
    sets_for_week, week_context, weekly_workload,
)
from tests.comparison_fixture import comparison_inputs

ROOT = Path(__file__).resolve().parents[1]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        export, coach, annotations = comparison_inputs(Path(temporary.name))
        self.annotations = load_dashboard_annotations(annotations)
        self.dashboard = build_history_dashboard(export, coach, load_config(ROOT / "config/exercises.example.json"), self.annotations)

    def test_block_averages_include_empty_exercise_weeks_not_future_or_partial_weeks(self):
        training, archive = block_reports(self.dashboard)
        self.assertEqual(training.complete_week_count, 3)
        self.assertEqual(training.sets_per_week, Decimal(4) / 3)
        self.assertEqual(training.days_per_week, Decimal(4) / 3)
        self.assertEqual(training.best_estimate(self.dashboard, "Tempo Back Squat"), Decimal("233.3"))
        self.assertIsNone(training.best_estimate(self.dashboard, "Barbell Back Squat"))
        self.assertEqual(archive.complete_week_count, 0)
        self.assertIsNone(archive.sets_per_week)
        self.assertIn("Partial", archive.coverage)
        # Partial-week performance is still visible, just not used in workload averages.
        self.assertEqual(archive.best_estimate(self.dashboard, "Tempo Back Squat"), Decimal("583.3"))

    def test_days_are_distinct_not_summed_across_exercises(self):
        record = self.dashboard.records[1]
        dashboard = replace(self.dashboard, records=self.dashboard.records + (replace(record, exercise="Another lift"),))
        self.assertEqual(block_reports(dashboard)[0].days_per_week, Decimal(4) / 3)

    def test_range_and_boundary_averages_exclude_partial_first_week(self):
        dashboard = replace(self.dashboard, first_workout=date(2026, 8, 4))
        report = block_reports(dashboard)[0]
        self.assertEqual(report.complete_week_count, 2)
        self.assertEqual(report.sets_per_week, 1)
        self.assertIn("Partial", report.coverage)
        self.assertEqual(len(calendar_weeks(dashboard, 1)), 1)
        self.assertEqual(len(block_reports(dashboard, 1)), 1)
        with self.assertRaises(ValueError):
            calendar_weeks(dashboard, -1)

    def test_invalid_or_outside_blocks_never_show_fabricated_zero_averages(self):
        first = self.dashboard.blocks[0]
        for changed in (replace(first, start_date=None), replace(first, start_date=date(2026, 8, 4)),
                        replace(first, week_labels=("Week 1", "Week 1"))):
            report = block_reports(replace(self.dashboard, blocks=(changed,)))[0]
            self.assertTrue(report.issue)
            self.assertIsNone(report.sets_per_week)
            self.assertIsNone(report.best_estimate(self.dashboard, "Tempo Back Squat"))
        report = block_reports(replace(self.dashboard, blocks=(first,), overlapping_blocks=frozenset({first.name})))[0]
        self.assertIn("Overlapping", report.issue)
        report = block_reports(replace(self.dashboard, blocks=(replace(first, start_date=date(2020, 1, 6)),)))[0]
        self.assertEqual(report.coverage, "Outside export date range")
        self.assertIsNone(report.sets_per_week)

    def test_workload_uses_full_weeks_and_retains_no_log_gaps(self):
        weeks = calendar_weeks(self.dashboard)
        self.assertEqual(len(full_weeks(self.dashboard, weeks)), 4)
        self.assertEqual(weekly_workload(self.dashboard, weeks), (1, 2, 1, 1, 2))
        workload = dict(exercise_workload(self.dashboard, weeks))
        self.assertEqual(workload["Tempo Back Squat"], Decimal("0.75"))
        self.assertEqual(workload["Unmapped Carry"], Decimal("0.5"))
        empty = date(2026, 8, 10)
        dashboard = replace(self.dashboard, weekly_trends=tuple(t for t in self.dashboard.weekly_trends if t.week_start != empty))
        self.assertIsNone(weekly_workload(dashboard, weeks)[2])
        self.assertEqual(dict(exercise_workload(dashboard, weeks))["Unmapped Carry"], Decimal("0.25"))

    def test_set_drilldown_preserves_zero_load_rir_missing_and_source_rows(self):
        records = sets_for_week(self.dashboard, date(2026, 8, 3), "Tempo Back Squat")
        self.assertEqual(len(records), 2)
        self.assertEqual([r.weight for r in records], [200, 210])
        self.assertTrue(all(r.rir is None for r in records))
        self.assertEqual(len({r.source_row for r in records}), 2)
        self.assertEqual(sets_for_week(self.dashboard, date(2026, 8, 17))[0].weight, 0)
        self.assertEqual(sets_for_week(self.dashboard, date(2026, 8, 10), "Tempo Back Squat"), ())

    def test_context_is_saved_not_inferred_from_load(self):
        self.assertIn("Return after travel", week_context(self.dashboard, self.annotations, date(2026, 8, 3)))
        self.assertIn("Injury", week_context(self.dashboard, self.annotations, date(2026, 8, 17)))
        self.assertEqual(week_context(self.dashboard, self.annotations, date(2026, 8, 24)), "")


if __name__ == "__main__":
    unittest.main()
