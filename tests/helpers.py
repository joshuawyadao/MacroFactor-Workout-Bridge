from __future__ import annotations

import copy
import zipfile
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def rewrite_xlsx(
    source: str | Path,
    destination: str | Path,
    transforms: dict[str, Callable[[bytes], bytes]],
    *,
    extra_members: dict[str, bytes] | None = None,
) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    with zipfile.ZipFile(source_path, "r") as original:
        with zipfile.ZipFile(destination_path, "w") as rewritten:
            rewritten.comment = original.comment
            for info in original.infolist():
                data = original.read(info.filename)
                transform = transforms.get(info.filename)
                rewritten.writestr(copy.copy(info), transform(data) if transform else data)
            for name, data in (extra_members or {}).items():
                rewritten.writestr(name, data)
    return destination_path


def transform_cell(
    reference: str,
    *,
    text: str | None = None,
    cell_type: str = "str",
    remove: bool = False,
) -> Callable[[bytes], bytes]:
    def transform(xml: bytes) -> bytes:
        root = ET.fromstring(xml)
        for row in root.iter(qn(MAIN_NS, "row")):
            for cell in list(row.findall(qn(MAIN_NS, "c"))):
                if cell.attrib.get("r") != reference:
                    continue
                if remove:
                    row.remove(cell)
                else:
                    for child in list(cell):
                        cell.remove(child)
                    cell.attrib["t"] = cell_type
                    value = ET.SubElement(cell, qn(MAIN_NS, "v"))
                    value.text = text
                return ET.tostring(root, encoding="utf-8", xml_declaration=True)
        raise AssertionError(f"Cell {reference} was not found in worksheet XML")

    return transform


def duplicate_first_worksheet(source: str | Path, destination: str | Path) -> Path:
    source_path = Path(source)
    with zipfile.ZipFile(source_path) as archive:
        workbook_xml = archive.read("xl/workbook.xml")
        relationships_xml = archive.read("xl/_rels/workbook.xml.rels")
        first_sheet_xml = archive.read("xl/worksheets/sheet1.xml")

    def duplicate_workbook(xml: bytes) -> bytes:
        root = ET.fromstring(xml)
        sheets = root.find(qn(MAIN_NS, "sheets"))
        if sheets is None or not list(sheets):
            raise AssertionError("Fixture workbook has no worksheet to duplicate")
        duplicate = copy.deepcopy(list(sheets)[0])
        duplicate.attrib["name"] = "Workout Log Copy"
        duplicate.attrib["sheetId"] = "2"
        duplicate.attrib[qn(REL_NS, "id")] = "duplicate-sheet"
        sheets.append(duplicate)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def duplicate_relationship(xml: bytes) -> bytes:
        root = ET.fromstring(xml)
        relationship = ET.SubElement(root, qn(PACKAGE_REL_NS, "Relationship"))
        relationship.attrib.update(
            {
                "Id": "duplicate-sheet",
                "Type": (
                    "http://schemas.openxmlformats.org/officeDocument/2006/"
                    "relationships/worksheet"
                ),
                "Target": "/xl/worksheets/sheet2.xml",
            }
        )
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    return rewrite_xlsx(
        source_path,
        destination,
        {
            "xl/workbook.xml": duplicate_workbook,
            "xl/_rels/workbook.xml.rels": duplicate_relationship,
        },
        extra_members={"xl/worksheets/sheet2.xml": first_sheet_xml},
    )
