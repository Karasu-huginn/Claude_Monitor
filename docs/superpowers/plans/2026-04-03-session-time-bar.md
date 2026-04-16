# Session Time Bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second progress bar showing elapsed session time (e.g. 3h elapsed / 5h = 60% filled) alongside the existing tokens bar, replacing the big percentage label with compact labeled-bar rows.

**Architecture:** `compute_time_utilization()` is added as a pure function to `poller.py`; the existing `_update_countdown` timer (1 s tick) calls it to keep the time bar live. The `visualizer.py` layout drops `_pct_label` and the subtitle row, replacing them with label+bar pairs for tokens and session time.

**Tech Stack:** Python 3, PyQt6, pytest

---

## Files

| File | Change |
|------|--------|
| `poller.py` | Add `compute_time_utilization()` |
| `visualizer.py` | Remove `_pct_label` + subtitle row; add labeled token/time bar pairs; update all state handlers |
| `tests/test_poller.py` | Add 4 tests for `compute_time_utilization` |

---

### Task 1: Add `compute_time_utilization` to `poller.py`

**Files:**
- Modify: `poller.py`
- Test: `tests/test_poller.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of the `# --- format_countdown ---` section in `tests/test_poller.py`, after line 69 (`assert format_countdown(reset_at) == "<1m"`):

```python

# --- compute_time_utilization ---

def test_compute_time_utilization_2h_remaining():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=2)
    assert compute_time_utilization(reset_at) == pytest.approx(0.60)

def test_compute_time_utilization_full_session_remaining():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=5)
    assert compute_time_utilization(reset_at) == pytest.approx(0.0)

def test_compute_time_utilization_expired_returns_1():
    reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert compute_time_utilization(reset_at) == pytest.approx(1.0)

def test_compute_time_utilization_clamps_when_over_5h():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=10)
    assert compute_time_utilization(reset_at) == pytest.approx(0.0)
```

Also update the import line at the top of `tests/test_poller.py` (line 6):

```python
from poller import read_credentials, parse_response, format_countdown, get_bar_color, compute_time_utilization
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_poller.py -k "compute_time_utilization" -v
```

Expected: 4 × FAILED with `ImportError: cannot import name 'compute_time_utilization'`

- [ ] **Step 3: Implement `compute_time_utilization` in `poller.py`**

Add this function after `format_countdown` (after line 50, before `get_bar_color`):

```python
def compute_time_utilization(reset_at: datetime, session_hours: float = 5.0) -> float:
    """Return fraction of the 5-hour session elapsed (0–1). 2h remaining → 0.60."""
    session_seconds = session_hours * 3600
    remaining = (reset_at - datetime.now(timezone.utc)).total_seconds()
    remaining = max(0.0, min(remaining, session_seconds))
    return 1.0 - remaining / session_seconds
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_poller.py -k "compute_time_utilization" -v
```

Expected: 4 × PASSED

- [ ] **Step 5: Run full test suite to check for regressions**

```
pytest tests/ -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add poller.py tests/test_poller.py
git commit -m "feat: add compute_time_utilization to poller"
```

---

### Task 2: Rework `visualizer.py` layout and state handlers

**Files:**
- Modify: `visualizer.py`

No automated tests exist for the UI. Manual smoke-test instructions are at the end of this task.

- [ ] **Step 1: Update the import line**

In `visualizer.py`, line 15, change:

```python
from poller import Poller, format_countdown, get_bar_color
```

to:

```python
from poller import Poller, format_countdown, get_bar_color, compute_time_utilization
```

- [ ] **Step 2: Remove `QFont` from the PyQt6 imports**

`QFont` was only used for `_pct_label`. In `visualizer.py` line 8, change:

```python
from PyQt6.QtGui import QPainter, QColor, QFont
```

to:

```python
from PyQt6.QtGui import QPainter, QColor
```

- [ ] **Step 3: Replace `_build_ui` entirely**

Replace the full `_build_ui` method (lines 126–182) with:

```python
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
```

- [ ] **Step 4: Update `_tick_spinner`**

Replace the method (currently lines 208–212):

```python
def _tick_spinner(self) -> None:
    if not self._is_loading:
        return
    self._spinner_idx = (self._spinner_idx + 1) % len(self.SPINNER_FRAMES)
    self._tokens_label.setText(f"Tokens — {self.SPINNER_FRAMES[self._spinner_idx]}")
```

- [ ] **Step 5: Update `_update_countdown`**

Replace the method (currently lines 214–216):

```python
def _update_countdown(self) -> None:
    if self._reset_at is not None:
        self._time_label.setText(
            f"Session time — resets in {format_countdown(self._reset_at)}"
        )
        self._time_bar.set_value(compute_time_utilization(self._reset_at))
```

- [ ] **Step 6: Update `_on_data`**

Replace the method (currently lines 232–244):

```python
def _on_data(self, utilization: float, reset_at: object) -> None:
    self._is_loading = False
    self._reset_at = reset_at  # type: ignore[assignment]
    pct = int(utilization * 100)

    self._bar.set_value(utilization)
    self._tokens_label.setText(f"Tokens — {pct}% used")
    self._tokens_label.setStyleSheet(f"color: {FOOTER_COLOR}; font-size: 9px; background: transparent;")
    self._dot_label.setStyleSheet(f"color: #00b894; font-size: 9px; background: transparent;")
    self._updated_label.setText(f"updated {datetime.now().strftime('%H:%M:%S')}")
```

- [ ] **Step 7: Update `_on_error`**

Replace the method (currently lines 246–268):

```python
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
```

- [ ] **Step 8: Smoke-test the UI**

```
python visualizer.py
```

Check:
- Panel shows two bars stacked with labels above each
- Tokens label shows spinning braille character during initial load, then switches to `"Tokens — X% used"` on first data
- Time label shows `"Session time — resets in Xh Ym"` and updates every second
- Both bars fill and change color (green → yellow → orange → red as % rises)
- Big percentage label is gone
- Close button and drag still work

- [ ] **Step 9: Commit**

```bash
git add visualizer.py
git commit -m "feat: replace big % label with labeled token+time bar rows"
```
