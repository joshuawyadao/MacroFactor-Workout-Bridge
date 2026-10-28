"""Operation-scoped archive verification without changing managed history safety."""

import json
from collections import Counter
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from macrofactor_bridge import local_workspace, managed_history
from macrofactor_bridge.local_workspace import archive_inbox, setup_workspace, verified_archives
from macrofactor_bridge.managed_history import load_managed_history
from tests.comparison_fixture import comparison_inputs


def workspace(directory):
    root = (directory / "local-data").resolve()
    setup_workspace(root)
    export, coach, annotation = comparison_inputs(directory)
    shutil.copy2(export, root / "inbox/macrofactor/all-time.csv")
    shutil.copy2(coach, root / "inbox/coach/coach.xlsx")
    shutil.copy2(annotation, root / "annotations/workout-history.json")
    return root


def clear_inbox(root):
    for path in (root / "inbox").glob("*/*"):
        path.unlink()


class ArchiveEfficiencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = workspace(Path(temporary.name))

    def test_duplicate_manifest_references_hash_each_canonical_archive_once(self):
        first = load_managed_history(self.root)
        clear_inbox(self.root)
        original = next((self.root / "manifests").glob("*--ingest.json"))
        payload = json.loads(original.read_text(encoding="utf-8"))
        original_entries = payload["entries"]
        incorrect = {**original_entries[0], "sha256": "0" * 64}
        payload["entries"] = [incorrect, *original_entries, *original_entries]
        duplicate = original.with_name("99991231T000000000000Z--ingest.json")
        duplicate.write_text(json.dumps(payload), encoding="utf-8")

        actual_hash = local_workspace.file_sha256
        hashed = Counter()

        def counted(path):
            hashed[Path(path).resolve()] += 1
            return actual_hash(path)

        with patch.object(local_workspace, "file_sha256", side_effect=counted):
            entries = verified_archives(self.root)

        archives = {source.path for source in first.exports} | {first.coach_path}
        self.assertEqual(len(entries), len(original_entries) * 3)
        self.assertEqual({entry["sha256"] for entry in entries},
                         {entry["sha256"] for entry in original_entries})
        self.assertEqual({path: hashed[path] for path in archives},
                         {path: 1 for path in archives})

    def test_history_load_reuses_archive_entries_and_rechecks_selected_content(self):
        initial = load_managed_history(self.root)
        clear_inbox(self.root)
        original_hash = local_workspace.file_sha256
        local_counts = Counter()
        history_counts = Counter()

        def local_hash(path):
            local_counts[Path(path).resolve()] += 1
            return original_hash(path)

        def history_hash(path):
            history_counts[Path(path).resolve()] += 1
            return original_hash(path)

        with patch.object(local_workspace, "file_sha256", side_effect=local_hash), \
             patch.object(managed_history, "file_sha256", side_effect=history_hash):
            loaded = load_managed_history(self.root)

        self.assertEqual(loaded.dashboard.records, initial.dashboard.records)
        self.assertEqual(loaded.dashboard.set_count, 7)
        self.assertEqual(loaded.issues, ())
        self.assertEqual(local_counts[initial.baseline.path], 2)  # manifest, current link
        self.assertEqual(local_counts[initial.coach_path], 2)
        self.assertEqual(history_counts[initial.baseline.path], 1)  # post-parse
        self.assertEqual(history_counts[initial.coach_path], 2)  # post-parse, final coach

    def test_each_invocation_verifies_again_and_reports_archive_tamper(self):
        initial = load_managed_history(self.root)
        clear_inbox(self.root)
        self.assertEqual(load_managed_history(self.root).dashboard.set_count, 7)
        initial.baseline.path.write_text("tampered archive", encoding="utf-8")

        self.assertFalse(any(entry["kind"] == "macrofactor"
                             for entry in verified_archives(self.root)))
        with self.assertRaisesRegex(ValueError, "No valid completed workout sets"):
            load_managed_history(self.root)

    def test_changed_during_parse_is_rejected_after_entry_reuse(self):
        initial = load_managed_history(self.root)
        clear_inbox(self.root)
        original_import = managed_history.load_exercise_log_with_diagnostics

        def mutate_after_parse(path):
            result = original_import(path)
            Path(path).write_text("changed after parse", encoding="utf-8")
            return result

        with patch.object(managed_history, "load_exercise_log_with_diagnostics",
                          side_effect=mutate_after_parse):
            with self.assertRaisesRegex(ValueError, "File changed during loading"):
                load_managed_history(self.root)
        self.assertTrue(initial.baseline.path.exists())

    def test_retargeted_archive_is_rejected_after_initial_verification(self):
        initial = load_managed_history(self.root)
        clear_inbox(self.root)
        external = self.root.parent / "synthetic-outside.csv"
        shutil.copy2(initial.baseline.path, external)
        original_verify = managed_history.verified_archives

        def retarget_after_verification(root):
            entries = original_verify(root)
            initial.baseline.path.unlink()
            initial.baseline.path.symlink_to(external)
            return entries

        with patch.object(managed_history, "verified_archives",
                          side_effect=retarget_after_verification):
            with self.assertRaisesRegex(ValueError, "No valid completed workout sets"):
                load_managed_history(self.root, archive=False)

    def test_selected_archive_is_rechecked_before_current_link_update(self):
        initial = load_managed_history(self.root)
        clear_inbox(self.root)
        current = self.root / "current/MacroFactor Exercise Log - Current.csv"
        target = current.readlink()
        original_update = local_workspace._update_current_files

        def mutate_before_update(root, entries):
            initial.baseline.path.write_text("changed after verification", encoding="utf-8")
            return original_update(root, entries)

        with patch.object(local_workspace, "_update_current_files", side_effect=mutate_before_update):
            result = archive_inbox(self.root, new_only=True)

        self.assertEqual(current.readlink(), target)
        self.assertEqual(result["entries"], [])
        self.assertTrue(any("Selected archive changed" in error["error"]
                            for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
