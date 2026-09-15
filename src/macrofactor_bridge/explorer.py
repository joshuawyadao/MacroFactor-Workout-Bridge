"""Read-only exercise-first views over existing weekly history metrics."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .history import HistoryDashboard, WeeklyExerciseTrend


# Navigation families only: never combine these movements into one strength series.
LIFT_FAMILIES = {
    "Squat": ("Barbell Back Squat", "High Bar Back Squat", "Pause Back Squat",
              "Tempo Back Squat", "Bottoms Up Pin Squat", "Safety Squat Bar Squat"),
    "Bench": ("Barbell Bench Press", "Pause Barbell Bench Press", "Tempo Bench Press",
              "Close Grip Bench Press", "Feet-Up Barbell Bench Press"),
    "Deadlift": ("Conventional Deadlift", "Sumo Deadlift", "Pause Conventional Deadlift",
                 "Pause Sumo Deadlift"),
}


@dataclass(frozen=True)
class ExplorerWeek:
    start: date
    trend: WeeklyExerciseTrend | None

    def metric(self, name: str) -> Decimal | None:
        if name not in ("estimated_1rm", "top_weight", "set_count", "training_days"):
            raise ValueError(f"Unknown trend metric: {name}")
        value = getattr(self.trend, name) if self.trend else None
        return Decimal(value) if value is not None else None


def exercise_names(dashboard: HistoryDashboard, family: str = "All exercises", query: str = "") -> tuple[str, ...]:
    allowed = LIFT_FAMILIES.get(family)
    return tuple(summary.exercise for summary in dashboard.exercises
                 if (allowed is None or summary.exercise in allowed)
                 and query.strip().casefold() in summary.exercise.casefold())


def default_exercise(dashboard: HistoryDashboard, names: tuple[str, ...]) -> str:
    """Most recently logged variation, with stable alphabetical tie-breaking."""
    latest = {name: max(t.week_start for t in dashboard.trends_for(name)) for name in names}
    return min(names, key=lambda name: (-latest[name].toordinal(), name.casefold())) if names else ""


def exercise_timeline(dashboard: HistoryDashboard, exercise: str, recent_weeks: int = 0) -> tuple[ExplorerWeek, ...]:
    if recent_weeks < 0:
        raise ValueError("The week count cannot be negative")
    if not any(s.exercise == exercise for s in dashboard.exercises):
        return ()
    end = dashboard.last_workout - timedelta(days=dashboard.last_workout.weekday())
    start = dashboard.first_workout - timedelta(days=dashboard.first_workout.weekday())
    if recent_weeks:
        start = max(start, end - timedelta(weeks=recent_weeks - 1))
    trends = {trend.week_start: trend for trend in dashboard.trends_for(exercise)}
    return tuple(ExplorerWeek(start + timedelta(weeks=i), trends.get(start + timedelta(weeks=i)))
                 for i in range((end - start).days // 7 + 1))


def best_estimate(dashboard: HistoryDashboard, exercise: str, block: str) -> Decimal | None:
    estimates = [t.estimated_1rm for t in dashboard.trends_for(exercise)
                 if t.block_name == block and t.estimated_1rm is not None]
    return max(estimates) if estimates else None


def week_location(dashboard: HistoryDashboard, week: ExplorerWeek) -> tuple[str, str]:
    if week.trend:
        return week.trend.block_name or "Unmapped", week.trend.block_week or "—"
    # Calendar context is allowed for missing logs, but never fabricate performance.
    candidates = [b for b in dashboard.blocks if b.start_date and b.start_date.weekday() == 0
                  and b.name not in dashboard.overlapping_blocks
                  and b.start_date <= week.start < b.start_date + timedelta(weeks=len(b.week_labels))]
    if len(candidates) == 1:
        block = candidates[0]
        return block.name, block.week_labels[(week.start - block.start_date).days // 7]
    return "Unmapped", "—"
