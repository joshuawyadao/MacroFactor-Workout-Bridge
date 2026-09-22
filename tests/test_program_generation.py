from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template

from tests.xlsx_factory import (
    add_day_header,
    write_macrofactor_program_template,
    write_program_workbook,
)


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def rewrite_zip_member(path: Path, member: str, transform) -> None:
    replacement = path.with_name(f"{path.stem}-replacement.xlsx")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(replacement, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == member:
                data = transform(data)
            target.writestr(info, data)
    replacement.replace(path)


class ProgramGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config_path = self.root / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "workbook": {
                        "exercise_header_labels": ["Variation", "Exercise"],
                        "week_header_pattern": "^week\\s*\\d+$",
                    },
                    "program": {
                        "week_pair_layout": "plan_then_result",
                        "defaults": {},
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
            ),
            encoding="utf-8",
        )
        self.config = load_config(self.config_path)
        self.template = self.root / "template.xlsx"
        write_macrofactor_program_template(
            self.template,
            day_row_counts=(2,),
            max_sets=4,
        )

    def write_coach(
        self,
        *,
        week_one: str = "3 x 8-10 @ 2 RIR, 120 sec rest",
        week_two: str = "3 x 8-10 @ 2 RIR, 120 sec rest",
        style: str = "Straight Sets",
    ) -> Path:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        for row, exercise in ((6, "Coach Alpha"), (7, "Coach Beta")):
            cells.update(
                {
                    f"D{row}": style,
                    f"E{row}": exercise,
                    f"F{row}": None,
                    f"G{row}": None,
                    f"H{row}": None,
                    f"J{row}": week_one,
                    f"K{row}": "PRIVATE-COMPLETED-RESULT",
                    f"L{row}": week_two,
                    f"M{row}": None,
                }
            )
        coach = self.root / "coach.xlsx"
        write_program_workbook(
            coach,
            sheet_name="Synthetic Program",
            cells=cells,
            merges=("J5:K5", "L5:M5"),
        )
        return coach

    def preview(
        self,
        coach: Path,
        *,
        weeks: tuple[str, ...] = ("Week 1", "Week 2"),
        template: Path | None = None,
    ):
        return build_program_preview(
            coach,
            self.config,
            "Synthetic Program",
            "block-1",
            weeks,
            template_path=template or self.template,
        )

    def test_inspects_anonymized_verified_template_structure(self) -> None:
        schema = inspect_program_template(self.template)

        self.assertEqual(schema.sheet_name, "Training Programs")
        self.assertEqual((schema.program_cell, schema.cycles_cell), ("A1", "B1"))
        self.assertEqual([len(day.rows) for day in schema.days], [2])
        self.assertEqual(len(schema.sets), 4)
        self.assertEqual(schema.sets[0].number, 1)

    def test_rejects_ambiguous_headers_and_unpreservable_package_features(self) -> None:
        duplicate_header = self.root / "duplicate-header.xlsx"
        write_macrofactor_program_template(duplicate_header)
        rewrite_zip_member(
            duplicate_header,
            "xl/sharedStrings.xml",
            lambda data: data.replace(b"Set 2 Type", b"Set 1 Type", 1),
        )
        with self.assertRaisesRegex(WorkbookError, "header must occur exactly once"):
            inspect_program_template(duplicate_header)

        missing_relationship = self.root / "missing-relationship.xlsx"
        write_macrofactor_program_template(missing_relationship)

        def remove_styles_relationship(data: bytes) -> bytes:
            root = ET.fromstring(data)
            for relationship in list(root):
                if relationship.attrib.get("Type", "").endswith("/styles"):
                    root.remove(relationship)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)

        rewrite_zip_member(
            missing_relationship,
            "xl/_rels/workbook.xml.rels",
            remove_styles_relationship,
        )
        with self.assertRaisesRegex(WorkbookError, "styles relationship"):
            inspect_program_template(missing_relationship)

        invalid_style = self.root / "invalid-style.xlsx"
        write_macrofactor_program_template(invalid_style)

        def invalidate_style_index(data: bytes) -> bytes:
            root = ET.fromstring(data)
            cell = next(
                item
                for item in root.iter(f"{{{MAIN_NS}}}c")
                if item.attrib.get("r") == "B4"
            )
            cell.attrib["s"] = "999"
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)

        rewrite_zip_member(
            invalid_style,
            "xl/worksheets/sheet1.xml",
            invalidate_style_index,
        )
        with self.assertRaisesRegex(WorkbookError, "references a missing style"):
            inspect_program_template(invalid_style)

        rich_string = self.root / "rich-string.xlsx"
        write_macrofactor_program_template(rich_string)

        def add_rich_string_run(data: bytes) -> bytes:
            root = ET.fromstring(data)
            item = root.find(f"{{{MAIN_NS}}}si")
            assert item is not None
            text = item.find(f"{{{MAIN_NS}}}t")
            assert text is not None
            item.remove(text)
            run = ET.SubElement(item, f"{{{MAIN_NS}}}r")
            run.append(text)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)

        rewrite_zip_member(
            rich_string,
            "xl/sharedStrings.xml",
            add_rich_string_run,
        )
        with self.assertRaisesRegex(WorkbookError, "Rich or extended shared strings"):
            inspect_program_template(rich_string)

        malformed_worksheet = self.root / "malformed-worksheet.xlsx"
        write_macrofactor_program_template(malformed_worksheet)
        rewrite_zip_member(
            malformed_worksheet,
            "xl/worksheets/sheet1.xml",
            lambda _: b"<worksheet",
        )
        with self.assertRaisesRegex(WorkbookError, "Invalid program template OOXML"):
            inspect_program_template(malformed_worksheet)

    def test_generates_homogeneous_cycles_and_validates_round_trip(self) -> None:
        coach = self.write_coach()
        coach_hash = file_sha256(coach)
        template_hash = file_sha256(self.template)
        report = self.preview(coach)
        output = self.root / "generated.xlsx"

        self.assertTrue(report.template_schema_verified)
        self.assertTrue(report.generation_safe)
        generate_program(report, self.template, output)

        self.assertEqual(file_sha256(coach), coach_hash)
        self.assertEqual(file_sha256(self.template), template_hash)
        self.assertEqual(report.source_hash_before, report.source_hash_after)
        self.assertEqual(report.template_hash, report.template_hash_after)
        self.assertEqual(report.output_file, str(output))
        self.assertFalse(report.manual_import_verified)
        self.assertEqual(report.validation["unrelated_members_changed"], [])
        self.assertEqual(inspect_program_template(output), inspect_program_template(self.template))

        snapshot = XlsxPackage(output).sheet_snapshot("Training Programs")
        self.assertEqual(snapshot.cells["A1"].value, "Program: Synthetic Program block-1")
        self.assertEqual(snapshot.cells["B1"].value, "Cycles: 2")
        self.assertEqual(snapshot.cells["A4"].value, "Day 1")
        self.assertEqual(snapshot.cells["B4"].value, "Synthetic Alpha")
        self.assertEqual(snapshot.cells["E4"].value, "Standard Set")
        self.assertEqual(snapshot.cells["F4"].value, "8 - 10")
        self.assertEqual(snapshot.cells["G4"].value, 2)
        self.assertEqual(snapshot.cells["H4"].value, 120)
        self.assertIsNone(snapshot.cells["Q4"].value)
        with zipfile.ZipFile(output) as archive:
            shared_strings = archive.read("xl/sharedStrings.xml")
        self.assertNotIn(b"Old Exercise", shared_strings)
        self.assertNotIn(b"Old Note", shared_strings)
        self.assertNotIn(b"PRIVATE-COMPLETED-RESULT", shared_strings)

    def test_generation_blocks_unproved_periodization_shape_and_set_semantics(self) -> None:
        differing = self.preview(
            self.write_coach(week_two="4 x 6-8 @ 1 RIR, 90 sec rest")
        )
        self.assertFalse(differing.generation_safe)
        self.assertTrue(
            any(
                issue.code == "periodized_template_required"
                for issue in differing.blocking_issues
            )
        )

        too_many = self.preview(
            self.write_coach(
                week_one="5 x 8-10 @ 2 RIR, 120 sec rest",
                week_two="5 x 8-10 @ 2 RIR, 120 sec rest",
            )
        )
        self.assertTrue(
            any(
                issue.code == "template_set_capacity_exceeded"
                for issue in too_many.blocking_issues
            )
        )

        unsupported = self.preview(self.write_coach(style="Drop Set"))
        self.assertTrue(
            any(
                issue.code == "unsupported_template_set_type"
                for issue in unsupported.blocking_issues
            )
        )

        ungrouped_superset = self.preview(self.write_coach(style="Superset"))
        self.assertTrue(
            any(
                issue.code == "missing_superset_membership"
                for issue in ungrouped_superset.blocking_issues
            )
        )

        shape_template = self.root / "shape-template.xlsx"
        write_macrofactor_program_template(shape_template, day_row_counts=(1,))
        shape = self.preview(self.write_coach(), template=shape_template)
        self.assertTrue(
            any(
                issue.code == "template_exercise_shape_mismatch"
                for issue in shape.blocking_issues
            )
        )

    def test_generation_refuses_overwrite_and_changed_inputs(self) -> None:
        coach = self.write_coach()
        report = self.preview(coach)
        output = self.root / "existing.xlsx"
        output.write_bytes(b"keep")

        with self.assertRaisesRegex(WorkbookError, "already exists"):
            generate_program(report, self.template, output)
        self.assertEqual(output.read_bytes(), b"keep")

        changed_output = self.root / "changed.xlsx"
        self.write_coach(week_one="2 x 8-10 @ 2 RIR, 120 sec rest")
        with self.assertRaisesRegex(WorkbookError, "changed after preview"):
            generate_program(report, self.template, changed_output)
        self.assertFalse(changed_output.exists())

        coach = self.write_coach()
        report = self.preview(coach)
        write_macrofactor_program_template(
            self.template,
            day_row_counts=(2,),
            max_sets=3,
        )
        with self.assertRaisesRegex(WorkbookError, "template changed after preview"):
            generate_program(
                report,
                self.template,
                self.root / "changed-template.xlsx",
            )

    def test_explicit_superset_membership_is_written_in_configured_order(self) -> None:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        for index, exercise in enumerate(payload["exercises"], start=1):
            exercise["coach_aliases"] = ["Coach Pair"]
            exercise["superset_group"] = "SS1"
            exercise["superset_order"] = index
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        self.config = load_config(self.config_path)
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        cells.update(
            {
                "D6": "Straight Sets",
                "E6": "Coach Pair",
                "F6": None,
                "G6": None,
                "H6": None,
                "J6": "3 x 8-10 @ 2 RIR, 120 sec rest",
                "K6": None,
                "L6": "3 x 8-10 @ 2 RIR, 120 sec rest",
                "M6": None,
            }
        )
        coach = self.root / "superset-coach.xlsx"
        write_program_workbook(
            coach,
            sheet_name="Synthetic Program",
            cells=cells,
            merges=("J5:K5", "L5:M5"),
        )
        conflicting = self.preview(coach)
        self.assertTrue(
            any(
                issue.code == "conflicting_superset_membership"
                for issue in conflicting.blocking_issues
            )
        )

        cells["D6"] = "Superset"
        write_program_workbook(
            coach,
            sheet_name="Synthetic Program",
            cells=cells,
            merges=("J5:K5", "L5:M5"),
        )
        report = self.preview(coach)
        output = self.root / "superset-output.xlsx"

        self.assertTrue(report.generation_safe)
        generate_program(report, self.template, output)
        snapshot = XlsxPackage(output).sheet_snapshot("Training Programs")
        self.assertEqual(snapshot.cells["B4"].value, "Synthetic Alpha ∈ SS1")
        self.assertEqual(snapshot.cells["B5"].value, "Synthetic Beta ∈ SS1")
        self.assertEqual(snapshot.cells["E4"].value, "Standard Set")

    def test_invalid_template_is_reported_and_cli_generates_only_new_outputs(self) -> None:
        coach = self.write_coach()
        invalid = self.preview(coach, template=coach)
        self.assertFalse(invalid.template_schema_verified)
        self.assertTrue(
            any(issue.code == "invalid_program_template" for issue in invalid.blocking_issues)
        )

        output = self.root / "cli-output.xlsx"
        report_path = self.root / "cli-report.json"
        with redirect_stdout(StringIO()):
            exit_code = main(
                [
                    "program-generate",
                    "--workbook",
                    str(coach),
                    "--config",
                    str(self.config_path),
                    "--template",
                    str(self.template),
                    "--output",
                    str(output),
                    "--sheet",
                    "Synthetic Program",
                    "--block",
                    "block-1",
                    "--week",
                    "Week 1",
                    "--week",
                    "Week 2",
                    "--report",
                    str(report_path),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertTrue(output.exists())
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["template_schema_verified"])
        self.assertEqual(payload["output_file"], str(output))
        self.assertFalse(payload["manual_import_verified"])


if __name__ == "__main__":
    unittest.main()
