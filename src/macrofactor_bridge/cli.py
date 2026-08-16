from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import ConfigError, load_config
from .importers import ImportError
from .ooxml import WorkbookError
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


def _write_report(path: str | None, report) -> None:
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _print_report(report, mode: str) -> None:
    print(f"{mode}: {report.sheet} | {report.week} | {report.from_date} to {report.to_date}")
    print(f"Rows read: {report.rows_read}; rows in range: {report.rows_in_range}")
    print(f"Proposed writes: {len(report.proposed_writes)}")
    for proposal in report.proposed_writes:
        print(f"  {proposal.cell}: {proposal.value} ({', '.join(proposal.source_exercises)})")
    print(
        "Reported: "
        f"{len(report.unmatched_exercises)} unmatched, "
        f"{len(report.ambiguous_matches)} ambiguous, "
        f"{len(report.zero_rep_rows)} zero-rep, "
        f"{len(report.occupied_cells)} occupied, "
        f"{len(report.skipped_rows)} other skipped"
    )
    if report.output_file:
        print(f"Output: {report.output_file}")
        print(f"Coach source unchanged: {report.source_hash_before == report.source_hash_after}")
        print(f"MacroFactor export unchanged: {report.export_hash_before == report.export_hash_after}")
        print(
            "Unrelated workbook parts unchanged: "
            f"{not report.validation.get('unrelated_members_changed', ['unknown'])}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macrofactor-bridge",
        description="Safely preview and copy MacroFactor workout results into a coach workbook.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "inspect":
            for sheet in discover_workbook(args.workbook, config):
                status = sheet.exercise_header_cell or "no configured exercise header"
                print(f"{sheet.name} [{status}]")
                for week in sheet.weeks:
                    print(f"  {week.label} ({week.header_cell} -> result column {week.result_column})")
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
        _write_report(args.report, report)
        _print_report(report, args.command.capitalize())
        return 0
    except (ConfigError, ImportError, WorkbookError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
