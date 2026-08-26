from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge import local_workspace
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
            self.assertEqual(len(created), 8)
            self.assertTrue((root / "inbox" / "coach").is_dir())
            self.assertTrue((root / "archive" / "macrofactor").is_dir())
            self.assertTrue((root / "current").is_dir())
            self.assertTrue((root / "generated" / "reports").is_dir())

    def test_archive_validates_copies_manifests_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            coach = root / "inbox" / "coach" / "download (17).xlsx"
            export = root / "inbox" / "macrofactor" / "export-final-FINAL.xlsx"
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
            coach_archive = next(path for path in archived if path.parent.name == "coach")
            export_archive = next(path for path in archived if path.parent.name == "macrofactor")
            self.assertRegex(
                coach_archive.name,
                r"^2026-08-24--Coach-Program--[0-9a-f]{12}\.xlsx$",
            )
            export_validation = next(
                entry["validation"]
                for entry in result["entries"]
                if entry["kind"] == "macrofactor"
            )
            self.assertRegex(
                export_archive.name,
                rf"^2026-08-24--{export_validation['first_workout']}_to_"
                rf"{export_validation['last_workout']}--MacroFactor-Exercise-Log--"
                r"[0-9a-f]{12}\.xlsx$",
            )
            payload = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            export_entry = next(
                item for item in payload["entries"] if item["kind"] == "macrofactor"
            )
            self.assertEqual(export_entry["validation"]["row_count"], 18)
            self.assertEqual(export_entry["original_name"], "export-final-FINAL.xlsx")
            coach_entry = next(
                item for item in payload["entries"] if item["kind"] == "coach"
            )
            self.assertGreaterEqual(coach_entry["validation"]["usable_sheet_count"], 1)
            current_coach = root / "current" / "Coach Program - Current.xlsx"
            current_export = root / "current" / "MacroFactor Exercise Log - Current.xlsx"
            self.assertTrue(current_coach.is_symlink())
            self.assertTrue(current_export.is_symlink())
            self.assertEqual(current_coach.resolve(), coach_archive)
            self.assertEqual(current_export.resolve(), export_archive)

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
            self.assertEqual(
                status["macrofactor"]["current"],
                str(root.resolve() / "current" / "MacroFactor Exercise Log - Current.xlsx"),
            )

    def test_source_replaced_during_validation_is_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            source = root / "inbox" / "macrofactor" / "log.csv"
            source.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2026-08-03,Upper,Press,Normal,100,8\n",
                encoding="utf-8",
            )
            original_validator = local_workspace._validate_export

            def replace_after_validation(path: Path) -> dict[str, object]:
                validation = original_validator(path)
                replacement = path.with_name("replacement.tmp")
                replacement.write_text(
                    "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                    "2099-01-08,Upper,Press,Normal,200,5\n",
                    encoding="utf-8",
                )
                replacement.replace(path)
                return validation

            with patch(
                "macrofactor_bridge.local_workspace._validate_export",
                side_effect=replace_after_validation,
            ):
                result = archive_inbox(root, CONFIG, now=NOW)

            self.assertEqual(result["entries"], [])
            self.assertEqual(result["current"], {})
            self.assertIn("changed during validation", result["errors"][0]["error"])
            self.assertFalse(any((root / "archive" / "macrofactor").iterdir()))

    def test_newer_export_updates_current_link_without_renaming_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            original = root / "inbox" / "macrofactor" / "Macrofactor Export.xlsx"
            original.write_bytes((FIXTURES / "macrofactor-log.xlsx").read_bytes())
            first = archive_inbox(root, CONFIG, now=NOW)
            first_archive = Path(first["entries"][0]["archive"])

            newer = root / "inbox" / "macrofactor" / "exercise_data (3).csv"
            newer.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2099-01-08,Upper,Press,Normal,100,8\n",
                encoding="utf-8",
            )
            second = archive_inbox(
                root,
                CONFIG,
                now=datetime(2026, 8, 25, 20, 15, tzinfo=timezone.utc),
            )

            current = root / "current" / "MacroFactor Exercise Log - Current.csv"
            selected = second["current"]["macrofactor"]
            self.assertTrue(current.is_symlink())
            self.assertEqual(current.resolve(), Path(selected["archive"]))
            self.assertIn("2099-01-08_to_2099-01-08", current.resolve().name)
            self.assertTrue(first_archive.exists())
            self.assertFalse(
                (root / "current" / "MacroFactor Exercise Log - Current.xlsx").exists()
            )

    def test_older_later_upload_does_not_roll_current_link_backward(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            inbox = root / "inbox" / "macrofactor"
            newer = inbox / "newer.csv"
            newer.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2099-01-08,Upper,Press,Normal,100,8\n",
                encoding="utf-8",
            )
            first = archive_inbox(root, CONFIG, now=NOW)
            newer_archive = Path(first["entries"][0]["archive"])
            newer.unlink()

            older = inbox / "older.csv"
            older.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
                "2020-01-08,Upper,Press,Normal,90,10\n",
                encoding="utf-8",
            )
            second = archive_inbox(root, CONFIG, now=NOW + timedelta(days=1))

            current = root / "current" / "MacroFactor Exercise Log - Current.csv"
            self.assertEqual(len(second["entries"]), 1)
            self.assertIn("2020-01-08", second["entries"][0]["archive"])
            self.assertEqual(Path(second["current"]["macrofactor"]["archive"]), newer_archive)
            self.assertEqual(current.resolve(), newer_archive)

    def test_legacy_macrofactor_archive_gets_upload_date_name_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            source = root / "inbox" / "macrofactor" / "download.xlsx"
            source.write_bytes((FIXTURES / "macrofactor-log.xlsx").read_bytes())
            digest = file_sha256(source)
            legacy = root / "archive" / "macrofactor" / (
                "2026-08-03_to_2026-08-09--MacroFactor-Exercise-Log--"
                f"{digest[:12]}.xlsx"
            )
            legacy.write_bytes(source.read_bytes())

            result = archive_inbox(root, CONFIG, now=NOW)

            entry = result["entries"][0]
            migrated = Path(entry["archive"])
            self.assertTrue(entry["deduplicated"])
            self.assertTrue(migrated.name.startswith("2026-08-24--2026-08-03_to_"))
            self.assertEqual(file_sha256(migrated), digest)
            self.assertTrue(legacy.exists())

    def test_current_regular_file_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            protected = root / "current" / "Coach Program - Current.xlsx"
            protected.write_bytes(b"personal file")
            coach = root / "inbox" / "coach" / "anything.xlsx"
            coach.write_bytes((FIXTURES / "coach-template.xlsx").read_bytes())

            result = archive_inbox(root, CONFIG, now=NOW)

            self.assertEqual(protected.read_bytes(), b"personal file")
            self.assertEqual(len(result["errors"]), 1)
            self.assertEqual(result["errors"][0]["kind"], "current")

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

    def test_unusable_coach_workbook_is_not_archived_or_promoted_to_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            unusable = root / "inbox" / "coach" / "not-a-coach-template.xlsx"
            unusable.write_bytes((FIXTURES / "macrofactor-log.xlsx").read_bytes())

            result = archive_inbox(root, CONFIG, now=NOW)

            self.assertEqual(result["entries"], [])
            self.assertEqual(result["current"], {})
            self.assertEqual(result["errors"][0]["kind"], "coach")
            self.assertIn("no worksheet matching", result["errors"][0]["error"])
            self.assertTrue(unusable.exists())
            self.assertFalse(any((root / "archive" / "coach").iterdir()))
            self.assertFalse((root / "current" / "Coach Program - Current.xlsx").exists())

    def test_latest_archives_ignores_corrupt_manifests_and_reads_legacy_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            setup_workspace(root)
            manifests = root / "manifests"
            (manifests / "20260824T000000000000Z--ingest.json").write_text(
                "not json", encoding="utf-8"
            )
            malformed_payloads = (
                [],
                {"ingested_at": NOW.isoformat(), "entries": {}},
                {"ingested_at": NOW.isoformat(), "entries": [None, "entry"]},
                {"ingested_at": NOW.isoformat(), "current": {"coach": []}},
                {
                    "ingested_at": NOW.isoformat(),
                    "entries": [
                        {
                            "kind": "coach",
                            "archive": "/invalid/coach.xlsx",
                            "validation": [],
                        }
                    ],
                },
            )
            for index, payload in enumerate(malformed_payloads, start=1):
                (manifests / f"20260824T00000{index}000000Z--ingest.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            legacy_path = manifests / "20260824T010000000000Z--ingest.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "ingested_at": NOW.isoformat(),
                        "entries": [
                            {
                                "kind": "coach",
                                "archive": "/archive/coach.xlsx",
                                "sha256": "abc",
                                "validation": {"usable_sheet_count": 1},
                            },
                            {"kind": "unknown", "archive": "/ignored"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = latest_archives(root)

            self.assertEqual(status["coach"]["archive"], "/archive/coach.xlsx")
            self.assertEqual(Path(status["coach"]["manifest"]).resolve(), legacy_path.resolve())
            self.assertIsNone(status["macrofactor"])

    def test_cli_setup_and_status_are_noninteractive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "local-data"
            self.assertEqual(main(["--root", str(root), "setup"]), 0)
            self.assertEqual(main(["--root", str(root), "status"]), 0)


if __name__ == "__main__":
    unittest.main()
