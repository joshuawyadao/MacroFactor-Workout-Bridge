"""Exact exercise-name evidence from private, native MacroFactor exports."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .ooxml import WorkbookError, XlsxPackage, file_sha256, make_cell_reference, split_cell_reference
from .program_models import Program, ProgramIssue
from .program_template import inspect_program_template

_SUPERSET_SUFFIX = re.compile(r" ∈ SS[1-9]\d*$")
_LOG_HEADERS = {"Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"}
_LOG_HEADER_ALIASES = {"Weight (lb)": "Weight (lbs)"}


def _base_name(value: str) -> str:
    """Remove only MacroFactor's exported superset suffix, never a name fragment."""
    return _SUPERSET_SUFFIX.sub("", value)


def _program_names(path: Path) -> set[str]:
    schema = inspect_program_template(path)
    cells = XlsxPackage(path).sheet_snapshot(schema.sheet_name).cells
    names: set[str] = set()
    for day in schema.days:
        for row in day.rows:
            reference = make_cell_reference(row, schema.exercise_column)
            cell = cells[reference]
            if not isinstance(cell.value, str) or not cell.value.strip():
                raise WorkbookError(f"Program export has an empty exercise name at {reference}")
            names.add(_base_name(cell.value))
    return names


def _log_names(path: Path) -> set[str]:
    package = XlsxPackage(path)
    if "Workout Log" not in {sheet.name for sheet in package.sheets}:
        raise WorkbookError("Exercise-name log evidence needs a Workout Log worksheet")
    cells = package.sheet_snapshot("Workout Log").cells
    rows: dict[int, dict[int, object]] = {}
    for reference, cell in cells.items():
        row, column = split_cell_reference(reference)
        if cell.formula is not None:
            raise WorkbookError("Exercise-name log evidence cannot contain formulas")
        rows.setdefault(row, {})[column] = cell.value
    candidates: list[tuple[int, int]] = []
    for row, values in rows.items():
        headers = {
            column: _LOG_HEADER_ALIASES.get(value.strip(), value.strip())
            for column, value in values.items()
            if isinstance(value, str)
        }
        if _LOG_HEADERS.issubset(headers.values()):
            if len(headers.values()) != len(set(headers.values())):
                raise WorkbookError("Workout Log has duplicate logical columns")
            candidates.append((row, next(column for column, name in headers.items() if name == "Exercise")))
    if len(candidates) != 1:
        raise WorkbookError("Exercise-name log evidence needs one native Workout Log table")
    header_row, exercise_column = candidates[0]
    names: set[str] = set()
    for row in sorted(rows):
        if row <= header_row:
            continue
        value = rows[row].get(exercise_column)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise WorkbookError(f"Workout Log has an invalid Exercise value in row {row}")
        names.add(value)
    if not names:
        raise WorkbookError("Workout Log has no exercise names")
    return names


def verify_program_exercise_names(
    program: Program,
    template_path: str | Path,
    reference_paths: tuple[str, ...] = (),
) -> tuple[tuple[ProgramIssue, ...], dict[str, Any], dict[str, str]]:
    """Verify included names against direct program and optional native log/program exports.

    Returns blocking issues, JSON-friendly evidence, and before hashes for every
    valid reference. Callers must recheck these hashes before and after writing.
    """
    sources = tuple(dict.fromkeys(
        [Path(template_path).resolve(strict=False),
         *(Path(value).resolve(strict=False) for value in reference_paths)]
    ))
    issues: list[ProgramIssue] = []
    hashes: dict[str, str] = {}
    available: set[str] = set()
    details: dict[str, Any] = {"sources": [], "verified_names": [], "unknown_names": []}
    for index, path in enumerate(sources):
        try:
            before = file_sha256(path)
            if index == 0:
                names = _program_names(path)
                kind = "program_export"
            else:
                package = XlsxPackage(path)
                if "Workout Log" in {sheet.name for sheet in package.sheets}:
                    names = _log_names(path)
                    kind = "workout_log"
                else:
                    names = _program_names(path)
                    kind = "program_export"
            after = file_sha256(path)
            if before != after:
                raise WorkbookError("Reference workbook changed during exercise-name verification")
        except (OSError, WorkbookError, ValueError, KeyError, IndexError,
                zipfile.BadZipFile, ET.ParseError) as exc:
            issues.append(ProgramIssue(
                severity="blocking", code="invalid_exercise_name_reference",
                message=f"Cannot verify native exercise-name reference {path}: {exc}",
                sheet="Training Programs",
            ))
            continue
        hashes[str(path)] = before
        available.update(names)
        details["sources"].append({
            "path": str(path), "kind": kind, "sha256": before, "name_count": len(names),
        })
    for day in program.days:
        for exercise in day.exercises:
            if exercise.excluded:
                continue
            name = exercise.macrofactor_name
            if name is not None and name in available:
                details["verified_names"].append(name)
                continue
            details["unknown_names"].append(name)
            issues.append(ProgramIssue(
                severity="blocking", code="unverified_exercise_name",
                message=(f"Exercise name {name!r} has no exact match in the selected "
                         "native MacroFactor program export or configured references"),
                sheet="Training Programs", cell=exercise.source_cell,
                day=day.label, exercise=exercise.coach_name,
            ))
    details["verified_names"] = sorted(set(details["verified_names"]))
    details["unknown_names"] = sorted(set(details["unknown_names"]), key=lambda value: value or "")
    return tuple(issues), details, hashes
