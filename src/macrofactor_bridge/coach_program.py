from __future__ import annotations

import re
import zipfile
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import normalize_name
from .models import BridgeConfig, CellData, ExerciseRule
from .ooxml import (
    WorkbookError,
    MAIN_NS,
    XlsxPackage,
    SheetSnapshot,
    make_cell_reference,
    split_cell_reference,
    split_range,
)
from .program_models import (
    CyclePrescription,
    ExpansionProvenance,
    OrderedExercise,
    PrescriptionField,
    Program,
    ProgramBlockOption,
    ProgramCycle,
    ProgramIssue,
    ProgramParseResult,
    RepTarget,
    SupersetMembership,
    WorkoutDay,
)
from .program_text import prepare_program_notes


@dataclass(frozen=True)
class _WeekLayout:
    label: str
    header_cell: str
    plan_column: int
    completed_columns: tuple[int, ...]
    safe: bool
    reason: str | None = None
    aligned_inherited: bool = False


@dataclass(frozen=True)
class _DayLayout:
    label: str
    number: float
    optional: bool
    header_row: int
    end_row: int
    columns: dict[str, int]
    weeks: tuple[_WeekLayout, ...]


@dataclass(frozen=True)
class _BlockLayout:
    option: ProgramBlockOption
    days: tuple[_DayLayout, ...]


@dataclass(frozen=True)
class _ParsedWeek:
    set_count: int | None = None
    rep_min: int | None = None
    rep_max: int | None = None
    rir: int | None = None
    rest_seconds: int | None = None


SET_TYPE_ALIASES = {
    "standard": "standard",
    "standard set": "standard",
    "standard sets": "standard",
    "straight set": "standard",
    "straight sets": "standard",
    "superset": "superset",
    "super set": "superset",
    "warmup": "warmup",
    "warm up": "warmup",
    "warm-up": "warmup",
    "myo set": "myo",
    "myo sets": "myo",
    "drop set": "drop",
    "drop sets": "drop",
}


def _raw(cell: CellData | None) -> str | None:
    if cell is None or cell.value is None:
        return None
    value = str(cell.value).strip()
    return value or None


def _header_column(values: dict[int, object], labels: tuple[str, ...]) -> int | None:
    aliases = {normalize_name(label) for label in labels}
    matches = [
        column
        for column, value in values.items()
        if isinstance(value, str) and normalize_name(value) in aliases
    ]
    return matches[0] if len(matches) == 1 else None


def _week_layouts(
    snapshot,
    header_row: int,
    end_row: int,
    pattern: re.Pattern[str],
    pair_layout: str | None,
    *,
    header_start: int | None = None,
) -> tuple[_WeekLayout, ...]:
    header_start = max(1, header_row - 1) if header_start is None else header_start
    candidates: list[tuple[int, int, str, str]] = []
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        if not header_start <= row <= header_row:
            continue
        if isinstance(cell.value, str) and pattern.fullmatch(cell.value.strip()):
            candidates.append((row, column, reference, cell.value.strip()))
    by_identity: dict[str, tuple[int, int, str, str]] = {}
    for candidate in sorted(candidates, key=lambda item: (-item[0], item[1])):
        by_identity.setdefault(normalize_name(candidate[3]), candidate)
    ordered = sorted(by_identity.values(), key=lambda item: item[1])

    layouts: list[_WeekLayout] = []
    for index, (_, column, reference, label) in enumerate(ordered):
        first_column = column
        last_column = column
        for merged in snapshot.merges:
            start_row, start_col, merge_end_row, end_col = split_range(merged)
            row, _ = split_cell_reference(reference)
            if start_row <= row <= merge_end_row and start_col <= column <= end_col:
                first_column = start_col
                last_column = end_col
                break
        width = last_column - first_column + 1
        if width == 2:
            plan_column = last_column if pair_layout == "result_then_plan" else first_column
            completed_column = first_column if pair_layout == "result_then_plan" else last_column
            layouts.append(
                _WeekLayout(
                    label=label,
                    header_cell=reference,
                    plan_column=plan_column,
                    completed_columns=(completed_column,),
                    safe=pair_layout is not None,
                    reason=(
                        None
                        if pair_layout is not None
                        else "week plan/result direction requires program.week_pair_layout"
                    ),
                )
            )
            continue
        if width > 2:
            layouts.append(
                _WeekLayout(
                    label=label,
                    header_cell=reference,
                    plan_column=first_column,
                    completed_columns=tuple(range(first_column + 1, last_column + 1)),
                    safe=False,
                    reason="week header spans more than one plan/result pair",
                )
            )
            continue

        next_column = ordered[index + 1][1] if index + 1 < len(ordered) else None
        adjacent_pair = next_column == column + 2
        if next_column is None:
            adjacent_pair = any(
                make_cell_reference(row, column) in snapshot.cells
                and make_cell_reference(row, column + 1) in snapshot.cells
                for row in range(header_row + 1, end_row + 1)
            )
        layouts.append(
            _WeekLayout(
                label=label,
                header_cell=reference,
                plan_column=column + 1 if pair_layout == "result_then_plan" else column,
                completed_columns=(
                    (column,) if pair_layout == "result_then_plan" else (column + 1,)
                ),
                safe=adjacent_pair and pair_layout is not None,
                reason=(
                    None
                    if adjacent_pair and pair_layout is not None
                    else (
                        "week plan/result direction requires program.week_pair_layout"
                        if adjacent_pair
                        else "unmerged week header has no structurally proven adjacent pair"
                    )
                ),
            )
        )
    return tuple(layouts)


def _day_table_end(
    snapshot,
    *,
    header_row: int,
    provisional_end_row: int,
    columns: dict[str, int],
    stop_before_reference_rows: bool = False,
) -> int:
    # Standalone weekly notes below a table do not extend its exercise rows.
    relevant_columns = tuple(columns.values())
    exercise_column = columns["exercise"]
    found_exercise = False
    leading_blank_rows = 0
    for row in range(header_row + 1, provisional_end_row + 1):
        if _raw(snapshot.cells.get(make_cell_reference(row, exercise_column))) is not None:
            found_exercise = True
            leading_blank_rows = 0
        row_is_blank = all(
            _raw(snapshot.cells.get(make_cell_reference(row, column))) is None
            for column in relevant_columns
        )
        if found_exercise and row_is_blank:
            return row - 1
        if not found_exercise and stop_before_reference_rows:
            leading_blank_rows = leading_blank_rows + 1 if row_is_blank else 0
            # One leading blank row accommodates the day designation beside the table.
            # A second blank row is a structural separator, not permission to absorb
            # later reference material as exercises in an unfinished day.
            if leading_blank_rows >= 2:
                return row - 1
    return provisional_end_row


def _align_base_week_headers(snapshot, days, pattern, config):
    """Infer missing header metadata only from one complete, same-block anchor."""
    def reject(reason):
        raise WorkbookError(f"Aligned week header coverage is unsafe: {reason}")

    if config.prescription_source != "base" or config.week_pair_layout not in {
        "plan_then_result", "result_then_plan"
    }:
        reject("requires base prescriptions and an explicit pair direction")
    canonical: dict[str, _WeekLayout] = {}
    explicit = []
    header_starts = []
    occupied: dict[int, str] = {}
    for day in days:
        if day.columns != days[0].columns:
            reject("day base schemas differ")
        header_start = day.header_row
        if day.header_row > 1 and all(
            cell is None or (_raw(cell) is None and cell.formula is None)
            for column in day.columns.values()
            for cell in (snapshot.cells.get(make_cell_reference(day.header_row - 1, column)),)
        ) and any(
            split_cell_reference(reference)[0] == day.header_row - 1
            and isinstance(cell.value, str) and pattern.fullmatch(cell.value.strip())
            for reference, cell in snapshot.cells.items()
        ):
            header_start -= 1
        header_starts.append(header_start)
        seen = set()
        for reference, cell in snapshot.cells.items():
            row, _ = split_cell_reference(reference)
            if header_start <= row <= day.header_row and isinstance(cell.value, str) and pattern.fullmatch(cell.value.strip()):
                key = normalize_name(cell.value)
                if key in seen or cell.formula is not None:
                    reject("duplicate or formula week header")
                seen.add(key)
        weeks = _week_layouts(snapshot, day.header_row, day.end_row, pattern, config.week_pair_layout,
                              header_start=header_start)
        observed = {}
        for week in weeks:
            key = normalize_name(week.label)
            pair = (week.plan_column, *week.completed_columns)
            if not week.safe or len(pair) != 2 or set(pair).intersection(day.columns.values()):
                reject("unsupported pair or pair touches base columns")
            if key in canonical and pair != (canonical[key].plan_column, *canonical[key].completed_columns):
                reject("the same label changes columns")
            if any(column in occupied and occupied[column] != key for column in pair):
                reject("different labels overlap the same pair")
            occupied.update({column: key for column in pair})
            canonical.setdefault(key, week)
            observed[key] = week
        explicit.append(observed)
    if not canonical or not any(set(weeks) == set(canonical) for weeks in explicit):
        reject("no explicit complete anchor day")
    ordered = sorted(canonical, key=lambda key: min(canonical[key].plan_column, *canonical[key].completed_columns))
    aligned = []
    for day, observed, header_start in zip(days, explicit, header_starts):
        first_base_row = next((
            row for row in range(day.header_row + 1, day.end_row + 1)
            if any(cell is not None and (_raw(cell) is not None or cell.formula is not None)
                   for column in day.columns.values()
                   for cell in (snapshot.cells.get(make_cell_reference(row, column)),))
        ), day.end_row + 1)
        weeks = []
        for key in ordered:
            anchor = canonical[key]
            pair = (anchor.plan_column, *anchor.completed_columns)
            header_end = day.header_row
            for merged in snapshot.merges:
                r1, c1, r2, c2 = split_range(merged)
                if r2 >= header_start and r1 <= day.end_row and any(c1 <= col <= c2 for col in pair):
                    if r2 < day.header_row and all(
                        cell.formula is None and _raw(cell) is None
                        for reference, cell in snapshot.cells.items()
                        for row, column in (split_cell_reference(reference),)
                        if r1 <= row <= r2 and c1 <= column <= c2
                    ):
                        continue
                    if not (header_start <= r1 <= day.header_row and r2 < first_base_row
                            and (c1, c2) == (min(pair), max(pair))):
                        reject("pair intersects an unsafe merge")
                    header_end = max(header_end, r2)
                    for row in range(r1, r2 + 1):
                        for column in pair:
                            cell = snapshot.cells.get(make_cell_reference(row, column))
                            if (row, column) != (r1, c1) and cell is not None and _raw(cell) is not None:
                                reject("merged header contains text outside its top-left cell")
            for row in range(header_start, header_end + 1):
                for column in pair:
                    cell = snapshot.cells.get(make_cell_reference(row, column))
                    text = _raw(cell)
                    if cell is not None and (cell.formula is not None or (text and normalize_name(text) != key)):
                        reject(f"pair header slot {make_cell_reference(row, column)} contains alternate text or a formula: {text!r}")
            if not any(
                _raw(snapshot.cells.get(make_cell_reference(row, day.columns["exercise"])))
                and all(make_cell_reference(row, col) in snapshot.cells for col in pair)
                for row in range(day.header_row + 1, day.end_row + 1)
            ):
                reject("pair cells are absent from this day exercise table")
            weeks.append(observed.get(key) or replace(anchor, aligned_inherited=True))
        aligned.append(replace(day, weeks=tuple(weeks)))
    return aligned


def _discover_sheet_layouts(
    package: XlsxPackage,
    sheet,
    config: BridgeConfig,
) -> tuple[_BlockLayout, ...]:
    snapshot = package.sheet_snapshot(sheet)
    by_row: dict[int, dict[int, object]] = {}
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        by_row.setdefault(row, {})[column] = cell.value

    day_pattern = re.compile(config.program.day_label_pattern, re.IGNORECASE)
    week_pattern = re.compile(config.program.week_header_pattern, re.IGNORECASE)
    candidates: list[tuple[int, str, float, bool, dict[str, int]]] = []
    for row, values in sorted(by_row.items()):
        day_matches = [
            (str(value).strip(), day_pattern.fullmatch(str(value).strip()))
            for value in values.values()
            if isinstance(value, str)
        ]
        day_matches = [(label, match) for label, match in day_matches if match]
        if len(day_matches) != 1:
            continue
        columns = {
            "style": _header_column(values, config.program.style_header_labels),
            "exercise": _header_column(values, config.program.exercise_header_labels),
            "sets": _header_column(values, config.program.sets_header_labels),
            "reps": _header_column(values, config.program.reps_header_labels),
            "rest": _header_column(values, config.program.rest_header_labels),
        }
        if any(column is None for column in columns.values()):
            continue
        variation_column = _header_column(values, config.program.variation_header_labels)
        if variation_column is not None:
            columns["variation"] = variation_column
        label, match = day_matches[0]
        assert match is not None
        candidates.append(
            (
                row,
                label,
                float(match.group(1)),
                "optional" in normalize_name(label),
                {key: int(value) for key, value in columns.items() if value is not None},
            )
        )
    if not candidates:
        return ()

    max_row = max(by_row)
    provisional: list[_DayLayout] = []
    for index, (row, label, number, optional, columns) in enumerate(candidates):
        end_row = candidates[index + 1][0] - 1 if index + 1 < len(candidates) else max_row
        weeks = _week_layouts(
            snapshot,
            row,
            end_row,
            week_pattern,
            config.program.week_pair_layout,
        )
        # A block may label its week columns only above its first day.
        # Never inherit across a day-number reset or a changed base layout.
        inherited_weeks = False
        if not weeks and provisional:
            previous = provisional[-1]
            if number > previous.number and columns == previous.columns:
                weeks = previous.weeks
                inherited_weeks = bool(weeks)
        end_row = _day_table_end(
            snapshot,
            header_row=row,
            provisional_end_row=end_row,
            columns=columns,
            stop_before_reference_rows=config.program.exclude_empty_days,
        )
        if inherited_weeks:
            weeks = tuple(
                _WeekLayout(
                    label=week.label,
                    header_cell=week.header_cell,
                    plan_column=week.plan_column,
                    completed_columns=week.completed_columns,
                    safe=week.safe and any(
                        all(
                            make_cell_reference(data_row, column) in snapshot.cells
                            for column in (week.plan_column, *week.completed_columns)
                        )
                        for data_row in range(row + 1, end_row + 1)
                        if _raw(snapshot.cells.get(make_cell_reference(data_row, columns["exercise"])))
                    ),
                    reason="Inherited week pair requires cells in this day table",
                )
                for week in weeks
            )
        provisional.append(
            _DayLayout(
                label=label,
                number=number,
                optional=optional,
                header_row=row,
                end_row=end_row,
                columns=columns,
                weeks=weeks,
            )
        )

    grouped: list[list[_DayLayout]] = []
    current: list[_DayLayout] = []
    previous: _DayLayout | None = None
    for day in provisional:
        schema = tuple(day.columns[key] for key in ("style", "exercise", "sets", "reps", "rest"))
        previous_schema = (
            tuple(previous.columns[key] for key in ("style", "exercise", "sets", "reps", "rest"))
            if previous is not None
            else None
        )
        if current and previous is not None and (
            day.number <= previous.number or schema != previous_schema
        ):
            grouped.append(current)
            current = []
        current.append(day)
        previous = day
    if current:
        grouped.append(current)

    layouts: list[_BlockLayout] = []
    for block_index, days in enumerate(grouped, start=1):
        if config.program.week_header_coverage_policy == "aligned_union_base_only":
            days = _align_base_week_headers(snapshot, days, week_pattern, config.program)
        common: dict[str, str] = {
            normalize_name(week.label): week.label
            for week in days[0].weeks
            if week.safe
        }
        for day in days[1:]:
            safe = {normalize_name(week.label) for week in day.weeks if week.safe}
            common = {key: label for key, label in common.items() if key in safe}
        first_week_order = [
            normalize_name(week.label) for week in days[0].weeks if week.safe
        ]
        labels = tuple(common[key] for key in first_week_order if key in common)
        if (
            not labels
            and config.program.base_cycle_count is not None
            and not any(day.weeks for day in days)
        ):
            labels = tuple(
                f"Cycle {number}"
                for number in range(1, config.program.base_cycle_count + 1)
            )
        end_row = days[-1].end_row
        option = ProgramBlockOption(
            identifier=f"block-{block_index}",
            sheet=sheet.name,
            start_row=days[0].header_row,
            end_row=end_row,
            day_labels=tuple(day.label for day in days),
            week_labels=labels,
        )
        layouts.append(_BlockLayout(option=option, days=tuple(days)))
    return tuple(layouts)


def discover_program_blocks(
    path: str | Path, config: BridgeConfig, *, sheet_name: str | None = None,
) -> tuple[ProgramBlockOption, ...]:
    package = XlsxPackage(path)
    sheets = (package.sheet_by_name(sheet_name),) if sheet_name is not None else package.sheets
    if config.program.sheet_order == "right_to_left":
        sheets = tuple(reversed(sheets))
    return tuple(
        layout.option
        for sheet in sheets
        for layout in _discover_sheet_layouts(package, sheet, config)
    )


def _parse_integer(raw: str | None) -> int | None:
    if raw is None or not re.fullmatch(r"\d+", raw):
        return None
    value = int(raw)
    return value if value > 0 else None


def _parse_set_count(raw: str | None, range_policy: str = "block") -> int | None:
    exact = _parse_integer(raw)
    per_side = re.fullmatch(r"(\d+)\s+(?:ea\.?|each)(?:\s+(?:leg|side))?", raw or "", re.I)
    if per_side:
        exact = _parse_integer(per_side.group(1))
    if exact is not None or raw is None or range_policy != "upper":
        return exact
    match = re.fullmatch(r"(\d+)\s*(?:[-–]|to)\s*(\d+)(?:\s*sets?)?", raw, re.IGNORECASE)
    if not match:
        return None
    lower, upper = int(match.group(1)), int(match.group(2))
    return upper if 1 <= lower <= upper else None


def _parse_reps(raw: str | None) -> tuple[int, int | None] | None:
    if raw is None:
        return None
    match = re.fullmatch(
        r"(\d+)(?:(\+)|\s*(?:[-–]|to)\s*(\d+))?(?:\s*reps?)?"
        r"(?:\s+(?:rep\s+)?range)?"
        r"(?:\s*(?:ea\.?|each)(?:\s+(?:leg|side))?)?(?:\s+(?:again|here))?",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    minimum = int(match.group(1))
    maximum = None if match.group(2) else int(match.group(3) or match.group(1))
    if minimum < 1 or (maximum is not None and maximum < minimum):
        return None
    return minimum, maximum


def _parse_rep_list(raw: str | None) -> tuple[tuple[int, int | None], ...]:
    if not raw or not re.fullmatch(r"\d+(?:\s*,\s*\d+)+", raw):
        return ()
    values = tuple(int(value.strip()) for value in raw.split(","))
    return tuple((value, value) for value in values) if all(value > 0 for value in values) else ()


@dataclass(frozen=True)
class _RestTarget:
    seconds: int
    ranged: bool
    unitless: bool
    qualifier: bool

    @property
    def source(self) -> str:
        if self.unitless:
            return ("coach_unitless_seconds_range_upper_by_policy" if self.ranged
                    else "coach_unitless_seconds_by_policy")
        return "coach_range_upper_by_policy" if self.ranged else "coach_base"


def _rest_target(raw: str | None, range_policy: str = "block",
                 unitless_policy: str = "block") -> _RestTarget | None:
    if raw is None:
        return None
    unit = r"(?:s|sec|secs|second|seconds|m|min|mins|minute|minutes)"
    match = re.fullmatch(
        rf"(\d+)\s*({unit})?(?:\s*(?:[-–]|to)\s*(\d+)\s*({unit})?)?"
        r"(?:\s*rest)?(?:\s+(max)|\s*\((timed)\))?",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    low, low_unit, high, high_unit, ceiling, timed = match.groups()
    lower, upper = int(low), int(high or low)
    ranged = high is not None
    unitless = not (low_unit or high_unit)
    if lower < 1 or upper < lower or (ranged and range_policy != "upper"):
        return None
    if unitless and unitless_policy != "seconds":
        return None
    # A range may share its trailing unit or repeat equivalent units. An omitted
    # trailing unit after an explicit leading one, or mixed units, needs review.
    if ranged and low_unit and (not high_unit or low_unit.lower().startswith("m")
                               != high_unit.lower().startswith("m")):
        return None
    resolved_unit = high_unit or low_unit or "seconds"
    return _RestTarget(upper * (60 if resolved_unit.lower().startswith("m") else 1),
                       ranged, unitless, bool(ceiling or timed))


def _parse_rest(raw: str | None, range_policy: str = "block") -> int | None:
    # Weekly instructions never inherit the base-column unitless policy.
    target = _rest_target(raw, range_policy)
    return target.seconds if target else None


def _parse_rir(raw: str) -> int | None:
    for pattern in (r"(\d+)\s*rir", r"rir\s*(\d+)"):
        match = re.fullmatch(pattern, raw, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _parse_week(raw: str | None) -> _ParsedWeek | None:
    if raw is None:
        return _ParsedWeek()
    parts = [part.strip() for part in re.split(r"\s*(?:,|;|@)\s*", raw) if part.strip()]
    if not parts:
        return _ParsedWeek()
    values: dict[str, int] = {}
    first = parts.pop(0)
    combined = re.fullmatch(
        r"(?:(\d+)\s*[x×]\s*)?(\d+)(?:\s*(?:[-–]|to)\s*(\d+))?(?:\s*reps?)?",
        first,
        re.IGNORECASE,
    )
    if combined:
        if combined.group(1):
            values["set_count"] = int(combined.group(1))
        values["rep_min"] = int(combined.group(2))
        values["rep_max"] = int(combined.group(3) or combined.group(2))
    else:
        sets = re.fullmatch(r"(\d+)\s*sets?", first, re.IGNORECASE)
        rir = _parse_rir(first)
        rest = _parse_rest(first)
        if sets:
            values["set_count"] = int(sets.group(1))
        elif rir is not None:
            values["rir"] = rir
        elif rest is not None:
            values["rest_seconds"] = rest
        else:
            return None
    for part in parts:
        rir = _parse_rir(part)
        rest = _parse_rest(part)
        if rir is not None and "rir" not in values:
            values["rir"] = rir
        elif rest is not None and "rest_seconds" not in values:
            values["rest_seconds"] = rest
        else:
            return None
    if values.get("set_count", 1) < 1:
        return None
    if values.get("rep_min", 1) < 1 or values.get("rep_max", 1) < values.get("rep_min", 1):
        return None
    return _ParsedWeek(**values)


def _matching_rules(
    coach_name: str, context: tuple[str, ...], config: BridgeConfig
) -> list[ExerciseRule]:
    name = normalize_name(coach_name)
    context_keys = {normalize_name(value) for value in context if value}
    matches: list[ExerciseRule] = []
    for rule in config.rules:
        if name not in {normalize_name(alias) for alias in rule.coach_aliases}:
            continue
        if rule.coach_context_aliases and not context_keys.intersection(
            normalize_name(alias) for alias in rule.coach_context_aliases
        ):
            continue
        matches.append(rule)
    return matches


def _exercise_rules(
    coach_name: str, variation: str | None, context: tuple[str, ...], config: BridgeConfig
) -> list[ExerciseRule]:
    if variation and normalize_name(variation) != normalize_name(coach_name):
        detailed = _matching_rules(variation, context, config)
        if detailed:
            return detailed
        exact_names = [
            rule for rule in config.rules
            if normalize_name(variation) == normalize_name(rule.canonical)
            and (not rule.coach_context_aliases or {normalize_name(v) for v in context}.intersection(
                normalize_name(alias) for alias in rule.coach_context_aliases
            ))
        ]
        if exact_names:
            return exact_names
    generic = _matching_rules(coach_name, context, config)
    if variation and normalize_name(variation) != normalize_name(coach_name):
        # A generic alias from another block must not erase a specific variation.
        return [rule for rule in generic if rule.coach_context_aliases]
    return generic


def _date_style_ids(path: str | Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        if "xl/styles.xml" not in archive.namelist():
            return set()
        root = ET.fromstring(archive.read("xl/styles.xml"))
    custom = {
        item.get("numFmtId"): item.get("formatCode", "")
        for item in root.iter(f"{{{MAIN_NS}}}numFmt")
    }
    styles = root.find(f"{{{MAIN_NS}}}cellXfs")
    if styles is None:
        return set()
    result = set()
    for index, style in enumerate(styles):
        number = int(style.get("numFmtId", "0"))
        code = re.sub(r'"[^"]*"|\\.|\[[^]]*\]', "", custom.get(str(number), ""))
        if number in {*range(14, 23), *range(27, 37), *range(45, 48), *range(50, 59)} or re.search(
            r"[ydh]", code, re.IGNORECASE
        ):
            result.add(str(index))
    return result


def _valid_superset_rules(rules: list[ExerciseRule]) -> bool:
    groups = {rule.superset_group for rule in rules}
    orders = [rule.superset_order for rule in rules]
    return (
        len(rules) > 1
        and len(groups) == 1
        and None not in groups
        and all(order > 0 for order in orders)
        and len(set(orders)) == len(orders)
        and sorted(orders) == list(range(1, len(rules) + 1))
    )


def _validate_day_supersets(
    *,
    day: _DayLayout,
    exercises: list[OrderedExercise],
    config: BridgeConfig,
    sheet_name: str,
    issues: list[ProgramIssue],
) -> None:
    actual_groups = {
        exercise.superset.group
        for exercise in exercises
        if exercise.superset is not None and not exercise.excluded
    }
    for group in sorted(actual_groups):
        expected_rules = [
            rule
            for rule in config.rules
            if rule.superset_group == group and not rule.program_excluded
        ]
        expected_names = Counter(rule.canonical for rule in expected_rules)
        actual_exercises = [
            exercise
            for exercise in exercises
            if exercise.superset is not None
            and exercise.superset.group == group
            and not exercise.excluded
        ]
        actual_names = Counter(
            exercise.macrofactor_name
            for exercise in actual_exercises
            if exercise.macrofactor_name is not None
        )
        orders = sorted(rule.superset_order for rule in expected_rules)
        complete_orders = orders == list(range(1, len(expected_rules) + 1))
        if len(expected_rules) < 2 or not complete_orders or actual_names != expected_names:
            issues.append(
                ProgramIssue(
                    severity="blocking",
                    code="incomplete_superset",
                    message=(
                        f"Superset {group!r} is incomplete, duplicated, or not ordered "
                        "contiguously from 1"
                    ),
                    sheet=sheet_name,
                    cell=actual_exercises[0].source_cell if actual_exercises else None,
                    day=day.label,
                    exercise=group,
                )
            )


def _classification(day_label: str, style: str | None, exercise: str) -> tuple[bool, bool, bool]:
    text = normalize_name(" ".join(value for value in (day_label, style, exercise) if value))
    optional = "optional" in text
    warmup = "warm up" in text or "warmup" in text or "warm-up" in text
    cardio = any(token in text for token in ("cardio", "conditioning", "zone 2", "interval"))
    return optional, warmup, cardio


def _field(
    value: int | str | None,
    source: str,
    cell: str | None,
    raw_text: str | None,
) -> PrescriptionField:
    return PrescriptionField(value=value, source=source, source_cell=cell, raw_text=raw_text)


def _resolve_field(
    *,
    name: str,
    base_value: int | str | None,
    base_cell: str | None,
    base_raw: str | None,
    week_value: int | str | None,
    week_cell: str,
    week_raw: str | None,
    default_value: int | str | None,
    sheet: str,
    day: str,
    exercise: str,
    cycle: str,
    issues: list[ProgramIssue],
    suppress_blockers: bool,
    allow_blank: bool = False,
) -> PrescriptionField:
    if base_value is not None and week_value is not None and base_value != week_value:
        if not suppress_blockers:
            issues.append(
                ProgramIssue(
                    severity="blocking",
                    code="conflicting_base_and_week",
                    message=f"Base and selected-week {name} values conflict",
                    sheet=sheet,
                    cell=week_cell,
                    day=day,
                    exercise=exercise,
                    cycle=cycle,
                    raw_text=week_raw,
                )
            )
        return _field(None, "conflict", week_cell, week_raw)
    if week_value is not None:
        return _field(week_value, "coach_week", week_cell, week_raw)
    if base_value is not None:
        return _field(base_value, "coach_base", base_cell, base_raw)
    if default_value is not None:
        issues.append(
            ProgramIssue(
                severity="warning",
                code="config_default_proposed",
                message=f"Configuration proposes a default {name} value",
                sheet=sheet,
                cell=week_cell,
                day=day,
                exercise=exercise,
                cycle=cycle,
            )
        )
        return _field(default_value, "config_default", None, None)
    if not suppress_blockers:
        issues.append(
            ProgramIssue(
                severity="warning" if allow_blank else "blocking",
                code="blank_target_requested" if allow_blank else "missing_prescription_field",
                message=(f"Leave {name} blank under the configured import policy" if allow_blank
                         else f"No supported {name} value was provided"),
                sheet=sheet,
                cell=week_cell,
                day=day,
                exercise=exercise,
                cycle=cycle,
            )
        )
    return _field(None, "blank_by_policy" if allow_blank else "missing", None, None)


def _base_value_issue(
    *,
    field_name: str,
    raw_text: str | None,
    cell: str,
    sheet: str,
    day: str,
    exercise: str,
    issues: list[ProgramIssue],
    suppress_blockers: bool,
) -> None:
    if raw_text is None or suppress_blockers:
        return
    issues.append(
        ProgramIssue(
            severity="blocking",
            code="unsupported_base_value",
            message=f"Base {field_name} is not a supported exact value",
            sheet=sheet,
            cell=cell,
            day=day,
            exercise=exercise,
            raw_text=raw_text,
        )
    )


def _apply_set_layout(
    prescription: CyclePrescription,
    *,
    set_types: tuple[str, ...],
    blank_reps: bool,
    sheet: str,
    day: str,
    exercise: str,
    issues: list[ProgramIssue],
    suppress_blockers: bool,
) -> CyclePrescription:
    notes = prescription.notes
    if set_types:
        if len(set_types) != prescription.set_count.value and not suppress_blockers:
            issues.append(ProgramIssue(
                severity="blocking", code="set_type_sequence_length_mismatch",
                message="Explicit per-set types must match the resolved total set count",
                sheet=sheet, day=day, exercise=exercise, cycle=prescription.cycle,
            ))
        coach_type = prescription.set_type.value
        if (prescription.set_type.source.startswith("coach") and coach_type not in set_types
                and not suppress_blockers):
            issues.append(ProgramIssue(
                severity="blocking", code="conflicting_set_type_sequence",
                message="Explicit per-set types omit the coach-provided set type",
                sheet=sheet, day=day, exercise=exercise, cycle=prescription.cycle,
            ))
        notes += ("Import setting: ordered set types = " + ", ".join(set_types) + ".",)
        prescription = replace(prescription, set_types=tuple(
            _field(kind, "config_set_sequence", None, None) for kind in set_types
        ))
    if blank_reps:
        notes += ("Import setting: leave rep targets blank; retain coach targets in notes.",)
        prescription = replace(prescription,
            rep_min=_field(None, "blank_by_policy", None, prescription.rep_min.raw_text),
            rep_max=_field(None, "blank_by_policy", None, prescription.rep_max.raw_text),
            set_rep_targets=(),
        )
    return replace(prescription, notes=notes)


def _prescriptions(
    *,
    snapshot,
    sheet: str,
    day: _DayLayout,
    row: int,
    exercise: str,
    base_raw: dict[str, str],
    weeks: tuple[str, ...],
    config: BridgeConfig,
    issues: list[ProgramIssue],
    suppress_blockers: bool,
    configured_superset: bool = False,
    date_styles: set[str] | None = None,
    set_types: tuple[str, ...] = (),
    blank_rep_targets: bool = False,
    rule: ExerciseRule | None = None,
) -> tuple[CyclePrescription, ...]:
    original_base = base_raw
    base_raw = dict(base_raw)
    overridden = set()
    for override in rule.program_base_overrides if rule else ():
        matches = base_raw.get(override.field) == override.expected
        if not suppress_blockers:
            issues.append(ProgramIssue(
                severity="warning" if matches else "blocking",
                code="reviewed_base_override" if matches else "stale_base_override",
                message=(f"Reviewed {override.field} correction: {override.expected!r} -> {override.value!r}"
                         if matches else f"Reviewed {override.field} correction no longer matches source"),
                sheet=sheet, day=day.label, exercise=exercise,
                cell=make_cell_reference(row, day.columns[override.field]),
                raw_text=base_raw.get(override.field),
            ))
        if matches:
            base_raw[override.field] = override.value
            overridden.add(override.field)
    cells = {
        key: make_cell_reference(row, day.columns[key])
        for key in ("style", "sets", "reps", "rest")
    }
    set_count = _parse_set_count(base_raw.get("sets"), config.program.set_count_range_policy)
    ranged_sets = set_count is not None and _parse_set_count(base_raw.get("sets")) is None
    per_side_sets = bool(set_count is not None and re.search(r"\b(?:ea\.?|each)\b", base_raw.get("sets", ""), re.I))
    rep_range = _parse_reps(base_raw.get("reps"))
    rep_list = _parse_rep_list(base_raw.get("reps"))
    rep_cell = snapshot.cells.get(cells["reps"])
    date_rep = bool(rep_cell and rep_cell.style in (date_styles or set())
                    and isinstance(rep_cell.value, (int, float)) and "reps" not in overridden)
    if date_rep:
        rep_range = None
        rep_list = ()
    if rep_list and len(rep_list) != set_count and not suppress_blockers:
        issues.append(ProgramIssue(
            severity="blocking", code="rep_sequence_length_mismatch",
            message="Per-set rep list must match the resolved total set count",
            sheet=sheet, day=day.label, exercise=exercise, cell=cells["reps"],
            raw_text=base_raw.get("reps"),
        ))
    rest_target = _rest_target(base_raw.get("rest"), config.program.rest_range_policy,
                               config.program.unitless_rest_policy)
    rest_seconds = rest_target.seconds if rest_target else None
    if rest_target and rest_target.unitless and not suppress_blockers:
        issues.append(ProgramIssue(
            severity="warning", code="unitless_rest_seconds_by_policy",
            message=("Configured base Rest units: seconds; using the upper range bound" if rest_target.ranged
                     else "Configured base Rest units: seconds"),
            sheet=sheet, day=day.label, exercise=exercise, cell=cells["rest"],
            raw_text=base_raw.get("rest"),
        ))
    for key, valid in (("sets", set_count is not None), ("reps", rep_range is not None or bool(rep_list))):
        if key in overridden and not valid and not suppress_blockers:
            issues.append(ProgramIssue(
                severity="blocking", code="unsupported_base_override",
                message=f"Reviewed {key} replacement is not a supported exact prescription",
                sheet=sheet, day=day.label, exercise=exercise, cell=cells[key], raw_text=base_raw[key],
            ))
    set_type = SET_TYPE_ALIASES.get(normalize_name(base_raw.get("style", "")))
    if set_count is None:
        _base_value_issue(
            field_name="set count", raw_text=base_raw.get("sets"), cell=cells["sets"],
            sheet=sheet, day=day.label, exercise=exercise, issues=issues,
            suppress_blockers=suppress_blockers,
        )
    notes_policy = config.program.preserve_coach_notes
    blank_targets = config.program.allow_blank_targets
    blank_reps_allowed = blank_targets or blank_rep_targets
    if date_rep and not suppress_blockers:
        issues.append(ProgramIssue(
            severity="warning" if notes_policy and blank_reps_allowed else "blocking",
            code="date_formatted_rep_target",
            message="Rep cell is stored as an Excel date; review the original target",
            sheet=sheet, cell=cells["reps"], day=day.label, exercise=exercise,
            raw_text=base_raw.get("reps"),
        ))
    if rep_range is None and not rep_list and not (notes_policy and blank_reps_allowed):
        _base_value_issue(
            field_name="rep target", raw_text=base_raw.get("reps"), cell=cells["reps"],
            sheet=sheet, day=day.label, exercise=exercise, issues=issues,
            suppress_blockers=suppress_blockers,
        )
    if rest_seconds is None:
        _base_value_issue(
            field_name="rest", raw_text=base_raw.get("rest"), cell=cells["rest"],
            sheet=sheet, day=day.label, exercise=exercise, issues=issues,
            suppress_blockers=suppress_blockers,
        )
    prescriptions: list[CyclePrescription] = []
    for week_label in weeks:
        week = next(
            (candidate
            for candidate in day.weeks
            if normalize_name(candidate.label) == normalize_name(week_label)),
            None,
        )
        if week is None and config.program.base_cycle_count is None:
            raise WorkbookError(f"Selected cycle has no safely discovered source week: {week_label}")
        week_cell = make_cell_reference(row, week.plan_column) if week is not None else None
        source_cell = snapshot.cells.get(week_cell) if week_cell is not None else None
        source_week = (
            _raw(source_cell)
            if source_cell is not None and source_cell.formula is None
            else None
        )
        raw_week = source_week if config.program.prescription_source == "selected_week" else None
        if source_week and config.program.prescription_source == "base" and not suppress_blockers:
            issues.append(ProgramIssue(
                severity="warning", code="weekly_update_not_applied",
                message="Base program mode: weekly instruction retained for later review, not applied",
                sheet=sheet, cell=week_cell, day=day.label, exercise=exercise,
                cycle=week_label, raw_text=source_week,
            ))
        parsed_week = _parse_week(raw_week)
        if notes_policy and raw_week and re.fullmatch(r"\d+(?:\.\d+)?", raw_week):
            # Unlabelled numbers in coach weeks can be weights, not rep targets.
            parsed_week = None
        raw_unparsed = raw_week if raw_week is not None and parsed_week is None else None
        if raw_unparsed is not None and not suppress_blockers:
            issues.append(
                ProgramIssue(
                    severity="warning" if notes_policy else "blocking",
                    code="coach_instruction_in_notes" if notes_policy else "unsupported_week_instruction",
                    message=("Selected-week instruction retained verbatim in exercise notes" if notes_policy
                             else "Selected-week text is not a fully supported prescription"),
                    sheet=sheet,
                    cell=week_cell,
                    day=day.label,
                    exercise=exercise,
                    cycle=week_label,
                    raw_text=raw_week,
                )
            )
        parsed_week = parsed_week or _ParsedWeek()
        minimum, maximum = rep_range or (rep_list[0] if rep_list else (None, None))
        if rep_range and maximum is None and parsed_week.rep_max is not None and not suppress_blockers:
            issues.append(ProgramIssue(
                severity="blocking", code="conflicting_base_and_week",
                message="Weekly bounded range conflicts with a minimum-only base target",
                sheet=sheet, day=day.label, exercise=exercise, cycle=week_label, cell=week_cell,
            ))
        if rep_list and (parsed_week.rep_min is not None or parsed_week.rep_max is not None):
            if any(target != (parsed_week.rep_min, parsed_week.rep_max) for target in rep_list) and not suppress_blockers:
                issues.append(ProgramIssue(
                    severity="blocking", code="conflicting_base_and_week",
                    message="Weekly rep target conflicts with the base per-set list",
                    sheet=sheet, day=day.label, exercise=exercise, cycle=week_label, cell=week_cell,
                ))
        explicit_types = {
            kind for kind, pattern in (
                ("myo", r"\bmyo(?:[ -]?reps?|[ -]?sets?)?\b"),
                ("drop", r"\bdrop[ -]?sets?\b"),
                ("superset", r"\bsuper[ -]?sets?\b"),
            )
            if re.search(pattern, " ".join((*base_raw.values(), raw_week or "")), re.IGNORECASE)
        }
        effective_type = next(iter(explicit_types)) if len(explicit_types) == 1 else set_type
        if (len(explicit_types) > 1 or (set_type and explicit_types
                                      and set_type not in explicit_types)) and not suppress_blockers:
            issues.append(ProgramIssue(
                severity="blocking", code="mixed_set_types",
                message="Multiple set types need individual-set review", sheet=sheet,
                day=day.label, exercise=exercise, cycle=week_label,
            ))
        default_type = config.program.defaults.set_type
        if configured_superset and effective_type is None and default_type == "standard":
            effective_type = "superset"
        resolved_set_type = _resolve_field(
            name="set type", base_value=effective_type, base_cell=cells["style"],
            base_raw=base_raw.get("style"), week_value=None, week_cell=week_cell,
            week_raw=raw_week, default_value=default_type, sheet=sheet, day=day.label,
            exercise=exercise, cycle=week_label, issues=issues,
            suppress_blockers=suppress_blockers,
        )
        if configured_superset and set_type is None and not explicit_types and effective_type:
            resolved_set_type = _field(effective_type, "config_superset", None, None)
        elif len(explicit_types) == 1:
            # Point review back to the actual instruction, not the category cell.
            pattern = {
                "myo": r"\bmyo(?:[ -]?reps?|[ -]?sets?)?\b",
                "drop": r"\bdrop[ -]?sets?\b",
                "superset": r"\bsuper[ -]?sets?\b",
            }[effective_type]
            if raw_week and re.search(pattern, raw_week, re.IGNORECASE):
                resolved_set_type = _field(effective_type, "coach_week", week_cell, raw_week)
            else:
                key = next(key for key, value in base_raw.items()
                           if re.search(pattern, value, re.IGNORECASE))
                resolved_set_type = _field(
                    effective_type, "coach_base",
                    make_cell_reference(row, day.columns.get(key, day.columns["exercise"])),
                    base_raw[key],
                )
        deferred_reps = bool(notes_policy and blank_reps_allowed and re.fullmatch(
            r"(?:read|check)\s+(?:the\s+)?week\)?", base_raw.get("reps", ""), re.IGNORECASE
        ))
        if deferred_reps:
            parsed_week = _ParsedWeek(
                set_count=parsed_week.set_count, rir=parsed_week.rir,
                rest_seconds=parsed_week.rest_seconds,
            )
        notes = tuple(f"Coach {key}: {value}" for key, value in base_raw.items()) if notes_policy else ()
        if notes_policy and raw_week:
            notes += (f"{week_label}: {raw_week}",)
        if notes_policy and date_rep:
            notes += ("Rep target needs review: Excel stored the coach rep cell as a date.",)
        if notes_policy and rest_target and rest_target.ranged:
            notes += (f"Import setting: use upper rest duration ({rest_seconds} seconds).",)
        if notes_policy and ranged_sets:
            notes += (f"Import setting: use upper set count ({set_count} sets).",)
        if notes_policy and resolved_set_type.source == "config_default":
            notes += ("Import setting: standard sets unless another set type is specified.",)
        prescription = CyclePrescription(
            cycle=week_label,
            set_count=_resolve_field(
                name="set count", base_value=set_count, base_cell=cells["sets"],
                base_raw=base_raw.get("sets"), week_value=parsed_week.set_count,
                week_cell=week_cell, week_raw=raw_week, default_value=None,
                sheet=sheet, day=day.label, exercise=exercise, cycle=week_label,
                issues=issues, suppress_blockers=suppress_blockers,
            ),
            set_type=resolved_set_type,
            rep_min=_resolve_field(
                name="minimum reps", base_value=minimum, base_cell=cells["reps"],
                base_raw=base_raw.get("reps"), week_value=parsed_week.rep_min,
                week_cell=week_cell, week_raw=raw_week,
                default_value=config.program.defaults.rep_min, sheet=sheet,
                day=day.label, exercise=exercise, cycle=week_label, issues=issues,
                suppress_blockers=suppress_blockers,
                allow_blank=blank_reps_allowed,
            ),
            rep_max=(_field(None, "coach_unbounded", cells["reps"], base_raw.get("reps"))
                     if rep_range and maximum is None else _resolve_field(
                name="maximum reps", base_value=maximum, base_cell=cells["reps"],
                base_raw=base_raw.get("reps"), week_value=parsed_week.rep_max,
                week_cell=week_cell, week_raw=raw_week,
                default_value=config.program.defaults.rep_max, sheet=sheet,
                day=day.label, exercise=exercise, cycle=week_label, issues=issues,
                suppress_blockers=suppress_blockers,
                allow_blank=blank_reps_allowed,
            )),
            rir=_resolve_field(
                name="RIR", base_value=None, base_cell=None, base_raw=None,
                week_value=parsed_week.rir, week_cell=week_cell,
                week_raw=raw_week, default_value=config.program.defaults.rir,
                sheet=sheet, day=day.label, exercise=exercise, cycle=week_label,
                issues=issues, suppress_blockers=suppress_blockers,
                allow_blank=blank_targets,
            ),
            rest_seconds=_resolve_field(
                name="rest", base_value=rest_seconds, base_cell=cells["rest"],
                base_raw=base_raw.get("rest"), week_value=parsed_week.rest_seconds,
                week_cell=week_cell, week_raw=raw_week,
                default_value=config.program.defaults.rest_seconds, sheet=sheet,
                day=day.label, exercise=exercise, cycle=week_label, issues=issues,
                suppress_blockers=suppress_blockers,
                allow_blank=blank_targets,
            ),
            notes=notes if notes_policy else ((raw_unparsed,) if raw_unparsed else ()),
            raw_week_text=source_week,
            raw_unparsed_text=(source_week if config.program.prescription_source == "base" else raw_unparsed),
        )
        if rep_list:
            prescription = replace(prescription, set_rep_targets=tuple(
                RepTarget(_field(lo, "coach_base", cells["reps"], base_raw.get("reps")),
                          _field(hi, "coach_base", cells["reps"], base_raw.get("reps")))
                for lo, hi in rep_list
            ))
        if rest_target and prescription.rest_seconds.source == "coach_base":
            prescription = replace(prescription, rest_seconds=_field(
                prescription.rest_seconds.value, rest_target.source,
                cells["rest"], base_raw.get("rest"),
            ))
        if ranged_sets and prescription.set_count.source == "coach_base":
            prescription = replace(prescription, set_count=_field(
                set_count, "coach_range_upper_by_policy", cells["sets"], base_raw.get("sets"),
            ))
        for key, fields in (("sets", ("set_count",)), ("reps", ("rep_min", "rep_max"))):
            if key in overridden:
                prescription = replace(prescription, **{
                    field: replace(getattr(prescription, field), source="config_reviewed_override",
                                   raw_text=original_base.get(key))
                    for field in fields if getattr(prescription, field).source != "conflict"
                })
        if "reps" in overridden and prescription.set_rep_targets:
            prescription = replace(prescription, set_rep_targets=tuple(
                RepTarget(replace(target.minimum, source="config_reviewed_override", raw_text=original_base.get("reps")),
                          replace(target.maximum, source="config_reviewed_override", raw_text=original_base.get("reps")))
                for target in prescription.set_rep_targets
            ))
        prescription = _apply_set_layout(
            prescription, set_types=set_types, blank_reps=blank_rep_targets,
            sheet=sheet, day=day.label, exercise=exercise, issues=issues,
            suppress_blockers=suppress_blockers,
        )
        if notes_policy and config.program.notes_mode == "concise":
            concise = list(rule.program_notes) if rule and rule.program_notes is not None else []
            variation = base_raw.get("variation")
            if (not rule or rule.program_notes is None) and variation and (
                    not rule or normalize_name(variation) != normalize_name(rule.canonical)):
                concise.append(variation)
            for key, parsed in (("sets", set_count), ("reps", rep_range or rep_list), ("rest", rest_seconds)):
                if base_raw.get(key) and (parsed is None or parsed == ()):
                    concise.append(f"{key.capitalize()}: {base_raw[key]}")
            if blank_rep_targets and (rep_range or rep_list):
                concise.append(f"Coach rep guidance: {base_raw['reps']}")
            if rep_range and re.search(r"\b(?:ea\.?|each)\b", base_raw.get("reps", ""), re.IGNORECASE):
                concise.append("Reps are per side.")
            if per_side_sets:
                concise.append("Sets are per side.")
            if rest_target and rest_target.qualifier:
                concise.append(f"Rest: {base_raw['rest']}")
            if raw_week:
                concise.append(raw_week)
            prescription = replace(prescription, notes=tuple(dict.fromkeys(concise)))
        if (config.program.minimum_rep_policy == "notes_only"
                and config.program.allow_blank_targets and notes_policy
                and type(prescription.rep_min.value) is int
                and prescription.rep_max.value is None
                and prescription.rep_min.source != "conflict"
                and prescription.rep_max.source in {"coach_unbounded", "config_reviewed_override"}):
            # Preserve minimum intent after concise-note and explicit set-layout policies.
            # Blank targets are verified; native unbounded targets are not.
            raw_minimum = base_raw.get("reps") or f"{prescription.rep_min.value}+ reps"
            note = f"Coach rep minimum: {raw_minimum} (set target manually)."
            prescription = replace(
                prescription,
                rep_min=replace(prescription.rep_min, value=None, source="blank_by_policy"),
                rep_max=replace(prescription.rep_max, value=None, source="blank_by_policy"),
                notes=tuple(dict.fromkeys((*prescription.notes, note))),
            )
            if not suppress_blockers:
                issues.append(ProgramIssue(
                    severity="warning", code="minimum_reps_in_notes",
                    message="Configured notes-only minimum policy: rep targets blank for manual entry",
                    sheet=sheet, cell=cells["reps"], day=day.label, exercise=exercise,
                    cycle=week_label, raw_text=raw_minimum,
                ))
        prescription = replace(
            prescription,
            notes=prepare_program_notes(
                prescription.notes, config.program.note_text_policy
            ),
        )
        prescriptions.append(prescription)
    return tuple(prescriptions)


def _day_designation(snapshot, day: _DayLayout) -> tuple[str | None, str | None, bool]:
    headings = [split_cell_reference(ref)[1] for ref, cell in snapshot.cells.items()
                if split_cell_reference(ref)[0] == day.header_row and _raw(cell) == day.label]
    if len(headings) != 1 or headings[0] in day.columns.values():
        return None, None, False
    candidates = [(ref, cell) for ref, cell in snapshot.cells.items()
                  if split_cell_reference(ref)[1] == headings[0]
                  and day.header_row < split_cell_reference(ref)[0] <= day.end_row
                  and (cell.formula is not None or _raw(cell))]
    if len(candidates) != 1 or candidates[0][1].formula is not None:
        return None, None, bool(candidates)
    reference, cell = candidates[0]
    if not isinstance(cell.value, str):
        return None, None, True
    return _raw(cell), reference, False


def _expand_program_exercise(
    exercise: OrderedExercise, rule: ExerciseRule | None, snapshot: SheetSnapshot,
    day: _DayLayout, sheet: str, issues: list[ProgramIssue],
) -> tuple[OrderedExercise, ...]:
    """Expand one reviewed base row without inferring allocation or supersets."""
    expansion = rule.program_expansion if rule else None
    if expansion is None or exercise.excluded:
        return (exercise,)
    variation_column = day.columns.get("variation", day.columns["exercise"])
    guard_cells = [snapshot.cells.get(make_cell_reference(exercise.source_row, column))
                   for column in (variation_column, day.columns["sets"])]
    guards_match = (
        exercise.raw_base_fields.get("variation") == expansion.expected_variation
        and exercise.raw_base_fields.get("sets") == expansion.expected_sets
        and all(cell is not None and cell.formula is None for cell in guard_cells)
    )
    unsupported = exercise.superset is not None or any(
        rx.set_rep_targets or rx.set_types or rx.set_type.value != "standard"
        for rx in exercise.prescriptions
    )
    code = ("stale_program_expansion" if not guards_match else
            "unsupported_program_expansion" if unsupported else "reviewed_program_expansion")
    issues.append(ProgramIssue(
        severity="warning" if guards_match and not unsupported else "blocking", code=code,
        message=("Reviewed source row expanded into independent sequential exercises with explicit sets each"
                 if code == "reviewed_program_expansion" else
                 "Expansion source guards no longer match literal coach cells; retaining unsplit source row"
                 if code == "stale_program_expansion" else
                 "Sequential expansion cannot allocate per-set targets, special sets or supersets"),
        sheet=sheet, cell=exercise.source_cell, day=day.label, exercise=exercise.coach_name,
        raw_text=exercise.raw_base_fields.get("variation"),
    ))
    if not guards_match or unsupported:
        return (exercise,)
    children = []
    for index, child in enumerate(expansion.exercises, start=1):
        prescriptions = tuple(replace(rx, set_count=PrescriptionField(
            child.sets, "config_program_expansion",
            make_cell_reference(exercise.source_row, day.columns["sets"]), expansion.expected_sets,
        )) for rx in exercise.prescriptions)
        children.append(replace(
            exercise, order=exercise.order + index - 1, macrofactor_name=child.canonical,
            mapping_status="exact_expansion", prescriptions=prescriptions,
            custom_exercise=child.macrofactor_custom, macrofactor_available=child.macrofactor_available,
            expansion=ExpansionProvenance(rule.canonical, index, len(expansion.exercises),
                                          expansion.expected_variation, expansion.expected_sets, child.sets),
        ))
        if child.macrofactor_custom:
            issues.append(ProgramIssue(
                severity="warning", code="custom_macrofactor_exercise",
                message=f"Confirm expanded custom exercise already exists in MacroFactor: {child.canonical}",
                sheet=sheet, cell=exercise.source_cell, day=day.label, exercise=exercise.coach_name,
            ))
        if not child.macrofactor_available:
            issues.append(ProgramIssue(
                severity="blocking", code="unavailable_macrofactor_exercise",
                message=f"Expanded MacroFactor exercise is marked unavailable: {child.canonical}",
                sheet=sheet, cell=exercise.source_cell, day=day.label, exercise=exercise.coach_name,
            ))
    return tuple(children)


def parse_coach_program(
    path: str | Path,
    config: BridgeConfig,
    sheet_name: str,
    block_identifier: str,
    included_weeks: tuple[str, ...],
) -> ProgramParseResult:
    if not included_weeks:
        raise WorkbookError("Select at least one included week")
    package = XlsxPackage(path)
    sheet = package.sheet_by_name(sheet_name)
    matches = [
        layout
        for layout in _discover_sheet_layouts(package, sheet, config)
        if layout.option.identifier == block_identifier
    ]
    if len(matches) != 1:
        raise WorkbookError(
            f"Program block {block_identifier!r} was not found uniquely in {sheet_name!r}"
        )
    layout = matches[0]
    available = {normalize_name(label): label for label in layout.option.week_labels}
    normalized_weeks = [normalize_name(label) for label in included_weeks]
    if len(set(normalized_weeks)) != len(normalized_weeks):
        raise WorkbookError("Included weeks must be unique")
    missing = [label for label in included_weeks if normalize_name(label) not in available]
    if missing:
        raise WorkbookError(
            f"Program block does not safely expose selected week(s): {', '.join(missing)}"
        )
    selected_weeks = tuple(available[normalize_name(label)] for label in included_weeks)
    snapshot = package.sheet_snapshot(sheet)
    date_styles = _date_style_ids(path)
    issues: list[ProgramIssue] = []
    skipped: list[dict[str, object]] = []
    workout_days: list[WorkoutDay] = []
    for day_order, day in enumerate(layout.days, start=1):
        for week in day.weeks:
            if week.aligned_inherited:
                issues.append(ProgramIssue(
                    severity="warning", code="aligned_week_header_inherited",
                    message="Missing week header uses the verified same-block column alignment",
                    sheet=sheet_name, cell=week.header_cell, day=day.label, cycle=week.label,
                ))
        designation, designation_cell, ambiguous = _day_designation(snapshot, day)
        day_optional = day.optional or bool(designation and "optional" in normalize_name(designation))
        day_exercises: list[OrderedExercise] = []
        exercise_order = 0
        for row in range(day.header_row + 1, day.end_row + 1):
            exercise_cell = make_cell_reference(row, day.columns["exercise"])
            coach_name = _raw(snapshot.cells.get(exercise_cell))
            if coach_name is None:
                continue
            for week in day.weeks:
                plan_reference = make_cell_reference(row, week.plan_column)
                plan_cell = snapshot.cells.get(plan_reference)
                if (normalize_name(week.label) in normalized_weeks and plan_cell is not None
                        and plan_cell.formula is not None):
                    issues.append(ProgramIssue(
                        severity="blocking", code="formula_prescription_cell",
                        message="Selected weekly planned cells must be literal, not cached formulas",
                        sheet=sheet_name, cell=plan_reference, day=day.label,
                        exercise=coach_name, cycle=week.label,
                        raw_text=_raw(plan_cell),
                    ))
            raw_base: dict[str, str] = {}
            for key in ("style", "sets", "reps", "rest"):
                reference = make_cell_reference(row, day.columns[key])
                cell = snapshot.cells.get(reference)
                if cell is not None and cell.formula is not None:
                    issues.append(ProgramIssue(
                        severity="blocking", code="formula_prescription_cell",
                        message="Base prescription cells must be literal, not cached formulas",
                        sheet=sheet_name, cell=reference, day=day.label,
                        exercise=coach_name, raw_text=_raw(cell),
                    ))
                    continue
                if (value := _raw(cell)) is not None:
                    raw_base[key] = value
            variation_column = day.columns.get("variation", day.columns["exercise"])
            variation_reference = make_cell_reference(row, variation_column)
            variation_cell = snapshot.cells.get(variation_reference)
            if variation_cell is not None and variation_cell.formula is not None:
                issues.append(ProgramIssue(
                    severity="blocking", code="formula_prescription_cell",
                    message="Exercise variation cells must be literal, not cached formulas",
                    sheet=sheet_name, cell=variation_reference, day=day.label,
                    exercise=coach_name, raw_text=_raw(variation_cell),
                ))
                raw_base["variation"] = coach_name
            else:
                raw_base["variation"] = _raw(variation_cell) or coach_name
            context = tuple(raw_base.values())
            week_texts = tuple(
                _raw(cell) or ""
                for week in day.weeks if normalize_name(week.label) in normalized_weeks
                for cell in (snapshot.cells.get(make_cell_reference(row, week.plan_column)),)
                if cell is None or cell.formula is None
            )
            if config.program.prescription_source == "base":
                week_texts = ()
            # Week text is context only, never a completed-result column.
            rules = _exercise_rules(coach_name, raw_base["variation"], context + week_texts, config)
            style = raw_base.get("style")
            optional, warmup, cardio = _classification(
                day.label, " ".join((*context, *week_texts)), coach_name
            )
            optional = optional or day_optional
            category_exclusion = (
                "Warmup excluded by program policy" if warmup and config.program.exclude_warmups
                and not (len(rules) == 1 and rules[0].program_include_warmup)
                else "Cardio excluded by program policy" if cardio and config.program.exclude_cardio
                else None
            )
            mapping_status = "exact"
            if category_exclusion:
                mapping_status = "excluded"
                rules_for_output: list[ExerciseRule | None] = [rules[0] if len(rules) == 1 else None]
            elif not rules:
                mapping_status = "unmatched"
                issues.append(
                    ProgramIssue(
                        severity="blocking",
                        code="unmatched_exercise",
                        message="No exact configured coach alias maps this exercise",
                        sheet=sheet_name,
                        cell=exercise_cell,
                        day=day.label,
                        exercise=coach_name,
                    )
                )
                rules_for_output = [None]
            elif len(rules) > 1 and _valid_superset_rules(rules):
                mapping_status = "exact_superset"
                rules_for_output = sorted(rules, key=lambda rule: rule.superset_order)
            elif len(rules) > 1:
                mapping_status = "ambiguous"
                issues.append(
                    ProgramIssue(
                        severity="blocking",
                        code="ambiguous_exercise_mapping",
                        message="Exact coach alias maps to multiple exercises without one ordered superset",
                        sheet=sheet_name,
                        cell=exercise_cell,
                        day=day.label,
                        exercise=coach_name,
                    )
                )
                rules_for_output = [None]
            else:
                rules_for_output = [rules[0]]

            for rule in rules_for_output:
                exercise_order += 1
                excluded = bool(category_exclusion or (rule and rule.program_excluded))
                exclusion_reason = category_exclusion or (rule.program_exclusion_reason if rule else None)
                if excluded:
                    mapping_status_for_rule = "excluded"
                    skipped.append(
                        {
                            "day": day.label,
                            "exercise": coach_name,
                            "canonical": rule.canonical if rule else None,
                            "reason": exclusion_reason,
                        }
                    )
                else:
                    mapping_status_for_rule = mapping_status
                if optional:
                    issues.append(
                        ProgramIssue(
                            severity="warning",
                            code="optional_item",
                            message="Optional day or exercise requires review",
                            sheet=sheet_name,
                            cell=exercise_cell,
                            day=day.label,
                            exercise=coach_name,
                        )
                    )
                if (warmup or cardio) and not excluded:
                    reviewed_warmup = bool(rule and rule.program_include_warmup and not cardio)
                    issues.append(
                        ProgramIssue(
                            severity="warning" if reviewed_warmup else "blocking",
                            code="reviewed_warmup_inclusion" if reviewed_warmup else "unsupported_exercise_category",
                            message=(
                                "Warmup exercise included by reviewed configuration" if reviewed_warmup else
                                "Warmup conversion requires explicit review"
                                if warmup
                                else "Cardio or conditioning conversion is unsupported"
                            ),
                            sheet=sheet_name,
                            cell=exercise_cell,
                            day=day.label,
                            exercise=coach_name,
                        )
                    )
                if rule and rule.macrofactor_custom:
                    issues.append(
                        ProgramIssue(
                            severity="warning",
                            code="custom_macrofactor_exercise",
                            message="Confirm this custom exercise already exists in MacroFactor",
                            sheet=sheet_name,
                            cell=exercise_cell,
                            day=day.label,
                            exercise=coach_name,
                        )
                    )
                if rule and not rule.macrofactor_available and not excluded:
                    issues.append(
                        ProgramIssue(
                            severity="blocking",
                            code="unavailable_macrofactor_exercise",
                            message="Configured MacroFactor exercise is marked unavailable",
                            sheet=sheet_name,
                            cell=exercise_cell,
                            day=day.label,
                            exercise=coach_name,
                        )
                    )
                prescriptions = _prescriptions(
                    snapshot=snapshot,
                    sheet=sheet_name,
                    day=day,
                    row=row,
                    exercise=coach_name,
                    base_raw=raw_base,
                    weeks=selected_weeks,
                    config=config,
                    issues=issues,
                    suppress_blockers=excluded,
                    configured_superset=bool(rule and rule.superset_group),
                    date_styles=date_styles,
                    set_types=rule.program_set_types if rule else (),
                    blank_rep_targets=bool(rule and rule.program_blank_rep_targets),
                    rule=rule,
                )
                superset = (
                    SupersetMembership(rule.superset_group, rule.superset_order)
                    if rule and rule.superset_group
                    else None
                )
                day_exercises.append(
                    OrderedExercise(
                        order=exercise_order,
                        source_row=row,
                        source_cell=exercise_cell,
                        coach_name=coach_name,
                        macrofactor_name=rule.canonical if rule else None,
                        mapping_status=mapping_status_for_rule,
                        raw_base_fields=raw_base,
                        prescriptions=prescriptions,
                        superset=superset,
                        excluded=excluded,
                        exclusion_reason=exclusion_reason,
                        custom_exercise=bool(rule and rule.macrofactor_custom),
                        macrofactor_available=bool(rule and rule.macrofactor_available),
                        optional=optional,
                        warmup=warmup,
                        cardio=cardio,
                    )
                )
                expanded = _expand_program_exercise(day_exercises[-1], rule, snapshot, day, sheet_name, issues)
                day_exercises[-1:] = expanded
                exercise_order += len(expanded) - 1
        _validate_day_supersets(
            day=day,
            exercises=day_exercises,
            config=config,
            sheet_name=sheet_name,
            issues=issues,
        )
        if not day_exercises and config.program.exclude_empty_days:
            skipped.append({
                "day": day.label,
                "exercise": None,
                "canonical": None,
                "reason": "No coach-authored exercise rows",
            })
            issues.append(ProgramIssue(
                severity="warning",
                code="empty_day_excluded",
                message="Configured policy omitted a day heading with no coach-authored exercise rows",
                sheet=sheet_name,
                day=day.label,
            ))
            continue
        if ambiguous and config.program.use_day_designations:
            issues.append(ProgramIssue(
                severity="warning", code="ambiguous_day_designation",
                message="No unique literal day designation; retaining the original day label",
                sheet=sheet_name, day=day.label,
            ))
        workout_days.append(
            WorkoutDay(
                label=day.label,
                order=len(workout_days) + 1,
                optional=day_optional,
                exercises=tuple(day_exercises),
                designation=designation,
                designation_cell=designation_cell,
                export_name=(designation if config.program.use_day_designations and designation else day.label),
            )
        )

    program = Program(
        name=f"{sheet_name} {block_identifier}",
        cycle_name=("Base program repeated across selected weeks" if config.program.prescription_source == "base"
                    else "Selected coach weeks"),
        cycles=tuple(
            ProgramCycle(label=label, order=index)
            for index, label in enumerate(selected_weeks, start=1)
        ),
        days=tuple(workout_days),
        prescription_source=config.program.prescription_source,
        color=config.program.color,
        icon=config.program.icon,
    )
    return ProgramParseResult(
        program=program,
        issues=tuple(issues),
        skipped_items=tuple(skipped),
    )
