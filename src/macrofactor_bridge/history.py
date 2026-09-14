from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import normalize_name, source_rule_index
from .importers import ExerciseLogImport, load_exercise_log_with_diagnostics
from .models import BridgeConfig, ExerciseRule, SetRecord, SheetOptions
from .ooxml import XlsxPackage
from .workbook import discover_workbook, target_rows


ANNOTATION_SCHEMA_VERSION = 1
BLOCK_TYPE_OPTIONS = (
    ("unspecified", "Unspecified"),
    ("volume_hypertrophy", "Volume / hypertrophy"),
    ("strength", "Strength"),
    ("peaking_testing", "Peaking / testing"),
    ("rebuild_return", "Rebuild / return"),
    ("mixed", "Mixed"),
)
WEEK_STATUS_OPTIONS = (
    ("normal", "Normal training"),
    ("deload_reentry", "Deload / re-entry"),
    ("modified", "Modified training"),
)
WEEK_REASON_OPTIONS = (
    ("unspecified", "Unspecified"),
    ("planned", "Planned"),
    ("fatigue", "Accumulated fatigue"),
    ("vacation", "Vacation / schedule"),
    ("injury", "Injury"),
    ("illness", "Illness"),
    ("other", "Other"),
)

_BLOCK_TYPES = {value for value, _ in BLOCK_TYPE_OPTIONS}
_WEEK_STATUSES = {value for value, _ in WEEK_STATUS_OPTIONS}
_WEEK_REASONS = {value for value, _ in WEEK_REASON_OPTIONS}
_SUPERSET_MARKER = re.compile(r"\s*∈\s*SS\d+\s*$", re.IGNORECASE)


class HistoryError(ValueError):
    """Raised when history inputs or private annotations are invalid."""


@dataclass(frozen=True)
class WeekAnnotation:
    status: str = "normal"
    reason: str = "unspecified"
    affected_movements: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class BlockAnnotation:
    block_type: str = "unspecified"
    start_date: date | None = None
    notes: str = ""
    weeks: dict[str, WeekAnnotation] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardAnnotations:
    blocks: dict[str, BlockAnnotation] = field(default_factory=dict)


@dataclass(frozen=True)
class BlockSummary:
    name: str
    position: int
    week_labels: tuple[str, ...]
    completed_results: int
    programmed_results: int
    block_type: str
    start_date: date | None
    annotated_week_count: int
    mapped_set_count: int
    mapped_training_days: int


@dataclass(frozen=True)
class WeeklyExerciseTrend:
    exercise: str
    week_start: date
    training_days: int
    set_count: int
    total_reps: Decimal
    volume_load: Decimal
    top_weight: Decimal | None
    estimated_1rm: Decimal | None
    average_rir: Decimal | None
    rir_set_count: int
    block_name: str | None
    block_week: str | None


@dataclass(frozen=True)
class ExerciseSummary:
    exercise: str
    trained_week_count: int
    set_count: int
    top_weight: Decimal | None
    best_estimated_1rm: Decimal | None
    rir_set_count: int
    trend: str


@dataclass(frozen=True)
class HistoryDashboard:
    first_workout: date
    last_workout: date
    set_count: int
    workout_count: int
    training_day_count: int
    rir_set_count: int
    duration_session_count: int
    total_duration_seconds: Decimal
    blocks: tuple[BlockSummary, ...]
    exercises: tuple[ExerciseSummary, ...]
    weekly_trends: tuple[WeeklyExerciseTrend, ...]
    warnings: tuple[str, ...]

    def trends_for(self, exercise: str) -> tuple[WeeklyExerciseTrend, ...]:
        return tuple(
            trend for trend in self.weekly_trends if trend.exercise == exercise
        )


@dataclass(frozen=True)
class _BlockInterval:
    name: str
    start: date
    end: date
    week_labels: tuple[str, ...]


@dataclass
class _TrendAccumulator:
    dates: set[date] = field(default_factory=set)
    set_count: int = 0
    total_reps: Decimal = Decimal("0")
    volume_load: Decimal = Decimal("0")
    weights: list[Decimal] = field(default_factory=list)
    estimated_1rms: list[Decimal] = field(default_factory=list)
    rirs: list[Decimal] = field(default_factory=list)
    block_locations: set[tuple[str, str]] = field(default_factory=set)


@dataclass
class _HistoryAggregation:
    trend_data: dict[tuple[str, date], _TrendAccumulator] = field(
        default_factory=dict
    )
    block_sets: dict[str, int] = field(default_factory=dict)
    block_days: dict[str, set[date]] = field(default_factory=dict)
    sessions: dict[tuple[date, str], list[Decimal]] = field(default_factory=dict)
    training_days: set[date] = field(default_factory=set)
    rir_set_count: int = 0


@dataclass(frozen=True)
class _HistorySources:
    imported: ExerciseLogImport
    records: tuple[SetRecord, ...]
    workbook: XlsxPackage
    blocks: tuple[SheetOptions, ...]


def _validated_text(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise HistoryError(f"{label} must be text")
    return value.strip()


def _parse_week_annotation(value: object, label: str) -> WeekAnnotation:
    if not isinstance(value, dict):
        raise HistoryError(f"{label} must be an object")
    status = _validated_text(value.get("status", "normal"), f"{label}.status")
    reason = _validated_text(
        value.get("reason", "unspecified"), f"{label}.reason"
    )
    if status not in _WEEK_STATUSES:
        raise HistoryError(f"{label}.status is not supported: {status!r}")
    if reason not in _WEEK_REASONS:
        raise HistoryError(f"{label}.reason is not supported: {reason!r}")
    movements = value.get("affected_movements", [])
    if not isinstance(movements, list) or not all(
        isinstance(item, str) for item in movements
    ):
        raise HistoryError(f"{label}.affected_movements must be a list of text")
    notes = _validated_text(value.get("notes", ""), f"{label}.notes")
    return WeekAnnotation(
        status=status,
        reason=reason,
        affected_movements=tuple(
            dict.fromkeys(item.strip() for item in movements if item.strip())
        ),
        notes=notes,
    )


def _parse_block_annotation(value: object, label: str) -> BlockAnnotation:
    if not isinstance(value, dict):
        raise HistoryError(f"{label} must be an object")
    block_type = _validated_text(
        value.get("block_type", "unspecified"), f"{label}.block_type"
    )
    if block_type not in _BLOCK_TYPES:
        raise HistoryError(f"{label}.block_type is not supported: {block_type!r}")
    raw_start = value.get("start_date")
    start_date: date | None = None
    if raw_start not in (None, ""):
        start_text = _validated_text(raw_start, f"{label}.start_date")
        try:
            start_date = date.fromisoformat(start_text)
        except ValueError as exc:
            raise HistoryError(
                f"{label}.start_date must use YYYY-MM-DD"
            ) from exc
        if start_date.isoformat() != start_text:
            raise HistoryError(f"{label}.start_date must use YYYY-MM-DD")
    raw_weeks = value.get("weeks", {})
    if not isinstance(raw_weeks, dict):
        raise HistoryError(f"{label}.weeks must be an object")
    weeks: dict[str, WeekAnnotation] = {}
    for week_name, week_value in raw_weeks.items():
        name = _validated_text(week_name, f"{label} week name")
        if not name:
            raise HistoryError(f"{label} contains an empty week name")
        weeks[name] = _parse_week_annotation(
            week_value, f"{label}.weeks[{name!r}]"
        )
    notes = _validated_text(value.get("notes", ""), f"{label}.notes")
    return BlockAnnotation(
        block_type=block_type,
        start_date=start_date,
        notes=notes,
        weeks=weeks,
    )


def load_dashboard_annotations(
    path: str | Path | None,
) -> DashboardAnnotations:
    if path is None or not str(path).strip():
        return DashboardAnnotations()
    source = Path(path)
    if source.is_symlink():
        raise HistoryError(f"Refusing to read symlinked annotations: {source}")
    if not source.exists():
        return DashboardAnnotations()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoryError(f"Could not read dashboard annotations {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HistoryError("Dashboard annotations must contain a JSON object")
    if payload.get("schema_version") != ANNOTATION_SCHEMA_VERSION:
        raise HistoryError(
            "Dashboard annotations use an unsupported schema version"
        )
    raw_blocks = payload.get("blocks", {})
    if not isinstance(raw_blocks, dict):
        raise HistoryError("Dashboard annotation blocks must be an object")
    blocks: dict[str, BlockAnnotation] = {}
    for block_name, block_value in raw_blocks.items():
        name = _validated_text(block_name, "Block name")
        if not name:
            raise HistoryError("Dashboard annotations contain an empty block name")
        blocks[name] = _parse_block_annotation(
            block_value, f"blocks[{name!r}]"
        )
    return DashboardAnnotations(blocks=blocks)


def _annotation_payload(annotations: DashboardAnnotations) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    for name, block in annotations.blocks.items():
        blocks[name] = {
            "block_type": block.block_type,
            "start_date": block.start_date.isoformat() if block.start_date else None,
            "notes": block.notes,
            "weeks": {
                week_name: {
                    "status": week.status,
                    "reason": week.reason,
                    "affected_movements": list(week.affected_movements),
                    "notes": week.notes,
                }
                for week_name, week in block.weeks.items()
            },
        }
    return {"schema_version": ANNOTATION_SCHEMA_VERSION, "blocks": blocks}


def save_dashboard_annotations(
    path: str | Path, annotations: DashboardAnnotations
) -> Path:
    destination = Path(path)
    if destination.suffix.lower() != ".json":
        raise HistoryError("Dashboard annotation filename must end in .json")
    if destination.is_symlink():
        raise HistoryError(f"Refusing to replace symlinked annotations: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.tmp-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                _annotation_payload(annotations),
                handle,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def default_dashboard_annotations_path(workbook_path: str | Path) -> Path:
    workbook = Path(workbook_path)
    for parent in (workbook.parent, *workbook.parent.parents):
        if parent.name == "local-data":
            return parent / "annotations" / "workout-history.json"
    return workbook.with_name(f"{workbook.stem}-workout-history.json")


def update_block_annotation(
    annotations: DashboardAnnotations,
    block_name: str,
    *,
    block_type: str,
    start_date: date | None,
    notes: str,
) -> DashboardAnnotations:
    if block_type not in _BLOCK_TYPES:
        raise HistoryError(f"Unsupported block type: {block_type!r}")
    existing = annotations.blocks.get(block_name, BlockAnnotation())
    blocks = dict(annotations.blocks)
    blocks[block_name] = BlockAnnotation(
        block_type=block_type,
        start_date=start_date,
        notes=notes.strip(),
        weeks=dict(existing.weeks),
    )
    return DashboardAnnotations(blocks=blocks)


def update_week_annotation(
    annotations: DashboardAnnotations,
    block_name: str,
    week_name: str,
    *,
    status: str,
    reason: str,
    affected_movements: tuple[str, ...],
    notes: str,
) -> DashboardAnnotations:
    if status not in _WEEK_STATUSES:
        raise HistoryError(f"Unsupported week status: {status!r}")
    if reason not in _WEEK_REASONS:
        raise HistoryError(f"Unsupported week reason: {reason!r}")
    existing = annotations.blocks.get(block_name, BlockAnnotation())
    weeks = dict(existing.weeks)
    weeks[week_name] = WeekAnnotation(
        status=status,
        reason=reason,
        affected_movements=tuple(
            dict.fromkeys(item.strip() for item in affected_movements if item.strip())
        ),
        notes=notes.strip(),
    )
    blocks = dict(annotations.blocks)
    blocks[block_name] = BlockAnnotation(
        block_type=existing.block_type,
        start_date=existing.start_date,
        notes=existing.notes,
        weeks=weeks,
    )
    return DashboardAnnotations(blocks=blocks)


def _canonical_exercise(
    record: SetRecord, source_index: dict[str, ExerciseRule]
) -> str:
    base_name = _SUPERSET_MARKER.sub("", record.exercise).strip()
    rule = source_index.get(normalize_name(base_name))
    return rule.canonical if rule else base_name


def _estimated_1rm(record: SetRecord) -> Decimal | None:
    if (
        record.weight is None
        or record.reps is None
        or not record.weight.is_finite()
        or not record.reps.is_finite()
        or record.weight <= 0
        or not Decimal("1") <= record.reps <= Decimal("12")
    ):
        return None
    set_kind = record.set_type.casefold().replace("-", " ")
    if any(marker in set_kind for marker in ("drop", "mini", "myo")):
        return None
    return (record.weight * (Decimal("1") + record.reps / Decimal("30"))).quantize(
        Decimal("0.1")
    )


def _sparkline(values: tuple[Decimal | None, ...]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    available = [value for value in values if value is not None]
    if not available:
        return "—"
    low = min(available)
    high = max(available)
    if high == low:
        return "".join("▄" if value is not None else "·" for value in values)
    scale = Decimal(len(bars) - 1) / (high - low)
    return "".join(
        bars[int((value - low) * scale)] if value is not None else "·"
        for value in values
    )


def _record_is_usable(record: SetRecord) -> bool:
    return bool(
        record.exercise
        and record.set_type
        and record.reps is not None
        and record.reps.is_finite()
        and record.reps > 0
    )


def _ordered_week_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    numbered: list[tuple[int, str]] = []
    for label in labels:
        match = re.match(r"week\s*(\d+)", label, re.IGNORECASE)
        if match is None:
            return labels
        numbered.append((int(match.group(1)), label))
    if len({number for number, _ in numbered}) != len(numbered):
        return labels
    return tuple(label for _, label in sorted(numbered))


def _load_history_sources(
    export_path: str | Path,
    workbook_path: str | Path,
    config: BridgeConfig,
) -> _HistorySources:
    imported = load_exercise_log_with_diagnostics(export_path)
    records = tuple(record for record in imported.records if _record_is_usable(record))
    if not records:
        raise HistoryError("The MacroFactor export contains no usable completed sets")
    workbook = XlsxPackage(workbook_path)
    blocks = tuple(
        sheet
        for sheet in discover_workbook(workbook_path, config)
        if sheet.exercise_column is not None and sheet.weeks
    )
    if not blocks:
        raise HistoryError("The coach workbook contains no usable block worksheets")
    return _HistorySources(imported, records, workbook, blocks)


def _block_result_counts(
    workbook: XlsxPackage,
    blocks: tuple[SheetOptions, ...],
    marker_text: str,
) -> dict[str, tuple[int, int]]:
    counts: dict[str, tuple[int, int]] = {}
    for block in blocks:
        sheet_ref = workbook.sheet_by_name(block.name)
        programmed = 0
        completed = 0
        for week in block.weeks:
            rows = target_rows(workbook, sheet_ref, block, week)
            programmed += len(rows)
            completed += sum(
                row.result is not None
                and not row.result.is_empty
                and (
                    not marker_text
                    or normalize_name(str(row.result.value or "")) != marker_text
                )
                for row in rows
            )
        counts[block.name] = (completed, programmed)
    return counts


def _dated_block_intervals(
    blocks: tuple[SheetOptions, ...],
    annotations: DashboardAnnotations,
    warnings: list[str],
) -> tuple[tuple[_BlockInterval, ...], frozenset[str]]:
    intervals: list[_BlockInterval] = []
    for block in blocks:
        annotation = annotations.blocks.get(block.name, BlockAnnotation())
        if annotation.start_date is None:
            continue
        labels = _ordered_week_labels(tuple(week.label for week in block.weeks))
        intervals.append(
            _BlockInterval(
                name=block.name,
                start=annotation.start_date,
                end=annotation.start_date + timedelta(days=len(labels) * 7 - 1),
                week_labels=labels,
            )
        )
    overlapping: set[str] = set()
    for index, first in enumerate(intervals):
        for second in intervals[index + 1 :]:
            if first.start <= second.end and second.start <= first.end:
                overlapping.update((first.name, second.name))
    if overlapping:
        warnings.append(
            "Overlapping block date ranges were not used for mapping: "
            + ", ".join(sorted(overlapping))
            + "."
        )
    return tuple(intervals), frozenset(overlapping)


def _locate_block(
    workout_date: date,
    intervals: tuple[_BlockInterval, ...],
    overlapping: frozenset[str],
) -> tuple[str, str] | None:
    matches = tuple(
        interval
        for interval in intervals
        if interval.name not in overlapping
        and interval.start <= workout_date <= interval.end
    )
    if len(matches) != 1:
        return None
    match = matches[0]
    week_index = (workout_date - match.start).days // 7
    return match.name, match.week_labels[week_index]


def _aggregate_history(
    records: tuple[SetRecord, ...],
    source_index: dict[str, ExerciseRule],
    intervals: tuple[_BlockInterval, ...],
    overlapping: frozenset[str],
) -> _HistoryAggregation:
    aggregation = _HistoryAggregation()
    for record in records:
        exercise = _canonical_exercise(record, source_index)
        monday = record.workout_date - timedelta(days=record.workout_date.weekday())
        values = aggregation.trend_data.setdefault(
            (exercise, monday), _TrendAccumulator()
        )
        values.dates.add(record.workout_date)
        values.set_count += 1
        assert record.reps is not None
        values.total_reps += record.reps
        if record.weight is not None and record.weight.is_finite():
            values.weights.append(record.weight)
            values.volume_load += record.weight * record.reps
        estimate = _estimated_1rm(record)
        if estimate is not None:
            values.estimated_1rms.append(estimate)
        if record.rir is not None:
            values.rirs.append(record.rir)
            aggregation.rir_set_count += 1
        location = _locate_block(record.workout_date, intervals, overlapping)
        if location is not None:
            values.block_locations.add(location)
            aggregation.block_sets[location[0]] = (
                aggregation.block_sets.get(location[0], 0) + 1
            )
            aggregation.block_days.setdefault(location[0], set()).add(
                record.workout_date
            )
        session = aggregation.sessions.setdefault(
            (record.workout_date, record.workout), []
        )
        if record.workout_duration_seconds is not None:
            session.append(record.workout_duration_seconds)
        aggregation.training_days.add(record.workout_date)
    return aggregation


def _weekly_trends(
    trend_data: dict[tuple[str, date], _TrendAccumulator],
) -> tuple[WeeklyExerciseTrend, ...]:
    trends: list[WeeklyExerciseTrend] = []
    for (exercise, monday), values in sorted(
        trend_data.items(), key=lambda item: (item[0][0].casefold(), item[0][1])
    ):
        location = (
            next(iter(values.block_locations))
            if len(values.block_locations) == 1
            else None
        )
        trends.append(
            WeeklyExerciseTrend(
                exercise=exercise,
                week_start=monday,
                training_days=len(values.dates),
                set_count=values.set_count,
                total_reps=values.total_reps,
                volume_load=values.volume_load,
                top_weight=max(values.weights) if values.weights else None,
                estimated_1rm=(
                    max(values.estimated_1rms) if values.estimated_1rms else None
                ),
                average_rir=(
                    sum(values.rirs, Decimal("0")) / len(values.rirs)
                    if values.rirs
                    else None
                ),
                rir_set_count=len(values.rirs),
                block_name=location[0] if location else None,
                block_week=location[1] if location else None,
            )
        )
    return tuple(trends)


def _exercise_summaries(
    weekly_trends: tuple[WeeklyExerciseTrend, ...],
) -> tuple[ExerciseSummary, ...]:
    by_exercise: defaultdict[str, list[WeeklyExerciseTrend]] = defaultdict(list)
    for trend in weekly_trends:
        by_exercise[trend.exercise].append(trend)
    summaries: list[ExerciseSummary] = []
    for exercise, trends in sorted(
        by_exercise.items(), key=lambda item: item[0].casefold()
    ):
        top_weights = [
            trend.top_weight for trend in trends if trend.top_weight is not None
        ]
        estimates = [
            trend.estimated_1rm for trend in trends if trend.estimated_1rm is not None
        ]
        summaries.append(
            ExerciseSummary(
                exercise=exercise,
                trained_week_count=len(trends),
                set_count=sum(trend.set_count for trend in trends),
                top_weight=max(top_weights) if top_weights else None,
                best_estimated_1rm=max(estimates) if estimates else None,
                rir_set_count=sum(trend.rir_set_count for trend in trends),
                trend=_sparkline(tuple(trend.estimated_1rm for trend in trends)),
            )
        )
    return tuple(summaries)


def _duration_summary(
    sessions: dict[tuple[date, str], list[Decimal]], warnings: list[str]
) -> tuple[int, Decimal]:
    sessions_with_duration = 0
    total_duration = Decimal("0")
    conflicting_durations = 0
    for durations in sessions.values():
        if not durations:
            continue
        unique = set(durations)
        conflicting_durations += len(unique) > 1
        sessions_with_duration += 1
        total_duration += max(unique)
    if conflicting_durations:
        warnings.append(
            f"{conflicting_durations} workout session(s) had conflicting duration values; "
            "the longest value was used once per session."
        )
    return sessions_with_duration, total_duration


def _append_coverage_warnings(
    warnings: list[str],
    blocks: tuple[SheetOptions, ...],
    annotations: DashboardAnnotations,
    record_count: int,
    rir_set_count: int,
) -> None:
    undated_blocks = sum(
        annotations.blocks.get(block.name, BlockAnnotation()).start_date is None
        for block in blocks
    )
    if undated_blocks:
        warnings.append(
            f"{undated_blocks} block(s) have no confirmed start date; their workouts "
            "remain visible by calendar week but are not assigned to a block."
        )
    if rir_set_count == 0:
        warnings.append(
            "No completed sets include RIR; history summaries use performance and workload only."
        )
    elif rir_set_count < record_count:
        warnings.append(
            f"RIR is recorded for {rir_set_count} of {record_count} completed sets; "
            "it remains descriptive and does not adjust estimated 1RM."
        )


def _block_summaries(
    blocks: tuple[SheetOptions, ...],
    annotations: DashboardAnnotations,
    result_counts: dict[str, tuple[int, int]],
    aggregation: _HistoryAggregation,
) -> tuple[BlockSummary, ...]:
    summaries: list[BlockSummary] = []
    for position, block in enumerate(blocks):
        annotation = annotations.blocks.get(block.name, BlockAnnotation())
        completed, programmed = result_counts[block.name]
        annotated_week_count = sum(
            week.status != "normal"
            or week.reason != "unspecified"
            or bool(week.affected_movements)
            or bool(week.notes)
            for week in annotation.weeks.values()
        )
        summaries.append(
            BlockSummary(
                name=block.name,
                position=position,
                week_labels=_ordered_week_labels(
                    tuple(week.label for week in block.weeks)
                ),
                completed_results=completed,
                programmed_results=programmed,
                block_type=annotation.block_type,
                start_date=annotation.start_date,
                annotated_week_count=annotated_week_count,
                mapped_set_count=aggregation.block_sets.get(block.name, 0),
                mapped_training_days=len(aggregation.block_days.get(block.name, set())),
            )
        )
    return tuple(summaries)


def build_history_dashboard(
    export_path: str | Path,
    workbook_path: str | Path,
    config: BridgeConfig,
    annotations: DashboardAnnotations | None = None,
) -> HistoryDashboard:
    annotation_state = annotations or DashboardAnnotations()
    sources = _load_history_sources(export_path, workbook_path, config)
    warnings = (
        [f"{len(sources.imported.skipped_rows)} malformed export row(s) were excluded."]
        if sources.imported.skipped_rows
        else []
    )
    marker_text = (
        normalize_name(config.empty_day_marker.text)
        if config.empty_day_marker is not None
        else ""
    )
    result_counts = _block_result_counts(
        sources.workbook, sources.blocks, marker_text
    )
    intervals, overlapping = _dated_block_intervals(
        sources.blocks, annotation_state, warnings
    )
    aggregation = _aggregate_history(
        sources.records, source_rule_index(config), intervals, overlapping
    )
    weekly_trends = _weekly_trends(aggregation.trend_data)
    duration_session_count, total_duration = _duration_summary(
        aggregation.sessions, warnings
    )
    _append_coverage_warnings(
        warnings,
        sources.blocks,
        annotation_state,
        len(sources.records),
        aggregation.rir_set_count,
    )
    return HistoryDashboard(
        first_workout=min(record.workout_date for record in sources.records),
        last_workout=max(record.workout_date for record in sources.records),
        set_count=len(sources.records),
        workout_count=len(aggregation.sessions),
        training_day_count=len(aggregation.training_days),
        rir_set_count=aggregation.rir_set_count,
        duration_session_count=duration_session_count,
        total_duration_seconds=total_duration,
        blocks=_block_summaries(
            sources.blocks, annotation_state, result_counts, aggregation
        ),
        exercises=_exercise_summaries(weekly_trends),
        weekly_trends=weekly_trends,
        warnings=tuple(warnings),
    )


def option_label(options: tuple[tuple[str, str], ...], value: str) -> str:
    return dict(options).get(value, value)


def decimal_text(value: Decimal | None, *, places: int = 1) -> str:
    if value is None:
        return "—"
    quantum = Decimal("1") if places == 0 else Decimal("1").scaleb(-places)
    rounded = value.quantize(quantum)
    if rounded == rounded.to_integral():
        return str(int(rounded))
    return format(rounded, "f")


def duration_text(seconds: Decimal) -> str:
    total_minutes = int((seconds / Decimal("60")).quantize(Decimal("1")))
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
