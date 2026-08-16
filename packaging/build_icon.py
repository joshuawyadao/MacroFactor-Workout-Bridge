from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen


FILES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def render_icon(path: Path, size: int) -> None:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 1024

    background = QPainterPath()
    background.addRoundedRect(QRectF(64 * scale, 64 * scale, 896 * scale, 896 * scale), 210 * scale, 210 * scale)
    painter.fillPath(background, QColor("#1769e0"))

    pen = QPen(QColor("#ffffff"), 70 * scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QPointF(250 * scale, 512 * scale), QPointF(774 * scale, 512 * scale))
    painter.drawLine(QPointF(304 * scale, 390 * scale), QPointF(304 * scale, 634 * scale))
    painter.drawLine(QPointF(720 * scale, 390 * scale), QPointF(720 * scale, 634 * scale))

    painter.setPen(QPen(QColor("#bfe0ff"), 54 * scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(512 * scale, 285 * scale), QPointF(512 * scale, 394 * scale))
    painter.drawLine(QPointF(512 * scale, 630 * scale), QPointF(512 * scale, 739 * scale))
    painter.setPen(QPen(QColor("#bfe0ff"), 44 * scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(455 * scale, 340 * scale), QPointF(512 * scale, 397 * scale))
    painter.drawLine(QPointF(569 * scale, 340 * scale), QPointF(512 * scale, 397 * scale))
    painter.drawLine(QPointF(455 * scale, 684 * scale), QPointF(512 * scale, 627 * scale))
    painter.drawLine(QPointF(569 * scale, 684 * scale), QPointF(512 * scale, 627 * scale))
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Could not create {path}")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_icon.py OUTPUT.iconset")
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    for filename, size in FILES.items():
        render_icon(destination / filename, size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
