from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from copy import copy
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.cli import main
from macrofactor_bridge.config import ConfigError, load_config
from macrofactor_bridge.importers import (
    ImportError,
    load_exercise_log,
    load_exercise_log_with_diagnostics,
)
from macrofactor_bridge.ooxml import MAIN_NS, XlsxPackage, file_sha256, qn, split_cell_reference
from macrofactor_bridge.service import apply_changes, build_preview
from macrofactor_bridge.workbook import discover_workbook


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = ROOT / "config" / "exercises.example.json"
COACH = FIXTURES / "coach-template.xlsx"
LOG = FIXTURES / "macrofactor-log.xlsx"


def copy_xlsx_with_singular_weight_header(source: Path, destination: Path) -> None:
    """Create an anonymized current-header fixture without committing another binary."""
    with (
        zipfile.ZipFile(source, "r") as source_zip,
        zipfile.ZipFile(destination, "w") as output_zip,
    ):
        for item in source_zip.infolist():
            content = source_zip.read(item.filename).replace(b"Weight (lbs)", b"Weight (lb)")
            output_zip.writestr(item, content)


def copy_xlsx_with_extra_cells(
    source: Path, destination: Path, cells: dict[str, str]
) -> None:
    package = XlsxPackage(source)
    sheet = package.sheet_by_name("Workout Log")
    with zipfile.ZipFile(source, "r") as source_zip:
        root = ET.fromstring(source_zip.read(sheet.path))
        sheet_data = root.find(qn(MAIN_NS, "sheetData"))
        assert sheet_data is not None
        rows = {
            int(row.attrib["r"]): row
            for row in sheet_data.findall(qn(MAIN_NS, "row"))
        }
        for reference, value in cells.items():
            row_number, _ = split_cell_reference(reference)
            row = rows.get(row_number)
            if row is None:
                row = ET.SubElement(
                    sheet_data, qn(MAIN_NS, "row"), {"r": str(row_number)}
                )
                rows[row_number] = row
            cell = ET.SubElement(
                row, qn(MAIN_NS, "c"), {"r": reference, "t": "inlineStr"}
            )
            inline = ET.SubElement(cell, qn(MAIN_NS, "is"))
            ET.SubElement(inline, qn(MAIN_NS, "t")).text = value
            row[:] = sorted(
                row,
                key=lambda element: split_cell_reference(
                    element.attrib.get("r", "A1")
                )[1],
            )
        sheet_data[:] = sorted(
            sheet_data,
            key=lambda element: int(element.attrib.get("r", "0")),
        )
        changed_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(destination, "w") as output_zip:
            output_zip.comment = source_zip.comment
            for item in source_zip.infolist():
                content = (
                    changed_xml
                    if item.filename == sheet.path
                    else source_zip.read(item.filename)
                )
                output_zip.writestr(copy(item), content)


def copy_minimal_log_xlsx(source: Path, destination: Path) -> None:
    package = XlsxPackage(source)
    sheet = package.sheet_by_name("Workout Log")
    with zipfile.ZipFile(source, "r") as source_zip:
        root = ET.fromstring(source_zip.read(sheet.path))
        sheet_data = root.find(qn(MAIN_NS, "sheetData"))
        assert sheet_data is not None
        for row in list(sheet_data):
            if int(row.attrib.get("r", "0")) > 1:
                sheet_data.remove(row)
        changed_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(destination, "w") as output_zip:
            output_zip.comment = source_zip.comment
            for item in source_zip.infolist():
                content = (
                    changed_xml
                    if item.filename == sheet.path
                    else source_zip.read(item.filename)
                )
                output_zip.writestr(copy(item), content)
    populated = destination.with_name(f"{destination.stem}-populated.xlsx")
    copy_xlsx_with_extra_cells(
        destination,
        populated,
        {
            "A2": "2026-08-03",
            "C2": "Day One",
            "D2": "Tempo Back Squat",
            "F2": "Standard Set",
            "G2": "200",
            "H2": "8",
            "C3": "Day Two",
            "D3": "Day Two Exercise",
            "F3": "Standard Set",
            "G3": "50",
            "H3": "10",
        },
    )
    destination.unlink()
    populated.rename(destination)


def copy_with_markup_compatibility_styles(source: Path, destination: Path) -> None:
    declarations = (
        b' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
        b' xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac"'
        b' mc:Ignorable="x14ac"'
    )
    with (
        zipfile.ZipFile(source, "r") as source_zip,
        zipfile.ZipFile(destination, "w") as output_zip,
    ):
        output_zip.comment = source_zip.comment
        for item in source_zip.infolist():
            content = source_zip.read(item.filename)
            if item.filename == "xl/styles.xml":
                declaration_end = content.find(b"?>")
                root_start = content.find(b"<", declaration_end + 2)
                root_name_end = content.find(b" ", root_start)
                content = (
                    content[:root_name_end]
                    + declarations
                    + content[root_name_end:]
                )
            output_zip.writestr(copy(item), content)


def copy_coach_with_second_day(
    source: Path, destination: Path, *, occupied_value: str | None = None
) -> None:
    package = XlsxPackage(source)
    sheet = package.sheet_by_name("Training Block")
    snapshot = package.sheet_snapshot(sheet)
    styles = {
        "B15": snapshot.cells["B3"].style,
        "C15": snapshot.cells["C3"].style,
        "D15": snapshot.cells["D3"].style,
        "D16": snapshot.cells["D5"].style,
        "J16": snapshot.cells["J5"].style,
    }
    with zipfile.ZipFile(source, "r") as source_zip:
        root = ET.fromstring(source_zip.read(sheet.path))
        sheet_data = root.find(qn(MAIN_NS, "sheetData"))
        assert sheet_data is not None
        rows = {int(row.attrib["r"]): row for row in sheet_data.findall(qn(MAIN_NS, "row"))}

        def add_cell(reference: str, value: str | None) -> None:
            row_number, _ = split_cell_reference(reference)
            row = rows[row_number]
            cell = ET.Element(qn(MAIN_NS, "c"), {"r": reference})
            if styles[reference] is not None:
                cell.attrib["s"] = styles[reference]
            if value is not None:
                cell.attrib["t"] = "inlineStr"
                inline = ET.SubElement(cell, qn(MAIN_NS, "is"))
                ET.SubElement(inline, qn(MAIN_NS, "t")).text = value
            row.append(cell)
            row[:] = sorted(
                row,
                key=lambda element: split_cell_reference(element.attrib.get("r", "A1"))[1],
            )

        add_cell("B15", "Day 2")
        add_cell("C15", "Style")
        add_cell("D15", "Variation")
        add_cell("D16", "Day Two Exercise")
        add_cell("J16", occupied_value)
        changed_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(destination, "w") as output_zip:
            output_zip.comment = source_zip.comment
            for item in source_zip.infolist():
                content = changed_xml if item.filename == sheet.path else source_zip.read(item.filename)
                output_zip.writestr(copy(item), content)


def write_marker_config(destination: Path) -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    payload["exercises"].append(
        {
            "canonical": "Day Two Exercise",
            "source_aliases": ["Day Two Exercise"],
            "coach_aliases": ["Day Two Exercise"],
        }
    )
    destination.write_text(json.dumps(payload), encoding="utf-8")


def write_clean_log(destination: Path, *, include_day_two: bool = False, uncertain: bool = False) -> None:
    rows = [
        {
            "Date": "2026-08-03",
            "Workout": "Day One",
            "Exercise": "Tempo Back Squat",
            "Set Type": "Standard Set",
            "Weight (lbs)": "200",
            "Reps": "8",
        }
    ]
    if include_day_two:
        rows.append(
            {
                "Date": "2026-08-04",
                "Workout": "Day Two",
                "Exercise": "Day Two Exercise",
                "Set Type": "Standard Set",
                "Weight (lbs)": "50",
                "Reps": "10",
            }
        )
    if uncertain:
        rows.append(
            {
                "Date": "2026-08-04",
                "Workout": "Unknown Day",
                "Exercise": "Unknown Exercise",
                "Set Type": "Standard Set",
                "Weight (lbs)": "25",
                "Reps": "10",
            }
        )
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"],
        )
        writer.writeheader()
        writer.writerows(rows)


def cell_style_details(path: Path, sheet_name: str, reference: str) -> tuple[dict[str, str], bytes, str | None]:
    package = XlsxPackage(path)
    style_index = int(package.sheet_snapshot(sheet_name).cells[reference].style or "0")
    with zipfile.ZipFile(path) as archive:
        styles = ET.fromstring(archive.read("xl/styles.xml"))
    cell_xfs = styles.find(qn(MAIN_NS, "cellXfs"))
    fills = styles.find(qn(MAIN_NS, "fills"))
    assert cell_xfs is not None and fills is not None
    cell_xf = list(cell_xfs)[style_index]
    fill = list(fills)[int(cell_xf.attrib.get("fillId", "0"))]
    foreground = fill.find(f"{qn(MAIN_NS, 'patternFill')}/{qn(MAIN_NS, 'fgColor')}")
    color = foreground.attrib.get("rgb") if foreground is not None else None
    alignment = cell_xf.find(qn(MAIN_NS, "alignment"))
    return dict(cell_xf.attrib), ET.tostring(alignment) if alignment is not None else b"", color


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG)

    def preview(self):
        return build_preview(
            LOG,
            COACH,
            self.config,
            "Training Block",
            "Week 1",
            date(2026, 8, 3),
            date(2026, 8, 9),
        )

    def test_discovers_sheet_week_and_result_column_from_labels(self) -> None:
        sheets = discover_workbook(COACH, self.config)
        training = next(sheet for sheet in sheets if sheet.name == "Training Block")
        self.assertEqual(training.exercise_header_cell, "D3")
        self.assertEqual([(week.label, week.result_column) for week in training.weeks], [("Week 1", 10), ("Week 2", 12)])

    def test_preview_formats_proposals_and_reports_conservative_exceptions(self) -> None:
        report = self.preview()
        proposals = {proposal.cell: proposal.value for proposal in report.proposed_writes}
        self.assertEqual(proposals["J5"], "200 x 8, 7; 180 x 10")
        self.assertEqual(proposals["J6"], "0 x 10, 9")
        self.assertEqual(proposals["J7"], "160 x 10+3+2")
        self.assertEqual(proposals["J8"], "100 x 8→70 x 10")
        self.assertEqual(proposals["J9"], "50/60 x 10/12")
        self.assertEqual(proposals["J10"], "45s x 12")
        self.assertEqual(len(report.zero_rep_rows), 1)
        self.assertEqual(len(report.unmatched_exercises), 1)
        self.assertEqual(len(report.ambiguous_matches), 1)
        self.assertEqual(len(report.occupied_cells), 1)
        self.assertEqual(len(report.skipped_rows), 1)
        self.assertNotIn("skipped workout", json.dumps(report.to_dict()).lower())

    def test_apply_changes_only_target_sheet_and_keeps_source_unchanged(self) -> None:
        before_hash = file_sha256(COACH)
        export_before_hash = file_sha256(LOG)
        before = XlsxPackage(COACH).sheet_snapshot("Training Block")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "coach-output.xlsx"
            report = apply_changes(self.preview(), self.config, output)
            self.assertTrue(output.exists())
            self.assertEqual(file_sha256(COACH), before_hash)
            self.assertEqual(file_sha256(LOG), export_before_hash)
            self.assertEqual(report.source_hash_before, report.source_hash_after)
            self.assertEqual(report.export_hash_before, report.export_hash_after)
            self.assertEqual(report.validation["unrelated_members_changed"], [])
            self.assertTrue(report.validation["zip_members_identical"])

            after = XlsxPackage(output).sheet_snapshot("Training Block")
            self.assertEqual(after.cells["J5"].value, "200 x 8, 7; 180 x 10")
            self.assertEqual(after.cells["J5"].style, before.cells["J5"].style)
            self.assertEqual(after.cells["J13"].value, "existing result")
            self.assertEqual(after.cells["J14"].formula, before.cells["J14"].formula)
            self.assertEqual(after.cells["N5"].formula, before.cells["N5"].formula)
            self.assertEqual(after.merges, before.merges)

            source_package = XlsxPackage(COACH)
            with zipfile.ZipFile(COACH) as source_zip, zipfile.ZipFile(output) as output_zip:
                changed_path = source_package.sheet_by_name("Training Block").path
                differences = [
                    name
                    for name in source_zip.namelist()
                    if source_zip.read(name) != output_zip.read(name)
                ]
                self.assertEqual(differences, [changed_path])

    def test_apply_refuses_to_overwrite_an_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "already-there.xlsx"
            output.write_bytes(b"do not replace")
            with self.assertRaisesRegex(ValueError, "Output already exists"):
                apply_changes(self.preview(), self.config, output)
            self.assertEqual(output.read_bytes(), b"do not replace")

    def test_accepts_csv_and_xlsx_exports(self) -> None:
        xlsx_records = load_exercise_log(LOG)
        self.assertGreater(len(xlsx_records), 10)
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "export.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Date": "2026-08-03",
                        "Workout": "Example",
                        "Exercise": "Tempo Back Squat",
                        "Set Type": "Standard Set",
                        "Weight (lbs)": "200",
                        "Reps": "8",
                    }
                )
            csv_records = load_exercise_log(csv_path)
            self.assertEqual(len(csv_records), 1)
            self.assertEqual(csv_records[0].exercise, "Tempo Back Squat")

    def test_accepts_current_singular_pound_header_in_csv_and_xlsx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            csv_path = directory_path / "current-export.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Date", "Workout", "Exercise", "Set Type", "Weight (lb)", "Reps"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Date": "2026-08-03",
                        "Workout": "Example",
                        "Exercise": "Tempo Back Squat",
                        "Set Type": "Standard Set",
                        "Weight (lb)": "205",
                        "Reps": "7",
                    }
                )
            csv_records = load_exercise_log(csv_path)
            self.assertEqual(csv_records[0].weight, Decimal("205"))

            xlsx_path = directory_path / "current-export.xlsx"
            copy_xlsx_with_singular_weight_header(LOG, xlsx_path)
            xlsx_records = load_exercise_log(xlsx_path)
            self.assertGreater(len(xlsx_records), 10)
            self.assertEqual(xlsx_records[0].weight, load_exercise_log(LOG)[0].weight)

    def test_rejects_duplicate_canonical_weight_headers_in_csv_and_xlsx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "duplicate.csv"
            csv_path.write_text(
                "Date,Workout,Exercise,Set Type,Weight (lb),Weight (lbs),Reps\n"
                "2026-08-03,Example,Tempo Back Squat,Standard Set,205,999,7\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ImportError, "duplicate logical columns: Weight"):
                load_exercise_log(csv_path)

            xlsx_path = root / "duplicate.xlsx"
            copy_xlsx_with_extra_cells(LOG, xlsx_path, {"I1": "Weight (lb)"})
            with self.assertRaisesRegex(ImportError, "duplicate logical columns: Weight"):
                load_exercise_log(xlsx_path)

    def test_empty_day_marker_is_proposed_and_highlighted_yellow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coach = root / "two-days.xlsx"
            log = root / "clean.csv"
            config_path = root / "config.json"
            output = root / "output.xlsx"
            copy_coach_with_second_day(COACH, coach)
            write_clean_log(log)
            write_marker_config(config_path)
            config = load_config(config_path)
            report = build_preview(
                log, coach, config, "Training Block", "Week 1", date(2026, 8, 3), date(2026, 8, 9)
            )
            marker = next(proposal for proposal in report.proposed_writes if proposal.kind == "empty_day_marker")
            self.assertEqual((marker.cell, marker.value, marker.fill_color), ("J16", "Skip", "FFFFFF00"))
            self.assertEqual(report.empty_day_markers[0]["day"], "Day 2")

            before_hash = file_sha256(coach)
            result = apply_changes(report, config, output)
            self.assertEqual(file_sha256(coach), before_hash)
            self.assertEqual(XlsxPackage(output).sheet_snapshot("Training Block").cells["J16"].value, "Skip")
            before_style, before_alignment, _ = cell_style_details(coach, "Training Block", "J16")
            after_style, after_alignment, fill_color = cell_style_details(output, "Training Block", "J16")
            for attribute in ("fontId", "borderId", "numFmtId", "xfId"):
                self.assertEqual(after_style.get(attribute), before_style.get(attribute))
            self.assertEqual(after_alignment, before_alignment)
            self.assertEqual(fill_color, "FFFFFF00")
            self.assertEqual(
                result.validation["changed_members"],
                ["xl/styles.xml", "xl/worksheets/sheet1.xml"],
            )
            self.assertEqual(result.validation["unrelated_members_changed"], [])

    def test_highlighted_output_preserves_markup_compatibility_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coach = root / "two-days.xlsx"
            extended_coach = root / "extended-two-days.xlsx"
            log = root / "clean.csv"
            config_path = root / "config.json"
            output = root / "output.xlsx"
            copy_coach_with_second_day(COACH, coach)
            copy_with_markup_compatibility_styles(coach, extended_coach)
            write_clean_log(log)
            write_marker_config(config_path)
            config = load_config(config_path)
            report = build_preview(
                log,
                extended_coach,
                config,
                "Training Block",
                "Week 1",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )
            apply_changes(report, config, output)

            with zipfile.ZipFile(output) as archive:
                styles = archive.read("xl/styles.xml")
            self.assertIn(b"xmlns:mc=", styles)
            self.assertIn(b"xmlns:x14ac=", styles)
            self.assertIn(b'mc:Ignorable="x14ac"', styles)
            root_element = ET.fromstring(styles)
            compatibility_ns = (
                "http://schemas.openxmlformats.org/markup-compatibility/2006"
            )
            self.assertEqual(
                root_element.attrib[qn(compatibility_ns, "Ignorable")], "x14ac"
            )

    def test_empty_day_marker_is_not_added_for_present_occupied_or_uncertain_days(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            write_marker_config(config_path)
            config = load_config(config_path)
            cases = (
                ("present", True, False, None),
                ("occupied", False, False, "Reviewed"),
                ("uncertain", False, True, None),
            )
            for name, include_day_two, uncertain, occupied in cases:
                with self.subTest(name=name):
                    coach = root / f"{name}.xlsx"
                    log = root / f"{name}.csv"
                    copy_coach_with_second_day(COACH, coach, occupied_value=occupied)
                    write_clean_log(log, include_day_two=include_day_two, uncertain=uncertain)
                    report = build_preview(
                        log,
                        coach,
                        config,
                        "Training Block",
                        "Week 1",
                        date(2026, 8, 3),
                        date(2026, 8, 9),
                    )
                    self.assertFalse(
                        any(proposal.kind == "empty_day_marker" for proposal in report.proposed_writes)
                    )

    def test_malformed_xlsx_rows_are_reported_and_withhold_empty_day_markers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coach = root / "two-days.xlsx"
            log = root / "malformed.xlsx"
            config_path = root / "config.json"
            copy_coach_with_second_day(COACH, coach)
            copy_minimal_log_xlsx(LOG, log)
            write_marker_config(config_path)
            imported = load_exercise_log_with_diagnostics(log)
            self.assertEqual(len(imported.records), 1)
            self.assertEqual(
                imported.skipped_rows,
                (
                    {
                        "row": 3,
                        "reason": "missing date in non-empty XLSX workout row",
                        "exercise": "Day Two Exercise",
                    },
                ),
            )
            report = build_preview(
                log,
                coach,
                load_config(config_path),
                "Training Block",
                "Week 1",
                date(2026, 8, 3),
                date(2026, 8, 9),
            )
            self.assertEqual(report.skipped_rows, list(imported.skipped_rows))
            self.assertFalse(
                any(
                    proposal.kind == "empty_day_marker"
                    for proposal in report.proposed_writes
                )
            )

    def test_empty_day_marker_configuration_is_validated(self) -> None:
        marker = self.config.empty_day_marker
        self.assertIsNotNone(marker)
        assert marker is not None
        self.assertEqual((marker.text, marker.fill_color), ("Skip", "FFFFFF00"))
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "invalid.json"
            payload = json.loads(CONFIG.read_text(encoding="utf-8"))
            payload["workbook"]["empty_day_marker"]["fill_color"] = "yellow"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "hex color"):
                load_config(config_path)

    def test_cli_writes_machine_readable_preview_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "preview.json"
            exit_code = main(
                [
                    "preview",
                    "--export",
                    str(LOG),
                    "--workbook",
                    str(COACH),
                    "--config",
                    str(CONFIG),
                    "--sheet",
                    "Training Block",
                    "--week",
                    "Week 1",
                    "--from-date",
                    "2026-08-03",
                    "--to-date",
                    "2026-08-09",
                    "--report",
                    str(report_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["sheet"], "Training Block")
            self.assertEqual(len(payload["proposed_writes"]), 6)


if __name__ == "__main__":
    unittest.main()
