"""Progressively disclose secondary history views without removing navigation."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QTabWidget, QToolButton


class HistoryTabs(QTabWidget):
    def configure_secondary_views(self, first=3):
        self.secondary_actions = {}
        self.more = QToolButton()
        self.more.setText("More")
        self.more.setAccessibleName("More history views")
        self.more.setObjectName("quietButton")
        self.more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self.more)
        for index in range(first, self.count()):
            action = self.more_menu.addAction(self.tabText(index))
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, i=index: self.setCurrentIndex(i))
            self.secondary_actions[index] = action
            self.setTabVisible(index, False)
        self.more.setMenu(self.more_menu)
        self.setCornerWidget(self.more, Qt.Corner.TopRightCorner)
        self.currentChanged.connect(self._sync_secondary)

    def setCurrentIndex(self, index):
        if index in getattr(self, "secondary_actions", {}):
            self.setTabVisible(index, True)
        super().setCurrentIndex(index)

    def setCurrentWidget(self, widget):
        self.setCurrentIndex(self.indexOf(widget))

    def _sync_secondary(self, current):
        for index, action in self.secondary_actions.items():
            self.setTabVisible(index, index == current)
            action.setChecked(index == current)
