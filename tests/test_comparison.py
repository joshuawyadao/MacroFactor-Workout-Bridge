from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from macrofactor_bridge.comparison import ComparisonError, compare_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.history import DashboardAnnotations, build_history_dashboard, load_dashboard_annotations
from macrofactor_bridge.ooxml import file_sha256
from tests.comparison_fixture import comparison_inputs


CONFIG = Path(__file__).resolve().parents[1] / "config/exercises.example.json"


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.export, self.coach, self.path = comparison_inputs(Path(temporary.name))
        self.annotations = load_dashboard_annotations(self.path)
        self.dashboard = self.build()

    def build(self, annotations=None):
        return build_history_dashboard(self.export, self.coach, load_config(CONFIG),
                                       annotations or self.annotations)

    def compare(self, dashboard=None, annotations=None, exercise="Tempo Back Squat"):
        return compare_blocks(dashboard or self.dashboard, annotations or self.annotations,
                              exercise, "Training Block", "Archive")

    def test_relative_weeks_keep_labels_dates_gaps_and_unequal_lengths(self):
        before = [file_sha256(p) for p in (self.export, self.coach, self.path)]
        comparison = self.compare()
        first, second = comparison.first.weeks, comparison.second.weeks
        self.assertEqual([w.label for w in first], ["Week 10", "Week 11", "Week 12"])
        self.assertEqual([w.relative_week for w in first], [1, 2, 3])
        self.assertEqual((first[0].start, first[-1].end), (date(2026, 8, 3), date(2026, 8, 23)))
        self.assertEqual(second[0].start, date(2026, 8, 24))
        self.assertIsNone(comparison.paired_weeks()[1][1], "A shorter block must not gain fictitious weeks")
        self.assertEqual(first[1].coverage, "No logged sets")
        self.assertIsNone(first[1].metric("set_count"), "An absent log is not a zero or confirmed skip")
        self.assertEqual(first[2].metric("top_weight"), 0, "A logged zero remains a real zero")
        self.assertIsNone(first[2].metric("estimated_1rm"))
        self.assertEqual(before, [file_sha256(p) for p in (self.export, self.coach, self.path)])

    def test_metrics_reuse_exact_exercise_trends_without_cross_exercise_totals(self):
        comparison = self.compare()
        week = comparison.first.weeks[0]
        self.assertIs(week.trend, self.dashboard.trends_for("Tempo Back Squat")[0])
        self.assertEqual(week.metric("training_days"), 2)
        self.assertEqual(week.metric("set_count"), 2)
        self.assertEqual(week.metric("estimated_1rm"), Decimal("233.3"))
        carry = self.compare(exercise="Unmapped Carry")
        self.assertIsNone(carry.first.weeks[0].trend)
        self.assertEqual(carry.first.weeks[1].metric("set_count"), 1)
        with self.assertRaises(ComparisonError):
            self.compare(exercise="Squat")

    def test_saved_week_and_block_context_is_preserved_without_interpretation(self):
        comparison = self.compare()
        first = comparison.first
        self.assertEqual(first.notes, "Synthetic strength block")
        self.assertEqual(first.weeks[0].context.reason, "vacation")
        self.assertEqual(first.weeks[1].context.notes, "Confirmed skipped squat sessions")
        self.assertEqual(first.weeks[1].coverage, "No logged sets")
        self.assertEqual(first.weeks[2].context.affected_movements, ("Squat",))
        self.assertIsNone(comparison.second.weeks[0].context)

    def test_partial_and_outside_export_ranges_do_not_claim_complete_data(self):
        self.assertIn("partial date range", self.compare().second.weeks[0].coverage)
        for start in (date(2026, 7, 6), date(2026, 9, 7)):
            with self.subTest(start=start):
                blocks = dict(self.annotations.blocks)
                blocks["Archive"] = replace(blocks["Archive"], start_date=start)
                annotations = DashboardAnnotations(blocks)
                week = self.compare(self.build(annotations), annotations).second.weeks[0]
                self.assertEqual(week.coverage, "Outside export date range")
                self.assertIsNone(week.metric("set_count"))

    def test_same_undated_non_monday_and_overlapping_blocks_are_rejected(self):
        with self.assertRaisesRegex(ComparisonError, "different"):
            compare_blocks(self.dashboard, self.annotations, "Tempo Back Squat", "Archive", "Archive")
        for start, message in ((None, "confirm"), (date(2026, 8, 25), "Monday"),
                               (date(2026, 8, 17), "overlap")):
            with self.subTest(start=start):
                blocks = dict(self.annotations.blocks)
                blocks["Archive"] = replace(blocks["Archive"], start_date=start)
                annotations = DashboardAnnotations(blocks)
                with self.assertRaisesRegex(ComparisonError, message):
                    self.compare(self.build(annotations), annotations)

    def test_repeated_week_labels_are_not_silently_paired(self):
        blocks = tuple(replace(b, week_labels=("Week 10", "Week 10"))
                       if b.name == "Training Block" else b for b in self.dashboard.blocks)
        with self.assertRaisesRegex(ComparisonError, "distinct weeks"):
            self.compare(replace(self.dashboard, blocks=blocks))


if __name__ == "__main__":
    unittest.main()
