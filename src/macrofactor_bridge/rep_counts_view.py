"""Explicit per-set confirmation of full and partial repetitions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class RepCountsDialog(QDialog):
    """Collect confirmations without interpreting MacroFactor's combined Reps value."""

    MAX_EDITABLE_REPS = 2_147_483_647

    def __init__(self, sets: list[dict], parent: QWidget | None = None) -> None:
        for entry in sets:
            for key in ("full_reps", "partial_reps"):
                count = entry.get(key)
                if count is not None and (count < 0 or count > self.MAX_EDITABLE_REPS):
                    raise ValueError(
                        f"Export row {entry.get('source_row')}: saved rep count exceeds "
                        "the editor's numeric range. The saved counts were not changed."
                    )
        super().__init__(parent)
        self.setWindowTitle("Review full and partial reps")
        self.resize(780, 560)
        self.rows: list[tuple[dict, QCheckBox, QSpinBox, QSpinBox]] = []
        outer = QVBoxLayout(self)
        intro = QLabel(
            "MacroFactor exports one combined rep value. Enter the actual full and "
            "partial counts for sets you know, then check Confirm. Unconfirmed "
            "fractional sets stay in Review needed."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        rows_layout = QVBoxLayout(body)
        positions: dict[tuple[object, object, object], int] = {}
        for entry in sets:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(4, 4, 4, 4)
            exported = entry.get("exported_reps")
            group = (entry.get("workout_date"), entry.get("workout"), entry.get("exercise"))
            positions[group] = positions.get(group, 0) + 1
            title = QLabel(
                f"{entry.get('workout_date', '')} · {entry.get('workout', '')} · "
                f"{entry.get('exercise', '')} · set {positions[group]} "
                f"(export row {entry.get('source_row', '')})\n"
                f"{entry.get('set_type', '')} · "
                f"{str(entry['weight']) + ' lb' if entry.get('weight') is not None else 'no weight'} · "
                f"exported reps: {exported if exported is not None else '—'}"
            )
            title.setWordWrap(True)
            layout.addWidget(title, 1)
            confirmed = QCheckBox("Confirm")
            confirmed.setObjectName(f"confirm_{entry.get('source_row')}")
            has_counts = entry.get("full_reps") is not None and entry.get("partial_reps") is not None
            confirmed.setChecked(has_counts)
            layout.addWidget(confirmed)
            full = QSpinBox()
            full.setRange(0, self.MAX_EDITABLE_REPS)
            full.setValue(entry["full_reps"] if has_counts else 0)
            full.setPrefix("Full: ")
            full.setObjectName(f"full_{entry.get('source_row')}")
            layout.addWidget(full)
            partial = QSpinBox()
            partial.setRange(0, self.MAX_EDITABLE_REPS)
            partial.setValue(entry["partial_reps"] if has_counts else 0)
            partial.setPrefix("Partial: ")
            partial.setObjectName(f"partial_{entry.get('source_row')}")
            layout.addWidget(partial)
            if _fractional(exported) and not has_counts:
                row.setStyleSheet("background-color: #493d26; border-radius: 4px;")
                title.setToolTip("Confirm the actual counts to include this fractional set.")
            self.rows.append((entry, confirmed, full, partial))
            rows_layout.addWidget(row)
        rows_layout.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self.validation_error = QLabel("")
        self.validation_error.setObjectName("repCountsValidationError")
        self.validation_error.setWordWrap(True)
        self.validation_error.setStyleSheet("color: #ffb4a9;")
        outer.addWidget(self.validation_error)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        save = QPushButton("Save counts and preview")
        save.setObjectName("saveCountsButton")
        save.clicked.connect(self._validate_and_accept)
        actions.addWidget(save)
        outer.addLayout(actions)

    def _validate_and_accept(self) -> None:
        try:
            self.entries()
        except ValueError as exc:
            self.validation_error.setText(str(exc))
            return
        self.validation_error.clear()
        self.accept()

    def entries(self) -> list[dict]:
        results = []
        for source, confirmed, full, partial in self.rows:
            entry = {
                key: source[key]
                for key in (
                    "source_row", "workout_date", "workout", "exercise", "set_type",
                    "weight", "exported_reps",
                )
            }
            if confirmed.isChecked():
                if full.value() + partial.value() == 0:
                    raise ValueError(
                        f"Export row {source['source_row']}: enter at least one full or partial rep."
                    )
                entry.update(full_reps=full.value(), partial_reps=partial.value())
            else:
                entry.update(full_reps=None, partial_reps=None)
            results.append(entry)
        return results


def _fractional(value: object) -> bool:
    if value is None:
        return False
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return number != number.to_integral_value()
