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
        """Show the empty grey bar in the loading state (before first data arrives)."""
        self._active = False
        self._color = GREY
        self.update()

    def set_error(self) -> None:
        """Show the empty grey bar in an error state. Visually identical to loading by design."""
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


class VisualizerWindow(QWidget):
    """Frameless, always-on-top dashboard panel."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos: Optional[QPoint] = None
        self._reset_at: Optional[datetime] = None
        self._spinner_idx: int = 0
        self._dot_visible: bool = True
        self._is_loading: bool = True

        self._setup_window()
        self._build_ui()
        self._position_bottom_right()
        self._start_timers()
        self._start_poller()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # excluded from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)

    def paintEvent(self, _event) -> None:
        """Draw the dark rounded rectangle background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BG))
        painter.drawRoundedRect(self.rect(), RADIUS, RADIUS)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(5)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("Claude Code · 5h Session")
        title.setStyleSheet(f"color: {TEXT}; font-size: 11px; font-weight: bold; background: transparent;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 18px; padding: 0;"
        )
        close_btn.clicked.connect(QApplication.quit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        root.addLayout(header)

        # --- Progress bar ---
        self._bar = ColorBar()
        root.addWidget(self._bar)

        # --- Big percentage / spinner ---
        self._pct_label = QLabel("⠋")
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pct_font = QFont()
        pct_font.setPointSize(34)
        pct_font.setBold(True)
        self._pct_label.setFont(pct_font)
        self._pct_label.setStyleSheet(f"color: {GREY}; background: transparent;")
        root.addWidget(self._pct_label)

        # --- Subtitle row ---
        subtitle = QHBoxLayout()
        self._used_label = QLabel("Loading…")
        self._used_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        self._countdown_label = QLabel("")
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._countdown_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        subtitle.addWidget(self._used_label)
        subtitle.addStretch()
        subtitle.addWidget(self._countdown_label)
        root.addLayout(subtitle)

        # --- Footer ---
        footer = QHBoxLayout()
        self._updated_label = QLabel("")
        self._updated_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
        self._dot_label = QLabel("●")
        self._dot_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._dot_label.setStyleSheet(f"color: {GREY}; font-size: 9px; background: transparent;")
        footer.addWidget(self._updated_label)
        footer.addStretch()
        footer.addWidget(self._dot_label)
        root.addLayout(footer)

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - WIDTH - MARGIN, screen.bottom() - HEIGHT - MARGIN)

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _start_timers(self) -> None:
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._tick_spinner)
        self._spinner_timer.start(100)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._toggle_dot)
        self._dot_timer.start(800)

    def _tick_spinner(self) -> None:
        if not self._is_loading:
            return
        self._spinner_idx = (self._spinner_idx + 1) % len(self.SPINNER_FRAMES)
        self._pct_label.setText(self.SPINNER_FRAMES[self._spinner_idx])

    def _update_countdown(self) -> None:
        if self._reset_at is not None:
            self._countdown_label.setText(f"resets in {format_countdown(self._reset_at)}")

    def _toggle_dot(self) -> None:
        self._dot_visible = not self._dot_visible
        self._dot_label.setVisible(self._dot_visible)

    # ------------------------------------------------------------------
    # Poller
    # ------------------------------------------------------------------

    def _start_poller(self) -> None:
        self._poller = Poller()
        self._poller.data_ready.connect(self._on_data)
        self._poller.error.connect(self._on_error)
        self._poller.start()

    def _on_data(self, utilization: float, reset_at: object) -> None:
        self._is_loading = False
        self._reset_at = reset_at  # type: ignore[assignment]
        color = get_bar_color(utilization)
        pct = int(utilization * 100)

        self._bar.set_value(utilization)
        self._pct_label.setText(f"{pct}%")
        self._pct_label.setStyleSheet(f"color: {color}; background: transparent;")
        self._used_label.setText(f"{pct}% used")
        self._used_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        self._dot_label.setStyleSheet(f"color: #00b894; font-size: 9px; background: transparent;")
        self._updated_label.setText(f"updated {datetime.now().strftime('%H:%M:%S')}")

    def _on_error(self, msg: str) -> None:
        self._bar.set_error()
        self._dot_label.setStyleSheet(f"color: #e17055; font-size: 9px; background: transparent;")

        if msg == "offline":
            self._is_loading = False
            # Keep last known percentage; only footer changes
            self._used_label.setText("offline")
            self._used_label.setStyleSheet("color: #e17055; font-size: 11px; background: transparent;")
        elif msg == "rate limited":
            self._is_loading = False
            self._used_label.setText("rate limited — retrying in 5m")
            self._used_label.setStyleSheet("color: #fdcb6e; font-size: 11px; background: transparent;")
        else:
            # Auth error or unknown
            self._is_loading = False
            self._pct_label.setText("—")
            self._pct_label.setStyleSheet(f"color: {GREY}; background: transparent;")
            self._used_label.setText(msg)
            self._used_label.setStyleSheet("color: #e17055; font-size: 11px; background: transparent;")
            self._countdown_label.setText("")

    # ------------------------------------------------------------------
    # Mouse: drag + right-click to quit
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_pos = None

    def contextMenuEvent(self, _event) -> None:
        QApplication.quit()

    def closeEvent(self, event) -> None:
        self._poller.stop()
        self._poller.wait(2000)
        event.accept()
