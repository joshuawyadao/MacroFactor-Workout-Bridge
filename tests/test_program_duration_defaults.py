from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import build_program_preview, generate_program
from tests.test_program_duration import change_cell, with_duration_columns
from tests.xlsx_factory import (
    add_day_header, add_program_name_evidence,
    write_macrofactor_program_template, write_program_workbook,
)


class NativeDurationDefaultIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "native-template.xlsx"
        self.output = self.root / "output.xlsx"
        self.config_path = self.root / "config.json"
        self.payload = {
            "program": {
                "week_pair_layout": "plan_then_result",
                "prescription_source": "base",
                "use_day_designations": True,
                "allow_blank_targets": True,
                "preserve_coach_notes": True,
                "notes_mode": "concise",
                "defaults": {"set_type": "standard", "rep_min": 8, "rep_max": 12,
                             "rir": 2, "rest_seconds": 90},
            },
            "exercises": [
                {"canonical": "Old Exercise 1-1", "coach_aliases": ["Old Exercise 1-1"]},
                {"canonical": "Old Exercise 1-2", "coach_aliases": ["Old Exercise 1-2"]},
            ],
        }
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        self.cells["C6"] = "Old Day 1"
        for row, name, count, reps in ((6, "Old Exercise 1-1", 2, None),
                                       (7, "Old Exercise 1-2", 1, "8-12")):
            self.cells.update({
                f"D{row}": "Straight Sets", f"E{row}": name,
                f"F{row}": count, f"G{row}": reps, f"H{row}": "90 sec",
                f"J{row}": None, f"K{row}": None,
                f"L{row}": None, f"M{row}": None,
            })
        self.cells["G6"] = None
        self.write_coach()
        write_macrofactor_program_template(self.template, day_row_counts=(2,), max_sets=2)
        with_duration_columns(self.template)
        change_cell(self.template, "F4", None)
        change_cell(self.template, "J4", "Standard Set")
        change_cell(self.template, "I4", 30)
        change_cell(self.template, "N4", 30)

    def write_coach(self) -> None:
        write_program_workbook(self.coach, sheet_name="Synthetic Block", cells=self.cells,
                               merges=("J5:K5", "L5:M5"))

    def config(self):
        self.config_path.write_text(json.dumps(self.payload))
        add_program_name_evidence(self.config_path)
        return load_config(self.config_path)

    def preview(self):
        config = self.config()
        block = discover_program_blocks(self.coach, config, sheet_name="Synthetic Block")[0]
        report = build_program_preview(self.coach, config, block.sheet, block.identifier,
                                       block.week_labels, self.template)
        return config, block, report

    def test_blank_coach_reps_keep_verified_native_seconds_despite_default_reps(self):
        before = file_sha256(self.coach), file_sha256(self.template)
        config, block, report = self.preview()
        self.assertTrue(report.generation_safe, [issue.to_dict() if hasattr(issue, "to_dict") else issue
                                                 for issue in report.blocking_issues])
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual((rx.rep_min.value, rx.rep_max.value), (None, None))
        self.assertEqual((rx.rep_min.source, rx.rep_max.source), ("blank_by_policy", "blank_by_policy"))
        self.assertEqual([target.value for target in rx.set_duration_targets], [30, 30])
        source_audit = audit_coach_program(self.coach, config, block, report)
        self.assertTrue(source_audit.passed, source_audit.issues)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["F4"].value, cells["K4"].value), (None, None))
        self.assertEqual((cells["I4"].value, cells["N4"].value), (30, 30))
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)
        self.assertEqual((file_sha256(self.coach), file_sha256(self.template)), before)

    def test_explicit_coach_reps_replace_native_duration_and_keep_reps(self):
        self.cells["G6"] = "10-12"
        self.write_coach()
        _, _, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual((rx.rep_min.value, rx.rep_max.value), (10, 12))
        self.assertFalse(rx.set_duration_targets)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["F4"].value, cells["K4"].value), ("10 - 12", "10 - 12"))
        self.assertEqual((cells["I4"].value, cells["N4"].value), (None, None))

    def test_ambiguous_native_time_with_default_reps_blocks(self):
        self.cells["C6"] = "Renamed Day"
        self.write_coach()
        _, _, report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertTrue(any(issue.code == "invalid_program_template" and "Native duration I4" in issue.message
                            for issue in report.blocking_issues), report.blocking_issues)
        self.assertFalse(self.output.exists())

    def test_explicit_base_reps_stay_blank_by_policy_without_inheriting_time(self):
        self.cells["G6"] = "8-12"
        self.payload["exercises"][0]["program_blank_rep_targets"] = True
        self.write_coach()
        config, block, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual((rx.rep_min.value, rx.rep_max.value), (None, None))
        self.assertFalse(rx.set_duration_targets)
        self.assertIn("Reps: 8-12", rx.notes)
        self.assertTrue(audit_coach_program(self.coach, config, block, report).passed)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["F4"].value, cells["K4"].value, cells["I4"].value, cells["N4"].value),
                         (None, None, None, None))

    def test_explicit_weekly_reps_stay_blank_by_policy_without_inheriting_time(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        self.payload["exercises"][0]["program_blank_rep_targets"] = True
        self.cells["J6"] = self.cells["L6"] = "2 x 8-12 @ 2 RIR, 90 sec rest"
        self.write_coach()
        _, _, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertIsNotNone(rx.rep_min.raw_text)
        self.assertFalse(rx.set_duration_targets)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (None, None))

    def test_output_audit_rejects_native_time_with_authored_rep_guidance(self):
        _, _, report = self.preview()
        generate_program(report, self.template, self.output)
        day = report.program.days[0]
        first = replace(day.exercises[0], raw_base_fields={**day.exercises[0].raw_base_fields, "reps": "8-12"})
        altered = replace(report.program, days=(replace(day, exercises=(first, day.exercises[1])),))
        audit = audit_program_output(altered, self.output, self.template)
        self.assertFalse(audit.passed)
        self.assertTrue(any("inherited duration" in error for error in audit.errors), audit.errors)

    def test_unparsed_selected_week_instruction_does_not_inherit_native_time(self):
        self.payload["program"].update(prescription_source="selected_week", notes_source="reviewed")
        self.cells["J6"] = self.cells["L6"] = "AMRAP"
        self.write_coach()
        _, _, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual(rx.raw_unparsed_text, "AMRAP")
        self.assertIn("AMRAP", rx.notes)
        self.assertFalse(rx.set_duration_targets)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (None, None))

    def test_supported_weekly_rir_cue_keeps_native_duration(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        self.cells["J6"] = self.cells["L6"] = "2 RIR"
        self.write_coach()
        _, _, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertIsNone(rx.raw_unparsed_text)
        self.assertEqual([target.value for target in rx.set_duration_targets], [30, 30])
        generate_program(report, self.template, self.output)


if __name__ == "__main__":
    unittest.main()
