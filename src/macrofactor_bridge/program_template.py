from __future__ import annotations

import os
import posixpath
import re
import tempfile
import zipfile
from collections import Counter
from copy import copy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from xml.dom import Node, minidom
from xml.etree import ElementTree as ET

from .config import normalize_name
from .ooxml import (
    MAIN_NS,
    PACKAGE_REL_NS,
    REL_NS,
    WorkbookError,
    XlsxPackage,
    make_cell_reference,
    qn,
    split_cell_reference,
    split_range,
    validate_copy_integrity,
)
from .program_models import CyclePrescription, Program, ProgramIssue


@dataclass(frozen=True)
class ProgramTemplateSetColumns:
    number: int
    set_type: int
    rep_range: int
    rir: int
    rest: int


@dataclass(frozen=True)
class ProgramTemplateDay:
    label_cell: str
    rows: tuple[int, ...]


@dataclass(frozen=True)
class ProgramTemplateSchema:
    sheet_name: str
    sheet_path: str
    program_cell: str
    cycles_cell: str
    block_cell: str
    cycle_cell: str
    header_row: int
    day_column: int
    exercise_column: int
    skipped_column: int
    notes_column: int
    sets: tuple[ProgramTemplateSetColumns, ...]
    days: tuple[ProgramTemplateDay, ...]


_SET_HEADER = re.compile(r"set\s+(\d+)\s+(type|rep\s+range|rir|rest)", re.IGNORECASE)
_CYCLE_HEADER = re.compile(r"cycle\s+(\d+)", re.IGNORECASE)
_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def _workbook_relationship_target(target: str) -> str:
    normalized = target.lstrip("/")
    if normalized.startswith("xl/"):
        return posixpath.normpath(normalized)
    return posixpath.normpath(posixpath.join("xl", normalized))


def _validate_template_package(
    template: Path,
    sheet_path: str,
) -> None:
    try:
        with zipfile.ZipFile(template) as archive:
            required = {
                "[Content_Types].xml",
                "xl/_rels/workbook.xml.rels",
                sheet_path,
                "xl/sharedStrings.xml",
                "xl/styles.xml",
            }
            missing = sorted(required.difference(archive.namelist()))
            if missing:
                raise WorkbookError(
                    "Program template is missing required OOXML part(s): "
                    + ", ".join(missing)
                )
            relationships = ET.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
            content_types = ET.fromstring(archive.read("[Content_Types].xml"))
            worksheet = ET.fromstring(archive.read(sheet_path))
            styles = ET.fromstring(archive.read("xl/styles.xml"))
            shared_strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise WorkbookError(f"Invalid program template OOXML package: {exc}") from exc

    expected_relationships = {
        f"{REL_NS}/worksheet": sheet_path,
        f"{REL_NS}/styles": "xl/styles.xml",
        f"{REL_NS}/sharedStrings": "xl/sharedStrings.xml",
    }
    for relationship_type, expected_target in expected_relationships.items():
        targets = [
            _workbook_relationship_target(relationship.attrib.get("Target", ""))
            for relationship in relationships.findall(
                qn(PACKAGE_REL_NS, "Relationship")
            )
            if relationship.attrib.get("Type") == relationship_type
        ]
        if targets.count(expected_target) != 1 or len(targets) != 1:
            label = relationship_type.rsplit("/", 1)[-1]
            raise WorkbookError(
                f"Program template needs one valid workbook {label} relationship"
            )

    expected_content_types = {
        f"/{sheet_path}": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
        ),
        "/xl/styles.xml": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"
        ),
        "/xl/sharedStrings.xml": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"
        ),
    }
    overrides = {
        override.attrib.get("PartName"): override.attrib.get("ContentType")
        for override in content_types.findall(
            qn(_CONTENT_TYPES_NS, "Override")
        )
    }
    if any(overrides.get(part) != kind for part, kind in expected_content_types.items()):
        raise WorkbookError("Program template has invalid required content-type declarations")

    if styles.tag != qn(MAIN_NS, "styleSheet"):
        raise WorkbookError("Program template styles part is not a SpreadsheetML stylesheet")
    cell_xfs = styles.find(qn(MAIN_NS, "cellXfs"))
    if cell_xfs is None:
        raise WorkbookError("Program template styles part has no cell formats")
    formats = cell_xfs.findall(qn(MAIN_NS, "xf"))
    try:
        declared_count = int(cell_xfs.attrib.get("count", ""))
    except ValueError as exc:
        raise WorkbookError("Program template cell-format count is invalid") from exc
    if not formats or declared_count != len(formats):
        raise WorkbookError("Program template cell-format declarations are inconsistent")
    style_references = [
        (cell.attrib.get("r", "unknown cell"), cell.attrib["s"])
        for cell in worksheet.iter(qn(MAIN_NS, "c"))
        if "s" in cell.attrib
    ]
    style_references.extend(
        (f"row {row.attrib.get('r', 'unknown')}", row.attrib["s"])
        for row in worksheet.iter(qn(MAIN_NS, "row"))
        if "s" in row.attrib
    )
    style_references.extend(
        (
            f"columns {column.attrib.get('min', '?')}-{column.attrib.get('max', '?')}",
            column.attrib["style"],
        )
        for column in worksheet.iter(qn(MAIN_NS, "col"))
        if "style" in column.attrib
    )
    for reference, raw_style_index in style_references:
        try:
            style_index = int(raw_style_index)
        except ValueError as exc:
            raise WorkbookError(
                f"Program template {reference} has an invalid style index"
            ) from exc
        if not 0 <= style_index < len(formats):
            raise WorkbookError(
                f"Program template {reference} references a missing style"
            )

    if shared_strings.tag != qn(MAIN_NS, "sst"):
        raise WorkbookError("Program template shared strings part is invalid")
    if any(child.tag != qn(MAIN_NS, "si") for child in shared_strings):
        raise WorkbookError(
            "Rich or extended shared strings are not supported by the safe generator"
        )
    for item in shared_strings.findall(qn(MAIN_NS, "si")):
        element_children = [
            child for child in item if isinstance(child.tag, str)
        ]
        if (
            len(element_children) != 1
            or element_children[0].tag != qn(MAIN_NS, "t")
        ):
            raise WorkbookError(
                "Rich or extended shared strings are not supported by the safe generator"
            )


def _raw(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_cell(
    cells: dict[str, object | None], predicate, description: str
) -> str:
    matches = [reference for reference, value in cells.items() if predicate(_raw(value))]
    if len(matches) != 1:
        raise WorkbookError(f"Program template needs exactly one {description}")
    return matches[0]


def inspect_program_template(path: str | Path) -> ProgramTemplateSchema:
    template = Path(path)
    package = XlsxPackage(template)
    if len(package.sheets) != 1:
        raise WorkbookError("Verified program templates must contain exactly one worksheet")
    sheet = package.sheets[0]
    _validate_template_package(template, sheet.path)
    snapshot = package.sheet_snapshot(sheet)
    if any(cell.formula is not None for cell in snapshot.cells.values()):
        raise WorkbookError("Program templates containing formulas are not supported")
    unsupported_strings = [
        reference
        for reference, cell in snapshot.cells.items()
        if isinstance(cell.value, str) and cell.cell_type != "s"
    ]
    if unsupported_strings:
        raise WorkbookError(
            "Program template string cells must use plain shared strings: "
            + ", ".join(unsupported_strings[:3])
        )

    values = {reference: cell.value for reference, cell in snapshot.cells.items()}
    by_row: dict[int, dict[int, object | None]] = {}
    for reference, value in values.items():
        row, column = split_cell_reference(reference)
        by_row.setdefault(row, {})[column] = value

    header_candidates: list[
        tuple[int, int, int, int, int, dict[int, dict[str, list[int]]]]
    ] = []
    for row, row_values in sorted(by_row.items()):
        exact_roles: dict[str, list[int]] = {"exercise": [], "skipped": [], "notes": []}
        cycle_columns: list[int] = []
        set_fields: dict[int, dict[str, list[int]]] = {}
        for column, value in row_values.items():
            text = _raw(value)
            normalized = normalize_name(text or "")
            if normalized in exact_roles:
                exact_roles[normalized].append(column)
            if text and _CYCLE_HEADER.fullmatch(text):
                cycle_columns.append(column)
            if text and (match := _SET_HEADER.fullmatch(text)):
                field = normalize_name(match.group(2)).replace(" ", "_")
                set_fields.setdefault(int(match.group(1)), {}).setdefault(
                    field, []
                ).append(column)
        if (
            all(len(columns) == 1 for columns in exact_roles.values())
            and len(cycle_columns) == 1
            and set_fields
        ):
            header_candidates.append(
                (
                    row,
                    cycle_columns[0],
                    exact_roles["exercise"][0],
                    exact_roles["skipped"][0],
                    exact_roles["notes"][0],
                    set_fields,
                )
            )
    if len(header_candidates) != 1:
        raise WorkbookError(
            "Only one distinct exported block/cycle table is currently supported"
        )
    (
        header_row,
        day_column,
        exercise_column,
        skipped_column,
        notes_column,
        set_fields,
    ) = header_candidates[0]
    set_numbers = sorted(set_fields)
    if set_numbers != list(range(1, len(set_numbers) + 1)):
        raise WorkbookError("Program template set groups must be contiguous from Set 1")
    required_fields = {"type", "rep_range", "rir", "rest"}
    if any(
        len(columns) != 1
        for fields in set_fields.values()
        for columns in fields.values()
    ):
        raise WorkbookError("Every template set header must occur exactly once")
    if any(set(fields) != required_fields for fields in set_fields.values()):
        raise WorkbookError("Every template set group needs Type, Rep Range, RIR, and Rest")
    sets = tuple(
        ProgramTemplateSetColumns(
            number=number,
            set_type=set_fields[number]["type"][0],
            rep_range=set_fields[number]["rep_range"][0],
            rir=set_fields[number]["rir"][0],
            rest=set_fields[number]["rest"][0],
        )
        for number in set_numbers
    )

    above_header = {
        reference: value
        for reference, value in values.items()
        if split_cell_reference(reference)[0] < header_row
    }
    program_cell = _unique_cell(
        above_header,
        lambda text: bool(text and re.fullmatch(r"program:\s*.+", text, re.IGNORECASE)),
        "Program metadata cell",
    )
    cycles_cell = _unique_cell(
        above_header,
        lambda text: bool(text and re.fullmatch(r"cycles:\s*[1-9]\d*", text, re.IGNORECASE)),
        "Cycles metadata cell",
    )
    block_cell = _unique_cell(
        above_header,
        lambda text: normalize_name(text or "") == "block 1",
        "Block 1 label",
    )
    cycle_cell = make_cell_reference(header_row, day_column)
    if normalize_name(_raw(values.get(cycle_cell)) or "") != "cycle 1":
        raise WorkbookError("The verified single-layout template must start with Cycle 1")

    exercise_rows = sorted(
        row
        for row, row_values in by_row.items()
        if row > header_row and _raw(row_values.get(exercise_column)) is not None
    )
    if not exercise_rows:
        raise WorkbookError("Program template contains no exercise rows")
    day_groups: list[ProgramTemplateDay] = []
    covered_rows: list[int] = []
    for merge in snapshot.merges:
        start_row, start_column, end_row, end_column = split_range(merge)
        if start_column != day_column or end_column != day_column or start_row <= header_row:
            continue
        label_cell = make_cell_reference(start_row, day_column)
        if _raw(values.get(label_cell)) is None:
            raise WorkbookError("Every merged workout group needs a label")
        rows = tuple(range(start_row, end_row + 1))
        day_groups.append(ProgramTemplateDay(label_cell=label_cell, rows=rows))
        covered_rows.extend(rows)
    day_groups.sort(key=lambda day: day.rows[0])
    if sorted(covered_rows) != exercise_rows or len(covered_rows) != len(set(covered_rows)):
        raise WorkbookError(
            "Exercise rows must be covered exactly once by merged workout groups"
        )

    target_columns = {
        exercise_column,
        skipped_column,
        notes_column,
        *(column for group in sets for column in (
            group.set_type,
            group.rep_range,
            group.rir,
            group.rest,
        )),
    }
    missing_cells = [
        make_cell_reference(row, column)
        for row in exercise_rows
        for column in target_columns
        if make_cell_reference(row, column) not in snapshot.cells
    ]
    if missing_cells:
        raise WorkbookError(
            "Program template omits target cells: " + ", ".join(missing_cells[:3])
        )

    return ProgramTemplateSchema(
        sheet_name=sheet.name,
        sheet_path=sheet.path,
        program_cell=program_cell,
        cycles_cell=cycles_cell,
        block_cell=block_cell,
        cycle_cell=cycle_cell,
        header_row=header_row,
        day_column=day_column,
        exercise_column=exercise_column,
        skipped_column=skipped_column,
        notes_column=notes_column,
        sets=sets,
        days=tuple(day_groups),
    )


def prepare_program_schema(
    template: Path,
    schema: ProgramTemplateSchema,
    program: Program,
    *,
    resize_workouts: bool = False,
) -> ProgramTemplateSchema:
    counts = [sum(not exercise.excluded for exercise in day.exercises) for day in program.days]
    if not resize_workouts or counts == [len(day.rows) for day in schema.days]:
        return schema
    if len(counts) != len(schema.days):
        raise WorkbookError("Workout resizing cannot add or remove template days")
    if any(count < 2 for count in counts) or any(len(day.rows) < 2 for day in schema.days):
        raise WorkbookError("Workout resizing currently requires at least two exercises per day")
    expected_rows = list(range(schema.header_row + 1, schema.days[-1].rows[-1] + 1))
    if [row for day in schema.days for row in day.rows] != expected_rows:
        raise WorkbookError("Workout resizing requires contiguous template exercise rows")
    with zipfile.ZipFile(template) as archive:
        root = ET.fromstring(archive.read(schema.sheet_path))
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    supported = {
        "sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols", "sheetData",
        "mergeCells", "pageMargins", "pageSetup", "printOptions", "headerFooter",
    }
    if any(
        child.tag not in {qn(MAIN_NS, tag) for tag in supported}
        and not (child.tag == qn(MAIN_NS, "extLst") and len(child) == 0)
        for child in root
    ):
        raise WorkbookError("Workout resizing cannot preserve this template's worksheet features")
    if any(True for _ in workbook.iter(qn(MAIN_NS, "definedName"))):
        raise WorkbookError("Workout resizing does not support defined names or print areas")
    if any(int(row.get("r", "0")) > expected_rows[-1] for row in root.iter(qn(MAIN_NS, "row"))):
        raise WorkbookError("Workout resizing cannot move trailing template rows")
    snapshot = XlsxPackage(template).sheet_snapshot(schema.sheet_name)
    valid_columns = {
        schema.day_column, schema.exercise_column, schema.skipped_column, schema.notes_column,
        *(column for group in schema.sets for column in (
            group.set_type, group.rep_range, group.rir, group.rest,
        )),
    }
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        if row > schema.header_row and column not in valid_columns and cell.value is not None:
            raise WorkbookError("Workout resizing cannot duplicate unknown exercise-row fields")
    expected_merges = {
        f"{day.label_cell}:{make_cell_reference(day.rows[-1], schema.day_column)}"
        for day in schema.days
    }
    for merge in snapshot.merges:
        if split_range(merge)[2] > schema.header_row and merge not in expected_merges:
            raise WorkbookError("Workout resizing cannot preserve non-workout body merges")
    next_row = schema.header_row + 1
    days = []
    for count in counts:
        rows = tuple(range(next_row, next_row + count))
        days.append(ProgramTemplateDay(make_cell_reference(next_row, schema.day_column), rows))
        next_row += count
    return replace(schema, days=tuple(days))


def _prescription_signature(prescription: CyclePrescription) -> tuple[object, ...]:
    return (
        prescription.set_count.value,
        prescription.set_type.value,
        prescription.rep_min.value,
        prescription.rep_max.value,
        prescription.rir.value,
        prescription.rest_seconds.value,
        prescription.notes,
    )


def template_generation_issues(
    program: Program, schema: ProgramTemplateSchema, *, sheet_name: str
) -> tuple[ProgramIssue, ...]:
    issues: list[ProgramIssue] = []

    def block(code: str, message: str, *, day: str | None = None, exercise: str | None = None) -> None:
        issues.append(
            ProgramIssue(
                severity="blocking",
                code=code,
                message=message,
                sheet=sheet_name,
                day=day,
                exercise=exercise,
            )
        )

    if not 1 <= len(program.cycles) <= 52:
        block("unsupported_cycle_count", "MacroFactor programs require 1 to 52 cycles")
    if not program.name.strip():
        block("missing_program_name", "Program name must not be empty")
    if len(program.days) != len(schema.days):
        block(
            "template_day_shape_mismatch",
            "Selected program day count does not match the verified template capacity",
        )
        return tuple(issues)

    for day, template_day in zip(program.days, schema.days, strict=True):
        exercises = [exercise for exercise in day.exercises if not exercise.excluded]
        if len(exercises) != len(template_day.rows):
            block(
                "template_exercise_shape_mismatch",
                "Included exercise count does not match this template workout group",
                day=day.label,
            )
        for exercise in exercises:
            if exercise.macrofactor_name is None or not exercise.macrofactor_available:
                block(
                    "unavailable_macrofactor_exercise",
                    "Every generated exercise needs an available exact MacroFactor name",
                    day=day.label,
                    exercise=exercise.coach_name,
                )
            if len(exercise.prescriptions) != len(program.cycles):
                block(
                    "missing_cycle_prescription",
                    "Exercise does not contain one prescription for every selected cycle",
                    day=day.label,
                    exercise=exercise.coach_name,
                )
                continue
            signatures = Counter(
                _prescription_signature(prescription)
                for prescription in exercise.prescriptions
            )
            if len(signatures) != 1:
                block(
                    "periodized_template_required",
                    "Selected cycles differ, but the verified export proves only one repeated cycle layout",
                    day=day.label,
                    exercise=exercise.coach_name,
                )
            for prescription in exercise.prescriptions:
                set_count = prescription.set_count.value
                set_type = prescription.set_type.value
                rep_min = prescription.rep_min.value
                rep_max = prescription.rep_max.value
                rir = prescription.rir.value
                rest_seconds = prescription.rest_seconds.value
                if type(set_count) is not int or not 1 <= set_count <= len(schema.sets):
                    block(
                        "template_set_capacity_exceeded",
                        f"Set count must fit the verified {len(schema.sets)}-set template capacity",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if set_type not in {"standard", "superset"}:
                    block(
                        "unsupported_template_set_type",
                        "The verified template proves only standard sets and explicit superset membership",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if set_type == "superset" and exercise.superset is None:
                    block(
                        "missing_superset_membership",
                        "Superset prescriptions require explicit configured membership",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if set_type == "standard" and exercise.superset is not None:
                    block(
                        "conflicting_superset_membership",
                        "Configured superset membership conflicts with a standard-set prescription",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if (
                    not (rep_min is None and rep_max is None
                         and prescription.rep_min.source == "blank_by_policy"
                         and prescription.rep_max.source == "blank_by_policy")
                    and (type(rep_min) is not int
                         or type(rep_max) is not int
                         or rep_min < 1
                         or rep_max < rep_min)
                ):
                    block(
                        "unsupported_template_rep_range",
                        "Rep targets require positive min/max values or an explicitly requested blank pair",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if not (rir is None and prescription.rir.source == "blank_by_policy") and (
                    type(rir) is not int or not 0 <= rir <= 6
                ):
                    block(
                        "unsupported_template_rir",
                        "RIR must be an integer from 0 through 6 or an explicitly requested blank",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
                if not (rest_seconds is None and prescription.rest_seconds.source == "blank_by_policy") and (
                    type(rest_seconds) is not int or rest_seconds < 1
                ):
                    block(
                        "unsupported_template_rest",
                        "Rest must be an exact positive duration in seconds",
                        day=day.label,
                        exercise=exercise.coach_name,
                    )
                    break
            if exercise.superset is not None and not re.fullmatch(
                r"SS[1-9]\d*", exercise.superset.group
            ):
                block(
                    "unsupported_superset_label",
                    "Template superset groups must use labels such as SS1 or SS2",
                    day=day.label,
                    exercise=exercise.coach_name,
                )
    return tuple(issues)


def _program_changes(
    program: Program, schema: ProgramTemplateSchema
) -> dict[str, str | int | None]:
    changes: dict[str, str | int | None] = {
        schema.program_cell: f"Program: {program.name}",
        schema.cycles_cell: f"Cycles: {len(program.cycles)}",
    }
    for day, template_day in zip(program.days, schema.days, strict=True):
        for row in template_day.rows:
            changes[make_cell_reference(row, schema.day_column)] = None
        changes[template_day.label_cell] = day.label
        exercises = [exercise for exercise in day.exercises if not exercise.excluded]
        for exercise, row in zip(exercises, template_day.rows, strict=True):
            prescription = exercise.prescriptions[0]
            exercise_name = exercise.macrofactor_name
            if exercise_name is None:
                raise WorkbookError("Cannot generate an unmapped exercise")
            if exercise.superset is not None:
                exercise_name = f"{exercise_name} ∈ {exercise.superset.group}"
            changes[make_cell_reference(row, schema.exercise_column)] = exercise_name
            changes[make_cell_reference(row, schema.skipped_column)] = "No"
            changes[make_cell_reference(row, schema.notes_column)] = (
                "\n".join(prescription.notes) if prescription.notes else None
            )
            set_count = prescription.set_count.value
            assert isinstance(set_count, int)
            for group in schema.sets:
                populated = group.number <= set_count
                changes[make_cell_reference(row, group.set_type)] = (
                    "Standard Set" if populated else None
                )
                changes[make_cell_reference(row, group.rep_range)] = (
                    f"{prescription.rep_min.value} - {prescription.rep_max.value}"
                    if populated and prescription.rep_min.value is not None
                    else None
                )
                changes[make_cell_reference(row, group.rir)] = (
                    prescription.rir.value if populated else None
                )
                changes[make_cell_reference(row, group.rest)] = (
                    prescription.rest_seconds.value if populated else None
                )
    return changes


def _dom_child(parent: minidom.Element, tag: str) -> minidom.Element | None:
    return next(
        (
            child
            for child in parent.childNodes
            if child.nodeType == Node.ELEMENT_NODE
            and child.namespaceURI == MAIN_NS
            and child.localName == tag
        ),
        None,
    )


def _append(parent: minidom.Element, tag: str) -> minidom.Element:
    qualified = f"{parent.prefix}:{tag}" if parent.prefix else tag
    child = parent.ownerDocument.createElementNS(MAIN_NS, qualified)
    parent.appendChild(child)
    return child


def _replace_cell_value(
    cell: minidom.Element,
    value: str | int | None,
    shared_indexes: dict[str, int],
    shared_values: list[str],
) -> None:
    for child in tuple(cell.childNodes):
        if (
            child.nodeType == Node.ELEMENT_NODE
            and child.namespaceURI == MAIN_NS
            and child.localName in {"f", "v", "is"}
        ):
            cell.removeChild(child)
    if value is None:
        if cell.hasAttribute("t"):
            cell.removeAttribute("t")
        return
    if isinstance(value, str):
        index = shared_indexes.get(value)
        if index is None:
            index = len(shared_values)
            shared_indexes[value] = index
            shared_values.append(value)
        cell.setAttribute("t", "s")
        _append(cell, "v").appendChild(cell.ownerDocument.createTextNode(str(index)))
        return
    cell.setAttribute("t", "n")
    _append(cell, "v").appendChild(cell.ownerDocument.createTextNode(str(value)))


def _rewrite_package_parts(
    template: Path,
    schema: ProgramTemplateSchema,
    changes: dict[str, str | int | None],
    source_schema: ProgramTemplateSchema | None = None,
) -> tuple[bytes, bytes]:
    package = XlsxPackage(template)
    snapshot = package.sheet_snapshot(schema.sheet_name)
    with zipfile.ZipFile(template) as archive:
        sheet_xml = archive.read(schema.sheet_path)
        strings_xml = archive.read("xl/sharedStrings.xml")
    shared_indexes: dict[str, int] = {}
    shared_values: list[str] = []
    shared_uses = 0
    with minidom.parseString(sheet_xml) as document:
        source_references = {reference: reference for reference in snapshot.cells}
        if source_schema is not None and source_schema != schema:
            source_references = _resize_workout_rows(document, source_schema, schema)
        cells = {
            cell.getAttribute("r"): cell
            for cell in document.getElementsByTagNameNS(MAIN_NS, "c")
            if cell.hasAttribute("r")
        }
        missing = sorted(set(changes).difference(cells))
        if missing:
            raise WorkbookError(
                "Template target cell is missing: " + ", ".join(missing[:3])
            )
        for reference, cell in cells.items():
            original = snapshot.cells[source_references[reference]]
            if reference in changes:
                value = changes[reference]
            elif isinstance(original.value, str):
                value = original.value
            else:
                continue
            _replace_cell_value(cell, value, shared_indexes, shared_values)
            if isinstance(value, str):
                shared_uses += 1
        updated_sheet = document.toxml(encoding="utf-8")

    with minidom.parseString(strings_xml) as document:
        root = document.documentElement
        for child in tuple(root.childNodes):
            if (
                child.nodeType == Node.ELEMENT_NODE
                and child.namespaceURI == MAIN_NS
                and child.localName == "si"
            ):
                root.removeChild(child)
        for value in shared_values:
            item = _append(root, "si")
            text = _append(item, "t")
            if value != value.strip():
                text.setAttributeNS(
                    "http://www.w3.org/XML/1998/namespace", "xml:space", "preserve"
                )
            text.appendChild(document.createTextNode(value))
        root.setAttribute("count", str(shared_uses))
        root.setAttribute("uniqueCount", str(len(shared_values)))
        updated_strings = document.toxml(encoding="utf-8")
    return updated_sheet, updated_strings


def _resize_workout_rows(
    document: minidom.Document,
    original: ProgramTemplateSchema,
    target: ProgramTemplateSchema,
) -> dict[str, str]:
    sheet_data = document.getElementsByTagNameNS(MAIN_NS, "sheetData")[0]
    rows = {
        int(row.getAttribute("r")): row
        for row in document.getElementsByTagNameNS(MAIN_NS, "row")
    }
    source_references = {
        cell.getAttribute("r"): cell.getAttribute("r")
        for cell in document.getElementsByTagNameNS(MAIN_NS, "c")
        if split_cell_reference(cell.getAttribute("r"))[0] <= original.header_row
    }
    for day in original.days:
        for number in day.rows:
            sheet_data.removeChild(rows[number])
    for source_day, target_day in zip(original.days, target.days, strict=True):
        for index, number in enumerate(target_day.rows):
            if index == 0:
                source_number = source_day.rows[0]
            elif index == len(target_day.rows) - 1:
                source_number = source_day.rows[-1]
            else:
                source_number = source_day.rows[min(index, len(source_day.rows) - 2)]
            row = rows[source_number].cloneNode(deep=True)
            row.setAttribute("r", str(number))
            for cell in row.getElementsByTagNameNS(MAIN_NS, "c"):
                old_ref = cell.getAttribute("r")
                new_ref = make_cell_reference(number, split_cell_reference(old_ref)[1])
                source_references[new_ref] = old_ref
                cell.setAttribute("r", new_ref)
            sheet_data.appendChild(row)
    merges = document.getElementsByTagNameNS(MAIN_NS, "mergeCells")[0]
    for merge in tuple(merges.getElementsByTagNameNS(MAIN_NS, "mergeCell")):
        if split_range(merge.getAttribute("ref"))[0] > original.header_row:
            merges.removeChild(merge)
    for day in target.days:
        merge = _append(merges, "mergeCell")
        merge.setAttribute("ref", f"{day.label_cell}:{make_cell_reference(day.rows[-1], target.day_column)}")
    merges.setAttribute("count", str(len(merges.getElementsByTagNameNS(MAIN_NS, "mergeCell"))))
    for dimension in document.getElementsByTagNameNS(MAIN_NS, "dimension"):
        start_row, start_column, _, end_column = split_range(dimension.getAttribute("ref"))
        dimension.setAttribute("ref", (
            f"{make_cell_reference(start_row, start_column)}:"
            f"{make_cell_reference(target.days[-1].rows[-1], end_column)}"
        ))
    return source_references


def _validate_generated_copy(
    template: Path,
    output: Path,
    schema: ProgramTemplateSchema,
    changes: dict[str, str | int | None],
) -> dict[str, Any]:
    generated_schema = inspect_program_template(output)
    if generated_schema != schema:
        raise WorkbookError("Generated workbook no longer matches the verified template structure")
    snapshot = XlsxPackage(output).sheet_snapshot(generated_schema.sheet_name)
    mismatches = [
        reference
        for reference, expected in changes.items()
        if snapshot.cells[reference].value != expected
    ]
    if mismatches:
        raise WorkbookError(
            "Generated workbook failed value round-trip validation: "
            + ", ".join(mismatches[:3])
        )
    integrity = validate_copy_integrity(
        template,
        output,
        {schema.sheet_path, "xl/sharedStrings.xml"},
    )
    if not integrity["zip_members_identical"] or integrity["unrelated_members_changed"]:
        raise WorkbookError("Generated workbook changed unrelated template package parts")
    integrity.update(
        {
            "template_schema_verified": True,
            "sheet": schema.sheet_name,
            "day_row_counts": [len(day.rows) for day in schema.days],
            "set_capacity": len(schema.sets),
            "validated_cells": len(changes),
        }
    )
    return integrity


def write_program_from_template(
    template_path: str | Path,
    output_path: str | Path,
    program: Program,
    schema: ProgramTemplateSchema,
    *,
    resize_workouts: bool = False,
) -> dict[str, Any]:
    template = Path(template_path)
    output = Path(output_path)
    if output.suffix.lower() != ".xlsx":
        raise WorkbookError("Output path must end in .xlsx")
    if output.resolve(strict=False) == template.resolve(strict=False):
        raise WorkbookError("Output path must differ from the template")
    if output.exists():
        raise WorkbookError(f"Output already exists; choose a new path: {output}")
    source_schema = schema
    schema = prepare_program_schema(template, schema, program, resize_workouts=resize_workouts)
    issues = template_generation_issues(program, schema, sheet_name=program.name)
    if issues:
        raise WorkbookError("Program is not safe to generate: " + issues[0].message)
    changes = _program_changes(program, schema)
    updated_sheet, updated_strings = _rewrite_package_parts(template, schema, changes, source_schema)
    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}-", suffix=".xlsx", dir=output.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(template) as source, zipfile.ZipFile(temporary, "w") as target:
            target.comment = source.comment
            for info in source.infolist():
                if info.filename == schema.sheet_path:
                    data = updated_sheet
                elif info.filename == "xl/sharedStrings.xml":
                    data = updated_strings
                else:
                    data = source.read(info.filename)
                target.writestr(copy(info), data)
        validation = _validate_generated_copy(template, temporary, schema, changes)
        os.link(temporary, output)
        return validation
    except FileExistsError as exc:
        raise WorkbookError(f"Output already exists; choose a new path: {output}") from exc
    finally:
        temporary.unlink(missing_ok=True)
