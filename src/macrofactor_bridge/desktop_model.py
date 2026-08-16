from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import load_config
from .importers import load_exercise_log
from .models import BridgeReport
from .workbook import discover_workbook


@dataclass(frozen=True)
class ReviewSection:
    title: str
    count: int
    details: tuple[str, ...]


def bundled_config_path() -> Path:
    """Return the bundled example mapping in source and frozen-app layouts."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        path = Path(frozen_root) / "config" / "exercises.example.json"
    else:
        path = Path(__file__).resolve().parents[2] / "config" / "exercises.example.json"
    if not path.is_file():
        raise FileNotFoundError(f"Bundled exercise mapping was not found: {path}")
    return path


def copy_mapping(source: str | Path, destination: str | Path) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    if destination_path.suffix.lower() != ".json":
        raise ValueError("Exercise mapping filename must end in .json")
    if destination_path.exists():
        raise FileExistsError(f"Mapping already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)
    return destination_path


def discover_sheet_weeks(
    workbook_path: str | Path, config_path: str | Path
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    config = load_config(config_path)
    return tuple(
        (sheet.name, tuple(week.label for week in sheet.weeks))
        for sheet in discover_workbook(workbook_path, config)
        if sheet.exercise_column is not None and sheet.weeks
    )


def latest_export_week(export_path: str | Path) -> tuple[date, date]:
    records = load_exercise_log(export_path)
    if not records:
        raise ValueError("The MacroFactor export contains no workout rows")
    latest = max(record.workout_date for record in records)
    monday = latest - timedelta(days=latest.weekday())
    return monday, monday + timedelta(days=6)


def default_output_path(
    workbook_path: str | Path, week_label: str, *, reserved: set[Path] | None = None
) -> Path:
    source = Path(workbook_path)
    safe_week = re.sub(r"[^A-Za-z0-9]+", "-", week_label.strip()).strip("-").lower()
    safe_week = safe_week or "results"
    blocked = {path.resolve() for path in (reserved or set())}
    candidate = source.with_name(f"{source.stem}-{safe_week}-results.xlsx")
    suffix = 2
    while candidate.exists() or candidate.resolve() in blocked or candidate.resolve() == source.resolve():
        candidate = source.with_name(f"{source.stem}-{safe_week}-results-{suffix}.xlsx")
        suffix += 1
    return candidate


def review_sections(report: BridgeReport) -> tuple[ReviewSection, ...]:
    categories = (
        ("Unmatched exercises", report.unmatched_exercises),
        ("Ambiguous matches", report.ambiguous_matches),
        ("Zero-rep rows", report.zero_rep_rows),
        ("Occupied cells", report.occupied_cells),
        ("Other skipped data", report.skipped_rows),
    )
    sections: list[ReviewSection] = []
    for title, entries in categories:
        details = tuple(
            ", ".join(f"{key}: {value}" for key, value in entry.items())
            for entry in entries
        )
        sections.append(ReviewSection(title=title, count=len(entries), details=details))
    return tuple(sections)


def review_text(report: BridgeReport) -> str:
    lines = [
        f"{len(report.proposed_writes)} proposed workbook change(s)",
        f"{report.rows_in_range} of {report.rows_read} export row(s) in the selected dates",
        "",
    ]
    for section in review_sections(report):
        lines.append(f"{section.title}: {section.count}")
        lines.extend(f"  • {detail}" for detail in section.details)
        lines.append("")
    lines.append("A missing workout is never interpreted as skipped.")
    return "\n".join(lines)
