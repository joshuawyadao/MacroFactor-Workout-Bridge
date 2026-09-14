from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProgramDefaults:
    rep_min: int | None = None
    rep_max: int | None = None
    rir: int | None = None
    rest_seconds: int | None = None


@dataclass(frozen=True)
class ProgramConfig:
    day_label_pattern: str = (
        r"^day\s*(\d+(?:\.\d+)?)(?:\s*(?:[-:]?\s*optional|\(optional\)))?$"
    )
    week_header_pattern: str = r"^week\s*\d+(?:\s*\([^)]*\))?$"
    week_pair_layout: str | None = None
    style_header_labels: tuple[str, ...] = ("Style",)
    exercise_header_labels: tuple[str, ...] = ("Variation", "Exercise")
    sets_header_labels: tuple[str, ...] = ("Sets",)
    reps_header_labels: tuple[str, ...] = ("Reps", "Rep Target")
    rest_header_labels: tuple[str, ...] = ("Rest",)
    defaults: ProgramDefaults = field(default_factory=ProgramDefaults)


@dataclass(frozen=True)
class ProgramBlockOption:
    identifier: str
    sheet: str
    start_row: int
    end_row: int
    day_labels: tuple[str, ...]
    week_labels: tuple[str, ...]


@dataclass(frozen=True)
class ProgramCycle:
    label: str
    order: int


@dataclass(frozen=True)
class PrescriptionField:
    value: int | str | None
    source: str
    source_cell: str | None = None
    raw_text: str | None = None


@dataclass(frozen=True)
class CyclePrescription:
    cycle: str
    set_count: PrescriptionField
    set_type: PrescriptionField
    rep_min: PrescriptionField
    rep_max: PrescriptionField
    rir: PrescriptionField
    rest_seconds: PrescriptionField
    notes: tuple[str, ...]
    raw_week_text: str | None
    raw_unparsed_text: str | None


@dataclass(frozen=True)
class SupersetMembership:
    group: str
    order: int


@dataclass(frozen=True)
class OrderedExercise:
    order: int
    source_row: int
    source_cell: str
    coach_name: str
    macrofactor_name: str | None
    mapping_status: str
    raw_base_fields: dict[str, str]
    prescriptions: tuple[CyclePrescription, ...]
    superset: SupersetMembership | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    custom_exercise: bool = False
    macrofactor_available: bool = True
    optional: bool = False
    warmup: bool = False
    cardio: bool = False


@dataclass(frozen=True)
class WorkoutDay:
    label: str
    order: int
    optional: bool
    exercises: tuple[OrderedExercise, ...]


@dataclass(frozen=True)
class Program:
    name: str
    cycle_name: str
    cycles: tuple[ProgramCycle, ...]
    days: tuple[WorkoutDay, ...]


@dataclass(frozen=True)
class ProgramIssue:
    severity: str
    code: str
    message: str
    sheet: str
    cell: str | None = None
    day: str | None = None
    exercise: str | None = None
    cycle: str | None = None
    raw_text: str | None = None


@dataclass(frozen=True)
class ProgramParseResult:
    program: Program
    issues: tuple[ProgramIssue, ...]
    skipped_items: tuple[dict[str, Any], ...]


@dataclass
class ProgramPreviewReport:
    input_workbook: str
    sheet: str
    block: str
    included_weeks: tuple[str, ...]
    program: Program | None = None
    issues: list[ProgramIssue] = field(default_factory=list)
    skipped_items: list[dict[str, Any]] = field(default_factory=list)
    source_hash_before: str | None = None
    source_hash_after: str | None = None
    template_hash: str | None = None
    template_schema_verified: bool = False
    manual_import_verified: bool = False
    generation_safe: bool = False

    @property
    def blocking_issues(self) -> tuple[ProgramIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "blocking")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
