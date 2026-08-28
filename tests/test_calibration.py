from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from macrofactor_bridge.config import load_config
from macrofactor_bridge.importers import load_exercise_notes
from macrofactor_bridge.models import CellData, ExerciseNote, ExerciseRule
from macrofactor_bridge.service import _matching_coach_rows, build_preview
from macrofactor_bridge.workbook import TargetRow


class CalibrationTests(unittest.TestCase):
    def test_exact_row_context_disambiguates_duplicate_coach_labels(self) -> None:
        main = TargetRow(
            row=6,
            exercise_name="Abs",
            exercise_cell="C6",
            result_cell="J6",
            result=CellData("J6", None, None, "1", "s"),
            context_values=("hanging leg raises (3ct tempo eccentric)", "3"),
        )
        optional = TargetRow(
            row=35,
            exercise_name="ABs",
            exercise_cell="C35",
            result_cell="J35",
            result=CellData("J35", None, None, "1", "s"),
            context_values=("Weighted GHD sit ups", "3"),
        )
        rule = ExerciseRule(
            canonical="Hanging Straight Leg Raise",
            source_aliases=("Hanging Straight Leg Raise",),
            coach_aliases=("Abs",),
            coach_context_aliases=("hanging leg raises (3ct tempo eccentric)",),
            weight_multiplier=Decimal("1"),
        )

        matches = _matching_coach_rows(rule, {"abs": [main, optional]})

        self.assertEqual(matches, {"C6": main})

    def test_reads_active_program_exercise_notes_for_review(self) -> None:
        cells = {
            "A1": SimpleNamespace(value="Exercise"),
            "B1": SimpleNamespace(value="Notes"),
            "A2": SimpleNamespace(value="Cable Curl ∈ SS1"),
            "B2": SimpleNamespace(value="Second set was misloaded"),
            "A3": SimpleNamespace(value="No note exercise"),
            "B3": SimpleNamespace(value=None),
        }
        sheet = SimpleNamespace(name="Active Program")
        package = SimpleNamespace(
            sheets=(sheet,),
            sheet_snapshot=lambda _sheet: SimpleNamespace(cells=cells),
        )
        with patch("macrofactor_bridge.importers.XlsxPackage", return_value=package):
            notes = load_exercise_notes("anonymized.xlsx")

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].exercise, "Cable Curl ∈ SS1")
        self.assertEqual(notes[0].note, "Second set was misloaded")

    def test_preview_reports_only_notes_for_exercises_in_selected_dates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        notes = [
            ExerciseNote(4, "Active Program", "Tempo Back Squat", "Use the blue rack"),
            ExerciseNote(5, "Active Program", "Not Performed", "Unrelated note"),
        ]
        with patch("macrofactor_bridge.service.load_exercise_notes", return_value=notes):
            report = build_preview(
                root / "tests" / "fixtures" / "macrofactor-log.xlsx",
                root / "tests" / "fixtures" / "coach-template.xlsx",
                load_config(root / "config" / "exercises.example.json"),
                "Training Block",
                "Week 1",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )

        self.assertEqual(len(report.exercise_notes), 1)
        self.assertEqual(report.exercise_notes[0]["note"], "Use the blue rack")
        self.assertIn("not written", report.exercise_notes[0]["behavior"])


if __name__ == "__main__":
    unittest.main()
