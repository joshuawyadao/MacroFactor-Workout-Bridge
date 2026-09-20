"""GUI fixtures release their Qt objects and finish workers before disposal."""

import importlib.util
import os
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtCore import QCoreApplication, QEvent, QRunnable, QThreadPool
    from PySide6.QtWidgets import QApplication, QDialog
    from shiboken6 import isValid

    from macrofactor_bridge.desktop import BridgeWindow
    from tests.gui_support import dispose_widget


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class GuiSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["gui-support-test"])

    def ensure_disposed(self, widget):
        """Release probes even when an assertion catches a broken helper."""
        if isValid(widget):
            widget.close()
            self.assertTrue(QThreadPool.globalInstance().waitForDone(15000))
            widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_repeated_windows_release_widgets_and_owned_top_level_dialogs(self):
        for iteration in range(3):
            with self.subTest(iteration=iteration):
                window = BridgeWindow()
                self.addCleanup(self.ensure_disposed, window)
                child = window.create_button
                dialog = QDialog(window)
                self.assertTrue(dialog.isWindow())
                dispose_widget(window)
                self.assertFalse(isValid(window))
                self.assertFalse(isValid(child))
                self.assertFalse(isValid(dialog))

    def test_disposal_is_idempotent_for_parent_and_deleted_children(self):
        window = BridgeWindow()
        self.addCleanup(self.ensure_disposed, window)
        dialog = QDialog(window)
        dispose_widget(window)
        self.assertFalse(isValid(dialog))
        dispose_widget(dialog)
        dispose_widget(window)

    def test_worker_finishes_before_window_and_controller_are_destroyed(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        observations = []

        class PendingLoad(QRunnable):
            def run(self):
                started.set()
                if release.wait(5):
                    observations.append("worker finished")
                    finished.set()

        class ClosingWindow(BridgeWindow):
            def closeEvent(self, event):
                observations.append("window closed")
                super().closeEvent(event)
                release.set()

        window = ClosingWindow()
        self.addCleanup(self.ensure_disposed, window)
        self.addCleanup(release.set)
        controller = window.managed
        window.destroyed.connect(lambda: observations.append("window destroyed"))
        job = PendingLoad()
        QThreadPool.globalInstance().start(job)
        self.assertTrue(started.wait(5), "The test worker did not start")
        self.assertFalse(finished.is_set())

        dispose_widget(window)

        self.assertTrue(finished.is_set(), "Disposal returned with the worker active")
        self.assertFalse(isValid(window))
        self.assertFalse(isValid(controller))
        self.assertEqual(observations, ["window closed", "worker finished", "window destroyed"])

    def test_worker_timeout_preserves_widget_for_later_cleanup(self):
        window = BridgeWindow()
        self.addCleanup(self.ensure_disposed, window)
        with patch("tests.gui_support.QThreadPool") as pool:
            pool.globalInstance.return_value.waitForDone.return_value = False
            with self.assertRaisesRegex(TimeoutError, "background workers"):
                dispose_widget(window, timeout_ms=1)
            pool.globalInstance.return_value.waitForDone.assert_called_once_with(1)
        self.assertTrue(isValid(window))
        self.assertTrue(window.managed._closed)
        dispose_widget(window)
        self.assertFalse(isValid(window))


if __name__ == "__main__":
    unittest.main()
