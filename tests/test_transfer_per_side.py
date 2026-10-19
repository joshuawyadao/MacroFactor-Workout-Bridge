"""Synthetic Part 1 transfer coverage for per-side weights and exact row mapping."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from macrofactor_bridge.config import load_config
from macrofactor_bridge.ooxml import XlsxPackage, file_sha256
from macrofactor_bridge.service import apply_changes, build_preview
from macrofactor_bridge.workbook import discover_workbook
from tests.xlsx_factory import write_program_workbook


SHEET = "Synthetic Block"
SESSION_DATE = date(2026, 8, 3)


class PerSideTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.coach = self.root / "coach.xlsx"
        self.export = self.root / "workout.csv"
        self.config_path = self.root / "config.json"

        exercises = [
            ("Harbor Plate Row", "Harbor Horizontal Row", True, "Harbor Plate Row"),
            ("Summit Plate Press", "Summit Incline Press", True, "Summit Plate Press"),
            ("Cedar Rear Fly", "Cedar Fly", True, "Cedar Rear Fly"),
            ("River Walk", "River Lunge", True, "River Walk"),
            ("North Dumbbell Press", "North High Press", True, "North Dumbbell Press"),
            ("Glide Cable Cross", "Glide Fly", True, "Glide Cable Cross"),
            ("Ridge Pullup", "Ridge Pullup", False, "Ridge Pullup"),
            ("Recorded Machine Hinge", "Forge RDL", False, "Planned Hinge"),
            ("Oak Curl", "Oak Curl", False, "Oak Curl"),
        ]
        rules = []
        cells: dict[str, object | None] = {
            "D5": "Style",
            "E5": "Variation",
            "I5": "Week 1",
            "K5": "Week 2",
        }
        for row, (source, coach, per_side, canonical) in enumerate(exercises, start=6):
            rule: dict[str, object] = {
                "canonical": canonical,
                "source_aliases": [source],
                "coach_aliases": [coach],
            }
            if per_side:
                rule.update(weight_multiplier=0.5, weight_suffix="s")
            rules.append(rule)
            cells[f"D{row}"] = coach
            cells[f"E{row}"] = f"Variation for {coach}"
            cells[f"J{row}"] = "Coach already reviewed" if source == "Oak Curl" else None
            cells[f"L{row}"] = None
        write_program_workbook(
            self.coach,
            sheet_name=SHEET,
            cells=cells,
            merges=("I5:J5", "K5:L5"),
        )
        self.config_path.write_text(
            json.dumps(
                {
                    "workbook": {
                        "exercise_header_labels": ["Style"],
                        "week_header_pattern": "^week\\s*\\d+$",
                    },
                    "exercises": rules,
                }
            ),
            encoding="utf-8",
        )
        self.config = load_config(self.config_path)

        rows: list[dict[str, str]] = []

        def add(source: str, weight: int, reps: tuple[int, ...], base: int = 0) -> None:
            for count in reps:
                rows.append(
                    {
                        "Date": SESSION_DATE.isoformat(),
                        "Workout": "Synthetic Session",
                        "Exercise": source,
                        "Set Type": "Standard Set",
                        "Weight (lb)": str(weight),
                        "Reps": str(count),
                        "Exercise Base Weight (lb)": str(base),
                    }
                )

        add("Harbor Plate Row", 94, (9, 9, 8), base=55)
        add("Summit Plate Press", 164, (11, 11, 8), base=55)
        add("Cedar Rear Fly", 36, (13, 11, 9))
        add("River Walk", 56, (16, 16, 15))
        add("North Dumbbell Press", 116, (11, 9, 7, 7))
        add("Glide Cable Cross", 84, (12, 11))
        add("Ridge Pullup", 0, (6, 6, 6, 5, 5, 5))
        add("Recorded Machine Hinge", 137, (9, 8), base=55)
        add("Oak Curl", 42, (12,))
        with self.export.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def preview(self, coach: Path | None = None, week: str = "Week 1"):
        return build_preview(
            self.export,
            coach or self.coach,
            self.config,
            SHEET,
            week,
            SESSION_DATE,
            SESSION_DATE,
        )

    def test_per_side_transfer_preserves_reps_and_ignores_machine_base_weight(self) -> None:
        options = discover_workbook(self.coach, self.config)[0]
        self.assertEqual(
            [(week.label, week.result_column) for week in options.weeks],
            [("Week 1", 10), ("Week 2", 12)],
        )
        report = self.preview()
        proposed = {write.cell: write.value for write in report.proposed_writes}
        self.assertEqual(
            proposed,
            {
                "J6": "47s x 9, 9, 8",
                "J7": "82s x 11, 11, 8",
                "J8": "18s x 13, 11, 9",
                "J9": "28s x 16, 16, 15",
                "J10": "58s x 11, 9, 7, 7",
                "J11": "42s x 12, 11",
                "J12": "0 x 6, 6, 6, 5, 5, 5",
                "J13": "137 x 9, 8",
            },
        )
        self.assertEqual(report.unmatched_exercises, [])
        self.assertEqual(report.ambiguous_matches, [])
        self.assertEqual([item["cell"] for item in report.occupied_cells], ["J14"])

        coach_hash = file_sha256(self.coach)
        export_hash = file_sha256(self.export)
        output = self.root / "completed.xlsx"
        apply_changes(report, self.config, output)
        self.assertEqual(file_sha256(self.coach), coach_hash)
        self.assertEqual(file_sha256(self.export), export_hash)
        snapshot = XlsxPackage(output).sheet_snapshot(SHEET)
        for cell, value in proposed.items():
            self.assertEqual(snapshot.cells[cell].value, value)
        self.assertEqual(snapshot.cells["J14"].value, "Coach already reviewed")
        self.assertTrue(all(snapshot.cells[f"L{row}"].is_empty for row in range(6, 15)))

        second_week = self.preview(output, "Week 2")
        self.assertEqual(
            {write.cell for write in second_week.proposed_writes},
            {f"L{row}" for row in range(6, 15)},
        )


if __name__ == "__main__":
    unittest.main()
