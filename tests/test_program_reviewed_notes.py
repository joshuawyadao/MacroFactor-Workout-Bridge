from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from macrofactor_bridge.coach_program import discover_program_blocks
from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage
from macrofactor_bridge.program_audit import audit_coach_program
from macrofactor_bridge.program_output_audit import audit_program_output
from macrofactor_bridge.program_service import build_program_preview, generate_program
from tests.test_program_preview import exercise_row
from tests.xlsx_factory import (
    add_day_header,
    write_macrofactor_program_template,
    write_program_workbook,
)


class ProgramReviewedNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach = self.root / "coach.xlsx"
        self.template = self.root / "template.xlsx"
        self.output = self.root / "output.xlsx"
        self.config_path = self.root / "config.json"
        self.residual_notes = (
            "Tempo: three-second eccentric.",
            "Pause: one count at the bottom.",
            "Intent: accelerate through the concentric.",
        )
        self.payload = {
            "workbook": {"exercise_header_labels": ["Style"]},
            "program": {
                "week_pair_layout": "plan_then_result",
                "prescription_source": "base",
                "preserve_coach_notes": True,
                "notes_mode": "concise",
                "defaults": {"set_type": "standard", "rir": 2},
            },
            "exercises": [
                {
                    "canonical": "Synthetic Base Press",
                    "coach_aliases": ["Tempo Pause Press"],
                    "coach_context_aliases": ["Horizontal Push"],
                    "program_notes": list(self.residual_notes),
                }
            ],
        }
        write_macrofactor_program_template(self.template, day_row_counts=(1,))

    def config(self):
        self.config_path.write_text(json.dumps(self.payload), encoding="utf-8")
        return load_config(self.config_path)

    def write_source(
        self,
        *,
        variation: str = "Tempo Pause Press",
        reps: str = "8-10",
    ) -> None:
        cells: dict[str, object | None] = {}
        add_day_header(cells, row=5, day="Day 1")
        exercise_row(
            cells,
            7,
            name=variation,
            style="Horizontal Push",
            sets=3,
            reps=reps,
            rest="90 sec",
            week_one="Switch to Similar Press next week",
            week_one_result="COMPLETED: Similar Press with a five-second pause",
            week_two="Move explosively only after the deload",
            week_two_result="COMPLETED: Speed Press",
        )
        write_program_workbook(
            self.coach,
            sheet_name="Synthetic Block",
            cells=cells,
            merges=("J5:K5", "L5:M5"),
        )

    def preview(self):
        config = self.config()
        block = discover_program_blocks(self.coach, config)[0]
        report = build_program_preview(
            self.coach,
            config,
            block.sheet,
            block.identifier,
            block.week_labels,
            self.template,
        )
        return config, block, report

    def test_reviewed_exact_mapping_serializes_only_residual_cues_and_passes_both_audits(self) -> None:
        self.write_source()
        config, block, report = self.preview()

        self.assertTrue(report.generation_safe, report.blocking_issues)
        exercise = report.program.days[0].exercises[0]
        self.assertEqual(exercise.macrofactor_name, "Synthetic Base Press")
        self.assertEqual(exercise.mapping_status, "exact")
        self.assertEqual(exercise.raw_base_fields["variation"], "Tempo Pause Press")
        self.assertEqual(exercise.raw_base_fields["style"], "Horizontal Push")
        for prescription in exercise.prescriptions:
            self.assertEqual(prescription.notes, self.residual_notes)
        self.assertEqual(
            [prescription.raw_week_text for prescription in exercise.prescriptions],
            ["Switch to Similar Press next week", "Move explosively only after the deload"],
        )
        preview_notes = "\n".join(
            note for prescription in exercise.prescriptions for note in prescription.notes
        )
        self.assertNotIn("Similar Press", preview_notes)
        self.assertNotIn("deload", preview_notes)
        self.assertNotIn("COMPLETED", json.dumps(report.to_dict()))

        source_audit = audit_coach_program(self.coach, config, block, report)
        self.assertTrue(source_audit.passed, source_audit.issues)

        generate_program(report, self.template, self.output)
        output_cells = XlsxPackage(self.output).sheet_snapshot("Training Programs").cells
        self.assertEqual(output_cells["B4"].value, "Synthetic Base Press")
        self.assertEqual(output_cells["D4"].value, "\n".join(self.residual_notes))
        self.assertNotIn("Similar Press", output_cells["D4"].value)
        output_audit = audit_program_output(report.program, self.output, self.template)
        self.assertTrue(output_audit.passed, output_audit.errors)

    def test_similar_unconfigured_variation_cannot_borrow_the_reviewed_identity_or_notes(self) -> None:
        self.write_source(variation="Tempo Pause Press Plus")
        _, _, report = self.preview()

        self.assertFalse(report.generation_safe)
        self.assertIn("unmatched_exercise", {issue.code for issue in report.blocking_issues})
        exercise = report.program.days[0].exercises[0]
        self.assertIsNone(exercise.macrofactor_name)
        self.assertNotIn("three-second eccentric", "\n".join(exercise.prescriptions[0].notes))

    def test_reviewed_notes_cannot_hide_a_malformed_base_prescription(self) -> None:
        self.write_source(reps="6,7")
        config, block, report = self.preview()

        self.assertFalse(report.generation_safe)
        self.assertIn("rep_sequence_length_mismatch", {issue.code for issue in report.blocking_issues})
        self.assertEqual(report.program.days[0].exercises[0].prescriptions[0].notes, self.residual_notes)
        source_audit = audit_coach_program(self.coach, config, block, report)
        self.assertFalse(source_audit.passed)
        self.assertIn("source_audit_rep_sequence", {issue.code for issue in source_audit.issues})
        with self.assertRaisesRegex(WorkbookError, "blocking items"):
            generate_program(report, self.template, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
