from __future__ import annotations

from decimal import Decimal

from .models import ExerciseRule, SetRecord


def _number(value: Decimal) -> str:
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


def format_sets(records: list[SetRecord], rule: ExerciseRule) -> str:
    """Format one exercise's ordered, non-zero completed sets."""
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
