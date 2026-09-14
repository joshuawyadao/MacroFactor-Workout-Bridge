from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import normalize_name
from .models import BridgeConfig, CellData, SheetOptions, SheetRef, WeekOption
from .ooxml import (
    WorkbookError,
    XlsxPackage,
    make_cell_reference,
    split_cell_reference,
    split_range,
)


@dataclass(frozen=True)
class TargetRow:
    row: int
    exercise_name: str
    exercise_cell: str
    result_cell: str
    result: CellData | None
    context_values: tuple[str, ...]


@dataclass(frozen=True)
class ProgramDay:
    label: str
    header_row: int
    rows: tuple[TargetRow, ...]


def discover_workbook(path: str | Path, config: BridgeConfig) -> tuple[SheetOptions, ...]:
    package = XlsxPackage(path)
    return tuple(_discover_sheet(package, sheet, config) for sheet in package.sheets)


def _discover_sheet(package: XlsxPackage, sheet: SheetRef, config: BridgeConfig) -> SheetOptions:
    snapshot = package.sheet_snapshot(sheet)
    week_pattern = re.compile(config.week_header_pattern, re.IGNORECASE)
    header_names = {normalize_name(value) for value in config.exercise_header_labels}
    weeks_by_identity: dict[tuple[str, int], WeekOption] = {}
    for reference, cell in snapshot.cells.items():
        if not isinstance(cell.value, str) or not week_pattern.fullmatch(cell.value.strip()):
            continue
        row, column = split_cell_reference(reference)
        first_col = column
        last_col = column
        for merge in snapshot.merges:
            start_row, start_col, end_row, end_col = split_range(merge)
            if start_row <= row <= end_row and start_col <= column <= end_col:
                first_col = start_col
                last_col = end_col
                break
        result_column = last_col if last_col > first_col else column + 1
        option = WeekOption(
            label=cell.value.strip(),
            header_cell=reference,
            header_row=row,
            first_column=first_col,
            last_column=last_col,
            result_column=result_column,
        )
        number_match = re.match(r"week\s*(\d+)", option.label, re.IGNORECASE)
        identity = number_match.group(1) if number_match else normalize_name(option.label)
        key = (identity, result_column)
        existing = weeks_by_identity.get(key)
        if existing is None or option.header_row < existing.header_row:
            weeks_by_identity[key] = option
    weeks = sorted(weeks_by_identity.values(), key=lambda item: (item.header_row, item.first_column))

    header_candidates: list[tuple[int, int, str]] = []
    for reference, cell in snapshot.cells.items():
        if isinstance(cell.value, str) and normalize_name(cell.value) in header_names:
            row, column = split_cell_reference(reference)
            header_candidates.append((row, column, reference))
    exercise_header: tuple[int, int, str] | None = None
    if header_candidates:
        week_rows = {week.header_row for week in weeks}
        same_row = [candidate for candidate in header_candidates if candidate[0] in week_rows]
        pool = same_row or header_candidates
        exercise_header = sorted(pool, key=lambda item: (item[0], item[1]))[0]

    return SheetOptions(
        name=sheet.name,
        path=sheet.path,
        exercise_column=exercise_header[1] if exercise_header else None,
        exercise_header_cell=exercise_header[2] if exercise_header else None,
        weeks=tuple(weeks),
    )


def select_sheet_options(
    path: str | Path,
    config: BridgeConfig,
    sheet_name: str,
    week_label: str,
) -> tuple[XlsxPackage, SheetRef, SheetOptions, WeekOption]:
    package = XlsxPackage(path)
    sheet = package.sheet_by_name(sheet_name)
    options = _discover_sheet(package, sheet, config)
    if options.exercise_column is None or options.exercise_header_cell is None:
        raise WorkbookError(
            f"Worksheet {sheet_name!r} has no configured exercise header "
            f"({', '.join(config.exercise_header_labels)})"
        )
    matches = [week for week in options.weeks if normalize_name(week.label) == normalize_name(week_label)]
    if not matches:
        requested_number = re.fullmatch(r"week\s*(\d+)", week_label.strip(), re.IGNORECASE)
        if requested_number:
            matches = [
                week
                for week in options.weeks
                if (
                    (candidate := re.match(r"week\s*(\d+)", week.label, re.IGNORECASE))
                    and candidate.group(1) == requested_number.group(1)
                )
            ]
    if not matches:
        available = ", ".join(week.label for week in options.weeks) or "none"
        raise WorkbookError(f"Week {week_label!r} was not found in {sheet_name!r}; available: {available}")
    if len(matches) > 1:
        locations = ", ".join(week.header_cell for week in matches)
        raise WorkbookError(f"Week label {week_label!r} is ambiguous in {sheet_name!r}: {locations}")
    return package, sheet, options, matches[0]


def target_rows(
    package: XlsxPackage,
    sheet: SheetRef,
    options: SheetOptions,
    week: WeekOption,
) -> tuple[TargetRow, ...]:
    if options.exercise_column is None or options.exercise_header_cell is None:
        return ()
    snapshot = package.sheet_snapshot(sheet)
    header_row, _ = split_cell_reference(options.exercise_header_cell)
    context_column_limit = min(
        (candidate.first_column for candidate in options.weeks),
        default=week.first_column,
    )
    context_by_row: dict[int, list[tuple[str, str]]] = {}
    for candidate_reference, candidate in snapshot.cells.items():
        candidate_row, candidate_column = split_cell_reference(candidate_reference)
        if (
            candidate_column < context_column_limit
            and isinstance(candidate.value, str)
            and candidate.value.strip()
        ):
            context_by_row.setdefault(candidate_row, []).append(
                (candidate_reference, candidate.value.strip())
            )
    rows: list[TargetRow] = []
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        if column != options.exercise_column or row <= header_row:
            continue
        if not isinstance(cell.value, str) or not cell.value.strip():
            continue
        result_reference = make_cell_reference(row, week.result_column)
        rows.append(
            TargetRow(
                row=row,
                exercise_name=cell.value.strip(),
                exercise_cell=reference,
                result_cell=result_reference,
                result=snapshot.cells.get(result_reference),
                context_values=tuple(
                    value
                    for candidate_reference, value in context_by_row.get(row, [])
                    if candidate_reference != reference
                ),
            )
        )
    return tuple(sorted(rows, key=lambda item: item.row))


def program_days(
    package: XlsxPackage,
    sheet: SheetRef,
    options: SheetOptions,
    week: WeekOption,
) -> tuple[ProgramDay, ...]:
    """Discover repeated ``Day N`` sections from the workbook's existing headers."""
    if options.exercise_column is None or options.exercise_header_cell is None:
        return ()
    snapshot = package.sheet_snapshot(sheet)
    header_cell = snapshot.cells.get(options.exercise_header_cell)
    if header_cell is None or not isinstance(header_cell.value, str):
        return ()
    header_name = normalize_name(header_cell.value)
    header_rows: list[tuple[int, str]] = []
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        if column != options.exercise_column or not isinstance(cell.value, str):
            continue
        if normalize_name(cell.value) != header_name:
            continue
        labels = [
            candidate.value.strip()
            for candidate_reference, candidate in snapshot.cells.items()
            if (
                (candidate_row := split_cell_reference(candidate_reference)[0]) == row
                and split_cell_reference(candidate_reference)[1] < options.exercise_column
                and isinstance(candidate.value, str)
                and re.fullmatch(r"day\s*\d+(?:\.\d+)?", candidate.value.strip(), re.IGNORECASE)
            )
        ]
        if labels:
            header_rows.append((row, labels[-1]))
    discovered_rows = target_rows(package, sheet, options, week)
    sorted_headers = sorted(header_rows)
    days: list[ProgramDay] = []
    for index, (header_row, label) in enumerate(sorted_headers):
        next_header = (
            sorted_headers[index + 1][0] if index + 1 < len(sorted_headers) else None
        )
        rows = tuple(
            target
            for target in discovered_rows
            if target.row > header_row and (next_header is None or target.row < next_header)
        )
        if rows:
            days.append(ProgramDay(label=label, header_row=header_row, rows=rows))
    return tuple(days)
