from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS, make_cell_reference, split_cell_reference


CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_program_workbook(
    path: Path,
    *,
    sheet_name: str,
    cells: dict[str, object | None],
    merges: tuple[str, ...] = (),
) -> None:
    worksheet = ET.Element(f"{{{MAIN_NS}}}worksheet")
    sheet_data = ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetData")
    by_row: dict[int, list[tuple[str, object | None]]] = {}
    for reference, value in cells.items():
        row, _ = split_cell_reference(reference)
        by_row.setdefault(row, []).append((reference, value))
    for row_number, entries in sorted(by_row.items()):
        row = ET.SubElement(sheet_data, f"{{{MAIN_NS}}}row", {"r": str(row_number)})
        for reference, value in sorted(entries, key=lambda item: split_cell_reference(item[0])[1]):
            cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", {"r": reference, "s": "0"})
            if value is None:
                continue
            if isinstance(value, (int, float)):
                ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = str(value)
            else:
                cell.attrib["t"] = "inlineStr"
                inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
                ET.SubElement(inline, f"{{{MAIN_NS}}}t").text = str(value)
    if merges:
        merge_cells = ET.SubElement(
            worksheet, f"{{{MAIN_NS}}}mergeCells", {"count": str(len(merges))}
        )
        for reference in merges:
            ET.SubElement(
                merge_cells, f"{{{MAIN_NS}}}mergeCell", {"ref": reference}
            )

    workbook = ET.Element(f"{{{MAIN_NS}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{MAIN_NS}}}sheet",
        {
            "name": sheet_name,
            "sheetId": "1",
            f"{{{OFFICE_REL_NS}}}id": "rId1",
        },
    )

    workbook_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
    ET.SubElement(
        workbook_rels,
        f"{{{PACKAGE_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{OFFICE_REL_NS}/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    package_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
    ET.SubElement(
        package_rels,
        f"{{{PACKAGE_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{OFFICE_REL_NS}/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    content_types = ET.Element(f"{{{CONTENT_NS}}}Types")
    ET.SubElement(
        content_types,
        f"{{{CONTENT_NS}}}Default",
        {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
    )
    ET.SubElement(
        content_types,
        f"{{{CONTENT_NS}}}Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    ET.SubElement(
        content_types,
        f"{{{CONTENT_NS}}}Override",
        {
            "PartName": "/xl/workbook.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        },
    )
    ET.SubElement(
        content_types,
        f"{{{CONTENT_NS}}}Override",
        {
            "PartName": "/xl/worksheets/sheet1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", _xml(content_types))
        archive.writestr("_rels/.rels", _xml(package_rels))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(workbook_rels))
        archive.writestr("xl/worksheets/sheet1.xml", _xml(worksheet))


def add_day_header(
    cells: dict[str, object | None],
    *,
    row: int,
    day: str,
    week_one: str = "Week 1",
    week_two: str = "Week 2",
) -> None:
    values = {
        3: day,
        4: "Style",
        5: "Variation",
        6: "Sets",
        7: "Reps",
        8: "Rest",
        10: week_one,
        12: week_two,
    }
    for column, value in values.items():
        cells[make_cell_reference(row, column)] = value


def write_macrofactor_program_template(
    path: Path,
    *,
    day_row_counts: tuple[int, ...] = (2,),
    max_sets: int = 4,
    set_types: tuple[str, ...] = (),
) -> None:
    if not day_row_counts or any(count < 1 for count in day_row_counts):
        raise ValueError("day_row_counts must contain positive values")
    if max_sets < 1:
        raise ValueError("max_sets must be positive")
    if len(set_types) > max_sets:
        raise ValueError("set_types exceeds fixture capacity")

    shared_values: list[str] = []
    shared_indexes: dict[str, int] = {}
    shared_uses = 0

    def string_index(value: str) -> int:
        nonlocal shared_uses
        shared_uses += 1
        if value not in shared_indexes:
            shared_indexes[value] = len(shared_values)
            shared_values.append(value)
        return shared_indexes[value]

    worksheet = ET.Element(f"{{{MAIN_NS}}}worksheet")
    ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetPr")
    views = ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetViews")
    ET.SubElement(views, f"{{{MAIN_NS}}}sheetView", {"workbookViewId": "0"})
    ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetFormatPr", {"defaultRowHeight": "15"})
    sheet_data = ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetData")
    column_count = 4 + max_sets * 4

    row_values: dict[int, dict[int, str | int | None]] = {
        1: {
            1: "Program: Synthetic Template",
            2: "Cycles: 3",
            3: "Deload: None",
            4: "Color: Blue",
            5: "Icon: Circle",
        },
        2: {1: "Block 1"},
        3: {1: "Cycle 1", 2: "Exercise", 3: "Skipped", 4: "Notes"},
    }
    for set_number in range(1, max_sets + 1):
        first_column = 5 + (set_number - 1) * 4
        row_values[3].update(
            {
                first_column: f"Set {set_number} Type",
                first_column + 1: f"Set {set_number} Rep Range",
                first_column + 2: f"Set {set_number} RIR",
                first_column + 3: f"Set {set_number} Rest",
            }
        )

    merges: list[str] = []
    row_number = 4
    for day_number, row_count in enumerate(day_row_counts, start=1):
        start_row = row_number
        for exercise_number in range(1, row_count + 1):
            row_values[row_number] = {
                1: f"Old Day {day_number}" if exercise_number == 1 else None,
                2: f"Old Exercise {day_number}-{exercise_number}",
                3: "No",
                4: f"Old Note {day_number}-{exercise_number}",
                5: "Standard Set",
                6: "8 - 12",
                7: 2,
                8: 90,
            }
            if set_types:
                # Minimal mixed-type values proved by a direct program export;
                # all names/metadata and package parts remain synthetic.
                for number, kind in enumerate(set_types):
                    column = 5 + number * 4
                    row_values[row_number].update({column: kind, column + 1: None,
                                                  column + 2: None, column + 3: None})
            row_number += 1
        merges.append(f"A{start_row}:A{row_number - 1}")

    for current_row in range(1, row_number):
        row = ET.SubElement(sheet_data, f"{{{MAIN_NS}}}row", {"r": str(current_row)})
        for column in range(1, column_count + 1):
            reference = make_cell_reference(current_row, column)
            cell = ET.SubElement(
                row,
                f"{{{MAIN_NS}}}c",
                {"r": reference, "s": "0"},
            )
            value = row_values.get(current_row, {}).get(column)
            if value is None:
                continue
            value_node = ET.SubElement(cell, f"{{{MAIN_NS}}}v")
            if isinstance(value, str):
                cell.attrib["t"] = "s"
                value_node.text = str(string_index(value))
            else:
                cell.attrib["t"] = "n"
                value_node.text = str(value)
    merge_cells = ET.SubElement(
        worksheet,
        f"{{{MAIN_NS}}}mergeCells",
        {"count": str(len(merges))},
    )
    for reference in merges:
        ET.SubElement(merge_cells, f"{{{MAIN_NS}}}mergeCell", {"ref": reference})

    shared_strings = ET.Element(
        f"{{{MAIN_NS}}}sst",
        {"count": str(shared_uses), "uniqueCount": str(len(shared_values))},
    )
    for value in shared_values:
        item = ET.SubElement(shared_strings, f"{{{MAIN_NS}}}si")
        ET.SubElement(item, f"{{{MAIN_NS}}}t").text = value

    workbook = ET.Element(f"{{{MAIN_NS}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{MAIN_NS}}}sheet",
        {
            "name": "Training Programs",
            "sheetId": "1",
            f"{{{OFFICE_REL_NS}}}id": "rId1",
        },
    )
    workbook_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
    for rel_id, rel_type, target in (
        ("rId1", "worksheet", "worksheets/sheet1.xml"),
        ("rId2", "styles", "styles.xml"),
        ("rId3", "sharedStrings", "sharedStrings.xml"),
    ):
        ET.SubElement(
            workbook_rels,
            f"{{{PACKAGE_REL_NS}}}Relationship",
            {
                "Id": rel_id,
                "Type": f"{OFFICE_REL_NS}/{rel_type}",
                "Target": target,
            },
        )
    package_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
    ET.SubElement(
        package_rels,
        f"{{{PACKAGE_REL_NS}}}Relationship",
        {
            "Id": "rId1",
            "Type": f"{OFFICE_REL_NS}/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    sheet_rels = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")

    styles = ET.Element(f"{{{MAIN_NS}}}styleSheet")
    fonts = ET.SubElement(styles, f"{{{MAIN_NS}}}fonts", {"count": "1"})
    ET.SubElement(fonts, f"{{{MAIN_NS}}}font")
    fills = ET.SubElement(styles, f"{{{MAIN_NS}}}fills", {"count": "2"})
    for pattern in ("none", "gray125"):
        fill = ET.SubElement(fills, f"{{{MAIN_NS}}}fill")
        ET.SubElement(fill, f"{{{MAIN_NS}}}patternFill", {"patternType": pattern})
    borders = ET.SubElement(styles, f"{{{MAIN_NS}}}borders", {"count": "1"})
    ET.SubElement(borders, f"{{{MAIN_NS}}}border")
    style_xfs = ET.SubElement(styles, f"{{{MAIN_NS}}}cellStyleXfs", {"count": "1"})
    ET.SubElement(
        style_xfs,
        f"{{{MAIN_NS}}}xf",
        {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"},
    )
    cell_xfs = ET.SubElement(styles, f"{{{MAIN_NS}}}cellXfs", {"count": "1"})
    ET.SubElement(
        cell_xfs,
        f"{{{MAIN_NS}}}xf",
        {
            "numFmtId": "0",
            "fontId": "0",
            "fillId": "0",
            "borderId": "0",
            "xfId": "0",
        },
    )

    content_types = ET.Element(f"{{{CONTENT_NS}}}Types")
    for extension, content_type in (
        ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
        ("xml", "application/xml"),
    ):
        ET.SubElement(
            content_types,
            f"{{{CONTENT_NS}}}Default",
            {"Extension": extension, "ContentType": content_type},
        )
    for part_name, content_type in (
        (
            "/xl/workbook.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        ),
        (
            "/xl/worksheets/sheet1.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        ),
        (
            "/xl/styles.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
        ),
        (
            "/xl/sharedStrings.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml",
        ),
    ):
        ET.SubElement(
            content_types,
            f"{{{CONTENT_NS}}}Override",
            {"PartName": part_name, "ContentType": content_type},
        )

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", _xml(content_types))
        archive.writestr("_rels/.rels", _xml(package_rels))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(workbook_rels))
        archive.writestr("xl/worksheets/sheet1.xml", _xml(worksheet))
        archive.writestr("xl/worksheets/_rels/sheet1.xml.rels", _xml(sheet_rels))
        archive.writestr("xl/sharedStrings.xml", _xml(shared_strings))
        archive.writestr("xl/styles.xml", _xml(styles))
