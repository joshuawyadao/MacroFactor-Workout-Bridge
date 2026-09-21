"""Aligned, exact-variation timeline with read-only source-set drill-down."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .explorer import ExplorerWeek, LIFT_FAMILIES, default_exercise, exercise_names, week_location
from .explorer_view import LIFT_COLORS, _label, _row, _table, period_selector
from .history import DashboardAnnotations, decimal_text
from .progress import block_reports, calendar_weeks, full_weeks, sets_for_week, week_context, weekly_workload
from .trend_chart import TrendChart


class TrainingTimeline(QWidget):
    back = Signal()
    range_changed = Signal(int)
    variation_changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.dashboard = None
        self.annotations = DashboardAnnotations()
        self.weeks = ()
        self.selectors = {}
        self.charts = {}
        self._saved = {}
        self.details_dialog = None
        outer = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = _label("See the whole training story")
        title.setObjectName("pageTitle")
        heading.addWidget(title, 1)
        back = QPushButton("← Overview")
        back.clicked.connect(self.back.emit)
        heading.addWidget(back)
        outer.addLayout(heading)
        controls = QHBoxLayout()
        self.period = period_selector()
        controls.addWidget(self.period)
        self.block = QComboBox()
        self.block.setAccessibleName("Focus block")
        self.block.setMinimumContentsLength(18)
        self.block.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        controls.addWidget(self.block, 1)
        self.show_context = QCheckBox("Show saved context")
        self.show_context.setChecked(True)
        controls.addWidget(self.show_context)
        outer.addLayout(controls)
        self.summary = _label("Load history to see aligned lift trends.")
        self.summary.setObjectName("subtitle")
        outer.addWidget(self.summary)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        columns = QHBoxLayout(page)
        columns.setContentsMargins(0, 0, 0, 0)
        plots = QVBoxLayout()
        for family in LIFT_FAMILIES:
            frame = QFrame()
            frame.setObjectName("summaryCard")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(8, 4, 8, 4)
            heading = QHBoxLayout()
            caption = _label(f"{family} · est. 1RM (lb)")
            caption.setStyleSheet(f"color: {LIFT_COLORS[family]}; font-weight: 600;")
            heading.addWidget(caption)
            selector = QComboBox()
            selector.setAccessibleName(f"Timeline {family} variation")
            selector.setMinimumContentsLength(12)
            selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            heading.addWidget(selector, 1)
            layout.addLayout(heading)
            chart = TrendChart()
            chart.setMinimumHeight(115)
            chart.setMaximumHeight(115)
            chart.series_colors = (LIFT_COLORS[family],)
            chart.setAccessibleName(f"{family} weekly estimated 1RM; use week controls for exact sets")
            layout.addWidget(chart)
            plots.addWidget(frame)
            self.selectors[family] = selector
            self.charts[family] = chart
            selector.currentTextChanged.connect(lambda name, f=family: self._variation(f, name))
            chart.point_clicked.connect(lambda index, f=family: self._point(index, f))
        self.workload = TrendChart()
        self.workload.bar_mode = True
        self.workload.series_colors = ("#abb1bc",)
        self.workload.setMinimumHeight(110)
        self.workload.setMaximumHeight(110)
        plots.addWidget(_label("Training workload · all exercises · logged sets / week"))
        plots.addWidget(self.workload)
        self.workload.point_clicked.connect(lambda index: self._point(index, ""))
        columns.addLayout(plots, 3)
        side = QFrame()
        side.setObjectName("summaryCard")
        side.setMaximumWidth(230)
        side.setMinimumWidth(180)
        sidebar = QVBoxLayout(side)
        title = _label("Inspect a week")
        title.setObjectName("sectionTitle")
        sidebar.addWidget(title)
        self.week_selector = QComboBox()
        self.week_selector.setAccessibleName("Week to inspect")
        sidebar.addWidget(self.week_selector)
        self.context = _label()
        sidebar.addWidget(self.context)
        self.detail_exercise = QComboBox()
        self.detail_exercise.setAccessibleName("Exercise for set details")
        self.detail_exercise.setMinimumContentsLength(12)
        self.detail_exercise.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        sidebar.addWidget(self.detail_exercise)
        self.details_button = QPushButton("View logged sets →")
        self.details_button.clicked.connect(self._open_details)
        sidebar.addWidget(self.details_button)
        sidebar.addStretch()
        sidebar.addWidget(_label("Exact variations stay separate. Dotted markers show saved context, not inferred causes. Gaps are not confirmed skips."))
        columns.addWidget(side)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        self.period.currentIndexChanged.connect(self._range)
        self.block.currentIndexChanged.connect(self._refresh)
        self.show_context.toggled.connect(self._refresh)
        self.week_selector.currentIndexChanged.connect(self._week_changed)
        self.set_history(None)

    def set_history(self, dashboard, annotations=None):
        if self.details_dialog:
            self.details_dialog.close()
            self.details_dialog = None
        self.dashboard = dashboard
        self.annotations = annotations or DashboardAnnotations()
        for family, selector in self.selectors.items():
            saved = selector.currentText() or self._saved.get(family, "")
            if saved:
                self._saved[family] = saved
            names = exercise_names(dashboard, family) if dashboard else ()
            selector.blockSignals(True)
            selector.clear()
            selector.addItems(names)
            if names:
                selector.setCurrentText(saved if saved in names else default_exercise(dashboard, names))
            selector.blockSignals(False)
            selector.setEnabled(bool(names))
        for control in (self.period, self.block, self.show_context):
            control.setEnabled(dashboard is not None)
        self._populate_blocks()
        self._refresh()

    def _populate_blocks(self):
        saved = self.block.currentData()
        self.block.blockSignals(True)
        self.block.clear()
        self.block.addItem("All blocks", "")
        if self.dashboard:
            for report in block_reports(self.dashboard, int(self.period.currentData())):
                if report.weeks and not report.issue:
                    self.block.addItem(report.block.name, report.block.name)
        index = self.block.findData(saved)
        self.block.setCurrentIndex(max(0, index))
        self.block.blockSignals(False)

    def _range(self):
        self._populate_blocks()
        self._refresh()
        self.range_changed.emit(int(self.period.currentData()))

    def _variation(self, family, name):
        if name:
            self._saved[family] = name
            self.variation_changed.emit(family, name)
        self._refresh()

    def open_exercise(self, exercise):
        self.block.setCurrentIndex(0)
        for family, names in LIFT_FAMILIES.items():
            if exercise in names:
                self.selectors[family].setCurrentText(exercise)
                self.detail_exercise.setCurrentText(exercise)
                self.selectors[family].setFocus()
                self.scroll.ensureWidgetVisible(self.charts[family])
                break

    def open_block(self, name):
        index = self.block.findData(name)
        if index >= 0:
            self.block.setCurrentIndex(index)
            self.scroll.verticalScrollBar().setValue(0)

    def _refresh(self):
        old_week = self.week_selector.currentData()
        self.week_selector.blockSignals(True)
        self.week_selector.clear()
        self.weeks = ()
        for chart in (*self.charts.values(), self.workload):
            chart.set_series(())
        if self.dashboard:
            self.weeks = calendar_weeks(self.dashboard, int(self.period.currentData()))
            focused = self.block.currentData()
            if focused:
                report = next((r for r in block_reports(self.dashboard, int(self.period.currentData())) if r.block.name == focused), None)
                self.weeks = report.weeks if report else ()
            labels = tuple(w.strftime("%m/%d/%y") for w in self.weeks)
            bands = tuple(week_location(self.dashboard, ExplorerWeek(w, None))[0] for w in self.weeks)
            notes = tuple(week_context(self.dashboard, self.annotations, w) for w in self.weeks) if self.show_context.isChecked() else ()
            for family, chart in self.charts.items():
                trends = {t.week_start: t for t in self.dashboard.trends_for(self.selectors[family].currentText())}
                values = tuple(trends[w].estimated_1rm if w in trends else None for w in self.weeks)
                chart.set_series((values,), labels, bands, notes)
            self.workload.set_series((weekly_workload(self.dashboard, self.weeks),), labels, bands, notes)
            for start in reversed(self.weeks):
                self.week_selector.addItem(start.isoformat(), start)
            self.summary.setText(f"{len(self.weeks)} Monday–Sunday weeks · {focused or 'all blocks'} · Click a chart week or use the week selector for exact sets.")
        else:
            self.summary.setText("Load history to see aligned lift trends.")
        previous = self._week_index(old_week)
        self.week_selector.setCurrentIndex(max(0, previous) if self.weeks else -1)
        self.week_selector.blockSignals(False)
        self.details_button.setEnabled(bool(self.weeks))
        self.week_selector.setEnabled(bool(self.weeks))
        self.detail_exercise.setEnabled(bool(self.weeks))
        self._week_changed()

    def _week_changed(self):
        selected = self.detail_exercise.currentText()
        self.detail_exercise.clear()
        self.detail_exercise.addItem("All exercises")
        start = self.week_selector.currentData()
        if self.dashboard and start:
            records = sets_for_week(self.dashboard, start)
            self.detail_exercise.addItems(sorted({r.exercise for r in records}))
            if self.detail_exercise.findText(selected) >= 0:
                self.detail_exercise.setCurrentText(selected)
            block, week = week_location(self.dashboard, ExplorerWeek(start, None))
            notes = week_context(self.dashboard, self.annotations, start) if self.show_context.isChecked() else "Context hidden"
            boundary = "Full calendar week within export date bounds" if start in full_weeks(self.dashboard, self.weeks) else "Partial export boundary week"
            text = f"{block}\n{week}\n\n{len(records)} logged sets\n{boundary}\n\n{notes or 'No saved week context.'}"
            self.context.setText(text[:350] + ("…" if len(text) > 350 else ""))
            self.context.setToolTip(text)
        else:
            self.context.setText("No week selected.")
            self.context.setToolTip("")

    def _week_index(self, start):
        # Python dates are opaque QVariant objects; compare them in Python.
        return next((i for i in range(self.week_selector.count()) if self.week_selector.itemData(i) == start), -1)

    def _point(self, index, family):
        if not 0 <= index < len(self.weeks):
            return
        self.week_selector.setCurrentIndex(self._week_index(self.weeks[index]))
        name = self.selectors[family].currentText() if family else "All exercises"
        if family and not name:
            return
        if name and self.detail_exercise.findText(name) < 0:
            self.detail_exercise.addItem(name)
        self.detail_exercise.setCurrentText(name or "All exercises")
        self._open_details()

    def _open_details(self):
        start = self.week_selector.currentData()
        if not self.dashboard or start is None:
            return
        if self.details_dialog:
            self.details_dialog.close()
        exercise = self.detail_exercise.currentText()
        records = sets_for_week(self.dashboard, start, "" if exercise == "All exercises" else exercise)
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(f"Logged sets · week of {start} · {exercise}")
        dialog.resize(900, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(_label(f"{exercise} · {len(records)} logged sets · week of {start}"))
        layout.addWidget(_label("Original logged values, using configured canonical exercise names. Blank RIR stays unknown. Source files are unchanged."))
        table = _table(["Date", "Workout", "Exercise", "Set type", "Weight lb", "Reps", "RIR", "Source row", "Source file"])
        table.setRowCount(len(records))
        for row, record in enumerate(records):
            # Aggregates exclude nonfinite weights, but source inspection retains them.
            weight = (f"Invalid ({record.weight})" if record.weight is not None and not record.weight.is_finite()
                      else decimal_text(record.weight))
            _row(table, row, (record.workout_date, record.workout, record.exercise, record.set_type,
                              weight, decimal_text(record.reps), decimal_text(record.rir), record.source_row,
                              record.source_file or "Selected export"))
        layout.addWidget(table)
        if not records:
            layout.addWidget(_label("No logged sets for this selection. This does not confirm a skipped workout."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.finished.connect(lambda: self._details_closed(dialog))
        self.details_dialog = dialog
        dialog.show()

    def _details_closed(self, dialog):
        if self.details_dialog is dialog:
            self.details_dialog = None
