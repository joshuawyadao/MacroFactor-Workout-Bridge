from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import BridgeConfig, EmptyDayMarker, ExerciseRule
from .program_models import (
    BasePrescriptionOverride, ProgramConfig, ProgramDefaults, ProgramExpansion, ProgramExpansionExercise,
    VERIFIED_PROGRAM_COLORS, VERIFIED_PROGRAM_ICONS,
)


class ConfigError(ValueError):
    """Raised when bridge configuration is invalid."""


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _string_list(
    payload: dict[str, object], key: str, default: tuple[str, ...], label: str
) -> tuple[str, ...]:
    value = payload.get(key, list(default))
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ConfigError(f"{label}.{key} must be a non-empty list of strings")
    return tuple(dict.fromkeys(item.strip() for item in value))


def _optional_int(
    payload: dict[str, object], key: str, label: str, *, minimum: int
) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{label}.{key} must be null or an integer >= {minimum}")
    return value


def _load_program_expansion(payload: object) -> ProgramExpansion | None:
    if payload is None:
        return None
    if not isinstance(payload, dict) or set(payload) != {"expected_variation", "expected_sets", "exercises"}:
        raise ConfigError("program_expansion needs expected_variation, expected_sets and exercises")
    if any(not isinstance(payload[key], str) or not payload[key].strip()
           for key in ("expected_variation", "expected_sets")):
        raise ConfigError("program_expansion source guards must be non-empty strings")
    children = payload["exercises"]
    if not isinstance(children, list) or len(children) != 2:
        raise ConfigError("program_expansion needs exactly two ordered exercises")
    parsed = []
    identities = set()
    for child in children:
        if (not isinstance(child, dict) or not {"canonical", "sets"} <= set(child)
                or set(child) - {"canonical", "sets", "macrofactor_custom", "macrofactor_available"}):
            raise ConfigError("Each program_expansion exercise needs canonical and sets; only availability flags are optional")
        name = child["canonical"]
        count = child["sets"]
        if not isinstance(name, str) or not name.strip() or normalize_name(name) in identities:
            raise ConfigError("program_expansion exercise names must be non-empty and unique")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ConfigError("program_expansion sets must be a positive integer for each exercise")
        custom = child.get("macrofactor_custom", False)
        available = child.get("macrofactor_available", True)
        if not isinstance(custom, bool) or not isinstance(available, bool):
            raise ConfigError("program_expansion availability flags must be booleans")
        identities.add(normalize_name(name))
        parsed.append(ProgramExpansionExercise(name.strip(), count, custom, available))
    return ProgramExpansion(payload["expected_variation"].strip(), payload["expected_sets"].strip(), tuple(parsed))


def _load_program_config(
    payload: object, exercise_header_labels: tuple[str, ...], week_pattern: str
) -> ProgramConfig:
    if payload is None:
        return ProgramConfig(
            exercise_header_labels=exercise_header_labels,
            week_header_pattern=week_pattern,
        )
    if not isinstance(payload, dict):
        raise ConfigError("program must be an object")
    day_pattern = payload.get("day_label_pattern", ProgramConfig.day_label_pattern)
    program_week_pattern = payload.get("week_header_pattern", week_pattern)
    week_pair_layout = payload.get("week_pair_layout")
    if week_pair_layout not in {None, "plan_then_result", "result_then_plan"}:
        raise ConfigError(
            "program.week_pair_layout must be plan_then_result, result_then_plan, or null"
        )
    for value, label in (
        (day_pattern, "program.day_label_pattern"),
        (program_week_pattern, "program.week_header_pattern"),
    ):
        if not isinstance(value, str):
            raise ConfigError(f"{label} must be a string")
        try:
            re.compile(value, re.IGNORECASE)
        except re.error as exc:
            raise ConfigError(f"Invalid {label}: {exc}") from exc

    defaults_payload = payload.get("defaults", {})
    if not isinstance(defaults_payload, dict):
        raise ConfigError("program.defaults must be an object")
    default_set_type = defaults_payload.get("set_type")
    if default_set_type not in (None, "standard"):
        raise ConfigError("program.defaults.set_type must be standard or null")
    policy_values = {}
    for key, choices, default in (
        ("sheet_order", ("left_to_right", "right_to_left"), "left_to_right"),
        ("rest_range_policy", ("block", "upper"), "block"),
        ("unitless_rest_policy", ("block", "seconds"), "block"),
        ("set_count_range_policy", ("block", "upper"), "block"),
        ("prescription_source", ("selected_week", "base"), "selected_week"),
        ("week_header_coverage_policy", ("intersection", "aligned_union_base_only"), "intersection"),
        ("notes_mode", ("full", "concise"), "full"),
        ("note_text_policy", ("verbatim", "conservative"), "verbatim"),
        ("minimum_rep_policy", ("block", "notes_only"), "block"),
        ("color", (None, *VERIFIED_PROGRAM_COLORS), None),
        ("icon", (None, *VERIFIED_PROGRAM_ICONS), None),
    ):
        value = payload.get(key, default)
        if value not in choices:
            raise ConfigError(f"program.{key} must be one of {choices}")
        policy_values[key] = value
    if policy_values["week_header_coverage_policy"] == "aligned_union_base_only" and (
        policy_values["prescription_source"] != "base" or week_pair_layout is None
    ):
        raise ConfigError("program.week_header_coverage_policy aligned_union_base_only requires base prescription_source and explicit week_pair_layout")
    for key in ("allow_blank_targets", "preserve_coach_notes", "exclude_warmups", "exclude_cardio",
                "exclude_empty_days", "resize_template_workouts", "use_day_designations"):
        value = payload.get(key, False)
        if not isinstance(value, bool):
            raise ConfigError(f"program.{key} must be a boolean")
        policy_values[key] = value
    base_cycle_count = payload.get("base_cycle_count")
    if base_cycle_count is not None and (
        type(base_cycle_count) is not int or not 1 <= base_cycle_count <= 52
    ):
        raise ConfigError("program.base_cycle_count must be an integer from 1 through 52 or null")
    if base_cycle_count is not None and policy_values["prescription_source"] != "base":
        raise ConfigError("program.base_cycle_count requires program.prescription_source: base")
    if (base_cycle_count is not None
            and policy_values["week_header_coverage_policy"] != "intersection"):
        raise ConfigError(
            "program.base_cycle_count requires the default intersection week-header policy"
        )
    if policy_values["minimum_rep_policy"] == "notes_only" and not (
        policy_values["allow_blank_targets"] and policy_values["preserve_coach_notes"]
    ):
        raise ConfigError("program.minimum_rep_policy notes_only requires allow_blank_targets and preserve_coach_notes")
    defaults = ProgramDefaults(
        set_type=default_set_type,
        rep_min=_optional_int(defaults_payload, "rep_min", "program.defaults", minimum=1),
        rep_max=_optional_int(defaults_payload, "rep_max", "program.defaults", minimum=1),
        rir=_optional_int(defaults_payload, "rir", "program.defaults", minimum=0),
        rest_seconds=_optional_int(
            defaults_payload, "rest_seconds", "program.defaults", minimum=1
        ),
    )
    if (
        defaults.rep_min is not None
        and defaults.rep_max is not None
        and defaults.rep_max < defaults.rep_min
    ):
        raise ConfigError("program.defaults.rep_max must be >= rep_min")
    if (defaults.rep_min is None) != (defaults.rep_max is None):
        raise ConfigError(
            "program.defaults.rep_min and rep_max must both be set or both be null"
        )

    return ProgramConfig(
        day_label_pattern=day_pattern,
        week_header_pattern=program_week_pattern,
        week_pair_layout=week_pair_layout,
        style_header_labels=_string_list(
            payload,
            "style_header_labels",
            ProgramConfig.style_header_labels,
            "program",
        ),
        exercise_header_labels=_string_list(
            payload,
            "exercise_header_labels",
            exercise_header_labels,
            "program",
        ),
        sets_header_labels=_string_list(
            payload,
            "sets_header_labels",
            ProgramConfig.sets_header_labels,
            "program",
        ),
        reps_header_labels=_string_list(
            payload,
            "reps_header_labels",
            ProgramConfig.reps_header_labels,
            "program",
        ),
        rest_header_labels=_string_list(
            payload,
            "rest_header_labels",
            ProgramConfig.rest_header_labels,
            "program",
        ),
        defaults=defaults,
        variation_header_labels=_string_list(
            payload, "variation_header_labels", ProgramConfig.variation_header_labels, "program"
        ),
        base_cycle_count=base_cycle_count,
        **policy_values,
    )


def load_config(path: str | Path) -> BridgeConfig:
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Could not read configuration {config_path}: {exc}") from exc

    workbook = payload.get("workbook", {})
    header_labels = workbook.get("exercise_header_labels", ["Variation", "Exercise"])
    pattern = workbook.get("week_header_pattern", r"^week\s*\d+(?:\s*\([^)]*\))?$")
    if not isinstance(header_labels, list) or not all(isinstance(item, str) for item in header_labels):
        raise ConfigError("workbook.exercise_header_labels must be a list of strings")
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ConfigError(f"Invalid workbook.week_header_pattern: {exc}") from exc

    marker_payload = workbook.get("empty_day_marker")
    empty_day_marker: EmptyDayMarker | None = None
    if marker_payload is not None:
        if not isinstance(marker_payload, dict):
            raise ConfigError("workbook.empty_day_marker must be an object")
        marker_text = marker_payload.get("text")
        marker_fill = marker_payload.get("fill_color")
        if not isinstance(marker_text, str) or not marker_text.strip():
            raise ConfigError("workbook.empty_day_marker.text must be a non-empty string")
        if not isinstance(marker_fill, str) or not re.fullmatch(
            r"(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})", marker_fill
        ):
            raise ConfigError(
                "workbook.empty_day_marker.fill_color must be a 6- or 8-digit hex color"
            )
        normalized_fill = marker_fill.upper()
        if len(normalized_fill) == 6:
            normalized_fill = f"FF{normalized_fill}"
        empty_day_marker = EmptyDayMarker(
            text=marker_text.strip(),
            fill_color=normalized_fill,
        )

    program_config = _load_program_config(
        payload.get("program"), tuple(header_labels), pattern
    )

    raw_rules = payload.get("exercises")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ConfigError("exercises must be a non-empty list")

    rules: list[ExerciseRule] = []
    seen_source_aliases: dict[str, str] = {}
    for index, raw in enumerate(raw_rules, start=1):
        if not isinstance(raw, dict):
            raise ConfigError(f"Exercise rule {index} must be an object")
        canonical = raw.get("canonical")
        source_aliases = raw.get("source_aliases", [])
        coach_aliases = raw.get("coach_aliases", [])
        if not isinstance(canonical, str) or not canonical.strip():
            raise ConfigError(f"Exercise rule {index} needs a canonical name")
        if not source_aliases:
            source_aliases = [canonical]
        if not isinstance(source_aliases, list) or not all(isinstance(item, str) for item in source_aliases):
            raise ConfigError(f"Exercise rule {canonical!r} has invalid source_aliases")
        if not isinstance(coach_aliases, list) or not coach_aliases or not all(
            isinstance(item, str) for item in coach_aliases
        ):
            raise ConfigError(f"Exercise rule {canonical!r} needs coach_aliases")
        context_aliases = raw.get("coach_context_aliases", [])
        if not isinstance(context_aliases, list) or not all(
            isinstance(item, str) for item in context_aliases
        ):
            raise ConfigError(
                f"Exercise rule {canonical!r} coach_context_aliases must be a list of strings"
            )
        try:
            multiplier = Decimal(str(raw.get("weight_multiplier", 1)))
        except InvalidOperation as exc:
            raise ConfigError(f"Exercise rule {canonical!r} has an invalid weight_multiplier") from exc
        if multiplier <= 0:
            raise ConfigError(f"Exercise rule {canonical!r} weight_multiplier must be positive")
        suffix = raw.get("weight_suffix", "")
        if not isinstance(suffix, str):
            raise ConfigError(f"Exercise rule {canonical!r} weight_suffix must be a string")
        group = raw.get("superset_group")
        if group is not None and not isinstance(group, str):
            raise ConfigError(f"Exercise rule {canonical!r} superset_group must be a string")
        order = raw.get("superset_order", 0)
        if not isinstance(order, int):
            raise ConfigError(f"Exercise rule {canonical!r} superset_order must be an integer")
        program_excluded = raw.get("program_excluded", False)
        if not isinstance(program_excluded, bool):
            raise ConfigError(f"Exercise rule {canonical!r} program_excluded must be a boolean")
        exclusion_reason = raw.get("program_exclusion_reason")
        if exclusion_reason is not None and not isinstance(exclusion_reason, str):
            raise ConfigError(
                f"Exercise rule {canonical!r} program_exclusion_reason must be a string"
            )
        if program_excluded and not (
            isinstance(exclusion_reason, str) and exclusion_reason.strip()
        ):
            raise ConfigError(
                f"Exercise rule {canonical!r} needs program_exclusion_reason when excluded"
            )
        macrofactor_custom = raw.get("macrofactor_custom", False)
        macrofactor_available = raw.get("macrofactor_available", True)
        set_types = raw.get("program_set_types", [])
        if (not isinstance(set_types, list)
                or any(not isinstance(value, str) or value not in {"standard", "myo"}
                       for value in set_types)):
            raise ConfigError(f"Exercise rule {canonical!r} program_set_types must list standard/myo types")
        blank_reps = raw.get("program_blank_rep_targets", False)
        include_warmup = raw.get("program_include_warmup", False)
        if not isinstance(include_warmup, bool) or (include_warmup and program_excluded):
            raise ConfigError("program_include_warmup must be a boolean and cannot accompany exclusion")
        overrides = raw.get("program_base_overrides", {})
        if not isinstance(overrides, dict) or set(overrides) - {"sets", "reps"}:
            raise ConfigError("program_base_overrides supports only sets and reps")
        parsed_overrides = []
        for key, override in overrides.items():
            if (not isinstance(override, dict) or set(override) != {"expected", "value"}
                    or any(not isinstance(v, str) or not v.strip() for v in override.values())):
                raise ConfigError("Each program_base_overrides entry needs non-empty expected/value strings")
            parsed_overrides.append(BasePrescriptionOverride(
                key, override["expected"].strip(), override["value"].strip()))
        program_notes = raw.get("program_notes")
        if program_notes is not None and (not isinstance(program_notes, list)
                or any(not isinstance(v, str) or not v.strip() for v in program_notes)):
            raise ConfigError("program_notes must be null or a list of non-empty reviewed note strings")
        if program_notes is not None and not program_config.preserve_coach_notes:
            raise ConfigError("program_notes requires program.preserve_coach_notes")
        if not isinstance(blank_reps, bool):
            raise ConfigError(f"Exercise rule {canonical!r} program_blank_rep_targets must be a boolean")
        if set_types and group:
            raise ConfigError("Per-set type sequences combined with supersets are not yet supported")
        if blank_reps and not program_config.preserve_coach_notes:
            raise ConfigError("Blank rep overrides require program.preserve_coach_notes")
        if not isinstance(macrofactor_custom, bool):
            raise ConfigError(f"Exercise rule {canonical!r} macrofactor_custom must be a boolean")
        if not isinstance(macrofactor_available, bool):
            raise ConfigError(
                f"Exercise rule {canonical!r} macrofactor_available must be a boolean"
            )
        expansion = _load_program_expansion(raw.get("program_expansion"))
        if expansion is not None:
            if program_config.prescription_source != "base":
                raise ConfigError("program_expansion currently requires base prescriptions")
            if group or set_types or program_excluded or exclusion_reason is not None or include_warmup or "sets" in overrides:
                raise ConfigError("program_expansion cannot accompany supersets, set-type sequences, exclusion/inclusion exceptions or set overrides")
            if macrofactor_custom or not macrofactor_available:
                raise ConfigError("Set program_expansion availability flags on each child, not the parent")

        aliases = tuple(dict.fromkeys([canonical, *source_aliases]))
        for alias in aliases:
            key = normalize_name(alias)
            if key in seen_source_aliases:
                other = seen_source_aliases[key]
                raise ConfigError(f"Source alias {alias!r} is shared by {other!r} and {canonical!r}")
            seen_source_aliases[key] = canonical
        rules.append(
            ExerciseRule(
                canonical=canonical.strip(),
                source_aliases=aliases,
                coach_aliases=tuple(dict.fromkeys(item.strip() for item in coach_aliases)),
                coach_context_aliases=tuple(
                    dict.fromkeys(item.strip() for item in context_aliases if item.strip())
                ),
                weight_multiplier=multiplier,
                weight_suffix=suffix,
                superset_group=group.strip() if isinstance(group, str) and group.strip() else None,
                superset_order=order,
                program_excluded=program_excluded,
                program_exclusion_reason=(
                    exclusion_reason.strip()
                    if isinstance(exclusion_reason, str) and exclusion_reason.strip()
                    else None
                ),
                macrofactor_custom=macrofactor_custom,
                macrofactor_available=macrofactor_available,
                program_set_types=tuple(set_types),
                program_blank_rep_targets=blank_reps,
                program_include_warmup=include_warmup,
                program_base_overrides=tuple(parsed_overrides),
                program_notes=tuple(v.strip() for v in program_notes) if program_notes is not None else None,
                program_expansion=expansion,
            )
        )

    return BridgeConfig(
        exercise_header_labels=tuple(header_labels),
        week_header_pattern=pattern,
        rules=tuple(rules),
        empty_day_marker=empty_day_marker,
        program=program_config,
    )


def source_rule_index(config: BridgeConfig) -> dict[str, ExerciseRule]:
    return {
        normalize_name(alias): rule
        for rule in config.rules
        for alias in rule.source_aliases
    }
