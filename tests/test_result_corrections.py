"""Synthetic safety checks for dated, source-checked result corrections."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from datetime import date
from contextlib import redirect_stdout
from pathlib import Path

from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.cli import main
from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.ooxml import WorkbookError, XlsxPackage, file_sha256
from macrofactor_bridge.rep_counts import rep_count_entry, save_rep_counts
from macrofactor_bridge.service import apply_changes, build_preview
from tests.xlsx_factory import write_program_workbook


DAY = date(2026, 10, 6)
SHEET = "Synthetic Block"
CORRECTED = "84s x 10, 8+3p"


def _set(weight: object, reps: object, set_type: str = "Standard Set") -> dict[str, object]:
    return {"set_type": set_type, "weight": weight, "reps": reps}


class ResultCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.coach = root / "coach.xlsx"
        self.export = root / "log.csv"
        self.mapping = root / "mapping.json"
        self.output = root / "completed.xlsx"
        write_program_workbook(
            self.coach,
            sheet_name=SHEET,
            cells={
                "B3": "Day 1", "C3": "Style", "D3": "Variation", "K3": "Week 2",
                "C6": "Horizontal press", "D6": "Unilateral plate machine", "L6": None,
                "C7": "Cable row", "D7": "Seated", "L7": None,
            },
            merges=("K3:L3",),
        )
        self.payload: dict[str, object] = {
            "workbook": {"exercise_header_labels": ["Style"]},
            "exercises": [
                {
                    "canonical": "River Press",
                    "source_aliases": ["River Press"],
                    "coach_aliases": ["Horizontal press"],
                    "coach_context_aliases": ["Unilateral plate machine"],
                    "weight_multiplier": 0.5,
                    "weight_suffix": "s",
                },
                {
                    "canonical": "Harbor Row",
                    "source_aliases": ["Harbor Row"],
                    "coach_aliases": ["Cable row"],
                },
            ],
            "result_corrections": [
                {
                    "date": DAY.isoformat(),
                    "workout": "Synthetic Push",
                    "exercise": "River Press",
                    "expected_sets": [_set(168, 10), _set(168, 9)],
                    "value": CORRECTED,
                    "reason": "Reviewed workout log against coaching notes",
                }
            ],
        }
        self.rows = [
            [DAY.isoformat(), "Synthetic Push", "River Press", "Standard Set", "168", "10"],
            [DAY.isoformat(), "Synthetic Push", "River Press", "Standard Set", "168", "9"],
            [DAY.isoformat(), "Synthetic Pull", "Harbor Row", "Standard Set", "96", "12"],
        ]
        self._write_log()
        self._write_mapping()

    def _write_log(self) -> None:
        with self.export.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"))
            writer.writerows(self.rows)

    def _write_mapping(self) -> None:
        self.mapping.write_text(json.dumps(self.payload), encoding="utf-8")

    def _preview(self, rep_counts_path=None):
        return build_preview(
            self.export, self.coach, load_config(self.mapping), SHEET, "Week 2", DAY, DAY,
            rep_counts_path=rep_counts_path,
        )

    def test_matching_correction_writes_reviewed_value_without_reconverting_weight(self) -> None:
        report = self._preview()
        proposals = {item.cell: item for item in report.proposed_writes}
        self.assertEqual(proposals["L6"].value, CORRECTED)
        self.assertEqual(proposals["L7"].value, "96 x 12")
        self.assertIn("Reviewed workout log", proposals["L6"].review_note or "")
        self.assertEqual(report.result_corrections[0]["status"], "applied")
        self.assertEqual(report.result_corrections[0]["original_value"], "84s x 10, 9")
        self.assertEqual(report.result_corrections[0]["corrected_value"], CORRECTED)
        self.assertEqual(report.result_corrections[0]["cell"], "L6")
        self.assertEqual(len(report.result_corrections[0]["source_rows"]), 2)

        coach_hash, export_hash = file_sha256(self.coach), file_sha256(self.export)
        apply_changes(report, load_config(self.mapping), self.output)
        snapshot = XlsxPackage(self.output).sheet_snapshot(SHEET)
        self.assertEqual(snapshot.cells["L6"].value, CORRECTED)
        self.assertEqual((file_sha256(self.coach), file_sha256(self.export)), (coach_hash, export_hash))
        self.assertEqual(report.validation["unrelated_members_changed"], [])

    def test_dated_correction_takes_precedence_over_saved_or_unconfirmed_splits(self) -> None:
        self.rows[1][-1] = "9.33"
        self.payload["result_corrections"][0]["expected_sets"][1]["reps"] = "9.33"
        self._write_log()
        self._write_mapping()
        path = self.mapping.with_name("counts.json")
        record = load_exercise_log(self.export)[1]

        for with_confirmation in (False, True):
            with self.subTest(with_confirmation=with_confirmation):
                if with_confirmation:
                    save_rep_counts(path, self.export, [
                        {**rep_count_entry(record), "full_reps": 7, "partial_reps": 5},
                    ])
                report = self._preview(path)
                self.assertEqual(report.proposed_writes[0].value, CORRECTED)
                self.assertEqual(report.result_corrections[0]["original_value"], "84s x 10, 9.33")
                self.assertEqual(report.result_corrections[0]["status"], "applied")
                self.assertEqual(report.ambiguous_matches, [])
                self.assertEqual([entry["exercise"] for entry in report.rep_count_sets], ["Harbor Row"])

    def test_correction_is_scoped_to_both_date_and_workout(self) -> None:
        for field, replacement in (("date", "2026-10-07"), ("workout", "Synthetic Pull")):
            with self.subTest(field=field):
                correction = self.payload["result_corrections"][0]
                original = correction[field]
                correction[field] = replacement
                try:
                    self._write_mapping()
                    report = self._preview()
                    self.assertEqual(
                        {item.cell: item.value for item in report.proposed_writes}["L6"],
                        "84s x 10, 9",
                    )
                    self.assertFalse(any(item["status"] == "applied" for item in report.result_corrections))
                finally:
                    correction[field] = original

    def test_cli_preview_exposes_original_and_corrected_results(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main([
                "preview", "--export", str(self.export), "--workbook", str(self.coach),
                "--config", str(self.mapping), "--sheet", SHEET, "--week", "Week 2",
                "--from-date", DAY.isoformat(), "--to-date", DAY.isoformat(),
            ])
        self.assertEqual(status, 0)
        self.assertIn(f"Result correction (applied) L6: 84s x 10, 9 -> {CORRECTED}", output.getvalue())
        self.assertIn("Reviewed workout log against coaching notes", output.getvalue())

    def test_stale_expected_sets_withhold_only_affected_result(self) -> None:
        original = self.payload["result_corrections"][0]["expected_sets"]
        for expected in (
            [_set(170, 10), _set(168, 9)],
            [_set(168, 10), _set(168, 8)],
            [_set(168, 9), _set(168, 10)],
            [_set(168, 10)],
        ):
            with self.subTest(expected=expected):
                self.payload["result_corrections"][0]["expected_sets"] = expected
                self._write_mapping()
                report = self._preview()
                self.assertEqual({item.cell for item in report.proposed_writes}, {"L7"})
                self.assertEqual(report.result_corrections[0]["status"], "withheld")
                self.assertTrue(any(item.get("cell") == "L6" for item in report.ambiguous_matches))
        self.payload["result_corrections"][0]["expected_sets"] = original

    def test_additional_zero_rep_source_row_cannot_escape_guard(self) -> None:
        self.rows.append([DAY.isoformat(), "Synthetic Push", "River Press", "Standard Set", "168", "0"])
        self._write_log()
        report = self._preview()
        self.assertEqual({item.cell for item in report.proposed_writes}, {"L7"})
        self.assertEqual(report.result_corrections[0]["status"], "withheld")

    def test_xlsx_row_with_missing_date_cannot_escape_complete_source_guard(self) -> None:
        self.export = self.export.with_suffix('.xlsx')
        headers = ('Date', 'Workout', 'Exercise', 'Set Type', 'Weight (lbs)', 'Reps')
        cells = {f'{column}1': value for column, value in zip('ABCDEF', headers)}
        rows = self.rows + [['', 'Synthetic Push', 'River Press', 'Standard Set', '168', '7']]
        for index, row in enumerate(rows, start=2):
            cells.update({f'{column}{index}': value for column, value in zip('ABCDEF', row)})
        write_program_workbook(self.export, sheet_name='Workout Log', cells=cells)
        report = self._preview()
        self.assertEqual({item.cell for item in report.proposed_writes}, {'L7'})
        self.assertEqual(report.result_corrections[0]['status'], 'withheld')
        self.assertIn('Skipped source rows', report.result_corrections[0]['review_reason'])

    def test_nonfinite_corrected_source_withholds_cell_and_preserves_unrelated_preview(self) -> None:
        for field in (4, 5):
            original = self.rows[0][field]
            for invalid in ('sNaN', 'NaN', 'Infinity'):
                with self.subTest(field=field, invalid=invalid):
                    self.rows[0][field] = invalid
                    self._write_log()
                    report = self._preview()
                    self.assertEqual({item.cell: item.value for item in report.proposed_writes}, {'L7': '96 x 12'})
                    self.assertEqual(report.result_corrections[0]['status'], 'withheld')
                    self.assertTrue(any('nonfinite' in item['reason'] for item in report.skipped_rows))
            self.rows[0][field] = original

    def test_unmatched_correction_is_visible_and_does_not_replace_other_workout(self) -> None:
        self.payload['result_corrections'][0]['workout'] = 'Old workout name'
        self._write_mapping()
        report = self._preview()
        self.assertEqual({item.cell: item.value for item in report.proposed_writes}['L6'], '84s x 10, 9')
        self.assertEqual(report.result_corrections[0]['status'], 'not_applied')
        self.assertIn('No eligible exact workout/exercise match', report.result_corrections[0]['review_reason'])

    def test_correction_cannot_be_discarded_by_shared_superset_formatter(self) -> None:
        first, second = self.payload["exercises"]
        first["superset_group"] = "PAIR"
        first["superset_order"] = 1
        second["coach_aliases"] = ["Horizontal press"]
        second["coach_context_aliases"] = ["Unilateral plate machine"]
        second["superset_group"] = "PAIR"
        second["superset_order"] = 2
        self.rows.append([DAY.isoformat(), "Synthetic Pull", "Harbor Row", "Standard Set", "96", "11"])
        self._write_log()
        self._write_mapping()

        report = self._preview()
        self.assertFalse(any(item.cell == "L6" for item in report.proposed_writes))
        self.assertEqual(report.result_corrections[0]["status"], "withheld")
        self.assertTrue(any(item.get("cell") == "L6" for item in report.ambiguous_matches))

    def test_occupied_result_is_preserved_even_with_matching_correction(self) -> None:
        write_program_workbook(
            self.coach,
            sheet_name=SHEET,
            cells={
                "B3": "Day 1", "C3": "Style", "D3": "Variation", "K3": "Week 2",
                "C6": "Horizontal press", "D6": "Unilateral plate machine", "L6": "Coach entry",
                "C7": "Cable row", "D7": "Seated", "L7": None,
            },
            merges=("K3:L3",),
        )
        report = self._preview()
        self.assertEqual({item.cell for item in report.proposed_writes}, {"L7"})
        self.assertEqual([item["cell"] for item in report.occupied_cells], ["L6"])
        apply_changes(report, load_config(self.mapping), self.output)
        self.assertEqual(XlsxPackage(self.output).sheet_snapshot(SHEET).cells["L6"].value, "Coach entry")

    def test_config_rejects_invalid_or_ambiguous_corrections(self) -> None:
        valid = self.payload["result_corrections"][0]
        bad_entries: tuple[object, ...] = (
            None,
            [{**valid, "unexpected": "field"}],
            [{**valid, "date": "2026-99-99"}],
            [{**valid, "exercise": "Unmapped movement"}],
            [{**valid, "expected_sets": []}],
            [{**valid, "expected_sets": [_set("NaN", 10)]}],
            [{**valid, "expected_sets": [_set(168, 0)]}],
            [{**valid, "expected_sets": [{**_set(168, 10), "extra": 1}]}],
            [{**valid, "value": " "}],
            [valid, {**valid, "workout": "  SYNTHETIC   PUSH  "}],
        )
        for entries in bad_entries:
            with self.subTest(entries=entries):
                self.payload["result_corrections"] = entries
                self._write_mapping()
                with self.assertRaises(ConfigError):
                    load_config(self.mapping)

    def test_mapping_changed_after_preview_requires_new_preview(self) -> None:
        report = self._preview()
        self.payload["result_corrections"][0]["value"] = "84s x 10, 9"
        self._write_mapping()
        with self.assertRaises(WorkbookError):
            apply_changes(report, load_config(self.mapping), self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
