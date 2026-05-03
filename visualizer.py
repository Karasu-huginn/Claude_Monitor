# visualizer.py
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSettings, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QHBoxLayout, QVBoxLayout, QPushButton,
)

from poller import Poller, format_countdown, get_bar_color, compute_time_utilization
from ping_poller import PingPoller
from session_scanner import SessionScanner

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


CONTEXT_BAR_HEIGHT = 12
CONTEXT_BAR_RADIUS = 6
COMPACT_THRESHOLD = 0.80


class ContextBar(QWidget):
    """Thinner progress bar with a compaction threshold mark."""

    def __init__(self) -> None:
        super().__init__()
        self._utilization: float = 0.0
        self._color: str = GREY
        self._active: bool = False
        self.setFixedHeight(CONTEXT_BAR_HEIGHT)

    def set_value(self, utilization: float) -> None:
        self._active = True
        self._utilization = max(0.0, min(1.0, utilization))
        self._color = get_bar_color(self._utilization)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TRACK))
        painter.drawRoundedRect(rect, CONTEXT_BAR_RADIUS, CONTEXT_BAR_RADIUS)

        # Fill
        if self._active and self._utilization > 0:
            fill_w = max(int(rect.width() * self._utilization), CONTEXT_BAR_RADIUS * 2)
            painter.save()
            painter.setClipRect(QRect(0, 0, fill_w, rect.height()))
            painter.setBrush(QColor(self._color))
            painter.drawRoundedRect(rect, CONTEXT_BAR_RADIUS, CONTEXT_BAR_RADIUS)
            painter.restore()

        # Threshold mark at 80%
        mark_x = int(rect.width() * COMPACT_THRESHOLD)
        painter.setPen(QColor(255, 255, 255, 80))
        painter.drawLine(mark_x, 1, mark_x, rect.height() - 1)

        painter.end()


class _ClickableLabel(QLabel):
    """QLabel that emits `clicked` on left mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        """Emit `clicked` for left-button presses, then defer to base behavior."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


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

        settings = QSettings("ClaudeMonitor", "Visualizer")
        self._context_expanded: bool = settings.value(
            "context_section_expanded", True, type=bool
        )
        self._context_session_count: int = 0

        self._setup_window()
        self._build_ui()
        self._position_top_right()
        self._start_timers()
        self._start_pollers()

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
        self.setFixedWidth(WIDTH)
        self.setMinimumHeight(HEIGHT)

    def paintEvent(self, _event) -> None:
        """Draw the dark rounded rectangle background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BG))
        painter.drawRoundedRect(self.rect(), RADIUS, RADIUS)
        painter.end()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(5)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("Claude Monitor")
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

        # --- Ping row ---
        ping_row = QHBoxLayout()
        ping_row.setSpacing(8)
        self._ping_dot = QLabel("●")
        self._ping_dot.setStyleSheet(
            f"color: {GREY}; font-size: 10px; background: transparent;"
        )
        self._ping_status = QLabel("---")
        self._ping_status.setStyleSheet(
            f"color: {GREY}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self._ping_latency = QLabel("")
        self._ping_latency.setStyleSheet(
            f"color: {GREY}; font-size: 9px; background: transparent;"
        )
        ping_row.addWidget(self._ping_dot)
        ping_row.addWidget(self._ping_status)
        ping_row.addWidget(self._ping_latency)
        ping_row.addStretch()
        root.addLayout(ping_row)

        # --- Tokens bar ---
        self._tokens_label = QLabel(f"Tokens — {self.SPINNER_FRAMES[0]}")
        self._tokens_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
        root.addWidget(self._tokens_label)
        self._bar = ColorBar()
        root.addWidget(self._bar)

        # --- Session time bar ---
        self._time_label = QLabel("Session time — …")
        self._time_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
        root.addWidget(self._time_label)
        self._time_bar = ColorBar()
        root.addWidget(self._time_bar)

        # --- Context section (user-collapsable; auto-hides when no sessions) ---
        self._context_container = QWidget()
        self._context_container.setStyleSheet("background: transparent;")
        context_outer_layout = QVBoxLayout(self._context_container)
        context_outer_layout.setContentsMargins(0, 0, 0, 0)
        context_outer_layout.setSpacing(4)

        self._context_header = _ClickableLabel("")
        self._context_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._context_header.setStyleSheet(
            f"color: {GREY}; font-size: 9px; background: transparent;"
        )
        self._context_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._context_header.clicked.connect(self._toggle_context_section)
        context_outer_layout.addWidget(self._context_header)

        self._context_rows_container = QWidget()
        self._context_rows_container.setStyleSheet("background: transparent;")
        self._context_rows_layout = QVBoxLayout(self._context_rows_container)
        self._context_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._context_rows_layout.setSpacing(4)
        context_outer_layout.addWidget(self._context_rows_container)

        self._context_container.setVisible(False)
        root.addWidget(self._context_container)

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

    def _position_top_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - WIDTH - MARGIN, geo.top() + 32)

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
        self._tokens_label.setText(f"Tokens — {self.SPINNER_FRAMES[self._spinner_idx]}")

    def _update_countdown(self) -> None:
        if self._reset_at is not None:
            self._time_label.setText(
                f"Session time — resets in {format_countdown(self._reset_at)}"
            )
            self._time_bar.set_value(compute_time_utilization(self._reset_at))

    def _toggle_dot(self) -> None:
        self._dot_visible = not self._dot_visible
        self._dot_label.setVisible(self._dot_visible)

    # ------------------------------------------------------------------
    # Poller
    # ------------------------------------------------------------------

    def _start_pollers(self) -> None:
        self._poller = Poller()
        self._poller.data_ready.connect(self._on_data)
        self._poller.error.connect(self._on_error)
        self._poller.start()

        self._ping_poller = PingPoller()
        self._ping_poller.ping_ready.connect(self._on_ping)
        self._ping_poller.start()

        self._session_scanner = SessionScanner()
        self._session_scanner.sessions_ready.connect(self._on_sessions)
        self._session_scanner.start()

    def _on_data(self, utilization: float, reset_at: object) -> None:
        self._is_loading = False
        self._reset_at = reset_at  # type: ignore[assignment]
        pct = int(utilization * 100)

        self._bar.set_value(utilization)
        self._tokens_label.setText(f"Tokens — {pct}% used")
        self._tokens_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
        self._dot_label.setStyleSheet(f"color: #00b894; font-size: 9px; background: transparent;")
        self._updated_label.setText(f"updated {datetime.now().strftime('%H:%M:%S')}")

    def _on_error(self, msg: str) -> None:
        self._dot_label.setStyleSheet(f"color: #e17055; font-size: 9px; background: transparent;")

        if msg == "offline":
            self._is_loading = False
            self._tokens_label.setText("Tokens — offline")
            self._tokens_label.setStyleSheet("color: #e17055; font-size: 9px; background: transparent;")
            # _time_bar and _time_label continue updating via _update_countdown (reset_at preserved)
        elif msg == "rate limited":
            self._is_loading = False
            self._tokens_label.setText("Tokens — rate limited")
            self._tokens_label.setStyleSheet("color: #fdcb6e; font-size: 9px; background: transparent;")
            # _time_bar and _time_label continue updating via _update_countdown (reset_at preserved)
        else:
            # Auth error or unknown — reset the whole display
            self._is_loading = False
            self._bar.set_error()
            self._time_bar.set_error()
            self._reset_at = None
            self._tokens_label.setText("")
            self._tokens_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
            self._time_label.setText("")

    def _on_ping(self, online: bool, latency: object) -> None:
        if online:
            color = "#00b894"
            text = "ONLINE"
            ms = f"{latency:.0f}ms" if latency is not None else ""
        else:
            color = "#d63031"
            text = "OFFLINE"
            ms = "---"
        self._ping_dot.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )
        self._ping_status.setText(text)
        self._ping_status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self._ping_latency.setText(ms)

    def _toggle_context_section(self) -> None:
        """Flip the context section's expanded state and persist the choice."""
        self._context_expanded = not self._context_expanded
        QSettings("ClaudeMonitor", "Visualizer").setValue(
            "context_section_expanded", self._context_expanded
        )
        self._apply_context_expanded_state()

    def _apply_context_expanded_state(self) -> None:
        """Sync header chevron and rows visibility with `_context_expanded`."""
        self._refresh_context_header()
        self._context_rows_container.setVisible(self._context_expanded)
        self.adjustSize()

    def _refresh_context_header(self) -> None:
        """Rewrite the context header text from current chevron + session count."""
        chevron = "▾" if self._context_expanded else "▸"
        count = self._context_session_count
        plural = "S" if count != 1 else ""
        self._context_header.setText(
            f"{chevron} CONTEXT · {count} SESSION{plural}"
        )

    def _on_sessions(self, sessions: list) -> None:
        """Rebuild per-session rows; auto-hide if empty; honor expanded preference."""
        # Clear existing per-session row widgets (header is persistent and skipped)
        while self._context_rows_layout.count():
            item = self._context_rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not sessions:
            self._context_container.setVisible(False)
            self.adjustSize()
            return

        self._context_session_count = len(sessions)

        # Per-session rows
        for project_name, model, fill_pct, is_waiting in sessions:
            # Strip model prefix for display (e.g. "claude-opus-4-6" -> "opus")
            short_model = model.replace("claude-", "").split("-")[0]
            pct_text = f"{int(fill_pct * 100)}%"
            label_color = "#00b894" if is_waiting else MUTED

            label_row = QHBoxLayout()
            name_label = QLabel(f"{project_name} · {short_model}")
            name_label.setStyleSheet(
                f"color: {label_color}; font-size: 10px; background: transparent;"
            )
            pct_label = QLabel(pct_text)
            pct_label.setStyleSheet(
                f"color: {label_color}; font-size: 10px; background: transparent;"
            )
            label_row.addWidget(name_label)
            label_row.addStretch()
            label_row.addWidget(pct_label)

            label_widget = QWidget()
            label_widget.setStyleSheet("background: transparent;")
            label_widget.setLayout(label_row)
            self._context_rows_layout.addWidget(label_widget)

            bar = ContextBar()
            bar.set_value(fill_pct)
            self._context_rows_layout.addWidget(bar)

        self._context_container.setVisible(True)
        self._apply_context_expanded_state()

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
        self._ping_poller.stop()
        self._ping_poller.wait(2000)
        self._session_scanner.stop()
        self._session_scanner.wait(2000)
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = VisualizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
