"""Local managed-folder ingestion and conservative, provenance-preserving history.

Exports have no stable set IDs. Reconcile whole dates as multisets: identical
snapshots count once, supersets replace subsets, incompatible snapshots are
reported rather than concatenated. Original files are never modified.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys

from .config import load_config, source_rule_index
from .desktop_model import bundled_config_path
from .history import (
    DashboardAnnotations, HistoryDashboard, _canonical_exercise, _record_is_usable,
    build_history_dashboard, load_dashboard_annotations,
)
from .importers import ExerciseLogImport, load_exercise_log_with_diagnostics
from .local_workspace import DIRECTORIES, archive_inbox, verified_archives
from .models import SetRecord
from .ooxml import file_sha256
from .workbook import discover_workbook


@dataclass(frozen=True)
class ExportSource:
    path: Path
    digest: str
    modified: float
    records: tuple[SetRecord, ...]
    skipped: int

    @property
    def first(self):
        return min(r.workout_date for r in self.records)

    @property
    def last(self):
        return max(r.workout_date for r in self.records)

    @property
    def days(self):
        return len({r.workout_date for r in self.records})


@dataclass(frozen=True)
class ManagedSnapshot:
    root: Path
    config_path: Path
    annotation_path: Path
    coach_path: Path
    baseline: ExportSource
    newest: ExportSource
    exports: tuple[ExportSource, ...]
    dashboard: HistoryDashboard
    annotations: DashboardAnnotations
    issues: tuple[str, ...]
    conflicts: tuple[str, ...]
    fingerprint: tuple

    def summary(self):
        d = self.dashboard
        return (f"Auto-loaded {len(self.exports)} unique exports · {d.first_workout:%b %d, %Y}–{d.last_workout:%b %d, %Y} · "
                f"{d.set_count:,} sets · {len(self.conflicts)} overlap conflicts · {len(self.issues)} source notices")

    def report(self):
        lines = [self.summary(), f"Workspace: {self.root}", f"Coach: {self.coach_path}",
                 "Coach selection: newest valid source modification time (not a filename-derived date).",
                 f"Mapping: {self.config_path}", f"Private feedback: {self.annotation_path}",
                 f"Broadest observed history: {self.baseline.path}",
                 f"Most recent workout coverage: {self.newest.path}",
                 "Coverage is observed logging, not proof that all workouts are present.", "", "Exports:"]
        for source in self.exports:
            roles = []
            if source.digest == self.baseline.digest:
                roles.append("BROAD HISTORY")
            if source.digest == self.newest.digest:
                roles.append("LATEST WORKOUT DATE")
            lines.append(f"{' / '.join(roles) or 'Supplement'} · {source.first}–{source.last} · "
                         f"{source.days} days · {len(source.records)} completed sets · {source.skipped} malformed rows\n{source.path}")
        lines.extend(["", "Overlap policy: preserve identical repeated sets within a workout; deduplicate export snapshots. "
                      "Add new dates and exact supersets. Incompatible dates keep the higher-ranked snapshot and require review. "
                      "Absence from a newer file is not a deletion instruction.", "", *self.conflicts, *self.issues])
        return "\n\n".join(lines)


def discover_workspace(saved: str = "", *, executable: Path | None = None, checkout: Path | None = None) -> Path | None:
    if saved:
        # A missing saved folder is an actionable error, not permission to switch datasets.
        return Path(saved).expanduser().resolve()
    bases = (Path(executable or sys.executable).resolve(), checkout or Path(__file__).resolve().parents[2])
    for base in bases:
        for parent in (base, *tuple(base.parents)[:5]):
            root = parent / "local-data"
            if (root / "inbox").is_dir():
                return root.resolve()
    return None


def workspace_paths(root: Path) -> tuple[Path, Path]:
    local = root.parent / "config" / "exercises.local.json"
    return (local if local.is_file() else bundled_config_path()), root / "annotations" / "workout-history.json"


def validate_root(root: Path):
    if not root.is_dir() or not (root / "inbox").is_dir():
        raise ValueError(f"Workspace not found: {root}. Choose the local-data folder containing inbox/coach and inbox/macrofactor.")
    for relative in (*DIRECTORIES, "inbox", "archive", "generated"):
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Automatic loading refuses a symlinked managed directory: {path}")
    annotations = root / "annotations" / "workout-history.json"
    if annotations.is_symlink():
        raise ValueError("Automatic loading refuses a symlinked feedback file")


def workspace_fingerprint(root: Path) -> tuple:
    """Cheap change detection; actual ingestion validates content hashes separately."""
    root = Path(root).resolve()
    validate_root(root)
    paths = []
    for relative in ("inbox/coach", "inbox/macrofactor", "archive/coach", "archive/macrofactor", "manifests", "current"):
        directory = root / relative
        if directory.is_dir():
            paths.extend(p for p in directory.iterdir() if not p.name.startswith((".", "~$")))
    paths.extend(workspace_paths(root))
    result = []
    for path in sorted(set(paths)):
        try:
            stat = path.lstat()
            result.append((str(path), stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            result.append((str(path), None, None))
    return tuple(result)


def _sources(root: Path, issues: list[str]):
    candidates = {}
    entries = verified_archives(root)
    for entry in entries:
        path = Path(entry["archive"])
        key = entry["kind"], entry["sha256"]
        modified = datetime.fromisoformat(entry["source_modified_at"]).timestamp()
        if key not in candidates or modified > candidates[key][2]:
            candidates[key] = (path, entry["sha256"], modified)
    for kind, extensions in (("coach", {".xlsx"}), ("macrofactor", {".csv", ".xlsx"})):
        folder = root / "inbox" / kind
        for path in sorted(folder.iterdir() if folder.is_dir() else ()):
            if path.name.startswith((".", "~$")) or path.suffix.lower() not in extensions:
                continue
            if path.is_symlink() or not path.is_file():
                issues.append(f"Skipped non-regular inbox file: {path.name}")
                continue
            try:
                digest = file_sha256(path)
                key = kind, digest
                # Prefer the immutable archive copy; duplicate filenames do not win priority.
                if key not in candidates:
                    candidates[key] = (path, digest, path.stat().st_mtime)
            except OSError as exc:
                issues.append(f"Cannot read {path.name}: {exc}")
    verified = {Path(entry["archive"]) for entry in entries}
    trusted_hashes = {(entry["kind"], entry["sha256"]) for entry in entries}
    for kind in ("coach", "macrofactor"):
        directory = root / "archive" / kind
        for path in sorted(directory.iterdir() if directory.is_dir() else ()):
            if path.suffix.lower() in {".csv", ".xlsx"} and path not in verified:
                # Older archive naming migrations may leave identical hardlinks.
                try:
                    if not path.is_symlink() and (kind, file_sha256(path)) in trusted_hashes:
                        continue
                except OSError:
                    pass
                issues.append(f"Unverified archive skipped (missing manifest or changed hash): {path.name}")
    return candidates


def _numeric_signature(value: Decimal | None):
    # NaNs do not compare equal; signaling NaNs cannot be hashed. Keep their
    # type, sign and payload in the signature without changing source values.
    return ("nonfinite", value.as_tuple()) if value is not None and not value.is_finite() else value


def _signature(records):
    return Counter((r.workout, r.exercise, r.set_type.casefold(),
                    _numeric_signature(r.weight), _numeric_signature(r.reps),
                    _numeric_signature(r.rir), _numeric_signature(r.workout_duration_seconds)) for r in records)


def consolidate(exports: tuple[ExportSource, ...]) -> tuple[ExportSource, tuple[SetRecord, ...], tuple[str, ...]]:
    ranked = sorted(exports, key=lambda s: (s.skipped == 0, s.days, (s.last - s.first).days,
                                            len(s.records), s.last, s.modified, s.digest), reverse=True)
    if not ranked:
        raise ValueError("No valid completed workout sets found in managed exports.")
    days: dict[date, tuple[SetRecord, ...]] = {}
    conflicts = []
    for source in ranked:
        grouped = defaultdict(list)
        for record in source.records:
            grouped[record.workout_date].append(record)
        for day, records in sorted(grouped.items()):
            incoming = tuple(records)
            existing = days.get(day)
            if existing is None:
                days[day] = incoming
                continue
            before, after = _signature(existing), _signature(incoming)
            if before <= after:
                if before != after:
                    days[day] = incoming
            elif not after <= before:
                conflicts.append(f"{day}: conflicting snapshots. Kept {Path(existing[0].source_file).name}; "
                                 f"review {source.path.name}. No sets from the conflicting date were appended.")
    records = tuple(r for day in sorted(days) for r in days[day])
    return ranked[0], records, tuple(conflicts)


def load_managed_history(root: str | Path, *, archive: bool = True) -> ManagedSnapshot:
    root = Path(root).resolve()
    validate_root(root)
    config_path, annotation_path = workspace_paths(root)
    config = load_config(config_path)
    annotations = load_dashboard_annotations(annotation_path)
    issues: list[str] = []
    if archive:
        manifest = archive_inbox(root, config_path, new_only=True)
        issues.extend(f"{Path(error['source']).name}: {error['error']}" for error in manifest["errors"])
    fingerprint = workspace_fingerprint(root)
    config = load_config(config_path)
    annotations = load_dashboard_annotations(annotation_path)
    candidates = _sources(root, issues)
    exports = []
    coaches = []
    index = source_rule_index(config)
    for (kind, _), (path, digest, modified) in candidates.items():
        try:
            if kind == "coach":
                sheets = discover_workbook(path, config)
                if not any(s.exercise_column is not None and s.weeks for s in sheets):
                    raise ValueError("No usable coach blocks")
                coaches.append((modified, str(path), digest))
            else:
                imported = load_exercise_log_with_diagnostics(path)
                records = tuple(replace(r, exercise=_canonical_exercise(r, index), source_file=str(path))
                                for r in imported.records if _record_is_usable(r))
                if not records:
                    raise ValueError("No usable completed sets")
                exports.append(ExportSource(path, digest, modified, records, len(imported.skipped_rows)))
                if imported.skipped_rows:
                    issues.append(f"{path.name}: {len(imported.skipped_rows)} malformed rows excluded; not proof of complete coverage.")
            if file_sha256(path) != digest:
                raise ValueError("File changed during loading; retry when copying is finished")
        except (OSError, ValueError) as exc:
            exports = [s for s in exports if s.path != path]
            coaches = [c for c in coaches if c[1] != str(path)]
            issues.append(f"Skipped {path.name}: {exc}")
    if not exports:
        raise ValueError("No valid completed workout sets found in managed exports. " + " ".join(issues[:5]))
    baseline, records, conflicts = consolidate(tuple(exports))
    if not coaches:
        raise ValueError("No valid coach workbook found in the managed inbox or verified archives. " + " ".join(issues))
    _, coach, digest = max(coaches)
    newest = max(exports, key=lambda s: (s.last, s.modified, s.digest))
    if newest.first > baseline.first:
        issues.append("The latest-workout export is narrower than the broad-history baseline; earlier history was retained.")
    dashboard = build_history_dashboard(baseline.path, coach, config, annotations,
                                        imported=ExerciseLogImport(records, ()))
    if file_sha256(coach) != digest:
        raise ValueError("Coach workbook changed during loading; retry when copying is finished")
    if workspace_fingerprint(root) != fingerprint:
        raise ValueError("Managed files changed during loading; retry when copying is finished")
    return ManagedSnapshot(root, config_path, annotation_path, Path(coach), baseline, newest,
                           tuple(sorted(exports, key=lambda s: (s.first, s.last, str(s.path)))),
                           dashboard, annotations, tuple(dict.fromkeys(issues)), conflicts, fingerprint)
