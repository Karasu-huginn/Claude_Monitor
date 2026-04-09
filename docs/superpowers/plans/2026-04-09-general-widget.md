# General Widget Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Claude tokens visualizer into "Claude Monitor" — adding a ping monitor row and per-session context compaction bars.

**Architecture:** Two new `QThread` pollers (`PingPoller`, `SessionScanner`) feed data into the existing `VisualizerWindow` via signals. The ping row is always visible. The context section auto-collapses when no Claude Code sessions are detected. A new `ContextBar` widget extends `ColorBar` with a threshold mark.

**Tech Stack:** PyQt6 (UI + threading), subprocess (OS ping), stdlib json/pathlib (JSONL file reads)

---

### Task 1: Ping function and tests

**Files:**
- Create: `ping_poller.py`
- Create: `tests/test_ping_poller.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ping_poller.py
import re
import pytest

from ping_poller import LATENCY_RE, ping


def test_regex_windows_normal():
    output = "Reply from 8.8.8.8: bytes=32 time=12ms TTL=118"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 12.0


def test_regex_windows_sub_1ms():
    output = "Reply from 8.8.8.8: bytes=32 time<1ms TTL=118"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 1.0


def test_regex_linux():
    output = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.3 ms"
    match = LATENCY_RE.search(output)
    assert match is not None
    assert float(match.group(1)) == 12.3


def test_regex_no_match():
    output = "Request timed out."
    match = LATENCY_RE.search(output)
    assert match is None


def test_ping_returns_tuple():
    ok, ms = ping()
    assert isinstance(ok, bool)
    if ok:
        assert isinstance(ms, float)
    else:
        assert ms is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ping_poller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ping_poller'`

- [ ] **Step 3: Write the ping function**

```python
# ping_poller.py
from __future__ import annotations

import platform
import re
import subprocess
from typing import Tuple, Optional

TARGET = "8.8.8.8"
TIMEOUT = 1

LATENCY_RE = re.compile(r'time[=<](\d+\.?\d*)\s*ms', re.IGNORECASE)


def ping(target: str = TARGET, timeout: int = TIMEOUT) -> Tuple[bool, Optional[float]]:
    """Ping target once. Return (success, latency_ms_or_None)."""
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), target]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), target]

    try:
        kwargs: dict = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout + 1,
        )
        if system == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
        if result.returncode != 0:
            return False, None
        match = LATENCY_RE.search(result.stdout or "")
        ms = float(match.group(1)) if match else None
        return True, ms
    except Exception:
        return False, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ping_poller.py -v`
Expected: all 5 PASS

- [ ] **Step 5: Commit**

```bash
git add ping_poller.py tests/test_ping_poller.py
git commit -m "feat: add ping function with platform-aware OS ping"
```

---

### Task 2: PingPoller QThread

**Files:**
- Modify: `ping_poller.py`

- [ ] **Step 1: Add PingPoller class**

Append to `ping_poller.py`:

```python
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

PING_INTERVAL = 2  # seconds between pings


class PingPoller(QThread):
    """Background thread that pings and emits results."""

    ping_ready = pyqtSignal(bool, object)  # (online, latency_ms_or_None)

    def __init__(self, target: str = TARGET, interval: int = PING_INTERVAL) -> None:
        super().__init__()
        self._target = target
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            ok, ms = ping(self._target)
            self.ping_ready.emit(ok, ms)
            for _ in range(self._interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
```

- [ ] **Step 2: Verify file compiles**

Run: `python -c "from ping_poller import PingPoller; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ping_poller.py
git commit -m "feat: add PingPoller QThread — pings every 2s, emits signal"
```

---

### Task 3: Session scanner utility functions and tests

**Files:**
- Create: `session_scanner.py`
- Create: `tests/test_session_scanner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_session_scanner.py
import json
import os
import pytest
from pathlib import Path

from session_scanner import (
    is_pid_alive,
    encode_cwd,
    scan_sessions,
    read_context_usage,
    compute_fill_pct,
    MODEL_CONTEXT_LIMITS,
)


# --- is_pid_alive ---

def test_current_pid_is_alive():
    assert is_pid_alive(os.getpid()) is True


def test_dead_pid_is_not_alive():
    # PID 99999999 is extremely unlikely to be alive
    assert is_pid_alive(99999999) is False


# --- encode_cwd ---

def test_encode_cwd_windows_path():
    cwd = "C:\\Users\\erwan\\my_project"
    assert encode_cwd(cwd) == "C--Users-erwan-my-project"


def test_encode_cwd_unix_path():
    cwd = "/home/erwan/my_project"
    assert encode_cwd(cwd) == "-home-erwan-my-project"


# --- scan_sessions ---

def test_scan_sessions_finds_alive_sessions(tmp_path):
    pid = os.getpid()
    session_file = tmp_path / f"{pid}.json"
    session_file.write_text(json.dumps({
        "pid": pid,
        "sessionId": "abc-123",
        "cwd": "C:\\Users\\erwan\\my_project",
        "startedAt": 1775730657047,
        "kind": "interactive",
    }))
    sessions = scan_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0] == (pid, "abc-123", "C:\\Users\\erwan\\my_project")


def test_scan_sessions_skips_dead_pids(tmp_path):
    session_file = tmp_path / "99999999.json"
    session_file.write_text(json.dumps({
        "pid": 99999999,
        "sessionId": "dead-session",
        "cwd": "/tmp/dead",
        "startedAt": 1000,
        "kind": "interactive",
    }))
    sessions = scan_sessions(tmp_path)
    assert len(sessions) == 0


def test_scan_sessions_empty_dir(tmp_path):
    sessions = scan_sessions(tmp_path)
    assert sessions == []


def test_scan_sessions_nonexistent_dir(tmp_path):
    sessions = scan_sessions(tmp_path / "no_such_dir")
    assert sessions == []


# --- read_context_usage ---

def test_read_context_usage_returns_model_and_tokens(tmp_path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    # Write a non-assistant line (no usage) then an assistant line (with usage)
    lines = [
        json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}),
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "role": "assistant",
                "usage": {
                    "input_tokens": 1,
                    "cache_creation_input_tokens": 500,
                    "cache_read_input_tokens": 79000,
                    "output_tokens": 200,
                },
            },
        }),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n")

    model, tokens = read_context_usage(
        projects_dir, "C:\\Users\\erwan\\my_project", "abc-123"
    )
    assert model == "claude-opus-4-6"
    assert tokens == 79501  # 1 + 500 + 79000


def test_read_context_usage_returns_none_for_missing_file(tmp_path):
    result = read_context_usage(tmp_path, "C:\\no\\such", "bad-id")
    assert result is None


def test_read_context_usage_returns_none_for_no_usage_entries(tmp_path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    jsonl_file.write_text(json.dumps({"type": "user", "message": {"role": "user"}}) + "\n")

    result = read_context_usage(
        projects_dir, "C:\\Users\\erwan\\my_project", "abc-123"
    )
    assert result is None


# --- compute_fill_pct ---

def test_compute_fill_pct_known_model():
    # 80000 / 200000 = 0.4
    assert compute_fill_pct("claude-opus-4-6", 80000) == pytest.approx(0.4)


def test_compute_fill_pct_unknown_model_uses_default():
    # Unknown model falls back to 200000
    assert compute_fill_pct("claude-unknown-99", 100000) == pytest.approx(0.5)


def test_compute_fill_pct_clamps_at_1():
    assert compute_fill_pct("claude-sonnet-4-6", 999999) == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'session_scanner'`

- [ ] **Step 3: Write the session scanner utility functions**

```python
# session_scanner.py
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
from pathlib import Path
from typing import List, Tuple, Optional

CLAUDE_DIR = Path.home() / ".claude"
SESSIONS_DIR = CLAUDE_DIR / "sessions"
PROJECTS_DIR = CLAUDE_DIR / "projects"

MODEL_CONTEXT_LIMITS = {
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
}
DEFAULT_CONTEXT_LIMIT = 200_000


def is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if platform.system() == "Windows":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle == 0:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def encode_cwd(cwd: str) -> str:
    """Encode a cwd path to the directory name format used by Claude Code.

    Replaces path separators, colons, and underscores with dashes.
    E.g. 'C:\\Users\\erwan\\my_project' -> 'C--Users-erwan-my-project'
    """
    return re.sub(r'[\\/:_]', '-', cwd).rstrip('-')


def scan_sessions(
    sessions_dir: Path = SESSIONS_DIR,
) -> List[Tuple[int, str, str]]:
    """Return list of (pid, session_id, cwd) for alive Claude Code sessions."""
    if not sessions_dir.is_dir():
        return []

    results: List[Tuple[int, str, str]] = []
    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            pid = data["pid"]
            if is_pid_alive(pid):
                results.append((pid, data["sessionId"], data["cwd"]))
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return results


def read_context_usage(
    projects_dir: Path,
    cwd: str,
    session_id: str,
) -> Optional[Tuple[str, int]]:
    """Read the last assistant message from a session JSONL file.

    Returns (model, total_input_tokens) or None if unavailable.
    total_input_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
    """
    encoded = encode_cwd(cwd)
    jsonl_path = projects_dir / encoded / f"{session_id}.jsonl"
    if not jsonl_path.is_file():
        return None

    try:
        # Read last 64KB — enough to find the last assistant message
        file_size = jsonl_path.stat().st_size
        read_size = min(file_size, 65536)
        with open(jsonl_path, "r", encoding="utf-8") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
                f.readline()  # skip partial line
            lines = f.readlines()
    except OSError:
        return None

    # Scan backwards for last entry with usage data
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message", {})
        usage = msg.get("usage")
        model = msg.get("model")
        if usage and model:
            total = (
                usage.get("input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0)
                + usage.get("cache_read_input_tokens", 0)
            )
            return model, total

    return None


def compute_fill_pct(model: str, total_input_tokens: int) -> float:
    """Return context fill fraction (0–1) for the given model and token count."""
    limit = MODEL_CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)
    return min(1.0, total_input_tokens / limit)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_scanner.py -v`
Expected: all 11 PASS

- [ ] **Step 5: Commit**

```bash
git add session_scanner.py tests/test_session_scanner.py
git commit -m "feat: add session scanner — detects active sessions, reads context usage from JSONL"
```

---

### Task 4: SessionScanner QThread

**Files:**
- Modify: `session_scanner.py`

- [ ] **Step 1: Add SessionScanner class**

Append to `session_scanner.py`:

```python
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

SCAN_INTERVAL = 15  # seconds between scans


class SessionScanner(QThread):
    """Background thread that scans for active Claude Code sessions."""

    # Emitted each cycle: list of (project_name, model, fill_pct) tuples
    sessions_ready = pyqtSignal(list)

    def __init__(
        self,
        sessions_dir: Path = SESSIONS_DIR,
        projects_dir: Path = PROJECTS_DIR,
        interval: int = SCAN_INTERVAL,
    ) -> None:
        super().__init__()
        self._sessions_dir = sessions_dir
        self._projects_dir = projects_dir
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            results: List[Tuple[str, str, float]] = []
            for _pid, session_id, cwd in scan_sessions(self._sessions_dir):
                usage = read_context_usage(self._projects_dir, cwd, session_id)
                if usage is None:
                    continue
                model, total_tokens = usage
                fill = compute_fill_pct(model, total_tokens)
                project_name = Path(cwd).name
                results.append((project_name, model, fill))
            self.sessions_ready.emit(results)

            for _ in range(self._interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
```

- [ ] **Step 2: Verify file compiles**

Run: `python -c "from session_scanner import SessionScanner; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add session_scanner.py
git commit -m "feat: add SessionScanner QThread — scans every 15s, emits session list"
```

---

### Task 5: ContextBar widget with threshold mark

**Files:**
- Modify: `visualizer.py`

- [ ] **Step 1: Add ContextBar class after the existing ColorBar class**

Add this class right after the `ColorBar` class in `visualizer.py` (around line 79):

```python
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
```

- [ ] **Step 2: Verify it compiles**

Run: `python -c "from visualizer import ContextBar; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add visualizer.py
git commit -m "feat: add ContextBar widget with compaction threshold mark at 80%"
```

---

### Task 6: Add ping row to the UI

**Files:**
- Modify: `visualizer.py`

- [ ] **Step 1: Add ping_poller import**

At the top of `visualizer.py`, add to the imports:

```python
from ping_poller import PingPoller
```

- [ ] **Step 2: Add ping UI widgets in `_build_ui`**

In `_build_ui`, after the header layout is added to `root` (after `root.addLayout(header)`), insert the ping row:

```python
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
```

- [ ] **Step 3: Add ping signal handler**

Add this method to `VisualizerWindow`:

```python
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
```

- [ ] **Step 4: Start PingPoller in `_start_poller` (rename to `_start_pollers`)**

Rename `_start_poller` to `_start_pollers` and add PingPoller startup. Update the call in `__init__` accordingly.

```python
    def _start_pollers(self) -> None:
        self._poller = Poller()
        self._poller.data_ready.connect(self._on_data)
        self._poller.error.connect(self._on_error)
        self._poller.start()

        self._ping_poller = PingPoller()
        self._ping_poller.ping_ready.connect(self._on_ping)
        self._ping_poller.start()
```

- [ ] **Step 5: Stop PingPoller in `closeEvent`**

Update `closeEvent`:

```python
    def closeEvent(self, event) -> None:
        self._poller.stop()
        self._poller.wait(2000)
        self._ping_poller.stop()
        self._ping_poller.wait(2000)
        event.accept()
```

- [ ] **Step 6: Update `__init__` to call `_start_pollers`**

Change `self._start_poller()` to `self._start_pollers()` in `__init__`.

- [ ] **Step 7: Update title**

In `_build_ui`, change:

```python
        title = QLabel("Claude Code · 5h Session")
```

to:

```python
        title = QLabel("Claude Monitor")
```

- [ ] **Step 8: Verify it runs**

Run: `python visualizer.py` — confirm the widget shows with ping row and "Claude Monitor" title. Close after visual check.

- [ ] **Step 9: Commit**

```bash
git add visualizer.py
git commit -m "feat: add ping monitor row to widget UI"
```

---

### Task 7: Add context section to the UI

**Files:**
- Modify: `visualizer.py`

- [ ] **Step 1: Add session_scanner import**

At the top of `visualizer.py`, add:

```python
from session_scanner import SessionScanner
```

- [ ] **Step 2: Add context section container in `_build_ui`**

After the time bar and before the footer, add a container widget for the context section:

```python
        # --- Context section (auto-collapse) ---
        self._context_container = QWidget()
        self._context_container.setStyleSheet("background: transparent;")
        self._context_layout = QVBoxLayout(self._context_container)
        self._context_layout.setContentsMargins(0, 0, 0, 0)
        self._context_layout.setSpacing(4)
        self._context_container.setVisible(False)
        root.addWidget(self._context_container)
```

- [ ] **Step 3: Add session signal handler**

Add this method to `VisualizerWindow`:

```python
    def _on_sessions(self, sessions: list) -> None:
        # Clear existing context widgets
        while self._context_layout.count():
            item = self._context_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not sessions:
            self._context_container.setVisible(False)
            self.adjustSize()
            return

        # Section header
        header = QLabel(f"Context · {len(sessions)} session{'s' if len(sessions) != 1 else ''}")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"color: {GREY}; font-size: 9px; background: transparent; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        self._context_layout.addWidget(header)

        # Per-session rows
        for project_name, model, fill_pct in sessions:
            # Strip model prefix for display (e.g. "claude-opus-4-6" -> "opus")
            short_model = model.replace("claude-", "").split("-")[0]
            pct_text = f"{int(fill_pct * 100)}%"

            label_row = QHBoxLayout()
            name_label = QLabel(f"{project_name} · {short_model}")
            name_label.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; background: transparent;"
            )
            pct_label = QLabel(pct_text)
            pct_label.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; background: transparent;"
            )
            label_row.addWidget(name_label)
            label_row.addStretch()
            label_row.addWidget(pct_label)

            label_widget = QWidget()
            label_widget.setStyleSheet("background: transparent;")
            label_widget.setLayout(label_row)
            self._context_layout.addWidget(label_widget)

            bar = ContextBar()
            bar.set_value(fill_pct)
            self._context_layout.addWidget(bar)

        self._context_container.setVisible(True)
        self.adjustSize()
```

- [ ] **Step 4: Start SessionScanner in `_start_pollers`**

Add to `_start_pollers`:

```python
        self._session_scanner = SessionScanner()
        self._session_scanner.sessions_ready.connect(self._on_sessions)
        self._session_scanner.start()
```

- [ ] **Step 5: Stop SessionScanner in `closeEvent`**

Add to `closeEvent` (before `event.accept()`):

```python
        self._session_scanner.stop()
        self._session_scanner.wait(2000)
```

- [ ] **Step 6: Switch to dynamic sizing**

In `_setup_window`, replace:

```python
        self.setFixedSize(WIDTH, HEIGHT)
```

with:

```python
        self.setFixedWidth(WIDTH)
        self.setMinimumHeight(HEIGHT)
```

- [ ] **Step 7: Update `_position_top_right` to use `sizeHint` height**

Change `geo.top() + 32` stays the same — position is from the top, height grows downward, so no positioning change needed. No code change for this step.

- [ ] **Step 8: Verify it runs**

Run: `python visualizer.py` — confirm the widget shows with context bars for any active Claude Code sessions. They should appear after ~15 seconds (first scan cycle). Close after visual check.

- [ ] **Step 9: Commit**

```bash
git add visualizer.py
git commit -m "feat: add context compaction section with auto-collapse"
```

---

### Task 8: Final integration test and cleanup

**Files:**
- Modify: `visualizer.py` (if needed)

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Run the widget end-to-end**

Run: `python visualizer.py`

Verify:
- Title shows "Claude Monitor"
- Ping row shows ONLINE/OFFLINE with colored dot + colored text + latency
- Token and time bars work as before
- Context section appears after ~15s if Claude Code sessions are running
- Context section is hidden if no sessions are detected
- Widget height adjusts dynamically
- Dragging still works
- Close button and right-click quit still work

- [ ] **Step 3: Commit any final tweaks**

```bash
git add -A
git commit -m "feat: Claude Monitor — general widget with ping + context bars"
```
