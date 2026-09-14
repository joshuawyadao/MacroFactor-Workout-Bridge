from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from macrofactor_bridge.cli import build_parser, main
from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.program_service import build_program_preview

from tests.xlsx_factory import add_day_header, write_program_workbook


def exercise_row(
    cells: dict[str, object | None],
    row: int,
    *,
    name: str,
    style: str = "Straight Sets",
    sets: object | None = 3,
    reps: object | None = "8-10",
    rest: object | None = "2 min",
    week_one: object | None = "3 x 8-10 @ 2 RIR, 120 sec rest",
    week_one_result: object | None = "COMPLETED-RESULT-SENTINEL",
    week_two: object | None = "3 x 8-10 @ 2 RIR, 120 sec rest",
    week_two_result: object | None = None,
) -> None:
    cells.update(
        {
            f"D{row}": style,
            f"E{row}": name,
            f"F{row}": sets,
            f"G{row}": reps,
            f"H{row}": rest,
            f"J{row}": week_one,
            f"K{row}": week_one_result,
            f"L{row}": week_two,
            f"M{row}": week_two_result,
        }
    )


class ProgramPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config_path = self.root / "config.json"
        self.write_config()
        self.config = load_config(self.config_path)

    def write_config(
        self,
        *,
        defaults: dict[str, int | None] | None = None,
        week_pair_layout: str | None = "plan_then_result",
    ) -> None:
        payload = {
            "workbook": {
                "exercise_header_labels": ["Variation", "Exercise"],
                "week_header_pattern": "^week\\s*\\d+$",
            },
            "program": {
                "week_pair_layout": week_pair_layout,
                "defaults": defaults
                if defaults is not None
                else {"rep_min": 8, "rep_max": 12, "rir": 2, "rest_seconds": 90}
            },
            "exercises": [
                {
                    "canonical": "Alpha",
                    "source_aliases": ["Alpha"],
                    "coach_aliases": ["Alpha Move"],
                },
                {
                    "canonical": "Pair First",
                    "source_aliases": ["Pair First"],
                    "coach_aliases": ["Arm Pair"],
                    "superset_group": "SS1",
                    "superset_order": 1,
                },
                {
                    "canonical": "Pair Second",
                    "source_aliases": ["Pair Second"],
                    "coach_aliases": ["Arm Pair"],
                    "superset_group": "SS1",
                    "superset_order": 2,
                },
                {
                    "canonical": "Custom",
                    "source_aliases": ["Custom"],
                    "coach_aliases": ["Custom Move"],
                    "macrofactor_custom": True,
                },
                {
                    "canonical": "Unavailable",
                    "source_aliases": ["Unavailable"],
                    "coach_aliases": ["Unavailable Move"],
                    "macrofactor_available": False,
                },
                {
                    "canonical": "Conditioning",
                    "source_aliases": ["Conditioning"],
                    "coach_aliases": ["Cardio Block"],
                    "program_excluded": True,
                    "program_exclusion_reason": "Not represented in the strength program import",
                },
                {
                    "canonical": "Warmup",
                    "source_aliases": ["Warmup"],
                    "coach_aliases": ["Warmup Move"],
                },
            ],
        }
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")

    def write_workbook(
        self,
        cells: dict[str, object | None],
        *,
        merges: tuple[str, ...] = ("J5:K5", "L5:M5"),
    ) -> Path:
        path = self.root / "coach.xlsx"
        write_program_workbook(
            path, sheet_name="Shifted Program Sheet", cells=cells, merges=merges
        )
        return path

    def test_discovers_shifted_days_weeks_and_two_program_blocks(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        add_day_header(cells, row=12, day="Day 2 (Optional)")
        exercise_row(cells, 13, name="Custom Move")
        add_day_header(cells, row=20, day="Day 1")
        exercise_row(cells, 21, name="Alpha Move")
        workbook = self.write_workbook(
            cells,
            merges=("J5:K5", "L5:M5", "J20:K20", "L20:M20"),
        )

        blocks = discover_program_blocks(workbook, self.config)

        self.assertEqual([block.identifier for block in blocks], ["block-1", "block-2"])
        self.assertEqual(blocks[0].day_labels, ("Day 1", "Day 2 (Optional)"))
        self.assertEqual(blocks[0].week_labels, ("Week 1", "Week 2"))
        self.assertEqual(blocks[1].start_row, 20)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        self.assertEqual(
            [day.exercises[0].order for day in report.program.days],
            [1, 1],
        )

    def test_parses_selected_cycles_and_never_reads_adjacent_results(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1", "Week 2"),
        )
        exercise = report.program.days[0].exercises[0]
        first = exercise.prescriptions[0]

        self.assertEqual(exercise.macrofactor_name, "Alpha")
        self.assertEqual(first.set_count.value, 3)
        self.assertEqual((first.rep_min.value, first.rep_max.value), (8, 10))
        self.assertEqual(first.rir.value, 2)
        self.assertEqual(first.rest_seconds.value, 120)
        self.assertEqual(first.raw_week_text, "3 x 8-10 @ 2 RIR, 120 sec rest")
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(report.to_dict()))
        self.assertEqual(report.source_hash_before, report.source_hash_after)
        self.assertIsNone(report.template_hash)
        self.assertFalse(report.generation_safe)
        self.assertIn(
            "direct_program_export_required", {issue.code for issue in report.blocking_issues}
        )

    def test_preserves_coach_style_without_treating_a_slot_label_as_set_type(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            6,
            name="Alpha Move",
            style="Primary strength slot",
        )
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        exercise = report.program.days[0].exercises[0]
        prescription = exercise.prescriptions[0]

        self.assertEqual(exercise.raw_base_fields["style"], "Primary strength slot")
        self.assertIsNone(prescription.set_type.value)
        self.assertEqual(prescription.set_type.source, "missing")
        self.assertFalse(
            any(
                issue.code == "unsupported_base_value"
                and issue.raw_text == "Primary strength slot"
                for issue in report.issues
            )
        )
        self.assertTrue(
            any(
                issue.code == "missing_prescription_field"
                and "set type" in issue.message
                for issue in report.issues
            )
        )

    def test_stops_a_day_at_blank_separator_before_trailing_reference_rows(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 7, name="Alpha Move")
        exercise_row(cells, 9, name="Reference Metric", style="Goal")
        workbook = self.write_workbook(cells)

        block = discover_program_blocks(workbook, self.config)[0]
        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )

        self.assertEqual(block.end_row, 7)
        self.assertEqual(
            [exercise.coach_name for exercise in report.program.days[0].exercises],
            ["Alpha Move"],
        )
        self.assertFalse(
            any(issue.exercise == "Reference Metric" for issue in report.issues)
        )

    def test_parses_plain_language_rep_ranges_without_accepting_prose(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            6,
            name="Alpha Move",
            reps="8 to 12 reps",
            week_one="3 x 8 to 12 reps @ 2 RIR, 120 sec rest",
        )
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        prescription = report.program.days[0].exercises[0].prescriptions[0]

        self.assertEqual(
            (prescription.rep_min.value, prescription.rep_max.value),
            (8, 12),
        )
        self.assertIsNone(prescription.raw_unparsed_text)
        self.assertFalse(
            any(
                issue.code == "unsupported_base_value"
                and issue.raw_text == "8 to 12 reps"
                for issue in report.issues
            )
        )

    def test_week_pair_direction_must_be_explicit_and_can_be_reversed(self) -> None:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["program"].pop("week_pair_layout")
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        unconfigured = load_config(self.config_path)

        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        workbook = self.write_workbook(cells)
        self.assertEqual(discover_program_blocks(workbook, unconfigured)[0].week_labels, ())

        self.write_config(week_pair_layout="result_then_plan")
        reversed_config = load_config(self.config_path)
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            6,
            name="Alpha Move",
            week_one="COMPLETED-RESULT-SENTINEL",
            week_one_result="3 x 8-10 @ 2 RIR, 120 sec rest",
        )
        workbook = self.write_workbook(cells)
        report = build_program_preview(
            workbook,
            reversed_config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )

        prescription = report.program.days[0].exercises[0].prescriptions[0]
        self.assertEqual(
            prescription.raw_week_text,
            "3 x 8-10 @ 2 RIR, 120 sec rest",
        )
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", json.dumps(report.to_dict()))

    def test_reports_base_week_conflicts_without_selecting_a_value(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            6,
            name="Alpha Move",
            week_two="4 x 6 @ 1 RIR, 90 sec rest",
        )
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 2",),
        )
        prescription = report.program.days[0].exercises[0].prescriptions[0]

        self.assertIsNone(prescription.set_count.value)
        self.assertEqual(prescription.set_count.source, "conflict")
        self.assertIsNone(prescription.rep_min.value)
        conflicts = [
            issue for issue in report.issues if issue.code == "conflicting_base_and_week"
        ]
        self.assertEqual(len(conflicts), 4)

    def test_exact_mapping_normalizes_only_case_and_whitespace(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="  alpha   MOVE  ")
        exercise_row(cells, 7, name="Unknown Movement")
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("week 1",),
        )
        exact, unmatched = report.program.days[0].exercises

        self.assertEqual(exact.macrofactor_name, "Alpha")
        self.assertEqual(exact.mapping_status, "exact")
        self.assertEqual(report.included_weeks, ("Week 1",))
        self.assertEqual(unmatched.mapping_status, "unmatched")
        self.assertFalse(unmatched.macrofactor_available)

    def test_retains_unsupported_weekly_prose_for_review(self) -> None:
        unsupported = (
            "Read week",
            "your choice",
            "RPE 8",
            "AMRAP after the last set",
            "Use 20 lb then 15 lb",
            "Substitute another movement",
            "Add reps when ready",
        )
        for raw in unsupported:
            with self.subTest(raw=raw):
                cells: dict[str, object | None] = {}
                add_day_header(cells, row=5, day="Day 1")
                exercise_row(cells, 6, name="Alpha Move", week_one=raw)
                workbook = self.write_workbook(cells)
                report = build_program_preview(
                    workbook,
                    self.config,
                    "Shifted Program Sheet",
                    "block-1",
                    ("Week 1",),
                )
                prescription = report.program.days[0].exercises[0].prescriptions[0]
                self.assertEqual(prescription.raw_unparsed_text, raw)
                self.assertIn(raw, prescription.notes)
                self.assertTrue(
                    any(issue.code == "unsupported_week_instruction" for issue in report.issues)
                )

    def test_defaults_are_visible_and_distinct_from_coach_values(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            6,
            name="Alpha Move",
            reps=None,
            rest=None,
            week_one=None,
        )
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        prescription = report.program.days[0].exercises[0].prescriptions[0]

        self.assertEqual(prescription.set_count.source, "coach_base")
        self.assertEqual(prescription.rep_min.source, "config_default")
        self.assertEqual(prescription.rep_max.source, "config_default")
        self.assertEqual(prescription.rir.source, "config_default")
        self.assertEqual(prescription.rest_seconds.source, "config_default")
        self.assertEqual(
            len([issue for issue in report.issues if issue.code == "config_default_proposed"]),
            4,
        )

    def test_exact_supersets_custom_unavailable_and_exclusions_are_reported(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1 (Optional)")
        exercise_row(cells, 6, name="Arm Pair", style="Superset")
        exercise_row(cells, 7, name="Custom Move")
        exercise_row(cells, 8, name="Unavailable Move")
        exercise_row(cells, 9, name="Cardio Block", style="Cardio")
        exercise_row(cells, 10, name="Warmup Move", style="Warm Up")
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            self.config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        exercises = report.program.days[0].exercises
        pair = [exercise for exercise in exercises if exercise.coach_name == "Arm Pair"]

        self.assertEqual(
            [(exercise.macrofactor_name, exercise.superset.order) for exercise in pair],
            [("Pair First", 1), ("Pair Second", 2)],
        )
        self.assertTrue(
            any(issue.code == "custom_macrofactor_exercise" for issue in report.issues)
        )
        self.assertTrue(
            any(issue.code == "unavailable_macrofactor_exercise" for issue in report.issues)
        )
        excluded = next(exercise for exercise in exercises if exercise.coach_name == "Cardio Block")
        self.assertTrue(excluded.excluded)
        self.assertTrue(excluded.cardio)
        self.assertTrue(report.program.days[0].optional)
        self.assertEqual(len(report.skipped_items), 1)
        self.assertTrue(
            any(
                issue.code == "unsupported_exercise_category"
                and issue.exercise == "Warmup Move"
                for issue in report.issues
            )
        )
        self.assertTrue(any(issue.code == "optional_item" for issue in report.issues))
        self.assertFalse(
            any(
                issue.code == "unsupported_exercise_category"
                and issue.exercise == "Cardio Block"
                for issue in report.issues
            )
        )

    def test_incomplete_or_noncontiguous_supersets_block_preview(self) -> None:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["exercises"][1]["coach_aliases"] = ["Pair First Only"]
        payload["exercises"][2]["coach_aliases"] = ["Pair Second Only"]
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        incomplete_config = load_config(self.config_path)
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Pair First Only", style="Superset")
        workbook = self.write_workbook(cells)

        report = build_program_preview(
            workbook,
            incomplete_config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        self.assertTrue(any(issue.code == "incomplete_superset" for issue in report.issues))

        payload["exercises"][1]["coach_aliases"] = ["Arm Pair"]
        payload["exercises"][2]["coach_aliases"] = ["Arm Pair"]
        payload["exercises"][2]["superset_order"] = 3
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        noncontiguous_config = load_config(self.config_path)
        cells = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Arm Pair", style="Superset")
        workbook = self.write_workbook(cells)
        report = build_program_preview(
            workbook,
            noncontiguous_config,
            "Shifted Program Sheet",
            "block-1",
            ("Week 1",),
        )
        self.assertTrue(
            any(issue.code == "ambiguous_exercise_mapping" for issue in report.issues)
        )

    def test_unexpected_week_merge_width_is_not_treated_as_safe(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        workbook = self.write_workbook(cells, merges=("J5:L5",))

        block = discover_program_blocks(workbook, self.config)[0]

        self.assertNotIn("Week 1", block.week_labels)

    def test_cli_help_and_json_report_expose_a_separate_gated_mode(self) -> None:
        self.assertIn("program-preview", build_parser().format_help())
        self.assertIn("program-generate", build_parser().format_help())
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        workbook = self.write_workbook(cells)
        report_path = self.root / "program-preview.json"

        exit_code = main(
            [
                "program-preview",
                "--workbook",
                str(workbook),
                "--config",
                str(self.config_path),
                "--sheet",
                "Shifted Program Sheet",
                "--block",
                "block-1",
                "--week",
                "Week 1",
                "--report",
                str(report_path),
            ]
        )

        self.assertEqual(exit_code, 0)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["program"]["days"][0]["label"], "Day 1")
        self.assertFalse(payload["generation_safe"])
        self.assertFalse(payload["template_schema_verified"])

    def test_cli_refuses_to_overwrite_reports_or_use_a_reserved_path(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(cells, 6, name="Alpha Move")
        workbook = self.write_workbook(cells)
        existing_report = self.root / "existing.json"
        existing_report.write_text("keep me", encoding="utf-8")
        common_args = [
            "program-preview",
            "--workbook",
            str(workbook),
            "--config",
            str(self.config_path),
            "--sheet",
            "Shifted Program Sheet",
            "--block",
            "block-1",
            "--week",
            "Week 1",
            "--report",
        ]

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exit_code = main([*common_args, str(existing_report)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(existing_report.read_text(encoding="utf-8"), "keep me")

        source_before = workbook.read_bytes()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exit_code = main([*common_args, str(workbook)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(workbook.read_bytes(), source_before)

        config_before = self.config_path.read_bytes()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exit_code = main([*common_args, str(self.config_path)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(self.config_path.read_bytes(), config_before)

    def test_program_config_validation_is_backward_compatible_and_strict(self) -> None:
        root = Path(__file__).resolve().parents[1]
        existing = load_config(root / "config" / "exercises.example.json")
        self.assertIsNone(existing.program.defaults.rir)
        self.assertEqual(existing.program.week_pair_layout, "plan_then_result")

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["program"]["defaults"] = {"rep_min": 8, "rir": 2}
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "rep_min and rep_max"):
            load_config(self.config_path)

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["program"]["defaults"] = {}
        payload["program"]["week_pair_layout"] = "guess"
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "week_pair_layout"):
            load_config(self.config_path)


if __name__ == "__main__":
    unittest.main()
