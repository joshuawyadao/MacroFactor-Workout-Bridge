from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS, WorkbookError, file_sha256
from macrofactor_bridge.program_models import (
    CyclePrescription, ExpansionProvenance, OrderedExercise, PrescriptionField,
    Program, ProgramCycle, RepTarget, SupersetMembership, WorkoutDay,
)
from macrofactor_bridge.program_output_audit import audit_program_output, inspect_import_contract
from macrofactor_bridge.program_template import inspect_program_template, write_program_from_template
from tests.xlsx_factory import write_macrofactor_program_template


def field(value):
    return PrescriptionField(value, "blank_by_policy" if value is None else "coach_base")


def change_cell(path: Path, reference: str, value: object) -> None:
    """Fault injection updates public worksheet/string storage, not writer helpers."""
    ns = f"{{{MAIN_NS}}}"
    with zipfile.ZipFile(path) as archive:
        members = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
    strings = ET.fromstring(dict((entry.filename, data) for entry, data in members)["xl/sharedStrings.xml"])
    sheet = ET.fromstring(dict((entry.filename, data) for entry, data in members)["xl/worksheets/sheet1.xml"])
    cell = next(item for item in sheet.iter(ns + "c") if item.get("r") == reference)
    cell[:] = []
    cell.attrib.pop("t", None)
    if isinstance(value, str):
        index = len(strings)
        ET.SubElement(ET.SubElement(strings, ns + "si"), ns + "t").text = value
        strings.set("uniqueCount", str(len(strings)))
        strings.set("count", str(int(strings.get("count", "0")) + 1))
        cell.set("t", "s")
        ET.SubElement(cell, ns + "v").text = str(index)
    elif value is not None:
        cell.set("t", "n")
        ET.SubElement(cell, ns + "v").text = str(value)
    replacement = path.with_suffix(".replacement.xlsx")
    with zipfile.ZipFile(replacement, "w") as archive:
        for entry, data in members:
            if entry.filename == "xl/sharedStrings.xml":
                data = ET.tostring(strings)
            elif entry.filename == "xl/worksheets/sheet1.xml":
                data = ET.tostring(sheet)
            archive.writestr(entry, data)
    replacement.replace(path)


class ProgramOutputAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        write_macrofactor_program_template(self.template)
        self.cycles = (ProgramCycle("Week 1", 1), ProgramCycle("Week 2", 2))
        self.rx = CyclePrescription("Week 1", field(3), field("standard"), field(8), field(10),
                                    field(2), field(90), ("Synthetic cue",), None, None)
        self.first = OrderedExercise(1, 7, "E7", "Coach Alpha", "Synthetic Alpha", "exact",
                                     {"sets": "3"}, (self.rx, replace(self.rx, cycle="Week 2")))
        self.second = replace(self.first, order=2, source_row=8, source_cell="E8",
                              coach_name="Coach Beta", macrofactor_name="Synthetic Beta")
        self.day = WorkoutDay("Day 1", 1, False, (self.first, self.second), export_name="Upper")
        self.program = Program("Synthetic Program", "Cycle", self.cycles, (self.day,))

    def generate(self, program=None, path=None):
        program = program or self.program
        path = path or self.output
        write_program_from_template(self.template, path, program, inspect_program_template(self.template),
                                    resize_workouts=True)
        return path

    def test_valid_output_is_read_only_and_audits_all_cycles_and_cells(self):
        self.generate()
        before = file_sha256(self.template), file_sha256(self.output)
        result = audit_program_output(self.program, self.output, self.template)
        self.assertTrue(result.passed, result.errors)
        self.assertEqual(result.errors, ())
        self.assertGreater(result.checked_cells, 50)
        self.assertEqual(result.to_dict()["checked_cells"], result.checked_cells)
        self.assertEqual(before, (file_sha256(self.template), file_sha256(self.output)))

    def test_faults_in_every_serialized_semantic_field_are_detected(self):
        self.generate()
        for reference, wrong, label in (
            ("A1", "Program: Wrong", "program name"), ("B1", "Cycles: 3", "cycle count"),
            ("A4", "Lower", "workout label/order"), ("B4", "Wrong Exercise", "exact exercise"),
            ("C4", "Yes", "skipped flag"), ("D4", "Lost cue", "exercise notes"),
            ("E4", "Myo Set", "set type"), ("F4", "9 - 10", "rep target"),
            ("G4", 1, "RIR"), ("H4", 120, "rest"), ("Q4", "Standard Set", "set type"),
            ("R4", "1 - 2", "rep target"), ("S4", 2, "RIR"), ("T4", 90, "rest"),
            ("D1", "Color: Orange", "program color"), ("E1", "Icon: Rocket", "program icon"),
        ):
            with self.subTest(reference=reference):
                candidate = self.root / f"fault-{reference}.xlsx"
                shutil.copyfile(self.output, candidate)
                change_cell(candidate, reference, wrong)
                result = audit_program_output(self.program, candidate, self.template)
                self.assertFalse(result.passed)
                self.assertTrue(any(label in error for error in result.errors), result.errors)

    def test_wrong_exercise_order_and_superset_membership_are_detected(self):
        prescriptions = tuple(replace(rx, set_type=field("superset")) for rx in self.first.prescriptions)
        first = replace(self.first, superset=SupersetMembership("SS1", 1), prescriptions=prescriptions)
        second = replace(self.second, superset=SupersetMembership("SS1", 2), prescriptions=prescriptions)
        program = replace(self.program, days=(replace(self.day, exercises=(first, second)),))
        self.generate(program)
        self.assertTrue(audit_program_output(program, self.output, self.template).passed)
        change_cell(self.output, "B4", "Synthetic Alpha ∈ SS2")
        self.assertFalse(audit_program_output(program, self.output, self.template).passed)
        change_cell(self.output, "B4", "Synthetic Beta ∈ SS1")
        self.assertFalse(audit_program_output(program, self.output, self.template).passed)

    def test_cycle_differences_cannot_hide_behind_first_cycle(self):
        self.generate()
        later = replace(self.rx, cycle="Week 2", rest_seconds=field(180))
        changed = replace(self.first, prescriptions=(self.rx, later))
        program = replace(self.program, days=(replace(self.day, exercises=(changed, self.second)),))
        result = audit_program_output(program, self.output, self.template)
        self.assertFalse(result.passed)
        self.assertTrue(any("rest" in error for error in result.errors))

    def test_coverage_counts_expansion_children_but_not_excluded_source(self):
        provenance = ExpansionProvenance("Synthetic Parent", 1, 2, "Coach pair", "2", 2)
        rx = replace(self.rx, set_count=field(2))
        children = tuple(replace(self.first, order=i, macrofactor_name=f"Synthetic Child {i}",
                                 prescriptions=(rx, replace(rx, cycle="Week 2")),
                                 expansion=replace(provenance, child_order=i)) for i in (1, 2))
        excluded = replace(self.second, excluded=True, exclusion_reason="Cardio")
        day = replace(self.day, exercises=(*children, replace(self.second, order=3), excluded))
        program = replace(self.program, days=(day,))
        self.generate(program)
        self.assertTrue(audit_program_output(program, self.output, self.template).passed)
        missing_child = replace(self.program, days=(replace(day, exercises=(children[0], self.second)),))
        self.assertFalse(audit_program_output(missing_child, self.output, self.template).passed)
        included_extra = replace(self.program, days=(replace(day, exercises=(*day.exercises, self.second)),))
        self.assertFalse(audit_program_output(included_extra, self.output, self.template).passed)

    def test_per_set_types_and_targets_are_checked_individually(self):
        rx = replace(self.rx, set_types=(field("standard"), field("myo"), field("myo")),
                     set_rep_targets=(RepTarget(field(8), field(8)), RepTarget(field(9), field(9)),
                                      RepTarget(field(10), field(10))))
        first = replace(self.first, prescriptions=(rx, replace(rx, cycle="Week 2")))
        program = replace(self.program, days=(replace(self.day, exercises=(first, self.second)),))
        self.generate(program)
        self.assertTrue(audit_program_output(program, self.output, self.template).passed)
        change_cell(self.output, "J4", "8 - 8")
        self.assertFalse(audit_program_output(program, self.output, self.template).passed)

    def test_appearance_override_is_checked_against_program_not_template(self):
        program = replace(self.program, color="Red", icon="Rocket")
        self.generate(program)
        self.assertTrue(audit_program_output(program, self.output, self.template).passed)
        change_cell(self.output, "E1", "Icon: Circle")
        self.assertFalse(audit_program_output(program, self.output, self.template).passed)

    def test_explicit_blank_targets_are_checked_and_form_distinct_contract_features(self):
        rx = replace(self.rx, rep_min=field(None), rep_max=field(None), rir=field(None), rest_seconds=field(None))
        first = replace(self.first, prescriptions=(rx, replace(rx, cycle="Week 2")))
        program = replace(self.program, days=(replace(self.day, exercises=(first, self.second)),))
        self.generate(program)
        self.assertTrue(audit_program_output(program, self.output, self.template).passed)
        contract = inspect_import_contract(self.output)
        self.assertTrue({"reps:blank", "rir:blank", "rest:blank"}.issubset(contract["features"]))
        change_cell(self.output, "G4", 2)
        self.assertFalse(audit_program_output(program, self.output, self.template).passed)

    def test_invalid_structure_and_missing_file_return_failed_audit(self):
        result = audit_program_output(self.program, self.output, self.template)
        self.assertFalse(result.passed)
        self.assertEqual(result.checked_cells, 0)
        self.generate()
        change_cell(self.output, "B3", "Not an exercise header")
        self.assertFalse(audit_program_output(self.program, self.output, self.template).passed)

    def test_contract_is_privacy_free_and_ignores_target_values_set_counts_and_names(self):
        self.generate()
        first_contract = inspect_import_contract(self.output)
        rx = replace(self.rx, set_count=field(2), rep_min=field(11), rep_max=field(15),
                     rir=field(1), rest_seconds=field(120), notes=("Different private cue",))
        first = replace(self.first, macrofactor_name="Different private exercise",
                        prescriptions=(rx, replace(rx, cycle="Week 2")))
        program = replace(self.program, name="Different private name",
                          days=(replace(self.day, exercises=(first, first)),))
        other = self.generate(program, self.root / "other.xlsx")
        self.assertEqual(first_contract, inspect_import_contract(other))
        encoded = json.dumps(first_contract)
        for private_text in (self.program.name, self.first.macrofactor_name, "Synthetic cue", "Upper"):
            self.assertNotIn(private_text, encoded)

    def test_contract_family_changes_with_resized_day_even_when_features_match(self):
        self.generate()
        original = inspect_import_contract(self.output)
        resized = replace(self.program, days=(replace(self.day, exercises=(
            self.first, self.second, replace(self.second, order=3))),))
        path = self.generate(resized, self.root / "resized.xlsx")
        contract = inspect_import_contract(path)
        self.assertEqual(original["features"], contract["features"])
        self.assertEqual(original["family"]["exercise_row_counts"], [2])
        self.assertEqual(contract["family"]["exercise_row_counts"], [3])
        self.assertNotEqual(original["family"], contract["family"])

    def test_contract_family_changes_with_cycle_total_even_when_features_match(self):
        self.generate()
        original = inspect_import_contract(self.output)
        shorter = replace(self.program, cycles=(self.cycles[0],), days=(replace(self.day, exercises=(
            replace(self.first, prescriptions=(self.rx,)),
            replace(self.second, prescriptions=(self.rx,)))),))
        path = self.generate(shorter, self.root / "shorter.xlsx")
        contract = inspect_import_contract(path)
        self.assertEqual(original["features"], contract["features"])
        self.assertEqual(original["family"]["cycle_count"], 2)
        self.assertEqual(contract["family"]["cycle_count"], 1)
        self.assertNotEqual(original["family"], contract["family"])

    def test_contract_distinguishes_new_mixed_shapes_and_superset_topology(self):
        self.generate()
        original = inspect_import_contract(self.output)
        rx = replace(self.rx, rep_min=field(None), rep_max=field(None),
                     set_types=(field("standard"), field("myo"), field("myo")))
        first = replace(self.first, prescriptions=(rx, replace(rx, cycle="Week 2")),
                        superset=SupersetMembership("SS1", 1))
        # The generation gate forbids mixed myo supersets; compare them separately.
        mixed = replace(first, superset=None)
        program = replace(self.program, days=(replace(self.day, exercises=(mixed, self.second)),))
        path = self.generate(program, self.root / "mixed.xlsx")
        contract = inspect_import_contract(path)
        self.assertEqual(original["family"], contract["family"])
        self.assertIn("sets:standard>myo", contract["features"])
        self.assertNotEqual(original["features"], contract["features"])
        prescriptions = tuple(replace(rx, set_type=field("superset")) for rx in self.first.prescriptions)
        paired = replace(self.program, days=(replace(self.day, exercises=(
            replace(self.first, superset=SupersetMembership("SS1", 1), prescriptions=prescriptions),
            replace(self.second, superset=SupersetMembership("SS1", 2), prescriptions=prescriptions))),))
        contract = inspect_import_contract(self.generate(paired, self.root / "paired.xlsx"))
        self.assertIn("supersets:2:contiguous", contract["features"])
        self.assertIn("superset-topology:g1", contract["features"])

    def test_contract_rejects_unknown_types_and_orphaned_targets(self):
        self.generate()
        for reference, value in (("E4", "Drop Set"), ("R4", "3 - 4"), ("F4", "15+")):
            candidate = self.root / f"unknown-{reference}.xlsx"
            shutil.copyfile(self.output, candidate)
            change_cell(candidate, reference, value)
            with self.subTest(reference=reference), self.assertRaises(WorkbookError):
                inspect_import_contract(candidate)

    def test_contract_family_changes_with_day_or_set_column_capacity(self):
        self.generate()
        original = inspect_import_contract(self.output)
        other = self.root / "different-template.xlsx"
        write_macrofactor_program_template(other, day_row_counts=(2, 2), max_sets=3)
        self.assertNotEqual(original["family"], inspect_import_contract(other)["family"])


if __name__ == "__main__":
    unittest.main()
