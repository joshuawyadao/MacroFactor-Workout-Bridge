from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from macrofactor_bridge.local_workspace import setup_workspace, archive_inbox
from macrofactor_bridge.managed_history import discover_workspace, load_managed_history, workspace_fingerprint
from macrofactor_bridge.ooxml import file_sha256
from tests.comparison_fixture import comparison_inputs

ROOT = Path(__file__).resolve().parents[1]


def managed_inputs(directory):
    root = (directory / "local-data").resolve()
    setup_workspace(root)
    export, coach, annotation = comparison_inputs(directory)
    shutil.copy2(export, root / "inbox/macrofactor/all-time.csv")
    shutil.copy2(coach, root / "inbox/coach/coach.xlsx")
    shutil.copy2(annotation, root / "annotations/workout-history.json")
    return root


def write_export(path, rows):
    path.write_text("Date,Workout,Exercise,Set Type,Weight (lbs),Reps,RIR\n" + "\n".join(rows) + "\n", encoding="utf-8")


class ManagedHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = managed_inputs(Path(temporary.name))

    def test_repeat_ingestion_is_idempotent_and_keeps_original_inputs(self):
        paths = list((self.root / "inbox").glob("*/*")) + [self.root / "annotations/workout-history.json"]
        before = [file_sha256(p) for p in paths]
        first = load_managed_history(self.root)
        manifests = tuple((self.root / "manifests").iterdir())
        second = load_managed_history(self.root)
        self.assertEqual(first.dashboard.set_count, 7)
        self.assertEqual(first.dashboard.records, second.dashboard.records)
        self.assertEqual(tuple((self.root / "manifests").iterdir()), manifests)
        self.assertEqual(before, [file_sha256(p) for p in paths])
        self.assertTrue(all("archive/macrofactor" in r.source_file for r in first.dashboard.records))
        self.assertEqual(first.fingerprint, workspace_fingerprint(self.root))

    def test_duplicate_files_and_duplicate_sets_are_different(self):
        file = self.root / "inbox/macrofactor/repeated.csv"
        row = "2026-09-01,Day A,Tempo Back Squat,Standard Set,100,5,"
        write_export(file, [row, row, row])
        shutil.copy2(file, file.with_name("copy.csv"))
        result = load_managed_history(self.root)
        self.assertEqual(len(result.exports), 2)
        self.assertEqual(result.dashboard.set_count, 10)
        self.assertEqual(sum(r.workout_date == date(2026, 9, 1) for r in result.dashboard.records), 3)

    def test_newer_narrow_export_extends_history_without_dropping_old_dates(self):
        write_export(self.root / "inbox/macrofactor/recent.csv", [
            "2026-08-24,Day A,Tempo Back Squat,Standard Set,500,5,",
            "2026-09-01,Day A,Tempo Back Squat,Standard Set,510,5,",
        ])
        result = load_managed_history(self.root)
        self.assertEqual(result.dashboard.first_workout, date(2026, 7, 27))
        self.assertEqual(result.dashboard.last_workout, date(2026, 9, 1))
        self.assertEqual(result.dashboard.set_count, 8)
        self.assertTrue(any("narrower" in issue for issue in result.issues))
        self.assertIn("BROAD HISTORY", result.report())
        self.assertIn("LATEST WORKOUT DATE", result.report())

    def test_exact_day_superset_replaces_snapshot_instead_of_summing(self):
        write_export(self.root / "inbox/macrofactor/expanded.csv", [
            "2026-08-24,Day A,Tempo Back Squat,Standard Set,500,5,",
            "2026-08-24,Day A,Tempo Back Squat,Standard Set,450,5,",
        ])
        result = load_managed_history(self.root)
        self.assertEqual(result.dashboard.set_count, 8)
        self.assertEqual(len(result.conflicts), 0)

    def test_conflicting_weight_or_rir_is_flagged_not_combined(self):
        write_export(self.root / "inbox/macrofactor/corrected.csv", [
            "2026-08-24,Day A,Tempo Back Squat,Standard Set,400,5,2",
        ])
        result = load_managed_history(self.root)
        self.assertEqual(result.dashboard.set_count, 7)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("2026-08-24", result.conflicts[0])
        self.assertEqual([r.weight for r in result.dashboard.records if r.workout_date == date(2026, 8, 24)], [500])

    def test_equivalent_nonfinite_snapshots_with_distinct_bytes_are_deduplicated(self):
        for index, weight in enumerate(("NaN", "sNaN", "-NaN12", "-sNaN12", "Infinity", "-Infinity")):
            with self.subTest(weight=weight):
                root = managed_inputs(self.root.parent / f"equivalent-{index}")
                first = root / "inbox/macrofactor/first.csv"
                second = root / "inbox/macrofactor/second.csv"
                row = f"2026-09-01,Day A,Tempo Back Squat,Standard Set,{weight},5,"
                write_export(first, [row])
                write_export(second, [row.replace("Standard Set", "STANDARD SET")])
                before = [file_sha256(path) for path in (first, second)]
                self.assertNotEqual(*before, "The two snapshots must not be deduplicated by file hash")

                result = load_managed_history(root)

                self.assertEqual(result.conflicts, ())
                self.assertEqual(result.dashboard.set_count, 8)
                records = [r for r in result.dashboard.records if r.workout_date == date(2026, 9, 1)]
                self.assertEqual([r.weight.as_tuple() for r in records], [Decimal(weight).as_tuple()])
                self.assertEqual(before, [file_sha256(path) for path in (first, second)])

    def test_nonfinite_snapshot_superset_preserves_identical_repeated_sets(self):
        for index, weight in enumerate(("NaN", "sNaN")):
            with self.subTest(weight=weight):
                root = managed_inputs(self.root.parent / f"superset-{index}")
                broad = root / "inbox/macrofactor/broad.csv"
                expanded = root / "inbox/macrofactor/expanded.csv"
                row = f"2026-09-01,Day A,Tempo Back Squat,Standard Set,{weight},5,"
                # More dates make this subset rank before the expanded day.
                write_export(broad, [row, row, "2026-09-02,Day B,Tempo Back Squat,Standard Set,100,5,"])
                write_export(expanded, [row, row, row])

                result = load_managed_history(root)

                self.assertEqual(result.conflicts, ())
                self.assertEqual(result.dashboard.set_count, 11)
                records = [r for r in result.dashboard.records if r.workout_date == date(2026, 9, 1)]
                self.assertEqual([r.weight.as_tuple() for r in records], [Decimal(weight).as_tuple()] * 3)
                self.assertEqual([r.source_row for r in records], [2, 3, 4])

    def test_different_nonfinite_values_and_finite_corrections_remain_conflicts(self):
        pairs = (("NaN", "sNaN"), ("NaN1", "NaN2"), ("NaN1", "-NaN1"),
                 ("sNaN1", "sNaN2"), ("Infinity", "-Infinity"), ("NaN", "100"), ("sNaN", "100"))
        for index, (original, corrected) in enumerate(pairs):
            with self.subTest(original=original, corrected=corrected):
                root = managed_inputs(self.root.parent / f"conflict-{index}")
                row = "2026-09-01,Day A,Tempo Back Squat,Standard Set,{},5,"
                write_export(root / "inbox/macrofactor/broad.csv", [
                    row.format(original), "2026-09-02,Day B,Tempo Back Squat,Standard Set,100,5,",
                ])
                write_export(root / "inbox/macrofactor/corrected.csv", [row.format(corrected)])

                result = load_managed_history(root)

                self.assertEqual(len(result.conflicts), 1)
                self.assertIn("2026-09-01", result.conflicts[0])
                self.assertEqual(result.dashboard.set_count, 9)
                records = [r for r in result.dashboard.records if r.workout_date == date(2026, 9, 1)]
                self.assertEqual([r.weight.as_tuple() for r in records], [Decimal(original).as_tuple()])

    def test_invalid_workbook_or_program_export_does_not_hide_valid_history(self):
        (self.root / "inbox/macrofactor/broken.xlsx").write_bytes(b"not an XLSX")
        write_export(self.root / "inbox/macrofactor/empty.csv", [])
        result = load_managed_history(self.root)
        self.assertEqual(result.dashboard.set_count, 7)
        self.assertTrue(any("broken.xlsx" in issue for issue in result.issues))
        self.assertTrue(any("empty.csv" in issue for issue in result.issues))

    def test_files_changed_during_loading_are_rejected(self):
        original = workspace_fingerprint(self.root)
        with patch("macrofactor_bridge.managed_history.workspace_fingerprint", side_effect=[original, original + (("changed", 1, 1),)]):
            with self.assertRaisesRegex(ValueError, "changed during loading"):
                load_managed_history(self.root, archive=False)

    def test_explicit_missing_workspace_does_not_fall_back_and_symlinks_are_rejected(self):
        missing = str(self.root / "missing")
        self.assertEqual(discover_workspace(missing), Path(missing))
        with self.assertRaisesRegex(ValueError, "Workspace not found"):
            load_managed_history(missing)
        target = self.root / "inbox/macrofactor/external.csv"
        target.symlink_to(self.root.parent / "history.csv")
        result = load_managed_history(self.root)
        self.assertEqual(result.dashboard.set_count, 7)
        self.assertTrue(any("symlink" in issue or "non-regular" in issue for issue in result.issues))

    def test_installed_app_discovers_sibling_local_data(self):
        executable = self.root.parent / "dist/App.app/Contents/MacOS/App"
        self.assertEqual(discover_workspace(executable=executable, checkout=Path("/nonexistent")), self.root)

    def test_archive_only_restart_and_tampered_archive(self):
        first = load_managed_history(self.root)
        # Simulate the user clearing inboxes after successful archival.
        for file in (self.root / "inbox").glob("*/*"):
            file.unlink()
        second = load_managed_history(self.root)
        self.assertEqual(second.dashboard.records, first.dashboard.records)
        first.baseline.path.write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No valid completed"):
            load_managed_history(self.root)


if __name__ == "__main__":
    unittest.main()
