from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import MAIN_NS, WorkbookError, file_sha256
from macrofactor_bridge.program_service import build_program_preview, generate_program
from tests.test_program_generation import rewrite_zip_member
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_macrofactor_program_template, write_program_workbook


class StandaloneSourceCoverageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.config_path = self.root / "config.json"
        write_macrofactor_program_template(self.template)
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        exercise_row(self.cells, 6, name="Alpha Move")
        exercise_row(self.cells, 7, name="Beta Move")
        self.merges = ("J5:K5", "L5:M5")

    def preview(self, *, source="base", weeks=("Week 1",), marker=None):
        self.config_path.write_text(json.dumps({
            "program": {"prescription_source": source, "week_pair_layout": "plan_then_result",
                        "allow_blank_targets": True, "preserve_coach_notes": True,
                        "resize_template_workouts": True,
                        "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Alpha", "coach_aliases": ["Alpha Move"]},
                          {"canonical": "Beta", "coach_aliases": ["Beta Move"]}],
        }))
        config = load_config(self.config_path)
        write_program_workbook(self.coach, sheet_name="Synthetic", cells=self.cells, merges=self.merges)
        block = discover_program_blocks(self.coach, config)[0]
        report = build_program_preview(self.coach, config, "Synthetic", block.identifier, weeks,
                                       self.template, reference_boundary_marker=marker)
        return report

    def test_authored_row_after_blank_gap_blocks_base_and_week_modes(self):
        exercise_row(self.cells, 9, name="Beta Move")
        for source in ("base", "selected_week"):
            with self.subTest(source=source):
                report = self.preview(source=source)
                self.assertEqual([e.source_row for e in report.program.days[0].exercises], [6, 7])
                self.assertFalse(report.generation_safe)
                self.assertIn("source_audit_row_coverage", {i.code for i in report.issues})
                with self.assertRaisesRegex(WorkbookError, "blocking"):
                    generate_program(report, self.template, self.root / "output.xlsx")
                self.assertFalse((self.root / "output.xlsx").exists())

    def test_intentional_week_subset_and_week_only_note_are_allowed(self):
        self.cells["J9"] = "Read week 1 coaching note"
        report = self.preview(weeks=("Week 2",))
        self.assertTrue(report.generation_safe, report.issues)
        self.assertEqual(report.included_weeks, ("Week 2",))

    def test_reviewed_reference_marker_bounds_final_day_only(self):
        self.cells["D10"] = "Reviewed footer"
        exercise_row(self.cells, 12, name="Beta Move")
        self.merges += ("D10:E10",)
        self.assertFalse(self.preview().generation_safe)
        accepted = self.preview(marker="Reviewed footer")
        self.assertTrue(accepted.generation_safe, accepted.issues)
        self.assertEqual([e.source_row for e in accepted.program.days[0].exercises], [6, 7])
        self.assertIn("source_audit_reference_boundary",
                      {i.code for i in self.preview(marker="Wrong footer").issues})

    def test_orphan_base_field_after_gap_blocks_preview(self):
        self.cells["F9"] = 3
        report = self.preview()
        self.assertIn("source_audit_orphan_prescription", {i.code for i in report.issues})
        self.assertFalse(report.generation_safe)

    def test_formula_base_cell_after_gap_blocks_preview_even_without_cached_value(self):
        self.cells["F9"] = None
        self.preview()
        def add_formula(data):
            ns = "{" + MAIN_NS + "}"
            root = ET.fromstring(data)
            cell = next(node for node in root.iter(ns + "c") if node.attrib["r"] == "F9")
            ET.SubElement(cell, ns + "f").text = "3"
            return ET.tostring(root)
        rewrite_zip_member(self.coach, "xl/worksheets/sheet1.xml", add_formula)
        config = load_config(self.config_path)
        block = discover_program_blocks(self.coach, config)[0]
        report = build_program_preview(self.coach, config, "Synthetic", block.identifier,
                                       ("Week 1",), self.template)
        self.assertFalse(report.generation_safe)
        self.assertIn("source_audit_formula", {i.code for i in report.issues})

    def test_source_mutation_during_added_scan_invalidates_preview(self):
        from macrofactor_bridge.program_audit import audit_program_source_rows

        original = audit_program_source_rows
        def scan_then_mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            with self.coach.open("ab") as stream:
                stream.write(b"mutation")
            return result
        with patch("macrofactor_bridge.program_service.audit_program_source_rows", side_effect=scan_then_mutate):
            report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("source_changed_during_preview", {i.code for i in report.issues})
        self.assertNotEqual(file_sha256(self.coach), report.source_hash_before)


if __name__ == "__main__":
    unittest.main()
