from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from macrofactor_bridge.local_workspace import (
    archive_inbox,
    latest_archives,
    main,
    setup_workspace,
)
from macrofactor_bridge.ooxml import file_sha256


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = ROOT / "config" / "exercises.example.json"
NOW = datetime(2026, 8, 24, 20, 15, tzinfo=timezone.utc)


class LocalWorkspaceTests(unittest.TestCase):
    def test_setup_creates_private_workflow_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            created = setup_workspace(root)
            self.assertEqual(len(created), 7)
            self.assertTrue((root / "inbox" / "coach").is_dir())
            self.assertTrue((root / "archive" / "macrofactor").is_dir())
            self.assertTrue((root / "generated" / "reports").is_dir())

    def test_archive_validates_copies_manifests_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            coach = root / "inbox" / "coach" / "coach.xlsx"
            export = root / "inbox" / "macrofactor" / "log.xlsx"
            coach.write_bytes((FIXTURES / "coach-template.xlsx").read_bytes())
            export.write_bytes((FIXTURES / "macrofactor-log.xlsx").read_bytes())
            source_hashes = (file_sha256(coach), file_sha256(export))

            result = archive_inbox(root, CONFIG, now=NOW)

            self.assertEqual(len(result["entries"]), 2)
            self.assertEqual(result["errors"], [])
            self.assertEqual((file_sha256(coach), file_sha256(export)), source_hashes)
            self.assertTrue(coach.exists())
            self.assertTrue(export.exists())
            archived = [Path(entry["archive"]) for entry in result["entries"]]
            self.assertTrue(all(path.exists() for path in archived))
            self.assertTrue(all("2026-08-24--" in path.name for path in archived))
            payload = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            export_entry = next(item for item in payload["entries"] if item["kind"] == "macrofactor")
            self.assertEqual(export_entry["validation"]["row_count"], 18)
            coach_entry = next(item for item in payload["entries"] if item["kind"] == "coach")
            self.assertGreaterEqual(coach_entry["validation"]["usable_sheet_count"], 1)

    def test_repeated_content_is_deduplicated_but_each_run_gets_a_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            export = root / "inbox" / "macrofactor" / "log.xlsx"
            export.write_bytes((FIXTURES / "macrofactor-log.xlsx").read_bytes())
            first = archive_inbox(root, CONFIG, now=NOW)
            later = datetime(2026, 8, 25, 20, 15, tzinfo=timezone.utc)
            second = archive_inbox(root, CONFIG, now=later)
            self.assertFalse(first["entries"][0]["deduplicated"])
            self.assertTrue(second["entries"][0]["deduplicated"])
            self.assertEqual(first["entries"][0]["archive"], second["entries"][0]["archive"])
            self.assertNotEqual(first["manifest"], second["manifest"])
            status = latest_archives(root)
            self.assertEqual(status["macrofactor"]["ingested_at"], later.isoformat())

    def test_invalid_or_unsupported_inputs_are_reported_and_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            invalid = root / "inbox" / "macrofactor" / "notes.txt"
            invalid.write_text("not a workout export", encoding="utf-8")
            result = archive_inbox(root, CONFIG, now=NOW)
            self.assertEqual(result["entries"], [])
            self.assertEqual(len(result["errors"]), 1)
            self.assertFalse(any((root / "archive" / "macrofactor").iterdir()))

    def test_cli_setup_and_status_are_noninteractive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            self.assertEqual(main(["--root", str(root), "setup"]), 0)
            self.assertEqual(main(["--root", str(root), "status"]), 0)


if __name__ == "__main__":
    unittest.main()
