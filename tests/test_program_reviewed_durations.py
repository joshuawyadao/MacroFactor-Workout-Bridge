from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macrofactor_bridge.ooxml import XlsxPackage
from macrofactor_bridge.program_batch import run_program_batch
from tests.test_program_duration import with_duration_columns
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_macrofactor_program_template, write_program_workbook


class ReviewedDurationBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach, self.template = self.root / "coach.xlsx", self.root / "template.xlsx"
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "notes_source": "reviewed", "preserve_coach_notes": False,
                        "defaults": {"set_type": "standard", "rir": 2}},
            "exercises": [{"canonical": "Old Exercise 1-1", "coach_aliases": ["Synthetic Hold"]}],
        }))
        write_macrofactor_program_template(self.template, day_row_counts=(1,), max_sets=2)
        with_duration_columns(self.template)

    def batch(self, target):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 7, name="Synthetic Hold", sets=2, reps=target, rest="90 sec",
                     week_one=None, week_two=None)
        write_program_workbook(self.coach, sheet_name="Synthetic", cells=cells,
                               merges=("J5:K5", "L5:M5"))
        return run_program_batch(self.coach, self.config, self.template, self.root / "batch", generate=True)

    def test_exact_duration_generates_in_reviewed_mode_without_notes(self):
        report = self.batch("30 sec")
        item, = report.results
        self.assertEqual(item["status"], "generated", item["issues"])
        self.assertTrue(item["source_audit"]["passed"])
        self.assertTrue(item["output_audit"]["passed"])
        cells = XlsxPackage(item["output"]).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (30, 30))
        self.assertIsNone(cells["F4"].value)
        self.assertIsNone(cells["D4"].value)

    def test_unsupported_target_still_blocks_when_notes_are_disabled(self):
        report = self.batch("Hold until tired")
        item, = report.results
        self.assertEqual(item["status"], "blocked")
        self.assertIn("source_audit_unsupported_reps", {issue["code"] for issue in item["issues"]})
        self.assertFalse(list((self.root / "batch").glob("*.xlsx")))


if __name__ == "__main__":
    unittest.main()
