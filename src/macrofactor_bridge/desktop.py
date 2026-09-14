from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import load_config
from .desktop_model import (
    bundled_config_path,
    copy_mapping,
    default_output_path,
    discover_sheet_weeks,
    latest_export_week,
    review_text,
)
from .history import (
    BLOCK_TYPE_OPTIONS,
    WEEK_REASON_OPTIONS,
    WEEK_STATUS_OPTIONS,
    DashboardAnnotations,
    HistoryDashboard,
    build_history_dashboard,
    decimal_text,
    default_dashboard_annotations_path,
    duration_text,
    load_dashboard_annotations,
    option_label,
    save_dashboard_annotations,
    update_block_annotation,
    update_week_annotation,
)
from .models import BridgeReport
from .service import apply_changes, build_preview


APP_NAME = "MacroFactor Workout Bridge"


class BridgeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._report: BridgeReport | None = None
        self._choices: dict[str, tuple[str, ...]] = {}
        self._history_dashboard: HistoryDashboard | None = None
        self._history_annotations = DashboardAnnotations()
        self.setWindowTitle(APP_NAME)
        self.resize(1120, 820)
        self.setMinimumSize(900, 680)
        self._build_ui()
        bundled = str(bundled_config_path())
        self.config_path.setText(bundled)
        self.history_config_path.setText(bundled)
        self._set_status("Choose a MacroFactor export and coach workbook to begin.")

    def _build_ui(self) -> None:
        bridge_tab = QWidget()
        outer = QVBoxLayout(bridge_tab)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(16)

        title = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        subtitle = QLabel(
            "Preview completed MacroFactor sets, then create a safe copy of your coach workbook."
        )
        subtitle.setObjectName("subtitle")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        inputs = QGroupBox("1  Choose files")
        input_grid = QGridLayout(inputs)
        input_grid.setColumnStretch(1, 1)
        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText("MacroFactor exercise-log export (.csv or .xlsx)")
        export_button = QPushButton("Choose…")
        export_button.clicked.connect(self._choose_export)
        input_grid.addWidget(QLabel("MacroFactor export"), 0, 0)
        input_grid.addWidget(self.export_path, 0, 1)
        input_grid.addWidget(export_button, 0, 2)

        self.workbook_path = QLineEdit()
        self.workbook_path.setPlaceholderText("Coach workbook (.xlsx)")
        workbook_button = QPushButton("Choose…")
        workbook_button.clicked.connect(self._choose_workbook)
        input_grid.addWidget(QLabel("Coach workbook"), 1, 0)
        input_grid.addWidget(self.workbook_path, 1, 1)
        input_grid.addWidget(workbook_button, 1, 2)

        self.config_path = QLineEdit()
        config_button = QPushButton("Choose…")
        config_button.clicked.connect(self._choose_config)
        save_mapping_button = QPushButton("Save editable copy…")
        save_mapping_button.clicked.connect(self._save_mapping_copy)
        config_actions = QHBoxLayout()
        config_actions.setContentsMargins(0, 0, 0, 0)
        config_actions.addWidget(config_button)
        config_actions.addWidget(save_mapping_button)
        input_grid.addWidget(QLabel("Exercise mapping"), 2, 0)
        input_grid.addWidget(self.config_path, 2, 1)
        input_grid.addLayout(config_actions, 2, 2)
        outer.addWidget(inputs)

        target = QGroupBox("2  Choose destination and workout dates")
        target_grid = QGridLayout(target)
        target_grid.setColumnStretch(1, 1)
        target_grid.setColumnStretch(3, 1)
        self.sheet_combo = QComboBox()
        self.week_combo = QComboBox()
        refresh_button = QPushButton("Discover")
        refresh_button.clicked.connect(self._discover_targets)
        target_grid.addWidget(QLabel("Worksheet"), 0, 0)
        target_grid.addWidget(self.sheet_combo, 0, 1)
        target_grid.addWidget(QLabel("Coach week"), 0, 2)
        target_grid.addWidget(self.week_combo, 0, 3)
        target_grid.addWidget(refresh_button, 0, 4)

        self.from_date = QDateEdit()
        self.to_date = QDateEdit()
        for control in (self.from_date, self.to_date):
            control.setCalendarPopup(True)
            control.setDisplayFormat("MMM d, yyyy")
        today = QDate.currentDate()
        self.from_date.setDate(today.addDays(-today.dayOfWeek() + 1))
        self.to_date.setDate(self.from_date.date().addDays(6))
        use_latest_button = QPushButton("Use latest export week")
        use_latest_button.clicked.connect(self._use_latest_export_week)
        target_grid.addWidget(QLabel("From"), 1, 0)
        target_grid.addWidget(self.from_date, 1, 1)
        target_grid.addWidget(QLabel("Through"), 1, 2)
        target_grid.addWidget(self.to_date, 1, 3)
        target_grid.addWidget(use_latest_button, 1, 4)
        outer.addWidget(target)

        action_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview workbook changes")
        self.preview_button.setObjectName("primaryButton")
        self.preview_button.clicked.connect(self._preview)
        self.create_button = QPushButton("Create safe workbook copy…")
        self.create_button.clicked.connect(self._create_output)
        self.create_button.setEnabled(False)
        self.save_report_button = QPushButton("Save review report…")
        self.save_report_button.clicked.connect(self._save_report)
        self.save_report_button.setEnabled(False)
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.create_button)
        action_row.addWidget(self.save_report_button)
        action_row.addStretch()
        outer.addLayout(action_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("Proposed changes"))
        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["Cell", "Value", "Source exercise(s)"])
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        preview_layout.addWidget(self.preview_table)
        splitter.addWidget(preview_frame)

        review_frame = QFrame()
        review_layout = QVBoxLayout(review_frame)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.addWidget(QLabel("Review needed"))
        self.review_panel = QPlainTextEdit()
        self.review_panel.setReadOnly(True)
        self.review_panel.setPlaceholderText(
            "Unmatched exercises, ambiguous matches, zero-rep rows, occupied cells, and skipped data will appear here."
        )
        review_layout.addWidget(self.review_panel)
        splitter.addWidget(review_frame)
        splitter.setSizes([620, 380])
        outer.addWidget(splitter, 1)

        self.status = QLabel()
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.tabs = QTabWidget()
        self.tabs.addTab(bridge_tab, "Weekly Bridge")
        self.tabs.addTab(self._build_history_ui(), "Workout History")
        self.setCentralWidget(self.tabs)

        self.sheet_combo.currentTextChanged.connect(self._sheet_changed)
        self.week_combo.currentTextChanged.connect(self._selection_changed)
        self.export_path.textChanged.connect(self._invalidate_preview)
        self.workbook_path.textChanged.connect(self._invalidate_preview)
        self.config_path.textChanged.connect(self._invalidate_preview)
        self.from_date.dateChanged.connect(self._invalidate_preview)
        self.to_date.dateChanged.connect(self._invalidate_preview)

        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7fa; }
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 9px 18px; }
            QGroupBox { background: white; border: 1px solid #d9dee7; border-radius: 10px;
                        margin-top: 12px; padding: 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLineEdit, QComboBox, QDateEdit, QPlainTextEdit, QTableWidget {
                background: white; border: 1px solid #cdd3dd; border-radius: 6px; padding: 5px;
            }
            QPushButton { min-height: 28px; padding: 2px 12px; }
            QPushButton#primaryButton { background: #1769e0; color: white; border: none;
                                        border-radius: 7px; font-weight: 600; min-height: 34px; }
            QPushButton#primaryButton:hover { background: #0d5dcc; }
            QLabel#subtitle { color: #586174; }
            QLabel#status { background: #eaf2ff; color: #214b84; border-radius: 7px; padding: 9px; }
            """
        )

    def _build_history_ui(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(12)

        title = QLabel("Workout History")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        subtitle = QLabel(
            "Review calendar-week exercise trends and coach-program blocks. "
            "This dashboard never changes either source file."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        inputs = QGroupBox("History sources")
        grid = QGridLayout(inputs)
        grid.setColumnStretch(1, 1)
        self.history_export_path = QLineEdit()
        self.history_export_path.setPlaceholderText(
            "MacroFactor all-time exercise-log export (.csv or .xlsx)"
        )
        export_button = QPushButton("Choose…")
        export_button.clicked.connect(self._choose_history_export)
        grid.addWidget(QLabel("All-time export"), 0, 0)
        grid.addWidget(self.history_export_path, 0, 1)
        grid.addWidget(export_button, 0, 2)

        self.history_workbook_path = QLineEdit()
        self.history_workbook_path.setPlaceholderText("Newest coach workbook (.xlsx)")
        workbook_button = QPushButton("Choose…")
        workbook_button.clicked.connect(self._choose_history_workbook)
        grid.addWidget(QLabel("Coach workbook"), 1, 0)
        grid.addWidget(self.history_workbook_path, 1, 1)
        grid.addWidget(workbook_button, 1, 2)

        self.history_config_path = QLineEdit()
        config_button = QPushButton("Choose…")
        config_button.clicked.connect(self._choose_history_config)
        grid.addWidget(QLabel("Exercise mapping"), 2, 0)
        grid.addWidget(self.history_config_path, 2, 1)
        grid.addWidget(config_button, 2, 2)

        self.history_annotations_path = QLineEdit()
        self.history_annotations_path.setPlaceholderText(
            "Private local annotation file (.json); created when you save"
        )
        annotations_button = QPushButton("Choose existing…")
        annotations_button.clicked.connect(self._choose_history_annotations)
        grid.addWidget(QLabel("Private annotations"), 3, 0)
        grid.addWidget(self.history_annotations_path, 3, 1)
        grid.addWidget(annotations_button, 3, 2)
        outer.addWidget(inputs)

        actions = QHBoxLayout()
        self.history_load_button = QPushButton("Load history dashboard")
        self.history_load_button.setObjectName("primaryButton")
        self.history_load_button.clicked.connect(self._load_history)
        self.history_overview = QLabel("Choose the two source files to summarize your history.")
        self.history_overview.setWordWrap(True)
        actions.addWidget(self.history_load_button)
        actions.addWidget(self.history_overview, 1)
        outer.addLayout(actions)

        analysis = QSplitter(Qt.Orientation.Horizontal)
        block_frame = QFrame()
        block_layout = QVBoxLayout(block_frame)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.addWidget(QLabel("Coach blocks (newest workbook, tab order)"))
        self.history_block_table = QTableWidget(0, 7)
        self.history_block_table.setHorizontalHeaderLabels(
            [
                "Block",
                "Weeks",
                "Results",
                "Type",
                "Start",
                "Mapped",
                "Context",
            ]
        )
        self.history_block_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.history_block_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        block_header = self.history_block_table.horizontalHeader()
        block_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            block_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        block_layout.addWidget(self.history_block_table)
        analysis.addWidget(block_frame)

        exercise_frame = QFrame()
        exercise_layout = QVBoxLayout(exercise_frame)
        exercise_layout.setContentsMargins(0, 0, 0, 0)
        exercise_selector = QHBoxLayout()
        exercise_selector.addWidget(QLabel("Exercise trend"))
        self.history_exercise_combo = QComboBox()
        exercise_selector.addWidget(self.history_exercise_combo, 1)
        self.history_trend = QLabel("Estimated 1RM trend: —")
        self.history_trend.setObjectName("trend")
        exercise_selector.addWidget(self.history_trend)
        exercise_layout.addLayout(exercise_selector)
        self.history_trend_table = QTableWidget(0, 9)
        self.history_trend_table.setHorizontalHeaderLabels(
            [
                "Week of",
                "Block",
                "Coach week",
                "Days",
                "Sets",
                "Top lb",
                "Est. 1RM",
                "Volume",
                "Avg RIR",
            ]
        )
        self.history_trend_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        trend_header = self.history_trend_table.horizontalHeader()
        trend_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        trend_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        trend_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(3, 9):
            trend_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        exercise_layout.addWidget(self.history_trend_table)
        analysis.addWidget(exercise_frame)
        analysis.setSizes([570, 500])
        outer.addWidget(analysis, 1)

        annotations = QGroupBox("Private block and week context")
        annotation_grid = QGridLayout(annotations)
        annotation_grid.setColumnStretch(1, 1)
        annotation_grid.setColumnStretch(3, 1)
        self.history_block_combo = QComboBox()
        self.history_block_type_combo = QComboBox()
        for value, label in BLOCK_TYPE_OPTIONS:
            self.history_block_type_combo.addItem(label, value)
        self.history_start_known = QCheckBox("Start date known")
        self.history_start_date = QDateEdit()
        self.history_start_date.setCalendarPopup(True)
        self.history_start_date.setDisplayFormat("MMM d, yyyy")
        self.history_start_date.setDate(QDate.currentDate())
        self.history_start_date.setEnabled(False)
        annotation_grid.addWidget(QLabel("Block"), 0, 0)
        annotation_grid.addWidget(self.history_block_combo, 0, 1)
        annotation_grid.addWidget(QLabel("Block type"), 0, 2)
        annotation_grid.addWidget(self.history_block_type_combo, 0, 3)
        annotation_grid.addWidget(self.history_start_known, 0, 4)
        annotation_grid.addWidget(self.history_start_date, 0, 5)

        self.history_block_notes = QLineEdit()
        self.history_block_notes.setPlaceholderText("Optional block context")
        annotation_grid.addWidget(QLabel("Block notes"), 1, 0)
        annotation_grid.addWidget(self.history_block_notes, 1, 1, 1, 5)

        self.history_week_combo = QComboBox()
        self.history_week_status_combo = QComboBox()
        for value, label in WEEK_STATUS_OPTIONS:
            self.history_week_status_combo.addItem(label, value)
        self.history_week_reason_combo = QComboBox()
        for value, label in WEEK_REASON_OPTIONS:
            self.history_week_reason_combo.addItem(label, value)
        annotation_grid.addWidget(QLabel("Coach week"), 2, 0)
        annotation_grid.addWidget(self.history_week_combo, 2, 1)
        annotation_grid.addWidget(QLabel("Status"), 2, 2)
        annotation_grid.addWidget(self.history_week_status_combo, 2, 3)
        annotation_grid.addWidget(QLabel("Reason"), 2, 4)
        annotation_grid.addWidget(self.history_week_reason_combo, 2, 5)

        self.history_affected_movements = QLineEdit()
        self.history_affected_movements.setPlaceholderText(
            "Optional comma-separated movements"
        )
        self.history_week_notes = QLineEdit()
        self.history_week_notes.setPlaceholderText("Optional week context")
        annotation_grid.addWidget(QLabel("Affected movements"), 3, 0)
        annotation_grid.addWidget(self.history_affected_movements, 3, 1, 1, 2)
        annotation_grid.addWidget(QLabel("Week notes"), 3, 3)
        annotation_grid.addWidget(self.history_week_notes, 3, 4, 1, 2)

        self.history_save_annotation_button = QPushButton("Save private annotation")
        self.history_save_annotation_button.setEnabled(False)
        self.history_save_annotation_button.clicked.connect(
            self._save_history_annotation
        )
        privacy = QLabel(
            "Vacation and injury remain context—not fatigue examples. "
            "Annotations are saved only to the selected local JSON file."
        )
        privacy.setObjectName("subtitle")
        privacy.setWordWrap(True)
        annotation_grid.addWidget(self.history_save_annotation_button, 4, 0, 1, 2)
        annotation_grid.addWidget(privacy, 4, 2, 1, 4)
        outer.addWidget(annotations)

        self.history_status = QLabel(
            "Recovery and deload prediction are intentionally outside this milestone."
        )
        self.history_status.setObjectName("status")
        self.history_status.setWordWrap(True)
        outer.addWidget(self.history_status)

        self.history_exercise_combo.currentTextChanged.connect(
            self._display_history_exercise
        )
        self.history_block_combo.currentTextChanged.connect(
            self._history_block_changed
        )
        self.history_week_combo.currentTextChanged.connect(
            self._history_week_changed
        )
        self.history_start_known.toggled.connect(
            self.history_start_date.setEnabled
        )
        return tab

    def _choose_export(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose MacroFactor exercise log", "", "Workout exports (*.csv *.xlsx)"
        )
        if path:
            self.export_path.setText(path)
            self._use_latest_export_week()

    def _choose_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose coach workbook", "", "Excel workbooks (*.xlsx)"
        )
        if path:
            self.workbook_path.setText(path)
            self._discover_targets()

    def _choose_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose exercise mapping", "", "JSON mappings (*.json)"
        )
        if path:
            self.config_path.setText(path)
            if self.workbook_path.text().strip():
                self._discover_targets()

    def _choose_history_export(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose MacroFactor all-time exercise log",
            "",
            "Workout exports (*.csv *.xlsx)",
        )
        if path:
            self.history_export_path.setText(path)

    def _choose_history_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose newest coach workbook", "", "Excel workbooks (*.xlsx)"
        )
        if not path:
            return
        self.history_workbook_path.setText(path)
        if not self.history_annotations_path.text().strip():
            self.history_annotations_path.setText(
                str(default_dashboard_annotations_path(path))
            )

    def _choose_history_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose exercise mapping", "", "JSON mappings (*.json)"
        )
        if path:
            self.history_config_path.setText(path)

    def _choose_history_annotations(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose existing dashboard annotations",
            "",
            "JSON annotations (*.json)",
        )
        if path:
            self.history_annotations_path.setText(path)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _load_history(self, *_args: object) -> None:
        selected_block = self.history_block_combo.currentText()
        selected_week = self.history_week_combo.currentText()
        selected_exercise = self.history_exercise_combo.currentText()
        try:
            required = {
                "MacroFactor all-time export": self.history_export_path.text().strip(),
                "coach workbook": self.history_workbook_path.text().strip(),
                "exercise mapping": self.history_config_path.text().strip(),
            }
            missing = [label for label, value in required.items() if not value]
            if missing:
                raise ValueError(f"Choose {', '.join(missing)} before loading history")
            if not self.history_annotations_path.text().strip():
                self.history_annotations_path.setText(
                    str(
                        default_dashboard_annotations_path(
                            self.history_workbook_path.text().strip()
                        )
                    )
                )
            annotations = load_dashboard_annotations(
                self.history_annotations_path.text().strip()
            )
            dashboard = build_history_dashboard(
                self.history_export_path.text().strip(),
                self.history_workbook_path.text().strip(),
                load_config(self.history_config_path.text().strip()),
                annotations,
            )
        except Exception as exc:
            self._show_history_error("History dashboard could not be loaded", exc)
            return
        self._history_annotations = annotations
        self._history_dashboard = dashboard
        self._display_history_dashboard(dashboard)
        self.history_save_annotation_button.setEnabled(True)

        if selected_block:
            block_index = self.history_block_combo.findText(selected_block)
            if block_index >= 0:
                self.history_block_combo.setCurrentIndex(block_index)
        if selected_week:
            week_index = self.history_week_combo.findText(selected_week)
            if week_index >= 0:
                self.history_week_combo.setCurrentIndex(week_index)
        if selected_exercise:
            exercise_index = self.history_exercise_combo.findText(selected_exercise)
            if exercise_index >= 0:
                self.history_exercise_combo.setCurrentIndex(exercise_index)

        warning_text = " ".join(dashboard.warnings)
        status = (
            "History loaded read-only; neither source file was changed. "
            "Estimated 1RM uses weighted standard sets of 1–12 reps."
        )
        if warning_text:
            status += f" {warning_text}"
        self.history_status.setText(status)

    def _display_history_dashboard(self, dashboard: HistoryDashboard) -> None:
        rir_percent = round(dashboard.rir_set_count * 100 / dashboard.set_count)
        duration = duration_text(dashboard.total_duration_seconds)
        self.history_overview.setText(
            f"{dashboard.first_workout:%b %d, %Y}–{dashboard.last_workout:%b %d, %Y}  •  "
            f"{dashboard.set_count} sets  •  {dashboard.training_day_count} training days  •  "
            f"{dashboard.workout_count} workouts  •  RIR {dashboard.rir_set_count}/{dashboard.set_count} "
            f"({rir_percent}%)  •  {duration} logged across "
            f"{dashboard.duration_session_count} workouts"
        )

        self.history_block_table.setRowCount(len(dashboard.blocks))
        for row, block in enumerate(dashboard.blocks):
            values = (
                block.name,
                str(len(block.week_labels)),
                f"{block.completed_results}/{block.programmed_results}",
                option_label(BLOCK_TYPE_OPTIONS, block.block_type),
                block.start_date.isoformat() if block.start_date else "Not set",
                str(block.mapped_set_count) if block.start_date else "—",
                str(block.annotated_week_count),
            )
            for column, value in enumerate(values):
                self.history_block_table.setItem(row, column, QTableWidgetItem(value))

        self.history_block_combo.blockSignals(True)
        self.history_block_combo.clear()
        self.history_block_combo.addItems(block.name for block in dashboard.blocks)
        self.history_block_combo.blockSignals(False)

        self.history_exercise_combo.blockSignals(True)
        self.history_exercise_combo.clear()
        self.history_exercise_combo.addItems(
            summary.exercise for summary in dashboard.exercises
        )
        self.history_exercise_combo.blockSignals(False)
        self._history_block_changed(self.history_block_combo.currentText())
        self._display_history_exercise(self.history_exercise_combo.currentText())

    def _display_history_exercise(self, exercise: str) -> None:
        dashboard = self._history_dashboard
        if dashboard is None or not exercise:
            self.history_trend.setText("Estimated 1RM trend: —")
            self.history_trend_table.setRowCount(0)
            return
        summary = next(
            (item for item in dashboard.exercises if item.exercise == exercise), None
        )
        trends = dashboard.trends_for(exercise)
        if summary is None:
            return
        self.history_trend.setText(
            f"Estimated 1RM trend: {summary.trend}  •  "
            f"best {decimal_text(summary.best_estimated_1rm)} lb"
        )
        self.history_trend_table.setRowCount(len(trends))
        for row, trend in enumerate(trends):
            block = trend.block_name or "Unmapped"
            values = (
                trend.week_start.isoformat(),
                block,
                trend.block_week or "—",
                str(trend.training_days),
                str(trend.set_count),
                decimal_text(trend.top_weight),
                decimal_text(trend.estimated_1rm),
                decimal_text(trend.volume_load, places=0),
                decimal_text(trend.average_rir),
            )
            for column, value in enumerate(values):
                self.history_trend_table.setItem(row, column, QTableWidgetItem(value))

    def _history_block_changed(self, block_name: str) -> None:
        dashboard = self._history_dashboard
        if dashboard is None or not block_name:
            return
        block = next((item for item in dashboard.blocks if item.name == block_name), None)
        if block is None:
            return
        annotation = self._history_annotations.blocks.get(block_name)
        self.history_week_combo.blockSignals(True)
        self.history_week_combo.clear()
        self.history_week_combo.addItems(block.week_labels)
        self.history_week_combo.blockSignals(False)
        self._set_combo_data(
            self.history_block_type_combo,
            annotation.block_type if annotation else "unspecified",
        )
        self.history_start_known.blockSignals(True)
        self.history_start_known.setChecked(
            bool(annotation and annotation.start_date is not None)
        )
        self.history_start_known.blockSignals(False)
        self.history_start_date.setEnabled(self.history_start_known.isChecked())
        if annotation and annotation.start_date:
            self.history_start_date.setDate(_to_qdate(annotation.start_date))
        self.history_block_notes.setText(annotation.notes if annotation else "")
        self._history_week_changed(self.history_week_combo.currentText())

    def _history_week_changed(self, week_name: str) -> None:
        block_name = self.history_block_combo.currentText()
        block = self._history_annotations.blocks.get(block_name)
        annotation = block.weeks.get(week_name) if block and week_name else None
        self._set_combo_data(
            self.history_week_status_combo,
            annotation.status if annotation else "normal",
        )
        self._set_combo_data(
            self.history_week_reason_combo,
            annotation.reason if annotation else "unspecified",
        )
        self.history_affected_movements.setText(
            ", ".join(annotation.affected_movements) if annotation else ""
        )
        self.history_week_notes.setText(annotation.notes if annotation else "")

    def _save_history_annotation(self, *_args: object) -> None:
        if self._history_dashboard is None:
            self._show_history_error(
                "History required", ValueError("Load the dashboard before saving context.")
            )
            return
        block_name = self.history_block_combo.currentText()
        week_name = self.history_week_combo.currentText()
        path = self.history_annotations_path.text().strip()
        if not block_name or not week_name or not path:
            self._show_history_error(
                "Annotation could not be saved",
                ValueError("Choose a block, week, and private annotation file."),
            )
            return
        start_date = (
            _from_qdate(self.history_start_date.date())
            if self.history_start_known.isChecked()
            else None
        )
        try:
            annotations = update_block_annotation(
                self._history_annotations,
                block_name,
                block_type=str(self.history_block_type_combo.currentData()),
                start_date=start_date,
                notes=self.history_block_notes.text(),
            )
            annotations = update_week_annotation(
                annotations,
                block_name,
                week_name,
                status=str(self.history_week_status_combo.currentData()),
                reason=str(self.history_week_reason_combo.currentData()),
                affected_movements=tuple(
                    item.strip()
                    for item in self.history_affected_movements.text().split(",")
                    if item.strip()
                ),
                notes=self.history_week_notes.text(),
            )
            save_dashboard_annotations(path, annotations)
            self._history_annotations = annotations
            self._load_history()
            self.history_status.setText(
                f"Saved private context for {block_name} · {week_name} at {path}. "
                "Source files remain unchanged."
            )
        except Exception as exc:
            self._show_history_error("Annotation could not be saved", exc)

    def _show_history_error(self, title: str, error: Exception) -> None:
        QMessageBox.critical(self, title, str(error))
        self.history_status.setText(str(error))

    def _save_mapping_copy(self) -> None:
        suggested = str(Path.home() / "Documents" / "macrofactor-exercise-mapping.json")
        destination, _ = QFileDialog.getSaveFileName(
            self, "Save editable exercise mapping", suggested, "JSON mappings (*.json)"
        )
        if not destination:
            return
        try:
            copied = copy_mapping(self.config_path.text().strip(), destination)
        except Exception as exc:
            self._show_error("Could not save the mapping", exc)
            return
        self.config_path.setText(str(copied))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(copied)))
        self._set_status(f"Saved an editable mapping at {copied}.")

    def _use_latest_export_week(self) -> None:
        try:
            start, end = latest_export_week(self.export_path.text().strip())
        except Exception as exc:
            self._show_error("Could not read workout dates", exc)
            return
        self.from_date.setDate(_to_qdate(start))
        self.to_date.setDate(_to_qdate(end))
        self._set_status(f"Using the latest export week: {start:%b %-d}–{end:%b %-d, %Y}.")

    def _discover_targets(self) -> None:
        try:
            choices = discover_sheet_weeks(
                self.workbook_path.text().strip(), self.config_path.text().strip()
            )
        except Exception as exc:
            self._show_error("Could not discover workbook targets", exc)
            return
        self._choices = dict(choices)
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(self._choices)
        self.sheet_combo.blockSignals(False)
        self._sheet_changed(self.sheet_combo.currentText())
        if not choices:
            self._set_status("No worksheets with a configured exercise header and week labels were found.")
        else:
            self._set_status(f"Found {len(choices)} usable worksheet(s). Choose a week, then preview.")

    def _sheet_changed(self, sheet: str) -> None:
        self.week_combo.blockSignals(True)
        self.week_combo.clear()
        self.week_combo.addItems(self._choices.get(sheet, ()))
        self.week_combo.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self, *_args: object) -> None:
        self._invalidate_preview()

    def _invalidate_preview(self, *_args: object) -> None:
        if self._report is None:
            return
        self._report = None
        self.preview_table.setRowCount(0)
        self.review_panel.clear()
        self.create_button.setEnabled(False)
        self.save_report_button.setEnabled(False)
        self._set_status("Inputs changed. Preview again before creating a workbook.")

    def _preview(self) -> None:
        try:
            self._require_selections()
            config = load_config(self.config_path.text().strip())
            report = build_preview(
                self.export_path.text().strip(),
                self.workbook_path.text().strip(),
                config,
                self.sheet_combo.currentText(),
                self.week_combo.currentText(),
                _from_qdate(self.from_date.date()),
                _from_qdate(self.to_date.date()),
            )
        except Exception as exc:
            self._show_error("Preview could not be created", exc)
            return
        self._report = report
        self._display_report(report)
        self.create_button.setEnabled(bool(report.proposed_writes))
        self.save_report_button.setEnabled(True)
        reported = sum(
            len(items)
            for items in (
                report.unmatched_exercises,
                report.ambiguous_matches,
                report.zero_rep_rows,
                report.occupied_cells,
                report.skipped_rows,
                report.exercise_notes,
                report.empty_day_markers,
            )
        )
        self._set_status(
            f"Preview ready: {len(report.proposed_writes)} proposed change(s), "
            f"{reported} item(s) to review. No source file was changed."
        )

    def _display_report(self, report: BridgeReport) -> None:
        self.preview_table.setRowCount(len(report.proposed_writes))
        for row, proposal in enumerate(report.proposed_writes):
            source = ", ".join(proposal.source_exercises) or proposal.review_note or proposal.kind
            values = (proposal.cell, proposal.value, source)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if proposal.fill_color:
                    item.setBackground(QColor(f"#{proposal.fill_color[-6:]}"))
                self.preview_table.setItem(row, column, item)
        self.review_panel.setPlainText(review_text(report))

    def _create_output(self) -> None:
        if self._report is None:
            self._show_error("Preview required", ValueError("Preview the changes before creating output."))
            return
        suggested = default_output_path(
            self.workbook_path.text().strip(), self.week_combo.currentText()
        )
        output, _ = QFileDialog.getSaveFileName(
            self, "Create safe workbook copy", str(suggested), "Excel workbooks (*.xlsx)"
        )
        if not output:
            return
        try:
            config = load_config(self.config_path.text().strip())
            report = apply_changes(self._report, config, output)
        except Exception as exc:
            self._show_error("Workbook could not be created", exc)
            return
        self._report = report
        self.save_report_button.setEnabled(True)
        message = (
            f"Created {Path(output).name}\n\n"
            "The source workbook and MacroFactor export are unchanged. "
            "Workbook integrity validation passed."
        )
        box = QMessageBox(self)
        box.setWindowTitle("Workbook created")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(message)
        reveal = box.addButton("Show in Finder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is reveal:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output).parent)))
        self._set_status(f"Safe output created and validated: {output}")

    def _save_report(self) -> None:
        if self._report is None:
            return
        base = Path(self._report.output_file or self._report.input_workbook)
        suggested = base.with_name(f"{base.stem}-review.json")
        destination, _ = QFileDialog.getSaveFileName(
            self, "Save review report", str(suggested), "JSON reports (*.json)"
        )
        if not destination:
            return
        try:
            Path(destination).write_text(
                json.dumps(self._report.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self._show_error("Review report could not be saved", exc)
            return
        self._set_status(f"Review report saved: {destination}")

    def _require_selections(self) -> None:
        required = {
            "MacroFactor export": self.export_path.text().strip(),
            "coach workbook": self.workbook_path.text().strip(),
            "exercise mapping": self.config_path.text().strip(),
            "worksheet": self.sheet_combo.currentText(),
            "coach week": self.week_combo.currentText(),
        }
        missing = [label for label, value in required.items() if not value]
        if missing:
            raise ValueError(f"Choose {', '.join(missing)} before previewing")

    def _set_status(self, message: str) -> None:
        self.status.setText(message)

    def _show_error(self, title: str, error: Exception) -> None:
        QMessageBox.critical(self, title, str(error))
        self._set_status(str(error))


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} graphical application")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="create and close the main window without entering the event loop",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args, _unknown = _parser().parse_known_args(argv)
    app = QApplication.instance() or QApplication([APP_NAME])
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MacroFactor Workout Bridge")
    window = BridgeWindow()
    if args.smoke_test:
        window.show()
        app.processEvents()
        window.close()
        print(f"{APP_NAME} {__version__} GUI smoke test passed")
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
