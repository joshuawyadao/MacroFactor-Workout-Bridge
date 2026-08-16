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
            )
        )
    return tuple(sorted(rows, key=lambda item: item.row))
