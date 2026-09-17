"""Read-only alignment of two blocks using the dashboard's existing metrics."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import zip_longest

from .history import (
    BlockAnnotation, BlockSummary, DashboardAnnotations, HistoryDashboard,
    WeekAnnotation, WeeklyExerciseTrend,
)


METRICS = (
    ("Estimated 1RM (lb)", "estimated_1rm"),
    ("Top weight (lb)", "top_weight"),
    ("Logged sets", "set_count"),
    ("Training days", "training_days"),
)


class ComparisonError(ValueError):
    """The selected blocks cannot be aligned without guessing."""


@dataclass(frozen=True)
class ComparisonWeek:
    relative_week: int
    label: str
    start: date
    end: date
    trend: WeeklyExerciseTrend | None
    coverage: str
    context: WeekAnnotation | None

    def metric(self, name: str) -> Decimal | None:
        if name not in {key for _, key in METRICS}:
            raise ComparisonError(f"Unknown comparison metric: {name}")
        if self.trend is None:
            return None
        value = getattr(self.trend, name)
        return Decimal(value) if value is not None else None


@dataclass(frozen=True)
class BlockSeries:
    block: BlockSummary
    notes: str
    weeks: tuple[ComparisonWeek, ...]


@dataclass(frozen=True)
class BlockComparison:
    exercise: str
    first: BlockSeries
    second: BlockSeries

    def paired_weeks(self) -> tuple[tuple[ComparisonWeek | None, ComparisonWeek | None], ...]:
        return tuple(zip_longest(self.first.weeks, self.second.weeks))


def _validated_block(dashboard: HistoryDashboard, name: str) -> BlockSummary:
    block = next((item for item in dashboard.blocks if item.name == name), None)
    if block is None:
        raise ComparisonError("Choose a block from the loaded workbook.")
    if block.start_date is None:
        raise ComparisonError(f"{name}: confirm its start date in Private block and week context.")
    if block.start_date.weekday() != 0:
        raise ComparisonError(f"{name}: comparison requires a confirmed Monday start; dates were not shifted.")
    if name in dashboard.overlapping_blocks:
        raise ComparisonError(f"{name}: its dates overlap another block. Correct the saved dates first.")
    if not block.week_labels or len({label.casefold() for label in block.week_labels}) != len(block.week_labels):
        raise ComparisonError(f"{name}: select distinct weeks using a private week layout first.")
    return block


def _series(
    dashboard: HistoryDashboard, annotations: DashboardAnnotations,
    exercise: str, block: BlockSummary,
) -> BlockSeries:
    annotation = annotations.blocks.get(block.name, BlockAnnotation())
    trends = {
        trend.week_start: trend for trend in dashboard.trends_for(exercise)
        if trend.block_name == block.name
    }
    assert block.start_date is not None
    weeks = []
    for index, label in enumerate(block.week_labels):
        start = block.start_date + timedelta(weeks=index)
        end = start + timedelta(days=6)
        trend = trends.get(start)
        # Keep absence separate from a real zero and never infer a skipped workout.
        coverage = "Logged sets" if trend is not None else "No logged sets"
        if end < dashboard.first_workout or start > dashboard.last_workout:
            coverage = "Outside export date range"
        elif start < dashboard.first_workout or end > dashboard.last_workout:
            coverage += " (partial date range)"
        weeks.append(ComparisonWeek(index + 1, label, start, end, trend, coverage,
                                    annotation.weeks.get(label)))
    return BlockSeries(block, annotation.notes, tuple(weeks))


def compare_blocks(
    dashboard: HistoryDashboard, annotations: DashboardAnnotations,
    exercise: str, first_name: str, second_name: str,
) -> BlockComparison:
    if first_name == second_name:
        raise ComparisonError("Choose two different blocks to compare.")
    if not any(item.exercise == exercise for item in dashboard.exercises):
        raise ComparisonError("Choose an exercise from the loaded export.")
    first = _validated_block(dashboard, first_name)
    second = _validated_block(dashboard, second_name)
    return BlockComparison(exercise, _series(dashboard, annotations, exercise, first),
                           _series(dashboard, annotations, exercise, second))
