"""Read-only projections for the overview and aligned training timeline.

Date bounds describe observed exports, not proof of complete logging. Averages
exclude boundary weeks but count interior no-log weeks as zero logged workload.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .explorer import ExplorerWeek, week_location
from .history import (
    BlockSummary, DashboardAnnotations, HistoryDashboard, WEEK_REASON_OPTIONS,
    WEEK_STATUS_OPTIONS, option_label,
)


def calendar_weeks(dashboard: HistoryDashboard, recent_weeks: int = 0) -> tuple[date, ...]:
    if recent_weeks < 0:
        raise ValueError("The week count cannot be negative")
    start = dashboard.first_workout - timedelta(days=dashboard.first_workout.weekday())
    end = dashboard.last_workout - timedelta(days=dashboard.last_workout.weekday())
    if recent_weeks:
        start = max(start, end - timedelta(weeks=recent_weeks - 1))
    return tuple(start + timedelta(weeks=i) for i in range((end - start).days // 7 + 1))


def block_issue(dashboard: HistoryDashboard, block: BlockSummary) -> str:
    if block.start_date is None:
        return "Needs a start date"
    if block.start_date.weekday() != 0:
        return "Needs a Monday start"
    if not block.week_labels or len(set(block.week_labels)) != len(block.week_labels):
        return "Needs unique coach weeks"
    if block.name in dashboard.overlapping_blocks:
        return "Overlapping block dates"
    return ""


def block_weeks(block: BlockSummary) -> tuple[date, ...]:
    return tuple(block.start_date + timedelta(weeks=i) for i in range(len(block.week_labels))) if block.start_date else ()


def full_weeks(dashboard: HistoryDashboard, weeks: tuple[date, ...]) -> tuple[date, ...]:
    return tuple(w for w in weeks if dashboard.first_workout <= w and w + timedelta(days=6) <= dashboard.last_workout)


def week_context(dashboard: HistoryDashboard, annotations: DashboardAnnotations, start: date) -> str:
    block_name, week_name = week_location(dashboard, ExplorerWeek(start, None))
    block = annotations.blocks.get(block_name)
    context = block.weeks.get(week_name) if block else None
    if not context:
        return ""
    if context.status == "normal" and context.reason == "unspecified" and not context.notes and not context.affected_movements:
        return ""
    parts = [option_label(WEEK_STATUS_OPTIONS, context.status), option_label(WEEK_REASON_OPTIONS, context.reason)]
    if context.affected_movements:
        parts.append(", ".join(context.affected_movements))
    if context.notes:
        parts.append(context.notes)
    return " · ".join(parts)


def weekly_workload(dashboard: HistoryDashboard, weeks: tuple[date, ...]) -> tuple[Decimal | None, ...]:
    counts: dict[date, int] = {}
    for trend in dashboard.weekly_trends:
        counts[trend.week_start] = counts.get(trend.week_start, 0) + trend.set_count
    # An empty week is unavailable in charts (not a confirmed skipped week).
    return tuple(Decimal(counts[w]) if w in counts else None for w in weeks)


def sets_for_week(dashboard: HistoryDashboard, start: date, exercise: str = ""):
    return tuple(sorted((r for r in dashboard.records if start <= r.workout_date <= start + timedelta(days=6)
                         and (not exercise or r.exercise == exercise)),
                        key=lambda r: (r.workout_date, r.workout, r.source_row)))


def exercise_workload(dashboard: HistoryDashboard, weeks: tuple[date, ...]) -> tuple[tuple[str, Decimal], ...]:
    complete = full_weeks(dashboard, weeks)
    if not complete:
        return ()
    counts: dict[str, int] = {}
    for trend in dashboard.weekly_trends:
        if trend.week_start in complete:
            counts[trend.exercise] = counts.get(trend.exercise, 0) + trend.set_count
    return tuple(sorted(((name, Decimal(count) / len(complete)) for name, count in counts.items()),
                        key=lambda item: (-item[1], item[0].casefold())))


@dataclass(frozen=True)
class BlockReport:
    block: BlockSummary
    weeks: tuple[date, ...]
    complete_week_count: int
    sets_per_week: Decimal | None
    days_per_week: Decimal | None
    coverage: str
    issue: str

    def best_estimate(self, dashboard: HistoryDashboard, exercise: str) -> Decimal | None:
        if self.issue:
            return None
        values = [t.estimated_1rm for t in dashboard.trends_for(exercise)
                  if t.week_start in self.weeks and t.block_name == self.block.name and t.estimated_1rm is not None]
        return max(values) if values else None


def block_reports(dashboard: HistoryDashboard, recent_weeks: int = 0) -> tuple[BlockReport, ...]:
    selected = calendar_weeks(dashboard, recent_weeks)
    reports = []
    for block in sorted(dashboard.blocks, key=lambda b: (b.start_date is None, str(b.start_date), b.position)):
        issue = block_issue(dashboard, block)
        dates = block_weeks(block)
        visible = tuple(w for w in dates if w in selected) if not issue else ()
        if recent_weeks and not visible:
            continue
        complete = full_weeks(dashboard, visible)
        sets_average = days_average = None
        if complete:
            count = sum(t.set_count for t in dashboard.weekly_trends
                        if t.week_start in complete and t.block_name == block.name)
            sets_average = Decimal(count) / len(complete)
            days = {r.workout_date for r in dashboard.records
                    if r.workout_date - timedelta(days=r.workout_date.weekday()) in complete}
            days_average = Decimal(len(days)) / len(complete)
        if issue:
            coverage = issue
        elif not visible:
            coverage = "Outside export date range"
        elif dates[-1] + timedelta(days=6) > dashboard.last_workout:
            coverage = "Partial · export ends before block end"
        elif len(complete) < len(dates):
            coverage = "Partial · selected range / export boundary"
        else:
            coverage = "Within export date range"
        reports.append(BlockReport(block, visible, len(complete), sets_average, days_average, coverage, issue))
    return tuple(reports)
