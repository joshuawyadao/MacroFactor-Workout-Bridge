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
