"""Independent, bounded checks against literal coach cells before batch generation.

This is deliberately not a second invocation of the production parser. Its small
numeric grammar and full-table scan act as an independent oracle for supported
base prescriptions. Prose is retained, not interpreted; app import remains manual.
"""
from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import normalize_name
from .models import BridgeConfig, ExerciseRule
from .ooxml import MAIN_NS, WorkbookError, XlsxPackage, make_cell_reference, split_cell_reference, split_range
from .program_models import ProgramBlockOption, ProgramIssue, ProgramPreviewReport


@dataclass(frozen=True)
class SourceAudit:
    passed: bool
    issues: tuple[ProgramIssue, ...]
    checked_rows: int
    checks: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class _Header:
    row: int
    label: str
    number: float
    columns: dict[str, int]
    label_column: int


_CHECKS = (
    "Independent literal day/header scan and source-row coverage, including blank gaps",
    "Exact configuration mapping, exclusion, expansion and superset ordering",
    "Independent base set/rep/rest values, explicit defaults and guarded overrides",
    "Per-cycle provenance, planned-text retention and result-column separation",
    "Unsupported target and configured residual-note retention",
)
_LIMITATIONS = (
    "Base-prescription mode only; weekly instructions are retained, not interpreted or applied.",
    "Free-form prose and exercise identity choices are not independently interpreted; explicit mappings remain user decisions.",
    "Retaining an instruction in notes does not prove that MacroFactor can represent it as a numeric target.",
    "Workbook checks do not establish successful manual MacroFactor import.",
)


def _text(cell) -> str | None:
    return str(cell.value).strip() or None if cell is not None and cell.value is not None else None


def _integer(text: str | None) -> int | None:
    return int(text) if text and text.isascii() and text.isdigit() and int(text) > 0 else None


def _bounds(text: str | None, *, suffix: str = "") -> tuple[int, int] | None:
    match = re.fullmatch(r"([0-9]+)\s*(?:to|[-–])\s*([0-9]+)" + suffix, text or "", re.I)
    if not match:
        return None
    low, high = map(int, match.groups())
    return (low, high) if 0 < low <= high else None


def _count(text: str | None, config: BridgeConfig) -> tuple[int | None, bool]:
    literal = re.sub(r"\s+(?:ea\.?|each)(?:\s+(?:leg|side))?$", "", text or "", flags=re.I)
    exact = _integer(literal)
    bounds = _bounds(text, suffix=r"(?:\s*sets?)?")
    if exact is not None:
        return exact, False
    if bounds and config.program.set_count_range_policy == "upper":
        return bounds[1], True
    return None, False


def _reps(text: str | None) -> tuple[tuple[int, int | None], ...]:
    """Small independently expressed grammar, no trailing arbitrary prose."""
    if not text:
        return ()
    if re.fullmatch(r"[0-9]+(?:\s*,\s*[0-9]+)+", text):
        values = tuple(_integer(value.strip()) for value in text.split(","))
        return tuple((value, value) for value in values) if all(values) else ()
    value = text.lower().strip()
    value = re.sub(r"\s+again$", "", value)
    value = re.sub(r"\s*(?:ea\.?|each)(?:\s+(?:leg|side))?$", "", value)
    value = re.sub(r"\s*reps?$", "", value).strip()
    if value.endswith("+"):
        minimum = _integer(value[:-1])
        return ((minimum, None),) if minimum is not None else ()
    exact = _integer(value)
    if exact is not None:
        return ((exact, exact),)
    bounds = _bounds(value)
    return (bounds,) if bounds else ()


def _rest(text: str | None, config: BridgeConfig) -> tuple[int | None, str | None]:
    value = re.sub(r"(?:\s*\(timed\)|\s+max)$", "", (text or "").lower())
    value = re.sub(r"\s*rest$", "", value).strip()
    parts = re.split(r"\s*(?:to|[-–])\s*", value)
    if len(parts) not in (1, 2) or len(parts) == 2 and config.program.rest_range_policy != "upper":
        return None, None
    numbers, units = [], []
    for part in parts:
        match = re.fullmatch(r"([0-9]+)\s*(seconds?|secs?|s|minutes?|mins?|m)?", part)
        if not match or not _integer(match[1]):
            return None, None
        numbers.append(int(match[1]))
        units.append(None if match[2] is None else 60 if match[2].startswith("m") else 1)
    if numbers[-1] < numbers[0] or len(units) == 2 and units[0] is not None and units[0] != units[1]:
        return None, None
    unitless = all(unit is None for unit in units)
    if unitless and config.program.unitless_rest_policy != "seconds":
        return None, None
    ranged = len(parts) == 2
    source = (("coach_unitless_seconds_range_upper_by_policy" if ranged else "coach_unitless_seconds_by_policy")
              if unitless else "coach_range_upper_by_policy" if ranged else "coach_base")
    return numbers[-1] * (units[-1] or 1), source


def _date_styles(path: str | Path) -> set[str]:
    """Inspect number formats independently; numeric date cells need exact review."""
    with zipfile.ZipFile(path) as archive:
        if "xl/styles.xml" not in archive.namelist():
            return set()
        root = ET.fromstring(archive.read("xl/styles.xml"))
    ns = "{" + MAIN_NS + "}"
    formats = {int(node.attrib["numFmtId"]): node.attrib.get("formatCode", "")
               for node in root.iter(ns + "numFmt")}
    result = set()
    styles = root.find(ns + "cellXfs")
    for index, node in enumerate(styles if styles is not None else ()):
        number = int(node.attrib.get("numFmtId", "0"))
        code = re.sub(r'"[^"]*"|\\.|\[[^]]*\]', "", formats.get(number, ""))
        if (14 <= number <= 22 or 27 <= number <= 36 or 45 <= number <= 47
                or 50 <= number <= 58 or re.search(r"[ydh]", code, re.I)):
            result.add(str(index))
    return result


def _headers(snapshot, config: BridgeConfig) -> tuple[list[_Header], dict[int, dict[int, object]]]:
    rows: dict[int, dict[int, object]] = defaultdict(dict)
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        rows[row][column] = cell
    roles = {role: getattr(config.program, role + "_header_labels")
             for role in ("style", "exercise", "sets", "reps", "rest", "variation")}
    result = []
    pattern = re.compile(config.program.day_label_pattern, re.I)
    for row, cells in sorted(rows.items()):
        labels = [(column, _text(cell), pattern.fullmatch(_text(cell) or ""))
                  for column, cell in cells.items()]
        labels = [entry for entry in labels if entry[2] is not None]
        if len(labels) != 1:
            continue
        columns = {}
        for role, names in roles.items():
            aliases = {normalize_name(name) for name in names}
            matches = [column for column, cell in cells.items()
                       if normalize_name(_text(cell) or "") in aliases]
            if len(matches) == 1:
                columns[role] = matches[0]
        if not all(role in columns for role in ("style", "exercise", "sets", "reps", "rest")):
            continue
        column, label, match = labels[0]
        result.append(_Header(row, label, float(match.group(1)), columns, column))
    return result, rows


def _rules(name: str, variation: str, raw: dict[str, str], config: BridgeConfig) -> list[ExerciseRule]:
    context = {normalize_name(value) for value in raw.values()}
    eligible = [rule for rule in config.rules if not rule.coach_context_aliases
                or context.intersection(map(normalize_name, rule.coach_context_aliases))]
    def aliases(value: str) -> list[ExerciseRule]:
        return [rule for rule in eligible if normalize_name(value)
                in set(map(normalize_name, rule.coach_aliases))]
    if normalize_name(variation) != normalize_name(name):
        detailed = aliases(variation)
        if detailed:
            return detailed
        canonical = [rule for rule in eligible if normalize_name(rule.canonical) == normalize_name(variation)]
        return canonical or [rule for rule in aliases(name) if rule.coach_context_aliases]
    return aliases(name)


def _reference_boundary(snapshot, headers, selected, rows, marker: str) -> int:
    """Resolve a reviewed footer, never infer one from formatting or blank gaps."""
    if not isinstance(marker, str) or not marker.strip():
        raise ValueError("Reviewed reference marker must be a nonempty exact literal")
    last_day = selected[-1]
    following_headers = [header.row for header in headers if header.row > last_day.row]
    scope_end = min(following_headers) if following_headers else max(rows, default=last_day.row) + 1
    matches = [(reference, cell) for reference, cell in snapshot.cells.items()
               if last_day.row < split_cell_reference(reference)[0] < scope_end
               and cell.value == marker]
    if len(matches) != 1:
        raise ValueError("Reviewed reference marker is missing, changed or ambiguous within this block's final day")
    reference, marker_cell = matches[0]
    row, column = split_cell_reference(reference)
    heading_columns = {last_day.columns["style"],
                       last_day.columns.get("variation", last_day.columns["exercise"])}
    if len(heading_columns) != 2 or max(heading_columns) - min(heading_columns) != 1:
        raise ValueError("Reviewed reference marker requires distinct adjacent style and variation/exercise columns")
    expected_merge = (row, min(heading_columns), row, max(heading_columns))
    if column != min(heading_columns) or sum(split_range(merge) == expected_merge for merge in snapshot.merges) != 1:
        raise ValueError("Reviewed reference marker must head one exact single-row style/variation merge")
    if marker_cell.formula is not None:
        raise ValueError("Reviewed reference marker must be literal, not a cached formula")
    for guard_row in (row - 1, row):
        for guard_column in set(last_day.columns.values()):
            if guard_row == row and guard_column == column:
                continue
            guard = snapshot.cells.get(make_cell_reference(guard_row, guard_column))
            if guard is not None and (guard.formula is not None or _text(guard) is not None):
                raise ValueError("Reviewed reference marker needs a blank base separator and blank remaining base/target cells")
    return row


def _aligned_source_weeks(snapshot, rows, headers, selected, config):
    """Reconstruct aligned pairs from literal source, independently of discovery."""
    if config.program.prescription_source != "base" or config.program.week_pair_layout not in {
        "plan_then_result", "result_then_plan"
    }:
        raise ValueError("Aligned coverage requires base mode and an explicit pair direction")
    pattern = re.compile(config.program.week_header_pattern, re.I)
    union = {}
    observations = []
    tables = []
    for header in selected:
        if header.columns != selected[0].columns:
            raise ValueError("Aligned day base schemas differ")
        preceding_base = [rows.get(header.row - 1, {}).get(col) for col in header.columns.values()]
        header_start = max(1, header.row - 1)
        if (any(cell is not None and (_text(cell) is not None or cell.formula is not None)
                for cell in preceding_base)
                or not any(_text(cell) and pattern.fullmatch(_text(cell))
                           for cell in rows.get(header.row - 1, {}).values())):
            header_start = header.row
        following = [item.row for item in headers if item.row > header.row]
        end = min(following) - 1 if following else max(rows, default=header.row)
        base_rows = [row for row in range(header.row + 1, end + 1)
                     if any(cell is not None and (_text(cell) is not None or cell.formula is not None)
                            for col in header.columns.values()
                            for cell in (rows.get(row, {}).get(col),))]
        first_base_row = min(base_rows, default=end + 1)
        exercise_rows = []
        for row in range(header.row + 1, end + 1):
            if exercise_rows and not any(_text(rows.get(row, {}).get(col)) for col in header.columns.values()):
                break
            if _text(rows.get(row, {}).get(header.columns["exercise"])):
                exercise_rows.append(row)
        table_end = exercise_rows[-1] if exercise_rows else header.row
        candidates = sorted(
            (col, row, cell) for row in range(header_start, header.row + 1)
            for col, cell in rows.get(row, {}).items()
            if _text(cell) and pattern.fullmatch(_text(cell))
        )
        observed = {}
        for index, (column, row, cell) in enumerate(candidates):
            key = normalize_name(_text(cell))
            if cell.formula is not None or key in observed:
                raise ValueError("Duplicate or formula week header")
            covering = [split_range(merge) for merge in snapshot.merges
                        if split_range(merge)[0] <= row <= split_range(merge)[2]
                        and split_range(merge)[1] <= column <= split_range(merge)[3]]
            first = column
            if covering:
                if (len(covering) != 1 or covering[0][0:2] != (row, column)
                        or covering[0][3] != column + 1 or covering[0][2] >= first_base_row):
                    raise ValueError("Unsupported merged week header")
            elif index + 1 < len(candidates):
                if candidates[index + 1][0] != column + 2:
                    raise ValueError("Unmerged week pair is not adjacent")
            elif not any(column in rows.get(r, {}) and column + 1 in rows.get(r, {}) for r in exercise_rows):
                raise ValueError("Unmerged week pair lacks structural cells")
            pair = (first, first + 1)
            if set(pair).intersection(header.columns.values()):
                raise ValueError("Week pair touches base columns")
            if key in union and union[key] != pair:
                raise ValueError("Week label changes source pair")
            if any(other != key and set(pair).intersection(other_pair) for other, other_pair in union.items()):
                raise ValueError("Week labels overlap source pairs")
            union[key] = pair
            observed[key] = pair
        observations.append(observed)
        tables.append((header, exercise_rows, table_end, first_base_row, header_start))
    if not union or not any(set(item) == set(union) for item in observations):
        raise ValueError("No explicit complete anchor day supports the union")
    for header, exercise_rows, table_end, first_base_row, header_start in tables:
        for key, pair in union.items():
            if not any(all(col in rows.get(row, {}) for col in pair) for row in exercise_rows):
                raise ValueError("Aligned pair cells are absent from the day exercise table")
            header_rows = set(range(header_start, header.row + 1))
            for merge in snapshot.merges:
                r1, c1, r2, c2 = split_range(merge)
                if r2 >= header_start and r1 <= table_end and any(c1 <= col <= c2 for col in pair):
                    if r2 < header.row and not any(
                        _text(cell) is not None or cell.formula is not None
                        for row, cells in rows.items() if r1 <= row <= r2
                        for col, cell in cells.items() if c1 <= col <= c2
                    ):
                        continue
                    if not (header_start <= r1 <= header.row and r2 < first_base_row and (c1, c2) == pair):
                        raise ValueError("Aligned pair intersects an unsafe merge")
                    header_rows.update(range(r1, r2 + 1))
                    for row in range(r1, r2 + 1):
                        for col in pair:
                            if (row, col) != (r1, c1) and _text(rows.get(row, {}).get(col)) is not None:
                                raise ValueError("Merged header contains non-top-left text")
            for row in header_rows:
                for col in pair:
                    cell = rows.get(row, {}).get(col)
                    if cell is not None and (cell.formula is not None or (_text(cell) and normalize_name(_text(cell)) != key)):
                        raise ValueError("Aligned header slots contain alternate text or formulas")
    offset = 1 if config.program.week_pair_layout == "result_then_plan" else 0
    return {key: pair[offset] for key, pair in sorted(union.items(), key=lambda item: item[1])}


def audit_coach_program(
    workbook_path: str | Path, config: BridgeConfig, block: ProgramBlockOption,
    report: ProgramPreviewReport, *, reference_boundary_marker: str | None = None,
    require_complete_week_coverage: bool = False,
) -> SourceAudit:
    """Fail closed on independent source discrepancies; never mutate the report."""
    issues: list[ProgramIssue] = []
    checked_rows = 0
    checks = _CHECKS
    limitations = _LIMITATIONS

    def fail(code: str, message: str, *, day=None, cell=None, raw=None):
        issues.append(ProgramIssue("blocking", "source_audit_" + code, message,
                                   block.sheet, cell=cell, day=day, raw_text=raw))

    def finish() -> SourceAudit:
        return SourceAudit(not issues, tuple(issues), checked_rows, checks, limitations)

    program = report.program
    if config.program.prescription_source != "base" or program is None or program.prescription_source != "base":
        fail("unsupported_mode", "Independent batch source audit requires a parsed base-prescription program")
        return finish()
    if report.sheet != block.sheet or report.block != block.identifier:
        fail("selection", "Preview selection does not match the audited block")
        return finish()
    try:
        package = XlsxPackage(workbook_path)
        snapshot = package.sheet_snapshot(package.sheet_by_name(block.sheet))
        headers, rows = _headers(snapshot, config)
        date_styles = _date_styles(workbook_path)
    except (WorkbookError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        fail("unreadable_source", f"Independent source inspection failed: {exc}")
        return finish()
    grouped: list[list[_Header]] = []
    for header in headers:
        if (not grouped or header.number <= grouped[-1][-1].number
                or any(header.columns[key] != grouped[-1][-1].columns[key]
                       for key in ("style", "exercise", "sets", "reps", "rest"))):
            grouped.append([])
        grouped[-1].append(header)
    matches = [group for group in grouped if group[0].row == block.start_row]
    if len(matches) != 1:
        fail("block_boundary", "Selected block start is not independently supported by literal day/header cells")
        return finish()
    selected = matches[0]
    reference_boundary = None
    if reference_boundary_marker is not None:
        try:
            reference_boundary = _reference_boundary(snapshot, headers, selected, rows, reference_boundary_marker)
        except ValueError as exc:
            fail("reference_boundary", str(exc))
            return finish()
        checks += ("Exact block-scoped reviewed reference marker, merge and blank-cell guards",)
        limitations += ("Content at and below the explicitly reviewed reference marker is outside this block's exercise-table audit.",)
    if tuple(day.label for day in program.days) != tuple(header.label for header in selected):
        fail("day_coverage", "Preview omits, adds or reorders independently discovered workout days")
        return finish()
    if tuple(day.order for day in program.days) != tuple(range(1, len(selected) + 1)):
        fail("day_order", "Workout day order does not follow the source")
    cycles = tuple(cycle.label for cycle in program.cycles)
    if (not cycles or cycles != report.included_weeks or len(set(map(normalize_name, cycles))) != len(cycles)
            or tuple(cycle.order for cycle in program.cycles) != tuple(range(1, len(cycles) + 1))
            or not set(map(normalize_name, cycles)).issubset(map(normalize_name, block.week_labels))):
        fail("cycles", "Program cycles do not match the explicitly selected source weeks")
    week_pattern = re.compile(config.program.week_header_pattern, re.I)
    prior_weeks: dict[str, int] = {}
    common_weeks: set[str] | None = None
    all_visible_weeks: set[str] = set()
    aligned_weeks = None
    if config.program.week_header_coverage_policy == "aligned_union_base_only":
        try:
            aligned_weeks = _aligned_source_weeks(snapshot, rows, headers, selected, config)
        except ValueError as exc:
            fail("week_alignment", str(exc))
            return finish()
        if tuple(map(normalize_name, block.week_labels)) != tuple(aligned_weeks):
            fail("week_coverage", "Selectable weeks differ from the independent canonical column order")
        checks += ("Independent same-block complete-anchor week alignment and pair guards",)

    for header, day in zip(selected, program.days):
        next_headers = [item.row for item in headers if item.row > header.row]
        end = min(next_headers) - 1 if next_headers else max(rows, default=header.row)
        if reference_boundary is not None and header.row == selected[-1].row:
            end = reference_boundary - 1
        designations = [(make_cell_reference(row, header.label_column), rows.get(row, {}).get(header.label_column))
                        for row in range(header.row + 1, end + 1)
                        if _text(rows.get(row, {}).get(header.label_column)) is not None
                        or (rows.get(row, {}).get(header.label_column) is not None
                            and rows[row][header.label_column].formula is not None)]
        designation = designation_cell = None
        if (header.label_column not in header.columns.values() and len(designations) == 1
                and designations[0][1].formula is None and isinstance(designations[0][1].value, str)):
            designation_cell, source_cell = designations[0]
            designation = _text(source_cell)
        expected_export_name = designation if config.program.use_day_designations and designation else day.label
        if (day.designation != designation or day.designation_cell != designation_cell
                or day.export_name != expected_export_name):
            fail("day_designation", "Workout designation/export name differs from the literal source and explicit policy", day=day.label)
        weeks: dict[str, int] = {}
        for header_row in (() if aligned_weeks is not None else (header.row - 1, header.row)):
            for column, cell in rows.get(header_row, {}).items():
                value = _text(cell)
                if value and week_pattern.fullmatch(value):
                    plan_column = column
                    for merge in snapshot.merges:
                        r1, c1, r2, c2 = split_range(merge)
                        if r1 <= header_row <= r2 and c1 <= column <= c2:
                            if c2 - c1 != 1:
                                fail("week_layout", "Weekly header is not an independently supported pair", day=day.label)
                            plan_column = c1
                    if config.program.week_pair_layout == "result_then_plan":
                        plan_column += 1
                    weeks[normalize_name(value)] = plan_column
        if aligned_weeks is not None:
            weeks = dict(aligned_weeks)
        elif not weeks:
            weeks = dict(prior_weeks)
        prior_weeks = weeks
        common_weeks = set(weeks) if common_weeks is None else common_weeks.intersection(weeks)
        all_visible_weeks.update(weeks)
        if config.program.week_pair_layout not in {"plan_then_result", "result_then_plan"}:
            fail("week_layout", "Plan/result direction has not been explicitly configured", day=day.label)
        if not set(map(normalize_name, cycles)).issubset(weeks):
            fail("week_coverage", "Selected cycles lack independent planned-column headers", day=day.label)
        if any(cell.formula is not None for cell in rows.get(header.row, {}).values()):
            fail("formula", "Day/header row contains formulas; literal source audit is required", day=day.label)
        source_rows = []
        for row in range(header.row + 1, end + 1):
            base = {role: _text(snapshot.cells.get(make_cell_reference(row, column)))
                    for role, column in header.columns.items()}
            if not any(base.values()):
                continue
            if not base.get("exercise"):
                fail("orphan_prescription", "Base fields occur without an exercise name", day=day.label,
                     cell=make_cell_reference(row, header.columns["exercise"]))
                continue
            source_rows.append(row)
        actual_rows = list(dict.fromkeys(exercise.source_row for exercise in day.exercises))
        if actual_rows != source_rows:
            fail("row_coverage", "Preview source rows differ from the complete base table, including rows after blank gaps",
                 day=day.label, raw=f"source={source_rows}; preview={actual_rows}")
        if tuple(exercise.order for exercise in day.exercises) != tuple(range(1, len(day.exercises) + 1)):
            fail("exercise_order", "Exercise order is not consecutive source order", day=day.label)
        actual_by_row = defaultdict(list)
        for exercise in day.exercises:
            actual_by_row[exercise.source_row].append(exercise)
        if [exercise.source_row for exercise in day.exercises] != sorted(exercise.source_row for exercise in day.exercises):
            fail("exercise_order", "Source exercise rows are reordered", day=day.label)
        for row in source_rows:
            checked_rows += 1
            cell = make_cell_reference(row, header.columns["exercise"])
            raw = {role: value for role in ("style", "sets", "reps", "rest")
                   if (value := _text(snapshot.cells.get(make_cell_reference(row, header.columns[role])))) is not None}
            name = _text(snapshot.cells.get(cell))
            raw["variation"] = _text(snapshot.cells.get(make_cell_reference(
                row, header.columns.get("variation", header.columns["exercise"])))) or name
            actual = actual_by_row.get(row, [])
            def row_fail(code, message, raw_text=None):
                fail(code, message, day=day.label, cell=cell, raw=raw_text)
            if any(snapshot.cells.get(make_cell_reference(row, col)) is not None
                   and snapshot.cells[make_cell_reference(row, col)].formula is not None
                   for col in header.columns.values()):
                row_fail("formula", "Base prescription or exercise cell contains a formula")
            matches = _rules(name, raw["variation"], raw, config)
            category = normalize_name(" ".join((day.label, name, *raw.values())))
            warmup = any(token in category for token in ("warmup", "warm up", "warm-up"))
            cardio = any(token in category for token in ("cardio", "conditioning", "zone 2", "interval"))
            category_excluded = (warmup and config.program.exclude_warmups
                                 and not (len(matches) == 1 and matches[0].program_include_warmup)
                                 or cardio and config.program.exclude_cardio)
            if category_excluded:
                if len(actual) != 1 or not actual[0].excluded:
                    row_fail("exclusion", "Category exclusion is missing or duplicates a source row")
                for exercise in actual:
                    if exercise.raw_base_fields != raw or exercise.source_cell != cell or exercise.coach_name != name:
                        row_fail("raw_source", "Excluded exercise lost literal source provenance")
                continue
            if not matches:
                row_fail("mapping", "No independently supported exact configuration mapping exists")
                continue
            if len(matches) > 1:
                if (len({rule.superset_group for rule in matches}) != 1 or matches[0].superset_group is None
                        or sorted(rule.superset_order for rule in matches) != list(range(1, len(matches) + 1))):
                    row_fail("mapping", "Multiple mappings are not one explicit ordered superset")
                    continue
                matches.sort(key=lambda rule: rule.superset_order)
            expected = []
            for rule in matches:
                expansion = rule.program_expansion if not rule.program_excluded else None
                if expansion:
                    if raw.get("sets") != expansion.expected_sets or raw["variation"] != expansion.expected_variation:
                        row_fail("expansion_guard", "Expansion guards do not exactly match source")
                        continue
                    expected.extend((rule, child, index) for index, child in enumerate(expansion.exercises, 1))
                else:
                    expected.append((rule, None, None))
            if len(actual) != len(expected):
                row_fail("mapping_coverage", "Source row expansion/superset count differs from explicit configuration")
            for exercise, (rule, child, child_index) in zip(actual, expected):
                canonical = child.canonical if child else rule.canonical
                if (exercise.macrofactor_name != canonical or exercise.source_cell != cell
                        or exercise.coach_name != name or exercise.raw_base_fields != raw):
                    row_fail("raw_source", "Exact mapping or literal base-cell provenance differs from source/configuration")
                expected_mapping_status = ("excluded" if rule.program_excluded else "exact_expansion" if child
                                           else "exact_superset" if len(matches) > 1 else "exact")
                if exercise.mapping_status != expected_mapping_status:
                    row_fail("mapping", "Mapping status differs from explicit configuration evidence")
                if exercise.excluded != rule.program_excluded:
                    row_fail("exclusion", "Exercise exclusion differs from explicit configuration")
                custom = child.macrofactor_custom if child else rule.macrofactor_custom
                available = child.macrofactor_available if child else rule.macrofactor_available
                if exercise.custom_exercise != custom or exercise.macrofactor_available != available:
                    row_fail("availability", "Exercise availability/custom flag differs from configuration")
                if not available and not exercise.excluded:
                    row_fail("availability", "Configured exercise is unavailable in MacroFactor")
                expected_superset = (rule.superset_group, rule.superset_order) if rule.superset_group else None
                actual_superset = (exercise.superset.group, exercise.superset.order) if exercise.superset else None
                if actual_superset != expected_superset:
                    row_fail("superset", "Superset membership differs from explicit configuration")
                if child:
                    exp = exercise.expansion
                    if (exp is None or exp.parent_canonical != rule.canonical or exp.child_order != child_index
                            or exp.child_count != len(rule.program_expansion.exercises) or exp.execution != "sequential"
                            or exp.expected_variation != raw["variation"] or exp.expected_sets != raw.get("sets")
                            or exp.sets_each != child.sets or actual_superset is not None):
                        row_fail("expansion", "Sequential expansion provenance differs from explicit configuration")
                elif exercise.expansion is not None:
                    row_fail("expansion", "An unconfigured row was expanded")
                if exercise.excluded:
                    continue
                _audit_prescriptions(snapshot, header, row, raw, rule, child, exercise,
                                     config, cycles, weeks, date_styles, row_fail)
    if set(map(normalize_name, block.week_labels)) != (common_weeks or set()):
        fail("week_coverage", "Discovered selectable weeks differ from independently visible common week headers")
    if require_complete_week_coverage:
        checks += ("All independently visible day-week headers are shared and represented by selected cycles",)
        if (all_visible_weeks != (common_weeks or set())
                or all_visible_weeks != set(map(normalize_name, cycles))):
            fail("complete_week_coverage", "All-weeks batch cannot silently shorten a block: visible day-week headers must be shared by every day and included as cycles")
    return finish()


def _audit_prescriptions(snapshot, header, row, raw, rule, child, exercise,
                         config, cycles, weeks, date_styles, fail):
    effective = dict(raw)
    overrides = set()
    for correction in rule.program_base_overrides:
        if raw.get(correction.field) != correction.expected:
            fail("override_guard", "Reviewed base correction no longer matches its source guard")
        else:
            effective[correction.field] = correction.value
            overrides.add(correction.field)
    count, ranged_count = _count(effective.get("sets"), config)
    reps = _reps(effective.get("reps"))
    rest, parsed_rest_source = _rest(effective.get("rest"), config)
    rep_cell = snapshot.cells.get(make_cell_reference(row, header.columns["reps"]))
    date_rep = bool(rep_cell and isinstance(rep_cell.value, (int, float))
                    and rep_cell.style in date_styles and "reps" not in overrides)
    if date_rep:
        reps = ()
        fail("date_target", "Date-formatted numeric reps require a source-guarded reviewed correction")
    if count is None:
        fail("unsupported_sets", "Set count is not independently supported by literal source and configured range policy")
    if len(reps) > 1 and (len(reps) != count or child):
        fail("rep_sequence", "Per-set rep sequence cannot be allocated to the configured set count/expansion")
    if effective.get("rest") and rest is None:
        fail("unsupported_rest", "Rest text is not independently supported; it requires human review")
    if "reps" in overrides and not reps:
        fail("override_value", "Reviewed rep correction is outside the independent numeric grammar")
    styles = {"standard": "standard", "standard set": "standard", "standard sets": "standard",
              "straight set": "standard", "straight sets": "standard", "superset": "superset",
              "super set": "superset", "warmup": "warmup", "warm up": "warmup", "warm-up": "warmup",
              "myo set": "myo", "myo sets": "myo", "drop set": "drop", "drop sets": "drop"}
    explicit = {kind for kind, pattern in (("myo", r"\bmyo(?:[ -]?reps?|[ -]?sets?)?\b"),
                                          ("drop", r"\bdrop[ -]?sets?\b"),
                                          ("superset", r"\bsuper[ -]?sets?\b"))
                if re.search(pattern, " ".join(effective.values()), re.I)}
    base_kind = styles.get(normalize_name(effective.get("style", "")))
    kind = next(iter(explicit)) if len(explicit) == 1 else base_kind
    if len(explicit) > 1 or (explicit and base_kind and base_kind not in explicit):
        fail("set_types", "Mixed source set types require explicit human review")
    kind_source = "coach_base" if kind else "config_default"
    if rule.superset_group and kind is None and config.program.defaults.set_type == "standard":
        kind, kind_source = "superset", "config_superset"
    kind = kind or config.program.defaults.set_type
    if child and (rule.program_set_types or len(reps) > 1 or kind != "standard" or rule.superset_group):
        fail("expansion", "Sequential expansion cannot allocate special sets, rep sequences or supersets")
    if rule.program_set_types and (len(rule.program_set_types) != count
                                  or kind_source == "coach_base" and kind not in rule.program_set_types):
        fail("set_types", "Configured set sequence conflicts with literal source type/count")
    if tuple(rx.cycle for rx in exercise.prescriptions) != cycles:
        fail("cycles", "Exercise prescriptions do not cover every selected cycle in order")
    defaults = config.program.defaults
    expected_count = child.sets if child else count
    count_source = ("config_program_expansion" if child else "config_reviewed_override" if "sets" in overrides
                    else "coach_range_upper_by_policy" if ranged_count else "coach_base")
    minimum, maximum = reps[0] if reps else (defaults.rep_min, defaults.rep_max)
    min_source = "config_reviewed_override" if "reps" in overrides else "coach_base" if reps else "config_default" if minimum is not None else "blank_by_policy"
    max_source = "config_reviewed_override" if "reps" in overrides else "coach_unbounded" if reps and maximum is None else "coach_base" if reps else "config_default" if maximum is not None else "blank_by_policy"
    blank_reps = rule.program_blank_rep_targets
    minimum_notes = bool(reps and minimum is not None and maximum is None
                         and config.program.minimum_rep_policy == "notes_only")
    if blank_reps or minimum_notes:
        minimum = maximum = None
        min_source = max_source = "blank_by_policy"
    expected_rest = rest if rest is not None else defaults.rest_seconds
    rest_source = parsed_rest_source or ("config_default" if expected_rest is not None else "blank_by_policy")
    if not config.program.allow_blank_targets and (
            expected_rest is None or defaults.rir is None or not blank_reps and (minimum is None or maximum is None)):
        fail("missing_targets", "Missing targets are not permitted by explicit configuration")
    if kind is None:
        fail("missing_set_type", "No source or explicitly configured set type exists")
    for rx in exercise.prescriptions:
        expected = (("set_count", expected_count, count_source, "sets"),
                    ("rep_min", minimum, min_source, "reps"), ("rep_max", maximum, max_source, "reps"),
                    ("rest_seconds", expected_rest, rest_source, "rest"),
                    ("rir", defaults.rir, "config_default" if defaults.rir is not None else "blank_by_policy", None),
                    ("set_type", kind, kind_source, None))
        for field_name, value, source, base_key in expected:
            field = getattr(rx, field_name)
            if field.value != value or field.source != source:
                fail("prescription", f"{field_name} value/provenance differs from independent source expectation", raw.get(base_key))
            if base_key and source in {"coach_base", "coach_unbounded", "coach_range_upper_by_policy", "config_reviewed_override", "config_program_expansion",
                                      "coach_unitless_seconds_by_policy", "coach_unitless_seconds_range_upper_by_policy"}:
                if field.source_cell != make_cell_reference(row, header.columns[base_key]) or field.raw_text != raw.get(base_key):
                    fail("provenance", f"{field_name} lost its exact source cell/raw text")
            if source == "config_default" and (field.source_cell is not None or field.raw_text is not None):
                fail("provenance", f"{field_name} default is misrepresented as coach-provided")
        targets = tuple((target.minimum.value, target.maximum.value) for target in rx.set_rep_targets)
        if targets != (reps if len(reps) > 1 and not blank_reps else ()):
            fail("rep_sequence", "Per-set rep values differ from the literal ordered source list")
        for target in rx.set_rep_targets:
            for field in (target.minimum, target.maximum):
                if (field.source != ("config_reviewed_override" if "reps" in overrides else "coach_base")
                        or field.source_cell != make_cell_reference(row, header.columns["reps"])
                        or field.raw_text != raw.get("reps")):
                    fail("provenance", "Per-set rep sequence lost original source-cell provenance")
        if (tuple(field.value for field in rx.set_types) != rule.program_set_types
                or any(field.source != "config_set_sequence" for field in rx.set_types)):
            fail("set_types", "Per-set type sequence differs from explicit configuration")
        plan_column = weeks.get(normalize_name(rx.cycle))
        if plan_column is not None:
            plan_cell = snapshot.cells.get(make_cell_reference(row, plan_column))
            raw_week = _text(plan_cell)
            if rx.raw_week_text != raw_week or rx.raw_unparsed_text != raw_week:
                fail("weekly_retention", "Weekly planned text was lost or replaced with completed results")
            if plan_cell and plan_cell.formula is not None:
                fail("formula", "Weekly planned cell contains a formula; literal retention cannot be verified")
        notes = "\n".join(rx.notes)
        required_notes = []
        if config.program.preserve_coach_notes:
            if config.program.notes_mode == "full":
                required_notes.extend(effective.values())
            else:
                if rule.program_notes is not None:
                    required_notes.extend(rule.program_notes)
                elif normalize_name(effective["variation"]) != normalize_name(rule.canonical):
                    required_notes.append(effective["variation"])
                if effective.get("reps") and not reps:
                    required_notes.append(effective["reps"])
                if blank_reps and reps:
                    required_notes.append(effective["reps"])
                if reps and re.search(r"\b(?:ea\.?|each)\b", effective.get("reps", ""), re.I):
                    required_notes.append("Reps are per side.")
                if count and re.search(r"\b(?:ea\.?|each)\b", effective.get("sets", ""), re.I):
                    required_notes.append("Sets are per side.")
                if rest and re.search(r"(?:\s+max|\(timed\))$", effective.get("rest", ""), re.I):
                    required_notes.append(effective["rest"])
            if minimum_notes:
                required_notes.append(effective["reps"])
        elif effective.get("reps") and not reps:
            fail("unsupported_reps", "Unsupported rep instruction has no approved notes-retention policy")
        if any(text not in notes for text in required_notes):
            fail("notes", "Required coach target text or explicitly approved residual cue is missing from notes")
