from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macrofactor_bridge.config import load_config
from macrofactor_bridge.program_service import build_program_preview, generate_program
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, add_program_name_evidence, write_macrofactor_program_template, write_program_workbook


class ProgramNoteMappingContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach, self.template = self.root / "coach.xlsx", self.root / "template.xlsx"
        self.config_path = self.root / "config.json"
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        exercise_row(self.cells, 7, name="Synthetic Press", week_one="2 RIR", week_two="3 RIR",
                     week_one_result="RESULT ONLY", week_two_result="RESULT ONLY")
        self.payload = {
            "program": {"week_pair_layout": "plan_then_result", "preserve_coach_notes": True,
                        "notes_mode": "concise", "prescription_source": "selected_week"},
            "exercises": [{"canonical": "Synthetic Press", "coach_aliases": ["Synthetic Press"],
                           "coach_context_aliases": ["2 RIR"]}],
        }
        write_macrofactor_program_template(self.template, day_row_counts=(1,))

    def preview(self, weeks=("Week 1",)):
        self.config_path.write_text(json.dumps(self.payload))
        add_program_name_evidence(self.config_path)
        config = load_config(self.config_path)
        write_program_workbook(self.coach, sheet_name="Synthetic", cells=self.cells,
                               merges=("J5:K5", "L5:M5"))
        return build_program_preview(self.coach, config, "Synthetic", "block-1", weeks, self.template)

    def test_selected_plan_context_matches_without_entering_row_notes(self):
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual(rx.rir.value, 2)
        self.assertEqual(rx.notes, ())
        generate_program(report, self.template, self.root / "output.xlsx")

    def test_completed_result_cannot_supply_mapping_context(self):
        self.payload["exercises"][0]["coach_context_aliases"] = ["RESULT ONLY"]
        report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("unmatched_exercise", {issue.code for issue in report.blocking_issues})

    def test_unselected_week_cannot_supply_mapping_context(self):
        report = self.preview(weeks=("Week 2",))
        self.assertFalse(report.generation_safe)
        self.assertIn("unmatched_exercise", {issue.code for issue in report.blocking_issues})

    def test_base_mode_does_not_use_weekly_mapping_context(self):
        self.payload["program"]["prescription_source"] = "base"
        report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("unmatched_exercise", {issue.code for issue in report.blocking_issues})

    def test_inherited_week_headers_keep_context_within_the_exercise_row(self):
        add_day_header(self.cells, row=12, day="Day 2")
        self.cells.pop("J12")
        self.cells.pop("L12")
        exercise_row(self.cells, 14, name="Synthetic Press", week_one="2 RIR", week_two="3 RIR",
                     week_one_result="RESULT ONLY", week_two_result="RESULT ONLY")
        write_macrofactor_program_template(self.template, day_row_counts=(1, 1))
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertEqual([day.exercises[0].prescriptions[0].notes for day in report.program.days], [(), ()])

    def test_result_then_plan_uses_only_the_planned_member_of_the_pair(self):
        self.payload["program"]["week_pair_layout"] = "result_then_plan"
        self.cells["J7"], self.cells["K7"] = self.cells["K7"], self.cells["J7"]
        self.cells["L7"], self.cells["M7"] = self.cells["M7"], self.cells["L7"]
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertEqual(report.program.days[0].exercises[0].prescriptions[0].notes, ())


if __name__ == "__main__":
    unittest.main()
