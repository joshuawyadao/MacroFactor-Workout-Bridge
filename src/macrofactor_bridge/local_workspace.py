from __future__ import annotations

import argparse
import json
import os
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
    "current",
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
    if not usable:
        raise LocalWorkspaceError(
            "Coach workbook has no worksheet matching the configured exercise and week headers"
        )
    return {
        "type": "coach_workbook",
        "sheet_count": len(package.sheets),
        "usable_sheet_count": len(usable),
        "sheets": sheets,
        "warnings": [],
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
    canonical_name: str,
) -> tuple[Path, bool]:
    suffix = source.suffix.lower()
    hash_label = digest[:12]
    destination = archive_directory / canonical_name
    if destination.exists():
        if file_sha256(destination) == digest:
            return destination, True
        raise LocalWorkspaceError(
            f"Canonical archive name already contains different data: {destination}"
        )

    existing = [
        candidate
        for candidate in sorted(archive_directory.glob(f"*--{hash_label}{suffix}"))
        if file_sha256(candidate) == digest
    ]
    for candidate in existing:
        if _has_upload_date_name(candidate.name):
            return candidate, True
    if existing:
        try:
            destination.hardlink_to(existing[0])
        except OSError:
            shutil.copy2(existing[0], destination)
        if file_sha256(destination) != digest:
            raise LocalWorkspaceError(
                f"Canonical archive link failed hash validation: {destination}"
            )
        return destination, True

    with source.open("rb") as input_handle, destination.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle)
    if file_sha256(destination) != digest:
        raise LocalWorkspaceError(f"Archived copy failed hash validation: {destination}")
    return destination, False


def _has_upload_date_name(name: str) -> bool:
    coach = r"^\d{4}-\d{2}-\d{2}--Coach-Program--"
    macrofactor = (
        r"^\d{4}-\d{2}-\d{2}--\d{4}-\d{2}-\d{2}_to_"
        r"\d{4}-\d{2}-\d{2}--MacroFactor-Exercise-Log--"
    )
    return bool(re.match(coach, name) or re.match(macrofactor, name))


def _canonical_archive_name(
    kind: str,
    source: Path,
    digest: str,
    date_label: str,
    validation: dict[str, Any],
) -> str:
    suffix = source.suffix.lower()
    hash_label = digest[:12]
    if kind == "coach":
        label = f"{date_label}--Coach-Program"
    else:
        first = validation["first_workout"]
        last = validation["last_workout"]
        label = f"{date_label}--{first}_to_{last}--MacroFactor-Exercise-Log"
    return f"{label}--{hash_label}{suffix}"


def _source_modified_at(source: Path) -> str:
    modified = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
    return modified.isoformat()


def _selected_entry(kind: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    if kind == "macrofactor":
        return max(
            entries,
            key=lambda entry: (
                entry["validation"]["last_workout"],
                entry["validation"]["first_workout"],
                entry["source_modified_at"],
            ),
        )
    return max(
        entries,
        key=lambda entry: (entry["source_modified_at"], entry["archive"]),
    )


def _replace_current_link(current: Path, archive: Path) -> None:
    if current.exists() and not current.is_symlink():
        raise LocalWorkspaceError(
            f"Refusing to replace a regular file in the managed current directory: {current}"
        )
    temporary = current.with_name(f".{current.name}.tmp-{file_sha256(archive)[:12]}")
    if temporary.exists() or temporary.is_symlink():
        if not temporary.is_symlink():
            raise LocalWorkspaceError(
                f"Refusing to replace an unexpected temporary file: {temporary}"
            )
        temporary.unlink()
    relative_target = os.path.relpath(archive, start=current.parent)
    temporary.symlink_to(relative_target)
    temporary.replace(current)


def _update_current_files(
    workspace: Path, entries: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    current_directory = workspace / "current"
    selected: dict[str, dict[str, Any]] = {}
    planned: list[tuple[str, dict[str, Any], Path, tuple[Path, ...]]] = []
    by_kind = {
        kind: [entry for entry in entries if entry["kind"] == kind]
        for kind in ("coach", "macrofactor")
    }
    for kind, candidates in by_kind.items():
        if not candidates:
            continue
        entry = _selected_entry(kind, candidates)
        archive = Path(entry["archive"])
        if kind == "coach":
            current = current_directory / "Coach Program - Current.xlsx"
            managed_paths = (current,)
        else:
            current = current_directory / (
                f"MacroFactor Exercise Log - Current{archive.suffix}"
            )
            managed_paths = tuple(
                current_directory / f"MacroFactor Exercise Log - Current{suffix}"
                for suffix in (".csv", ".xlsx")
            )
        planned.append((kind, entry, current, managed_paths))

    for _, _, _, managed_paths in planned:
        for managed in managed_paths:
            if (managed.exists() or managed.is_symlink()) and not managed.is_symlink():
                raise LocalWorkspaceError(
                    "Refusing to replace a regular file in the managed current directory: "
                    f"{managed}"
                )

    for kind, entry, current, managed_paths in planned:
        archive = Path(entry["archive"])
        if kind == "macrofactor":
            for alternate in managed_paths:
                if alternate == current or (
                    not alternate.exists() and not alternate.is_symlink()
                ):
                    continue
                alternate.unlink()
        _replace_current_link(current, archive)
        selected[kind] = {
            "current": str(current),
            "archive": entry["archive"],
            "sha256": entry["sha256"],
            "validation": entry["validation"],
        }
    return selected


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
        "schema_version": 2,
        "ingested_at": timestamp.isoformat(),
        "workspace": str(workspace),
        "config": {"path": str(config), "sha256": file_sha256(config)},
        "entries": [],
        "current": {},
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
                canonical_name = _canonical_archive_name(
                    kind, source, source_hash, date_label, validation
                )
                archived, deduplicated = _archive_copy(
                    source, archive, source_hash, canonical_name
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
                    "original_name": source.name,
                    "source_modified_at": _source_modified_at(source),
                    "archive": str(archived),
                    "sha256": source_hash,
                    "bytes": source.stat().st_size,
                    "deduplicated": deduplicated,
                    "validation": validation,
                }
            )
    try:
        manifest["current"] = _update_current_files(workspace, manifest["entries"])
    except (OSError, ValueError) as exc:
        manifest["errors"].append(
            {
                "kind": "current",
                "source": str(workspace / "current"),
                "error": str(exc),
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
        current_entries = payload.get("current")
        if isinstance(current_entries, dict) and current_entries:
            entries = [
                {"kind": kind, **entry}
                for kind, entry in current_entries.items()
                if isinstance(entry, dict)
            ]
        else:
            entries = payload.get("entries", [])
        for entry in entries:
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
                current = entry.get("current")
                location = current or entry["archive"]
                details = ""
                validation = entry.get("validation", {})
                if kind == "macrofactor" and validation.get("first_workout"):
                    details = (
                        f"; workouts {validation['first_workout']} to "
                        f"{validation['last_workout']}"
                    )
                print(f"{kind}: {location} ({entry['ingested_at']}{details})")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
