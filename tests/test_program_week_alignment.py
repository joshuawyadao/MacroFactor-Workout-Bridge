from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import MAIN_NS, WorkbookError, file_sha256
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_batch import _discovery_settings
from macrofactor_bridge.program_service import build_program_preview
from tests.test_program_generation import rewrite_zip_member
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_program_workbook


class ProgramWeekAlignmentTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "coach.xlsx"
        self.payload = {
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "week_header_coverage_policy": "aligned_union_base_only",
                        "allow_blank_targets": True, "preserve_coach_notes": True,
                        "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Alpha", "coach_aliases": ["Alpha Move"]}],
        }
        self.cells = {}
        self.merges = []
        for number, row in enumerate((5, 12), 1):
            add_day_header(self.cells, row=row, day=f"Day {number}")
            exercise_row(self.cells, row + 1, name="Alpha Move")
            for week, (plan, result) in enumerate((("J", "K"), ("L", "M"), ("N", "O"), ("P", "Q")), 1):
                self.cells[f"{plan}{row}"] = f"Week {week}"
                self.cells[f"{plan}{row + 1}"] = f"RAW-PLAN-{week}"
                self.cells[f"{result}{row + 1}"] = "RESULT-SENTINEL"
                self.merges.append(f"{plan}{row}:{result}{row}")
        del self.cells["P5"]

    def config(self):
        path = self.root / "config.json"
        path.write_text(json.dumps(self.payload))
        return load_config(path)

    def write(self):
        write_program_workbook(self.path, sheet_name="Synthetic", cells=self.cells, merges=tuple(self.merges))

    def prepare(self, weeks=None):
        self.write()
        self.cfg = self.config()
        self.block = discover_program_blocks(self.path, self.cfg)[0]
        self.report = build_program_preview(self.path, self.cfg, "Synthetic", "block-1", weeks or self.block.week_labels)

    def audit(self, complete=True):
        return audit_coach_program(self.path, self.cfg, self.block, self.report,
                                   require_complete_week_coverage=complete)

    def formula(self, reference):
        def add_formula(data):
            root = ET.fromstring(data)
            cell = root.find(f".//{{{MAIN_NS}}}c[@r='{reference}']")
            ET.SubElement(cell, f"{{{MAIN_NS}}}f").text = '"cached"'
            return ET.tostring(root)
        rewrite_zip_member(self.path, "xl/worksheets/sheet1.xml", add_formula)

    def assertUnsafe(self):
        self.write()
        with self.assertRaises(WorkbookError):
            discover_program_blocks(self.path, self.config())

    def test_partial_first_day_uses_later_complete_anchor_and_preserves_raw_plans(self):
        self.prepare()
        self.assertEqual(self.block.week_labels, ("Week 1", "Week 2", "Week 3", "Week 4"))
        before = file_sha256(self.path)
        rx = self.report.program.days[0].exercises[0].prescriptions[-1]
        self.assertEqual((rx.set_count.value, rx.rep_min.value, rx.rep_max.value), (3, 8, 10))
        self.assertEqual(rx.raw_week_text, "RAW-PLAN-4")
        self.assertEqual(rx.raw_unparsed_text, "RAW-PLAN-4")
        self.assertNotIn("RESULT-SENTINEL", json.dumps(self.report.to_dict()))
        warnings = [issue for issue in self.report.issues if issue.code == "aligned_week_header_inherited"]
        self.assertEqual([(issue.day, issue.cell, issue.cycle) for issue in warnings], [("Day 1", "P12", "Week 4")])
        with patch("macrofactor_bridge.coach_program._align_base_week_headers", side_effect=AssertionError("audit depends on parser")):
            self.assertTrue(self.audit().passed, self.audit().issues)
        self.assertEqual(before, file_sha256(self.path))

    def test_default_intersection_is_unchanged_and_all_week_audit_still_blocks_shortening(self):
        del self.payload["program"]["week_header_coverage_policy"]
        self.prepare()
        self.assertEqual(self.cfg.program.week_header_coverage_policy, "intersection")
        self.assertEqual(self.block.week_labels, ("Week 1", "Week 2", "Week 3"))
        self.assertFalse(self.audit().passed)

    def test_intentional_subset_requires_non_complete_audit(self):
        self.prepare(("Week 1", "Week 2"))
        self.assertTrue(self.audit(complete=False).passed)
        self.assertIn("source_audit_complete_week_coverage", {issue.code for issue in self.audit().issues})

    def test_completely_unlabeled_first_day_uses_same_block_anchor(self):
        for col in ("J", "L", "N"):
            del self.cells[f"{col}5"]
        self.prepare()
        self.assertEqual(len(self.block.week_labels), 4)
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_adjacent_days_do_not_read_prior_exercise_plans_or_results_as_headers(self):
        for column in ("D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "O", "P", "Q"):
            self.cells[f"{column}11"] = self.cells.pop(f"{column}6")
        self.cells["J11"] = "Week 1"
        self.cells["P11"] = "Week 4"
        self.cells["Q11"] = "Week 99"
        self.prepare()
        self.assertEqual(self.block.week_labels, ("Week 1", "Week 2", "Week 3", "Week 4"))
        first_day = self.report.program.days[0]
        self.assertEqual(first_day.exercises[0].source_row, 11)
        self.assertEqual(first_day.exercises[0].prescriptions[0].raw_week_text, "Week 1")
        self.assertEqual(first_day.exercises[0].prescriptions[-1].raw_week_text, "Week 4")
        self.assertNotIn("Week 99", json.dumps(self.report.to_dict()))
        self.assertNotIn("RESULT-SENTINEL", json.dumps(self.report.to_dict()))
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_full_base_schema_must_match_even_when_required_columns_match(self):
        self.payload["program"]["exercise_header_labels"] = ["Exercise"]
        self.cells.update({"E5": "Exercise", "E12": "Exercise", "I12": "Variation"})
        self.assertUnsafe()

    def test_unmerged_pairs_require_structural_adjacency(self):
        self.merges = []
        self.prepare()
        self.assertTrue(self.audit().passed, self.audit().issues)
        del self.cells["L5"]
        self.assertUnsafe()

    def test_policy_requires_base_mode_and_explicit_direction(self):
        for update in ({"prescription_source": "selected_week"}, {"week_pair_layout": None},
                       {"week_header_coverage_policy": "guess"}):
            with self.subTest(update=update):
                original = dict(self.payload["program"])
                self.payload["program"].update(update)
                with self.assertRaises(ConfigError):
                    self.config()
                self.payload["program"] = original

    def test_policy_participates_in_batch_discovery_consistency(self):
        config = self.config()
        other = replace(config, program=replace(config.program, week_header_coverage_policy="intersection"))
        self.assertNotEqual(_discovery_settings(config), _discovery_settings(other))

    def test_shifted_label_and_same_slot_different_labels_are_rejected(self):
        self.cells["N5"] = "Week 4"
        self.assertUnsafe()
        self.cells["N5"] = "Week 8"
        self.assertUnsafe()

    def test_disjoint_headers_without_complete_anchor_are_rejected(self):
        del self.cells["N12"]
        self.assertUnsafe()

    def test_duplicate_normalized_label_is_rejected(self):
        self.cells["J4"] = " WEEK 1 "
        self.assertUnsafe()

    def test_base_column_touch_is_rejected(self):
        self.cells["I5"] = "Week 5"
        self.merges.append("H5:I5")
        self.assertUnsafe()

    def test_unsafe_merged_pair_is_rejected(self):
        self.merges.remove("N5:O5")
        self.merges.append("N5:P5")
        self.assertUnsafe()

    def test_unsafe_inherited_merge_is_rejected(self):
        self.merges.remove("P5:Q5")
        self.merges.append("P4:R5")
        self.assertUnsafe()

    def two_row_headers(self):
        for source_row in (6, 13):
            for column in ("D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "O", "P", "Q"):
                self.cells[f"{column}{source_row + 1}"] = self.cells.pop(f"{column}{source_row}")
            self.cells[f"C{source_row}"] = "Upper body"
        self.merges = [f"{plan}{row}:{result}{row + 1}" for row in (5, 12)
                       for plan, result in (("J", "K"), ("L", "M"), ("N", "O"), ("P", "Q"))]

    def test_two_row_headers_end_before_base_data_and_preserve_alignment(self):
        self.two_row_headers()
        self.prepare()
        self.assertEqual(self.block.week_labels, ("Week 1", "Week 2", "Week 3", "Week 4"))
        self.assertEqual(self.report.program.days[0].exercises[0].source_row, 7)
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_vertical_header_merge_cannot_reach_first_exercise(self):
        self.two_row_headers()
        self.prepare()
        self.merges.remove("P5:Q6")
        self.merges.append("P5:Q7")
        self.assertUnsafe()
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_vertical_header_merge_cannot_cover_orphan_base_prescription(self):
        self.two_row_headers()
        self.prepare()
        self.cells["F6"] = 3
        self.assertUnsafe()
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_entire_vertical_header_merge_requires_blank_non_top_left_cells(self):
        self.two_row_headers()
        self.prepare()
        self.cells["Q6"] = "hidden header text"
        self.assertUnsafe()
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_formula_in_lower_header_merge_cell_blocks_parser_and_audit(self):
        self.two_row_headers()
        self.cells["Q6"] = None
        self.prepare()
        self.formula("Q6")
        with self.assertRaises(WorkbookError):
            discover_program_blocks(self.path, self.cfg)
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_blank_decoration_above_header_may_span_multiple_pairs(self):
        self.two_row_headers()
        self.merges.extend(("J4:M4", "J11:M11"))
        self.prepare()
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_nonheader_prose_above_day_is_not_read_as_header_data(self):
        self.two_row_headers()
        self.merges.append("J4:M4")
        self.prepare()
        self.cells["M4"] = "not blank"
        self.prepare()
        self.assertTrue(self.audit().passed, self.audit().issues)
        self.assertNotIn("not blank", str(self.report.program))

    def test_literal_previous_row_headers_are_still_observed_and_formula_guarded(self):
        for row in (5, 12):
            for plan in ("J", "L", "N", "P"):
                value = self.cells.pop(f"{plan}{row}", None)
                if value is not None:
                    self.cells[f"{plan}{row - 1}"] = value
        self.merges = [merge.replace("5", "4").replace("12", "11") for merge in self.merges]
        self.prepare()
        self.assertEqual(len(self.block.week_labels), 4)
        self.assertTrue(self.audit().passed, self.audit().issues)
        self.formula("J4")
        with self.assertRaises(WorkbookError):
            discover_program_blocks(self.path, self.cfg)
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_formula_outside_observed_header_band_is_not_imported(self):
        self.two_row_headers()
        self.merges.append("J4:M4")
        self.cells["M4"] = None
        self.prepare()
        self.formula("M4")
        self.assertEqual(discover_program_blocks(self.path, self.cfg)[0].week_labels, self.block.week_labels)
        self.assertTrue(self.audit().passed, self.audit().issues)

    def test_blank_decoration_crossing_header_is_not_ignored(self):
        self.two_row_headers()
        self.prepare()
        del self.cells["N5"]
        self.merges.append("N4:Q5")
        self.assertUnsafe()
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_missing_pair_cells_or_alternate_header_text_is_rejected(self):
        del self.cells["Q6"]
        self.assertUnsafe()
        self.cells["Q6"] = None
        self.cells["P5"] = "Other block instructions"
        self.assertUnsafe()

    def test_formula_header_blocks_discovery_and_independent_audit(self):
        self.prepare()
        self.formula("P12")
        with self.assertRaises(WorkbookError):
            discover_program_blocks(self.path, self.cfg)
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_inferred_plan_formula_blocks_audit_but_completed_formula_is_ignored(self):
        self.prepare()
        self.formula("Q6")
        self.assertTrue(self.audit().passed)
        self.formula("P6")
        self.assertIn("source_audit_formula", {issue.code for issue in self.audit().issues})
        preview = build_program_preview(self.path, self.cfg, "Synthetic", "block-1", self.block.week_labels)
        self.assertIn("aligned_week_plan_formula", {issue.code for issue in preview.blocking_issues})

    def test_audit_detects_pair_drift_after_preview(self):
        self.prepare()
        self.cells["N12"], self.cells["P12"] = self.cells["P12"], self.cells["N12"]
        self.write()
        self.assertIn("source_audit_week_alignment", {issue.code for issue in self.audit().issues})

    def test_anchor_cannot_cross_day_number_reset(self):
        self.cells["C12"] = "Day 1"
        self.prepare()
        blocks = discover_program_blocks(self.path, self.cfg)
        self.assertEqual([block.week_labels for block in blocks], [
            ("Week 1", "Week 2", "Week 3"), ("Week 1", "Week 2", "Week 3", "Week 4")])
        for col in ("J", "L", "N", "P"):
            self.cells.pop(f"{col}12", None)
        self.assertUnsafe()

    def test_reverse_direction_retains_only_planned_column(self):
        self.payload["program"]["week_pair_layout"] = "result_then_plan"
        for row in (6, 13):
            for plan, result in (("J", "K"), ("L", "M"), ("N", "O"), ("P", "Q")):
                self.cells[f"{plan}{row}"], self.cells[f"{result}{row}"] = self.cells[f"{result}{row}"], self.cells[f"{plan}{row}"]
        self.prepare()
        self.assertTrue(self.audit().passed, self.audit().issues)
        self.assertNotIn("RESULT-SENTINEL", json.dumps(self.report.to_dict()))


if __name__ == "__main__":
    unittest.main()
