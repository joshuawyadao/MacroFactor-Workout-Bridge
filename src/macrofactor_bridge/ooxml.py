from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import CellData, SheetRef


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", REL_NS)


class WorkbookError(ValueError):
    """Raised when an XLSX workbook cannot be safely understood or updated."""


@dataclass(frozen=True)
class SheetSnapshot:
    cells: dict[str, CellData]
    merges: tuple[str, ...]
    xml: bytes


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_to_number(column: str) -> int:
    result = 0
    for char in column.upper():
        if not "A" <= char <= "Z":
            raise WorkbookError(f"Invalid column: {column!r}")
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def number_to_column(number: int) -> str:
    if number < 1:
        raise WorkbookError(f"Invalid column number: {number}")
    chars: list[str] = []
    while number:
        number, remainder = divmod(number - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def split_cell_reference(reference: str) -> tuple[int, int]:
    match = re.fullmatch(r"\$?([A-Za-z]+)\$?(\d+)", reference)
    if not match:
        raise WorkbookError(f"Invalid cell reference: {reference!r}")
    return int(match.group(2)), column_to_number(match.group(1))


def make_cell_reference(row: int, column: int) -> str:
    return f"{number_to_column(column)}{row}"


def split_range(reference: str) -> tuple[int, int, int, int]:
    start, _, end = reference.partition(":")
    if not end:
        end = start
    start_row, start_col = split_cell_reference(start)
    end_row, end_col = split_cell_reference(end)
    return start_row, start_col, end_row, end_col


class XlsxPackage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if self.path.suffix.lower() != ".xlsx":
            raise WorkbookError("Only .xlsx workbooks are supported")
        if not self.path.is_file():
            raise WorkbookError(f"Workbook does not exist: {self.path}")
        try:
            with zipfile.ZipFile(self.path) as archive:
                self._names = set(archive.namelist())
                self._shared_strings = self._read_shared_strings(archive)
                self._sheets = self._read_sheet_refs(archive)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            raise WorkbookError(f"Invalid or unsupported XLSX workbook {self.path}: {exc}") from exc

    @property
    def sheets(self) -> tuple[SheetRef, ...]:
        return self._sheets

    @staticmethod
    def _read_shared_strings(archive: zipfile.ZipFile) -> tuple[str, ...]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return ()
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        values: list[str] = []
        for item in root.findall(qn(MAIN_NS, "si")):
            values.append("".join(node.text or "" for node in item.iter(qn(MAIN_NS, "t"))))
        return tuple(values)

    @staticmethod
    def _read_sheet_refs(archive: zipfile.ZipFile) -> tuple[SheetRef, ...]:
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall(qn(PACKAGE_REL_NS, "Relationship"))
        }
        sheets: list[SheetRef] = []
        sheets_node = workbook_root.find(qn(MAIN_NS, "sheets"))
        if sheets_node is None:
            raise WorkbookError("Workbook has no sheets collection")
        for sheet in sheets_node.findall(qn(MAIN_NS, "sheet")):
            rel_id = sheet.attrib.get(qn(REL_NS, "id"))
            if not rel_id or rel_id not in relationships:
                raise WorkbookError(f"Worksheet relationship is missing for {sheet.attrib.get('name')!r}")
            target = relationships[rel_id].lstrip("/")
            path = target if target.startswith("xl/") else posixpath.normpath(posixpath.join("xl", target))
            sheets.append(SheetRef(name=sheet.attrib["name"], path=path))
        return tuple(sheets)

    def sheet_by_name(self, name: str) -> SheetRef:
        matches = [sheet for sheet in self.sheets if sheet.name == name]
        if not matches:
            raise WorkbookError(f"Worksheet not found: {name!r}")
        return matches[0]

    def sheet_snapshot(self, sheet: SheetRef | str) -> SheetSnapshot:
        selected = self.sheet_by_name(sheet) if isinstance(sheet, str) else sheet
        with zipfile.ZipFile(self.path) as archive:
            xml = archive.read(selected.path)
        root = ET.fromstring(xml)
        cells: dict[str, CellData] = {}
        for element in root.iter(qn(MAIN_NS, "c")):
            reference = element.attrib.get("r")
            if not reference:
                continue
            cell_type = element.attrib.get("t")
            formula_node = element.find(qn(MAIN_NS, "f"))
            formula = formula_node.text if formula_node is not None else None
            value: str | float | int | None = None
            if cell_type == "inlineStr":
                inline = element.find(qn(MAIN_NS, "is"))
                if inline is not None:
                    value = "".join(node.text or "" for node in inline.iter(qn(MAIN_NS, "t")))
            else:
                value_node = element.find(qn(MAIN_NS, "v"))
                if value_node is not None and value_node.text is not None:
                    raw = value_node.text
                    if cell_type == "s":
                        try:
                            value = self._shared_strings[int(raw)]
                        except (ValueError, IndexError) as exc:
                            raise WorkbookError(f"Invalid shared string index in {reference}") from exc
                    elif cell_type in {"str", "e"}:
                        value = raw
                    elif cell_type == "b":
                        value = 1 if raw == "1" else 0
                    else:
                        try:
                            numeric = float(raw)
                            value = int(numeric) if numeric.is_integer() else numeric
                        except ValueError:
                            value = raw
            cells[reference] = CellData(
                reference=reference,
                value=value,
                formula=formula,
                style=element.attrib.get("s"),
                cell_type=cell_type,
            )
        merge_node = root.find(qn(MAIN_NS, "mergeCells"))
        merges = tuple(
            node.attrib["ref"]
            for node in merge_node.findall(qn(MAIN_NS, "mergeCell"))
        ) if merge_node is not None else ()
        return SheetSnapshot(cells=cells, merges=merges, xml=xml)

    def write_copy(
        self,
        output_path: str | Path,
        sheet: SheetRef,
        changes: dict[str, str],
    ) -> None:
        output = Path(output_path)
        if output.resolve() == self.path.resolve():
            raise WorkbookError("Output path must be different from the source workbook")
        if output.suffix.lower() != ".xlsx":
            raise WorkbookError("Output path must end in .xlsx")
        if output.exists():
            raise WorkbookError(f"Output already exists; choose a new path: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.path, "r") as source:
            original_xml = source.read(sheet.path)
            changed_xml = self._updated_sheet_xml(original_xml, changes)
            with zipfile.ZipFile(output, "w") as destination:
                destination.comment = source.comment
                for info in source.infolist():
                    data = changed_xml if info.filename == sheet.path else source.read(info.filename)
                    destination.writestr(copy(info), data)

    @staticmethod
    def _updated_sheet_xml(xml: bytes, changes: dict[str, str]) -> bytes:
        root = ET.fromstring(xml)
        sheet_data = root.find(qn(MAIN_NS, "sheetData"))
        if sheet_data is None:
            raise WorkbookError("Worksheet has no sheetData")
        cell_elements = {
            cell.attrib.get("r"): cell
            for cell in root.iter(qn(MAIN_NS, "c"))
            if cell.attrib.get("r")
        }
        for reference, value in changes.items():
            cell = cell_elements.get(reference)
            if cell is None:
                raise WorkbookError(
                    f"Target cell {reference} does not exist; refusing to create an unstyled cell"
                )
            formula = cell.find(qn(MAIN_NS, "f"))
            existing_value = cell.find(qn(MAIN_NS, "v"))
            inline = cell.find(qn(MAIN_NS, "is"))
            if (
                formula is not None
                or (existing_value is not None and existing_value.text not in (None, ""))
                or inline is not None
            ):
                raise WorkbookError(f"Target cell {reference} is no longer empty")
            if existing_value is not None:
                cell.remove(existing_value)
            cell.attrib["t"] = "inlineStr"
            inline = ET.SubElement(cell, qn(MAIN_NS, "is"))
            text = ET.SubElement(inline, qn(MAIN_NS, "t"))
            if value != value.strip():
                text.attrib[qn(XML_NS, "space")] = "preserve"
            text.text = value
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_copy_integrity(
    source_path: str | Path,
    output_path: str | Path,
    changed_member: str,
) -> dict[str, object]:
    source = Path(source_path)
    output = Path(output_path)
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        before_names = before.namelist()
        after_names = after.namelist()
        unchanged_differences = [
            name
            for name in before_names
            if name != changed_member and before.read(name) != after.read(name)
        ]
        return {
            "zip_members_identical": before_names == after_names,
            "changed_member": changed_member,
            "unrelated_members_changed": unchanged_differences,
            "source_size": source.stat().st_size,
            "output_size": output.stat().st_size,
        }
