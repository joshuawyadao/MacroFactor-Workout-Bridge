from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
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
from .models import BridgeReport
from .service import apply_changes, build_preview


APP_NAME = "MacroFactor Workout Bridge"


class BridgeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._report: BridgeReport | None = None
        self._choices: dict[str, tuple[str, ...]] = {}
        self.setWindowTitle(APP_NAME)
        self.resize(1040, 760)
        self.setMinimumSize(850, 620)
        self._build_ui()
        self.config_path.setText(str(bundled_config_path()))
        self._set_status("Choose a MacroFactor export and coach workbook to begin.")

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
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
        self.setCentralWidget(central)

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
            )
        )
        self._set_status(
            f"Preview ready: {len(report.proposed_writes)} proposed change(s), "
            f"{reported} item(s) to review. No source file was changed."
        )

    def _display_report(self, report: BridgeReport) -> None:
        self.preview_table.setRowCount(len(report.proposed_writes))
        for row, proposal in enumerate(report.proposed_writes):
            values = (proposal.cell, proposal.value, ", ".join(proposal.source_exercises))
            for column, value in enumerate(values):
                self.preview_table.setItem(row, column, QTableWidgetItem(value))
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
