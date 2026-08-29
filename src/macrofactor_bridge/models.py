from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ExerciseRule:
    canonical: str
    source_aliases: tuple[str, ...]
    coach_aliases: tuple[str, ...]
    coach_context_aliases: tuple[str, ...] = ()
    weight_multiplier: Decimal = Decimal("1")
    weight_suffix: str = ""
    superset_group: str | None = None
    superset_order: int = 0


@dataclass(frozen=True)
class BridgeConfig:
    exercise_header_labels: tuple[str, ...]
    week_header_pattern: str
    rules: tuple[ExerciseRule, ...]


@dataclass(frozen=True)
class SetRecord:
    source_row: int
    workout_date: date
    workout: str
    exercise: str
    set_type: str
    weight: Decimal | None
    reps: Decimal | None


@dataclass(frozen=True)
class ExerciseNote:
    source_row: int
    sheet: str
    exercise: str
    note: str


@dataclass(frozen=True)
class CellData:
    reference: str
    value: str | float | int | None
    formula: str | None
    style: str | None
    cell_type: str | None

    @property
    def is_empty(self) -> bool:
        return self.formula is None and self.value is None


@dataclass(frozen=True)
class SheetRef:
    name: str
    path: str


@dataclass(frozen=True)
class WeekOption:
    label: str
    header_cell: str
    header_row: int
    first_column: int
    last_column: int
    result_column: int


@dataclass(frozen=True)
class SheetOptions:
    name: str
    path: str
    exercise_column: int | None
    exercise_header_cell: str | None
    weeks: tuple[WeekOption, ...]


@dataclass(frozen=True)
class ProposedWrite:
    sheet: str
    week: str
    cell: str
    value: str
    source_exercises: tuple[str, ...]


@dataclass
class BridgeReport:
    input_export: str
    input_workbook: str
    sheet: str
    week: str
    from_date: str
    to_date: str
    rows_read: int = 0
    rows_in_range: int = 0
    proposed_writes: list[ProposedWrite] = field(default_factory=list)
    unmatched_exercises: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_matches: list[dict[str, Any]] = field(default_factory=list)
    zero_rep_rows: list[dict[str, Any]] = field(default_factory=list)
    skipped_rows: list[dict[str, Any]] = field(default_factory=list)
    occupied_cells: list[dict[str, Any]] = field(default_factory=list)
    exercise_notes: list[dict[str, Any]] = field(default_factory=list)
    source_hash_before: str | None = None
    source_hash_after: str | None = None
    export_hash_before: str | None = None
    export_hash_after: str | None = None
    output_file: str | None = None
    output_hash: str | None = None
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
