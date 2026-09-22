from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_service import build_program_preview
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import add_day_header, write_macrofactor_program_template, write_program_workbook


class BaseRestPolicyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "coach.xlsx"
        self.config_path = self.root / "config.json"
        self.template = self.root / "template.xlsx"
        write_macrofactor_program_template(self.template, day_row_counts=(1,))
        self.payload = {
            "program": {"prescription_source": "base", "week_pair_layout": "plan_then_result",
                        "allow_blank_targets": True, "preserve_coach_notes": True,
                        "notes_mode": "concise", "rest_range_policy": "upper",
                        "unitless_rest_policy": "seconds", "defaults": {"set_type": "standard"}},
            "exercises": [{"canonical": "Alpha", "coach_aliases": ["Alpha Move"]}],
        }

    def prepare(self, rest, *, sets=2, week="UNLABELLED WEEK INSTRUCTION"):
        self.config_path.write_text(json.dumps(self.payload))
        self.config = load_config(self.config_path)
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move", sets=sets, rest=rest,
                     week_one=week, week_two=None)
        write_program_workbook(self.path, sheet_name="Synthetic", cells=cells,
                               merges=("J5:K5", "L5:M5"))
        self.block = discover_program_blocks(self.path, self.config)[0]
        self.report = build_program_preview(self.path, self.config, "Synthetic", "block-1", ("Week 1",),
                                            template_path=self.template)
        return self.report.program.days[0].exercises[0].prescriptions[0]

    def audit(self):
        return audit_coach_program(self.path, self.config, self.block, self.report)

    def mutate(self, **changes):
        day = self.report.program.days[0]
        exercise = day.exercises[0]
        rx = replace(exercise.prescriptions[0], **changes)
        self.report.program = replace(self.report.program, days=(replace(
            day, exercises=(replace(exercise, prescriptions=(rx,)),)),))

    def test_unitless_rest_is_strict_by_default_and_policy_values_are_validated(self):
        self.payload["program"].pop("unitless_rest_policy")
        self.prepare("90")
        self.assertEqual(self.config.program.unitless_rest_policy, "block")
        self.assertIn("unsupported_base_value", {i.code for i in self.report.blocking_issues})
        self.assertFalse(self.audit().passed)
        for invalid in ("minutes", True, 1, None):
            self.payload["program"]["unitless_rest_policy"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ConfigError):
                self.prepare("90")

    def test_opt_in_seconds_and_ranges_retain_distinct_policy_provenance(self):
        for raw, expected, source in (
            (90, 90, "coach_unitless_seconds_by_policy"),
            ("75 to 105", 105, "coach_unitless_seconds_range_upper_by_policy"),
            ("180–240", 240, "coach_unitless_seconds_range_upper_by_policy"),
        ):
            with self.subTest(raw=raw):
                rx = self.prepare(raw)
                self.assertEqual((rx.rest_seconds.value, rx.rest_seconds.source,
                                  rx.rest_seconds.source_cell, rx.rest_seconds.raw_text),
                                 (expected, source, "H6", str(raw)))
                self.assertIn("unitless_rest_seconds_by_policy", {i.code for i in self.report.issues})
                self.assertFalse(self.report.blocking_issues)
                self.assertTrue(self.audit().passed, self.audit().issues)

    def test_explicit_units_win_and_repeated_units_are_supported(self):
        for raw, expected, source in (
            ("2 min", 120, "coach_base"),
            ("1 to 3 minutes", 180, "coach_range_upper_by_policy"),
            ("1 min to 2 minutes", 120, "coach_range_upper_by_policy"),
            ("75 sec to 105 seconds", 105, "coach_range_upper_by_policy"),
            ("120 SEC MAX", 120, "coach_base"),
            ("2 min rest (timed)", 120, "coach_base"),
        ):
            with self.subTest(raw=raw):
                rx = self.prepare(raw)
                self.assertEqual((rx.rest_seconds.value, rx.rest_seconds.source), (expected, source))
                self.assertTrue(self.audit().passed, self.audit().issues)
                self.assertNotIn("unitless_rest_seconds_by_policy", {i.code for i in self.report.issues})

    def test_ranges_still_require_upper_policy_even_when_seconds_are_configured(self):
        self.payload["program"]["rest_range_policy"] = "block"
        for raw in ("75-105", "75 sec to 105 sec", "1 to 2 min"):
            with self.subTest(raw=raw):
                self.prepare(raw)
                self.assertIn("unsupported_base_value", {i.code for i in self.report.blocking_issues})
                self.assertFalse(self.audit().passed)

    def test_malformed_mixed_units_and_prose_stay_blocked_even_with_defaults(self):
        self.payload["program"]["defaults"]["rest_seconds"] = 90
        for raw in ("0", "-10", "1.5", "105-75", "1 min to 90 sec", "75sec to105",
                    "75 105", "90 if needed", "90 sec (or longer)", "90 max then 120",
                    "0-10", "1-2-3", "90 sec min", "90secmax"):
            with self.subTest(raw=raw):
                self.prepare(raw)
                self.assertIn("unsupported_base_value", {i.code for i in self.report.blocking_issues})
                self.assertFalse(self.audit().passed)

    def test_weekly_numeric_text_does_not_inherit_seconds_or_completed_results(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        rx = self.prepare(None, week="90")
        self.assertIsNone(rx.rest_seconds.value)
        self.assertEqual(rx.raw_unparsed_text, "90")
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", "\n".join(rx.notes))

    def test_weekly_conflicts_still_block_and_equal_explicit_week_retains_its_source(self):
        self.payload["program"]["prescription_source"] = "selected_week"
        rx = self.prepare("90", week="120 sec")
        self.assertEqual(rx.rest_seconds.source, "conflict")
        self.assertIn("conflicting_base_and_week", {i.code for i in self.report.blocking_issues})
        rx = self.prepare("90", week="90 sec")
        self.assertEqual((rx.rest_seconds.source, rx.rest_seconds.source_cell), ("coach_week", "J6"))

    def test_independent_audit_detects_lost_rest_value_policy_cell_and_raw_text(self):
        for changes in ({"value": 60}, {"source": "coach_base"}, {"source_cell": "K6"}, {"raw_text": "60"}):
            with self.subTest(changes=changes):
                rx = self.prepare("90")
                self.mutate(rest_seconds=replace(rx.rest_seconds, **changes))
                self.assertFalse(self.audit().passed)

    def test_rest_ceiling_and_timed_cues_survive_concise_notes_and_are_audited(self):
        for raw in ("120 sec max", "2 minutes (timed)"):
            with self.subTest(raw=raw):
                rx = self.prepare(raw)
                self.assertIn(f"Rest: {raw}", rx.notes)
                self.mutate(notes=tuple(note for note in rx.notes if not note.startswith("Rest:")))
                self.assertIn("source_audit_notes", {i.code for i in self.audit().issues})

    def test_per_side_sets_are_not_doubled_or_labelled_as_range_defaults(self):
        for raw in ("2 ea leg", "2 each side", "2 ea.", "2 each"):
            with self.subTest(raw=raw):
                rx = self.prepare("90", sets=raw)
                self.assertEqual((rx.set_count.value, rx.set_count.source), (2, "coach_base"))
                self.assertEqual(rx.set_count.raw_text, raw)
                self.assertIn("Sets are per side.", rx.notes)
                self.assertTrue(self.audit().passed, self.audit().issues)
                self.mutate(notes=tuple(note for note in rx.notes if note != "Sets are per side."))
                self.assertIn("source_audit_notes", {i.code for i in self.audit().issues})

    def test_unreviewed_per_side_set_prose_stays_blocked(self):
        for raw in ("0 each", "2 each or 3", "2 ea other leg", "2-3 each leg", "two each"):
            with self.subTest(raw=raw):
                self.prepare("90", sets=raw)
                self.assertIn("unsupported_base_value", {i.code for i in self.report.blocking_issues})
                self.assertFalse(self.audit().passed)
