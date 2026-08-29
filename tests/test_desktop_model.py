from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from macrofactor_bridge.desktop_model import (
    bundled_config_path,
    copy_mapping,
    default_output_path,
    discover_sheet_weeks,
    latest_export_week,
    review_sections,
    review_text,
)
from macrofactor_bridge.models import BridgeReport


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = ROOT / "config" / "exercises.example.json"


class DesktopModelTests(unittest.TestCase):
    def test_bundled_mapping_and_workbook_choices_are_discoverable(self) -> None:
        self.assertEqual(bundled_config_path(), CONFIG)
        choices = discover_sheet_weeks(FIXTURES / "coach-template.xlsx", CONFIG)
        self.assertIn(("Training Block", ("Week 1", "Week 2")), choices)

    def test_bundled_mapping_falls_back_to_installed_package_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_checkout = Path(directory) / "missing.json"
            with patch(
                "macrofactor_bridge.desktop_model._checkout_config_path",
                return_value=missing_checkout,
            ):
                packaged = bundled_config_path()

        self.assertEqual(packaged.parent.name, "resources")
        self.assertEqual(packaged.read_bytes(), CONFIG.read_bytes())

    def test_latest_export_date_selects_its_monday_through_sunday(self) -> None:
        start, end = latest_export_week(FIXTURES / "macrofactor-log.xlsx")
        self.assertEqual((start, end), (date(2026, 8, 3), date(2026, 8, 9)))

    def test_output_name_is_safe_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Coach Plan.xlsx"
            source.touch()
            first = default_output_path(source, "Week 1")
            self.assertEqual(first.name, "Coach Plan-week-1-results.xlsx")
            first.touch()
            second = default_output_path(source, "Week 1")
            self.assertEqual(second.name, "Coach Plan-week-1-results-2.xlsx")
            self.assertNotEqual(second, source)

    def test_mapping_copy_refuses_an_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "mapping.json"
            self.assertEqual(copy_mapping(CONFIG, destination), destination)
            with self.assertRaises(FileExistsError):
                copy_mapping(CONFIG, destination)

    def test_review_text_counts_each_conservative_outcome(self) -> None:
        report = BridgeReport("export.xlsx", "coach.xlsx", "Sheet", "Week 1", "a", "b")
        report.rows_read = 3
        report.rows_in_range = 2
        report.unmatched_exercises.append({"exercise": "Unknown"})
        report.zero_rep_rows.append({"row": 4, "reps": "0"})
        report.exercise_notes.append({"exercise": "Example", "note": "Use the blue rack"})
        sections = review_sections(report)
        self.assertEqual([section.count for section in sections], [1, 0, 1, 0, 0, 1])
        text = review_text(report)
        self.assertIn("Unmatched exercises: 1", text)
        self.assertIn("MacroFactor exercise notes: 1", text)
        self.assertIn("missing workout is never interpreted as skipped", text)


if __name__ == "__main__":
    unittest.main()
