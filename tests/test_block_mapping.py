"""Invalid block metadata must never attribute completed sets to a coach week."""

from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from macrofactor_bridge.comparison import ComparisonError, compare_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.explorer import best_estimate, exercise_timeline, week_location
from macrofactor_bridge.history import (
    DashboardAnnotations, _load_history_sources, block_mapping_issues,
    build_history_dashboard, load_dashboard_annotations,
)
from macrofactor_bridge.progress import block_issue, block_reports
from tests.comparison_fixture import comparison_inputs


CONFIG = Path(__file__).resolve().parents[1] / "config/exercises.example.json"


class BlockMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.export, self.coach, path = comparison_inputs(Path(temporary.name))
        self.annotations = load_dashboard_annotations(path)
        self.config = load_config(CONFIG)

    def build(self, annotations=None):
        return build_history_dashboard(
            self.export, self.coach, self.config, annotations or self.annotations,
        )

    def test_shared_rule_rejects_blank_and_case_duplicate_weeks(self) -> None:
        monday = date(2026, 8, 3)
        self.assertEqual(block_mapping_issues(monday, ("Week 1", "Week 2"), overlapping=False), ())
        self.assertEqual(block_mapping_issues(None, (), overlapping=True),
                         ("missing_start", "invalid_weeks", "overlap"))
        for labels in ((), (" ",), ("Week 1", " week 1 ")):
            with self.subTest(labels=labels):
                self.assertIn("invalid_weeks", block_mapping_issues(monday, labels, overlapping=False))

    def test_tuesday_date_keeps_raw_history_but_maps_no_sets(self) -> None:
        baseline = self.build()
        blocks = dict(self.annotations.blocks)
        blocks["Training Block"] = replace(blocks["Training Block"], start_date=date(2026, 7, 28))
        dashboard = self.build(DashboardAnnotations(blocks))
        training = next(block for block in dashboard.blocks if block.name == "Training Block")

        self.assertEqual((dashboard.set_count, dashboard.training_day_count, len(dashboard.records)),
                         (baseline.set_count, baseline.training_day_count, len(baseline.records)))
        self.assertEqual((training.mapped_set_count, training.mapped_training_days), (0, 0))
        self.assertEqual(block_issue(dashboard, training), "Needs a Monday start")
        self.assertTrue(all(trend.block_name != training.name for trend in dashboard.weekly_trends))
        self.assertEqual(week_location(dashboard, exercise_timeline(dashboard, "Tempo Back Squat")[1]),
                         ("Unmapped", "—"))
        self.assertIsNone(best_estimate(dashboard, "Tempo Back Squat", training.name))
        self.assertTrue(any("invalid start date" in warning for warning in dashboard.warnings))
        self.assertIsNone(block_reports(dashboard)[0].sets_per_week)
        archive = next(block for block in dashboard.blocks if block.name == "Archive")
        self.assertGreater(archive.mapped_set_count, 0)

    def test_invalid_tuesday_range_also_disqualifies_overlapping_monday_block(self) -> None:
        blocks = dict(self.annotations.blocks)
        blocks["Archive"] = replace(blocks["Archive"], start_date=date(2026, 8, 18))
        annotations = DashboardAnnotations(blocks)
        dashboard = self.build(annotations)

        self.assertEqual(dashboard.overlapping_blocks, frozenset({"Training Block", "Archive"}))
        self.assertEqual([(block.name, block.mapped_set_count) for block in dashboard.blocks],
                         [("Training Block", 0), ("Archive", 0)])
        self.assertEqual(dashboard.set_count, len(dashboard.records))
        self.assertTrue(all(trend.block_name is None for trend in dashboard.weekly_trends))
        training = next(block for block in dashboard.blocks if block.name == "Training Block")
        self.assertEqual(block_issue(dashboard, training), "Overlapping block dates")
        with self.assertRaisesRegex(ComparisonError, "overlap"):
            compare_blocks(dashboard, annotations, "Tempo Back Squat", "Training Block", "Archive")

    def test_duplicate_discovered_labels_are_not_attributed(self) -> None:
        original = _load_history_sources

        def duplicated(*args, **kwargs):
            sources = original(*args, **kwargs)
            blocks = tuple(
                replace(block, weeks=(block.weeks[0], replace(block.weeks[1], label=" week 10 "), *block.weeks[2:]))
                if block.name == "Training Block" else block
                for block in sources.blocks
            )
            return replace(sources, blocks=blocks)

        with patch("macrofactor_bridge.history._load_history_sources", side_effect=duplicated):
            dashboard = self.build()
        training = next(block for block in dashboard.blocks if block.name == "Training Block")

        self.assertEqual((training.mapped_set_count, training.mapped_training_days), (0, 0))
        self.assertEqual(block_issue(dashboard, training), "Needs unique coach weeks")
        self.assertTrue(all(trend.block_name != training.name for trend in dashboard.weekly_trends))
        self.assertEqual(dashboard.set_count, len(dashboard.records))
        self.assertEqual(week_location(dashboard, exercise_timeline(dashboard, "Tempo Back Squat")[1]),
                         ("Unmapped", "—"))

    def test_block_without_weeks_does_not_invent_an_overlapping_date_range(self) -> None:
        original = _load_history_sources
        blocks = dict(self.annotations.blocks)
        blocks["Archive"] = replace(blocks["Archive"], start_date=blocks["Training Block"].start_date)

        def without_weeks(*args, **kwargs):
            sources = original(*args, **kwargs)
            return replace(sources, blocks=tuple(
                replace(block, weeks=()) if block.name == "Archive" else block
                for block in sources.blocks
            ))

        with patch("macrofactor_bridge.history._load_history_sources", side_effect=without_weeks):
            dashboard = self.build(DashboardAnnotations(blocks))
        training, archive = dashboard.blocks
        self.assertEqual(dashboard.overlapping_blocks, frozenset())
        self.assertGreater(training.mapped_set_count, 0)
        self.assertEqual(archive.mapped_set_count, 0)
        self.assertEqual(block_issue(dashboard, archive), "Needs unique coach weeks")


if __name__ == "__main__":
    unittest.main()
