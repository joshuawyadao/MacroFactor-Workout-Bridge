from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import BridgeConfig, ExerciseRule


class ConfigError(ValueError):
    """Raised when bridge configuration is invalid."""


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


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
                weight_multiplier=multiplier,
                weight_suffix=suffix,
                superset_group=group.strip() if isinstance(group, str) and group.strip() else None,
                superset_order=order,
            )
        )

    return BridgeConfig(
        exercise_header_labels=tuple(header_labels),
        week_header_pattern=pattern,
        rules=tuple(rules),
    )


def source_rule_index(config: BridgeConfig) -> dict[str, ExerciseRule]:
    return {
        normalize_name(alias): rule
        for rule in config.rules
        for alias in rule.source_aliases
    }
