"""One-shot, private batch review around the existing fail-closed program services."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .coach_program import discover_program_blocks
from .config import ConfigError, load_config
from .models import BridgeConfig
from .ooxml import WorkbookError, XlsxPackage, file_sha256, make_cell_reference, split_cell_reference
from .program_audit import audit_coach_program
from .program_models import ProgramIssue, ProgramBlockOption
from .program_output_audit import audit_program_output, inspect_import_contract
from .program_service import build_program_preview, generate_program
from .program_template import inspect_program_template


_INPUT_ERRORS = (WorkbookError, ValueError, OSError, ET.ParseError, zipfile.BadZipFile)


def _identity_key(name: str) -> str:
    # Local evidence keys are still private, not anonymized public data.
    return hashlib.sha256(" ".join(name.split()).casefold().encode()).hexdigest()


def _imported_identities(path: Path) -> list[str]:
    schema = inspect_program_template(path)
    cells = XlsxPackage(path).sheet_snapshot(schema.sheet_name).cells
    return sorted({_identity_key(re.sub(r" ∈ SS[1-9]\d*$", "", str(cells[
        make_cell_reference(row, schema.exercise_column)].value))) for day in schema.days for row in day.rows})


@dataclass
class ProgramBatchReport:
    input_workbook: str
    template_workbook: str
    output_directory: str
    generated_requested: bool
    sheet_order: str
    input_hashes_before: dict[str, str | None]
    input_hashes_after: dict[str, str | None] = field(default_factory=dict)
    inputs_unchanged: bool = False
    results: list[dict[str, Any]] = field(default_factory=list)
    review_items: list[dict[str, Any]] = field(default_factory=list)
    manual_import_plan: dict[str, Any] = field(default_factory=dict)
    manual_import_verified: bool = False
    limitations: tuple[str, ...] = (
        "Worksheet order is configured chronology, not an inferred date order.",
        "Source checks cover supported literal structures and reviewed policies, not free-form coach intent.",
        "Automated validation and representative sampling do not verify each file inside MacroFactor.",
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _key(value: object) -> tuple[str, str]:
    if (not isinstance(value, dict) or not {"sheet", "block"} <= value.keys()
            or any(not isinstance(value[k], str) or not value[k].strip() for k in ("sheet", "block"))):
        raise ConfigError("A batch block key needs exact non-empty sheet and block strings")
    return value["sheet"], value["block"]


def _resolve_path(value: object, parent: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("Batch paths must be non-empty strings")
    path = Path(value)
    return (path if path.is_absolute() else parent / path).resolve()


def _manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"block_configs": {}, "reference_boundaries": {}, "skip_sheets": {}, "evidence": [], "start_after": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {"schema_version", "start_after", "block_configs", "reference_boundaries", "skip_sheets", "manual_import_evidence"}
    if (not isinstance(data, dict) or set(data) - allowed
            or type(data.get("schema_version")) is not int or data["schema_version"] != 1):
        raise ConfigError("Batch manifest needs schema_version 1 and only documented fields")
    start = data.get("start_after")
    if start is not None and (not isinstance(start, dict) or set(start) != {"sheet", "block"}):
        raise ConfigError("start_after needs only sheet and block")
    overrides, boundaries, skipped, evidence = {}, {}, {}, []
    for name in ("block_configs", "reference_boundaries", "skip_sheets", "manual_import_evidence"):
        if not isinstance(data.get(name, []), list):
            raise ConfigError(f"{name} must be a list")
    for entry in data.get("block_configs", []):
        key = _key(entry)
        if set(entry) != {"sheet", "block", "config"} or key in overrides:
            raise ConfigError("block_configs must have unique exact keys and one config path")
        overrides[key] = _resolve_path(entry["config"], path.parent)
    for entry in data.get("reference_boundaries", []):
        key = _key(entry)
        if (set(entry) != {"sheet", "block", "marker_text"} or key in boundaries
                or not isinstance(entry["marker_text"], str) or not entry["marker_text"].strip()):
            raise ConfigError("reference_boundaries needs unique block keys and exact reviewed marker_text")
        boundaries[key] = entry["marker_text"]
    for entry in data.get("skip_sheets", []):
        if (not isinstance(entry, dict) or set(entry) != {"sheet", "reason"}
                or any(not isinstance(v, str) or not v.strip() for v in entry.values())
                or entry["sheet"] in skipped):
            raise ConfigError("skip_sheets needs unique exact sheet names and explicit reasons")
        skipped[entry["sheet"]] = entry["reason"]
    for entry in data.get("manual_import_evidence", []):
        if (not isinstance(entry, dict) or set(entry) != {"output", "sha256", "confirmed"}
                or entry["confirmed"] is not True or not isinstance(entry["sha256"], str)
                or len(entry["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["sha256"])):
            raise ConfigError("Import evidence requires output, lowercase sha256 and explicit confirmed: true")
        evidence.append({**entry, "output": _resolve_path(entry["output"], path.parent)})
    return {"block_configs": overrides, "reference_boundaries": boundaries, "skip_sheets": skipped, "evidence": evidence,
            "start_after": _key(start) if start is not None else None}


def _require_base(config: BridgeConfig) -> None:
    if config.program.prescription_source != "base":
        raise ConfigError("Batch conversion currently requires program.prescription_source: base")


def _require_shared_mapping_only(config: BridgeConfig) -> None:
    for rule in config.rules:
        if (rule.program_base_overrides or rule.program_notes is not None or rule.program_expansion
                or rule.program_set_types or rule.program_blank_rep_targets or rule.program_include_warmup
                or rule.program_excluded or rule.program_exclusion_reason or rule.superset_group):
            raise ConfigError("Shared batch configuration must contain reusable exact mappings only; "
                              "put reviewed notes, corrections, special sets, exclusions and supersets in block_configs")


def _discovery_settings(config: BridgeConfig) -> tuple[Any, ...]:
    p = config.program
    return (p.day_label_pattern, p.week_header_pattern, p.week_pair_layout, p.week_header_coverage_policy,
            p.style_header_labels, p.exercise_header_labels, p.variation_header_labels,
            p.sets_header_labels, p.reps_header_labels, p.rest_header_labels, p.sheet_order)


def _hashes(paths: list[Path]) -> dict[str, str | None]:
    result = {}
    for path in paths:
        try:
            result[str(path)] = file_sha256(path)
        except OSError:
            result[str(path)] = None
    return result


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _issue(code: str, message: str, sheet: str) -> ProgramIssue:
    return ProgramIssue("blocking", code, message, sheet)


def consolidate_review(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    technical = {"discovery_failed", "no_program_blocks", "unsafe_week_selection", "block_config_invalid",
                 "invalid_program_template", "generation_failed", "output_audit_failed", "input_changed",
                 "template_set_capacity_exceeded", "template_day_count_mismatch"}
    for item in results:
        rows = item.get("source_rows", [])

        def context_for(issue):
            cell = issue.get("cell")
            matches = [r for r in rows if (cell and split_cell_reference(cell)[0] == r["row"])
                       or (not cell and issue.get("day") == r["day"] and issue.get("exercise") == r["exercise"])]
            if len(matches) == 1:
                return matches[0]["cell"], matches[0]["context"], matches[0]["identities"]
            return cell, item.get("source_context", {}).get(cell, {}), []

        unmatched = {context_for(i)[0] for i in item["issues"] if i["code"] == "unmatched_exercise"}
        for issue in item["issues"]:
            if issue["severity"] != "blocking" and issue["code"] != "custom_macrofactor_exercise":
                continue
            # Exact coach context prevents one decision being silently reused for a different variation.
            cell, context, identities = context_for(issue)
            if cell and cell in unmatched and issue["code"] in {"source_audit_mapping", "unavailable_macrofactor_exercise"}:
                # Derivative diagnostics remain intact in per-block JSON, not separate user questions.
                continue
            subject = [issue["code"], issue["message"], issue.get("exercise"), issue.get("raw_text"), context, identities]
            fingerprint = hashlib.sha256(json.dumps(subject, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            group = grouped.setdefault(fingerprint, {
                "id": f"review-{len(grouped) + 1:03d}", "code": issue["code"],
                "category": "technical" if issue["code"] in technical or
                    (issue["code"].startswith("source_audit_") and issue["code"] != "source_audit_date_target") else "review",
                "message": issue["message"], "exercise": issue.get("exercise"),
                "raw_text": issue.get("raw_text"), "source_context": context, "identities": identities, "occurrences": [],
            })
            location = {"item": item["id"], "sheet": item["sheet"], "block": item["block"],
                        "day": issue.get("day"), "cell": cell, "cycle": issue.get("cycle")}
            if location not in group["occurrences"]:
                group["occurrences"].append(location)
    return list(grouped.values())


def _covered(contract: dict[str, Any], witness: dict[str, Any]) -> bool:
    return contract["family"] == witness["family"] and set(contract["features"]) <= set(witness["features"])


def select_manual_imports(results: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in results if r["status"] == "generated"]
    newest = next((r for r in reversed(results) if r["status"] != "skipped"), None)
    witnesses = [e["contract"] for e in evidence]
    pending = [r for r in eligible if not any(_covered(r["contract"], w) for w in witnesses)]
    selected = []
    while pending:
        # Prefer a newer broad representative; exact workbook acceptance is never inherited.
        best = max(pending, key=lambda candidate: (sum(_covered(r["contract"], candidate["contract"])
                                                       for r in pending), results.index(candidate)))
        selected.append({"item": best["id"], "output": best["output"], "reason": "representative import structure"})
        pending = [r for r in pending if not _covered(r["contract"], best["contract"])]
    if newest and newest["status"] == "generated" and not any(s["item"] == newest["id"] for s in selected):
        selected.append({"item": newest["id"], "output": newest["output"], "reason": "newest selected program"})
    identity_witnesses = {key for e in evidence for key in e.get("identities", [])}
    selected_ids = {s["item"] for s in selected}
    identity_witnesses.update(key for r in eligible if r["id"] in selected_ids
                              for key in r.get("identity_review_keys", []))
    for candidate in reversed(eligible):
        unseen = set(candidate.get("identity_review_keys", [])) - identity_witnesses
        if unseen:
            selected.append({"item": candidate["id"], "output": candidate["output"],
                             "reason": "uncovered custom or block-only exercise identity"})
            identity_witnesses.update(candidate["identity_review_keys"])
    return {"selected": selected, "newest_item": newest["id"] if newest else None,
            "newest_ready": bool(newest and newest["status"] == "generated"),
            "prior_evidence_count": len(evidence), "manual_import_verified": False,
            "policy": "Test representatives for uncovered structures and custom/block-only identities, plus the newest selected program. "
                      "Sampling reduces manual work; no other output is marked app-tested."}


def _review_markdown(report: ProgramBatchReport) -> str:
    lines = ["# Private batch review", "", "Automated validation is not MacroFactor import verification.", "",
             f"Inputs unchanged: {report.inputs_unchanged}", "", "## Blocks", ""]
    for item in report.results:
        lines.append(f"- {item['id']}: {item['sheet']} / {item['block'] or 'undiscovered'} — {item['status']}")
    counts: dict[str, int] = {}
    for question in report.review_items:
        counts[question["code"]] = counts.get(question["code"], 0) + 1
    lines.extend(["", "## Review at a glance", "",
        "Repeated diagnostics for the same missing mapping are one question. All original diagnostics remain in per-block JSON.",
        "Mapping approval does not approve set counts, notes, substitutions or supersets. Keep those decisions block-scoped.", ""])
    lines.extend(f"- {code}: {count} distinct context(s)" for code, count in sorted(counts.items()))
    lines.extend(["", "Technical findings require source/layout or implementation review, not a guess about coach intent.",
                  "Coverage findings can include trailing reference sections; they do not prove every flagged row belongs in a workout.",
                  "Full locations and raw text are retained in summary.json and each block report.", "",
                  "## Consolidated exceptions", ""])
    if not report.review_items:
        lines.append("No blocking exceptions or custom-exercise review items.")
    for question in report.review_items:
        lines.extend([f"### {question['id']}: {question['code']} ({question['category']})", "", question["message"], ""])
        if question["exercise"]:
            lines.append(f"Exercise: {question['exercise']}")
        if question["raw_text"]:
            lines.append(f"Raw coach text: {question['raw_text']}")
        if question["source_context"]:
            lines.append("Source context: " + json.dumps(question["source_context"], ensure_ascii=False))
        locations = question["occurrences"]
        shown = locations[:12] if question["category"] == "technical" else locations
        lines.extend(f"- {o['item']} / {o['day'] or ''} / {o['cell'] or ''} / {o['cycle'] or ''}" for o in shown)
        if len(shown) < len(locations):
            lines.append(f"- {len(locations) - len(shown)} additional locations retained in summary.json")
        lines.append("")
    lines.extend(["## Manual import plan", "", report.manual_import_plan["policy"], ""])
    for item in report.manual_import_plan["selected"]:
        lines.append(f"- {item['item']}: {item['reason']} ({Path(item['output']).name})")
    if not report.manual_import_plan["newest_ready"]:
        lines.append("The newest selected program is not ready; do not substitute an older file silently.")
    lines.extend(["", "## Limits", "", *[f"- {text}" for text in report.limitations], ""])
    return "\n".join(lines)


def run_program_batch(
    workbook_path: str | Path, config_path: str | Path, template_path: str | Path,
    output_dir: str | Path, *, manifest_path: str | Path | None = None, generate: bool = False,
) -> ProgramBatchReport:
    source, config_file, template = [Path(p).resolve() for p in (workbook_path, config_path, template_path)]
    manifest_file = Path(manifest_path).resolve() if manifest_path is not None else None
    initial_paths = [source, config_file, template, *([manifest_file] if manifest_file else [])]
    initial_hashes = _hashes(initial_paths)
    config = load_config(config_file)
    _require_base(config)
    _require_shared_mapping_only(config)
    manifest = _manifest(manifest_file)
    protected = list(dict.fromkeys([*initial_paths, *manifest["block_configs"].values(),
                                   *[e["output"] for e in manifest["evidence"]]]))
    before = _hashes(protected)
    if any(before[key] != value for key, value in initial_hashes.items()):
        raise WorkbookError("Batch inputs changed during setup")
    evidence = []
    for entry in manifest["evidence"]:
        if before[str(entry["output"])] != entry["sha256"]:
            raise WorkbookError("Manual import evidence hash does not match the confirmed file")
        evidence.append({"output": str(entry["output"]), "sha256": entry["sha256"],
                         "contract": inspect_import_contract(entry["output"]),
                         "identities": _imported_identities(entry["output"])})
    sheets = XlsxPackage(source).sheets
    if config.program.sheet_order == "right_to_left":
        sheets = tuple(reversed(sheets))
    known_sheets = {s.name for s in sheets}
    if set(manifest["skip_sheets"]) - known_sheets:
        raise ConfigError("A skipped sheet is not present in the workbook")
    selections: list[tuple[str, ProgramBlockOption | None, str | None, str | None]] = []
    for sheet in sheets:
        if sheet.name in manifest["skip_sheets"]:
            selections.append((sheet.name, None, None, manifest["skip_sheets"][sheet.name]))
            continue
        try:
            blocks = discover_program_blocks(source, config, sheet_name=sheet.name)
        except _INPUT_ERRORS as exc:
            selections.append((sheet.name, None, f"Discovery failed: {exc}", None))
        else:
            selections.extend((sheet.name, block, None, None) for block in blocks)
            if not blocks:
                selections.append((sheet.name, None, "No program blocks discovered; review this sheet explicitly", None))
    known = {(sheet, block.identifier) for sheet, block, _, _ in selections if block}
    if set(manifest["block_configs"]) - known:
        raise ConfigError("A block_configs key is not in discovery; fix its exact key or shared discovery settings")
    if set(manifest["reference_boundaries"]) - known:
        raise ConfigError("A reference_boundaries key is not in discovery")
    start = manifest["start_after"]
    if start is not None:
        indexes = [i for i, (sheet, block, _, _) in enumerate(selections) if block and (sheet, block.identifier) == start]
        if len(indexes) != 1:
            raise ConfigError("start_after must match one exact discovered sheet/block")
        selections = selections[indexes[0] + 1:]
    if not selections:
        raise WorkbookError("No remaining worksheets or blocks after the selected starting point")
    run_dir = Path(output_dir).absolute()
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError("Batch output directory must be new; existing runs are never overwritten")
    if _hashes(protected) != before:
        raise WorkbookError("Batch inputs changed before execution")
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = ProgramBatchReport(str(source), str(template), str(run_dir), generate,
                                config.program.sheet_order, before)
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=run_dir) as staging:
        drift = False
        previews = {}
        pending_paths = {}
        shared_identities = {_identity_key(rule.canonical) for rule in config.rules}
        for index, (sheet, block, discovery_error, skip_reason) in enumerate(selections, start=1):
            item: dict[str, Any] = {"id": f"block-{index:03d}", "sheet": sheet,
                                    "block": block.identifier if block else None, "status": "blocked",
                                    "issues": [], "output": None, "manual_import_verified": False}
            report.results.append(item)
            if _hashes(protected) != before:
                drift = True
            preview = None
            if drift:
                item["status"] = "not_run_input_changed"
                item["issues"] = [asdict(_issue("input_changed", "Batch input drift; rerun from unchanged inputs", sheet))]
            elif skip_reason:
                item.update(status="skipped", reason=skip_reason)
            elif discovery_error:
                code = "no_program_blocks" if discovery_error.startswith("No program") else "discovery_failed"
                item["issues"] = [asdict(_issue(code, discovery_error, sheet))]
            elif not block.week_labels:
                item["issues"] = [asdict(_issue("unsafe_week_selection", "No safe shared plan/result week selection", sheet))]
            else:
                try:
                    selected_path = manifest["block_configs"].get((sheet, block.identifier), config_file)
                    selected = config if selected_path == config_file else load_config(selected_path)
                    _require_base(selected)
                    if _discovery_settings(selected) != _discovery_settings(config):
                        raise ConfigError("Block config cannot change shared batch discovery settings")
                    item["config"] = str(selected_path)
                except (ConfigError, ValueError, OSError) as exc:
                    item["issues"] = [asdict(_issue("block_config_invalid", str(exc), sheet))]
                else:
                    try:
                        preview = build_program_preview(source, selected, sheet, block.identifier, block.week_labels, template)
                        marker = manifest["reference_boundaries"].get((sheet, block.identifier))
                        item["reference_boundary_marker"] = marker
                        audit = audit_coach_program(source, selected, block, preview,
                            reference_boundary_marker=marker, require_complete_week_coverage=True)
                        item["source_audit"] = audit.to_dict()
                        preview.issues.extend(audit.issues)
                        preview.generation_safe = preview.generation_safe and audit.passed and not preview.blocking_issues
                        item["source_context"] = {e.source_cell: e.raw_base_fields for day in preview.program.days
                                                   for e in day.exercises} if preview.program else {}
                        item["source_rows"] = []
                        identity_review = set()
                        for day in preview.program.days if preview.program else ():
                            for exercise in day.exercises:
                                identities = [_identity_key(exercise.macrofactor_name)] if exercise.macrofactor_name else []
                                row = next((r for r in item["source_rows"] if r["cell"] == exercise.source_cell), None)
                                if row:
                                    row["identities"].extend(identities)
                                else:
                                    item["source_rows"].append({"cell": exercise.source_cell, "row": exercise.source_row,
                                        "day": day.label, "exercise": exercise.coach_name,
                                        "context": exercise.raw_base_fields, "identities": identities})
                                if not exercise.excluded and identities and (exercise.custom_exercise or identities[0] not in shared_identities):
                                    identity_review.update(identities)
                        item["identity_review_keys"] = sorted(identity_review)
                        item["status"] = "ready" if preview.generation_safe else "blocked"
                        if generate and preview.generation_safe:
                            output = run_dir / f"{item['id']}.xlsx"
                            # Audit an unpublished candidate; a failed audit never creates a deliverable.
                            with tempfile.TemporaryDirectory(prefix=".validate-", dir=run_dir) as scratch:
                                candidate = Path(scratch) / "candidate.xlsx"
                                generate_program(preview, template, candidate)
                                output_audit = audit_program_output(preview.program, candidate, template)
                                item["output_audit"] = output_audit.to_dict()
                                preview.output_file = None
                                preview.output_hash = None
                                if not output_audit.passed:
                                    preview.issues.append(_issue("output_audit_failed", "; ".join(output_audit.errors), sheet))
                                    preview.generation_safe = False
                                    item["status"] = "generation_failed"
                                elif _hashes(protected) != before:
                                    raise WorkbookError("Batch inputs changed before candidate publication")
                                else:
                                    contract = inspect_import_contract(candidate)
                                    pending = Path(staging) / output.name
                                    os.link(candidate, pending)
                                    pending_paths[item["id"]] = pending
                                    item.update(status="generated", output=str(output), contract=contract)
                                    preview.output_file = str(output)
                                    preview.output_hash = file_sha256(pending)
                        item["issues"] = [asdict(i) for i in preview.issues]
                    except _INPUT_ERRORS as exc:
                        item["status"] = "generation_failed" if generate and preview and preview.generation_safe else "blocked"
                        item["issues"] = [asdict(i) for i in preview.issues] if preview else []
                        item["issues"].append(asdict(_issue("generation_failed", str(exc), sheet)))
                        if preview:
                            preview.generation_safe = False
                            preview.output_file = None
                            preview.output_hash = None
            item["report"] = str(run_dir / f"{item['id']}.json")
            previews[item["id"]] = preview
        report.input_hashes_after = _hashes(protected)
        report.inputs_unchanged = report.input_hashes_after == before
        if report.inputs_unchanged:
            # Publish only after every block has finished and global inputs still match.
            for item in report.results:
                if item["status"] != "generated":
                    continue
                try:
                    os.link(pending_paths[item["id"]], item["output"])
                except OSError as exc:
                    item.update(status="generation_failed", output=None)
                    item.pop("contract", None)
                    item["issues"].append(asdict(_issue("generation_failed", str(exc), item["sheet"])))
                    previews[item["id"]].generation_safe = False
                    previews[item["id"]].output_file = None
                    previews[item["id"]].output_hash = None
            report.input_hashes_after = _hashes(protected)
            report.inputs_unchanged = report.input_hashes_after == before
        if not report.inputs_unchanged:
            for item in report.results:
                if item["status"] in {"ready", "generated"}:
                    item["status"] = "invalidated_input_change"
                    item["issues"].append(asdict(_issue("input_changed", "Batch inputs changed; do not use this run", item["sheet"])))
                    if item["output"]:
                        output = Path(item["output"])
                        if output.exists() and output.samefile(pending_paths[item["id"]]):
                            output.unlink()  # Only the exact hard link just created by this run.
                    item["output"] = None
                    item.pop("contract", None)
                    if previews[item["id"]]:
                        previews[item["id"]].generation_safe = False
                        previews[item["id"]].output_file = None
                        previews[item["id"]].output_hash = None
        for item in report.results:
            preview = previews[item["id"]]
            _write_json(Path(item["report"]), {"item": item, "preview": preview.to_dict() if preview else None})
        report.review_items = consolidate_review(report.results)
        report.manual_import_plan = select_manual_imports(report.results, evidence)
        _write_json(run_dir / "summary.json", report.to_dict())
        with (run_dir / "review.md").open("x", encoding="utf-8") as stream:
            stream.write(_review_markdown(report))
        return report
