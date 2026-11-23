"""Confirmed full and partial rep counts alongside an unchanged MacroFactor export."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .importers import load_exercise_log
from .models import SetRecord
from .ooxml import file_sha256


_IDENTITY = (
    "source_row", "workout_date", "workout", "exercise", "set_type",
    "weight", "exported_reps",
)
_ENTRY = frozenset((*_IDENTITY, "full_reps", "partial_reps"))


def rep_count_entry(record: SetRecord) -> dict[str, Any]:
    return {
        "source_row": record.source_row,
        "workout_date": record.workout_date.isoformat(),
        "workout": record.workout,
        "exercise": record.exercise,
        "set_type": record.set_type,
        "weight": str(record.weight) if record.weight is not None else None,
        "exported_reps": str(record.reps) if record.reps is not None else None,
        "full_reps": record.full_reps,
        "partial_reps": record.partial_reps,
    }


def needs_rep_confirmation(record: SetRecord) -> bool:
    reps = record.reps
    return bool(
        reps is not None and reps.is_finite() and reps > 0
        and reps != reps.to_integral_value()
        and (record.full_reps is None or record.partial_reps is None)
    )


def _valid_counts(entry: dict[str, Any], *, allow_empty: bool) -> bool:
    full, partial = entry["full_reps"], entry["partial_reps"]
    if allow_empty and full is None and partial is None:
        return False
    if type(full) is not int or type(partial) is not int:
        raise ValueError("Full and partial reps must both be nonnegative integers")
    if full < 0 or partial < 0 or full + partial == 0:
        raise ValueError("Full and partial reps must be nonnegative with a positive total")
    return True


def _record_index(records: Iterable[SetRecord]) -> dict[int, SetRecord]:
    indexed: dict[int, SetRecord] = {}
    for record in records:
        if type(record.source_row) is not int or record.source_row in indexed:
            raise ValueError("Export contains duplicate or invalid source rows")
        indexed[record.source_row] = record
    return indexed


def _validated_entries(
    entries: Any, records: dict[int, SetRecord], *, allow_empty: bool
) -> dict[int, dict[str, Any] | None]:
    if not isinstance(entries, list):
        raise ValueError("Rep counts sets must be a list")
    result: dict[int, dict[str, Any] | None] = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.keys() != _ENTRY:
            raise ValueError("Rep count entry has missing or unexpected fields")
        row = entry["source_row"]
        if type(row) is not int or row in result:
            raise ValueError("Rep counts contain a duplicate or invalid source row")
        record = records.get(row)
        if record is None:
            raise ValueError(f"Rep counts reference an unknown source row {row}")
        raw = rep_count_entry(record)
        if any(type(entry[key]) is not type(raw[key]) or entry[key] != raw[key] for key in _IDENTITY):
            raise ValueError(f"Rep counts have a stale raw identity at source row {row}")
        confirmed = _valid_counts(entry, allow_empty=allow_empty)
        if confirmed:
            reps = record.reps
            if (
                reps is None or not reps.is_finite() or reps <= 0
                or not record.exercise or not record.set_type
                or (record.weight is not None and not record.weight.is_finite())
            ):
                raise ValueError(
                    f"Rep counts require a usable row with positive finite exported reps "
                    f"at source row {row}"
                )
        result[row] = dict(entry) if confirmed else None
    return result


def _load(path: Path, export_hash: str, records: dict[int, SetRecord]) -> dict[int, dict[str, Any]]:
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked rep counts file: {path}")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read rep counts file {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.keys() != {"schema_version", "export_sha256", "sets"}:
        raise ValueError("Rep counts file must contain schema_version, export_sha256, and sets")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("Unsupported rep counts schema version")
    if payload["export_sha256"] != export_hash:
        raise ValueError("Rep counts export hash does not match the current export")
    validated = _validated_entries(payload["sets"], records, allow_empty=False)
    return {row: entry for row, entry in validated.items() if entry is not None}


def apply_rep_counts(
    records: Iterable[SetRecord], path: str | Path | None, export_hash: str
) -> tuple[SetRecord, ...]:
    raw = tuple(records)
    if path is None:
        return raw
    confirmed = _load(Path(path), export_hash, _record_index(raw))
    return tuple(
        replace(record, full_reps=confirmed[record.source_row]["full_reps"],
                partial_reps=confirmed[record.source_row]["partial_reps"])
        if record.source_row in confirmed else record
        for record in raw
    )


def _refuse_alias(destination: Path, sources: Iterable[Path]) -> None:
    if destination.is_symlink():
        raise ValueError(f"Refusing symlinked rep counts destination: {destination}")
    for source in sources:
        if destination.resolve() == source.resolve() or (
            destination.exists() and source.exists() and os.path.samefile(destination, source)
        ):
            raise ValueError(f"Rep counts destination aliases a source file: {source}")


def save_rep_counts(
    path: str | Path,
    export_path: str | Path,
    entries: Iterable[dict[str, Any]],
    *,
    expected_hash: str | None = None,
    expected_export_hash: str | None = None,
    reserved: Iterable[str | Path] = (),
) -> None:
    destination, export = Path(path), Path(export_path)
    sources = (export, *(Path(item) for item in reserved))
    _refuse_alias(destination, sources)
    if destination.exists() and not destination.is_file():
        raise ValueError("Rep counts destination must be a file")
    actual_hash = file_sha256(destination) if destination.exists() else None
    if actual_hash != expected_hash:
        raise ValueError("Rep counts file changed since preview; review it again")
    export_hash = file_sha256(export)
    if expected_export_hash is not None and export_hash != expected_export_hash:
        raise ValueError("MacroFactor export changed since preview; review it again")
    raw_records = _record_index(load_exercise_log(export))
    existing = _load(destination, export_hash, raw_records)
    updates = _validated_entries(list(entries), raw_records, allow_empty=True)
    merged = {**existing}
    for row, entry in updates.items():
        if entry is None:
            merged.pop(row, None)
        else:
            merged[row] = entry
    payload = {"schema_version": 1, "export_sha256": export_hash,
               "sets": [merged[row] for row in sorted(merged)]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.tmp-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _refuse_alias(destination, sources)
        if (file_sha256(destination) if destination.exists() else None) != actual_hash:
            raise ValueError("Rep counts file changed during save; review it again")
        if file_sha256(export) != export_hash:
            raise ValueError("MacroFactor export changed during save; review it again")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
