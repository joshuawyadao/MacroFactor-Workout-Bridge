"""Read-back semantic checks independent of the OOXML writer's change map.

These checks establish workbook consistency, never successful import by the app.
The contract fingerprint is deliberately free of exercise names and coach text.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import groupby
from pathlib import Path
from typing import Any

from .ooxml import WorkbookError, XlsxPackage, make_cell_reference, split_cell_reference
from .program_models import CyclePrescription, Program
from .program_template import ProgramTemplateSchema, inspect_program_template


@dataclass(frozen=True)
class OutputAudit:
    passed: bool
    errors: tuple[str, ...]
    checked_cells: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _layout(schema: ProgramTemplateSchema) -> dict[str, Any]:
    return {
        "day_count": len(schema.days),
        "set_capacity": len(schema.sets),
        "header_row": schema.header_row,
        "metadata_cells": [schema.program_cell, schema.cycles_cell, schema.block_cell,
                           schema.cycle_cell, schema.color_cell, schema.icon_cell],
        "role_columns": [schema.day_column, schema.exercise_column,
                         schema.skipped_column, schema.notes_column],
        "set_columns": [asdict(columns) for columns in schema.sets],
    }


def _set_values(rx: CyclePrescription, number: int) -> tuple[object, ...]:
    """Translate the independently verified public export labels, not writer output."""
    count = rx.set_count.value
    if type(count) is not int or count < 1:
        raise WorkbookError("Prescription has no positive integer set count")
    if number > count:
        return (None, None, None, None, None)
    if rx.set_types and len(rx.set_types) != count:
        raise WorkbookError("Per-set type count differs from the prescribed count")
    if rx.set_rep_targets and len(rx.set_rep_targets) != count:
        raise WorkbookError("Per-set rep target count differs from the prescribed count")
    if rx.set_duration_targets and len(rx.set_duration_targets) != count:
        raise WorkbookError("Per-set duration count differs from the prescribed count")
    kind = rx.set_types[number - 1].value if rx.set_types else rx.set_type.value
    # Native membership lives in the exercise suffix; its sets stay Standard Set.
    labels = {"standard": "Standard Set", "superset": "Standard Set", "myo": "Myo Set"}
    if kind not in labels:
        raise WorkbookError("Prescription uses an unverified set type")
    target = rx.set_rep_targets[number - 1] if rx.set_rep_targets else None
    lower = target.minimum.value if target else rx.rep_min.value
    upper = target.maximum.value if target else rx.rep_max.value
    if lower is None and upper is None:
        reps = None
    elif type(lower) is int and type(upper) is int and 0 < lower <= upper:
        reps = f"{lower} - {upper}"
    else:
        raise WorkbookError("Prescription has an unsupported rep target")
    for value, minimum, maximum in ((rx.rir.value, 0, 6), (rx.rest_seconds.value, 1, None)):
        if value is not None and (type(value) is not int or value < minimum
                                  or (maximum is not None and value > maximum)):
            raise WorkbookError("Prescription has an unsupported RIR or rest target")
    duration = (rx.set_duration_targets[number - 1].value if rx.set_duration_targets
                else rx.duration_seconds.value if rx.duration_seconds else None)
    if duration is not None and (type(duration) is not int or duration < 1 or reps is not None):
        raise WorkbookError("Prescription has an unsupported or conflicting duration target")
    return labels[kind], reps, rx.rir.value, rx.rest_seconds.value, duration


def _native_duration_provenance_matches(
    program: Program, day: object, exercise: object, rx: CyclePrescription,
    original: dict[str, Any], schema: ProgramTemplateSchema,
) -> bool:
    """Independently verify that inherited durations came from this native row."""
    if not rx.set_duration_targets or not any(
        field.source == "native_template" for field in rx.set_duration_targets
    ):
        return True
    count = rx.set_count.value
    if (type(count) is not int or len(rx.set_duration_targets) != count
        or rx.duration_seconds is not None
        or rx.rep_min.value is not None or rx.rep_max.value is not None
        or rx.set_rep_targets or exercise.raw_base_fields.get("reps")
        or rx.rep_min.raw_text or rx.rep_max.raw_text
        or program.prescription_source == "selected_week" and rx.raw_unparsed_text):
        return False
    label = day.export_name or day.label
    if sum((item.export_name or item.label) == label for item in program.days) != 1:
        return False
    native_days = [item for item in schema.days if original[item.label_cell].value == label]
    if len(native_days) != 1:
        return False
    name = exercise.macrofactor_name
    if exercise.superset is not None:
        name = f"{name} ∈ {exercise.superset.group}"
    if Counter(
        f"{item.macrofactor_name} ∈ {item.superset.group}"
        if item.superset is not None else item.macrofactor_name
        for item in day.exercises if not item.excluded
    )[name] != 1:
        return False
    native_day = native_days[0]
    native_rows = [row for row in native_day.rows
                   if original[make_cell_reference(row, schema.exercise_column)].value == name]
    if len(native_rows) != 1:
        return False
    row = native_rows[0]
    active = [group for group in schema.sets
              if original[make_cell_reference(row, group.set_type)].value is not None]
    if len(active) != count or active != list(schema.sets[:count]):
        return False
    if any(original[make_cell_reference(row, group.rep_range)].value is not None for group in active):
        return False
    return all(
        group.duration is not None
        and field.source == "native_template"
        and field.source_cell == make_cell_reference(row, group.duration)
        and field.value == original[field.source_cell].value
        and (field.value is None or (type(field.value) is int and field.value > 0))
        for field, group in zip(rx.set_duration_targets, active, strict=True)
    )


def audit_program_output(
    program: Program, output_path: str | Path, template_path: str | Path,
) -> OutputAudit:
    """Compare all populated and cleared program fields to freshly read output.

    Excluded rows do not consume output rows; explicitly expanded children do.
    Every cycle is compared because the supported file repeats one cycle layout.
    Errors identify fields/cells, but never disclose exercise names or notes.
    """
    errors: list[str] = []
    checked: set[str] = set()
    try:
        schema = inspect_program_template(output_path)
        template_schema = inspect_program_template(template_path)
        cells = XlsxPackage(output_path).sheet_snapshot(schema.sheet_name).cells
        original = XlsxPackage(template_path).sheet_snapshot(template_schema.sheet_name).cells
    except (OSError, WorkbookError) as exc:
        return OutputAudit(False, (f"Cannot inspect supported program structure: {exc}",), 0)

    def value(reference: str) -> object:
        cell = cells.get(reference)
        return cell.value if cell is not None else None

    def check(reference: str, expected: object, label: str) -> None:
        checked.add(reference)
        if value(reference) != expected:
            errors.append(f"{reference}: {label} does not match the reviewed program")

    output_layout = _layout(schema)
    template_layout = _layout(template_schema)
    # Opt-in generation may remove trailing workout groups while preserving the
    # verified header, role and set-column contract. Program coverage below is
    # the independent authority for the resulting workout count.
    output_layout.pop("day_count")
    template_layout.pop("day_count")
    if output_layout != template_layout:
        errors.append("Output header/metadata layout differs from the verified template")
    if schema.sheet_name != template_schema.sheet_name:
        errors.append("Output worksheet identity differs from the verified template")
    for reference, cell in original.items():
        row, _ = split_cell_reference(reference)
        if row == template_schema.header_row or reference == template_schema.block_cell:
            check(reference, cell.value, "preserved template header")
    check(schema.program_cell, f"Program: {program.name}", "program name")
    check(schema.cycles_cell, f"Cycles: {len(program.cycles)}", "cycle count")
    if not 1 <= len(program.cycles) <= 52:
        errors.append("Program does not contain a supported cycle count")
    for key in ("color", "icon"):
        cell = getattr(schema, f"{key}_cell")
        previous = getattr(template_schema, f"{key}_cell")
        configured = getattr(program, key)
        if configured is not None and cell is None:
            errors.append(f"Output has no {key} metadata for the requested override")
        elif cell is not None:
            expected = (f"{key.capitalize()}: {configured}" if configured is not None
                        else original[previous].value if previous in original else None)
            check(cell, expected, f"program {key}")

    if len(program.days) != len(schema.days):
        errors.append("Output workout count differs from the reviewed program")
    for day_number, (day, output_day) in enumerate(zip(program.days, schema.days), 1):
        check(output_day.label_cell, day.export_name or day.label, "workout label/order")
        for row in output_day.rows[1:]:
            check(make_cell_reference(row, schema.day_column), None, "non-leading workout label")
        exercises = tuple(exercise for exercise in day.exercises if not exercise.excluded)
        if len(exercises) != len(output_day.rows):
            errors.append(f"Workout {day_number}: included exercise coverage differs")
        for exercise, row in zip(exercises, output_day.rows):
            name = exercise.macrofactor_name
            if not name or not exercise.macrofactor_available:
                errors.append(f"Workout {day_number}: exercise has no available exact mapping")
            if exercise.superset is not None:
                name = f"{name} ∈ {exercise.superset.group}"
            check(make_cell_reference(row, schema.exercise_column), name, "exact exercise/order/superset")
            check(make_cell_reference(row, schema.skipped_column), "No", "skipped flag")
            if len(exercise.prescriptions) != len(program.cycles) or not exercise.prescriptions:
                errors.append(f"Row {row}: cycle prescription coverage differs")
            for rx in exercise.prescriptions:
                if not _native_duration_provenance_matches(
                    program, day, exercise, rx, original, template_schema,
                ):
                    errors.append(f"Row {row}: inherited duration does not match native exercise evidence")
                check(make_cell_reference(row, schema.notes_column), "\n".join(rx.notes) or None,
                      "exercise notes")
                if type(rx.set_count.value) is int and rx.set_count.value > len(schema.sets):
                    errors.append(f"Row {row}: prescribed sets exceed output capacity")
                try:
                    for group in schema.sets:
                        expected = _set_values(rx, group.number)
                        columns = (group.set_type, group.rep_range, group.rir, group.rest)
                        labels = ("set type", "rep target", "RIR", "rest")
                        if group.duration is not None:
                            columns += (group.duration,)
                            labels += ("duration",)
                        elif expected[4] is not None:
                            raise WorkbookError("Duration target needs a native Duration column")
                        for column, target, label in zip(
                            columns, expected, labels,
                        ):
                            reference = make_cell_reference(row, column)
                            check(reference, target, label)
                            if label == "duration" and target is not None:
                                cell = cells.get(reference)
                                if cell is None or cell.cell_type not in {None, "n"}:
                                    errors.append(f"{reference}: duration is not stored as a numeric seconds target")
                except WorkbookError as exc:
                    errors.append(f"Row {row}: {exc}")

    body_rows = {row for day in schema.days for row in day.rows}
    role_columns = {schema.day_column, schema.exercise_column, schema.skipped_column, schema.notes_column}
    role_columns.update(column for group in schema.sets for column in
                        (group.set_type, group.rep_range, group.rir, group.rest,
                         *((group.duration,) if group.duration is not None else ())))
    for reference, cell in cells.items():
        row, column = split_cell_reference(reference)
        if row > schema.header_row and row not in body_rows and column in role_columns:
            check(reference, None, "surplus program field outside workouts")
    return OutputAudit(not errors, tuple(dict.fromkeys(errors)), len(checked))


def _runs(values: list[str]) -> str:
    # Repeated identical sets/targets are count changes, not new import features.
    return ">".join(key for key, _ in groupby(values)) or "none"


def inspect_import_contract(path: str | Path) -> dict[str, Any]:
    """Return privacy-free structural features for conservative import sampling.

    This is evidence grouping, not compatibility validation. Numeric targets,
    exercise identities and text contents are excluded. Per-day row counts and
    repeated cycle totals remain separate families so evidence does not silently
    cover a new resized workout shape or program duration. New alternating
    per-set shapes or native superset topology also remain distinct.
    Unsupported active values fail closed rather than inheriting prior evidence.
    """
    schema = inspect_program_template(path)
    cells = XlsxPackage(path).sheet_snapshot(schema.sheet_name).cells
    features: set[str] = set()

    def value(row: int, column: int) -> object:
        cell = cells.get(make_cell_reference(row, column))
        return cell.value if cell is not None else None

    for day in schema.days:
        supersets: dict[str, list[int]] = {}
        superset_order: list[str] = []
        for position, row in enumerate(day.rows):
            name = str(value(row, schema.exercise_column))
            membership = re.search(r" ∈ (SS[1-9]\d*)$", name)
            if membership:
                supersets.setdefault(membership.group(1), []).append(position)
                superset_order.append(membership.group(1))
            elif " ∈ " in name:
                raise WorkbookError("Unverified superset membership representation")
            if value(row, schema.skipped_column) != "No":
                raise WorkbookError("Unverified skipped-exercise representation")
            features.add("notes:" + ("present" if value(row, schema.notes_column) else "blank"))
            types: list[str] = []
            reps: list[str] = []
            rirs: list[str] = []
            rests: list[str] = []
            durations: list[str] = []
            inactive = False
            for group in schema.sets:
                kind = value(row, group.set_type)
                target, rir, rest = (value(row, column) for column in
                                     (group.rep_range, group.rir, group.rest))
                duration = value(row, group.duration) if group.duration is not None else None
                if duration is not None and group.duration is not None:
                    duration_cell = cells[make_cell_reference(row, group.duration)]
                    if duration_cell.cell_type not in {None, "n"}:
                        raise WorkbookError("Unverified duration cell type")
                if kind is None:
                    inactive = True
                    if any(item is not None for item in (target, rir, rest, duration)):
                        raise WorkbookError("Inactive set has nonblank target fields")
                    continue
                if inactive or kind not in {"Standard Set", "Myo Set"}:
                    raise WorkbookError("Unverified or noncontiguous active set types")
                types.append("standard" if kind == "Standard Set" else "myo")
                match = re.fullmatch(r"([1-9]\d*) - ([1-9]\d*)", str(target)) if target is not None else None
                if target is None:
                    reps.append("blank")
                elif match and int(match.group(1)) <= int(match.group(2)):
                    reps.append("equal" if match.group(1) == match.group(2) else "range")
                else:
                    raise WorkbookError("Unverified rep target representation")
                if duration is not None and (type(duration) is not int or duration < 1 or target is not None):
                    raise WorkbookError("Unverified or conflicting duration target representation")
                durations.append("blank" if duration is None else "present")
                for item, output, label, upper in ((rir, rirs, "RIR", 6), (rest, rests, "rest", None)):
                    if item is not None and (type(item) is not int or item < (0 if upper else 1)
                                             or (upper is not None and item > upper)):
                        raise WorkbookError(f"Unverified {label} representation")
                    output.append("blank" if item is None else "present")
            if not types:
                raise WorkbookError("Exercise has no active sets")
            features.add("sets:" + _runs(types))
            features.add("reps:" + _runs(reps))
            features.add("rir:" + _runs(rirs))
            features.add("rest:" + _runs(rests))
            if schema.sets[0].duration is not None:
                features.add("duration:" + _runs(durations))
            # Joint shape prevents independently seen features implying an unseen mix.
            shape_fields = (types, reps, rirs, rests, durations) if schema.sets[0].duration is not None \
                else (types, reps, rirs, rests)
            features.add("set-shape:" + _runs(["/".join(items) for items in zip(*shape_fields)]))
        if not supersets:
            features.add("supersets:none")
        else:
            identities = {group: f"g{index}" for index, group in enumerate(supersets, 1)}
            features.add("superset-topology:" + _runs([identities[group] for group in superset_order]))
        for positions in supersets.values():
            if len(positions) < 2:
                raise WorkbookError("Native superset must contain at least two exercises")
            contiguous = positions == list(range(positions[0], positions[-1] + 1))
            features.add(f"supersets:{len(positions)}:" + ("contiguous" if contiguous else "separated"))
    family = _layout(schema)
    family["exercise_row_counts"] = [len(day.rows) for day in schema.days]
    # The strict schema inspector already requires one positive Cycles metadata.
    family["cycle_count"] = int(str(cells[schema.cycles_cell].value).split(":", 1)[1].strip())
    return {"family": family, "features": sorted(features)}
