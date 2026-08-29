from __future__ import annotations

import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import normalize_name, source_rule_index
from .formatting import format_sets, format_superset
from .importers import load_exercise_log, load_exercise_notes
from .models import BridgeConfig, BridgeReport, ExerciseRule, ProposedWrite, SetRecord
from .ooxml import WorkbookError, file_sha256, split_cell_reference, validate_copy_integrity
from .workbook import TargetRow, select_sheet_options, target_rows


SUPERSET_MARKER = re.compile(r"\s*∈\s*(SS\d+)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class _FormattedTarget:
    rule: ExerciseRule
    source_name: str
    value: str
    target_cell: str
    target_name: str
    superset_key: str | None
    first_row: int
    records: tuple[SetRecord, ...]


def _source_name_and_superset(value: str) -> tuple[str, str | None]:
    match = SUPERSET_MARKER.search(value)
    if not match:
        return value.strip(), None
    return value[: match.start()].strip(), match.group(1).upper()


def _matching_coach_rows(
    rule: ExerciseRule, coach_index: dict[str, list[TargetRow]]
) -> dict[str, TargetRow]:
    matching_rows: list[TargetRow] = []
    for alias in rule.coach_aliases:
        matching_rows.extend(coach_index.get(normalize_name(alias), []))
    unique_rows = {row.exercise_cell: row for row in matching_rows}
    if not rule.coach_context_aliases:
        return unique_rows
    context_keys = {normalize_name(alias) for alias in rule.coach_context_aliases}
    return {
        cell: row
        for cell, row in unique_rows.items()
        if context_keys.intersection(normalize_name(value) for value in row.context_values)
    }


def build_preview(
    export_path: str | Path,
    workbook_path: str | Path,
    config: BridgeConfig,
    sheet_name: str,
    week_label: str,
    from_date: date,
    to_date: date,
) -> BridgeReport:
    if to_date < from_date:
        raise ValueError("to-date must be on or after from-date")
    records = load_exercise_log(export_path)
    exercise_notes = load_exercise_notes(export_path)
    package, sheet, options, week = select_sheet_options(
        workbook_path, config, sheet_name, week_label
    )
    report = BridgeReport(
        input_export=str(Path(export_path)),
        input_workbook=str(Path(workbook_path)),
        sheet=sheet_name,
        week=week.label,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        rows_read=len(records),
    )
    valid: list[SetRecord] = []
    for record in records:
        if not from_date <= record.workout_date <= to_date:
            continue
        report.rows_in_range += 1
        if not record.exercise:
            report.skipped_rows.append({"row": record.source_row, "reason": "missing exercise"})
            continue
        if record.reps is None:
            report.skipped_rows.append(
                {"row": record.source_row, "exercise": record.exercise, "reason": "missing reps"}
            )
            continue
        if record.reps <= 0:
            report.zero_rep_rows.append(
                {"row": record.source_row, "exercise": record.exercise, "reps": str(record.reps)}
            )
            continue
        if not record.set_type:
            report.skipped_rows.append(
                {"row": record.source_row, "exercise": record.exercise, "reason": "missing set type"}
            )
            continue
        valid.append(record)

    source_index = source_rule_index(config)
    coach_rows = target_rows(package, sheet, options, week)
    coach_index: dict[str, list] = defaultdict(list)
    for row in coach_rows:
        coach_index[normalize_name(row.exercise_name)].append(row)

    grouped: OrderedDict[str, list[SetRecord]] = OrderedDict()
    source_names: dict[str, str] = {}
    source_supersets: dict[str, str | None] = {}
    for record in valid:
        base_name, superset = _source_name_and_superset(record.exercise)
        key = normalize_name(base_name)
        grouped.setdefault(key, []).append(record)
        source_names.setdefault(key, base_name)
        if source_supersets.get(key) not in (None, superset) and superset is not None:
            report.ambiguous_matches.append(
                {"exercise": base_name, "reason": "multiple superset markers in selected range"}
            )
        source_supersets.setdefault(key, superset)

    for note in exercise_notes:
        base_name, _ = _source_name_and_superset(note.exercise)
        if normalize_name(base_name) not in grouped:
            continue
        report.exercise_notes.append(
            {
                "exercise": base_name,
                "note": note.note,
                "sheet": note.sheet,
                "row": note.source_row,
                "behavior": "reported for review; not written into the coach result cell",
            }
        )

    formatted_targets: list[_FormattedTarget] = []
    for key, exercise_records in grouped.items():
        source_name = source_names[key]
        rule = source_index.get(key)
        if rule is None:
            report.unmatched_exercises.append(
                {"exercise": source_name, "reason": "no exact configured source alias"}
            )
            continue
        sessions = {(record.workout_date, record.workout) for record in exercise_records}
        if len(sessions) > 1:
            report.ambiguous_matches.append(
                {
                    "exercise": source_name,
                    "reason": "exercise appears in multiple workout sessions in the selected range",
                    "sessions": [f"{day.isoformat()} | {workout}" for day, workout in sorted(sessions)],
                }
            )
            continue
        unique_rows = _matching_coach_rows(rule, coach_index)
        if not unique_rows:
            report.unmatched_exercises.append(
                {
                    "exercise": source_name,
                    "canonical": rule.canonical,
                    "reason": (
                        "no exact configured coach alias and row context on selected worksheet"
                        if rule.coach_context_aliases
                        else "no exact configured coach alias on selected worksheet"
                    ),
                }
            )
            continue
        if len(unique_rows) > 1:
            report.ambiguous_matches.append(
                {
                    "exercise": source_name,
                    "canonical": rule.canonical,
                    "reason": "configured coach alias matches multiple worksheet rows",
                    "cells": sorted(unique_rows),
                }
            )
            continue
        target = next(iter(unique_rows.values()))
        if target.result is None:
            report.skipped_rows.append(
                {
                    "exercise": source_name,
                    "cell": target.result_cell,
                    "reason": "target result cell does not exist; refusing to create an unstyled cell",
                }
            )
            continue
        formatted = format_sets(exercise_records, rule)
        if not formatted:
            report.skipped_rows.append(
                {"exercise": source_name, "reason": "no completed sets remained after filtering"}
            )
            continue
        formatted_targets.append(
            _FormattedTarget(
                rule=rule,
                source_name=source_name,
                value=formatted,
                target_cell=target.result_cell,
                target_name=target.exercise_name,
                superset_key=rule.superset_group or source_supersets.get(key),
                first_row=min(record.source_row for record in exercise_records),
                records=tuple(exercise_records),
            )
        )

    by_target: dict[str, list[_FormattedTarget]] = defaultdict(list)
    for target in formatted_targets:
        by_target[target.target_cell].append(target)
    snapshot = package.sheet_snapshot(sheet)
    for cell_reference, pieces in sorted(by_target.items(), key=lambda item: split_cell_reference(item[0])):
        cell = snapshot.cells[cell_reference]
        if not cell.is_empty:
            report.occupied_cells.append(
                {
                    "cell": cell_reference,
                    "exercise": pieces[0].target_name,
                    "existing_value": cell.value,
                    "has_formula": cell.formula is not None,
                }
            )
            continue
        if len(pieces) == 1:
            combined = pieces[0].value
        else:
            keys = {piece.superset_key for piece in pieces}
            if len(keys) != 1 or None in keys:
                report.ambiguous_matches.append(
                    {
                        "cell": cell_reference,
                        "reason": "multiple exercises map to one target without one shared superset group",
                        "exercises": [piece.source_name for piece in pieces],
                    }
                )
                continue
            pieces.sort(key=lambda piece: (piece.rule.superset_order, piece.first_row))
            try:
                combined = format_superset(
                    [(list(piece.records), piece.rule) for piece in pieces]
                )
            except ValueError as exc:
                report.ambiguous_matches.append(
                    {
                        "cell": cell_reference,
                        "reason": str(exc),
                        "exercises": [piece.source_name for piece in pieces],
                    }
                )
                continue
        report.proposed_writes.append(
            ProposedWrite(
                sheet=sheet_name,
                week=week.label,
                cell=cell_reference,
                value=combined,
                source_exercises=tuple(piece.source_name for piece in pieces),
            )
        )
    return report


def apply_changes(
    report: BridgeReport,
    config: BridgeConfig,
    output_path: str | Path,
) -> BridgeReport:
    if not report.proposed_writes:
        raise WorkbookError("There are no proposed writes; output workbook was not created")
    package, sheet, _, _ = select_sheet_options(
        report.input_workbook, config, report.sheet, report.week
    )
    source_hash = file_sha256(report.input_workbook)
    export_hash = file_sha256(report.input_export)
    changes = {proposal.cell: proposal.value for proposal in report.proposed_writes}
    package.write_copy(output_path, sheet, changes)
    after_hash = file_sha256(report.input_workbook)
    export_after_hash = file_sha256(report.input_export)
    if after_hash != source_hash:
        raise WorkbookError("Source workbook changed during apply; stop and restore from backup")
    if export_after_hash != export_hash:
        raise WorkbookError("MacroFactor export changed during apply; stop and restore from backup")
    report.source_hash_before = source_hash
    report.source_hash_after = after_hash
    report.export_hash_before = export_hash
    report.export_hash_after = export_after_hash
    report.output_file = str(Path(output_path))
    report.output_hash = file_sha256(output_path)
    report.validation = validate_copy_integrity(
        report.input_workbook, output_path, sheet.path
    )
    if report.validation["unrelated_members_changed"]:
        raise WorkbookError("Workbook integrity check found unrelated changed ZIP members")
    if not report.validation["zip_members_identical"]:
        raise WorkbookError("Workbook integrity check found a changed ZIP member list")
    return report
