from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template, template_generation_issues
from tests.test_program_preview import exercise_row
from tests.test_program_generation import rewrite_zip_member
from tests.xlsx_factory import add_day_header, write_program_workbook, write_macrofactor_program_template


class ProgramCorrectionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        self.config_path = self.root / "config.json"
        self.payload = {
            "program": {"week_pair_layout": "plan_then_result", "prescription_source": "base",
                        "use_day_designations": True, "allow_blank_targets": True,
                        "preserve_coach_notes": True, "notes_mode": "concise",
                        "exclude_warmups": True, "exclude_cardio": True,
                        "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Synthetic Alpha", "coach_aliases": ["Coach Alpha"]},
                          {"canonical": "Synthetic Beta", "coach_aliases": ["Coach Beta"]}],
        }
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        self.cells["C7"] = "Technical Lower"
        exercise_row(self.cells, 7, name="Coach Alpha", sets=4, reps="6,7,8,9",
                     week_one="2 x 11-13 @ 2 RIR, 40 sec rest",
                     week_two="Warmup drop sets and substitution LATER-UPDATE")
        exercise_row(self.cells, 8, name="Coach Beta", week_one=None, week_two=None)
        self.merges = ("J5:K5", "L5:M5", "C5:C6", "C7:C8")
        write_macrofactor_program_template(self.template)

    def config(self):
        self.config_path.write_text(json.dumps(self.payload))
        return load_config(self.config_path)

    def preview(self, weeks=("Week 1", "Week 2")):
        write_program_workbook(self.coach, sheet_name="Synthetic Block", cells=self.cells, merges=self.merges)
        return build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1", weeks, self.template)

    def first(self, report):
        return report.program.days[0].exercises[0].prescriptions[0]

    def test_base_mode_repeats_prescriptions_without_applying_weekly_text(self):
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertEqual(len(report.program.cycles), 2)
        exercise = report.program.days[0].exercises[0]
        self.assertFalse(exercise.warmup)
        rx = self.first(report)
        self.assertEqual(rx.set_count.value, 4)
        self.assertEqual(rx.set_type.value, "standard")
        self.assertIsNone(rx.rir.value)
        self.assertEqual(rx.rest_seconds.value, 120)
        self.assertEqual(rx.raw_week_text, self.cells["J7"])
        self.assertEqual(exercise.prescriptions[1].raw_week_text, self.cells["L7"])
        self.assertNotIn("LATER-UPDATE", " ".join(exercise.prescriptions[1].notes))
        self.assertIn("weekly_update_not_applied", {issue.code for issue in report.issues})
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(report.to_dict()))

    def test_cli_base_mode_selects_all_weeks_and_round_trips_each_set(self):
        self.preview()
        hashes = file_sha256(self.coach), file_sha256(self.template)
        stdout = StringIO()
        with redirect_stdout(stdout):
            result = main(["program-generate", "--workbook", str(self.coach), "--config", str(self.config_path),
                           "--sheet", "Synthetic Block", "--block", "block-1", "--template", str(self.template),
                           "--output", str(self.output)])
        self.assertEqual(result, 0, stdout.getvalue())
        self.assertIn("2 cycle(s)", stdout.getvalue())
        self.assertIn("6-6, 7-7, 8-8, 9-9", stdout.getvalue())
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual(cells["B1"].value, "Cycles: 2")
        self.assertEqual(cells["A4"].value, "Technical Lower")
        self.assertEqual([cells[ref].value for ref in ("F4", "J4", "N4", "R4")],
                         ["6 - 6", "7 - 7", "8 - 8", "9 - 9"])
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(self.template)))
        output_hash = file_sha256(self.output)
        with self.assertRaisesRegex(WorkbookError, "Output already exists"):
            generate_program(self.preview(), self.template, self.output)
        self.assertEqual(output_hash, file_sha256(self.output))

    def test_explicit_week_selection_limits_base_duration(self):
        self.assertEqual(len(self.preview(("Week 2",)).program.cycles), 1)

    def test_supported_rep_suffixes_and_single_values(self):
        for raw, expected in [(11, (11, 11)), ("7 to 11 ea", (7, 11)),
                              ("9 ea leg", (9, 9)), ("6-9 each side", (6, 9)),
                              ("11 to 14 again", (11, 14))]:
            with self.subTest(raw=raw):
                self.cells["G7"] = raw
                report = self.preview()
                self.assertTrue(report.generation_safe, report.blocking_issues)
                rx = self.first(report)
                self.assertEqual((rx.rep_min.value, rx.rep_max.value), expected)
                self.assertEqual(report.program.days[0].exercises[0].raw_base_fields["reps"], str(raw))
        self.assertNotIn("Coach sets", " ".join(self.first(report).notes))

    def test_minimum_only_target_does_not_invent_maximum_and_blocks_output(self):
        self.cells["G7"] = "14+ reps"
        self.payload["program"]["defaults"].update(rep_min=6, rep_max=20)
        report = self.preview()
        rx = self.first(report)
        self.assertEqual(rx.rep_min.value, 14)
        self.assertIsNone(rx.rep_max.value)
        self.assertEqual(rx.rep_max.source, "coach_unbounded")
        self.assertEqual({issue.code for issue in report.blocking_issues}, {"minimum_only_template_required"})
        with self.assertRaises(WorkbookError):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_bad_rep_lists_and_unsupported_prose_are_not_guessed(self):
        for raw in ["7,8,9", "7,8,9,10,11"]:
            with self.subTest(raw=raw):
                self.cells["G7"] = raw
                self.assertIn("rep_sequence_length_mismatch", {i.code for i in self.preview().blocking_issues})
        for raw in ["8 each then AMRAP", "8+4", "8,0,9,10", "8,9,10kg,11"]:
            with self.subTest(raw=raw):
                self.cells["G7"] = raw
                rx = self.first(self.preview())
                self.assertFalse(rx.set_rep_targets)
                self.assertIsNone(rx.rep_min.value)
                self.assertIn(raw, " ".join(rx.notes))

    def test_notes_only_minimum_keeps_raw_intent_and_blank_targets_in_both_note_modes(self):
        self.cells["G7"] = "14+ reps"
        self.payload["program"]["minimum_rep_policy"] = "notes_only"
        self.payload["program"]["defaults"].update(rep_min=6, rep_max=20)
        self.payload["exercises"][0]["program_notes"] = []
        for mode in ("full", "concise"):
            with self.subTest(mode=mode):
                self.payload["program"]["notes_mode"] = mode
                report = self.preview()
                self.assertTrue(report.generation_safe, report.blocking_issues)
                rx = self.first(report)
                self.assertEqual((rx.rep_min.value, rx.rep_max.value), (None, None))
                self.assertEqual(rx.rep_min.source, "blank_by_policy")
                self.assertEqual(rx.rep_min.raw_text, "14+ reps")
                self.assertIn("Coach rep minimum: 14+ reps (set target manually).", rx.notes)
                self.assertIn("minimum_reps_in_notes", {i.code for i in report.issues})
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertTrue(all(cells[ref].value is None for ref in ("F4", "J4", "N4", "R4")))
        self.assertIn("14+ reps", cells["D4"].value)

    def test_minimum_policy_does_not_change_exact_range_or_ordered_targets(self):
        self.payload["program"]["minimum_rep_policy"] = "notes_only"
        for raw, expected in [(15, (15, 15)), ("8-12", (8, 12)), ("6,7,8,9", (6, 6))]:
            with self.subTest(raw=raw):
                self.cells["G7"] = raw
                report = self.preview()
                rx = self.first(report)
                self.assertEqual((rx.rep_min.value, rx.rep_max.value), expected)
                self.assertNotIn("minimum_reps_in_notes", {i.code for i in report.issues})

    def test_minimum_policy_cannot_bypass_week_conflicts_or_explicit_blank_layout(self):
        self.payload["program"]["minimum_rep_policy"] = "notes_only"
        self.cells["G7"] = "14+ reps"
        self.payload["program"]["prescription_source"] = "selected_week"
        self.cells["J7"] = "4 x 8-12 @ 2 RIR, 120 sec rest"
        self.assertIn("conflicting_base_and_week", {i.code for i in self.preview(("Week 1",)).blocking_issues})
        self.payload["program"]["prescription_source"] = "base"
        self.payload["exercises"][0].update(program_set_types=["standard", "myo", "myo", "myo"],
                                               program_blank_rep_targets=True)
        report = self.preview()
        rx = self.first(report)
        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertIsNone(rx.rep_min.value)
        self.assertEqual([t.value for t in rx.set_types], ["standard", "myo", "myo", "myo"])
        self.assertIn("14+ reps", " ".join(rx.notes))

    def test_minimum_policy_requires_both_blank_and_note_approval(self):
        self.payload["program"]["minimum_rep_policy"] = "notes_only"
        for key in ("allow_blank_targets", "preserve_coach_notes"):
            self.payload["program"][key] = False
            with self.assertRaisesRegex(ConfigError, "notes_only requires"):
                self.config()
            self.payload["program"][key] = True

    def test_appearance_and_minimum_config_reject_unverified_values(self):
        for key, values in {"color": ["Purple", True, []], "icon": ["Dumbbell", 1, {}],
                            "minimum_rep_policy": ["fixed", True, []]}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.payload["program"][key] = value
                    with self.assertRaises(ConfigError):
                        self.config()
            del self.payload["program"][key]

    def test_appearance_preserves_template_by_default(self):
        report = self.preview()
        self.assertIsNone(report.program.color)
        self.assertIsNone(report.program.icon)
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["D1"].value, cells["E1"].value), ("Color: Blue", "Icon: Circle"))

    def test_appearance_cli_round_trip_preserves_inputs_styles_and_non_overwrite(self):
        self.payload["program"].update(color="Red", icon="Rocket", minimum_rep_policy="notes_only")
        self.cells["G7"] = "14+ reps"
        self.preview()
        before = file_sha256(self.coach), file_sha256(self.template)
        stdout = StringIO()
        with redirect_stdout(stdout):
            result = main(["program-generate", "--workbook", str(self.coach), "--config", str(self.config_path),
                           "--sheet", "Synthetic Block", "--block", "block-1", "--template", str(self.template),
                           "--output", str(self.output)])
        self.assertEqual(result, 0, stdout.getvalue())
        self.assertIn("color=Red; icon=Rocket (configured overrides)", stdout.getvalue())
        self.assertIn("minimum_reps_in_notes", stdout.getvalue())
        self.assertEqual(before, (file_sha256(self.coach), file_sha256(self.template)))
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["D1"].value, cells["E1"].value), ("Color: Red", "Icon: Rocket"))
        with zipfile.ZipFile(self.output) as output, zipfile.ZipFile(self.template) as template:
            self.assertEqual(set(output.namelist()), set(template.namelist()))
            for member in template.namelist():
                if member not in {"xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"}:
                    self.assertEqual(output.read(member), template.read(member), member)
        digest = file_sha256(self.output)
        with self.assertRaisesRegex(WorkbookError, "Output already exists"):
            generate_program(self.preview(), self.template, self.output)
        self.assertEqual(digest, file_sha256(self.output))

    def test_appearance_cells_are_discovered_not_hardcoded(self):
        self.payload["program"].update(color="Red", icon="Rocket")
        def move_metadata(data):
            root = ET.fromstring(data)
            for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                swaps = {"D1": "F1", "F1": "D1", "E1": "G1", "G1": "E1"}
                if cell.get("r") in swaps:
                    cell.set("r", swaps[cell.get("r")])
            return ET.tostring(root)
        rewrite_zip_member(self.template, "xl/worksheets/sheet1.xml", move_metadata)
        report = self.preview()
        schema = inspect_program_template(self.template)
        self.assertEqual((schema.color_cell, schema.icon_cell), ("F1", "G1"))
        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual((cells["F1"].value, cells["G1"].value), ("Color: Red", "Icon: Rocket"))

    def test_missing_appearance_cells_only_block_when_override_requested(self):
        def remove_color(data):
            root = ET.fromstring(data)
            for row in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                for cell in list(row):
                    if cell.get("r") == "D1":
                        row.remove(cell)
            return ET.tostring(root)
        rewrite_zip_member(self.template, "xl/worksheets/sheet1.xml", remove_color)
        self.assertTrue(self.preview().generation_safe)
        self.payload["program"]["color"] = "Red"
        self.assertIn("missing_appearance_metadata", {i.code for i in self.preview().blocking_issues})

    def test_ambiguous_metadata_and_direct_unverified_program_override_block(self):
        report = self.preview()
        issues = template_generation_issues(replace(report.program, color="Invented"),
                                            inspect_program_template(self.template), sheet_name=report.sheet)
        self.assertIn("unverified_program_appearance", {i.code for i in issues})
        rewrite_zip_member(self.template, "xl/sharedStrings.xml",
                           lambda data: data.replace(b"Icon: Circle", b"Color: Red"))
        with self.assertRaisesRegex(WorkbookError, "ambiguous color"):
            inspect_program_template(self.template)

    def test_weekly_mode_still_blocks_conflicts_with_per_set_targets(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        self.cells["J7"] = "4 x 6 @ 2 RIR, 120 sec rest"
        report = self.preview(("Week 1",))
        self.assertIn("conflicting_base_and_week", {i.code for i in report.blocking_issues})

    def test_reviewed_overrides_require_unchanged_source_and_report_provenance(self):
        self.payload["exercises"][0]["program_base_overrides"] = {
            "sets": {"expected": "4", "value": "3"},
            "reps": {"expected": "6,7,8,9", "value": "11-17"},
        }
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        rx = self.first(report)
        self.assertEqual(rx.set_count.value, 3)
        self.assertEqual(rx.rep_min.value, 11)
        self.assertEqual(rx.rep_min.source, "config_reviewed_override")
        self.assertEqual(rx.rep_min.raw_text, "6,7,8,9")
        self.cells["F7"] = 2
        self.assertIn("stale_base_override", {i.code for i in self.preview().blocking_issues})

    def test_unsupported_override_cannot_hide_behind_blank_policy(self):
        self.payload["exercises"][0]["program_base_overrides"] = {
            "reps": {"expected": "6,7,8,9", "value": "your choice"}}
        self.assertIn("unsupported_base_override", {i.code for i in self.preview().blocking_issues})

    def test_removing_set_override_restores_base_count_and_clears_all_surplus_fields(self):
        self.cells["F7"] = 2
        self.cells["G7"] = "6-9"
        self.payload["exercises"][0]["program_base_overrides"] = {
            "sets": {"expected": "2", "value": "3"}}
        before = self.preview()
        self.assertTrue(before.generation_safe, before.blocking_issues)
        self.assertEqual(self.first(before).set_count.value, 3)
        self.assertEqual(self.first(before).set_count.source, "config_reviewed_override")
        prior_output = self.root / "prior-output.xlsx"
        generate_program(before, self.template, prior_output)
        hashes = file_sha256(self.coach), file_sha256(self.template), file_sha256(prior_output)
        del self.payload["exercises"][0]["program_base_overrides"]
        # Do not recreate the source: prove the same bytes restore base provenance.
        after = build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                      ("Week 1", "Week 2"), self.template)
        for rx in after.program.days[0].exercises[0].prescriptions:
            self.assertEqual(rx.set_count.value, 2)
            self.assertEqual(rx.set_count.source, "coach_base")
        generate_program(after, self.template, self.output)
        old = XlsxPackage(prior_output).sheet_snapshot("Training Programs").cells
        new = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual([new[f"{col}4"].value for col in "MNOPQRST"], [None] * 8)
        changed = {ref for ref in old if old[ref].value != new[ref].value}
        self.assertEqual(changed, {"M4", "N4", "P4"})  # RIR was already blank.
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(self.template), file_sha256(prior_output)))

    def test_reviewed_date_correction_keeps_source_bytes_and_original_raw_value(self):
        self.cells["G7"] = 45000
        self.preview()
        with zipfile.ZipFile(self.coach, "a") as archive:
            archive.writestr("xl/styles.xml", (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<numFmts count="1"><numFmt numFmtId="164" formatCode="m-d"/></numFmts>'
                '<cellXfs count="1"><xf numFmtId="164"/></cellXfs></styleSheet>'))
        before = file_sha256(self.coach)
        self.payload["exercises"][0]["program_base_overrides"] = {
            "reps": {"expected": "45000", "value": "7-13"}}
        report = build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                       ("Week 1", "Week 2"), self.template)
        rx = self.first(report)
        self.assertEqual((rx.rep_min.value, rx.rep_max.value), (7, 13))
        self.assertEqual(rx.rep_min.raw_text, "45000")
        self.assertEqual(rx.rep_min.source, "config_reviewed_override")
        self.assertEqual(before, file_sha256(self.coach))

    def test_base_mode_cannot_use_weekly_text_to_choose_an_exercise_mapping(self):
        self.payload["exercises"][0]["coach_context_aliases"] = ["WEEKLY-MAPPING-CONTEXT"]
        self.cells["J7"] = "WEEKLY-MAPPING-CONTEXT"
        self.assertIn("unmatched_exercise", {i.code for i in self.preview().blocking_issues})

    def test_designations_do_not_cross_day_or_block_boundaries(self):
        self.cells.pop("C7")
        add_day_header(self.cells, row=12, day="Day 2")
        self.cells["C14"] = "Technical Upper"
        exercise_row(self.cells, 14, name="Coach Alpha", week_one=None, week_two=None)
        exercise_row(self.cells, 15, name="Coach Beta", week_one=None, week_two=None)
        add_day_header(self.cells, row=20, day="Day 1")
        self.cells["C22"] = "Different Block"
        exercise_row(self.cells, 22, name="Coach Beta", week_one=None, week_two=None)
        self.merges += ("J12:K12", "L12:M12", "J20:K20", "L20:M20")
        report = self.preview()
        self.assertEqual([d.export_name for d in report.program.days], ["Day 1", "Technical Upper"])

    def test_day_designations_shift_with_the_header_column_and_reject_formulas(self):
        self.cells["A5"] = self.cells.pop("C5")
        self.cells["A7"] = self.cells.pop("C7")
        self.merges = ("J5:K5", "L5:M5", "A5:A6", "A7:A8")
        day = self.preview().program.days[0]
        self.assertEqual(day.designation_cell, "A7")
        self.assertEqual(day.export_name, "Technical Lower")
        def formula_title(data):
            ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
            root = ET.fromstring(data)
            cell = next(c for c in root.iter(f"{{{ns}}}c") if c.get("r") == "A7")
            ET.SubElement(cell, f"{{{ns}}}f").text = '"Computed title"'
            return ET.tostring(root)
        rewrite_zip_member(self.coach, "xl/worksheets/sheet1.xml", formula_title)
        report = build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                       ("Week 1",), self.template)
        self.assertEqual(report.program.days[0].export_name, "Day 1")
        self.assertIn("ambiguous_day_designation", {i.code for i in report.issues})

    def test_optional_designation_flags_but_keeps_the_day_and_exercises(self):
        self.cells["C7"] = "Optional assistance"
        report = self.preview()
        day = report.program.days[0]
        self.assertTrue(day.optional)
        self.assertTrue(all(e.optional and not e.excluded for e in day.exercises))

    def test_concise_notes_keep_unresolved_targets_after_reviewed_cue_replacement(self):
        self.payload["exercises"][0]["program_notes"] = []
        self.cells["G7"] = "Read week"
        self.assertIn("Reps: Read week", self.first(self.preview()).notes)

    def test_concise_notes_preserve_review_data_and_unilateral_cues(self):
        self.payload["exercises"][0]["program_notes"] = ["Pause at the bottom."]
        self.cells["G7"] = "9 ea leg"
        report = self.preview()
        rx = self.first(report)
        self.assertEqual(rx.notes, ("Pause at the bottom.", "Reps are per side."))
        self.assertIn("variation", report.program.days[0].exercises[0].raw_base_fields)
        self.assertEqual(rx.raw_week_text, self.cells["J7"])
        self.payload["program"]["notes_mode"] = "full"
        self.assertIn("Coach reps: 9 ea leg", self.first(self.preview()).notes)

    def test_blank_myo_override_clears_per_set_targets_but_preserves_guidance(self):
        self.payload["exercises"][0].update(program_set_types=["standard", "myo", "myo", "myo"],
                                              program_blank_rep_targets=True)
        rx = self.first(self.preview())
        self.assertFalse(rx.set_rep_targets)
        self.assertIsNone(rx.rep_min.value)
        self.assertIn("6,7,8,9", " ".join(rx.notes))

    def test_reviewed_warmup_inclusion_does_not_bypass_cardio_or_mapping(self):
        self.cells["D7"] = "Warmup"
        self.assertTrue(self.preview().program.days[0].exercises[0].excluded)
        self.payload["exercises"][0]["program_include_warmup"] = True
        # Reviewed inclusion does not reinterpret an explicit warmup set type.
        self.cells["D7"] = "Warmup movement"
        report = self.preview()
        self.assertFalse(report.program.days[0].exercises[0].excluded)
        self.assertIn("reviewed_warmup_inclusion", {i.code for i in report.issues})
        self.cells["D7"] = "Cardio warmup movement"
        self.assertTrue(self.preview().program.days[0].exercises[0].excluded)

    def test_designation_discovery_retains_original_fractional_day_identity(self):
        self.cells["C5"] = "Day 3.5"
        day = self.preview().program.days[0]
        self.assertEqual(day.label, "Day 3.5")
        self.assertEqual(day.designation, "Technical Lower")
        self.assertEqual(day.designation_cell, "C7")
        self.assertEqual(day.export_name, "Technical Lower")
        self.cells.pop("C7")
        self.assertEqual(self.preview().program.days[0].export_name, "Day 3.5")

    def test_ambiguous_designations_fall_back_without_borrowing_another_column(self):
        self.cells["C8"] = "Second title"
        report = self.preview()
        self.assertEqual(report.program.days[0].export_name, "Day 1")
        self.assertIn("ambiguous_day_designation", {i.code for i in report.issues})

    def test_per_set_targets_participate_in_cycle_consistency_and_writer_checks(self):
        report = self.preview()
        day = report.program.days[0]
        exercise = day.exercises[0]
        rx = exercise.prescriptions[1]
        changed = replace(rx, set_rep_targets=tuple(reversed(rx.set_rep_targets)))
        exercise = replace(exercise, prescriptions=(exercise.prescriptions[0], changed))
        program = replace(report.program, days=(replace(day, exercises=(exercise, day.exercises[1])),))
        schema = inspect_program_template(self.template)
        codes = {i.code for i in template_generation_issues(program, schema, sheet_name="Synthetic Block")}
        self.assertIn("periodized_template_required", codes)
        invalid = replace(rx, set_rep_targets=rx.set_rep_targets[:1])
        exercise = replace(exercise, prescriptions=(invalid, invalid))
        program = replace(program, days=(replace(day, exercises=(exercise, day.exercises[1])),))
        codes = {i.code for i in template_generation_issues(program, schema, sheet_name="Synthetic Block")}
        self.assertIn("unsupported_template_rep_sequence", codes)

    def test_new_configuration_fields_are_strictly_validated(self):
        for key, value in [("prescription_source", "guess"), ("notes_mode", "guess"),
                           ("use_day_designations", 1)]:
            with self.subTest(key=key):
                original = self.payload["program"][key]
                self.payload["program"][key] = value
                with self.assertRaises(ConfigError): self.config()
                self.payload["program"][key] = original
        for key, value in [("program_include_warmup", 1), ("program_notes", "text"),
                           ("program_base_overrides", {"weights": {"expected": "1", "value": "2"}}),
                           ("program_base_overrides", {"sets": {"value": "2"}})]:
            with self.subTest(key=key, value=value):
                self.payload["exercises"][0][key] = value
                with self.assertRaises(ConfigError): self.config()
                self.payload["exercises"][0].pop(key)
