from __future__ import annotations

from pathlib import Path

from .coach_program import parse_coach_program
from .models import BridgeConfig
from .ooxml import WorkbookError, file_sha256, split_cell_reference
from .program_audit import audit_program_source_rows
from .program_models import ProgramIssue, ProgramPreviewReport
from .program_identity import verify_program_exercise_names
from .program_output_audit import audit_program_output
from .program_template import (
    bind_template_durations,
    inspect_program_template,
    prepare_program_schema,
    template_generation_issues,
    write_program_from_template,
)


def program_name_reference_paths(config: BridgeConfig) -> tuple[str, ...]:
    base = Path(config.source_path).parent if config.source_path else Path.cwd()
    return tuple(str((base / path).resolve()) for path in config.program.exercise_name_references)


def _references_unchanged(report: ProgramPreviewReport) -> bool:
    try:
        return all(file_sha256(path) == digest
                   for path, digest in report.exercise_name_reference_hashes.items())
    except OSError:
        return False


def _resolved_native_time_rep_issue(issue: ProgramIssue, report: ProgramPreviewReport) -> bool:
    """Retire only a parser rep omission resolved by the exact native set evidence."""
    if (issue.code != "missing_prescription_field"
        or issue.message not in {
            "No supported minimum reps value was provided",
            "No supported maximum reps value was provided",
        }
        or issue.sheet != report.sheet or report.program is None):
        return False
    try:
        issue_row = split_cell_reference(issue.cell)[0] if issue.cell else None
    except WorkbookError:
        return False
    matches = [
        (exercise, prescription)
        for day in report.program.days if day.label == issue.day
        for exercise in day.exercises
        if not exercise.excluded and exercise.coach_name == issue.exercise
        and (issue_row is None or exercise.source_row == issue_row)
        for prescription in exercise.prescriptions if prescription.cycle == issue.cycle
    ]
    if len(matches) != 1:
        return False
    exercise, prescription = matches[0]
    targets = prescription.set_duration_targets
    return bool(
        not exercise.raw_base_fields.get("reps")
        and prescription.duration_seconds is None
        and prescription.rep_min.value is None and prescription.rep_max.value is None
        and prescription.rep_min.source == prescription.rep_max.source == "blank_by_policy"
        and not prescription.set_rep_targets
        and type(prescription.set_count.value) is int
        and prescription.set_count.value > 0
        and len(targets) == prescription.set_count.value
        and all(target.source == "native_template" for target in targets)
        and all(type(target.value) is int and target.value > 0 for target in targets)
    )


def build_program_preview(
    workbook_path: str | Path,
    config: BridgeConfig,
    sheet_name: str,
    block_identifier: str,
    included_weeks: tuple[str, ...],
    template_path: str | Path | None = None,
    *,
    reference_boundary_marker: str | None = None,
) -> ProgramPreviewReport:
    source = Path(workbook_path)
    before_hash = file_sha256(source)
    parsed = parse_coach_program(
        source,
        config,
        sheet_name,
        block_identifier,
        included_weeks,
    )
    after_hash = file_sha256(source)
    report = ProgramPreviewReport(
        input_workbook=str(source),
        sheet=sheet_name,
        block=block_identifier,
        included_weeks=tuple(cycle.label for cycle in parsed.program.cycles),
        program=parsed.program,
        issues=list(parsed.issues),
        skipped_items=list(parsed.skipped_items),
        source_hash_before=before_hash,
        source_hash_after=after_hash,
        resize_template_workouts=config.program.resize_template_workouts,
    )
    if before_hash != after_hash:
        report.issues.append(
            ProgramIssue(
                severity="blocking",
                code="source_changed_during_preview",
                message="Coach workbook changed during preview; run preview again",
                sheet=sheet_name,
            )
        )
    report.issues.extend(audit_program_source_rows(
        source, config, report, reference_boundary_marker=reference_boundary_marker,
    ))
    after_hash = file_sha256(source)
    report.source_hash_after = after_hash
    if before_hash != after_hash and not any(issue.code == "source_changed_during_preview" for issue in report.issues):
        report.issues.append(ProgramIssue(
            severity="blocking", code="source_changed_during_preview",
            message="Coach workbook changed during preview; run preview again", sheet=sheet_name,
        ))
    included_exercises = [
        exercise
        for day in parsed.program.days
        for exercise in day.exercises
        if not exercise.excluded
    ]
    if not included_exercises:
        report.issues.append(
            ProgramIssue(
                severity="blocking",
                code="no_included_exercises",
                message="The selected program contains no included exercises",
                sheet=sheet_name,
            )
        )
    if template_path is None:
        report.issues.append(
            ProgramIssue(
                severity="blocking",
                code="direct_program_export_required",
                message=(
                    "Provide a fresh .xlsx created through MacroFactor Program Settings > "
                    "Export Program before generation"
                ),
                sheet=sheet_name,
            )
        )
    else:
        template = Path(template_path)
        report.template_workbook = str(template)
        report.template_hash = file_sha256(template)
        try:
            schema = inspect_program_template(template)
            report.program = bind_template_durations(report.program, template, schema)
            schema = prepare_program_schema(
                template, schema, report.program,
                resize_workouts=report.resize_template_workouts,
            )
        except WorkbookError as exc:
            report.issues.append(
                ProgramIssue(
                    severity="blocking",
                    code="invalid_program_template",
                    message=str(exc),
                    sheet=sheet_name,
                )
            )
        else:
            report.template_schema_verified = True
            report.issues = [issue for issue in report.issues
                             if not _resolved_native_time_rep_issue(issue, report)]
            name_issues, verification, hashes = verify_program_exercise_names(
                report.program, template, program_name_reference_paths(config),
            )
            report.issues.extend(name_issues)
            report.exercise_name_verification = verification
            report.exercise_name_reference_hashes = hashes
            report.issues.extend(
                template_generation_issues(
                    report.program,
                    schema,
                    sheet_name=sheet_name,
                )
            )
        report.template_hash_after = file_sha256(template)
        if report.template_hash != report.template_hash_after:
            report.issues.append(
                ProgramIssue(
                    severity="blocking",
                    code="template_changed_during_preview",
                    message="MacroFactor template changed during preview; run preview again",
                    sheet=sheet_name,
                )
            )
    report.generation_safe = bool(
        report.template_schema_verified
        and included_exercises
        and not report.blocking_issues
        and before_hash == after_hash
    )
    return report


def generate_program(
    report: ProgramPreviewReport,
    template_path: str | Path,
    output_path: str | Path,
) -> ProgramPreviewReport:
    if not report.generation_safe or report.program is None:
        raise WorkbookError("Program preview contains blocking items; generation is refused")
    source = Path(report.input_workbook)
    template = Path(template_path)
    output = Path(output_path)
    if output.resolve(strict=False) in {
        source.resolve(strict=False),
        template.resolve(strict=False),
        *(Path(path).resolve(strict=False) for path in report.exercise_name_reference_hashes),
    }:
        raise WorkbookError("Output path must differ from both input workbooks")
    if file_sha256(source) != report.source_hash_after:
        raise WorkbookError("Coach workbook changed after preview; run preview again")
    if file_sha256(template) != report.template_hash_after:
        raise WorkbookError("MacroFactor template changed after preview; run preview again")
    if not _references_unchanged(report):
        raise WorkbookError("Exercise-name reference changed after preview; run preview again")
    if not report.exercise_name_reference_hashes:
        raise WorkbookError("Native exercise-name evidence is required; run preview again")
    name_issues, _, _ = verify_program_exercise_names(
        report.program, template, tuple(report.exercise_name_reference_hashes),
    )
    if name_issues:
        raise WorkbookError("Exercise names no longer match native export evidence; run preview again")

    schema = inspect_program_template(template)
    validation = write_program_from_template(
        template, output, report.program, schema,
        resize_workouts=report.resize_template_workouts,
    )
    output_audit = audit_program_output(report.program, output, template)
    if not output_audit.passed:
        output.unlink(missing_ok=True)
        raise WorkbookError("Generated program failed independent output audit: " + "; ".join(output_audit.errors))
    validation["output_audit"] = output_audit.to_dict()
    source_after = file_sha256(source)
    template_after = file_sha256(template)
    if source_after != report.source_hash_before or template_after != report.template_hash or not _references_unchanged(report):
        output.unlink(missing_ok=True)
        raise WorkbookError("An input workbook changed during generation; output was removed")
    report.source_hash_after = source_after
    report.template_hash_after = template_after
    report.output_file = str(output)
    report.output_hash = file_sha256(output)
    report.validation = validation
    return report
