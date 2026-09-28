from __future__ import annotations

from decimal import Decimal

from .models import ExerciseRule, SetRecord


def _number(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Result numbers must be finite")
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(int(normalized))
    return format(normalized, "f").rstrip("0").rstrip(".")


def _weight(record: SetRecord, rule: ExerciseRule) -> str:
    raw = record.weight if record.weight is not None else Decimal("0")
    converted = raw * rule.weight_multiplier
    suffix = rule.weight_suffix if converted != 0 else ""
    return f"{_number(converted)}{suffix}"


def _reps(record: SetRecord) -> str:
    if record.reps is None:
        raise ValueError("Cannot format a set without reps")
    return _number(record.reps)


def _validate_numbers(records: list[SetRecord], rule: ExerciseRule) -> None:
    if not rule.weight_multiplier.is_finite() or rule.weight_multiplier <= 0:
        raise ValueError("Weight multiplier must be finite and positive")
    for record in records:
        for field in ("weight", "reps"):
            value = getattr(record, field)
            if value is not None and not value.is_finite():
                raise ValueError(f"Set {field} must be finite (source row {record.source_row})")


def format_sets(records: list[SetRecord], rule: ExerciseRule) -> str:
    """Format one exercise's ordered, non-zero completed sets."""
    _validate_numbers(records, rule)
    output: list[str] = []
    current_weight: str | None = None
    current_index: int | None = None
    current_kind: str | None = None
    for record in records:
        if record.reps is None or record.reps <= 0:
            continue
        kind = record.set_type.casefold().replace("-", " ")
        weight = _weight(record, rule)
        reps = _reps(record)
        if "mini" in kind:
            if current_index is None:
                output.append(f"{weight} x {reps}")
                current_index = len(output) - 1
                current_weight = weight
            elif current_kind in {"myo", "mini"} and weight == current_weight:
                output[current_index] += f"+{reps}"
            else:
                output[current_index] += f"+{weight} x {reps}"
            current_kind = "mini"
            continue
        if "drop" in kind:
            if current_index is None:
                output.append(f"{weight} x {reps}")
                current_index = len(output) - 1
            else:
                output[current_index] += f"→{weight} x {reps}"
            current_weight = weight
            current_kind = "drop"
            continue
        if "myo" in kind:
            output.append(f"{weight} x {reps}")
            current_index = len(output) - 1
            current_weight = weight
            current_kind = "myo"
            continue
        if current_index is not None and current_kind == "standard" and weight == current_weight:
            output[current_index] += f", {reps}"
        else:
            output.append(f"{weight} x {reps}")
            current_index = len(output) - 1
            current_weight = weight
        current_kind = "standard"
    return "; ".join(output)


def format_superset(exercises: list[tuple[list[SetRecord], ExerciseRule]]) -> str:
    """Pair standard superset sets by position in configured exercise order."""
    for records, rule in exercises:
        _validate_numbers(records, rule)
    completed = [
        ([record for record in records if record.reps is not None and record.reps > 0], rule)
        for records, rule in exercises
    ]
    if not completed or any(not records for records, _ in completed):
        raise ValueError("Superset exercises must each contain completed sets")
    counts = {len(records) for records, _ in completed}
    if len(counts) != 1:
        raise ValueError("Superset exercises have different completed-set counts")
    for records, _ in completed:
        if any(
            any(marker in record.set_type.casefold().replace("-", " ") for marker in ("mini", "myo", "drop"))
            for record in records
        ):
            raise ValueError("Paired supersets currently require standard sets")

    output: list[str] = []
    current_weights: str | None = None
    current_index: int | None = None
    for set_index in range(next(iter(counts))):
        weights = "/".join(_weight(records[set_index], rule) for records, rule in completed)
        reps = "/".join(_reps(records[set_index]) for records, _ in completed)
        if current_index is not None and weights == current_weights:
            output[current_index] += f", {reps}"
        else:
            output.append(f"{weights} x {reps}")
            current_index = len(output) - 1
            current_weights = weights
    return "; ".join(output)
