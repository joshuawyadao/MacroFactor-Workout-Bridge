"""Dashboard and exercise-first desktop navigation; no file access or writes."""

from datetime import timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .comparison import METRICS
from .explorer import LIFT_FAMILIES, default_exercise, exercise_names, exercise_timeline, week_location
from .history import BLOCK_TYPE_OPTIONS, DashboardAnnotations, WEEK_REASON_OPTIONS, WEEK_STATUS_OPTIONS, decimal_text, option_label
from .progress import block_reports, calendar_weeks, exercise_workload, full_weeks, week_context
from .trend_chart import TrendChart

LIFT_COLORS = {"Squat": "#72d6ef", "Bench": "#c5a4f5", "Deadlift": "#ffcc66"}


def period_selector():
    combo = QComboBox()
    for text, weeks in (("All history", 0), ("Last 4 weeks", 4), ("Last 12 weeks", 12), ("Last 24 weeks", 24)):
        combo.addItem(text, weeks)
    combo.setAccessibleName("Time range")
    return combo


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
        self.recent_weeks = 0
        self.setObjectName("summaryCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)
        heading = _label(family)
        heading.setStyleSheet(f"color: {LIFT_COLORS[family]}; font-size: 18px; font-weight: 600;")
        outer.addWidget(heading)
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
        self.chart.series_colors = (LIFT_COLORS[family],)
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
            weeks = exercise_timeline(self.dashboard, name, self.recent_weeks)
            logged = [w for w in weeks if w.trend]
            if logged:
                latest = logged[-1]
                self.value.setText(f"{decimal_text(latest.metric('estimated_1rm'))} lb")
                self.detail.setText(f"Est. 1RM · last logged week {latest.start:%b %d, %Y}")
            else:
                self.detail.setText("No logged sets in this range.")
            self.chart.set_series((tuple(w.metric("estimated_1rm") for w in weeks),), tuple(w.start.strftime("%m/%d/%y") for w in weeks))
        self.changed.emit()


class HistoryHome(QScrollArea):
    explore = Signal(str)
    focus_block = Signal(str)
    range_changed = Signal(int)
    variations_changed = Signal()

    def __init__(self):
        super().__init__()
        self.dashboard = None
        self.annotations = DashboardAnnotations()
        self.report_cards = []
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 8, 0, 0)
        heading = QHBoxLayout()
        title = _label("Your progress, across blocks")
        title.setObjectName("pageTitle")
        heading.addWidget(title, 1)
        self.period = period_selector()
        heading.addWidget(self.period)
        outer.addLayout(heading)
        self.coverage = _label("Start with an all-time export above. Then explore your main lifts or any exercise—no block selection needed.")
        outer.addWidget(self.coverage)
        cards = QHBoxLayout()
        self.cards = [LiftCard(family) for family in LIFT_FAMILIES]
        for card in self.cards:
            cards.addWidget(card, 1)
            card.changed.connect(self._refresh_blocks)
            card.changed.connect(self.variations_changed.emit)
            card.explore.connect(self.explore.emit)
        outer.addLayout(cards)
        title = _label("Across your blocks · scroll to browse →")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        self.report_scroll = QScrollArea()
        self.report_scroll.setWidgetResizable(True)
        self.report_scroll.setFixedHeight(225)
        self.report_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.report_page = QWidget()
        self.report_layout = QHBoxLayout(self.report_page)
        self.report_layout.setContentsMargins(0, 0, 0, 0)
        self.report_scroll.setWidget(self.report_page)
        outer.addWidget(self.report_scroll)
        self.averages_note = _label("Weekly averages use full weeks within the selected export range; partial weeks are excluded. No logs ≠ a confirmed skip.")
        self.averages_note.setObjectName("subtitle")
        outer.addWidget(self.averages_note)
        lower = QHBoxLayout()
        self.workload_frame = QFrame()
        self.workload_frame.setObjectName("summaryCard")
        self.workload_layout = QVBoxLayout(self.workload_frame)
        lower.addWidget(self.workload_frame, 3)
        context_frame = QFrame()
        context_frame.setObjectName("summaryCard")
        context_layout = QVBoxLayout(context_frame)
        context_title = _label("Context to keep in view")
        context_title.setObjectName("sectionTitle")
        context_layout.addWidget(context_title)
        self.context = _label()
        context_layout.addWidget(self.context)
        context_layout.addStretch()
        context_layout.addWidget(_label("Saved notes only. Lower loads do not automatically mean fatigue or lost strength."))
        lower.addWidget(context_frame, 2)
        outer.addLayout(lower)
        self.values_button = QPushButton("Show exact block values")
        self.values_button.setCheckable(True)
        outer.addWidget(self.values_button)
        self.legend = _label("Across blocks · best estimated 1RM (lb) for each selected variation. Blanks mean no estimate, not zero.")
        self.legend.setObjectName("subtitle")
        outer.addWidget(self.legend)
        self.blocks = _table(["Start", "Coach block", "Squat", "Bench", "Deadlift", "Logged days", "Logged sets"])
        self.blocks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.blocks.setColumnWidth(1, 245)
        self.blocks.verticalHeader().setDefaultSectionSize(27)
        self.blocks.setMinimumHeight(140)
        outer.addWidget(self.blocks, 1)
        self.blocks.setVisible(False)
        self.legend.setVisible(False)
        self.values_button.toggled.connect(self.blocks.setVisible)
        self.values_button.toggled.connect(self.legend.setVisible)
        self.period.currentIndexChanged.connect(self._range_changed)
        self.setWidget(page)
        self.set_history(None)

    def set_history(self, dashboard, annotations=None):
        self.dashboard = dashboard
        self.annotations = annotations or DashboardAnnotations()
        self.period.setEnabled(dashboard is not None)
        for card in self.cards:
            card.recent_weeks = int(self.period.currentData())
            card.set_history(dashboard)
        if dashboard:
            self.coverage.setText(f"{dashboard.first_workout:%b %d, %Y}–{dashboard.last_workout:%b %d, %Y} · "
                                  f"{dashboard.set_count:,} sets · {dashboard.training_day_count} training days. "
                                  + ("Short export: load all-time history for earlier blocks." if (dashboard.last_workout - dashboard.first_workout).days < 28
                                     else "Choose a variation, or explore any exercise across all blocks."))
        else:
            self.coverage.setText("Start with an all-time export above. Then explore your main lifts or any exercise—no block selection needed.")
        self._refresh_blocks()

    def _range_changed(self):
        for card in self.cards:
            card.recent_weeks = int(self.period.currentData())
            card._refresh()
        self._refresh_blocks()
        self.range_changed.emit(int(self.period.currentData()))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def _refresh_blocks(self):
        self.blocks.setRowCount(0)
        self._clear_layout(self.report_layout)
        self._clear_layout(self.workload_layout)
        self.report_cards = []
        self.context.setText("Load history to see saved block and week context.")
        if not self.dashboard:
            return
        reports = block_reports(self.dashboard, int(self.period.currentData()))
        self.blocks.setRowCount(len(reports))
        names = [card.exercise.currentText() for card in self.cards]
        for column, name in enumerate(names, start=2):
            self.blocks.horizontalHeaderItem(column).setToolTip(name or "No variation selected")
        for row, report in enumerate(reports):
            block = report.block
            frame = QFrame()
            frame.setObjectName("summaryCard")
            frame.setFixedWidth(265)
            layout = QVBoxLayout(frame)
            title = _label(block.name)
            title.setObjectName("sectionTitle")
            title.setMaximumHeight(48)
            title.setToolTip(block.name)
            layout.addWidget(title)
            layout.addWidget(_label(f"{block.start_date or 'Not dated'} · {len(block.week_labels)} weeks"))
            layout.addWidget(_label(option_label(BLOCK_TYPE_OPTIONS, block.block_type)))
            coverage = _label(report.coverage)
            coverage.setObjectName("subtitle")
            layout.addWidget(coverage)
            layout.addWidget(_label(f"{decimal_text(report.sets_per_week)} sets / week   ·   {decimal_text(report.days_per_week)} days / week"))
            layout.addWidget(_label(f"{report.complete_week_count} full weeks used for averages"))
            layout.addStretch()
            button = QPushButton("Analyze block →")
            button.setEnabled(bool(report.weeks) and not report.issue)
            button.clicked.connect(lambda checked=False, name=block.name: self.focus_block.emit(name))
            layout.addWidget(button)
            self.report_layout.addWidget(frame)
            self.report_cards.append(frame)
            _row(self.blocks, row, (block.start_date or "Not dated", block.name,
                                    *(decimal_text(report.best_estimate(self.dashboard, name)) for name in names),
                                    decimal_text(report.days_per_week), decimal_text(report.sets_per_week)))
        self.blocks.setHorizontalHeaderLabels(["Start", "Coach block", "Squat", "Bench", "Deadlift", "Days / week", "Sets / week"])
        self.report_layout.addStretch()
        weeks = calendar_weeks(self.dashboard, int(self.period.currentData()))
        title = _label("Training focus · sets per week")
        title.setObjectName("sectionTitle")
        self.workload_layout.addWidget(title)
        self.workload_layout.addWidget(_label(f"By exercise · {len(full_weeks(self.dashboard, weeks))} full weeks · not muscle growth"))
        workload = exercise_workload(self.dashboard, weeks)[:5]
        for name, value in workload:
            button = QPushButton(f"{name}   {decimal_text(value)} →")
            button.setToolTip(name)
            button.clicked.connect(lambda checked=False, exercise=name: self.explore.emit(exercise))
            self.workload_layout.addWidget(button)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(value / workload[0][1] * 1000))
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            self.workload_layout.addWidget(bar)
        if not workload:
            self.workload_layout.addWidget(_label("No full weeks with logged sets in this range."))
        notes = [(week, week_context(self.dashboard, self.annotations, week)) for week in reversed(weeks)]
        notes = [(week, note) for week, note in notes if note]
        self.context.setText("\n\n".join(f"{week:%b %d} · {note[:170]}{'…' if len(note) > 170 else ''}" for week, note in notes[:3])
                             or "No saved week context in this range.")
        self.context.setToolTip("\n\n".join(f"{week.isoformat()} · {note}" for week, note in notes))
