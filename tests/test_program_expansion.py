from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import ConfigError, load_config, source_rule_index
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.service import build_preview, apply_changes
from tests.test_program_preview import exercise_row
from tests.test_program_generation import rewrite_zip_member
from tests.xlsx_factory import add_day_header, write_program_workbook, write_macrofactor_program_template


class ProgramExpansionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coach, self.template = self.root / "coach.xlsx", self.root / "template.xlsx"
        self.config_path, self.output = self.root / "config.json", self.root / "output.xlsx"
        self.payload = {
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "resize_template_workouts": True, "preserve_coach_notes": True,
                        "allow_blank_targets": True, "defaults": {"set_type": "standard"}},
            "exercises": [
                {"canonical": "Synthetic Combined", "coach_aliases": ["Coach Pair"],
                 "program_expansion": {"expected_variation": "Coach Pair", "expected_sets": "2",
                                       "exercises": [{"canonical": "Synthetic First", "sets": 2},
                                                     {"canonical": "Synthetic Second", "sets": 2}]}},
                {"canonical": "Synthetic Last", "coach_aliases": ["Coach Last"]}],
        }
        self.cells = {}
        add_day_header(self.cells, row=5, day="Day 1")
        exercise_row(self.cells, 7, name="Coach Pair", sets=2, reps="AMRAP", week_one="LATER UPDATE",
                     week_two=None)
        exercise_row(self.cells, 8, name="Coach Last", week_one=None, week_two=None)
        write_macrofactor_program_template(self.template)

    @property
    def rule(self):
        return self.payload["exercises"][0]

    def config(self):
        self.config_path.write_text(json.dumps(self.payload))
        return load_config(self.config_path)

    def preview(self):
        write_program_workbook(self.coach, sheet_name="Synthetic Block", cells=self.cells,
                               merges=("J5:K5", "L5:M5"))
        return build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                     ("Week 1", "Week 2"), self.template)

    def test_explicit_sequential_children_keep_source_and_prescriptions(self):
        report = self.preview()
        self.assertTrue(report.generation_safe, report.blocking_issues)
        first, second, last = report.program.days[0].exercises
        self.assertEqual([e.macrofactor_name for e in (first, second, last)],
                         ["Synthetic First", "Synthetic Second", "Synthetic Last"])
        self.assertEqual([e.order for e in (first, second, last)], [1, 2, 3])
        self.assertEqual(first.source_cell, second.source_cell)
        self.assertEqual(first.raw_base_fields, second.raw_base_fields)
        self.assertEqual(first.raw_base_fields["sets"], "2")
        for index, exercise in enumerate((first, second), start=1):
            self.assertIsNone(exercise.superset)
            self.assertEqual(exercise.mapping_status, "exact_expansion")
            self.assertEqual(exercise.expansion.child_order, index)
            self.assertEqual(exercise.expansion.execution, "sequential")
            for rx in exercise.prescriptions:
                self.assertEqual((rx.set_count.value, rx.set_count.source, rx.set_count.raw_text),
                                 (2, "config_program_expansion", "2"))
                self.assertEqual(rx.set_count.source_cell, "F7")
                self.assertEqual(rx.set_type.value, "standard")
                self.assertEqual(rx.rest_seconds.value, 120)
                self.assertIsNone(rx.rep_min.value)
                self.assertIsNone(rx.rir.value)
                self.assertIn("AMRAP", " ".join(rx.notes))
            self.assertEqual(exercise.prescriptions[0].raw_week_text, "LATER UPDATE")
        self.assertEqual(sum(i.code == "reviewed_program_expansion" for i in report.issues), 1)
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(report.to_dict()))

    def test_part_one_indexes_are_unchanged_and_children_are_not_result_aliases(self):
        expanded = source_rule_index(self.config())
        del self.rule["program_expansion"]
        legacy = source_rule_index(self.config())
        self.assertEqual(set(expanded), set(legacy))
        for key in legacy:
            self.assertEqual(expanded[key].canonical, legacy[key].canonical)
            self.assertEqual(expanded[key].source_aliases, legacy[key].source_aliases)
            self.assertEqual(expanded[key].weight_multiplier, legacy[key].weight_multiplier)
            self.assertEqual(expanded[key].superset_group, legacy[key].superset_group)
        self.assertNotIn("synthetic first", expanded)

    def test_stale_source_guard_retains_unsplit_row_and_blocks(self):
        for field, value in (("expected_sets", "3"), ("expected_variation", "coach pair"),
                             ("expected_variation", "Coach  Pair")):
            with self.subTest(field=field, value=value):
                prior = self.rule["program_expansion"][field]
                self.rule["program_expansion"][field] = value
                report = self.preview()
                self.assertFalse(report.generation_safe)
                self.assertIn("stale_program_expansion", {i.code for i in report.blocking_issues})
                self.assertEqual(len(report.program.days[0].exercises), 2)
                first = report.program.days[0].exercises[0]
                self.assertEqual(first.macrofactor_name, "Synthetic Combined")
                self.assertEqual(first.prescriptions[0].set_count.value, 2)
                self.assertIsNone(first.expansion)
                self.rule["program_expansion"][field] = prior

    def test_part_one_preview_and_apply_ignore_program_expansion(self):
        repo = Path(__file__).resolve().parents[1]
        self.payload = json.loads((repo / "config/exercises.example.json").read_text())
        self.payload["program"]["prescription_source"] = "base"
        args = (repo / "tests/fixtures/macrofactor-log.xlsx", repo / "tests/fixtures/coach-template.xlsx")
        baseline = self.config()
        before = build_preview(*args, baseline, "Training Block", "Week 1", date(2026, 8, 3), date(2026, 8, 9))
        self.rule["program_expansion"] = {
            "expected_variation": "Tempo Squat", "expected_sets": "3",
            "exercises": [{"canonical": "Synthetic First", "sets": 2},
                          {"canonical": "Synthetic Second", "sets": 2}],
        }
        expanded = self.config()
        after = build_preview(*args, expanded, "Training Block", "Week 1", date(2026, 8, 3), date(2026, 8, 9))
        self.assertTrue(before.proposed_writes)
        self.assertEqual(before.to_dict(), after.to_dict())
        baseline_output = self.root / "baseline.xlsx"
        apply_changes(before, baseline, baseline_output)
        apply_changes(after, expanded, self.output)
        with zipfile.ZipFile(baseline_output) as original, zipfile.ZipFile(self.output) as updated:
            self.assertEqual(original.namelist(), updated.namelist())
            for name in original.namelist():
                self.assertEqual(original.read(name), updated.read(name), name)

    def test_unconfigured_combined_text_does_not_expand(self):
        del self.rule["program_expansion"]
        self.rule["coach_aliases"] = ["Left / Right"]
        self.cells["E7"] = "Left / Right"
        report = self.preview()
        self.assertEqual(len(report.program.days[0].exercises), 2)
        self.assertIsNone(report.program.days[0].exercises[0].expansion)

    def test_cached_formula_guards_do_not_authorize_expansion(self):
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        for reference in ("E7", "F7"):
            with self.subTest(reference=reference):
                self.preview()
                def add_formula(data):
                    sheet = ET.fromstring(data)
                    cell = next(c for c in sheet.iter(ns + "c") if c.attrib["r"] == reference)
                    ET.SubElement(cell, ns + "f").text = '2' if reference == "F7" else '"Coach Pair"'
                    return ET.tostring(sheet)
                rewrite_zip_member(self.coach, "xl/worksheets/sheet1.xml", add_formula)
                report = build_program_preview(self.coach, self.config(), "Synthetic Block", "block-1",
                                               ("Week 1", "Week 2"), self.template)
                self.assertFalse(report.generation_safe)
                self.assertIn("stale_program_expansion", {i.code for i in report.blocking_issues})
                self.assertEqual(len(report.program.days[0].exercises), 2)

    def test_per_set_reps_and_source_supersets_cannot_be_allocated(self):
        for cell, value in (("G7", "7,9"), ("D7", "Superset"), ("D7", "Myo Reps")):
            with self.subTest(cell=cell, value=value):
                prior = self.cells[cell]
                self.cells[cell] = value
                report = self.preview()
                self.assertFalse(report.generation_safe)
                self.assertIn("unsupported_program_expansion", {i.code for i in report.blocking_issues})
                self.assertEqual(len(report.program.days[0].exercises), 2)
                self.cells[cell] = prior

    def test_children_preserve_custom_and_unavailable_gates(self):
        children = self.rule["program_expansion"]["exercises"]
        children[0]["macrofactor_custom"] = True
        children[1]["macrofactor_available"] = False
        report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertIn("unavailable_macrofactor_exercise", {i.code for i in report.blocking_issues})
        self.assertIn("custom_macrofactor_exercise", {i.code for i in report.issues})
        self.assertTrue(report.program.days[0].exercises[0].custom_exercise)
        self.assertFalse(report.program.days[0].exercises[1].macrofactor_available)
        with self.assertRaises(WorkbookError):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())

    def test_cli_generation_resizes_rows_and_preserves_inputs_and_nonoverwrite(self):
        report = self.preview()
        hashes = file_sha256(self.coach), file_sha256(self.template)
        stdout = StringIO()
        with redirect_stdout(stdout):
            result = main(["program-generate", "--workbook", str(self.coach), "--config", str(self.config_path),
                           "--sheet", "Synthetic Block", "--block", "block-1", "--template", str(self.template),
                           "--output", str(self.output)])
        self.assertEqual(result, 0, stdout.getvalue())
        self.assertIn("Sequential expansion 2/2", stdout.getvalue())
        cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual(cells["B1"].value, "Cycles: 2")
        self.assertEqual([cells[f"B{row}"].value for row in (4, 5, 6)],
                         ["Synthetic First", "Synthetic Second", "Synthetic Last"])
        for row in (4, 5):
            self.assertEqual([cells[f"{col}{row}"].value for col in ("E", "I")], ["Standard Set"] * 2)
            self.assertTrue(all(cells.get(f"{col}{row}") is None or cells[f"{col}{row}"].value is None
                                for col in ("M", "N", "O", "P", "Q", "R", "S", "T")))
            self.assertIn("AMRAP", cells[f"D{row}"].value)
        self.assertEqual(hashes, (file_sha256(self.coach), file_sha256(self.template)))
        with zipfile.ZipFile(self.template) as source, zipfile.ZipFile(self.output) as target:
            self.assertEqual(set(source.namelist()), set(target.namelist()))
            for name in source.namelist():
                if name not in {"xl/worksheets/sheet1.xml", "xl/sharedStrings.xml"}:
                    self.assertEqual(source.read(name), target.read(name), name)
        output_hash = file_sha256(self.output)
        with self.assertRaisesRegex(WorkbookError, "Output already exists"):
            generate_program(report, self.template, self.output)
        self.assertEqual(output_hash, file_sha256(self.output))

    def test_explicit_child_count_still_obeys_template_capacity(self):
        self.rule["program_expansion"]["exercises"][1]["sets"] = 5
        report = self.preview()
        self.assertFalse(report.generation_safe)
        self.assertTrue(any("capacity" in issue.code or "capacity" in issue.message
                            for issue in report.blocking_issues))

    def test_strict_expansion_config(self):
        valid = copy.deepcopy(self.rule["program_expansion"])
        cases = [[], {}, {**valid, "expected_sets": ""}, {**valid, "extra": True},
                 {**valid, "exercises": []}, {**valid, "exercises": valid["exercises"][:1]},
                 {**valid, "exercises": valid["exercises"] + [{"canonical": "Third", "sets": 2}]}]
        for change in ({"sets": True}, {"sets": 0}, {"sets": -1}, {"sets": "2"},
                       {"canonical": " "}, {"canonical": "synthetic second"},
                       {"macrofactor_custom": "false"}, {"macrofactor_available": 1}, {"superset": True}):
            changed = copy.deepcopy(valid)
            changed["exercises"][0].update(change)
            cases.append(changed)
        for invalid in cases:
            with self.subTest(invalid=invalid):
                self.rule["program_expansion"] = invalid
                with self.assertRaises(ConfigError):
                    self.config()

    def test_incompatible_parent_policies_are_rejected(self):
        for change in ({"superset_group": "A"}, {"program_set_types": ["standard", "myo"]},
                       {"program_base_overrides": {"sets": {"expected": "2", "value": "3"}}},
                       {"program_excluded": True, "program_exclusion_reason": "reviewed"},
                       {"program_exclusion_reason": "unused"}, {"program_include_warmup": True},
                       {"macrofactor_custom": True}, {"macrofactor_available": False}):
            with self.subTest(change=change):
                original = copy.deepcopy(self.rule)
                self.rule.update(change)
                with self.assertRaises(ConfigError):
                    self.config()
                self.payload["exercises"][0] = original
        self.payload["program"]["prescription_source"] = "selected_week"
        with self.assertRaises(ConfigError):
            self.config()


if __name__ == "__main__":
    unittest.main()
