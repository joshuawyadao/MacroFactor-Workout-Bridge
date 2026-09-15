"""Desktop presentation of one exercise across two independently dated blocks."""

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .comparison import METRICS, BlockComparison, ComparisonError, compare_blocks
from .desktop_theme import SERIES_COLORS
from .trend_chart import TrendChart
from .history import (
    BLOCK_TYPE_OPTIONS, WEEK_REASON_OPTIONS, WEEK_STATUS_OPTIONS,
    DashboardAnnotations, HistoryDashboard, decimal_text, option_label,
)


class ComparisonChart(TrendChart):
    """One shared scale including zero; missing points break the connecting line."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(135)
        self.comparison: BlockComparison | None = None
        self.metric_name = METRICS[0][1]
        self.setAccessibleName("Block comparison trend chart; values also appear in the table")

    def set_comparison(self, comparison: BlockComparison | None, metric: str) -> None:
        self.comparison, self.metric_name = comparison, metric
        self.update()

    def plot_values(self) -> tuple[tuple[Decimal | None, ...], ...]:
        if self.comparison is None:
            return ()
        return tuple(tuple(week.metric(self.metric_name) for week in series.weeks)
                     for series in (self.comparison.first, self.comparison.second))

class BlockComparisonPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._dashboard: HistoryDashboard | None = None
        self._annotations = DashboardAnnotations()
        self._selection = ("", "", "")
        outer = QVBoxLayout(self)
        controls = QGridLayout()
        self.exercise = QComboBox()
        self.first_block = QComboBox()
        self.second_block = QComboBox()
        self.metric_selector = QComboBox()
        for label, value in METRICS:
            self.metric_selector.addItem(label, value)
        for row, (label, combo) in enumerate((
            ("Exercise", self.exercise), ("A · cyan solid", self.first_block),
            ("B · orange dashed", self.second_block), ("Chart metric", self.metric_selector),
        )):
            # Two rows keep the table usable at the app's minimum height.
            caption = QLabel(label)
            caption.setBuddy(combo)
            combo.setAccessibleName(label)
            if row in (1, 2):
                caption.setObjectName("seriesA" if row == 1 else "seriesB")
            controls.addWidget(caption, row // 2, (row % 2) * 2)
            controls.addWidget(combo, row // 2, (row % 2) * 2 + 1)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.currentIndexChanged.connect(self._refresh)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)
        self.swap_button = QPushButton("Swap A/B")
        self.swap_button.setToolTip("Exchange the two blocks while keeping the exercise and metric.")
        self.swap_button.clicked.connect(self._swap_blocks)
        controls.addWidget(self.swap_button, 0, 4)
        self.notes_button = QPushButton("Block notes…")
        self.notes_button.setToolTip("Read the saved type and full notes for both selected blocks.")
        controls.addWidget(self.notes_button, 1, 4)
        outer.addLayout(controls)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.chart = ComparisonChart()
        outer.addWidget(self.chart)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Relative week", "Block", "Coach week / dates", "Days", "Sets", "Top lb",
            "Est. 1RM lb", "Logged data", "Saved week context",
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.horizontalHeaderItem(8).setToolTip("Full saved context is available by hovering over a cell; edit in Block context.")
        header = self.table.horizontalHeader()
        for column in range(8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        outer.addWidget(self.table, 1)
        self.notes_dialog = QDialog(self)
        self.notes_dialog.setWindowTitle("Saved block notes · A and B")
        self.notes_dialog.resize(580, 260)
        notes_layout = QVBoxLayout(self.notes_dialog)
        self.block_notes = QPlainTextEdit()
        self.block_notes.setReadOnly(True)
        self.block_notes.setAccessibleName("Saved block types and notes for A and B")
        notes_layout.addWidget(self.block_notes)
        close_notes = QPushButton("Close")
        close_notes.clicked.connect(self.notes_dialog.accept)
        notes_layout.addWidget(close_notes)
        self.notes_button.clicked.connect(self.notes_dialog.open)
        note = QLabel("X-axis: relative week. Gaps stay missing; no logs ≠ a confirmed skip. "
                      "Export coverage ≠ completeness.")
        note.setWordWrap(True)
        note.setObjectName("subtitle")
        outer.addWidget(note)
        self.set_history(None)

    def set_history(
        self, dashboard: HistoryDashboard | None,
        annotations: DashboardAnnotations | None = None,
    ) -> None:
        selectors = (self.exercise, self.first_block, self.second_block)
        current = tuple(combo.currentText() for combo in selectors)
        if any(current):
            self._selection = current
        self._dashboard = dashboard
        self._annotations = annotations or DashboardAnnotations()
        for combo in selectors:
            combo.blockSignals(True)
            combo.clear()
            combo.setEnabled(dashboard is not None)
        self.metric_selector.setEnabled(dashboard is not None)
        self.swap_button.setEnabled(dashboard is not None)
        if dashboard is not None:
            self.exercise.addItems(item.exercise for item in dashboard.exercises)
            names = [block.name for block in dashboard.blocks]
            self.first_block.addItems(names)
            self.second_block.addItems(names)
            eligible = [block.name for block in dashboard.blocks
                        if block.start_date and block.start_date.weekday() == 0
                        and block.name not in dashboard.overlapping_blocks]
            logged = [block.name for block in dashboard.blocks if block.mapped_set_count and block.name in eligible]
            preferred = logged + [name for name in eligible if name not in logged]
            defaults = (self.exercise.currentText(),
                        preferred[0] if preferred else self.first_block.currentText(),
                        preferred[1] if len(preferred) > 1 else names[-1] if names else "")
            for combo, saved, default in zip(selectors, self._selection, defaults):
                combo.setCurrentText(saved if combo.findText(saved) >= 0 else default)
        for combo in selectors:
            combo.blockSignals(False)
        self._refresh()

    def _swap_blocks(self) -> None:
        first, second = self.first_block.currentIndex(), self.second_block.currentIndex()
        self.first_block.blockSignals(True)
        self.second_block.blockSignals(True)
        self.first_block.setCurrentIndex(second)
        self.second_block.setCurrentIndex(first)
        self.first_block.blockSignals(False)
        self.second_block.blockSignals(False)
        self._refresh()

    def _refresh(self, *_args: object) -> None:
        self.table.setRowCount(0)
        self.block_notes.clear()
        self.notes_button.setEnabled(False)
        self.chart.set_comparison(None, str(self.metric_selector.currentData()))
        if self._dashboard is None:
            self.status.setText("Load history to compare two blocks.")
            return
        try:
            comparison = compare_blocks(self._dashboard, self._annotations, self.exercise.currentText(),
                                        self.first_block.currentText(), self.second_block.currentText())
        except ComparisonError as exc:
            self.status.setText(str(exc))
            return
        self.status.setText("A and B share one scale. Counts and weights are per exercise, not whole-block totals.")
        self.chart.set_comparison(comparison, str(self.metric_selector.currentData()))
        self.notes_button.setEnabled(True)
        pairs = comparison.paired_weeks()
        self.table.setRowCount(len(pairs) * 2)
        for index, pair in enumerate(pairs):
            for side, week in enumerate(pair):
                values = self._row_values(index, side, week)
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    if column == 1:
                        item.setForeground(QColor(SERIES_COLORS[side]))
                    self.table.setItem(index * 2 + side, column, item)
        self.table.resizeRowsToContents()
        self.block_notes.setPlainText("\n".join(
            f"{label}: {option_label(BLOCK_TYPE_OPTIONS, series.block.block_type)}"
            + (f" — {series.notes}" if series.notes else " — no saved block notes")
            for label, series in (("A", comparison.first), ("B", comparison.second))
        ))

    @staticmethod
    def _row_values(index, side, week) -> tuple[str, ...]:
        prefix = (str(index + 1), "A" if side == 0 else "B")
        if week is None:
            return (*prefix, "Outside this block", "—", "—", "—", "—", "Not applicable", "—")
        context = week.context
        text = "No saved week context"
        if context is not None:
            text = f"{option_label(WEEK_STATUS_OPTIONS, context.status)}; {option_label(WEEK_REASON_OPTIONS, context.reason)}"
            if context.affected_movements:
                text += "; movements: " + ", ".join(context.affected_movements)
            if context.notes:
                text += "; " + context.notes
        return (*prefix, f"{week.label}\n{week.start.isoformat()} – {week.end.isoformat()}",
                decimal_text(week.metric("training_days"), places=0),
                decimal_text(week.metric("set_count"), places=0),
                decimal_text(week.metric("top_weight")), decimal_text(week.metric("estimated_1rm")),
                week.coverage, text)
