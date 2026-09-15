from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import XlsxPackage, file_sha256
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template
from tests.xlsx_factory import add_day_header, write_program_workbook, write_macrofactor_program_template
from tests.test_program_preview import exercise_row
from tests.test_program_generation import rewrite_zip_member


class ProgramPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config_path = self.root / "config.json"
        self.payload = {
            "workbook": {"exercise_header_labels": ["Style"]},
            "program": {
                "week_pair_layout": "plan_then_result",
                "sheet_order": "right_to_left",
                "rest_range_policy": "upper",
                "allow_blank_targets": True,
                "preserve_coach_notes": True,
                "exclude_warmups": True,
                "exclude_cardio": True,
                "defaults": {"set_type": "standard"},
            },
            "exercises": [
                {"canonical": "Machine Alpha", "coach_aliases": ["Push"],
                 "coach_context_aliases": ["Machine with a pause"]},
                {"canonical": "Machine Beta", "coach_aliases": ["Push"],
                 "coach_context_aliases": ["Another machine"]},
            ],
        }
        self.coach = self.root / "coach.xlsx"

    def config(self):
        self.config_path.write_text(json.dumps(self.payload), encoding="utf-8")
        return load_config(self.config_path)

    def write(self, cells, merges=("J5:K5", "L5:M5")):
        write_program_workbook(self.coach, sheet_name="Early Block", cells=cells, merges=merges)

    def preview(self, *, template=None):
        return build_program_preview(
            self.coach, self.config(), "Early Block", "block-1", ("Week 1",), template_path=template
        )

    def row(self, cells, row=7, **kwargs):
        exercise_row(cells, row, name="Machine with a pause", style="Push", **kwargs)

    def test_shared_week_headers_and_variation_context_keep_all_days(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        add_day_header(cells, row=12, day="Day 3.5")
        cells.pop("J12")
        cells.pop("L12")
        self.row(cells, row=14)
        self.write(cells)

        blocks = discover_program_blocks(self.coach, self.config())
        self.assertEqual(blocks[0].week_labels, ("Week 1", "Week 2"))
        report = self.preview()
        self.assertEqual([day.label for day in report.program.days], ["Day 1", "Day 3.5"])
        for day in report.program.days:
            exercise = day.exercises[0]
            self.assertEqual(exercise.coach_name, "Push")
            self.assertEqual(exercise.macrofactor_name, "Machine Alpha")
            self.assertEqual(exercise.raw_base_fields["variation"], "Machine with a pause")

    def test_shared_week_headers_do_not_cross_a_block_reset(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        add_day_header(cells, row=12, day="Day 1")
        cells.pop("J12")
        cells.pop("L12")
        self.row(cells, row=14)
        self.write(cells)
        blocks = discover_program_blocks(self.coach, self.config())
        self.assertEqual(blocks[1].week_labels, ())

    def test_sheet_order_can_start_at_the_last_worksheet(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        self.write(cells)
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

        def second_sheet(data):
            root = ET.fromstring(data)
            ET.SubElement(root.find(f"{{{ns}}}sheets"), f"{{{ns}}}sheet", {
                "name": "Oldest Block", "sheetId": "2", f"{{{rel}}}id": "rId2",
            })
            return ET.tostring(root)

        def relationship(data):
            root = ET.fromstring(data)
            ET.SubElement(root, f"{{{package_rel}}}Relationship", {
                "Id": "rId2", "Type": f"{rel}/worksheet", "Target": "worksheets/sheet2.xml",
            })
            return ET.tostring(root)

        rewrite_zip_member(self.coach, "xl/workbook.xml", second_sheet)
        rewrite_zip_member(self.coach, "xl/_rels/workbook.xml.rels", relationship)
        def content_type(data):
            root = ET.fromstring(data)
            ET.SubElement(root, "{http://schemas.openxmlformats.org/package/2006/content-types}Override", {
                "PartName": "/xl/worksheets/sheet2.xml",
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
            })
            return ET.tostring(root)
        rewrite_zip_member(self.coach, "[Content_Types].xml", content_type)
        with zipfile.ZipFile(self.coach, "a") as archive:
            archive.writestr("xl/worksheets/sheet2.xml", archive.read("xl/worksheets/sheet1.xml"))
        self.assertEqual(
            [block.sheet for block in discover_program_blocks(self.coach, self.config())],
            ["Oldest Block", "Early Block"],
        )

    def test_weekly_footer_text_does_not_extend_the_exercise_table(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        cells["J8"] = "Future coaching updates"
        cells["D9"] = "Reference legend"
        self.write(cells)
        report = self.preview()
        self.assertEqual(len(report.program.days[0].exercises), 1)

    def test_specific_variation_cannot_fall_back_to_unqualified_modern_alias(self):
        self.payload["exercises"][0].pop("coach_context_aliases")
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        self.write(cells)
        exercise = self.preview().program.days[0].exercises[0]
        self.assertIsNone(exercise.macrofactor_name)
        self.assertEqual(exercise.mapping_status, "unmatched")

    def test_date_formatted_rep_cell_is_not_a_large_rep_prescription(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, reps=45000, week_one="Technique notes")
        self.write(cells)
        with zipfile.ZipFile(self.coach, "a") as archive:
            archive.writestr("xl/styles.xml", (
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<numFmts count="1"><numFmt numFmtId="164" formatCode="m-d"/></numFmts>'
                '<cellXfs count="1"><xf numFmtId="164"/></cellXfs></styleSheet>'
            ))
        report = self.preview()
        rx = report.program.days[0].exercises[0].prescriptions[0]
        self.assertIsNone(rx.rep_min.value)
        self.assertIn("date_formatted_rep_target", {issue.code for issue in report.issues})

    def test_explicit_superset_mapping_is_preserved_with_standard_default(self):
        for index, rule in enumerate(self.payload["exercises"], start=1):
            rule["coach_context_aliases"] = ["Machine with a pause"]
            rule["superset_group"] = "SS1"
            rule["superset_order"] = index
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells)
        self.write(cells)
        template = self.root / "template.xlsx"
        write_macrofactor_program_template(template, day_row_counts=(2,))
        report = self.preview(template=template)
        self.assertTrue(report.generation_safe)
        for index, exercise in enumerate(report.program.days[0].exercises, start=1):
            self.assertEqual(exercise.superset.order, index)
            self.assertEqual(exercise.prescriptions[0].set_type.source, "config_superset")
        output = self.root / "superset.xlsx"
        generate_program(report, template, output)
        cells = XlsxPackage(output).sheet_snapshot("Training Programs").cells
        self.assertEqual(cells["B4"].value, "Machine Alpha ∈ SS1")
        self.assertEqual(cells["B5"].value, "Machine Beta ∈ SS1")

    def test_policy_defaults_rest_ranges_and_deferred_targets_keep_notes(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, reps="Read week", rest="2-3 minutes (timed)",
                 week_one="Keep the first two sets easy; use 40 lb")
        self.write(cells)
        report = self.preview()
        prescription = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual(prescription.set_type.value, "standard")
        self.assertEqual(prescription.set_type.source, "config_default")
        self.assertEqual(prescription.rest_seconds.value, 180)
        self.assertIsNone(prescription.rep_min.value)
        self.assertEqual(prescription.rep_max.source, "blank_by_policy")
        self.assertIsNone(prescription.rir.value)
        self.assertIn("Machine with a pause", "\n".join(prescription.notes))
        self.assertIn("40 lb", "\n".join(prescription.notes))
        self.assertIn("upper rest", "\n".join(prescription.notes))
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(report.to_dict()))
        self.assertEqual({issue.code for issue in report.blocking_issues}, {"direct_program_export_required"})

    def test_notes_policy_never_interprets_a_bare_week_weight_as_reps(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, reps="8 to 12", week_one=140)
        self.write(cells)
        prescription = self.preview().program.days[0].exercises[0].prescriptions[0]
        self.assertEqual((prescription.rep_min.value, prescription.rep_max.value), (8, 12))
        self.assertIn("Week 1: 140", prescription.notes)

    def test_exclusions_apply_before_mapping_and_preserve_optional_exercises(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1 (Optional)")
        self.row(cells)
        exercise_row(cells, 8, name="Unmapped prep", style="Prep", week_one="Warm up movement")
        exercise_row(cells, 9, name="Unmapped cardio", style="Cardio")
        self.write(cells)
        report = self.preview()
        self.assertEqual(len(report.skipped_items), 2)
        self.assertTrue(report.program.days[0].optional)
        self.assertFalse(report.program.days[0].exercises[0].excluded)
        self.assertFalse(any(issue.code == "unmatched_exercise" for issue in report.issues))

    def test_special_set_instructions_override_standard_default_and_stay_gated(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, week_one="Use myo rep match")
        self.row(cells, row=8, week_one="Use myo rep match")
        self.write(cells)
        template = self.root / "template.xlsx"
        write_macrofactor_program_template(template, day_row_counts=(2,))
        report = self.preview(template=template)
        field = report.program.days[0].exercises[0].prescriptions[0].set_type
        self.assertEqual(field.value, "myo")
        self.assertEqual((field.source, field.source_cell, field.raw_text),
                         ("coach_week", "J7", "Use myo rep match"))
        self.assertFalse(report.generation_safe)
        self.assertIn("unsupported_template_set_type", {issue.code for issue in report.blocking_issues})

    def test_set_count_ranges_are_not_resolved_by_rest_or_blank_policy(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, sets="2 to 3", rest="2-3 minutes", week_one="Pause each rep")
        self.write(cells)
        report = self.preview()
        prescription = report.program.days[0].exercises[0].prescriptions[0]
        self.assertIsNone(prescription.set_count.value)
        self.assertEqual(prescription.rest_seconds.value, 180)
        self.assertIn("unsupported_base_value", {issue.code for issue in report.blocking_issues})

    def test_explicit_base_set_type_cannot_be_overridden_without_review(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, week_one="Use drop sets")
        cells["D7"] = "Standard"
        self.write(cells)
        report = self.preview()
        self.assertIn("mixed_set_types", {issue.code for issue in report.blocking_issues})

    def test_blank_targets_round_trip_as_blank_active_sets(self):
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        self.row(cells, reps="Read week", rest=None, week_one="Pause each rep")
        self.row(cells, row=8, reps="Read week", rest=None, week_one="Pause each rep")
        self.write(cells)
        template = self.root / "template.xlsx"
        write_macrofactor_program_template(template, day_row_counts=(2,))
        hashes = (file_sha256(self.coach), file_sha256(template))
        report = self.preview(template=template)
        self.assertTrue(report.generation_safe)
        output = self.root / "output.xlsx"
        generate_program(report, template, output)
        snapshot = XlsxPackage(output).sheet_snapshot("Training Programs")
        self.assertEqual(snapshot.cells["E4"].value, "Standard Set")
        for reference in ("F4", "G4", "H4", "J4", "K4", "L4"):
            self.assertIsNone(snapshot.cells[reference].value)
        self.assertIn("Pause each rep", snapshot.cells["D4"].value)
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(template)))
        self.assertNotIn("PRIVATE-COMPLETED-RESULT", snapshot.cells["D4"].value)

    def test_invalid_policy_values_are_rejected(self):
        for key, value in (("allow_blank_targets", "true"), ("rest_range_policy", "average"),
                           ("sheet_order", "by_date"), ("exclude_warmups", 1)):
            with self.subTest(key=key):
                before = self.payload["program"][key]
                self.payload["program"][key] = value
                with self.assertRaises(ConfigError):
                    self.config()
                self.payload["program"][key] = before

    def test_resize_preserves_days_headers_notes_and_unrelated_parts(self):
        self.payload["program"]["resize_template_workouts"] = True
        cells = {}
        counts = (3, 2, 5)
        header_row = 5
        merges = []
        for day_number, count in enumerate(counts, start=1):
            add_day_header(cells, row=header_row, day=f"Day {day_number}")
            merges.extend((f"J{header_row}:K{header_row}", f"L{header_row}:M{header_row}"))
            for row in range(header_row + 1, header_row + count + 1):
                self.row(cells, row=row, reps="Read week", week_one="Pause at the top")
            header_row += count + 3
        self.write(cells, merges=tuple(merges))
        template = self.root / "different-shape.xlsx"
        write_macrofactor_program_template(template, day_row_counts=(2, 4, 3))
        hashes = (file_sha256(self.coach), file_sha256(template))
        report = self.preview(template=template)
        self.assertTrue(report.generation_safe, report.blocking_issues)
        output = self.root / "resized.xlsx"
        generate_program(report, template, output)
        schema = inspect_program_template(output)
        self.assertEqual([len(day.rows) for day in schema.days], list(counts))
        self.assertEqual(schema.header_row, 3)
        snapshot = XlsxPackage(output).sheet_snapshot(schema.sheet_name)
        for number, day in enumerate(schema.days, start=1):
            self.assertEqual(snapshot.cells[day.label_cell].value, f"Day {number}")
            for row in day.rows:
                self.assertEqual(snapshot.cells[f"B{row}"].value, "Machine Alpha")
                self.assertIn("Pause at the top", snapshot.cells[f"D{row}"].value)
                self.assertIsNone(snapshot.cells[f"F{row}"].value)
        with zipfile.ZipFile(template) as source, zipfile.ZipFile(output) as generated:
            self.assertEqual(set(source.namelist()), set(generated.namelist()))
            for name in source.namelist():
                if name not in {schema.sheet_path, "xl/sharedStrings.xml"}:
                    self.assertEqual(source.read(name), generated.read(name), name)
            self.assertNotIn(b"Old Exercise", generated.read("xl/sharedStrings.xml"))
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(template)))

    def test_resize_refuses_reference_bearing_template_features(self):
        self.payload["program"]["resize_template_workouts"] = True
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        for row in (7, 8, 9):
            self.row(cells, row=row)
        self.write(cells)
        template = self.root / "filtered.xlsx"
        write_macrofactor_program_template(template, day_row_counts=(2,))

        def add_filter(data):
            root = ET.fromstring(data)
            ET.SubElement(root, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}autoFilter",
                          {"ref": "B3:T5"})
            return ET.tostring(root)

        rewrite_zip_member(template, "xl/worksheets/sheet1.xml", add_filter)
        report = self.preview(template=template)
        self.assertFalse(report.generation_safe)
        self.assertTrue(any("worksheet features" in issue.message for issue in report.blocking_issues))


if __name__ == "__main__":
    unittest.main()
