from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import ConfigError, load_config
from .coach_program import discover_program_blocks
from .importers import ImportError
from .ooxml import WorkbookError
from .program_service import build_program_preview, generate_program
from .program_batch import run_program_batch
from .service import apply_changes, build_preview
from .workbook import discover_workbook


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _select(label: str, options: list[str]) -> str:
    if not options:
        raise WorkbookError(f"No {label.lower()} options were discovered")
    print(f"Select {label.lower()}:")
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")
    while True:
        try:
            selection = int(input(f"{label} [1-{len(options)}]: "))
        except (ValueError, EOFError):
            print("Enter one of the listed numbers.", file=sys.stderr)
            continue
        if 1 <= selection <= len(options):
            return options[selection - 1]
        print("Enter one of the listed numbers.", file=sys.stderr)


def _resolve_selection(args, config):
    options = discover_workbook(args.workbook, config)
    usable = [sheet for sheet in options if sheet.exercise_column is not None and sheet.weeks]
    sheet_name = args.sheet or _select("Worksheet", [sheet.name for sheet in usable])
    matches = [sheet for sheet in usable if sheet.name == sheet_name]
    if not matches:
        raise WorkbookError(f"Worksheet is not available for transfer: {sheet_name!r}")
    week_label = args.week or _select("Week", [week.label for week in matches[0].weeks])
    return sheet_name, week_label


def _validate_report_path(
    path: str | None, *, reserved: tuple[str | None, ...]
) -> Path | None:
    if not path:
        return None
    output = Path(path)
    resolved = output.resolve(strict=False)
    for reserved_path in reserved:
        if reserved_path and resolved == Path(reserved_path).resolve(strict=False):
            raise FileExistsError(f"Report path is reserved input or output: {output}")
    if output.exists():
        raise FileExistsError(f"Report path already exists: {output}")
    return output


def _write_report(
    path: str | None, report, *, reserved: tuple[str | None, ...] = ()
) -> None:
    output = _validate_report_path(path, reserved=reserved)
    if output is None:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as report_file:
        report_file.write(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")


def _print_report(report, mode: str) -> None:
    print(f"{mode}: {report.sheet} | {report.week} | {report.from_date} to {report.to_date}")
    print(f"Rows read: {report.rows_read}; rows in range: {report.rows_in_range}")
    print(f"Proposed writes: {len(report.proposed_writes)}")
    for proposal in report.proposed_writes:
        source = ", ".join(proposal.source_exercises) or proposal.review_note or proposal.kind
        print(f"  {proposal.cell}: {proposal.value} ({source})")
    print(
        "Reported: "
        f"{len(report.unmatched_exercises)} unmatched, "
        f"{len(report.ambiguous_matches)} ambiguous, "
        f"{len(report.zero_rep_rows)} zero-rep, "
        f"{len(report.occupied_cells)} occupied, "
        f"{len(report.skipped_rows)} other skipped, "
        f"{len(report.exercise_notes)} exercise notes, "
        f"{len(report.empty_day_markers)} empty-day review markers"
    )
    if report.output_file:
        print(f"Output: {report.output_file}")
        print(f"Coach source unchanged: {report.source_hash_before == report.source_hash_after}")
        print(f"MacroFactor export unchanged: {report.export_hash_before == report.export_hash_after}")
        print(
            "Unrelated workbook parts unchanged: "
            f"{not report.validation.get('unrelated_members_changed', ['unknown'])}"
        )


def _resolve_program_selection(args, config):
    blocks = discover_program_blocks(args.workbook, config)
    usable = [block for block in blocks if block.week_labels]
    sheet_name = args.sheet or _select(
        "Worksheet", list(dict.fromkeys(block.sheet for block in usable))
    )
    sheet_blocks = [block for block in usable if block.sheet == sheet_name]
    block_id = args.block or _select(
        "Program block",
        [
            f"{block.identifier} ({len(block.day_labels)} days)"
            for block in sheet_blocks
        ],
    ).split(" ", 1)[0]
    matches = [block for block in sheet_blocks if block.identifier == block_id]
    if len(matches) != 1:
        raise WorkbookError(
            f"Program block is not available on worksheet {sheet_name!r}: {block_id!r}"
        )
    weeks = tuple(args.week or ())
    if not weeks:
        weeks = (matches[0].week_labels if config.program.prescription_source == "base"
                 else (_select("Week", list(matches[0].week_labels)),))
    return sheet_name, block_id, weeks


def _print_program_report(report) -> None:
    print(
        f"Program preview: {report.sheet} | {report.block} | "
        f"{', '.join(report.included_weeks)}"
    )
    if report.program is not None:
        print(f"Prescription source: {report.program.prescription_source}; "
              f"{len(report.program.cycles)} cycle(s). {report.program.cycle_name}")
        print(f"Program appearance: color={report.program.color or 'preserve template'}; "
              f"icon={report.program.icon or 'preserve template'} (configured overrides)")
        print(
            f"Discovered: {len(report.program.days)} day(s), "
            f"{sum(len(day.exercises) for day in report.program.days)} exercise mapping(s)"
        )
        for day in report.program.days:
            print(f"  {day.label}" + (f" -> {day.export_name}" if day.export_name and day.export_name != day.label else ""))
            for exercise in day.exercises:
                mapped = exercise.macrofactor_name or "unmapped"
                flags = [exercise.mapping_status]
                if exercise.custom_exercise:
                    flags.append("custom")
                if exercise.excluded:
                    flags.append("excluded")
                print(f"    {exercise.coach_name} -> {mapped} ({', '.join(flags)})")
                if exercise.expansion:
                    expansion = exercise.expansion
                    print(f"      Sequential expansion {expansion.child_order}/{expansion.child_count} "
                          f"from {exercise.source_cell}: {expansion.sets_each} sets for this exercise; no superset")
                for prescription in exercise.prescriptions:
                    rep_value = (
                        "missing"
                        if prescription.rep_min.value is None
                        else (
                            str(prescription.rep_min.value)
                            if prescription.rep_min.value == prescription.rep_max.value
                            else f"{prescription.rep_min.value}-{prescription.rep_max.value}"
                        )
                    )
                    rest_value = (
                        "missing"
                        if prescription.rest_seconds.value is None
                        else f"{prescription.rest_seconds.value}s"
                    )
                    if prescription.rep_min.value is not None and prescription.rep_max.value is None:
                        rep_value = f"{prescription.rep_min.value}+ (maximum unset)"
                    if prescription.set_rep_targets:
                        rep_value = ", ".join(f"{target.minimum.value}-{target.maximum.value}"
                                              for target in prescription.set_rep_targets)
                    fields = (
                        f"sets={prescription.set_count.value or 'missing'} "
                        f"[{prescription.set_count.source}], "
                        f"type={prescription.set_type.value or 'missing'} "
                        f"[{prescription.set_type.source}], "
                        f"reps={rep_value} [{prescription.rep_min.source}], "
                        f"RIR={prescription.rir.value if prescription.rir.value is not None else 'missing'} "
                        f"[{prescription.rir.source}], "
                        f"rest={rest_value} [{prescription.rest_seconds.source}]"
                    )
                    print(f"      {prescription.cycle}: {fields}")
                    if prescription.set_types:
                        print("        ordered set types: " + ", ".join(
                            f"{index}: {field.value} [{field.source}]"
                            for index, field in enumerate(prescription.set_types, start=1)
                        ))
                    if prescription.raw_unparsed_text:
                        print(f"        review raw text: {prescription.raw_unparsed_text}")
                    if prescription.notes:
                        print("        export notes: " + " / ".join(prescription.notes))
    blockers = report.blocking_issues
    warnings = [issue for issue in report.issues if issue.severity == "warning"]
    print(
        f"Review: {len(blockers)} blocking item(s), {len(warnings)} warning(s), "
        f"{len(report.skipped_items)} skipped item(s)"
    )
    for item in report.skipped_items:
        print(
            f"  [skipped] {item.get('day')}: {item.get('exercise')} "
            f"({item.get('reason')})"
        )
    for issue in report.issues:
        location = issue.cell or issue.day or report.sheet
        print(f"  [{issue.severity}] {issue.code} at {location}: {issue.message}")
        if issue.raw_text:
            print(f"    raw text: {issue.raw_text}")
    print(f"Coach source unchanged: {report.source_hash_before == report.source_hash_after}")
    print(f"Source hash: {report.source_hash_before}")
    print(f"Template hash: {report.template_hash or 'not available'}")
    print(f"Generation safe: {'yes' if report.generation_safe else 'no'}")
    if report.output_file:
        print(f"Output: {report.output_file}")
        print(
            "Template unchanged: "
            f"{report.template_hash == report.template_hash_after}"
        )
        print(
            "Unrelated template parts unchanged: "
            f"{not report.validation.get('unrelated_members_changed', ['unknown'])}"
        )
        print("Manual MacroFactor import verified: no")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macrofactor-bridge",
        description=(
            "Safely transfer MacroFactor results to a coach workbook, or review and "
            "generate a coach program for manual MacroFactor import."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="List discovered worksheets and weeks")
    inspect_parser.add_argument("--workbook", required=True)
    inspect_parser.add_argument("--config", required=True)

    for command in ("preview", "apply"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--export", required=True)
        command_parser.add_argument("--workbook", required=True)
        command_parser.add_argument("--config", required=True)
        command_parser.add_argument("--sheet")
        command_parser.add_argument("--week")
        command_parser.add_argument("--from-date", required=True, type=_date)
        command_parser.add_argument("--to-date", required=True, type=_date)
        command_parser.add_argument("--report", help="Optional JSON report path")
        if command == "apply":
            command_parser.add_argument("--output", required=True)

    program_inspect = subparsers.add_parser(
        "program-inspect",
        help="Part 2: list coach program blocks and structurally separated plan weeks",
    )
    program_inspect.add_argument("--workbook", required=True)
    program_inspect.add_argument("--config", required=True)

    program_preview = subparsers.add_parser(
        "program-preview",
        help="Part 2: parse and review a coach program without generating a workbook",
    )
    program_preview.add_argument("--workbook", required=True)
    program_preview.add_argument("--config", required=True)
    program_preview.add_argument("--sheet")
    program_preview.add_argument("--block")
    program_preview.add_argument(
        "--week",
        action="append",
        help="Included week; repeat for multiple cycles. In base mode, all repeat the base table",
    )
    program_preview.add_argument(
        "--template",
        help="Optional direct MacroFactor Export Program .xlsx used for safety checks",
    )
    program_preview.add_argument("--report", help="Optional private JSON report path")

    program_generate = subparsers.add_parser(
        "program-generate",
        help="Part 2: generate a structurally validated workbook for manual import",
    )
    program_generate.add_argument("--workbook", required=True)
    program_generate.add_argument("--config", required=True)
    program_generate.add_argument("--template", required=True)
    program_generate.add_argument("--output", required=True)
    program_generate.add_argument("--sheet")
    program_generate.add_argument("--block")
    program_generate.add_argument(
        "--week",
        action="append",
        help="Included week; repeat for multiple cycles. In base mode, all repeat the base table",
    )
    program_generate.add_argument("--report", help="Optional private JSON report path")
    program_batch = subparsers.add_parser(
        "program-batch", help="Part 2: audit all remaining base programs and consolidate private exceptions",
    )
    program_batch.add_argument("--workbook", required=True)
    program_batch.add_argument("--config", required=True, help="Shared exact mappings and base-mode policies only")
    program_batch.add_argument("--template", required=True, help="Verified full-layout direct Export Program template")
    program_batch.add_argument("--output-dir", required=True, help="New private run directory; never overwrite an earlier run")
    program_batch.add_argument("--manifest", help="Private scoped configs/reference boundaries, start-after key, skips and declared import evidence")
    program_batch.add_argument("--generate", action="store_true", help="Generate only candidates passing source and output audits; otherwise preview only")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "program-batch":
            batch = run_program_batch(args.workbook, args.config, args.template, args.output_dir,
                                      manifest_path=args.manifest, generate=args.generate)
            for item in batch.results:
                print(f"{item['id']}: {item['sheet']} | {item['block'] or 'undiscovered'} | {item['status']}")
            print(f"Consolidated review items: {len(batch.review_items)}")
            print(f"Representative/manual imports requested: {len(batch.manual_import_plan['selected'])}")
            print(f"Inputs unchanged: {batch.inputs_unchanged}")
            print(f"Private review: {Path(batch.output_directory) / 'review.md'}")
            print("Automated checks do not mark any candidate manually imported.")
            return 0 if batch.inputs_unchanged and all(r["status"] in {"ready", "generated", "skipped"}
                                                       for r in batch.results) else 1
        report_reserved: tuple[str | None, ...] = ()
        if args.command in {"program-preview", "program-generate"}:
            report_reserved = (
                args.workbook,
                args.config,
                getattr(args, "template", None),
                getattr(args, "output", None),
            )
        elif args.command in {"preview", "apply"}:
            report_reserved = (
                args.export,
                args.workbook,
                args.config,
                getattr(args, "output", None),
            )
        _validate_report_path(
            getattr(args, "report", None),
            reserved=report_reserved,
        )
        config = load_config(args.config)
        if args.command == "inspect":
            for sheet in discover_workbook(args.workbook, config):
                status = sheet.exercise_header_cell or "no configured exercise header"
                print(f"{sheet.name} [{status}]")
                for week in sheet.weeks:
                    print(f"  {week.label} ({week.header_cell} -> result column {week.result_column})")
            return 0
        if args.command == "program-inspect":
            blocks = discover_program_blocks(args.workbook, config)
            if not blocks:
                raise WorkbookError("No coach program blocks were discovered")
            for block in blocks:
                print(
                    f"{block.sheet} | {block.identifier} | rows "
                    f"{block.start_row}-{block.end_row}"
                )
                print(f"  Days: {', '.join(block.day_labels)}")
                print(
                    "  Safely separated plan weeks: "
                    f"{', '.join(block.week_labels) or 'none'}"
                )
            return 0
        if args.command in {"program-preview", "program-generate"}:
            sheet_name, block_id, weeks = _resolve_program_selection(args, config)
            report = build_program_preview(
                args.workbook,
                config,
                sheet_name,
                block_id,
                weeks,
                template_path=args.template,
            )
            if args.command == "program-generate":
                report = generate_program(
                    report,
                    args.template,
                    args.output,
                )
            _write_report(
                args.report,
                report,
                reserved=report_reserved,
            )
            _print_program_report(report)
            return 0
        sheet_name, week_label = _resolve_selection(args, config)
        report = build_preview(
            args.export,
            args.workbook,
            config,
            sheet_name,
            week_label,
            args.from_date,
            args.to_date,
        )
        if args.command == "apply":
            report = apply_changes(report, config, args.output)
        _write_report(
            args.report,
            report,
            reserved=report_reserved,
        )
        _print_report(report, args.command.capitalize())
        return 0
    except (ConfigError, ImportError, WorkbookError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
