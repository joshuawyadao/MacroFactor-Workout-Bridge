"""Explicit, read-only week selection for irregular coach history sheets."""

from dataclasses import dataclass, replace
import re

from .models import SheetOptions, WeekOption
from .ooxml import XlsxPackage, split_cell_reference, split_range


class HistoryLayoutError(ValueError):
    """A private week layout is invalid or no longer matches the workbook."""


@dataclass(frozen=True)
class HistoryWeek:
    label: str
    header_cell: str
    expected_header: str


def week_layout_payload(layout: tuple[HistoryWeek, ...]) -> list[dict[str, str]]:
    return [
        {"label": week.label, "header_cell": week.header_cell,
         "expected_header": week.expected_header}
        for week in layout
    ]


def parse_week_layout(value: object) -> tuple[HistoryWeek, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise HistoryLayoutError("week_layout must be a non-empty list or null")
    result: list[HistoryWeek] = []
    labels: set[str] = set()
    anchors: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"label", "header_cell", "expected_header"}:
            raise HistoryLayoutError("Each history week needs label, header_cell, and expected_header")
        if any(not isinstance(v, str) or not v.strip() for v in entry.values()):
            raise HistoryLayoutError("History week fields must contain non-empty text")
        week = HistoryWeek(**{key: text.strip() for key, text in entry.items()})
        if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", week.header_cell):
            raise HistoryLayoutError("History header_cell must use A1 notation, such as I3")
        row, column = split_cell_reference(week.header_cell)
        if row > 1048576 or column > 16384:
            raise HistoryLayoutError("History header_cell is outside Excel's worksheet limits")
        if week.label.casefold() in labels or week.header_cell in anchors:
            raise HistoryLayoutError("History week labels and header cells must be unique")
        labels.add(week.label.casefold())
        anchors.add(week.header_cell)
        result.append(week)
    return tuple(result)


def resolve_week_layout(
    workbook: XlsxPackage, block: SheetOptions, layout: tuple[HistoryWeek, ...]
) -> SheetOptions:
    """Resolve an explicit chronological list into ordinary read-only week options."""
    # Validate direct Python callers as well as JSON callers before reading columns.
    parsed = parse_week_layout(week_layout_payload(layout))
    assert parsed is not None
    snapshot = workbook.sheet_snapshot(block.name)
    if block.exercise_column is None or block.exercise_header_cell is None:
        raise HistoryLayoutError("The configured sheet has no exercise header")
    exercise_row, _ = split_cell_reference(block.exercise_header_cell)
    weeks: list[WeekOption] = []
    result_columns: set[int] = set()
    for entry in parsed:
        cell = snapshot.cells.get(entry.header_cell)
        if cell is None or cell.formula is not None or str(cell.value).strip() != entry.expected_header:
            raise HistoryLayoutError(
                f"Header {entry.header_cell} changed or is missing; review the private week layout"
            )
        row, column = split_cell_reference(entry.header_cell)
        if row < exercise_row or column <= block.exercise_column:
            raise HistoryLayoutError("History week headers must follow the exercise header")
        last_column = column
        result_column = column + 1
        for merge in snapshot.merges:
            r1, c1, r2, c2 = split_range(merge)
            if r1 <= row <= r2 and c1 <= column <= c2:
                if (row, column) != (r1, c1):
                    raise HistoryLayoutError("History headers must anchor the top left of a merged range")
                last_column = c2
                result_column = c2
                break
        if result_column > 16384 or result_column in result_columns:
            raise HistoryLayoutError("History weeks must select distinct valid result columns")
        result_columns.add(result_column)
        weeks.append(WeekOption(entry.label, entry.header_cell, row, column, last_column, result_column))
    for week in weeks:
        if any(
            other is not week and other.first_column <= week.result_column <= other.last_column
            for other in weeks
        ):
            raise HistoryLayoutError("A history result column overlaps another selected header range")
    return replace(block, weeks=tuple(weeks))
