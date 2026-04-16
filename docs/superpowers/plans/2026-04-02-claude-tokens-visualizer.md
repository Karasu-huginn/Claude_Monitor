# Claude Tokens Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a frameless always-on-top PyQt6 widget that polls `https://claude.ai/api/oauth/usage` every 60 s and displays the current 5-hour session utilization with a color-coded progress bar and live countdown.

**Architecture:** Two files — `poller.py` holds the pure utility functions and the `QThread` poller; `visualizer.py` holds the UI (`ColorBar`, `VisualizerWindow`) and the `main()` entry point. Splitting by responsibility makes the pure functions testable without a QApplication. The user runs `python visualizer.py`.

**Tech Stack:** Python 3.10+, PyQt6, requests, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Pinned deps |
| `poller.py` | `read_credentials`, `parse_response`, `format_countdown`, `get_bar_color`, `Poller(QThread)` |
| `visualizer.py` | `ColorBar(QWidget)`, `VisualizerWindow(QWidget)`, `main()` |
| `tests/__init__.py` | empty |
| `tests/test_poller.py` | Unit tests for all pure functions in `poller.py` |

---

## Task 1: Project setup

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write requirements.txt**

```
PyQt6>=6.4.0
requests>=2.28.0
pytest>=7.0.0
```

- [ ] **Step 2: Create empty tests package**

```bash
touch tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all three packages install without errors.

- [ ] **Step 4: Commit**

```bash
git init
git add requirements.txt tests/__init__.py
git commit -m "chore: project setup"
```

---

## Task 2: Failing tests for pure utility functions

**Files:**
- Create: `tests/test_poller.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_poller.py
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from poller import read_credentials, parse_response, format_countdown, get_bar_color


# --- read_credentials ---

def test_read_credentials_returns_token(tmp_path):
    p = tmp_path / ".credentials.json"
    p.write_text(json.dumps({"claudeAiOauth": {"accessToken": "sk-ant-oat01-test"}}))
    assert read_credentials(p) == "sk-ant-oat01-test"

def test_read_credentials_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        read_credentials(Path("/nonexistent/.credentials.json"))

def test_read_credentials_raises_on_wrong_schema(tmp_path):
    p = tmp_path / ".credentials.json"
    p.write_text('{"other": {}}')
    with pytest.raises(KeyError):
        read_credentials(p)


# --- parse_response ---

def test_parse_response_returns_utilization_and_reset_at():
    data = {"five_hour": {"utilization": 0.73, "reset_at": "2026-04-02T16:00:00Z"}}
    utilization, reset_at = parse_response(data)
    assert utilization == 0.73
    assert reset_at == datetime(2026, 4, 2, 16, 0, 0, tzinfo=timezone.utc)

def test_parse_response_raises_on_missing_five_hour():
    with pytest.raises(KeyError):
        parse_response({})


# --- format_countdown ---

def test_format_countdown_hours_and_minutes():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=2, minutes=14, seconds=30)
    assert format_countdown(reset_at) == "2h 14m"

def test_format_countdown_minutes_only():
    reset_at = datetime.now(timezone.utc) + timedelta(minutes=7, seconds=45)
    assert format_countdown(reset_at) == "7m"

def test_format_countdown_expired_returns_now():
    reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert format_countdown(reset_at) == "now"


# --- get_bar_color ---

def test_get_bar_color_green_below_60():
    assert get_bar_color(0.0) == "#00b894"
    assert get_bar_color(0.59) == "#00b894"

def test_get_bar_color_yellow_60_to_80():
    assert get_bar_color(0.6) == "#fdcb6e"
    assert get_bar_color(0.79) == "#fdcb6e"

def test_get_bar_color_orange_80_to_90():
    assert get_bar_color(0.8) == "#e17055"
    assert get_bar_color(0.89) == "#e17055"

def test_get_bar_color_red_90_and_above():
    assert get_bar_color(0.9) == "#d63031"
    assert get_bar_color(1.0) == "#d63031"
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
pytest tests/test_poller.py -v
```

Expected: `ImportError: No module named 'poller'` or similar — no test should pass yet.

- [ ] **Step 3: Commit**

```bash
git add tests/test_poller.py
git commit -m "test: failing tests for pure utility functions"
```

---

## Task 3: Implement pure utility functions

**Files:**
- Create: `poller.py`

- [ ] **Step 1: Write poller.py with only the four pure functions**

```python
# poller.py
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://claude.ai/api/oauth/usage"
POLL_INTERVAL = 60      # seconds between normal polls
BACKOFF_INTERVAL = 300  # seconds to wait after a 429


def read_credentials(path: Path = CREDENTIALS_PATH) -> str:
    """Return the OAuth access token from the credentials file."""
    with open(path) as f:
        data = json.load(f)
    return data["claudeAiOauth"]["accessToken"]


def parse_response(data: dict) -> Tuple[float, datetime]:
    """Return (utilization 0–1, reset_at UTC datetime) from the API response dict."""
    five_hour = data["five_hour"]
    utilization = float(five_hour["utilization"])
    reset_at = datetime.fromisoformat(five_hour["reset_at"].replace("Z", "+00:00"))
    return utilization, reset_at


def format_countdown(reset_at: datetime) -> str:
    """Format time remaining until reset_at as 'Xh Ym', 'Xm', or 'now'."""
    remaining = (reset_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return "now"
    total_minutes = int(remaining // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_bar_color(utilization: float) -> str:
    """Return the hex progress-bar color for the given utilization (0–1)."""
    if utilization < 0.6:
        return "#00b894"
    if utilization < 0.8:
        return "#fdcb6e"
    if utilization < 0.9:
        return "#e17055"
    return "#d63031"


class Poller(QThread):
    pass  # implemented in Task 4
```

- [ ] **Step 2: Run tests — verify they all pass**

```bash
pytest tests/test_poller.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add poller.py
git commit -m "feat: pure utility functions for credential reading and response parsing"
```

---

## Task 4: Poller QThread

**Files:**
- Modify: `poller.py` — replace `class Poller(QThread): pass` with full implementation

- [ ] **Step 1: Replace the Poller stub**

Replace the `class Poller(QThread): pass` line in `poller.py` with:

```python
class Poller(QThread):
    """Background thread that polls the usage API and emits signals."""

    # Emitted on success: (utilization float, reset_at datetime)
    data_ready = pyqtSignal(float, object)
    # Emitted on any error: short human-readable message string
    error = pyqtSignal(str)

    def __init__(self, credentials_path: Path = CREDENTIALS_PATH) -> None:
        super().__init__()
        self._credentials_path = credentials_path
        self._running = True

    def run(self) -> None:
        while self._running:
            sleep_seconds = POLL_INTERVAL
            try:
                token = read_credentials(self._credentials_path)
                resp = requests.get(
                    USAGE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "User-Agent": "claude-tokens-visualizer/1.0",
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    utilization, reset_at = parse_response(resp.json())
                    self.data_ready.emit(utilization, reset_at)
                elif resp.status_code == 429:
                    sleep_seconds = BACKOFF_INTERVAL
                    self.error.emit("rate limited")
                elif resp.status_code == 401:
                    self.error.emit("auth error — reopen Claude Code")
                else:
                    self.error.emit(f"HTTP {resp.status_code}")
            except FileNotFoundError:
                self.error.emit("auth error — reopen Claude Code")
            except requests.RequestException:
                self.error.emit("offline")
            except Exception as e:
                self.error.emit(str(e))

            # Sleep in 1-second ticks so stop() is responsive
            for _ in range(sleep_seconds):
                if not self._running:
                    return
                time.sleep(1)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```bash
pytest tests/test_poller.py -v
```

Expected: all 11 tests still PASS.

- [ ] **Step 3: Commit**

```bash
git add poller.py
git commit -m "feat: Poller QThread polls usage API and emits data_ready / error signals"
```

---

## Task 5: ColorBar custom widget

**Files:**
- Create: `visualizer.py`

- [ ] **Step 1: Write visualizer.py with only ColorBar**

```python
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
```

- [ ] **Step 2: Verify imports parse cleanly**

```bash
python -c "from visualizer import ColorBar; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add visualizer.py
git commit -m "feat: ColorBar custom widget with rounded color-coded progress bar"
```

---

## Task 6: VisualizerWindow

**Files:**
- Modify: `visualizer.py` — append `VisualizerWindow` class after `ColorBar`

- [ ] **Step 1: Append VisualizerWindow to visualizer.py**

Add the following class after `ColorBar` (before the end of the file):

```python
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
            # Keep last known percentage; only footer changes
            self._used_label.setText("offline")
            self._used_label.setStyleSheet("color: #e17055; font-size: 11px; background: transparent;")
        elif msg == "rate limited":
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
```

- [ ] **Step 2: Verify imports parse cleanly**

```bash
python -c "from visualizer import VisualizerWindow; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add visualizer.py
git commit -m "feat: VisualizerWindow with full layout, drag, error states, spinner"
```

---

## Task 7: Entry point and smoke test

**Files:**
- Modify: `visualizer.py` — append `main()` and `__main__` block

- [ ] **Step 1: Append main() to visualizer.py**

Add at the very end of `visualizer.py`:

```python
def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = VisualizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the widget**

```bash
python visualizer.py
```

Expected:
- A small dark panel appears in the bottom-right corner of the screen
- The big label shows a spinning braille character (loading state) for up to 60 s
- After the first poll completes, it shows a percentage + colored progress bar
- Dragging the window repositions it
- Right-clicking quits; clicking `×` quits

- [ ] **Step 3: Run unit tests one final time**

```bash
pytest tests/test_poller.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add visualizer.py
git commit -m "feat: main entry point — run with python visualizer.py"
```

---

## Self-Review Checklist

| Spec requirement | Covered by |
|---|---|
| Poll `https://claude.ai/api/oauth/usage` | Task 4, `Poller.run()` |
| Auth via `~/.claude/.credentials.json` → `claudeAiOauth.accessToken` | Task 3, `read_credentials()` |
| 60 s poll interval, 5 min backoff on 429 | Task 4, `POLL_INTERVAL` / `BACKOFF_INTERVAL` |
| Frameless always-on-top window | Task 6, `_setup_window()` |
| Default position: bottom-right, 16 px margin | Task 6, `_position_bottom_right()` |
| Draggable | Task 6, `mousePressEvent` / `mouseMoveEvent` |
| Close via × button or right-click | Task 6, `close_btn.clicked` / `contextMenuEvent` |
| Color-coded rounded progress bar | Task 5, `ColorBar` |
| Colors: green/yellow/orange/red at 60/80/90% | Task 3, `get_bar_color()` |
| Big percentage label, color matches bar | Task 6, `_on_data()` |
| "resets in Xh Ym" live countdown | Task 6, `_update_countdown()` |
| Pulsing dot in footer | Task 6, `_toggle_dot()` |
| Last updated timestamp | Task 6, `_on_data()` |
| Loading spinner before first data | Task 6, `_tick_spinner()` |
| Auth error → grey bar + message | Task 6, `_on_error()` |
| Network error → "offline" in orange | Task 6, `_on_error()` |
| Rate limit → "rate limited" + backoff | Tasks 4 & 6 |
