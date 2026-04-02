# visualizer.py
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QHBoxLayout, QVBoxLayout, QPushButton,
)

from poller import Poller, format_countdown, get_bar_color

BG = "#1a1a2e"
TEXT = "#ffffff"
GREY = "#555577"
TRACK = "#2d2d4e"
MUTED = "#aaaacc"
FOOTER_COLOR = "#666688"
WIDTH = 300
HEIGHT = 160
MARGIN = 16
RADIUS = 12
BAR_RADIUS = 9
BAR_HEIGHT = 18


class ColorBar(QWidget):
    """Rounded, color-coded horizontal progress bar."""

    def __init__(self) -> None:
        super().__init__()
        self._utilization: float = 0.0
        self._color: str = GREY
        self._active: bool = False  # False = show grey empty bar (loading/error)
        self.setFixedHeight(BAR_HEIGHT)

    def set_loading(self) -> None:
        self._active = False
        self._color = GREY
        self.update()

    def set_error(self) -> None:
        self._active = False
        self._color = GREY
        self.update()

    def set_value(self, utilization: float) -> None:
        self._active = True
        self._utilization = max(0.0, min(1.0, utilization))
        self._color = get_bar_color(self._utilization)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Track (background)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TRACK))
        painter.drawRoundedRect(rect, BAR_RADIUS, BAR_RADIUS)

        # Fill — clipped so right edge is square when < 100%
        if self._active and self._utilization > 0:
            fill_w = max(int(rect.width() * self._utilization), BAR_RADIUS * 2)
            painter.save()
            painter.setClipRect(QRect(0, 0, fill_w, rect.height()))
            painter.setBrush(QColor(self._color))
            painter.drawRoundedRect(rect, BAR_RADIUS, BAR_RADIUS)
            painter.restore()

        painter.end()
