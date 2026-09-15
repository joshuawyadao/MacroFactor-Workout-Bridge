"""Dashboard and exercise-first desktop navigation; no file access or writes."""

from datetime import timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .comparison import METRICS
from .explorer import LIFT_FAMILIES, best_estimate, default_exercise, exercise_names, exercise_timeline, week_location
from .history import DashboardAnnotations, WEEK_REASON_OPTIONS, WEEK_STATUS_OPTIONS, decimal_text, option_label
from .trend_chart import TrendChart


def _label(text=""):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setWordWrap(False)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _row(table, index, values):
    for column, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        item.setToolTip(str(value))
        table.setItem(index, column, item)


class ExerciseExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.dashboard = None
        self.annotations = DashboardAnnotations()
        self._saved_exercise = ""
        outer = QVBoxLayout(self)
        filters = QGridLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find an exercise…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search exercises")
        self.family = QComboBox()
        self.family.addItems(["All exercises", *LIFT_FAMILIES])
        self.exercise = QComboBox()
        self.period = QComboBox()
        for text, weeks in (("All history", 0), ("Last 4 weeks", 4), ("Last 12 weeks", 12), ("Last 24 weeks", 24)):
            self.period.addItem(text, weeks)
        self.metric_selector = QComboBox()
        for text, name in METRICS:
            self.metric_selector.addItem(text, name)
        for i, (caption, control) in enumerate((("Search", self.search), ("Group", self.family),
                                                ("Exercise", self.exercise), ("Time range", self.period))):
            label = _label(caption)
            label.setBuddy(control)
            control.setAccessibleName(caption)
            filters.addWidget(label, i // 2, (i % 2) * 2)
            filters.addWidget(control, i // 2, (i % 2) * 2 + 1)
        filters.setColumnStretch(1, 2)
        filters.setColumnStretch(3, 1)
        self.exercise.setMinimumContentsLength(15)
        self.exercise.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        outer.addLayout(filters)
        chart_heading = QHBoxLayout()
        self.summary = _label("Load an all-time export to explore exercise history.")
        chart_heading.addWidget(self.summary, 1)
        self.metric_selector.setAccessibleName("Chart metric")
        chart_heading.addWidget(self.metric_selector)
        outer.addLayout(chart_heading)
        self.chart = TrendChart()
        outer.addWidget(self.chart)
        self.table = _table(["Week of", "Block", "Coach week", "Days", "Sets", "Top lb", "Est. 1RM lb", "Coverage / saved context"])
        for column, width in ((1, 160), (2, 120)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        outer.addWidget(self.table, 1)
        self.note = _label("Ranges end in the export's latest week. No logged sets ≠ a confirmed skip. Variations stay separate.")
        self.note.setObjectName("subtitle")
        outer.addWidget(self.note)
        self.search.textChanged.connect(self._filter)
        self.family.currentIndexChanged.connect(self._filter)
        self.exercise.currentIndexChanged.connect(self._refresh)
        self.period.currentIndexChanged.connect(self._refresh)
        self.metric_selector.currentIndexChanged.connect(self._refresh)
        self.set_history(None)

    def set_history(self, dashboard, annotations=None):
        if self.exercise.currentText():
            self._saved_exercise = self.exercise.currentText()
        self.dashboard = dashboard
        self.annotations = annotations or DashboardAnnotations()
        for control in (self.search, self.family, self.exercise, self.period, self.metric_selector):
            control.setEnabled(dashboard is not None)
        self._filter()

    def _filter(self, *_args):
        current = self.exercise.currentText() or self._saved_exercise
        names = exercise_names(self.dashboard, self.family.currentText(), self.search.text()) if self.dashboard else ()
        self.exercise.blockSignals(True)
        self.exercise.clear()
        self.exercise.addItems(names)
        if current in names:
            self.exercise.setCurrentText(current)
        elif names:
            self.exercise.setCurrentText(default_exercise(self.dashboard, names))
        self.exercise.blockSignals(False)
        self._refresh()

    def open_exercise(self, exercise):
        self.search.clear()
        self.family.setCurrentIndex(0)
        self.period.setCurrentIndex(0)
        self.exercise.setCurrentText(exercise)
        self.exercise.setFocus()

    def _refresh(self, *_args):
        self.table.setRowCount(0)
        self.chart.set_series(())
        if self.dashboard is None:
            self.summary.setText("Load an all-time export to explore exercise history.")
            return
        exercise = self.exercise.currentText()
        if not exercise:
            self.summary.setText("No exercises match. Clear the search or choose All exercises.")
            return
        self._saved_exercise = exercise
        weeks = exercise_timeline(self.dashboard, exercise, int(self.period.currentData()))
        metric = self.metric_selector.currentData()
        self.chart.set_series((tuple(w.metric(metric) for w in weeks),),
                              tuple(w.start.strftime("%m/%d/%y") for w in weeks),
                              tuple(week_location(self.dashboard, w)[0] for w in weeks))
        sets = sum(w.trend.set_count for w in weeks if w.trend)
        self.summary.setText(f"{weeks[0].start:%b %d, %Y}–{self.dashboard.last_workout:%b %d, %Y} · {sets} logged sets · all blocks")
        self.table.setRowCount(len(weeks))
        for row, week in enumerate(reversed(weeks)):
            block_name, week_name = week_location(self.dashboard, week)
            block = self.annotations.blocks.get(block_name)
            context = block.weeks.get(week_name) if block else None
            description = "Logged sets" if week.trend else "No logged sets"
            if week.start < self.dashboard.first_workout or week.start + timedelta(days=6) > self.dashboard.last_workout:
                description += " (partial export date range)"
            if context:
                description += " · " + option_label(WEEK_STATUS_OPTIONS, context.status) + "; " + option_label(WEEK_REASON_OPTIONS, context.reason)
                if context.affected_movements:
                    description += "; " + ", ".join(context.affected_movements)
                if context.notes:
                    description += "; " + context.notes
            _row(self.table, row, (week.start.isoformat(), block_name, week_name,
                                  decimal_text(week.metric("training_days"), places=0), decimal_text(week.metric("set_count"), places=0),
                                  decimal_text(week.metric("top_weight")), decimal_text(week.metric("estimated_1rm")), description))
        self.table.scrollToTop()


class LiftCard(QFrame):
    changed = Signal()
    explore = Signal(str)

    def __init__(self, family):
        super().__init__()
        self.family = family
        self.dashboard = None
        self._saved = ""
        self.setObjectName("summaryCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)
        outer.addWidget(_label(family))
        self.exercise = QComboBox()
        self.exercise.setAccessibleName(f"{family} variation")
        self.exercise.setMinimumContentsLength(12)
        self.exercise.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        outer.addWidget(self.exercise)
        self.value = _label("—")
        self.value.setObjectName("summaryValue")
        outer.addWidget(self.value)
        self.detail = _label("Load history to see this lift.")
        self.detail.setObjectName("subtitle")
        outer.addWidget(self.detail)
        self.chart = TrendChart()
        self.chart.setMinimumHeight(95)
        self.chart.setMaximumHeight(95)
        self.chart.max_labels = 3
        outer.addWidget(self.chart)
        self.button = QPushButton(f"Explore {family.lower()} →")
        self.button.clicked.connect(lambda: self.explore.emit(self.exercise.currentText()))
        outer.addWidget(self.button)
        self.exercise.currentIndexChanged.connect(self._refresh)

    def set_history(self, dashboard):
        if self.exercise.currentText():
            self._saved = self.exercise.currentText()
        self.dashboard = dashboard
        names = exercise_names(dashboard, self.family) if dashboard else ()
        self.exercise.blockSignals(True)
        self.exercise.clear()
        self.exercise.addItems(names)
        if names:
            self.exercise.setCurrentText(self._saved if self._saved in names else default_exercise(dashboard, names))
        self.exercise.blockSignals(False)
        self.exercise.setEnabled(bool(names))
        self.button.setEnabled(bool(names))
        self._refresh()

    def _refresh(self, *_args):
        self.chart.set_series(())
        self.value.setText("—")
        self.detail.setText("No supported variation logged. Other movements are in Explore exercise." if self.dashboard else "Load history to see this lift.")
        if self.dashboard and self.exercise.currentText():
            name = self.exercise.currentText()
            self._saved = name
            weeks = exercise_timeline(self.dashboard, name)
            logged = [w for w in weeks if w.trend]
            latest = logged[-1]
            self.value.setText(f"{decimal_text(latest.metric('estimated_1rm'))} lb")
            self.detail.setText(f"Est. 1RM · last logged week {latest.start:%b %d, %Y}")
            self.chart.set_series((tuple(w.metric("estimated_1rm") for w in weeks),), tuple(w.start.strftime("%m/%d/%y") for w in weeks))
        self.changed.emit()


class HistoryHome(QScrollArea):
    explore = Signal(str)

    def __init__(self):
        super().__init__()
        self.dashboard = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 8, 0, 0)
        self.coverage = _label("Start with an all-time export above. Then explore your main lifts or any exercise—no block selection needed.")
        outer.addWidget(self.coverage)
        cards = QHBoxLayout()
        self.cards = [LiftCard(family) for family in LIFT_FAMILIES]
        for card in self.cards:
            cards.addWidget(card, 1)
            card.changed.connect(self._refresh_blocks)
            card.explore.connect(self.explore.emit)
        outer.addLayout(cards)
        self.legend = _label("Across blocks · best estimated 1RM (lb) for each selected variation. Blanks mean no estimate, not zero.")
        self.legend.setObjectName("subtitle")
        outer.addWidget(self.legend)
        self.blocks = _table(["Start", "Coach block", "Squat", "Bench", "Deadlift", "Logged days", "Logged sets"])
        self.blocks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.blocks.setColumnWidth(1, 245)
        self.blocks.verticalHeader().setDefaultSectionSize(27)
        self.blocks.setMinimumHeight(140)
        outer.addWidget(self.blocks, 1)
        self.setWidget(page)
        self.set_history(None)

    def set_history(self, dashboard):
        self.dashboard = dashboard
        for card in self.cards:
            card.set_history(dashboard)
        if dashboard:
            self.coverage.setText(f"{dashboard.first_workout:%b %d, %Y}–{dashboard.last_workout:%b %d, %Y} · "
                                  f"{dashboard.set_count:,} sets · {dashboard.training_day_count} training days. "
                                  + ("Short export: load all-time history for earlier blocks." if (dashboard.last_workout - dashboard.first_workout).days < 28
                                     else "Choose a variation, or explore any exercise across all blocks."))
        else:
            self.coverage.setText("Start with an all-time export above. Then explore your main lifts or any exercise—no block selection needed.")
        self._refresh_blocks()

    def _refresh_blocks(self):
        self.blocks.setRowCount(0)
        if not self.dashboard:
            return
        blocks = sorted(self.dashboard.blocks, key=lambda b: (b.start_date is None, str(b.start_date), b.position))
        self.blocks.setRowCount(len(blocks))
        names = [card.exercise.currentText() for card in self.cards]
        for column, name in enumerate(names, start=2):
            self.blocks.horizontalHeaderItem(column).setToolTip(name or "No variation selected")
        for row, block in enumerate(blocks):
            _row(self.blocks, row, (block.start_date or "Not dated", block.name,
                                    *(decimal_text(best_estimate(self.dashboard, name, block.name)) for name in names),
                                    block.mapped_training_days if block.start_date else "—",
                                    block.mapped_set_count if block.start_date else "—"))
