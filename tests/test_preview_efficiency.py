from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from collections import Counter
from copy import copy
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from macrofactor_bridge.config import load_config
from macrofactor_bridge import importers
from macrofactor_bridge.importers import (
    ImportError,
    load_exercise_log_with_diagnostics,
    load_exercise_notes,
)
from macrofactor_bridge.ooxml import MAIN_NS, PACKAGE_REL_NS, REL_NS, XlsxPackage, qn
from macrofactor_bridge.service import build_preview
from macrofactor_bridge.workbook import select_sheet_options
from tests.test_integration import (
    COACH,
    CONFIG,
    LOG,
    copy_coach_with_second_day,
    copy_xlsx_with_extra_cells,
    write_clean_log,
    write_marker_config,
)


def write_export_with_notes_sheet(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.find(qn(MAIN_NS, "sheets"))
        assert sheets is not None
        ET.SubElement(sheets, qn(MAIN_NS, "sheet"), {
            "name": "Active Program", "sheetId": "2", qn(REL_NS, "id"): "Rnotes",
        })
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        ET.SubElement(relationships, qn(PACKAGE_REL_NS, "Relationship"), {
            "Type": f"{REL_NS}/worksheet", "Target": "/xl/worksheets/sheet2.xml", "Id": "Rnotes",
        })
        content_types = ET.fromstring(archive.read("[Content_Types].xml"))
        content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        ET.SubElement(content_types, qn(content_ns, "Override"), {
            "PartName": "/xl/worksheets/sheet2.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        })
        worksheet = ET.Element(qn(MAIN_NS, "worksheet"))
        sheet_data = ET.SubElement(worksheet, qn(MAIN_NS, "sheetData"))
        for row_number, values in enumerate(
            (("Exercise", "Notes"), ("Tempo Back Squat", "Separate sheet note")), start=1
        ):
            row = ET.SubElement(sheet_data, qn(MAIN_NS, "row"), {"r": str(row_number)})
            for column, value in zip(("A", "B"), values):
                cell = ET.SubElement(row, qn(MAIN_NS, "c"), {
                    "r": f"{column}{row_number}", "t": "inlineStr",
                })
                ET.SubElement(ET.SubElement(cell, qn(MAIN_NS, "is")), qn(MAIN_NS, "t")).text = value
        replacements = {
            "xl/workbook.xml": ET.tostring(workbook, encoding="utf-8"),
            "xl/_rels/workbook.xml.rels": ET.tostring(relationships, encoding="utf-8"),
            "[Content_Types].xml": ET.tostring(content_types, encoding="utf-8"),
        }
        with zipfile.ZipFile(destination, "w") as output:
            for member in archive.infolist():
                output.writestr(copy(member), replacements.get(member.filename, archive.read(member)))
            output.writestr("xl/worksheets/sheet2.xml", ET.tostring(worksheet, encoding="utf-8"))


class PreviewReadReuseTests(unittest.TestCase):
    def _preview(self, export: Path, coach: Path, config_path: Path):
        calls: Counter[tuple[Path, str]] = Counter()
        original = XlsxPackage.sheet_snapshot

        def counted(package: XlsxPackage, sheet):
            calls[(package.path, sheet.name if hasattr(sheet, "name") else sheet)] += 1
            return original(package, sheet)

        with patch.object(XlsxPackage, "sheet_snapshot", counted):
            report = build_preview(
                export, coach, load_config(config_path), "Training Block", "Week 1",
                date(2026, 8, 3), date(2026, 8, 9),
            )
        return report, calls

    def test_ordinary_xlsx_preview_reads_each_selected_sheet_once_and_keeps_notes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "log-with-notes.xlsx"
            copy_xlsx_with_extra_cells(
                LOG, export,
                {
                    "M30": "Exercise", "N30": "Notes",
                    "M31": "Tempo Back Squat", "N31": "Use the blue rack",
                    "M32": "Not Performed", "N32": "Unrelated note",
                },
            )
            report, calls = self._preview(export, COACH, CONFIG)

            self.assertEqual(calls, Counter({
                (export, "Workout Log"): 1,
                (COACH, "Training Block"): 1,
            }))
            self.assertEqual(
                {proposal.cell: proposal.value for proposal in report.proposed_writes}["J5"],
                "200 x 8, 7; 180 x 10",
            )
            self.assertEqual(len(report.exercise_notes), 1)
            self.assertEqual(report.exercise_notes[0]["note"], "Use the blue rack")
            self.assertEqual(report.exercise_notes[0]["sheet"], "Workout Log")
            self.assertEqual(len(report.occupied_cells), 1)
            self.assertEqual(len(report.unmatched_exercises), 1)

            # Parsed rows belong only to this operation; a later preview sees the new file.
            changed = Path(directory) / "changed.xlsx"
            copy_xlsx_with_extra_cells(LOG, changed, {
                "M30": "Exercise", "N30": "Notes",
                "M31": "Tempo Back Squat", "N31": "Updated note",
            })
            changed.replace(export)
            refreshed, fresh_calls = self._preview(export, COACH, CONFIG)
            self.assertEqual(fresh_calls[(export, "Workout Log")], 1)
            self.assertEqual(refreshed.exercise_notes[0]["note"], "Updated note")
            self.assertNotEqual(report.preview_export_hash, refreshed.preview_export_hash)

    def test_eligible_empty_day_marker_reads_coach_sheet_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coach = root / "two-days.xlsx"
            export = root / "clean.csv"
            config_path = root / "mapping.json"
            copy_coach_with_second_day(COACH, coach)
            write_clean_log(export)
            write_marker_config(config_path)

            report, calls = self._preview(export, coach, config_path)
            self.assertEqual(calls, Counter({(coach, "Training Block"): 1}))
            markers = [write for write in report.proposed_writes if write.kind == "empty_day_marker"]
            self.assertEqual([(write.cell, write.value) for write in markers], [("J16", "Skip")])
            self.assertEqual(report.empty_day_markers[0]["day"], "Day 2")
            self.assertEqual(report.unmatched_exercises, [])

            shutil.copyfile(COACH, coach)
            refreshed, fresh_calls = self._preview(export, coach, config_path)
            self.assertEqual(fresh_calls[(coach, "Training Block")], 1)
            self.assertEqual(refreshed.empty_day_markers, [])
            self.assertNotEqual(report.preview_source_hash, refreshed.preview_source_hash)

    def test_separate_notes_sheet_is_read_once_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "two-sheets.xlsx"
            write_export_with_notes_sheet(LOG, export)
            report, calls = self._preview(export, COACH, CONFIG)
            self.assertEqual(calls, Counter({
                (export, "Workout Log"): 1,
                (export, "Active Program"): 1,
                (COACH, "Training Block"): 1,
            }))
            self.assertEqual(len(report.proposed_writes), 6)
            self.assertEqual(len(report.exercise_notes), 1)
            self.assertEqual(report.exercise_notes[0]["sheet"], "Active Program")
            self.assertEqual(report.exercise_notes[0]["note"], "Separate sheet note")

            default = load_exercise_log_with_diagnostics(export)
            self.assertEqual(default.exercise_notes, ())
            imported = load_exercise_log_with_diagnostics(export, include_notes=True)
            self.assertEqual(default.records, imported.records)
            self.assertEqual(default.skipped_rows, imported.skipped_rows)
            self.assertEqual(len(imported.exercise_notes), 1)
            self.assertEqual(imported.exercise_notes[0].note, "Separate sheet note")
            self.assertEqual(imported.exercise_notes, tuple(load_exercise_notes(export)))
            self.assertEqual(set(vars(imported)), {"records", "skipped_rows", "exercise_notes"})

    def test_default_xlsx_import_skips_note_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "two-sheets.xlsx"
            write_export_with_notes_sheet(LOG, export)
            original_notes = importers._notes_from_rows
            with patch.object(importers, "_notes_from_rows", wraps=original_notes) as scan:
                default = load_exercise_log_with_diagnostics(export)
                self.assertEqual(scan.call_count, 0)
                self.assertEqual(default.exercise_notes, ())
                opted_in = load_exercise_log_with_diagnostics(export, include_notes=True)
                self.assertEqual(scan.call_count, 2)
            self.assertEqual(default.records, opted_in.records)
            self.assertEqual(default.skipped_rows, opted_in.skipped_rows)
            self.assertEqual(len(opted_in.exercise_notes), 1)

    def test_public_selection_keeps_four_value_contract(self) -> None:
        selection = select_sheet_options(COACH, load_config(CONFIG), "Training Block", "Week 1")
        self.assertEqual(len(selection), 4)
        self.assertEqual(selection[3].label, "Week 1")

    def test_multiple_log_tables_still_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "two-logs.xlsx"
            copy_xlsx_with_extra_cells(LOG, export, {
                "A30": "Date", "C30": "Workout", "D30": "Exercise",
                "F30": "Set Type", "G30": "Weight (lbs)", "H30": "Reps",
            })
            with self.assertRaisesRegex(ImportError, "Multiple MacroFactor log tables"):
                load_exercise_log_with_diagnostics(export)

    def test_csv_diagnostic_result_has_no_notes_or_sheet_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "clean.csv"
            write_clean_log(export)
            imported = load_exercise_log_with_diagnostics(export)
            self.assertEqual(len(imported.records), 1)
            self.assertEqual(imported.exercise_notes, ())
            self.assertEqual(load_exercise_notes(export), [])
            self.assertEqual(set(vars(imported)), {"records", "skipped_rows", "exercise_notes"})

    def test_standalone_notes_import_accepts_workbook_without_log_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "with-log.xlsx"
            note_only = Path(directory) / "notes-only.xlsx"
            write_export_with_notes_sheet(LOG, source)
            empty_sheet = ET.Element(qn(MAIN_NS, "worksheet"))
            ET.SubElement(empty_sheet, qn(MAIN_NS, "sheetData"))
            with zipfile.ZipFile(source) as archive, zipfile.ZipFile(note_only, "w") as output:
                for member in archive.infolist():
                    contents = (
                        ET.tostring(empty_sheet, encoding="utf-8")
                        if member.filename == "xl/worksheets/sheet1.xml"
                        else archive.read(member)
                    )
                    output.writestr(copy(member), contents)
            notes = load_exercise_notes(note_only)
            self.assertEqual([(note.sheet, note.note) for note in notes], [
                ("Active Program", "Separate sheet note")
            ])
            with self.assertRaisesRegex(ImportError, "No worksheet contains"):
                load_exercise_log_with_diagnostics(note_only)


if __name__ == "__main__":
    unittest.main()
