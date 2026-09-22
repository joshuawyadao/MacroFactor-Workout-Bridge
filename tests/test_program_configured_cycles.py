from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macrofactor_bridge.cli import main
from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import build_program_preview, generate_program
from macrofactor_bridge.program_template import inspect_program_template
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import (
    add_day_header,
    write_macrofactor_program_template,
    write_program_workbook,
)


class ConfiguredBaseCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        self.report_path = self.root / "report.json"
        self.config_path = self.root / "config.json"
        self.payload = {
            "program": {
                "prescription_source": "base",
                "base_cycle_count": 4,
                "exclude_empty_days": True,
                "week_pair_layout": "plan_then_result",
                "allow_blank_targets": True,
                "preserve_coach_notes": True,
                "notes_mode": "concise",
                "use_day_designations": True,
                "resize_template_workouts": True,
                "rest_range_policy": "upper",
                "set_count_range_policy": "upper",
                "defaults": {"set_type": "standard"},
            },
            "exercises": [
                {
                    "canonical": "Synthetic Row",
                    "coach_aliases": ["Machine Row"],
                    "program_notes": ["Keep the torso supported."],
                },
                {
                    "canonical": "Synthetic Lunge",
                    "coach_aliases": ["Walking Lunge"],
                    "program_notes": ["Use dumbbells; reps are per side."],
                },
            ],
        }
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1", week_one="", week_two="")
        cells["C6"] = "Upper"
        exercise_row(
            cells,
            7,
            name="Machine Row",
            style="Horizontal Row",
            sets="3 to 4",
            reps="8 to 15 range",
            rest="90 to 120 seconds",
            week_one="WEEKLY-PLAN-MUST-NOT-BECOME-A-TARGET",
            week_one_result="COMPLETED-RESULT-SENTINEL",
            week_two=None,
            week_two_result=None,
        )
        exercise_row(
            cells,
            8,
            name="Machine Row",
            style="Horizontal Row",
            sets=3,
            reps="8 to 15 range",
            rest="90s",
            week_one=None,
            week_one_result=None,
            week_two=None,
            week_two_result=None,
        )
        add_day_header(cells, row=12, day="Day 2", week_one="", week_two="")
        cells["C13"] = "Lower"
        exercise_row(
            cells,
            14,
            name="Walking Lunge",
            style="Lunges",
            sets=3,
            reps="12 to 20 rep range ea leg",
            rest="120s",
            week_one="UNLABELLED-WEEKLY-TEXT",
            week_one_result="COMPLETED-RESULT-SENTINEL",
            week_two=None,
            week_two_result=None,
        )
        exercise_row(
            cells,
            15,
            name="Walking Lunge",
            style="Lunges",
            sets=3,
            reps="12 to 20 rep range ea leg",
            rest="120s",
            week_one=None,
            week_one_result=None,
            week_two=None,
            week_two_result=None,
        )
        add_day_header(cells, row=20, day="Day 3", week_one="", week_two="")
        cells["C21"] = "Unfinished upper day"
        add_day_header(cells, row=25, day="Day 4", week_one="", week_two="")
        cells["C26"] = "Unfinished lower day"
        # Reference material after a real blank separator must not become Day 4.
        cells.update({"D30": "Reference", "E30": "Not a coach-authored exercise"})
        write_program_workbook(self.source, sheet_name="Synthetic", cells=cells, merges=())
        # The verified user template has more workout groups than this temporary
        # two-day program; opt-in resizing may remove only trailing groups.
        write_macrofactor_program_template(
            self.template,
            day_row_counts=(2, 2, 2, 2),
            max_sets=4,
        )

    def config(self):
        self.config_path.write_text(json.dumps(self.payload), encoding="utf-8")
        return load_config(self.config_path)

    def preview(self):
        config = self.config()
        block = discover_program_blocks(self.source, config, sheet_name="Synthetic")[0]
        report = build_program_preview(
            self.source,
            config,
            block.sheet,
            block.identifier,
            block.week_labels,
            self.template,
        )
        return config, block, report

    def test_configured_cycles_and_source_empty_day_omission_are_explicit(self) -> None:
        config, block, report = self.preview()

        self.assertEqual(block.week_labels, ("Cycle 1", "Cycle 2", "Cycle 3", "Cycle 4"))
        self.assertEqual(block.day_labels, ("Day 1", "Day 2", "Day 3", "Day 4"))
        self.assertEqual([day.label for day in report.program.days], ["Day 1", "Day 2"])
        self.assertEqual([day.export_name for day in report.program.days], ["Upper", "Lower"])
        self.assertEqual([day.order for day in report.program.days], [1, 2])
        self.assertEqual(
            [cycle.label for cycle in report.program.cycles],
            ["Cycle 1", "Cycle 2", "Cycle 3", "Cycle 4"],
        )
        self.assertEqual(
            [(rx.rep_min.value, rx.rep_max.value) for rx in report.program.days[0].exercises[0].prescriptions],
            [(8, 15)] * 4,
        )
        self.assertEqual(
            (report.program.days[1].exercises[0].prescriptions[0].rep_min.value,
             report.program.days[1].exercises[0].prescriptions[0].rep_max.value),
            (12, 20),
        )
        self.assertEqual(
            [item["day"] for item in report.skipped_items if item.get("reason") == "No coach-authored exercise rows"],
            ["Day 3", "Day 4"],
        )
        self.assertEqual(
            [issue.day for issue in report.issues if issue.code == "empty_day_excluded"],
            ["Day 3", "Day 4"],
        )
        serialized = json.dumps(report.to_dict())
        self.assertNotIn("WEEKLY-PLAN-MUST-NOT-BECOME-A-TARGET", serialized)
        self.assertNotIn("COMPLETED-RESULT-SENTINEL", serialized)
        self.assertNotIn("Not a coach-authored exercise", serialized)
        self.assertTrue(report.generation_safe, report.blocking_issues)
        audit = audit_coach_program(self.source, config, block, report)
        self.assertTrue(audit.passed, audit.issues)

    def test_generation_round_trip_is_two_workouts_four_cycles_and_inputs_are_immutable(self) -> None:
        _, _, report = self.preview()
        before = (file_sha256(self.source), file_sha256(self.template))

        generate_program(report, self.template, self.output)
        audit = audit_program_output(report.program, self.output, self.template)

        self.assertTrue(audit.passed, audit.errors)
        self.assertEqual(before, (file_sha256(self.source), file_sha256(self.template)))
        cells = XlsxPackage(self.output).sheet_snapshot(
            XlsxPackage(self.output).sheets[0]
        ).cells
        values = {str(cell.value) for cell in cells.values() if cell.value is not None}
        self.assertIn("Cycles: 4", values)
        self.assertIn("Upper", values)
        self.assertIn("Lower", values)
        schema = inspect_program_template(self.output)
        self.assertEqual(len(schema.days), 2)
        with self.assertRaisesRegex(WorkbookError, "already exists"):
            generate_program(report, self.template, self.output)

    def test_cli_generates_without_week_flags_when_configured_cycles_are_exposed(self) -> None:
        self.config()
        code = main([
            "program-generate",
            "--workbook", str(self.source),
            "--config", str(self.config_path),
            "--template", str(self.template),
            "--sheet", "Synthetic",
            "--block", "block-1",
            "--output", str(self.output),
            "--report", str(self.report_path),
        ])
        self.assertEqual(code, 0)
        self.assertTrue(self.output.exists())
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["included_weeks"], ["Cycle 1", "Cycle 2", "Cycle 3", "Cycle 4"])

    def test_configured_cycles_are_strictly_validated(self) -> None:
        for value in (0, 53, True, "4"):
            with self.subTest(value=value):
                self.payload["program"]["base_cycle_count"] = value
                with self.assertRaises(ConfigError):
                    self.config()
        self.payload["program"]["base_cycle_count"] = 4
        self.payload["program"]["prescription_source"] = "selected_week"
        with self.assertRaises(ConfigError):
            self.config()

    def test_configured_cycles_do_not_bypass_partial_week_headers(self) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1", week_one="Week 1", week_two="")
        exercise_row(cells, 6, name="Machine Row", week_two=None, week_two_result=None)
        add_day_header(cells, row=12, day="Day 2", week_one="Week 2", week_two="")
        exercise_row(cells, 13, name="Walking Lunge", week_two=None, week_two_result=None)
        partial = self.root / "partial-headers.xlsx"
        write_program_workbook(partial, sheet_name="Synthetic", cells=cells, merges=())

        block = discover_program_blocks(partial, self.config(), sheet_name="Synthetic")[0]

        self.assertEqual(block.week_labels, ())


if __name__ == "__main__":
    unittest.main()
