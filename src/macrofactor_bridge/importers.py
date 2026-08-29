from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import ExerciseNote, SetRecord
from .ooxml import WorkbookError, XlsxPackage, split_cell_reference


REQUIRED_HEADERS = {"Date", "Workout", "Exercise", "Set Type", "Weight (lbs)", "Reps"}


class ImportError(ValueError):
    """Raised when a MacroFactor export is missing required data."""


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ImportError(f"Invalid numeric value: {value!r}") from exc


def _parse_date(value: object) -> date:
    if isinstance(value, (int, float)):
        return date(1899, 12, 30) + timedelta(days=float(value))
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    raise ImportError(f"Unsupported workout date: {value!r}")


def _record_from_mapping(row_number: int, row: dict[str, object]) -> SetRecord:
    return SetRecord(
        source_row=row_number,
        workout_date=_parse_date(row.get("Date")),
        workout=str(row.get("Workout") or "").strip(),
        exercise=str(row.get("Exercise") or "").strip(),
        set_type=str(row.get("Set Type") or "").strip(),
        weight=_parse_decimal(row.get("Weight (lbs)")),
        reps=_parse_decimal(row.get("Reps")),
    )


def load_exercise_log(path: str | Path) -> list[SetRecord]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return _load_csv(source)
    if suffix == ".xlsx":
        return _load_xlsx(source)
    raise ImportError("MacroFactor export must be .csv or .xlsx")


def load_exercise_notes(path: str | Path) -> list[ExerciseNote]:
    """Read exercise-level notes exposed by MacroFactor's Active Program table."""
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return []
    if source.suffix.lower() != ".xlsx":
        raise ImportError("MacroFactor export must be .csv or .xlsx")
    try:
        package = XlsxPackage(source)
    except WorkbookError as exc:
        raise ImportError(str(exc)) from exc

    notes: list[ExerciseNote] = []
    for sheet in package.sheets:
        snapshot = package.sheet_snapshot(sheet)
        by_row: dict[int, dict[int, object]] = {}
        for reference, cell in snapshot.cells.items():
            row, column = split_cell_reference(reference)
            by_row.setdefault(row, {})[column] = cell.value
        note_tables: list[tuple[int, int, int]] = []
        for header_row, header_values in sorted(by_row.items()):
            headers = {
                str(value).strip(): column
                for column, value in header_values.items()
                if isinstance(value, str) and str(value).strip()
            }
            if not {"Exercise", "Notes"}.issubset(headers):
                continue
            note_tables.append((header_row, headers["Exercise"], headers["Notes"]))
        for table_index, (header_row, exercise_column, notes_column) in enumerate(note_tables):
            next_header = (
                note_tables[table_index + 1][0]
                if table_index + 1 < len(note_tables)
                else None
            )
            for row_number in sorted(
                row
                for row in by_row
                if row > header_row and (next_header is None or row < next_header)
            ):
                values = by_row[row_number]
                exercise = str(values.get(exercise_column) or "").strip()
                note = str(values.get(notes_column) or "").strip()
                if exercise and note:
                    notes.append(
                        ExerciseNote(
                            source_row=row_number,
                            sheet=sheet.name,
                            exercise=exercise,
                            note=note,
                        )
                    )
    return notes


def _load_csv(path: Path) -> list[SetRecord]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = REQUIRED_HEADERS - headers
            if missing:
                raise ImportError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
            return [_record_from_mapping(index, row) for index, row in enumerate(reader, start=2)]
    except OSError as exc:
        raise ImportError(f"Could not read MacroFactor CSV {path}: {exc}") from exc


def _load_xlsx(path: Path) -> list[SetRecord]:
    try:
        package = XlsxPackage(path)
    except WorkbookError as exc:
        raise ImportError(str(exc)) from exc
    candidate_rows: list[tuple[str, int, dict[int, str], dict[str, object]]] = []
    for sheet in package.sheets:
        snapshot = package.sheet_snapshot(sheet)
        by_row: dict[int, dict[int, object]] = {}
        for reference, cell in snapshot.cells.items():
            row, column = split_cell_reference(reference)
            by_row.setdefault(row, {})[column] = cell.value
        for row_number, values in by_row.items():
            headers = {
                column: str(value).strip()
                for column, value in values.items()
                if isinstance(value, str) and str(value).strip()
            }
            if REQUIRED_HEADERS.issubset(set(headers.values())):
                candidate_rows.append((sheet.name, row_number, headers, {"snapshot": snapshot, "by_row": by_row}))
    if not candidate_rows:
        raise ImportError("No worksheet contains the required MacroFactor exercise-log columns")
    if len(candidate_rows) > 1:
        locations = ", ".join(f"{sheet}!{row}" for sheet, row, _, _ in candidate_rows)
        raise ImportError(f"Multiple MacroFactor log tables were found: {locations}")
    _, header_row, header_by_column, context = candidate_rows[0]
    by_row = context["by_row"]
    column_by_header = {header: column for column, header in header_by_column.items()}
    records: list[SetRecord] = []
    for row_number in sorted(row for row in by_row if row > header_row):
        values = by_row[row_number]
        row = {header: values.get(column) for header, column in column_by_header.items()}
        if not any(row.get(header) not in (None, "") for header in REQUIRED_HEADERS):
            continue
        if not row.get("Exercise") or row.get("Date") in (None, ""):
            continue
        records.append(_record_from_mapping(row_number, row))
    return records
