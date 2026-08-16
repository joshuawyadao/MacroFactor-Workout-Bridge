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
