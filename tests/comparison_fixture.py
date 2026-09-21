"""Synthetic source files for two-block comparison and desktop tests."""

from datetime import date
from pathlib import Path

from macrofactor_bridge.history import (
    BlockAnnotation, DashboardAnnotations, WeekAnnotation, save_dashboard_annotations,
)
from tests.history_fixture import LAYOUT, irregular_workbook


def comparison_inputs(root: Path) -> tuple[Path, Path, Path]:
    coach, export, annotations = root / "coach.xlsx", root / "history.csv", root / "context.json"
    irregular_workbook(coach)
    export.write_text(
        "Date,Workout,Exercise,Set Type,Weight (lbs),Reps\n"
        "2026-07-27,Before,Unmapped Carry,Standard Set,50,10\n"
        "2026-08-03,Day A,Tempo Back Squat,Standard Set,200,5\n"
        "2026-08-09,Day B,Tempo Back Squat,Standard Set,210,3\n"
        "2026-08-10,Day A,Unmapped Carry,Standard Set,50,10\n"
        "2026-08-17,Day A,Tempo Back Squat,Standard Set,0,20\n"
        "2026-08-24,Day A,Tempo Back Squat,Standard Set,500,5\n"
        "2026-08-26,Day B,Unmapped Carry,Standard Set,50,10\n",
        encoding="utf-8",
    )
    save_dashboard_annotations(annotations, DashboardAnnotations({
        "Training Block": BlockAnnotation(
            block_type="strength", start_date=date(2026, 8, 3), week_layout=LAYOUT,
            notes="Synthetic strength block", weeks={
                "Week 10": WeekAnnotation(status="deload_reentry", reason="vacation", notes="Return after travel"),
                "Week 11": WeekAnnotation(notes="Confirmed skipped squat sessions"),
                "Week 12": WeekAnnotation(status="modified", reason="injury", affected_movements=("Squat",)),
            },
        ),
        "Archive": BlockAnnotation(block_type="volume_hypertrophy", start_date=date(2026, 8, 24)),
    }))
    return export, coach, annotations
