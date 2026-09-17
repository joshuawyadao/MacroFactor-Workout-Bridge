"""Shared desktop colors and controls; independent of training data and storage."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette, QTextCharFormat
from PySide6.QtWidgets import QApplication, QCalendarWidget, QFrame, QLabel, QToolButton, QVBoxLayout

BACKGROUND = "#101113"
SURFACE = "#191b1f"
TEXT = "#f5f6f7"
MUTED = "#abb1bc"
SERIES_COLORS = ("#72d6ef", "#ffba7a")


def apply_dark_theme(app: QApplication) -> None:
    # Fusion respects the palette for popup lists, calendars, and checkboxes too.
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        "Window": BACKGROUND, "WindowText": TEXT, "Base": SURFACE,
        "AlternateBase": "#202328", "Text": TEXT, "Button": "#262a30",
        "ButtonText": TEXT, "BrightText": "#ffffff", "Highlight": "#344c59",
        "HighlightedText": "#ffffff", "ToolTipBase": "#30353d", "ToolTipText": TEXT,
        "PlaceholderText": MUTED, "Light": "#505762", "Midlight": "#3e444e",
        "Mid": "#30353d", "Dark": "#101113", "Shadow": "#000000",
        "Link": SERIES_COLORS[0], "LinkVisited": "#c5b8ef",
    }
    for role, color in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#858c98"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)


def style_calendar(calendar: QCalendarWidget) -> None:
    weekend = QTextCharFormat()
    weekend.setForeground(QColor(SERIES_COLORS[1]))
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, weekend)
    # Qt's standard navigation icons can stay black despite the dark palette.
    for name, text in (("qt_calendar_prevmonth", "‹"), ("qt_calendar_nextmonth", "›")):
        button = calendar.findChild(QToolButton, name)
        if button is not None:
            button.setIcon(QIcon())
            button.setText(text)
    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)


class SummaryCard(QFrame):
    """Compact, plain-text statistic with an always-visible unit/meaning."""

    def __init__(self, label: str) -> None:
        super().__init__()
        self.setObjectName("summaryCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(1)
        self.value = QLabel("—")
        self.value.setObjectName("summaryValue")
        caption = QLabel(label)
        caption.setObjectName("subtitle")
        layout.addWidget(self.value)
        layout.addWidget(caption)
        self.setAccessibleName(label)


STYLESHEET = """
QWidget { color: #f5f6f7; }
QMainWindow, QDialog { background: #101113; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #191b1f; color: #abb1bc; padding: 9px 18px;
    border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: white; background: #262a30; border-bottom: 2px solid #72d6ef; }
QTabBar::tab:hover { background: #30353d; color: white; }
QTabBar::tab:focus { border: 1px solid #72d6ef; }
QGroupBox { background: #191b1f; border: 1px solid #343941; border-radius: 10px;
    margin-top: 10px; padding: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QComboBox, QDateEdit, QPlainTextEdit, QTableWidget {
    background: #191b1f; border: 1px solid #424852; border-radius: 6px;
    padding: 5px; selection-background-color: #344c59; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus, QTableWidget:focus {
    border: 1px solid #72d6ef; }
QComboBox QAbstractItemView { background: #202328; color: white;
    selection-background-color: #344c59; selection-color: white; border: 1px solid #59616e; }
QHeaderView::section { background: #262a30; color: #c4c9d1; padding: 7px 6px;
    border: none; border-bottom: 1px solid #424852; font-weight: 600; }
QTableWidget { gridline-color: #30353d; }
QTableWidget::item { padding: 3px; }
QTableCornerButton::section { background: #262a30; border: none; }
QPushButton { background: #262a30; border: 1px solid #505762; border-radius: 7px;
    min-height: 26px; padding: 2px 12px; }
QPushButton:hover { background: #363c45; border-color: #88919f; }
QPushButton:pressed, QPushButton:checked { background: #344c59; }
QPushButton:focus { border: 2px solid #72d6ef; padding: 1px 11px; }
QPushButton#primaryButton { background: #f5f6f7; color: #101113;
    border: 1px solid #f5f6f7; font-weight: 600; min-height: 30px; }
QPushButton#primaryButton:hover { background: #d5eaf0; }
QPushButton#primaryButton:focus { border: 2px solid #2997b5; }
QPushButton#quietButton, QToolButton#quietButton {
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    color: #abb1bc; padding: 4px 8px; min-height: 24px; text-align: left; }
QPushButton#quietButton:hover, QToolButton#quietButton:hover {
    color: white; background: #262a30; border-color: #424852; }
QPushButton#quietButton:focus, QToolButton#quietButton:focus {
    color: white; border: 2px solid #72d6ef; padding: 3px 7px; }
QPushButton#quietButton[attention="true"] { color: #ffcc66; }
QPushButton#quietButton:disabled { color: #858c98; background: transparent; border-color: transparent; }
QToolButton#quietButton::menu-indicator { subcontrol-position: right center; }
QComboBox#quietSelector { background: transparent; border-color: transparent; padding-left: 0px; }
QComboBox#quietSelector:hover { background: #202328; border-color: #424852; }
QComboBox#quietSelector:focus { border: 1px solid #72d6ef; }
QMenu { background: #202328; color: #f5f6f7; border: 1px solid #424852; padding: 5px; }
QMenu::item { padding: 7px 24px; border-radius: 4px; }
QMenu::item:selected { background: #344c59; }
QMenu::item:disabled { color: #858c98; }
QMenu::separator { height: 1px; background: #424852; margin: 5px 8px; }
QWidget:disabled { color: #858c98; }
QPushButton:disabled { background: #1d2025; border-color: #343941; color: #858c98; }
QLabel#subtitle { color: #abb1bc; }
QLabel#status { background: #1d2b33; color: #cce7f0; border: 1px solid #344c59;
    border-radius: 7px; padding: 8px; }
QLabel#trend { color: #72d6ef; }
QFrame#summaryCard { background: #191b1f; border: 1px solid #343941; border-radius: 9px; }
QLabel#summaryValue { font-size: 22px; font-weight: 600; }
QLabel#pageTitle { font-size: 24px; font-weight: 600; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; }
QProgressBar { background: #30353d; border: none; border-radius: 3px; }
QProgressBar::chunk { background: #72d6ef; border-radius: 3px; }
QLabel#seriesA { color: #72d6ef; font-weight: 600; }
QLabel#seriesB { color: #ffba7a; font-weight: 600; }
QSplitter::handle { background: #343941; }
QToolTip { background: #30353d; color: #f5f6f7; border: 1px solid #59616e; padding: 6px; }
QCalendarWidget QToolButton { color: white; background: #262a30; padding: 4px; }
QCalendarWidget QToolButton:hover { background: #344c59; }
QScrollBar:vertical { background: #191b1f; width: 12px; }
QScrollBar:horizontal { background: #191b1f; height: 12px; }
QScrollBar::handle { background: #59616e; border-radius: 4px; min-width: 24px; min-height: 24px; }
QScrollBar::handle:hover { background: #88919f; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
"""
