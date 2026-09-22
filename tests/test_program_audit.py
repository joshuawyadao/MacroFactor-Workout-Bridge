from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import file_sha256, make_cell_reference, split_cell_reference
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_models import PrescriptionField, SupersetMembership
from macrofactor_bridge.program_service import build_program_preview
from tests.test_program_generation import rewrite_zip_member
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_program_workbook


class ProgramSourceAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "coach.xlsx"
        self.config_path = self.root / "config.json"
        self.payload = {
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "allow_blank_targets": True, "preserve_coach_notes": True,
                        "notes_mode": "concise", "set_count_range_policy": "upper",
                        "rest_range_policy": "upper", "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Alpha", "coach_aliases": ["Alpha Move"],
                           "program_notes": ["Pause one count"]},
                          {"canonical": "Beta", "coach_aliases": ["Beta Move"]}],
        }
        self.cells = {}
        self.additional_merges = ()
        self.reference_boundary_marker = None
        self.require_complete_week_coverage = False
        add_day_header(self.cells, row=5, day="Day 1")
        exercise_row(self.cells, 6, name="Alpha Move", style="Strength", sets="2 to 3",
                     reps="8 to 12 ea leg", rest="1-2 min", week_one="5 x 2 @ 4 RIR",
                     week_two="WEIGHT-ONLY-PLAN", week_one_result="3x99 RESULT NEVER TARGET")
        exercise_row(self.cells, 7, name="Beta Move", reps="15", week_one=None, week_two=None)

    def prepare(self):
        self.config_path.write_text(json.dumps(self.payload))
        self.config = load_config(self.config_path)
        merges = tuple(f"{column}{row}:{end}{row}" for row in (5, 12, 20)
                       if f"C{row}" in self.cells for column, end in (("J", "K"), ("L", "M")))
        write_program_workbook(self.path, sheet_name="Synthetic", cells=self.cells,
                               merges=merges + self.additional_merges)
        self.block = discover_program_blocks(self.path, self.config)[0]
        self.report = build_program_preview(self.path, self.config, "Synthetic", self.block.identifier,
                                            self.block.week_labels)
        return self.audit()

    def audit(self):
        return audit_coach_program(self.path, self.config, self.block, self.report,
                                   reference_boundary_marker=self.reference_boundary_marker,
                                   require_complete_week_coverage=self.require_complete_week_coverage)

    def mutate_exercise(self, transform, *, index=0):
        day = self.report.program.days[0]
        exercises = list(day.exercises)
        exercises[index] = transform(exercises[index])
        self.report.program = replace(self.report.program,
                                      days=(replace(day, exercises=tuple(exercises)), *self.report.program.days[1:]))

    def mutate_rx(self, transform):
        self.mutate_exercise(lambda exercise: replace(exercise,
                             prescriptions=(transform(exercise.prescriptions[0]), *exercise.prescriptions[1:])))

    def assertCode(self, code):
        audit = self.audit()
        self.assertFalse(audit.passed)
        self.assertIn("source_audit_" + code, {issue.code for issue in audit.issues})

    def test_supported_base_prescriptions_pass_without_changing_source_or_report(self):
        audit = self.prepare()
        before = (file_sha256(self.path), json.dumps(self.report.to_dict(), sort_keys=True))
        self.assertTrue(audit.passed, audit.issues)
        self.assertEqual(audit.checked_rows, 2)
        self.assertTrue(audit.checks)
        self.assertIn("manual MacroFactor import", " ".join(audit.limitations))
        self.assertEqual(audit.to_dict()["passed"], True)
        self.audit()
        self.assertEqual(before, (file_sha256(self.path), json.dumps(self.report.to_dict(), sort_keys=True)))

    def test_wrong_set_count_is_detected_independently(self):
        self.prepare()
        self.mutate_rx(lambda rx: replace(rx, set_count=replace(rx.set_count, value=2)))
        self.assertCode("prescription")

    def test_wrong_rep_bound_is_detected_independently(self):
        self.prepare()
        self.mutate_rx(lambda rx: replace(rx, rep_max=replace(rx.rep_max, value=15)))
        self.assertCode("prescription")

    def test_lost_approved_notes_and_unilateral_cue_are_detected(self):
        for removed in ("Pause one count", "Reps are per side."):
            with self.subTest(removed=removed):
                self.prepare()
                self.mutate_rx(lambda rx: replace(rx, notes=tuple(note for note in rx.notes if note != removed)))
                self.assertCode("notes")

    def test_changed_exact_mapping_and_forged_raw_text_are_detected(self):
        self.prepare()
        self.mutate_exercise(lambda exercise: replace(exercise, macrofactor_name="Unapproved"))
        self.assertCode("raw_source")
        self.prepare()
        self.mutate_exercise(lambda exercise: replace(exercise, raw_base_fields={**exercise.raw_base_fields, "sets": "5"}))
        self.assertCode("raw_source")

    def test_source_row_omitted_after_blank_gap_is_not_silently_accepted(self):
        exercise_row(self.cells, 10, name="Alpha Move", week_one=None, week_two=None)
        audit = self.prepare()
        self.assertEqual([exercise.source_row for exercise in self.report.program.days[0].exercises], [6, 7])
        self.assertFalse(audit.passed)
        self.assertEqual(audit.checked_rows, 3)
        self.assertCode("row_coverage")

    def test_prescription_without_an_exercise_is_reported(self):
        self.cells["F8"] = 2
        self.cells["G8"] = 10
        self.prepare()
        self.assertCode("orphan_prescription")

    def test_omitted_day_and_source_order_are_detected(self):
        add_day_header(self.cells, row=12, day="Day 2 (Optional)")
        exercise_row(self.cells, 13, name="Beta Move", week_one=None, week_two=None)
        self.assertTrue(self.prepare().passed)
        self.report.program = replace(self.report.program, days=self.report.program.days[:1])
        self.assertCode("day_coverage")

    def test_weekly_values_cannot_override_base_and_raw_results_cannot_replace_plans(self):
        self.prepare()
        self.mutate_rx(lambda rx: replace(rx, set_count=PrescriptionField(5, "coach_week", "J6", "5 x 2 @ 4 RIR")))
        self.assertCode("prescription")
        self.prepare()
        self.mutate_rx(lambda rx: replace(rx, raw_week_text="3x99 RESULT NEVER TARGET"))
        self.assertCode("weekly_retention")

    def test_per_cycle_missing_or_different_targets_are_detected(self):
        self.prepare()
        self.mutate_exercise(lambda exercise: replace(exercise, prescriptions=exercise.prescriptions[:1]))
        self.assertCode("cycles")
        self.prepare()
        self.report.program = replace(self.report.program, cycles=self.report.program.cycles[:1])
        self.assertCode("cycles")

    def test_configurable_defaults_are_checked_and_not_misrepresented_as_coach_values(self):
        self.cells.pop("H6")
        self.payload["program"]["defaults"].update({"rest_seconds": 90, "rir": 2})
        self.assertTrue(self.prepare().passed)
        self.mutate_rx(lambda rx: replace(rx, rest_seconds=replace(rx.rest_seconds, source="coach_base", source_cell="H6")))
        self.assertCode("prescription")

    def test_supported_minimum_and_prose_targets_must_remain_in_notes(self):
        self.payload["program"]["minimum_rep_policy"] = "notes_only"
        for value in ("15+ reps", "AMRAP each", "Refer to week", "Read week", "your choice"):
            with self.subTest(value=value):
                self.cells["G6"] = value
                self.assertTrue(self.prepare().passed)
                self.mutate_rx(lambda rx: replace(rx, notes=("Pause one count",)))
                self.assertCode("notes")

    def test_explicit_per_set_reps_and_types_are_checked(self):
        self.cells["F6"], self.cells["G6"] = 3, "12, 10, 8"
        self.assertTrue(self.prepare().passed)
        self.mutate_rx(lambda rx: replace(rx, set_rep_targets=tuple(reversed(rx.set_rep_targets))))
        self.assertCode("rep_sequence")
        self.cells["E6"], self.cells["G6"] = "Alpha myo rep match", "your choice"
        self.payload["exercises"][0].update({"coach_aliases": ["Alpha myo rep match"],
            "program_set_types": ["standard", "myo", "myo"], "program_blank_rep_targets": True})
        self.assertTrue(self.prepare().passed)
        self.mutate_rx(lambda rx: replace(rx, set_types=()))
        self.assertCode("set_types")

    def test_exact_override_guards_and_provenance_are_checked(self):
        self.cells["G6"] = "7 to 12 here"
        self.payload["exercises"][0]["program_base_overrides"] = {"reps": {"expected": "7 to 12 here", "value": "7-12"}}
        self.assertTrue(self.prepare().passed)
        self.mutate_rx(lambda rx: replace(rx, rep_min=replace(rx.rep_min, raw_text="7-12")))
        self.assertCode("provenance")
        self.cells["G6"] = "Different guidance"
        self.prepare()
        self.assertCode("override_guard")

    def test_sequential_expansion_is_explicit_two_sets_each_and_not_supersetted(self):
        self.cells["F6"], self.cells["G6"] = 2, "AMRAP"
        self.payload["exercises"][0]["program_expansion"] = {
            "expected_variation": "Alpha Move", "expected_sets": "2",
            "exercises": [{"canonical": "First Movement", "sets": 2},
                          {"canonical": "Second Movement", "sets": 2}],
        }
        self.assertTrue(self.prepare().passed)
        self.assertEqual(len(self.report.program.days[0].exercises), 3)
        self.mutate_exercise(lambda exercise: replace(exercise, superset=SupersetMembership("SS1", 1)))
        self.assertCode("superset")
        self.prepare()
        self.mutate_rx(lambda rx: replace(rx, set_count=replace(rx.set_count, value=1)))
        self.assertCode("prescription")

    def test_custom_unavailable_expansion_preserves_availability_gate(self):
        self.payload["exercises"][0]["macrofactor_custom"] = True
        self.assertTrue(self.prepare().passed)
        self.mutate_exercise(lambda exercise: replace(exercise, custom_exercise=False))
        self.assertCode("availability")
        self.payload["exercises"][0]["macrofactor_available"] = False
        self.prepare()
        self.assertCode("availability")

    def test_exclusion_requires_explicit_rule_or_category_policy(self):
        self.payload["exercises"][0].update({"program_excluded": True, "program_exclusion_reason": "Reviewed exclusion"})
        self.assertTrue(self.prepare().passed)
        self.mutate_exercise(lambda exercise: replace(exercise, excluded=False))
        self.assertCode("exclusion")

    def test_cached_base_formula_is_rejected(self):
        self.prepare()
        def add_formula(data):
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            root = ET.fromstring(data)
            cell = next(node for node in root.iter(ns + "c") if node.attrib["r"] == "G6")
            ET.SubElement(cell, ns + "f").text = '"8 to 12 ea leg"'
            return ET.tostring(root)
        rewrite_zip_member(self.path, "xl/worksheets/sheet1.xml", add_formula)
        self.assertCode("formula")

    def test_audit_is_fail_closed_outside_base_mode(self):
        self.prepare()
        self.config = replace(self.config, program=replace(self.config.program, prescription_source="selected_week"))
        self.assertCode("unsupported_mode")

    def test_shifted_columns_and_header_roles_are_discovered_independently(self):
        self.cells = {make_cell_reference(split_cell_reference(ref)[0] + 3,
                                          split_cell_reference(ref)[1] + 2): value
                      for ref, value in self.cells.items()}
        self.assertTrue(self.prepare().passed)
        self.assertEqual(self.report.program.days[0].exercises[0].source_cell, "G9")
        self.payload["program"]["exercise_header_labels"] = ["Style"]
        self.assertTrue(self.prepare().passed)
        self.assertEqual(self.report.program.days[0].exercises[0].source_cell, "F9")

    def test_day_designations_are_checked_against_literal_title_cells(self):
        self.payload["program"]["use_day_designations"] = True
        self.cells["C6"] = "Lower Strength"
        self.assertTrue(self.prepare().passed)
        self.report.program = replace(self.report.program, days=(replace(self.report.program.days[0], export_name="Day 1"),))
        self.assertCode("day_designation")

    def test_native_superset_expansion_requires_explicit_order(self):
        self.payload["exercises"][0].update({"superset_group": "SS1", "superset_order": 1})
        self.payload["exercises"].append({"canonical": "Gamma", "coach_aliases": ["Alpha Move"],
                                          "superset_group": "SS1", "superset_order": 2})
        self.cells["F6"] = 2
        self.assertTrue(self.prepare().passed)
        self.mutate_exercise(lambda exercise: replace(exercise, superset=SupersetMembership("SS1", 1)), index=1)
        self.assertCode("superset")

    def test_date_formatted_numeric_reps_require_guarded_review(self):
        self.cells["G6"] = 46011
        self.prepare()
        with zipfile.ZipFile(self.path, "a") as archive:
            archive.writestr("xl/styles.xml", (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<numFmts count="1"><numFmt numFmtId="164" formatCode="m-d"/></numFmts>'
                '<cellXfs count="1"><xf numFmtId="164"/></cellXfs></styleSheet>'))
        self.assertCode("date_target")
        self.payload["exercises"][0]["program_base_overrides"] = {
            "reps": {"expected": "46011", "value": "12-20"}}
        self.config_path.write_text(json.dumps(self.payload))
        self.config = load_config(self.config_path)
        self.report = build_program_preview(self.path, self.config, "Synthetic", self.block.identifier,
                                            self.block.week_labels)
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_formula_in_weekly_plan_is_not_silently_treated_as_literal(self):
        self.prepare()
        def add_formula(data):
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            root = ET.fromstring(data)
            cell = next(node for node in root.iter(ns + "c") if node.attrib["r"] == "J6")
            ET.SubElement(cell, ns + "f").text = '"5 x 2 @ 4 RIR"'
            return ET.tostring(root)
        rewrite_zip_member(self.path, "xl/worksheets/sheet1.xml", add_formula)
        self.assertCode("formula")

    def test_completed_result_formula_is_not_an_instruction_or_blocker(self):
        self.prepare()
        def add_formula(data):
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            root = ET.fromstring(data)
            cell = next(node for node in root.iter(ns + "c") if node.attrib["r"] == "K6")
            ET.SubElement(cell, ns + "f").text = '"COMPLETED"'
            return ET.tostring(root)
        rewrite_zip_member(self.path, "xl/worksheets/sheet1.xml", add_formula)
        self.assertTrue(self.audit().passed, self.audit().issues)

    def add_reviewed_reference_footer(self, *, row=10):
        self.reference_boundary_marker = "Synthetic reference legend"
        self.cells[f"D{row}"] = self.reference_boundary_marker
        self.cells[f"E{row + 2}"] = "Reference-only planning scale"
        self.cells[f"F{row + 2}"] = 80
        self.additional_merges += (f"D{row}:E{row}",)

    def test_explicit_reviewed_reference_footer_bounds_audit_without_touching_source(self):
        self.add_reviewed_reference_footer()
        audit = self.prepare()
        self.assertTrue(audit.passed, audit.issues)
        self.assertEqual(audit.checked_rows, 2)
        self.assertIn("reviewed reference marker", " ".join(audit.checks))
        self.assertIn("outside this block", " ".join(audit.limitations))
        self.reference_boundary_marker = None
        self.assertFalse(self.audit().passed, "A merged footer must never become an implicit default boundary")

    def test_reviewed_footer_never_hides_rows_across_blank_gaps_before_marker(self):
        self.add_reviewed_reference_footer(row=14)
        exercise_row(self.cells, 10, name="Alpha Move", week_one=None, week_two=None)
        self.prepare()
        self.assertCode("row_coverage")
        self.assertEqual(self.audit().checked_rows, 3)

    def test_missing_changed_or_ambiguous_reference_markers_fail_closed(self):
        self.add_reviewed_reference_footer()
        self.prepare()
        for marker in ("Missing marker", "synthetic reference legend", "Synthetic reference legend ", ""):
            with self.subTest(marker=marker):
                self.reference_boundary_marker = marker
                self.assertCode("reference_boundary")
        self.reference_boundary_marker = "Synthetic reference legend"
        self.cells["D15"] = self.reference_boundary_marker
        self.additional_merges += ("D15:E15",)
        self.prepare()
        self.assertCode("reference_boundary")

    def test_unmerged_or_nonblank_reference_boundary_guards_fail_closed(self):
        self.add_reviewed_reference_footer()
        self.additional_merges = ()
        self.prepare()
        self.assertCode("reference_boundary")
        self.additional_merges = ("D10:E10",)
        for reference in ("F10", "G10", "H10", "E10", "D9", "E9", "F9", "G9", "H9"):
            with self.subTest(reference=reference):
                self.cells[reference] = "Nonblank guard"
                self.prepare()
                self.assertCode("reference_boundary")
                self.cells.pop(reference)

    def test_cached_reference_marker_and_guard_formulas_fail_closed(self):
        self.add_reviewed_reference_footer()
        for reference in ("D10", "F10", "F9"):
            with self.subTest(reference=reference):
                self.cells.setdefault(reference, None)
                self.prepare()
                def add_formula(data):
                    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                    root = ET.fromstring(data)
                    cell = next(node for node in root.iter(ns + "c") if node.attrib["r"] == reference)
                    ET.SubElement(cell, ns + "f").text = '"Synthetic reference legend"' if reference == "D10" else '""'
                    return ET.tostring(root)
                rewrite_zip_member(self.path, "xl/worksheets/sheet1.xml", add_formula)
                self.assertCode("reference_boundary")

    def test_other_blocks_reference_markers_are_outside_the_selection(self):
        self.add_reviewed_reference_footer()
        add_day_header(self.cells, row=20, day="Day 1")
        exercise_row(self.cells, 21, name="Alpha Move", week_one=None, week_two=None)
        self.cells["D24"] = self.reference_boundary_marker
        self.additional_merges += ("D24:E24",)
        self.assertTrue(self.prepare().passed, self.audit().issues)
        self.cells.pop("D10")
        self.prepare()
        self.assertCode("reference_boundary")

    def test_reviewed_footer_does_not_broaden_pre_marker_cardio_exclusions(self):
        self.add_reviewed_reference_footer(row=14)
        self.payload["program"]["exclude_cardio"] = True
        self.cells["E10"] = "Rest-day cardio instruction"
        self.prepare()
        self.assertCode("row_coverage")
        self.assertCode("exclusion")

    def test_all_weeks_audit_rejects_duration_shortened_by_day_week_intersection(self):
        add_day_header(self.cells, row=12, day="Day 2", week_one="Week 2", week_two="Week 3")
        exercise_row(self.cells, 13, name="Beta Move", week_one=None, week_two=None)
        self.assertTrue(self.prepare().passed, self.audit().issues)
        self.assertEqual(self.block.week_labels, ("Week 2",))
        self.assertEqual(tuple(cycle.label for cycle in self.report.program.cycles), ("Week 2",))
        self.require_complete_week_coverage = True
        self.assertCode("complete_week_coverage")

    def test_all_weeks_audit_accepts_complete_case_normalized_day_week_coverage(self):
        add_day_header(self.cells, row=12, day="Day 2", week_one=" week 1 ", week_two="WEEK 2")
        exercise_row(self.cells, 13, name="Beta Move", week_one=None, week_two=None)
        self.require_complete_week_coverage = True
        self.assertTrue(self.prepare().passed, self.audit().issues)
        self.assertEqual(len(self.report.program.cycles), 2)
        self.assertIn("All independently visible", " ".join(self.audit().checks))

    def test_intentional_subset_remains_allowed_unless_all_weeks_is_required(self):
        self.prepare()
        self.report = build_program_preview(self.path, self.config, "Synthetic", self.block.identifier,
                                            ("Week 1",))
        self.assertTrue(self.audit().passed, self.audit().issues)
        self.require_complete_week_coverage = True
        self.assertCode("complete_week_coverage")


if __name__ == "__main__":
    unittest.main()
