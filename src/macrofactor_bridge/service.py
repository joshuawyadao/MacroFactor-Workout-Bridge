from __future__ import annotations

import errno
import os
import re
import shutil
import tempfile
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import DecimalException
from pathlib import Path

from .config import load_config, normalize_name, part_one_config_fingerprint, source_rule_index
from .formatting import format_sets, format_superset
from .importers import load_exercise_log_with_diagnostics, load_exercise_notes
from .models import (
    BridgeConfig,
    BridgeReport,
    EmptyDayMarker,
    ExerciseRule,
    ProposedWrite,
    ResultCorrection,
    SetRecord,
)
from .ooxml import WorkbookError, file_sha256, split_cell_reference, validate_copy_integrity
from .workbook import (
    ProgramDay,
    TargetRow,
    program_days,
    select_sheet_options,
    select_sheet_with_snapshot,
    target_rows,
)


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
    correction_review: dict[str, object] | None = None


def _source_name_and_superset(value: str) -> tuple[str, str | None]:
    match = SUPERSET_MARKER.search(value)
    if not match:
        return value.strip(), None
    return value[: match.start()].strip(), match.group(1).upper()


def _review_result_correction(
    correction: ResultCorrection,
    records: list[SetRecord],
    original_value: str,
    cell: str,
) -> dict[str, object]:
    expected = [(normalize_name(item.set_type), item.weight, item.reps)
                for item in correction.expected_sets]
    logged = [(normalize_name(item.set_type), item.weight, item.reps) for item in records]
    finite = all(value is None or value.is_finite()
                 for item in records for value in (item.weight, item.reps))
    return {
        "status": "matched" if finite and logged == expected else "withheld",
        "date": correction.workout_date.isoformat(),
        "workout": correction.workout,
        "exercise": correction.exercise,
        "cell": cell,
        "source_rows": [item.source_row for item in records],
        "original_value": original_value,
        "corrected_value": correction.value,
        "reason": correction.reason,
    }


def _record_correction_outcomes(
    report: BridgeReport,
    pieces: list[_FormattedTarget],
    status: str,
    review_reason: str | None = None,
) -> None:
    for piece in pieces:
        if piece.correction_review is not None:
            entry = {**piece.correction_review, "status": status}
            if review_reason:
                entry["review_reason"] = review_reason
            report.result_corrections.append(entry)


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


def _empty_day_marker_target(day: ProgramDay) -> TargetRow | None:
    substantive_rows = [
        row
        for row in day.rows
        if normalize_name(row.exercise_name) not in {"general warm up", "general warmup"}
    ]
    if any(
        row.result is not None and not row.result.is_empty
        for row in substantive_rows
    ):
        return None
    candidates = [
        row for row in substantive_rows if row.result is not None and row.result.is_empty
    ]
    if not candidates:
        candidates = [
            row for row in day.rows if row.result is not None and row.result.is_empty
        ]
    return candidates[0] if candidates else None


def _append_empty_day_markers(
    report: BridgeReport,
    marker: EmptyDayMarker,
    days: tuple[ProgramDay, ...],
    matched_cells: set[str],
) -> None:
    for day in days:
        if any(row.result_cell in matched_cells for row in day.rows):
            continue
        target = _empty_day_marker_target(day)
        if target is None:
            continue
        review_note = (
            f"{day.label} has no matched MacroFactor session in the selected dates; "
            "review this highlighted marker before sharing"
        )
        report.proposed_writes.append(
            ProposedWrite(
                sheet=report.sheet,
                week=report.week,
                cell=target.result_cell,
                value=marker.text,
                source_exercises=(),
                kind="empty_day_marker",
                fill_color=marker.fill_color,
                review_note=review_note,
            )
        )
        report.empty_day_markers.append(
            {
                "day": day.label,
                "cell": target.result_cell,
                "value": marker.text,
                "fill_color": marker.fill_color,
                "reason": review_note,
            }
        )
    report.proposed_writes.sort(key=lambda proposal: split_cell_reference(proposal.cell))


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
    source_hash = file_sha256(workbook_path)
    export_hash = file_sha256(export_path)
    config_fingerprint = part_one_config_fingerprint(config)
    _check_mapping(config, config.source_path, config_fingerprint)
    export_is_xlsx = Path(export_path).suffix.lower() == ".xlsx"
    # CSV has no notes and keeps the ordinary single-argument import path.
    imported_log = (
        load_exercise_log_with_diagnostics(export_path, include_notes=True)
        if export_is_xlsx
        else load_exercise_log_with_diagnostics(export_path)
    )
    records = imported_log.records
    exercise_notes = load_exercise_notes(
        export_path,
        _preloaded_notes=imported_log.exercise_notes if export_is_xlsx else None,
    )
    package, sheet, options, week, snapshot = select_sheet_with_snapshot(
        workbook_path, config, sheet_name, week_label
    )
    report = BridgeReport(
        input_export=str(Path(export_path)),
        input_workbook=str(Path(workbook_path)),
        sheet=sheet_name,
        week=week.label,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        rows_read=len(records) + len(imported_log.skipped_rows),
        preview_source_hash=source_hash,
        preview_export_hash=export_hash,
        preview_config_fingerprint=config_fingerprint,
        preview_config_path=config.source_path,
    )
    report.skipped_rows.extend(imported_log.skipped_rows)
    corrections = {
        (item.workout_date, normalize_name(item.workout), normalize_name(item.exercise)): item
        for item in config.result_corrections
    }
    logged_sessions: dict[tuple[date, str, str], list[SetRecord]] = defaultdict(list)
    valid: list[SetRecord] = []
    invalid_numeric: list[SetRecord] = []
    for record in records:
        if not from_date <= record.workout_date <= to_date:
            continue
        report.rows_in_range += 1
        source_name, _ = _source_name_and_superset(record.exercise)
        logged_sessions[(record.workout_date, normalize_name(record.workout), normalize_name(source_name))].append(record)
        if not record.exercise:
            report.skipped_rows.append({"row": record.source_row, "reason": "missing exercise"})
            continue
        invalid_fields = [field for field in ("weight", "reps")
                          if (value := getattr(record, field)) is not None and not value.is_finite()]
        if invalid_fields:
            invalid_numeric.append(record)
            for field in invalid_fields:
                report.skipped_rows.append({
                    "row": record.source_row, "exercise": record.exercise,
                    "field": field, "value": str(getattr(record, field)),
                    "reason": f"nonfinite {field}; affected result cell withheld for review",
                })
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
    coach_rows = target_rows(package, sheet, options, week, snapshot=snapshot)
    coach_index: dict[str, list] = defaultdict(list)
    for row in coach_rows:
        coach_index[normalize_name(row.exercise_name)].append(row)
    invalid_cells: set[str] = set()
    for record in invalid_numeric:
        name, _ = _source_name_and_superset(record.exercise)
        rule = source_index.get(normalize_name(name))
        if rule is not None:
            invalid_cells.update(row.result_cell for row in _matching_coach_rows(rule, coach_index).values())

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
        try:
            formatted = format_sets(exercise_records, rule)
        except (ValueError, DecimalException) as exc:
            invalid_cells.add(target.result_cell)
            report.ambiguous_matches.append({
                "exercise": source_name, "cell": target.result_cell,
                "reason": f"Result cannot be formatted safely: {exc}",
            })
            continue
        if not formatted:
            report.skipped_rows.append(
                {"exercise": source_name, "reason": "no completed sets remained after filtering"}
            )
            continue
        session_key = (exercise_records[0].workout_date, normalize_name(exercise_records[0].workout), key)
        correction = corrections.get(session_key)
        correction_review = None
        if correction is not None:
            correction_review = _review_result_correction(
                correction, logged_sessions[session_key], formatted, target.result_cell
            )
            alias_keys = {normalize_name(alias) for alias in rule.source_aliases}
            uncertain_rows = [item for item in imported_log.skipped_rows
                              if not item.get("exercise") or normalize_name(
                                  _source_name_and_superset(str(item["exercise"]))[0]
                              ) in alias_keys]
            if uncertain_rows:
                correction_review["status"] = "withheld"
                correction_review["uncertain_source_rows"] = uncertain_rows
            if correction_review["status"] == "withheld":
                reason = (
                    "Skipped source rows prevent verifying reviewed result correction; affected result withheld"
                    if uncertain_rows else
                    "Reviewed result correction source sets changed; affected result withheld for review"
                )
                correction_review["review_reason"] = reason
                report.result_corrections.append(correction_review)
                report.ambiguous_matches.append({"exercise": source_name, "cell": target.result_cell, "reason": reason})
                invalid_cells.add(target.result_cell)
                continue
            formatted = correction.value
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
                correction_review=correction_review,
            )
        )

    by_target: dict[str, list[_FormattedTarget]] = defaultdict(list)
    for target in formatted_targets:
        by_target[target.target_cell].append(target)
    for cell_reference, pieces in sorted(by_target.items(), key=lambda item: split_cell_reference(item[0])):
        if cell_reference in invalid_cells:
            _record_correction_outcomes(report, pieces, "withheld", "Another mapped source for this target is invalid")
            report.ambiguous_matches.append({
                "cell": cell_reference,
                "reason": "Result withheld because a mapped set or conversion has invalid numeric values",
            })
            continue
        cell = snapshot.cells[cell_reference]
        if not cell.is_empty:
            _record_correction_outcomes(report, pieces, "withheld", "Target result cell is occupied")
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
            if any(piece.correction_review is not None for piece in pieces):
                reason = "Reviewed result corrections require a single source exercise per target"
                _record_correction_outcomes(report, pieces, "withheld", reason)
                report.ambiguous_matches.append({"cell": cell_reference, "reason": reason})
                continue
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
            except (ValueError, DecimalException) as exc:
                report.ambiguous_matches.append(
                    {
                        "cell": cell_reference,
                        "reason": str(exc),
                        "exercises": [piece.source_name for piece in pieces],
                    }
                )
                continue
        _record_correction_outcomes(report, pieces, "applied")
        report.proposed_writes.append(
            ProposedWrite(
                sheet=sheet_name,
                week=week.label,
                cell=cell_reference,
                value=combined,
                source_exercises=tuple(piece.source_name for piece in pieces),
                review_note=(
                    f"Reviewed result correction: {pieces[0].correction_review['reason']}"
                    if pieces[0].correction_review is not None else None
                ),
            )
        )
    reviewed_scopes = {
        (item["date"], normalize_name(str(item["workout"])), normalize_name(str(item["exercise"])))
        for item in report.result_corrections
    }
    for correction in config.result_corrections:
        scope = (correction.workout_date.isoformat(), normalize_name(correction.workout), normalize_name(correction.exercise))
        if from_date <= correction.workout_date <= to_date and scope not in reviewed_scopes:
            report.result_corrections.append({
                "status": "not_applied", "date": correction.workout_date.isoformat(),
                "workout": correction.workout, "exercise": correction.exercise, "cell": None,
                "source_rows": [], "original_value": None, "corrected_value": correction.value,
                "reason": correction.reason,
                "review_reason": "No eligible exact workout/exercise match in selected dates; correction not applied",
            })
    marker = config.empty_day_marker
    uncertain_absence = any(
        (
            report.unmatched_exercises,
            report.ambiguous_matches,
            report.zero_rep_rows,
            report.skipped_rows,
            any(item["status"] != "applied" for item in report.result_corrections),
        )
    )
    if marker is not None and valid and not uncertain_absence:
        _append_empty_day_markers(
            report,
            marker,
            program_days(
                package, sheet, options, week,
                snapshot=snapshot, discovered_rows=coach_rows,
            ),
            set(by_target),
        )
    _check_preview_inputs(report, config)
    return report


def _check_mapping(config: BridgeConfig, path: str | None, expected: str) -> None:
    if part_one_config_fingerprint(config) != expected:
        raise WorkbookError("Mapping changed since preview; create a new preview")
    if path:
        try:
            current = part_one_config_fingerprint(load_config(path))
        except (OSError, ValueError) as exc:
            raise WorkbookError("Cannot verify reviewed mapping; create a new preview") from exc
        if current != expected:
            raise WorkbookError("Mapping changed since preview; create a new preview")


def _check_preview_inputs(report: BridgeReport, config: BridgeConfig) -> None:
    if not all((report.preview_source_hash, report.preview_export_hash, report.preview_config_fingerprint)):
        raise WorkbookError("Reviewed input fingerprints are missing; create a new preview")
    for path, expected, label in (
        (report.input_workbook, report.preview_source_hash, "Source workbook"),
        (report.input_export, report.preview_export_hash, "MacroFactor export"),
    ):
        try:
            current = file_sha256(path)
        except OSError as exc:
            raise WorkbookError(f"Cannot verify {label.lower()}; create a new preview") from exc
        if current != expected:
            raise WorkbookError(f"{label} changed since preview; create a new preview")
    _check_mapping(config, report.preview_config_path, report.preview_config_fingerprint)


def _is_published_file(output: Path, created: os.stat_result) -> bool:
    try:
        return os.path.samestat(output.stat(follow_symlinks=False), created)
    except OSError:
        return False


@contextmanager
def _publish_candidate(candidate: Path, output: Path):
    """Publish exclusively and remove only our output if copying or verification fails."""
    created = None
    try:
        candidate_identity = candidate.stat()
        try:
            os.link(candidate, output)
        except OSError as exc:
            if exc.errno not in {errno.EPERM, errno.EACCES, errno.ENOTSUP,
                                 errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV}:
                raise
            # Some external/network filesystems cannot link files. The candidate
            # is already validated; exclusive creation still protects collisions.
            with candidate.open("rb") as source, output.open("xb") as destination:
                created = os.fstat(destination.fileno())
                shutil.copyfileobj(source, destination)
        else:
            created = candidate_identity
        yield created
    except BaseException as exc:
        if created is not None and _is_published_file(output, created):
            try:
                output.unlink()
            except OSError:
                pass
        if isinstance(exc, FileExistsError):
            raise WorkbookError(f"Output already exists; choose a new path: {output}") from exc
        raise


def apply_changes(
    report: BridgeReport,
    config: BridgeConfig,
    output_path: str | Path,
) -> BridgeReport:
    if not report.proposed_writes:
        raise WorkbookError("There are no proposed writes; output workbook was not created")
    _check_preview_inputs(report, config)
    output = Path(output_path)
    if output.suffix.lower() != ".xlsx":
        raise WorkbookError("Output path must end in .xlsx")
    for path in (report.input_workbook, report.input_export, report.preview_config_path, config.source_path):
        if path and output.resolve() == Path(path).resolve():
            raise WorkbookError("Output path must be different from the source workbook, export and mapping")
    if output.exists() or output.is_symlink():
        raise WorkbookError(f"Output already exists; choose a new path: {output}")
    package, sheet, _, _ = select_sheet_options(
        report.input_workbook, config, report.sheet, report.week
    )
    changes = {proposal.cell: proposal.value for proposal in report.proposed_writes}
    highlight_fills = {
        proposal.cell: proposal.fill_color
        for proposal in report.proposed_writes
        if proposal.fill_color is not None
    }
    changed_members = {sheet.path}
    if highlight_fills:
        changed_members.add("xl/styles.xml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bridge-", dir=output.parent) as staging:
        candidate = Path(staging) / "candidate.xlsx"
        package.write_copy(candidate, sheet, changes, highlight_fills)
        validation = validate_copy_integrity(report.input_workbook, candidate, changed_members)
        if validation["unrelated_members_changed"]:
            raise WorkbookError("Workbook integrity check found unrelated changed ZIP members")
        if not validation["zip_members_identical"]:
            raise WorkbookError("Workbook integrity check found a changed ZIP member list")
        _check_preview_inputs(report, config)
        output_hash = file_sha256(candidate)
        with _publish_candidate(candidate, output) as created:
            _check_preview_inputs(report, config)
            if not _is_published_file(output, created) or file_sha256(output) != output_hash:
                raise WorkbookError("Output changed during publication; create a new preview")
    report.source_hash_before = report.source_hash_after = report.preview_source_hash
    report.export_hash_before = report.export_hash_after = report.preview_export_hash
    report.output_file = str(output)
    report.output_hash = output_hash
    report.validation = validation
    return report
