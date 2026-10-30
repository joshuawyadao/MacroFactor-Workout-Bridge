from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS
from macrofactor_bridge.program_identity import verify_program_exercise_names
from macrofactor_bridge.program_models import OrderedExercise, Program, WorkoutDay
from tests.xlsx_factory import write_macrofactor_program_template, write_program_workbook


def _program(name: str, *, custom: bool = False, excluded: bool = False) -> Program:
    exercise = OrderedExercise(
        order=1, source_row=6, source_cell="D6", coach_name="Coach movement",
        macrofactor_name=name, mapping_status="mapped", raw_base_fields={},
        prescriptions=(), custom_exercise=custom, excluded=excluded,
    )
    return Program(
        name="Synthetic", cycle_name="Cycle", cycles=(),
        days=(WorkoutDay(label="Day 1", order=1, optional=False, exercises=(exercise,)),),
    )


def _replace_shared_string(path: Path, old: str, new: str) -> None:
    replacement = path.with_name("replacement.xlsx")
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(replacement, "w") as updated:
        for info in original.infolist():
            body = original.read(info.filename)
            if info.filename == "xl/sharedStrings.xml":
                root = ET.fromstring(body)
                matches = [node for node in root.iter(f"{{{MAIN_NS}}}t") if node.text == old]
                if len(matches) != 1:
                    raise AssertionError("Expected one synthetic string")
                matches[0].text = new
                body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            updated.writestr(info, body)
    replacement.replace(path)


class ProgramIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.template = self.root / "native-program.xlsx"
        write_macrofactor_program_template(self.template, day_row_counts=(1,))

    def test_exact_native_program_name_is_verified_and_hashed(self) -> None:
        issues, details, hashes = verify_program_exercise_names(
            _program("Old Exercise 1-1"), self.template,
        )
        self.assertFalse(issues)
        self.assertEqual(details["verified_names"], ["Old Exercise 1-1"])
        self.assertEqual(details["sources"][0]["kind"], "program_export")
        self.assertIn(str(self.template.resolve()), hashes)

    def test_unknown_name_and_casing_block_even_when_available_flag_is_true(self) -> None:
        for name in ("Old exercise 1-1", "Invented Machine Name"):
            with self.subTest(name=name):
                issues, details, _ = verify_program_exercise_names(_program(name), self.template)
                self.assertEqual([issue.code for issue in issues], ["unverified_exercise_name"])
                self.assertEqual(details["unknown_names"], [name])

    def test_custom_exercise_requires_native_evidence(self) -> None:
        issues, _, _ = verify_program_exercise_names(
            _program("Custom Coach Machine", custom=True), self.template,
        )
        self.assertEqual([issue.code for issue in issues], ["unverified_exercise_name"])
        self.assertFalse(verify_program_exercise_names(
            _program("Old Exercise 1-1", custom=True), self.template,
        )[0])

    def test_excluded_exercise_needs_no_evidence(self) -> None:
        self.assertFalse(verify_program_exercise_names(
            _program("Excluded Name", excluded=True), self.template,
        )[0])

    def test_native_superset_suffix_does_not_change_base_name(self) -> None:
        _replace_shared_string(self.template, "Old Exercise 1-1", "Old Exercise 1-1 ∈ SS2")
        self.assertFalse(verify_program_exercise_names(
            _program("Old Exercise 1-1"), self.template,
        )[0])
        self.assertEqual(verify_program_exercise_names(
            _program("Old Exercise 1-1 ∈ SS2"), self.template,
        )[0][0].code, "unverified_exercise_name")

    def test_native_workout_log_supplies_exact_additional_names(self) -> None:
        log = self.root / "Workout Log.xlsx"
        write_program_workbook(log, sheet_name="Workout Log", cells={
            "A1": "Date", "B1": "Workout", "C1": "Exercise",
            "D1": "Set Type", "E1": "Weight (lb)", "F1": "Reps",
            "A2": "2026-01-01", "B2": "Day 1", "C2": "Native Log Exercise",
            "D2": "Standard Set", "E2": "not parsed", "F2": "not parsed",
        })
        issues, details, hashes = verify_program_exercise_names(
            _program("Native Log Exercise"), self.template, (str(log),),
        )
        self.assertFalse(issues)
        self.assertEqual(details["sources"][1]["kind"], "workout_log")
        self.assertEqual(len(hashes), 2)

    def test_invalid_log_reference_blocks_verification(self) -> None:
        log = self.root / "bad-log.xlsx"
        write_program_workbook(log, sheet_name="Workout Log", cells={
            "A1": "Exercise", "A2": "Unproven Exercise",
        })
        issues, details, _ = verify_program_exercise_names(
            _program("Unproven Exercise"), self.template, (str(log),),
        )
        self.assertIn("invalid_exercise_name_reference", [issue.code for issue in issues])
        self.assertIn("unverified_exercise_name", [issue.code for issue in issues])
        self.assertEqual(len(details["sources"]), 1)

    def test_malformed_log_worksheet_blocks_instead_of_raising(self) -> None:
        log = self.root / "malformed-log.xlsx"
        write_program_workbook(log, sheet_name="Workout Log", cells={
            "A1": "Date", "B1": "Workout", "C1": "Exercise",
            "D1": "Set Type", "E1": "Weight (lbs)", "F1": "Reps",
            "C2": "Native Log Exercise",
        })
        replacement = self.root / "replacement.xlsx"
        with zipfile.ZipFile(log) as original, zipfile.ZipFile(replacement, "w") as updated:
            for info in original.infolist():
                body = original.read(info.filename)
                if info.filename == "xl/worksheets/sheet1.xml":
                    body = b"<malformed"
                updated.writestr(info, body)
        replacement.replace(log)
        issues, details, _ = verify_program_exercise_names(
            _program("Native Log Exercise"), self.template, (str(log),),
        )
        self.assertIn("invalid_exercise_name_reference", [issue.code for issue in issues])
        self.assertIn("unverified_exercise_name", [issue.code for issue in issues])
        self.assertEqual(len(details["sources"]), 1)

    def test_reference_change_while_reading_blocks(self) -> None:
        with patch("macrofactor_bridge.program_identity.file_sha256", side_effect=["before", "after"]):
            issues, _, hashes = verify_program_exercise_names(
                _program("Old Exercise 1-1"), self.template,
            )
        self.assertIn("invalid_exercise_name_reference", [issue.code for issue in issues])
        self.assertFalse(hashes)


if __name__ == "__main__":
    unittest.main()
