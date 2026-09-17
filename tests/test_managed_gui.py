import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from macrofactor_bridge.history import load_dashboard_annotations
from macrofactor_bridge.ooxml import file_sha256
from tests.test_managed_history import managed_inputs, write_export

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from macrofactor_bridge.desktop import BridgeWindow


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class ManagedGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["managed-test"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = managed_inputs(self.directory)
        self.settings = QSettings(str(self.directory / "preferences.ini"), QSettings.Format.IniFormat)
        self.window = BridgeWindow(autoload=True, settings=self.settings, workspace_root=self.root)
        self.addCleanup(self.window.close)
        self.wait_for(lambda: self.window.managed.snapshot is not None)

    def wait_for(self, condition):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(10)
        self.fail("Background load did not reach expected state: " + self.window.managed.status.text())

    def add_new_export(self):
        write_export(self.root / "inbox/macrofactor/new.csv", [
            "2026-09-01,Day A,Tempo Back Squat,Standard Set,510,5,2",
        ])

    def test_startup_loads_sources_and_remembers_workspace_for_next_launch(self):
        self.assertEqual(self.window._history_dashboard.set_count, 7)
        self.assertTrue(self.window.managed.enabled)
        self.assertFalse(self.window.history_sources.isEnabled())
        self.assertEqual(self.settings.value("workspace"), str(self.root))
        second = BridgeWindow(autoload=True, settings=self.settings)
        self.addCleanup(second.close)
        self.wait_for(lambda: second.managed.snapshot is not None)
        self.assertEqual(second._history_dashboard.set_count, 7)
        self.assertEqual(second.managed.root, self.root)

    def test_changed_inbox_refreshes_without_manual_file_selection(self):
        self.add_new_export()
        self.window.managed.poll()
        self.wait_for(lambda: self.window._history_dashboard.set_count == 8)
        self.assertIn("2 unique exports", self.window.managed.status.text())
        self.assertTrue(self.window._history_dashboard.records[-1].source_file)

    def test_refresh_waits_for_unsaved_feedback_then_resumes_after_save(self):
        self.window.managed.open_feedback()
        self.assertIs(self.window.history_analysis_tabs.currentWidget(), self.window.history_context_page)
        self.assertEqual(self.window.history_block_combo.currentText(), "Archive")
        self.window.history_week_notes.setText("Felt recovered after travel")
        self.add_new_export()
        self.window.managed.poll()
        self.assertIsNone(self.window.managed._job)
        self.assertIn("Save weekly feedback", self.window.managed.status.text())
        self.assertEqual(self.window._history_dashboard.set_count, 7)
        selected_week = self.window.history_week_combo.currentText()
        self.window._save_history_annotation()
        self.wait_for(lambda: self.window._history_dashboard.set_count == 8)
        saved = load_dashboard_annotations(self.root / "annotations/workout-history.json")
        self.assertEqual(saved.blocks["Archive"].weeks[selected_week].notes, "Felt recovered after travel")

    def test_edits_started_while_loading_are_not_discarded_on_result(self):
        controller = self.window.managed
        snapshot = controller.snapshot
        self.window.history_week_notes.setText("Unsaved feedback")
        controller._received(controller._token, snapshot, "")
        self.assertEqual(self.window.history_week_notes.text(), "Unsaved feedback")
        self.assertIn("Save weekly feedback first", controller.status.text())

    def test_explicit_refresh_defaults_to_preserving_unsaved_feedback(self):
        self.window.history_week_notes.setText("Keep this feedback")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as question:
            self.window.managed.refresh(force=True)
        self.assertEqual(question.call_args.args[-1], QMessageBox.StandardButton.No)
        self.assertIsNone(self.window.managed._job)
        self.assertEqual(self.window.history_week_notes.text(), "Keep this feedback")

    def test_external_annotation_change_cannot_be_overwritten(self):
        path = self.root / "annotations/workout-history.json"
        self.window.history_week_notes.setText("My unsaved note")
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        changed = file_sha256(path)
        with patch.object(QMessageBox, "critical") as message:
            self.window._save_history_annotation()
        self.assertTrue(message.called)
        self.assertEqual(file_sha256(path), changed)
        self.assertEqual(self.window.history_week_notes.text(), "My unsaved note")

    def test_manual_override_and_stale_results_do_not_replace_view(self):
        controller = self.window.managed
        before = self.window._history_dashboard
        token, snapshot = controller._token, controller.snapshot
        controller.auto.setChecked(False)
        self.assertTrue(self.window.history_sources.isEnabled())
        controller._received(token, snapshot, "")
        self.assertIs(self.window._history_dashboard, before)
        self.assertFalse(self.settings.value("automatic", True, type=bool))

    def test_failed_refresh_keeps_previous_view_with_explicit_status(self):
        controller = self.window.managed
        before = self.window._history_dashboard
        controller._received(controller._token, None, "A file is still being copied")
        self.assertIs(self.window._history_dashboard, before)
        self.assertIn("previous data was not replaced", controller.status.text())
        self.assertFalse(controller.status.isHidden())
        self.assertIn("needs attention", controller.health.text())

    def test_compact_toolbar_hides_duplicate_controls_but_keeps_data_menu(self):
        controller = self.window.managed
        self.assertTrue(self.window.history_load_button.isHidden())
        self.assertTrue(self.window.history_sources_toggle.isHidden())
        self.assertTrue(self.window.history_overview.isHidden())
        self.assertTrue(self.window.history_status.isHidden())
        self.assertTrue(controller.status.isHidden())
        self.assertIn("Auto", controller.health.text())
        actions = {action.text(): action for action in controller.data_menu.actions()}
        self.assertTrue(actions["Auto-load inboxes"].isChecked())
        self.assertTrue(actions["Refresh inboxes"].isEnabled())
        self.assertIn("Choose workspace…", actions)
        actions["Source status…"].trigger()
        self.assertIsNotNone(controller._report_dialog)
        controller._report_dialog.close()
        actions["Select files manually…"].trigger()
        self.assertFalse(controller.enabled)
        self.assertFalse(self.window.history_load_button.isHidden())
        self.assertFalse(self.window.history_sources.isHidden())
        self.assertTrue(self.window.history_sources.isEnabled())

    def test_secondary_views_are_reachable_and_active_view_stays_visible(self):
        tabs = self.window.history_analysis_tabs
        self.assertEqual([tabs.isTabVisible(i) for i in range(tabs.count())], [True, True, True, False, False, False])
        self.window.history_week_notes.setText("Keep my pending feedback")
        tabs.secondary_actions[4].trigger()
        self.assertIs(tabs.currentWidget(), self.window.history_comparison)
        self.assertTrue(tabs.isTabVisible(4))
        self.assertTrue(tabs.secondary_actions[4].isChecked())
        self.window.managed.feedback.click()
        self.assertIs(tabs.currentWidget(), self.window.history_context_page)
        self.assertTrue(tabs.isTabVisible(5))
        self.assertFalse(tabs.isTabVisible(4))
        self.assertEqual(self.window.history_week_notes.text(), "Keep my pending feedback")
        self.assertFalse(self.window.history_status.isHidden())
        tabs.setCurrentWidget(self.window.history_home)
        self.assertFalse(tabs.isTabVisible(5))
        self.assertTrue(self.window.history_status.isHidden())

    def test_minimum_window_auto_controls_and_source_report(self):
        self.window.resize(900, 680)
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.width(), 900)
        self.assertFalse(self.window.grab().isNull())
        self.window.managed.show_sources()
        self.assertIsNotNone(self.window.managed._report_dialog)
        self.window.managed._report_dialog.close()

    def test_background_reload_recalculates_scroll_layout_without_overlap(self):
        self.window.resize(900, 680)
        self.window.show()
        self.app.processEvents()
        self.add_new_export()
        self.window.managed.poll()
        self.wait_for(lambda: self.window._history_dashboard.set_count == 8)
        QTest.qWait(100)
        self.app.processEvents()
        home = self.window.history_home
        for first, second in zip(home.report_cards, home.report_cards[1:]):
            self.assertLess(first.geometry().right(), second.geometry().left())
        for card in home.cards:
            self.assertLess(card.button.geometry().bottom(), card.chart.geometry().top())
        self.assertGreater(home.widget().height(), home.viewport().height())


if __name__ == "__main__":
    unittest.main()
