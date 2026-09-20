"""Lifecycle support for tests that share one QApplication."""

from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
from shiboken6 import isValid


def dispose_widget(widget, *, timeout_ms=15000):
    """Close a fixture, finish its workers, and destroy its owned Qt objects."""
    if not isValid(widget):
        return

    # BridgeWindow.closeEvent stops managed polling and ignores pending results.
    widget.close()
    # Workers can still be using temporary fixture files after close returns.
    # Keep the widget and its controller alive until those jobs finish.
    if not QThreadPool.globalInstance().waitForDone(timeout_ms):
        raise TimeoutError("GUI cleanup timed out waiting for background workers")

    if isValid(widget):
        widget.deleteLater()
    # unittest never enters QApplication.exec(), so deferred deletion must be
    # delivered explicitly, including deletes queued by rebuilt child panels.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
