from __future__ import annotations

import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS, WorkbookError, XlsxPackage, make_cell_reference, split_cell_reference
from macrofactor_bridge.program_models import (
    CyclePrescription, OrderedExercise, PrescriptionField, Program, ProgramCycle, WorkoutDay,
)
from macrofactor_bridge.program_output_audit import audit_program_output, inspect_import_contract
from macrofactor_bridge.program_template import (
    bind_template_durations, inspect_program_template, template_generation_issues,
    write_program_from_template,
)
from tests.xlsx_factory import write_macrofactor_program_template


def field(value):
    return PrescriptionField(value, "blank_by_policy" if value is None else "coach_base")


def with_duration_columns(path: Path) -> None:
    """Turn the synthetic four-field fixture into the five-field native header."""
    namespace = f"{{{MAIN_NS}}}"
    with zipfile.ZipFile(path) as archive:
        members = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
    parts = dict((entry.filename, data) for entry, data in members)
    sheet = ET.fromstring(parts["xl/worksheets/sheet1.xml"])
    strings = ET.fromstring(parts["xl/sharedStrings.xml"])
    for row in sheet.iter(namespace + "row"):
        row_number = int(row.get("r"))
        for cell in row.findall(namespace + "c"):
            original = cell.get("r")
            number, column = split_cell_reference(original)
            if column >= 9:
                cell.set("r", make_cell_reference(number, column + 1))
        for number, column in ((1, 9), (2, 14)):
            new = ET.SubElement(row, namespace + "c", {"r": make_cell_reference(row_number, column), "s": "0"})
            if row_number == 3:
                text = f"Set {number} Duration"
                index = len(strings)
                ET.SubElement(ET.SubElement(strings, namespace + "si"), namespace + "t").text = text
                new.set("t", "s")
                ET.SubElement(new, namespace + "v").text = str(index)
    strings.set("uniqueCount", str(len(strings)))
    strings.set("count", str(int(strings.get("count", "0")) + 2))
    replacement = path.with_name("native-layout.xlsx")
    with zipfile.ZipFile(replacement, "w") as archive:
        for info, data in members:
            if info.filename == "xl/worksheets/sheet1.xml":
                data = ET.tostring(sheet)
            if info.filename == "xl/sharedStrings.xml":
                data = ET.tostring(strings)
            archive.writestr(info, data)
    replacement.replace(path)


def change_cell(path: Path, reference: str, value: int | str | None) -> None:
    namespace = f"{{{MAIN_NS}}}"
    with zipfile.ZipFile(path) as archive:
        members = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
    sheet = ET.fromstring(dict((entry.filename, data) for entry, data in members)["xl/worksheets/sheet1.xml"])
    cell = next(item for item in sheet.iter(namespace + "c") if item.get("r") == reference)
    cell[:] = []
    cell.attrib.pop("t", None)
    if isinstance(value, int):
        cell.set("t", "n")
        ET.SubElement(cell, namespace + "v").text = str(value)
    elif isinstance(value, str):
        cell.set("t", "s")
        # Only use previously registered strings for this synthetic fixture.
        strings = ET.fromstring(dict((entry.filename, data) for entry, data in members)["xl/sharedStrings.xml"])
        options = [item.find(namespace + "t").text for item in strings.findall(namespace + "si")]
        ET.SubElement(cell, namespace + "v").text = str(options.index(value))
    replacement = path.with_name("changed.xlsx")
    with zipfile.ZipFile(replacement, "w") as archive:
        for info, data in members:
            if info.filename == "xl/worksheets/sheet1.xml":
                data = ET.tostring(sheet)
            archive.writestr(info, data)
    replacement.replace(path)


class ProgramDurationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        write_macrofactor_program_template(self.template, day_row_counts=(2,), max_sets=2)
        with_duration_columns(self.template)
        change_cell(self.template, "F4", None)
        change_cell(self.template, "J4", "Standard Set")
        change_cell(self.template, "I4", 30)
        change_cell(self.template, "N4", 30)
        change_cell(self.template, "I5", 45)  # stale if this row becomes a rep exercise
        self.schema = inspect_program_template(self.template)
        self.assertEqual([group.duration for group in self.schema.sets], [9, 14])
        timed = CyclePrescription("Cycle 1", field(2), field("standard"), field(None), field(None),
                                  field(2), field(90), (), None, None)
        reps = CyclePrescription("Cycle 1", field(1), field("standard"), field(8), field(12),
                                 field(2), field(90), (), None, None)
        first = OrderedExercise(1, 7, "E7", "Synthetic Hold", "Old Exercise 1-1", "exact", {}, (timed,))
        second = replace(first, order=2, source_row=8, source_cell="E8", coach_name="Synthetic Rep",
                         macrofactor_name="Old Exercise 1-2", prescriptions=(reps,))
        day = WorkoutDay("Day 1", 1, False, (first, second), export_name="Old Day 1")
        self.program = Program("Synthetic Program", "Cycle", (ProgramCycle("Cycle 1", 1),), (day,))

    def test_matching_native_hold_survives_and_stale_duration_clears(self):
        bound = bind_template_durations(self.program, self.template, self.schema)
        first = bound.days[0].exercises[0].prescriptions[0]
        self.assertEqual([field.value for field in first.set_duration_targets], [30, 30])
        self.assertEqual(first.set_duration_targets[0].source_cell, "I4")
        self.assertFalse(template_generation_issues(bound, self.schema, sheet_name="Synthetic"))
        write_program_from_template(self.template, self.output, bound, self.schema)
        cells = XlsxPackage(self.output).sheet_snapshot(self.schema.sheet_name).cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (30, 30))
        self.assertEqual((cells["I5"].value, cells["N5"].value), (None, None))
        self.assertTrue(audit_program_output(bound, self.output, self.template).passed)
        self.assertIn("duration:present", inspect_import_contract(self.output)["features"])
        change_cell(self.output, "N4", 31)
        audit = audit_program_output(bound, self.output, self.template)
        self.assertFalse(audit.passed)
        self.assertTrue(any("duration" in error for error in audit.errors), audit.errors)

    def test_explicit_duration_overrides_native_target(self):
        first = self.program.days[0].exercises[0]
        rx = replace(first.prescriptions[0], duration_seconds=field(35))
        day = replace(self.program.days[0], exercises=(replace(first, prescriptions=(rx,)),
                                                    self.program.days[0].exercises[1]))
        program = replace(self.program, days=(day,))
        bound = bind_template_durations(program, self.template, self.schema)
        self.assertFalse(bound.days[0].exercises[0].prescriptions[0].set_duration_targets)
        write_program_from_template(self.template, self.output, bound, self.schema)
        cells = XlsxPackage(self.output).sheet_snapshot(self.schema.sheet_name).cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (35, 35))

    def test_changed_identity_does_not_inherit_native_duration(self):
        day = self.program.days[0]
        renamed = replace(day.exercises[0], macrofactor_name="Different Hold")
        program = replace(self.program, days=(replace(day, exercises=(renamed, day.exercises[1])),))
        bound = bind_template_durations(program, self.template, self.schema)
        self.assertFalse(bound.days[0].exercises[0].prescriptions[0].set_duration_targets)
        write_program_from_template(self.template, self.output, bound, self.schema)
        cells = XlsxPackage(self.output).sheet_snapshot(self.schema.sheet_name).cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (None, None))

    def test_legacy_template_blocks_explicit_duration(self):
        legacy = self.root / "legacy.xlsx"
        write_macrofactor_program_template(legacy, day_row_counts=(2,), max_sets=2)
        rx = replace(self.program.days[0].exercises[0].prescriptions[0], duration_seconds=field(30))
        day = replace(self.program.days[0], exercises=(replace(self.program.days[0].exercises[0], prescriptions=(rx,)),
                                                    self.program.days[0].exercises[1]))
        issues = template_generation_issues(replace(self.program, days=(day,)), inspect_program_template(legacy),
                                            sheet_name="Synthetic")
        self.assertIn("duration_template_required", {issue.code for issue in issues})

    def test_invalid_native_duration_is_rejected(self):
        change_cell(self.template, "I4", 0)
        with self.assertRaisesRegex(WorkbookError, "positive numeric seconds"):
            bind_template_durations(self.program, self.template, self.schema)

    def test_reps_and_duration_cannot_share_active_set(self):
        rx = replace(self.program.days[0].exercises[1].prescriptions[0], duration_seconds=field(30))
        day = replace(self.program.days[0], exercises=(self.program.days[0].exercises[0],
                                                    replace(self.program.days[0].exercises[1], prescriptions=(rx,))))
        issues = template_generation_issues(replace(self.program, days=(day,)), self.schema, sheet_name="Synthetic")
        self.assertIn("conflicting_reps_and_duration", {issue.code for issue in issues})

    def test_resizing_clears_cloned_duration_cells(self):
        day = self.program.days[0]
        extra = replace(day.exercises[1], order=3, source_row=9, source_cell="E9",
                        coach_name="Synthetic Extra", macrofactor_name="New Exercise")
        program = replace(self.program, days=(replace(day, exercises=day.exercises + (extra,)),))
        bound = bind_template_durations(program, self.template, self.schema)
        write_program_from_template(self.template, self.output, bound, self.schema,
                                    resize_workouts=True)
        cells = XlsxPackage(self.output).sheet_snapshot(self.schema.sheet_name).cells
        self.assertEqual((cells["I6"].value, cells["N6"].value), (None, None))
        self.assertTrue(audit_program_output(bound, self.output, self.template).passed)

    def test_extra_program_day_is_retained_for_shape_blocker(self):
        rep = self.program.days[0].exercises[1]
        extra = replace(self.program.days[0], label="Day 2", order=2, export_name="Other Day",
                        exercises=(rep, replace(rep, macrofactor_name="Another Rep")))
        program = replace(self.program, days=self.program.days + (extra,))
        bound = bind_template_durations(program, self.template, self.schema)
        self.assertEqual(len(bound.days), 2)
        self.assertIn("template_day_shape_mismatch",
                      {issue.code for issue in template_generation_issues(bound, self.schema,
                                                                          sheet_name="Synthetic")})

    def test_reordered_unique_exercise_preserves_its_own_heterogeneous_durations(self):
        change_cell(self.template, "N4", 45)
        day = self.program.days[0]
        program = replace(self.program, days=(replace(day, exercises=tuple(reversed(day.exercises))),))
        bound = bind_template_durations(program, self.template, self.schema)
        timed = bound.days[0].exercises[1].prescriptions[0]
        self.assertEqual([target.value for target in timed.set_duration_targets], [30, 45])
        write_program_from_template(self.template, self.output, bound, self.schema)
        cells = XlsxPackage(self.output).sheet_snapshot(self.schema.sheet_name).cells
        self.assertEqual((cells["I4"].value, cells["N4"].value), (None, None))
        self.assertEqual((cells["I5"].value, cells["N5"].value), (30, 45))
        self.assertTrue(audit_program_output(bound, self.output, self.template).passed)

    def test_changed_set_count_or_workout_label_blocks_unresolved_native_duration(self):
        day = self.program.days[0]
        first = day.exercises[0]
        one_set = replace(first, prescriptions=(replace(first.prescriptions[0], set_count=field(1)),))
        for candidate in (replace(day, exercises=(one_set, day.exercises[1])),
                          replace(day, export_name="Renamed Day")):
            with self.subTest(candidate=candidate.export_name):
                with self.assertRaisesRegex(WorkbookError, "Native duration I4 cannot be safely associated"):
                    bind_template_durations(replace(self.program, days=(candidate,)),
                                            self.template, self.schema)

    def test_duplicate_exercise_names_or_workout_labels_block_unresolved_duration(self):
        day = self.program.days[0]
        duplicate = replace(day.exercises[1], macrofactor_name=day.exercises[0].macrofactor_name)
        with self.assertRaisesRegex(WorkbookError, "Native duration I4 cannot be safely associated"):
            bind_template_durations(replace(self.program, days=(replace(day, exercises=(day.exercises[0], duplicate)),)),
                                    self.template, self.schema)
        second = replace(day, label="Day 2", order=2, export_name="Old Day 1")
        program = replace(self.program, days=(day, second))
        with self.assertRaisesRegex(WorkbookError, "Native duration I4 cannot be safely associated"):
            bind_template_durations(program, self.template, self.schema)

    def test_duplicate_native_timed_name_blocks_without_override(self):
        change_cell(self.template, "B5", "Old Exercise 1-1")
        change_cell(self.template, "I5", 45)
        with self.assertRaisesRegex(WorkbookError, "Native duration I4 cannot be safely associated"):
            bind_template_durations(self.program, self.template, self.schema)

    def test_duplicate_native_workout_label_blocks_without_override(self):
        duplicate = self.root / "duplicate-workouts.xlsx"
        write_macrofactor_program_template(duplicate, day_row_counts=(2, 2), max_sets=2)
        with_duration_columns(duplicate)
        change_cell(duplicate, "A6", "Old Day 1")
        change_cell(duplicate, "I4", 30)
        schema = inspect_program_template(duplicate)
        with self.assertRaisesRegex(WorkbookError, "Native duration I4 cannot be safely associated"):
            bind_template_durations(self.program, duplicate, schema)

    def test_explicit_rep_or_duration_override_resolves_ambiguous_native_time(self):
        day = self.program.days[0]
        first = day.exercises[0]
        for rx in (replace(first.prescriptions[0], duration_seconds=field(35), set_count=field(1)),
                   replace(first.prescriptions[0], rep_min=field(8), rep_max=field(10), set_count=field(1))):
            with self.subTest(rx=rx):
                changed = replace(day, export_name="Renamed Day",
                                  exercises=(replace(first, prescriptions=(rx,)), day.exercises[1]))
                bound = bind_template_durations(replace(self.program, days=(changed,)),
                                                self.template, self.schema)
                self.assertEqual(bound.days[0].exercises[0].prescriptions[0], rx)

    def test_output_audit_rejects_forged_native_duration_origin(self):
        bound = bind_template_durations(self.program, self.template, self.schema)
        write_program_from_template(self.template, self.output, bound, self.schema)
        day = bound.days[0]
        first = day.exercises[0]
        rx = first.prescriptions[0]
        forged = replace(rx, set_duration_targets=(
            replace(rx.set_duration_targets[0], source_cell="I5"),
            rx.set_duration_targets[1],
        ))
        program = replace(bound, days=(replace(day, exercises=(
            replace(first, prescriptions=(forged,)), day.exercises[1],
        )),))
        audit = audit_program_output(program, self.output, self.template)
        self.assertFalse(audit.passed)
        self.assertTrue(any("inherited duration" in error for error in audit.errors), audit.errors)


if __name__ == "__main__":
    unittest.main()
