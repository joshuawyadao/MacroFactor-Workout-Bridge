"""Conservative presentation cleanup for exported MacroFactor exercise notes.

The source workbook and parser provenance remain verbatim.  This module only
formats the separate note strings that are written to a generated program.
"""
from __future__ import annotations

import re
from collections.abc import Iterable


_SPELLING_CORRECTIONS = {
    "convenitonal": "conventional",
    "dumbell": "dumbbell",
    "gased": "gassed",
    "movmement": "movement",
    "parrallell": "parallel",
    "pressdiwn": "pressdown",
    "thorugh": "through",
    "weighte": "weighted",
    "zottiman": "zottman",
}

_ABBREVIATIONS = (
    (re.compile(r"\bb\.?\s*s\.?\s*s\.?(?=\s|\(|$)", re.IGNORECASE), "BSS"),
    (re.compile(r"\bamrap\b", re.IGNORECASE), "AMRAP"),
    (re.compile(r"\bghd\b", re.IGNORECASE), "GHD"),
    (re.compile(r"\brir\b", re.IGNORECASE), "RIR"),
    (re.compile(r"\brpe\b", re.IGNORECASE), "RPE"),
    (re.compile(r"\brom\b", re.IGNORECASE), "ROM"),
)

_PHRASE_CORRECTIONS = (
    (re.compile(r"\bchest supported\b", re.IGNORECASE), "chest-supported"),
    (re.compile(r"\bpec dec\b", re.IGNORECASE), "pec deck"),
    (re.compile(r"\bpull down\b", re.IGNORECASE), "pulldown"),
    (re.compile(r"\bsit up\b", re.IGNORECASE), "sit-up"),
    (re.compile(r"\btricep\b", re.IGNORECASE), "triceps"),
)


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement.capitalize()
    return replacement


def _correct_known_words(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        replacement = _SPELLING_CORRECTIONS[match.group(0).lower()]
        return _match_case(match.group(0), replacement)

    pattern = r"\b(?:" + "|".join(map(re.escape, _SPELLING_CORRECTIONS)) + r")\b"
    return re.sub(pattern, replace, text, flags=re.IGNORECASE)


def clean_program_note(text: str) -> str:
    """Apply only reviewed, non-semantic spelling and punctuation repairs."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or re.fullmatch(r"https?://\S+", cleaned, re.IGNORECASE):
        return cleaned
    cleaned = _correct_known_words(cleaned)
    for pattern, replacement in _ABBREVIATIONS:
        cleaned = pattern.sub(replacement, cleaned)
    for pattern, replacement in _PHRASE_CORRECTIONS:
        cleaned = pattern.sub(
            lambda match: _match_case(match.group(0), replacement), cleaned
        )
    cleaned = re.sub(r"\b(\d+(?:-\d+)?)\s+degree\b", r"\1 degrees", cleaned,
                     flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(\d+)\s+count negative\b", r"\1-count negative", cleaned,
                     flags=re.IGNORECASE)
    first_letter = re.search(r"[A-Za-z]", cleaned)
    if first_letter:
        index = first_letter.start()
        cleaned = cleaned[:index] + cleaned[index].upper() + cleaned[index + 1:]
    cleaned = re.sub(
        r"([.!?]\s+|:\s+)([a-z])",
        lambda match: match.group(1) + match.group(2).upper(),
        cleaned,
    )
    if cleaned.count("(") > cleaned.count(")"):
        cleaned += ")" * (cleaned.count("(") - cleaned.count(")"))
    if cleaned and re.search(r"[A-Za-z0-9)]$", cleaned):
        cleaned += "."
    return cleaned


def prepare_program_notes(notes: Iterable[str], policy: str) -> tuple[str, ...]:
    """Return stable, de-duplicated presentation notes under the chosen policy."""
    if policy == "verbatim":
        return tuple(dict.fromkeys(notes))
    if policy != "conservative":
        raise ValueError(f"Unsupported program note-text policy: {policy}")
    return tuple(dict.fromkeys(
        cleaned for note in notes if (cleaned := clean_program_note(note))
    ))
