"""Palette contrast and popup/control coverage without screenshot pixel coupling."""

import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from tests.gui_support import dispose_widget
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QMessageBox
    from macrofactor_bridge.desktop import BridgeWindow
    from macrofactor_bridge.desktop_theme import BACKGROUND, SURFACE, TEXT, MUTED, SERIES_COLORS


def contrast(first, second):
    def luminance(value):
        rgb = QColor(value).getRgbF()[:3]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + 0.05) / (a + 0.05)


@unittest.skipUnless(HAS_QT, "PySide6 is an optional desktop dependency")
class DesktopThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["theme-test"])

    def test_text_and_chart_colors_have_readable_contrast(self):
        for background in (BACKGROUND, SURFACE):
            for foreground in (TEXT, MUTED, *SERIES_COLORS):
                self.assertGreaterEqual(contrast(foreground, background), 4.5)
        self.assertGreaterEqual(contrast("#101113", "#ffff00"), 4.5)
        self.assertGreaterEqual(contrast("#ffffff", "#344c59"), 4.5)

    def test_dark_palette_reaches_calendar_popup_lists_and_dialogs(self):
        window = BridgeWindow()
        self.addCleanup(dispose_widget, window)
        dialog = QMessageBox(window)
        self.addCleanup(dispose_widget, dialog)
        self.app.processEvents()
        for widget, background, foreground in (
            (window, BACKGROUND, TEXT), (window.from_date.calendarWidget(), BACKGROUND, TEXT),
            (window.sheet_combo.view(), "#202328", "#ffffff"), (dialog, BACKGROUND, TEXT),
        ):
            self.assertEqual(widget.palette().color(QPalette.ColorRole.Window).name(), background)
            self.assertEqual(widget.palette().color(QPalette.ColorRole.Text).name(), foreground)
        self.assertEqual(window.create_button.palette().color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText).name(), "#858c98")
        self.assertFalse(window.create_button.isEnabled())
        calendar = window.from_date.calendarWidget()
        self.assertEqual(calendar.firstDayOfWeek(), Qt.DayOfWeek.Monday)
        self.assertEqual(calendar.weekdayTextFormat(Qt.DayOfWeek.Sunday).foreground().color().name(),
                         SERIES_COLORS[1])


if __name__ == "__main__":
    unittest.main()
