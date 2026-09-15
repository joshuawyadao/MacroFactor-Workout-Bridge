"""Small reusable Qt line chart with explicit gaps and a zero-based shared scale."""

from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .desktop_theme import SERIES_COLORS, SURFACE
from .history import decimal_text


class TrendChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(135)
        self.values: tuple[tuple[Decimal | None, ...], ...] = ()
        self.labels: tuple[str, ...] = ()
        self.contexts: tuple[str, ...] = ()
        self.max_labels = 8
        self.setMouseTracking(True)
        self.setAccessibleName("Trend chart; exact values are available in the table")

    def set_series(self, values, labels=(), contexts=()) -> None:
        self.values = tuple(tuple(series) for series in values)
        self.labels = tuple(labels)
        self.contexts = tuple(contexts)
        self.setToolTip("")
        self.update()

    def context_bands(self):
        bands = []
        for index, label in enumerate(self.contexts):
            if bands and bands[-1][2] == label:
                start, _, name = bands[-1]
                bands[-1] = (start, index, name)
            else:
                bands.append((index, index, label))
        return tuple(bands)

    def mouseMoveEvent(self, event) -> None:
        values = self.plot_values()
        if self.labels and values:
            fraction = (event.position().x() - 52) / max(1, self.width() - 80)
            index = min(len(self.labels) - 1, max(0, round(fraction * (len(self.labels) - 1))))
            text = self.labels[index]
            if index < len(self.contexts):
                text += " · " + self.contexts[index]
            text += "\n" + ", ".join(decimal_text(series[index]) for series in values if index < len(series))
            self.setToolTip(text)
        super().mouseMoveEvent(event)

    def plot_values(self) -> tuple[tuple[Decimal | None, ...], ...]:
        return self.values

    def value_range(self) -> tuple[Decimal, Decimal]:
        available = [value for series in self.plot_values() for value in series if value is not None]
        return min([Decimal(0), *available]), max([Decimal(1), *available])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(QRectF(self.rect()), 9, 9)
        painter.setPen(self.palette().text().color())
        values = self.plot_values()
        if not any(value is not None for series in values for value in series):
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No logged values to plot")
            return
        minimum, maximum = self.value_range()
        span = maximum - minimum
        count = max(map(len, values))
        area = QRectF(52, 16, max(1, self.width() - 80), max(1, self.height() - 43))
        for band_index, (first, last, label) in enumerate(self.context_bands()):
            left = area.left() + max(0, first - 0.5) * area.width() / max(1, count - 1)
            right = area.left() + min(count - 1, last + 0.5) * area.width() / max(1, count - 1)
            if right - left < 8:
                continue
            if band_index % 2 == 0:
                painter.fillRect(QRectF(left, area.top(), right - left, area.height()), QColor("#252a31"))
            painter.setPen(self.palette().text().color())
            title = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, max(0, int(right - left - 8)))
            painter.drawText(QRectF(left + 4, 0, right - left - 8, 16), Qt.AlignmentFlag.AlignLeft, title)
        for fraction in (Decimal(0), Decimal("0.5"), Decimal(1)):
            y = area.bottom() - float(fraction) * area.height()
            painter.setPen(QPen(self.palette().mid().color(), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(self.palette().text().color())
            painter.drawText(QRectF(0, y - 9, 46, 18), Qt.AlignmentFlag.AlignRight,
                             decimal_text(minimum + span * fraction, places=1))
        # Leave enough width for dates, including in the three dashboard cards.
        label_limit = max(2, min(self.max_labels, int(area.width() / 90)))
        indexes = sorted({round(i * (count - 1) / (label_limit - 1)) for i in range(label_limit)})
        for index in indexes:
            x = area.left() + index * area.width() / max(1, count - 1)
            label = self.labels[index] if index < len(self.labels) else str(index + 1)
            painter.drawText(QRectF(x - 34, area.bottom() + 5, 68, 18),
                             Qt.AlignmentFlag.AlignCenter, label)
        for number, series in enumerate(values):
            color = QColor(SERIES_COLORS[number % len(SERIES_COLORS)])
            pen = QPen(color, 2)
            if number % 2:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(color)
            previous = None
            for index, value in enumerate(series):
                if value is None:
                    previous = None
                    continue
                point = QPointF(area.left() + index * area.width() / max(1, count - 1),
                                area.bottom() - float((value - minimum) / span) * area.height())
                if previous is not None:
                    painter.drawLine(previous, point)
                painter.drawEllipse(point, 3, 3)
                previous = point
