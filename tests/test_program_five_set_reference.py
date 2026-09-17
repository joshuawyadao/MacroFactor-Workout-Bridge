from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template
from tests.test_program_output_audit import change_cell
from tests.xlsx_factory import (
    add_day_header,
    write_macrofactor_program_template,
    write_program_workbook,
)


class FiveSetProgramReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config_path = self.root / "config.json"
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        self.payload = {
            "workbook": {
                "exercise_header_labels": ["Variation", "Exercise"],
                "week_header_pattern": "^week\\s*\\d+$",
            },
            "program": {
                "week_pair_layout": "plan_then_result",
                "defaults": {"set_type": "standard"},
            },
            "exercises": [
                {
                    "canonical": "Synthetic Alpha",
                    "source_aliases": ["Synthetic Alpha"],
                    "coach_aliases": ["Coach Alpha"],
                },
                {
                    "canonical": "Synthetic Beta",
                    "source_aliases": ["Synthetic Beta"],
                    "coach_aliases": ["Coach Beta"],
                },
            ],
        }
        write_macrofactor_program_template(
            self.template,
            max_sets=5,
            day_row_counts=(2, 2, 2, 2),
        )

    def config(self):
        self.config_path.write_text(json.dumps(self.payload), encoding="utf-8")
        return load_config(self.config_path)

    def write_coach(self, *, sets: int = 5, one_row_per_day: bool = False) -> None:
        cells: dict[str, object | None] = {}
        merges: list[str] = []
        for day_number, header_row in enumerate((5, 12, 19, 26), start=1):
            add_day_header(cells, row=header_row, day=f"Day {day_number}")
            merges.extend((f"J{header_row}:K{header_row}", f"L{header_row}:M{header_row}"))
            names = ("Coach Pair",) if one_row_per_day else ("Coach Alpha", "Coach Beta")
            for offset, name in enumerate(names, start=1):
                row = header_row + offset
                cells.update(
                    {
                        f"D{row}": "Superset" if one_row_per_day else "Straight Sets",
                        f"E{row}": name,
                        f"F{row}": sets,
                        f"G{row}": "8-10",
                        f"H{row}": "120 sec",
                        f"J{row}": f"{sets} x 8-10 @ 2 RIR, 120 sec rest",
                        f"K{row}": "SYNTHETIC-COMPLETED-RESULT",
                        f"L{row}": f"{sets} x 8-10 @ 2 RIR, 120 sec rest",
                        f"M{row}": None,
                    }
                )
        write_program_workbook(
            self.coach,
            sheet_name="Synthetic Program",
            cells=cells,
            merges=tuple(merges),
        )

    def preview(self):
        return build_program_preview(
            self.coach,
            self.config(),
            "Synthetic Program",
            "block-1",
            ("Week 1",),
            template_path=self.template,
        )

    def test_five_active_sets_round_trip_and_independent_output_audit(self) -> None:
        self.write_coach(sets=5)
        report = self.preview()

        self.assertTrue(report.generation_safe, report.blocking_issues)
        self.assertEqual([len(day.rows) for day in inspect_program_template(self.template).days], [2] * 4)
        self.assertEqual(len(inspect_program_template(self.template).sets), 5)
        generate_program(report, self.template, self.output)

        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        for row in range(4, 12):
            self.assertEqual(cells[f"U{row}"].value, "Standard Set")
            self.assertEqual(cells[f"V{row}"].value, "8 - 10")
            self.assertEqual(cells[f"W{row}"].value, 2)
            self.assertEqual(cells[f"X{row}"].value, 120)

        audit = audit_program_output(report.program, self.output, self.template)
        self.assertTrue(audit.passed, audit.errors)
        faulted = self.root / "faulted-fifth-set.xlsx"
        shutil.copyfile(self.output, faulted)
        change_cell(faulted, "U4", None)
        self.assertFalse(audit_program_output(report.program, faulted, self.template).passed)

    def test_fewer_sets_clear_the_unused_fifth_slot(self) -> None:
        self.write_coach(sets=4)
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        generate_program(report, self.template, self.output)

        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        for row in range(4, 12):
            self.assertTrue(
                all(cells[f"{column}{row}"].value is None for column in "UVWX")
            )
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)

    def test_blank_rir_values_keep_all_five_required_header_groups(self) -> None:
        self.payload["program"].update(prescription_source="base", allow_blank_targets=True)
        self.write_coach(sets=5)
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        generate_program(report, self.template, self.output)
        schema = inspect_program_template(self.output)
        self.assertEqual(len(schema.sets), 5)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        for row in range(4, 12):
            for column in "GKOSW":
                self.assertIsNone(cells[f"{column}{row}"].value)
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)

    def test_source_and_template_are_immutable_and_output_is_not_overwritten(self) -> None:
        self.write_coach(sets=5)
        report = self.preview()
        before = (file_sha256(self.coach), file_sha256(self.template))
        generate_program(report, self.template, self.output)

        self.assertEqual(before, (file_sha256(self.coach), file_sha256(self.template)))
        output_hash = file_sha256(self.output)
        with self.assertRaisesRegex(WorkbookError, "already exists"):
            generate_program(report, self.template, self.output)
        self.assertEqual(output_hash, file_sha256(self.output))
        self.assertEqual(before, (file_sha256(self.coach), file_sha256(self.template)))

    def test_six_sets_are_blocked_by_the_five_set_capacity(self) -> None:
        self.write_coach(sets=6)
        report = self.preview()

        self.assertFalse(report.generation_safe)
        self.assertIn(
            "template_set_capacity_exceeded",
            {issue.code for issue in report.blocking_issues},
        )
        with self.assertRaises(WorkbookError):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_each_malformed_fifth_set_header_is_blocked(self) -> None:
        for label in ("Type", "Rep Range", "RIR", "Rest"):
            with self.subTest(label=label):
                malformed = self.root / f"malformed-{label.replace(' ', '-').lower()}.xlsx"
                shutil.copyfile(self.template, malformed)
                with zipfile.ZipFile(malformed) as archive:
                    members = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
                replacement = malformed.with_suffix(".replacement.xlsx")
                needle = f"Set 5 {label}".encode()
                with zipfile.ZipFile(replacement, "w") as archive:
                    for entry, data in members:
                        if entry.filename == "xl/sharedStrings.xml":
                            self.assertIn(needle, data)
                            data = data.replace(needle, b"Malformed Fifth Header", 1)
                        archive.writestr(entry, data)
                replacement.replace(malformed)

                with self.assertRaises(WorkbookError):
                    inspect_program_template(malformed)

    def test_native_superset_children_each_keep_the_full_listed_set_count(self) -> None:
        for index, rule in enumerate(self.payload["exercises"], start=1):
            rule["coach_aliases"] = ["Coach Pair"]
            rule["superset_group"] = "SS1"
            rule["superset_order"] = index
        self.write_coach(sets=5, one_row_per_day=True)
        report = self.preview()

        self.assertTrue(report.generation_safe, report.blocking_issues)
        for day in report.program.days:
            self.assertEqual(len(day.exercises), 2)
            for index, exercise in enumerate(day.exercises, start=1):
                self.assertEqual(exercise.mapping_status, "exact_superset")
                self.assertEqual((exercise.superset.group, exercise.superset.order), ("SS1", index))
                self.assertEqual(exercise.prescriptions[0].set_count.value, 5)

        generate_program(report, self.template, self.output)
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        for row in range(4, 12):
            self.assertEqual(cells[f"U{row}"].value, "Standard Set")
            self.assertIn(" ∈ SS1", cells[f"B{row}"].value)
        self.assertTrue(audit_program_output(report.program, self.output, self.template).passed)


if __name__ == "__main__":
    unittest.main()
