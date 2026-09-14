from __future__ import annotations

from pathlib import Path

from .coach_program import parse_coach_program
from .models import BridgeConfig
from .ooxml import file_sha256
from .program_models import ProgramIssue, ProgramPreviewReport


def build_program_preview(
    workbook_path: str | Path,
    config: BridgeConfig,
    sheet_name: str,
    block_identifier: str,
    included_weeks: tuple[str, ...],
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
    report.issues.append(
        ProgramIssue(
            severity="blocking",
            code="direct_program_export_required",
            message=(
                "Provide a fresh .xlsx created through MacroFactor Program Settings > "
                "Export Program before generator schema work can begin"
            ),
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
