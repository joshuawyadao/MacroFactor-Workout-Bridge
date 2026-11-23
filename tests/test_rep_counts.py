from __future__ import annotations

import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge.importers import load_exercise_log
from macrofactor_bridge.ooxml import file_sha256
from macrofactor_bridge.rep_counts import (
    apply_rep_counts, needs_rep_confirmation, rep_count_entry, save_rep_counts,
)
from macrofactor_bridge import rep_counts
from tests.xlsx_factory import write_program_workbook


class RepCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.export = self.root / "log.csv"
        self.export.write_text(
            "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
            "2026-08-03,Day 1,Rear fly,Standard Set,25,9.33\n"
            "2026-08-04,Day 2,Pushdown,Drop Set,30,11.67\n",
            encoding="utf-8",
        )
        self.path = self.root / "rep-counts.json"
        self.records = load_exercise_log(self.export)

    def entry(self, index: int, full: int | None, partial: int | None) -> dict:
        return {**rep_count_entry(self.records[index]),
                "full_reps": full, "partial_reps": partial}

    def test_exported_reps_remain_raw_and_confirmation_survives_reopen(self) -> None:
        self.assertTrue(needs_rep_confirmation(self.records[0]))
        self.assertEqual(rep_count_entry(self.records[0])["exported_reps"], "9.33")
        save_rep_counts(self.path, self.export, [self.entry(0, 8, 4)],
                        expected_export_hash=file_sha256(self.export))
        reopened = apply_rep_counts(load_exercise_log(self.export), self.path,
                                    file_sha256(self.export))
        self.assertEqual(reopened[0].reps, Decimal("9.33"))
        self.assertEqual((reopened[0].full_reps, reopened[0].partial_reps), (8, 4))
        self.assertFalse(needs_rep_confirmation(reopened[0]))
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_merge_preserves_off_range_and_null_pair_removes_confirmation(self) -> None:
        save_rep_counts(self.path, self.export, [self.entry(0, 8, 4)])
        first_hash = file_sha256(self.path)
        save_rep_counts(self.path, self.export, [self.entry(1, 10, 5)], expected_hash=first_hash)
        self.assertEqual([entry["source_row"] for entry in json.loads(self.path.read_text())["sets"]], [2, 3])
        save_rep_counts(self.path, self.export, [self.entry(0, None, None)],
                        expected_hash=file_sha256(self.path))
        self.assertEqual([entry["source_row"] for entry in json.loads(self.path.read_text())["sets"]], [3])

    def test_csv_and_xlsx_have_physical_row_identity(self) -> None:
        xlsx = self.root / "log.xlsx"
        write_program_workbook(xlsx, sheet_name="Exercise Log", cells={
            "A1": "Date", "B1": "Workout", "C1": "Exercise", "D1": "Set Type",
            "E1": "Weight (lbs)", "F1": "Reps", "A2": "2026-08-03",
            "B2": "Day 1", "C2": "Rear fly", "D2": "Standard Set",
            "E2": 25, "F2": 9.33,
        })
        csv_identity = rep_count_entry(self.records[0])
        xlsx_identity = rep_count_entry(load_exercise_log(xlsx)[0])
        self.assertEqual(csv_identity, xlsx_identity)
        self.assertEqual(csv_identity["workout_date"], "2026-08-03")

    def test_rejects_stale_duplicate_unknown_and_malformed_entries(self) -> None:
        valid = self.entry(0, 8, 4)
        cases = [
            ([valid, valid], "duplicate"),
            ([{**valid, "source_row": 99}], "unknown"),
            ([{**valid, "exercise": "Other"}], "stale"),
            ([{**valid, "full_reps": True}], "integers"),
            ([{**valid, "partial_reps": None}], "integers"),
            ([{**valid, "full_reps": -1}], "nonnegative"),
            ([{**valid, "full_reps": 0, "partial_reps": 0}], "positive"),
            ([{key: value for key, value in valid.items() if key != "weight"}], "missing"),
        ]
        for entries, reason in cases:
            with self.subTest(reason=reason, entries=entries):
                self.path.write_text(json.dumps({"schema_version": 1,
                    "export_sha256": file_sha256(self.export), "sets": entries}))
                with self.assertRaisesRegex(ValueError, reason):
                    apply_rep_counts(self.records, self.path, file_sha256(self.export))
        self.path.write_text(json.dumps({"schema_version": True,
            "export_sha256": file_sha256(self.export), "sets": []}))
        with self.assertRaisesRegex(ValueError, "schema version"):
            apply_rep_counts(self.records, self.path, file_sha256(self.export))
        self.path.write_text("{invalid JSON", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Could not read rep counts file"):
            apply_rep_counts(self.records, self.path, file_sha256(self.export))

    def test_rejects_source_changes_and_destination_aliases(self) -> None:
        with self.assertRaisesRegex(ValueError, "aliases"):
            save_rep_counts(self.export, self.export, [])
        reserved = self.root / "coach.xlsx"
        reserved.write_bytes(b"private workbook")
        with self.assertRaisesRegex(ValueError, "aliases"):
            save_rep_counts(reserved, self.export, [], reserved=[reserved])
        self.path.symlink_to(self.export)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            save_rep_counts(self.path, self.export, [])
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "export changed"):
            save_rep_counts(self.path, self.export, [], expected_export_hash="0" * 64)
        save_rep_counts(self.path, self.export, [self.entry(0, 8, 4)])
        with self.assertRaisesRegex(ValueError, "changed since preview"):
            save_rep_counts(self.path, self.export, [], expected_hash="0" * 64)
        with self.assertRaisesRegex(ValueError, "hash"):
            apply_rep_counts(self.records, self.path, "0" * 64)

    def test_counts_require_usable_exported_row(self) -> None:
        alternate = self.root / "unusable.csv"
        for exercise, set_type, weight, reps in (
            ("Exercise", "Standard Set", "10", "0"),
            ("", "Standard Set", "10", "9.33"),
            ("Exercise", "", "10", "9.33"),
            ("Exercise", "Standard Set", "NaN", "9.33"),
            ("Exercise", "Standard Set", "10", "Infinity"),
        ):
            with self.subTest(exercise=exercise, set_type=set_type, weight=weight, reps=reps):
                alternate.write_text(
                    "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                    f"2026-08-03,Day 1,{exercise},{set_type},{weight},{reps}\n",
                    encoding="utf-8",
                )
                raw = load_exercise_log(alternate)[0]
                with self.assertRaisesRegex(ValueError, "usable row"):
                    save_rep_counts(self.path, alternate,
                                    [{**rep_count_entry(raw), "full_reps": 1, "partial_reps": 0}])
                self.assertFalse(self.path.exists())

    def test_export_mutation_during_save_preserves_existing_counts(self) -> None:
        save_rep_counts(self.path, self.export, [self.entry(0, 8, 4)])
        prior = self.path.read_bytes()
        original_hash = file_sha256
        export_checks = 0

        def mutate_on_final_export_check(path: str | Path) -> str:
            nonlocal export_checks
            if Path(path) == self.export:
                export_checks += 1
                if export_checks == 2:
                    self.export.write_text(self.export.read_text() + "\n", encoding="utf-8")
            return original_hash(path)

        with patch.object(rep_counts, "file_sha256", side_effect=mutate_on_final_export_check):
            with self.assertRaisesRegex(ValueError, "Export|export changed during save"):
                save_rep_counts(self.path, self.export, [self.entry(1, 10, 5)],
                                expected_hash=original_hash(self.path))
        self.assertEqual(self.path.read_bytes(), prior)
        self.assertFalse(list(self.root.glob(".rep-counts.json.tmp-*")))

    def test_concurrent_count_change_preserves_external_content(self) -> None:
        save_rep_counts(self.path, self.export, [self.entry(0, 8, 4)])
        prior_hash = file_sha256(self.path)
        external = b'{"external": "preserve me"}\n'
        original_hash = file_sha256
        count_checks = 0

        def mutate_on_final_count_check(path: str | Path) -> str:
            nonlocal count_checks
            if Path(path) == self.path:
                count_checks += 1
                if count_checks == 2:
                    self.path.write_bytes(external)
            return original_hash(path)

        with patch.object(rep_counts, "file_sha256", side_effect=mutate_on_final_count_check):
            with self.assertRaisesRegex(ValueError, "changed during save"):
                save_rep_counts(self.path, self.export, [self.entry(1, 10, 5)],
                                expected_hash=prior_hash)
        self.assertEqual(self.path.read_bytes(), external)
        self.assertFalse(list(self.root.glob(".rep-counts.json.tmp-*")))


if __name__ == "__main__":
    unittest.main()
