"""Desktop coordination for managed history; scanning runs off the UI thread."""

from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget, QMessageBox,
)

from .explorer import ExplorerWeek, week_location
from .history import BlockAnnotation, WeekAnnotation
from .managed_history import discover_workspace, load_managed_history, workspace_fingerprint
from .ooxml import file_sha256


class _Result(QObject):
    ready = Signal(int, object, str)


class _Load(QRunnable):
    def __init__(self, token, root):
        super().__init__()
        self.token, self.root = token, root
        self.result = _Result()

    def run(self):
        try:
            snapshot = load_managed_history(self.root)
        except Exception as exc:
            self.result.ready.emit(self.token, None, str(exc))
        else:
            self.result.ready.emit(self.token, snapshot, "")


class ManagedHistoryController(QObject):
    def __init__(self, window, *, autoload=False, settings=None, root=None):
        super().__init__(window)
        self.window = window
        self.settings = settings if settings is not None else (QSettings("MacroFactor Workout Bridge", "Dashboard") if autoload else None)
        saved = self.settings.value("workspace", "") if self.settings else ""
        self.root = Path(root).resolve() if root else (discover_workspace(str(saved)) if autoload else None)
        self.snapshot = None
        self.fingerprint = None
        self.annotation_hash = None
        self._token = 0
        self._job = None
        self._closed = False
        self._report_dialog = None
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.auto = QCheckBox("Auto-load inboxes")
        bar.addWidget(self.auto)
        folder = QPushButton("Workspace…")
        folder.clicked.connect(self.choose_workspace)
        bar.addWidget(folder)
        self.refresh_button = QPushButton("Refresh inboxes")
        self.refresh_button.clicked.connect(lambda: self.refresh(force=True))
        bar.addWidget(self.refresh_button)
        self.sources_button = QPushButton("Source status…")
        self.sources_button.clicked.connect(self.show_sources)
        bar.addWidget(self.sources_button)
        feedback = QPushButton("Weekly feedback →")
        feedback.setToolTip("Open saved context for the export's latest logged Monday–Sunday week.")
        feedback.clicked.connect(self.open_feedback)
        bar.addWidget(feedback)
        bar.addStretch()
        layout.addLayout(bar)
        self.status = QLabel("Manual file selection. Enable automatic loading to use your managed folders.")
        self.status.setWordWrap(True)
        self.status.setObjectName("subtitle")
        self.status.setMaximumHeight(42)
        layout.addWidget(self.status)
        window.history_outer.insertWidget(2, panel)
        panel.setVisible(autoload or settings is not None or root is not None)
        if autoload or settings is not None or root is not None:
            window.history_title.hide()
            window.history_subtitle.hide()
        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.poll)
        self.auto.toggled.connect(self._mode_changed)
        enabled = bool(autoload and (self.settings.value("automatic", True, type=bool) if self.settings else True))
        self.auto.setChecked(enabled)
        self.refresh_button.setEnabled(enabled)
        self.sources_button.setEnabled(False)
        if enabled:
            QTimer.singleShot(0, self.refresh)

    @property
    def enabled(self):
        return self.auto.isChecked()

    def _message(self, text):
        self.status.setText(text)
        self.status.setToolTip(text)

    def _mode_changed(self, enabled):
        self._token += 1
        self.window.history_sources.setEnabled(not enabled)
        self.window.history_load_button.setText("Refresh dashboard" if enabled else "Load history dashboard")
        self.refresh_button.setEnabled(enabled)
        if self.settings:
            self.settings.setValue("automatic", enabled)
        if enabled:
            self.timer.start()
            QTimer.singleShot(0, self.refresh)
        else:
            self.timer.stop()
            self._message("Manual mode. Selected files stay available; loading a single export replaces the combined view.")
            self.window.history_sources_toggle.setChecked(True)

    def choose_workspace(self):
        if self.feedback_dirty():
            self._message("Save your weekly feedback before switching workspaces.")
            return
        path = QFileDialog.getExistingDirectory(self.window, "Choose local-data folder", str(self.root or Path.home()))
        if path:
            root = Path(path)
            self.root = (root / "local-data" if (root / "local-data" / "inbox").is_dir() else root).resolve()
            if self.settings:
                self.settings.setValue("workspace", str(self.root))
            self.fingerprint = None
            self.snapshot = None
            self._token += 1
            self.auto.setChecked(True)
            self.refresh(force=True)

    def feedback_dirty(self):
        w = self.window
        if w._history_dashboard is None:
            return False
        block = w._history_annotations.blocks.get(w.history_block_combo.currentText(), BlockAnnotation())
        week = block.weeks.get(w.history_week_combo.currentText(), WeekAnnotation())
        selected_date = w.history_start_date.date().toPython() if w.history_start_known.isChecked() else None
        movements = tuple(dict.fromkeys(s.strip() for s in w.history_affected_movements.text().split(",") if s.strip()))
        return (block.block_type != w.history_block_type_combo.currentData() or block.start_date != selected_date
                or block.notes != w.history_block_notes.text().strip() or week.status != w.history_week_status_combo.currentData()
                or week.reason != w.history_week_reason_combo.currentData() or week.notes != w.history_week_notes.text().strip()
                or week.affected_movements != movements)

    def poll(self):
        if not self.enabled or not self.root or self._job or self._closed:
            return
        try:
            changed = workspace_fingerprint(self.root) != self.fingerprint
        except (OSError, ValueError) as exc:
            self._message(f"Automatic refresh unavailable; showing previously loaded data. {exc}")
            return
        if changed:
            self.refresh()

    def refresh(self, *, force=False):
        if self._closed or not self.enabled or self._job:
            return
        if self.feedback_dirty():
            if not force or QMessageBox.question(
                self.window, "Unsaved weekly feedback",
                "Discard the unsaved feedback in this form and refresh from disk? Choose No to keep editing.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                self._message("New data may be available. Save weekly feedback before refreshing; your edits have been kept.")
                return
            selected_week = self.window.history_week_combo.currentText()
            self.window._history_block_changed(self.window.history_block_combo.currentText())
            self.window.history_week_combo.setCurrentText(selected_week)
        if not self.root:
            self._message("Choose your local-data workspace once; future launches will load it automatically.")
            return
        self._token += 1
        job = _Load(self._token, self.root)
        self._job = job
        job.result.ready.connect(self._received)
        self.refresh_button.setEnabled(False)
        self._message("Checking inboxes and verified archives in the background…")
        QThreadPool.globalInstance().start(job)

    def _received(self, token, snapshot, error):
        self._job = None
        self.refresh_button.setEnabled(self.enabled)
        if self._closed:
            return
        if token != self._token or not self.enabled:
            if self.enabled:
                QTimer.singleShot(0, self.refresh)
            return
        if error:
            self._message(f"Refresh needs attention; previous data was not replaced. {error}")
            return
        if self.feedback_dirty():
            self._message("New data is ready. Save weekly feedback first; your edits have been kept.")
            return
        try:
            if workspace_fingerprint(snapshot.root) != snapshot.fingerprint:
                self._message("Files changed again while loading; checking the latest versions…")
                QTimer.singleShot(0, self.refresh)
                return
        except (OSError, ValueError) as exc:
            self._message(f"Refresh needs attention; previous data was not replaced. {exc}")
            return
        self.apply(snapshot)

    def apply(self, snapshot):
        w = self.window
        if self._report_dialog:
            self._report_dialog.close()
        selected = (w.history_block_combo.currentText(), w.history_week_combo.currentText())
        w._clear_history_dashboard("Loading managed history…")
        for field, path in ((w.history_export_path, snapshot.baseline.path), (w.history_workbook_path, snapshot.coach_path),
                            (w.history_config_path, snapshot.config_path), (w.history_annotations_path, snapshot.annotation_path)):
            field.blockSignals(True)
            field.setText(str(path))
            field.blockSignals(False)
        w._history_annotations = snapshot.annotations
        w._history_dashboard = snapshot.dashboard
        w._display_history_dashboard(snapshot.dashboard)
        if w.history_block_combo.findText(selected[0]) >= 0:
            w.history_block_combo.setCurrentText(selected[0])
            if w.history_week_combo.findText(selected[1]) >= 0:
                w.history_week_combo.setCurrentText(selected[1])
        w.history_save_annotation_button.setEnabled(True)
        w.history_sources_toggle.setChecked(False)
        w.history_status.setText("Managed history loaded locally. Original inputs are unchanged. " + " ".join(snapshot.dashboard.warnings))
        self.snapshot = snapshot
        self.fingerprint = snapshot.fingerprint
        self.note_saved()
        self.sources_button.setEnabled(True)
        self._message(snapshot.summary() + " · Source status explains coverage and any conflicts.")
        if self.settings:
            self.settings.setValue("workspace", str(snapshot.root))

    def note_saved(self):
        path = Path(self.window.history_annotations_path.text())
        self.annotation_hash = file_sha256(path) if path.is_file() else None

    def check_save(self):
        if not self.enabled or not self.snapshot:
            return
        path = self.snapshot.annotation_path
        actual = file_sha256(path) if path.is_file() else None
        if actual != self.annotation_hash:
            raise ValueError("The feedback file changed outside this app. Your edits are still visible; copy them before reloading to avoid overwriting newer feedback.")

    def open_feedback(self):
        w = self.window
        dashboard = w._history_dashboard
        if dashboard is None:
            self._message("Load history before entering weekly feedback.")
            return
        if not self.feedback_dirty():
            monday = dashboard.last_workout - timedelta(days=dashboard.last_workout.weekday())
            block, week = week_location(dashboard, ExplorerWeek(monday, None))
            if w.history_block_combo.findText(block) < 0:
                self._message("The latest logged week is not mapped to a coach block. Confirm its block dates in Block context.")
            else:
                w.history_block_combo.setCurrentText(block)
                w.history_week_combo.setCurrentText(week)
        w.history_analysis_tabs.setCurrentWidget(w.history_context_page)
        w.history_week_notes.setFocus()

    def show_sources(self):
        if not self.snapshot:
            return
        if self._report_dialog:
            self._report_dialog.close()
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Managed source status")
        dialog.resize(850, 600)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self.snapshot.report())
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        self._report_dialog = dialog
        dialog.show()

    def shutdown(self):
        self._closed = True
        self.timer.stop()
        self._token += 1
