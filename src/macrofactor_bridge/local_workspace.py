from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .desktop_model import bundled_config_path
from .importers import load_exercise_log
from .ooxml import XlsxPackage, file_sha256
from .workbook import discover_workbook


DIRECTORIES = (
    "inbox/coach",
    "inbox/macrofactor",
    "archive/coach",
    "archive/macrofactor",
    "generated/workbooks",
    "generated/reports",
    "manifests",
)


class LocalWorkspaceError(ValueError):
    """Raised when local input files cannot be safely validated or archived."""


def setup_workspace(root: str | Path) -> tuple[Path, ...]:
    workspace = Path(root).resolve()
    created: list[Path] = []
    for relative in DIRECTORIES:
        directory = workspace / relative
        directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)
    return tuple(created)


def default_config_path() -> Path:
    local = Path.cwd() / "config" / "exercises.local.json"
    return local if local.is_file() else bundled_config_path()


def _safe_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return safe or "input"


def _validate_coach(path: Path, config_path: Path) -> dict[str, Any]:
    package = XlsxPackage(path)
    config = load_config(config_path)
    discovered = discover_workbook(path, config)
    sheets = [
        {
            "name": sheet.name,
            "exercise_header": sheet.exercise_header_cell,
            "weeks": [week.label for week in sheet.weeks],
        }
        for sheet in discovered
    ]
    usable = [sheet for sheet in sheets if sheet["exercise_header"] and sheet["weeks"]]
    return {
        "type": "coach_workbook",
        "sheet_count": len(package.sheets),
        "usable_sheet_count": len(usable),
        "sheets": sheets,
        "warnings": [] if usable else ["No worksheet matched the configured exercise/week headers"],
    }


def _validate_export(path: Path) -> dict[str, Any]:
    records = load_exercise_log(path)
    if not records:
        raise LocalWorkspaceError("MacroFactor export contains no exercise-log rows")
    dates = [record.workout_date for record in records]
    exercises = sorted({record.exercise for record in records if record.exercise})
    return {
        "type": "macrofactor_export",
        "row_count": len(records),
        "first_workout": min(dates).isoformat(),
        "last_workout": max(dates).isoformat(),
        "exercise_count": len(exercises),
    }


def _candidate_files(directory: Path) -> tuple[Path, ...]:
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and not path.name.startswith(".")
            ),
            key=lambda path: path.name.casefold(),
        )
    )


def _archive_copy(
    source: Path,
    archive_directory: Path,
    digest: str,
    date_label: str,
) -> tuple[Path, bool]:
    suffix = source.suffix.lower()
    hash_label = digest[:12]
    existing = sorted(archive_directory.glob(f"*--{hash_label}{suffix}"))
    for candidate in existing:
        if file_sha256(candidate) == digest:
            return candidate, True

    base = f"{date_label}--{_safe_stem(source.stem)}--{hash_label}"
    destination = archive_directory / f"{base}{suffix}"
    counter = 2
    while destination.exists():
        destination = archive_directory / f"{base}-{counter}{suffix}"
        counter += 1
    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle)
    if file_sha256(destination) != digest:
        raise LocalWorkspaceError(f"Archived copy failed hash validation: {destination}")
    return destination, False


def archive_inbox(
    root: str | Path,
    config_path: str | Path | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    workspace = Path(root).resolve()
    setup_workspace(workspace)
    config = Path(config_path).resolve() if config_path else default_config_path().resolve()
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    date_label = timestamp.date().isoformat()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "ingested_at": timestamp.isoformat(),
        "workspace": str(workspace),
        "config": {"path": str(config), "sha256": file_sha256(config)},
        "entries": [],
        "errors": [],
    }
    categories = (
        (
            "coach",
            workspace / "inbox" / "coach",
            workspace / "archive" / "coach",
            {".xlsx"},
            lambda path: _validate_coach(path, config),
        ),
        (
            "macrofactor",
            workspace / "inbox" / "macrofactor",
            workspace / "archive" / "macrofactor",
            {".csv", ".xlsx"},
            _validate_export,
        ),
    )
    for kind, inbox, archive, allowed, validator in categories:
        for source in _candidate_files(inbox):
            if source.suffix.lower() not in allowed:
                manifest["errors"].append(
                    {
                        "kind": kind,
                        "source": str(source),
                        "error": f"Unsupported file type {source.suffix or '(none)'}",
                    }
                )
                continue
            try:
                source_hash = file_sha256(source)
                validation = validator(source)
                archived, deduplicated = _archive_copy(
                    source, archive, source_hash, date_label
                )
            except (OSError, ValueError) as exc:
                manifest["errors"].append(
                    {"kind": kind, "source": str(source), "error": str(exc)}
                )
                continue
            manifest["entries"].append(
                {
                    "kind": kind,
                    "source": str(source),
                    "archive": str(archived),
                    "sha256": source_hash,
                    "bytes": source.stat().st_size,
                    "deduplicated": deduplicated,
                    "validation": validation,
                }
            )
    manifest_name = timestamp.strftime("%Y%m%dT%H%M%S%fZ") + "--ingest.json"
    manifest_path = workspace / "manifests" / manifest_name
    with manifest_path.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    manifest["manifest"] = str(manifest_path)
    return manifest


def latest_archives(root: str | Path) -> dict[str, dict[str, Any] | None]:
    workspace = Path(root).resolve()
    latest: dict[str, dict[str, Any] | None] = {"coach": None, "macrofactor": None}
    manifests = workspace / "manifests"
    if not manifests.is_dir():
        return latest
    for path in sorted(manifests.glob("*--ingest.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ingested_at = payload.get("ingested_at", "")
        for entry in payload.get("entries", []):
            kind = entry.get("kind")
            if kind not in latest:
                continue
            candidate = {**entry, "ingested_at": ingested_at, "manifest": str(path)}
            current = latest[kind]
            if current is None or candidate["ingested_at"] >= current["ingested_at"]:
                latest[kind] = candidate
    return latest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macrofactor-workspace",
        description="Set up and archive private MacroFactor/coach input files safely.",
    )
    parser.add_argument("--root", default="local-data", help="Local workspace directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Create the private local directory structure")
    archive = commands.add_parser("archive", help="Validate and archive files currently in inbox")
    archive.add_argument("--config", help="Exercise mapping used for coach-workbook discovery")
    commands.add_parser("status", help="Show the newest archived coach and MacroFactor inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "setup":
            directories = setup_workspace(args.root)
            print(f"Local workspace ready: {Path(args.root).resolve()}")
            for directory in directories:
                print(f"  {directory}")
            return 0
        if args.command == "archive":
            manifest = archive_inbox(args.root, args.config)
            print(f"Manifest: {manifest['manifest']}")
            for entry in manifest["entries"]:
                action = "reused" if entry["deduplicated"] else "archived"
                print(f"  {action} {entry['kind']}: {entry['archive']}")
            for error in manifest["errors"]:
                print(f"  error {error['kind']}: {error['source']} — {error['error']}", file=sys.stderr)
            return 2 if manifest["errors"] else 0
        status = latest_archives(args.root)
        for kind in ("coach", "macrofactor"):
            entry = status[kind]
            if entry is None:
                print(f"{kind}: no archived input")
            else:
                print(f"{kind}: {entry['archive']} ({entry['ingested_at']})")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
