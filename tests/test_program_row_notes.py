from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage
from macrofactor_bridge.program_audit import audit_coach_program, audit_program_source_rows
from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import build_program_preview, generate_program
from tests.test_program_preview import exercise_row
from tests.test_program_duration import with_duration_columns
from tests.xlsx_factory import (
    add_day_header, add_program_name_evidence, write_macrofactor_program_template,
    write_program_workbook,
)


class ProgramRowNotesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach, self.template = self.root / "coach.xlsx", self.root / "template.xlsx"
        self.config_path, self.output = self.root / "config.json", self.root / "output.xlsx"
        self.payload = {
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "preserve_coach_notes": True, "notes_mode": "concise",
                        "allow_blank_targets": True, "exclude_warmups": True,
                        "defaults": {"set_type": "standard", "rep_min": 8, "rep_max": 12}},
            "exercises": [{"canonical": "Synthetic Row", "coach_aliases": [
                "Single arm row with pad", "Both arms row with neutral handles"],
                "program_notes": ["BORROWED warmup cue", "WEEK ONE cue"]}],
        }
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        exercise_row(self.cells, 6, name="Warmup Move", style="Warmup", reps="Warmup sentinel")
        exercise_row(self.cells, 7, name="Single arm row with pad", style="Horizontal Row",
                     sets=2, reps="12-20 each side", rest="90 sec",
                     week_one="WEEK ONE sentinel", week_one_result="COMPLETED sentinel")
        exercise_row(self.cells, 8, name="Both arms row with neutral handles", style="Machine Row",
                     sets=2, reps="12-20", rest="90 sec", week_one="Different weekly cue")
        self.cells["J10"] = "BELOW ROW sentinel"
        write_macrofactor_program_template(self.template, day_row_counts=(2,), max_sets=2)

    def preview(self, *, native_names=True):
        self.config_path.write_text(json.dumps(self.payload))
        if native_names:
            add_program_name_evidence(self.config_path)
        config = load_config(self.config_path)
        write_program_workbook(self.coach, sheet_name="Synthetic", cells=self.cells,
                               merges=("J5:K5", "L5:M5"))
        block = discover_program_blocks(self.coach, config)[0]
        report = build_program_preview(self.coach, config, block.sheet, block.identifier,
                                        ("Week 1",), self.template)
        return config, block, report

    def test_service_blocks_unknown_names_despite_valid_mapping(self):
        _, _, report = self.preview(native_names=False)
        self.assertFalse(report.generation_safe)
        self.assertIn("unverified_exercise_name", {i.code for i in report.blocking_issues})
        with self.assertRaisesRegex(WorkbookError, "blocking"):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_shared_name_keeps_only_each_rows_left_table_notes(self):
        config, block, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        first, second = [e for e in report.program.days[0].exercises if not e.excluded]
        self.assertEqual(first.prescriptions[0].notes, (
            "Horizontal Row", "Single arm row with pad", "Reps: 12-20 each side"))
        self.assertEqual(second.prescriptions[0].notes, (
            "Machine Row", "Both arms row with neutral handles"))
        self.assertIn("configured_notes_not_applied", {i.code for i in report.issues})
        self.assertTrue(audit_coach_program(self.coach, config, block, report).passed)
        generate_program(report, self.template, self.output)
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)
        notes = [cell.value for ref, cell in XlsxPackage(self.output).sheet_snapshot("Training Programs").cells.items()
                 if ref in {"D4", "D5"}]
        self.assertNotIn("Single arm", notes[1])
        for sentinel in ("BORROWED", "WEEK ONE", "COMPLETED", "Warmup", "BELOW ROW"):
            self.assertNotIn(sentinel, "\n".join(notes))

    def test_full_notes_are_also_row_scoped(self):
        self.payload["program"]["notes_mode"] = "full"
        config, _, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        notes = report.program.days[0].exercises[1].prescriptions[0].notes
        self.assertIn("Coach reps: 12-20 each side", notes)
        self.assertFalse(any("Import setting" in text or "WEEK ONE" in text for text in notes))
        self.assertEqual(audit_program_source_rows(self.coach, config, report), ())

    def test_independent_audits_reject_appended_neighbor_text(self):
        config, block, report = self.preview()
        day = report.program.days[0]
        exercise = day.exercises[1]
        rx = exercise.prescriptions[0]
        altered = replace(exercise, prescriptions=(replace(rx, notes=(*rx.notes, "Warmup sentinel")),))
        report.program = replace(report.program, days=(replace(day, exercises=(day.exercises[0], altered, day.exercises[2])),))
        self.assertIn("source_audit_notes", {i.code for i in audit_program_source_rows(self.coach, config, report)})
        self.assertIn("source_audit_notes", {i.code for i in audit_coach_program(self.coach, config, block, report).issues})

    def test_unparsed_week_cannot_be_dropped_into_row_only_notes(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        _, _, report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("unsupported_week_instruction", {i.code for i in report.blocking_issues})

    def test_duration_seconds_stay_separate_from_rep_defaults_and_rest(self):
        self.cells["G7"] = "30sec eachleg"
        with_duration_columns(self.template)
        config, block, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[1].prescriptions[0]
        self.assertEqual(rx.duration_seconds.value, 30)
        self.assertEqual(rx.duration_seconds.source_cell, "G7")
        self.assertIsNone(rx.rep_min.value)
        self.assertIsNone(rx.rep_max.value)
        self.assertEqual(rx.rest_seconds.value, 90)
        self.assertIn("Duration: 30sec eachleg", rx.notes)
        from macrofactor_bridge.cli import _print_program_report
        rendered = StringIO()
        with redirect_stdout(rendered):
            _print_program_report(report)
        self.assertIn("duration target: 30s [coach_base]", rendered.getvalue())
        self.assertIn("reps=not applicable (timed)", rendered.getvalue())
        self.assertTrue(audit_coach_program(self.coach, config, block, report).passed)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (30, 30))
        self.assertIsNone(cells["F4"].value)
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)

    def test_explicit_time_grammar_keeps_minutes_and_rejects_ambiguous_units(self):
        from macrofactor_bridge.coach_program import _parse_duration
        for raw, expected in (("30 sec each leg", 30), ("30sec eachleg", 30),
                              ("1 min each side", 60), ("45 seconds", 45),
                              ("0 sec", None), ("30", None), ("30-45 sec", None),
                              ("30 sec then add weight", None)):
            with self.subTest(raw=raw):
                self.assertEqual(_parse_duration(raw), expected)

    def test_guarded_duration_override_retains_original_row_note(self):
        self.cells["G7"] = "Hold thirty seconds per leg"
        self.payload["exercises"][0]["program_base_overrides"] = {
            "reps": {"expected": "Hold thirty seconds per leg", "value": "30 sec each leg"}}
        # The same canonical is reused on row 8; its stale correction must block,
        # so isolate the duration row for this source-guard test.
        for column in ("D", "E", "F", "G", "H", "J", "K", "L", "M"):
            self.cells.pop(f"{column}8", None)
        write_macrofactor_program_template(self.template, day_row_counts=(1,), max_sets=2)
        with_duration_columns(self.template)
        self.payload["program"]["allow_blank_targets"] = False
        self.payload["program"]["defaults"]["rir"] = 2
        config, block, report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = report.program.days[0].exercises[1].prescriptions[0]
        self.assertEqual(rx.duration_seconds.source, "config_reviewed_override")
        self.assertEqual(rx.duration_seconds.raw_text, "Hold thirty seconds per leg")
        self.assertIn("Reps: Hold thirty seconds per leg", rx.notes)
        self.assertTrue(audit_coach_program(self.coach, config, block, report).passed)
        generate_program(report, self.template, self.output)

    def test_reference_changes_before_or_during_generation_refuse_output(self):
        _, _, report = self.preview()
        reference = self.config_path.with_name("config-native-names.xlsx")
        original = reference.read_bytes()
        reference.write_bytes(original + b" ")
        with self.assertRaisesRegex(WorkbookError, "reference changed"):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())
        reference.write_bytes(original)
        from macrofactor_bridge.program_service import write_program_from_template
        def drift(*args, **kwargs):
            result = write_program_from_template(*args, **kwargs)
            reference.write_bytes(original + b" ")
            return result
        with patch("macrofactor_bridge.program_service.write_program_from_template", side_effect=drift):
            with self.assertRaisesRegex(WorkbookError, "changed during generation"):
                generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_new_config_fields_validate_and_defaults_are_row_only(self):
        for key, value in (("notes_source", "all_weeks"), ("exercise_name_references", "names.xlsx"),
                           ("exercise_name_references", [None]), ("exercise_name_references", [""])):
            with self.subTest(key=key, value=value):
                payload = json.loads(json.dumps(self.payload))
                payload["program"][key] = value
                self.config_path.write_text(json.dumps(payload))
                with self.assertRaises(ConfigError):
                    load_config(self.config_path)
        config, _, _ = self.preview()
        self.assertEqual(config.program.notes_source, "left_table_row")


if __name__ == "__main__":
    unittest.main()
