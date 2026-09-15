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
    make_cell_reference,
    split_cell_reference,
    split_range,
)
from .program_models import (
    CyclePrescription,
    OrderedExercise,
    PrescriptionField,
    Program,
    ProgramBlockOption,
    ProgramCycle,
    ProgramIssue,
    ProgramParseResult,
    SupersetMembership,
    WorkoutDay,
)


@dataclass(frozen=True)
class _WeekLayout:
    label: str
    header_cell: str
    plan_column: int
    completed_columns: tuple[int, ...]
    safe: bool
    reason: str | None = None


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
) -> tuple[_WeekLayout, ...]:
    candidates: list[tuple[int, int, str, str]] = []
    for reference, cell in snapshot.cells.items():
        row, column = split_cell_reference(reference)
        if row not in {max(1, header_row - 1), header_row}:
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
) -> int:
    # Standalone weekly notes below a table do not extend its exercise rows.
    relevant_columns = tuple(columns.values())
    exercise_column = columns["exercise"]
    found_exercise = False
    for row in range(header_row + 1, provisional_end_row + 1):
        if _raw(snapshot.cells.get(make_cell_reference(row, exercise_column))) is not None:
            found_exercise = True
        if found_exercise and all(
            _raw(snapshot.cells.get(make_cell_reference(row, column))) is None
            for column in relevant_columns
        ):
            return row - 1
    return provisional_end_row


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
    path: str | Path, config: BridgeConfig
) -> tuple[ProgramBlockOption, ...]:
    package = XlsxPackage(path)
    sheets = package.sheets
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


def _parse_reps(raw: str | None) -> tuple[int, int] | None:
    if raw is None:
        return None
    match = re.fullmatch(
        r"(\d+)(?:\s*(?:[-–]|to)\s*(\d+))?(?:\s*reps?)?",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    minimum = int(match.group(1))
    maximum = int(match.group(2) or match.group(1))
    if minimum < 1 or maximum < minimum:
        return None
    return minimum, maximum


def _parse_rest(raw: str | None, range_policy: str = "block") -> int | None:
    if raw is None:
        return None
    match = re.fullmatch(
        r"(\d+)(?:\s*(?:[-–]|to)\s*(\d+))?\s*"
        r"(s|sec|secs|second|seconds|m|min|mins|minute|minutes)"
        r"(?:\s*rest)?(?:\s*\(timed\))?",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    amount = int(match.group(1))
    if amount < 1:
        return None
    if match.group(2):
        upper = int(match.group(2))
        if range_policy != "upper" or upper < amount:
            return None
        amount = upper
    return amount * 60 if match.group(3).casefold().startswith("m") else amount


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
) -> tuple[CyclePrescription, ...]:
    cells = {
        key: make_cell_reference(row, day.columns[key])
        for key in ("style", "sets", "reps", "rest")
    }
    set_count = _parse_integer(base_raw.get("sets"))
    rep_range = _parse_reps(base_raw.get("reps"))
    rep_cell = snapshot.cells.get(cells["reps"])
    date_rep = bool(rep_cell and rep_cell.style in (date_styles or set())
                    and isinstance(rep_cell.value, (int, float)))
    if date_rep:
        rep_range = None
    rest_seconds = _parse_rest(base_raw.get("rest"), config.program.rest_range_policy)
    set_type = SET_TYPE_ALIASES.get(normalize_name(base_raw.get("style", "")))
    if set_count is None:
        _base_value_issue(
            field_name="set count", raw_text=base_raw.get("sets"), cell=cells["sets"],
            sheet=sheet, day=day.label, exercise=exercise, issues=issues,
            suppress_blockers=suppress_blockers,
        )
    notes_policy = config.program.preserve_coach_notes
    blank_targets = config.program.allow_blank_targets
    if date_rep and not suppress_blockers:
        issues.append(ProgramIssue(
            severity="warning" if notes_policy and blank_targets else "blocking",
            code="date_formatted_rep_target",
            message="Rep cell is stored as an Excel date; review the original target",
            sheet=sheet, cell=cells["reps"], day=day.label, exercise=exercise,
            raw_text=base_raw.get("reps"),
        ))
    if rep_range is None and not (notes_policy and blank_targets):
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
            candidate
            for candidate in day.weeks
            if normalize_name(candidate.label) == normalize_name(week_label)
        )
        week_cell = make_cell_reference(row, week.plan_column)
        raw_week = _raw(snapshot.cells.get(week_cell))
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
        minimum, maximum = rep_range or (None, None)
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
        deferred_reps = bool(notes_policy and blank_targets and re.fullmatch(
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
        if notes_policy and rest_seconds is not None and _parse_rest(base_raw.get("rest")) is None:
            notes += (f"Import setting: use upper rest duration ({rest_seconds} seconds).",)
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
                allow_blank=blank_targets,
            ),
            rep_max=_resolve_field(
                name="maximum reps", base_value=maximum, base_cell=cells["reps"],
                base_raw=base_raw.get("reps"), week_value=parsed_week.rep_max,
                week_cell=week_cell, week_raw=raw_week,
                default_value=config.program.defaults.rep_max, sheet=sheet,
                day=day.label, exercise=exercise, cycle=week_label, issues=issues,
                suppress_blockers=suppress_blockers,
                allow_blank=blank_targets,
            ),
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
            raw_week_text=raw_week,
            raw_unparsed_text=raw_unparsed,
        )
        if (rest_seconds is not None and _parse_rest(base_raw.get("rest")) is None
                and prescription.rest_seconds.source != "conflict"):
            prescription = replace(prescription, rest_seconds=_field(
                prescription.rest_seconds.value, "coach_range_upper_by_policy",
                cells["rest"], base_raw.get("rest"),
            ))
        prescriptions.append(prescription)
    return tuple(prescriptions)


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
        day_exercises: list[OrderedExercise] = []
        exercise_order = 0
        for row in range(day.header_row + 1, day.end_row + 1):
            exercise_cell = make_cell_reference(row, day.columns["exercise"])
            coach_name = _raw(snapshot.cells.get(exercise_cell))
            if coach_name is None:
                continue
            raw_base = {
                key: value
                for key in ("style", "sets", "reps", "rest")
                if (
                    value := _raw(
                        snapshot.cells.get(make_cell_reference(row, day.columns[key]))
                    )
                )
                is not None
            }
            variation_column = day.columns.get("variation", day.columns["exercise"])
            raw_base["variation"] = _raw(
                snapshot.cells.get(make_cell_reference(row, variation_column))
            ) or coach_name
            context = tuple(raw_base.values())
            week_texts = tuple(
                _raw(snapshot.cells.get(make_cell_reference(row, week.plan_column))) or ""
                for week in day.weeks if normalize_name(week.label) in normalized_weeks
            )
            # Week text is context only, never a completed-result column.
            rules = _exercise_rules(coach_name, raw_base["variation"], context + week_texts, config)
            style = raw_base.get("style")
            optional, warmup, cardio = _classification(
                day.label, " ".join((*context, *week_texts)), coach_name
            )
            category_exclusion = (
                "Warmup excluded by program policy" if warmup and config.program.exclude_warmups
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
                    issues.append(
                        ProgramIssue(
                            severity="blocking",
                            code="unsupported_exercise_category",
                            message=(
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
        _validate_day_supersets(
            day=day,
            exercises=day_exercises,
            config=config,
            sheet_name=sheet_name,
            issues=issues,
        )
        workout_days.append(
            WorkoutDay(
                label=day.label,
                order=day_order,
                optional=day.optional,
                exercises=tuple(day_exercises),
            )
        )

    program = Program(
        name=f"{sheet_name} {block_identifier}",
        cycle_name="Selected coach weeks",
        cycles=tuple(
            ProgramCycle(label=label, order=index)
            for index, label in enumerate(selected_weeks, start=1)
        ),
        days=tuple(workout_days),
    )
    return ProgramParseResult(
        program=program,
        issues=tuple(issues),
        skipped_items=tuple(skipped),
    )
