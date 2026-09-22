from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_models import PrescriptionField, ProgramCycle
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template, template_generation_issues
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_program_workbook, write_macrofactor_program_template


class ProgramMyoTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.output = self.root / "candidate.xlsx"
        self.config_path = self.root / "config.json"
        self.payload = {
            "program": {"week_pair_layout": "plan_then_result", "allow_blank_targets": True,
                        "preserve_coach_notes": True, "defaults": {"set_type": "standard"}},
            "exercises": [
                {"canonical": "Synthetic Alpha", "coach_aliases": ["Coach Alpha"],
                 "program_set_types": ["standard", "myo", "myo"],
                 "program_blank_rep_targets": True},
                {"canonical": "Synthetic Beta", "coach_aliases": ["Coach Beta"]},
            ],
        }
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 7, name="Coach Alpha", style="Myo Sets", reps="8-12",
                     week_one="Match the first set with short rests")
        exercise_row(cells, 8, name="Coach Beta", week_one=None)
        write_program_workbook(self.coach, sheet_name="Synthetic Block", cells=cells,
                               merges=("J5:K5", "L5:M5"))
        write_macrofactor_program_template(self.template,
                                           set_types=("Standard Set", "Myo Set", "Myo Set"))

    def config(self):
        self.config_path.write_text(json.dumps(self.payload))
        return load_config(self.config_path)

    def preview(self):
        return build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                     ("Week 1",), self.template)

    def test_reference_fixture_has_proved_mixed_labels_and_blank_targets(self):
        cells = XlsxPackage(self.template).sheet_snapshot("Training Programs").cells
        self.assertEqual([cells[ref].value for ref in ("E4", "I4", "M4")],
                         ["Standard Set", "Myo Set", "Myo Set"])
        self.assertTrue(all(cells[ref].value is None for ref in
                            ("F4", "G4", "H4", "J4", "K4", "L4", "N4", "O4", "P4")))

    def test_cli_round_trip_preserves_mixed_sets_blank_reps_and_coach_notes(self):
        hashes = file_sha256(self.coach), file_sha256(self.template)
        self.config()
        stdout = StringIO()
        report_path = self.root / "report.json"
        with redirect_stdout(stdout):
            result = main(["program-generate", "--workbook", str(self.coach),
                           "--config", str(self.config_path), "--sheet", "Synthetic Block",
                           "--block", "block-1", "--week", "Week 1", "--template", str(self.template),
                           "--output", str(self.output), "--report", str(report_path)])
        self.assertEqual(result, 0, stdout.getvalue())
        self.assertIn("1: standard [config_set_sequence], 2: myo", stdout.getvalue())
        report = json.loads(report_path.read_text())
        self.assertFalse(report["manual_import_verified"])
        self.assertFalse(report["validation"]["unrelated_members_changed"])
        rx = report["program"]["days"][0]["exercises"][0]["prescriptions"][0]
        self.assertEqual([field["value"] for field in rx["set_types"]], ["standard", "myo", "myo"])
        self.assertEqual(rx["rep_min"]["source"], "blank_by_policy")
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual([cells[ref].value for ref in ("E4", "I4", "M4", "Q4")],
                         ["Standard Set", "Myo Set", "Myo Set", None])
        self.assertTrue(all(cells[ref].value is None for ref in ("F4", "J4", "N4")))
        self.assertIn("Coach reps: 8-12", cells["D4"].value)
        self.assertIn("Match the first set with short rests", cells["D4"].value)
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", cells["D4"].value)
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(self.template)))
        output_hash = file_sha256(self.output)
        with self.assertRaisesRegex(WorkbookError, "Output already exists"):
            generate_program(self.preview(), self.template, self.output)
        self.assertEqual(output_hash, file_sha256(self.output))

    def test_sequence_must_match_resolved_set_count(self):
        self.payload["exercises"][0]["program_set_types"] = ["standard", "myo"]
        report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("set_type_sequence_length_mismatch", {issue.code for issue in report.blocking_issues})
        with self.assertRaises(WorkbookError):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_sequence_cannot_erase_coach_myo_instruction(self):
        self.payload["exercises"][0]["program_set_types"] = ["standard"] * 3
        report = self.preview()
        self.assertIn("conflicting_set_type_sequence", {issue.code for issue in report.blocking_issues})

    def test_rep_override_does_not_silently_allow_missing_rir(self):
        self.payload["program"]["allow_blank_targets"] = False
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 7, name="Coach Alpha", style="Myo Sets", reps="Your choice", week_one=None)
        exercise_row(cells, 8, name="Coach Beta")
        write_program_workbook(self.coach, sheet_name="Synthetic Block", cells=cells,
                               merges=("J5:K5", "L5:M5"))
        report = self.preview()
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual(rx.rep_min.source, "blank_by_policy")
        self.assertEqual(rx.rir.source, "missing")
        self.assertIn("Coach reps: Your choice", rx.notes)
        alpha_issues = [issue for issue in report.blocking_issues if issue.exercise == "Coach Alpha"]
        self.assertFalse(any(issue.code == "unsupported_base_value" for issue in alpha_issues))
        self.assertTrue(any(issue.code == "missing_prescription_field" and "RIR" in issue.message
                            for issue in alpha_issues))

    def test_invalid_configuration_and_unproved_superset_combination_are_rejected(self):
        rule = self.payload["exercises"][0]
        for value in ("standard,myo,myo", None, [True], ["Myo Set"], ["mini"], ["drop"], {}):
            with self.subTest(value=value):
                rule["program_set_types"] = value
                with self.assertRaises(ConfigError):
                    self.config()
        rule["program_set_types"] = ["standard", "myo", "myo"]
        rule["superset_group"] = "SS1"
        with self.assertRaises(ConfigError):
            self.config()
        rule.pop("superset_group")
        rule["program_blank_rep_targets"] = "yes"
        with self.assertRaises(ConfigError):
            self.config()
        rule["program_blank_rep_targets"] = True
        self.payload["program"]["preserve_coach_notes"] = False
        with self.assertRaises(ConfigError):
            self.config()

    def test_writer_validation_rejects_invalid_sequence_without_parser(self):
        report = self.preview()
        day = report.program.days[0]
        exercise = day.exercises[0]
        rx = exercise.prescriptions[0]
        schema = inspect_program_template(self.template)
        for sequence in (("standard", "myo"), ("standard", "drop", "myo")):
            with self.subTest(sequence=sequence):
                changed = replace(rx, set_types=tuple(PrescriptionField(kind, "config_set_sequence")
                                                      for kind in sequence))
                program = replace(report.program, days=(replace(day, exercises=(
                    replace(exercise, prescriptions=(changed,)), day.exercises[1])),))
                issues = template_generation_issues(program, schema, sheet_name="Synthetic Block")
                self.assertIn("invalid_set_type_sequence", {issue.code for issue in issues})

    def test_sequence_order_changes_are_periodized_even_when_other_fields_match(self):
        report = self.preview()
        day = report.program.days[0]
        exercise = day.exercises[0]
        rx = exercise.prescriptions[0]
        other = replace(rx, cycle="Week 2", set_types=tuple(reversed(rx.set_types)))
        program = replace(report.program,
            cycles=report.program.cycles + (ProgramCycle("Week 2", 2),),
            days=(replace(day, exercises=(replace(exercise, prescriptions=(rx, other)),
                replace(day.exercises[1], prescriptions=day.exercises[1].prescriptions * 2))),))
        issues = template_generation_issues(program, inspect_program_template(self.template),
                                           sheet_name="Synthetic Block")
        self.assertIn("periodized_template_required", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
