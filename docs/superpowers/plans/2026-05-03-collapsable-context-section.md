# Collapsable Context Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the per-session "Context" section in `visualizer.py` user-collapsable via a clickable header with a chevron, persisting the collapsed/expanded preference across app restarts.

**Architecture:** Add a small `_ClickableLabel` QLabel subclass that emits a `clicked` signal. Restructure the existing `_context_container` so it holds a *persistent* clickable header label and a *separate* rebuilt-on-update rows container. Persist the toggle state via `QSettings("ClaudeMonitor", "Visualizer")`. No new files; everything lives in `visualizer.py`.

**Tech Stack:** Python, PyQt6 (existing stack — no new dependencies). The spec is at `docs/superpowers/specs/2026-05-03-collapsable-context-section-design.md`.

**Note on tests:** The spec explicitly defers tests for this change (no `tests/test_visualizer.py` exists; the project does not have a PyQt UI test pattern). Verification is manual, captured in Task 3.

---

## File Structure

Only `visualizer.py` is touched.

- `visualizer.py`
  - **New module-scope class `_ClickableLabel(QLabel)`** — emits `clicked` signal on left-mouse-press. Used only for the context section header.
  - **Modified `VisualizerWindow.__init__`** — reads persisted expanded state from QSettings; initializes `_context_session_count`.
  - **Modified `VisualizerWindow._build_ui`** — splits the context section into a persistent header (`_context_header`) plus a separately-managed rows container (`_context_rows_container`).
  - **New methods `_toggle_context_section`, `_apply_context_expanded_state`, `_refresh_context_header`** on `VisualizerWindow`.
  - **Modified `VisualizerWindow._on_sessions`** — clears/rebuilds only `_context_rows_layout` (not the header), updates `_context_session_count`, applies expanded state.

No changes to imports/exports of other modules. No new files.

---

### Task 1: Add `_ClickableLabel` subclass

**Files:**
- Modify: `visualizer.py` (imports near line 8; new class after `ContextBar` ends at line 128)

- [ ] **Step 1: Extend the `PyQt6.QtCore` import**

In `visualizer.py`, find the existing import line:

```python
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
```

Replace it with:

```python
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSettings, pyqtSignal
```

(`QSettings` is for Task 2; adding both here in one shot keeps the import block tidy.)

- [ ] **Step 2: Add the `_ClickableLabel` class**

In `visualizer.py`, immediately after the closing of the `ContextBar` class (the line `painter.end()` on line 128, followed by the blank line), insert the following block. It should sit between `ContextBar` and the `VisualizerWindow` class declaration:

```python
class _ClickableLabel(QLabel):
    """QLabel that emits `clicked` on left mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:
        """Emit `clicked` for left-button presses, then defer to base behavior."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
```

- [ ] **Step 3: Sanity-check the file still imports cleanly**

Run:

```bash
python -c "import visualizer"
```

Expected: no output, exit code 0. (No syntax errors, imports resolve.)

- [ ] **Step 4: Commit**

```bash
git add visualizer.py
git commit -m "feat: add _ClickableLabel widget for collapsable headers"
```

---

### Task 2: Restructure context section into persistent header + rebuildable rows, with persisted toggle state

This task is intentionally atomic — the new header widget, the new rows container, the new state attributes, the new toggle methods, and the rewritten `_on_sessions` all depend on each other. Splitting them would leave the UI in a broken intermediate state between commits.

**Files:**
- Modify: `visualizer.py:136-148` (`__init__`)
- Modify: `visualizer.py:232-239` (context section block in `_build_ui`)
- Add new methods on `VisualizerWindow` (place them just above `_on_sessions`, around line 364)
- Modify: `visualizer.py:364-416` (`_on_sessions`)

- [ ] **Step 1: Initialize the persisted state in `__init__`**

In `visualizer.py`, find the `__init__` method (currently lines 136-148):

```python
    def __init__(self) -> None:
        super().__init__()
        self._drag_pos: Optional[QPoint] = None
        self._reset_at: Optional[datetime] = None
        self._spinner_idx: int = 0
        self._dot_visible: bool = True
        self._is_loading: bool = True

        self._setup_window()
        self._build_ui()
        self._position_top_right()
        self._start_timers()
        self._start_pollers()
```

Replace it with:

```python
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
```

- [ ] **Step 2: Replace the context section block in `_build_ui`**

In `visualizer.py`, find the existing context section block (currently lines 232-239):

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

Replace it with:

```python
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
```

- [ ] **Step 3: Add the three new methods**

In `visualizer.py`, find the `_on_sessions` method (currently starting at line 364). Immediately *above* it (i.e., after `_on_ping` ends at line 362), insert these three methods:

```python
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
```

- [ ] **Step 4: Rewrite `_on_sessions`**

In `visualizer.py`, find the entire `_on_sessions` method (currently lines 364-416):

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
        count = len(sessions)
        header = QLabel(f"CONTEXT · {count} SESSION{'S' if count != 1 else ''}")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"color: {GREY}; font-size: 9px; background: transparent;"
        )
        self._context_layout.addWidget(header)

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
            self._context_layout.addWidget(label_widget)

            bar = ContextBar()
            bar.set_value(fill_pct)
            self._context_layout.addWidget(bar)

        self._context_container.setVisible(True)
        self.adjustSize()
```

Replace it with:

```python
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
```

(Note: `_apply_context_expanded_state` is called *after* `setVisible(True)` on the outer container so that the inner-rows visibility flip and the `adjustSize()` happen with the outer container already shown — otherwise the panel sizing would not account for the now-visible section.)

- [ ] **Step 5: Sanity-check the module still imports**

Run:

```bash
python -c "import visualizer"
```

Expected: no output, exit code 0.

- [ ] **Step 6: Verify no stale `_context_layout` references remain**

Use the Grep tool (or `git grep`) to search the project for `_context_layout`:

```bash
git grep -n "_context_layout" -- visualizer.py
```

Expected: **no matches**. (The attribute was renamed to `_context_rows_layout` and any leftover would mean an incomplete rewrite.)

If matches appear, find them and rename to `_context_rows_layout` before committing.

- [ ] **Step 7: Commit**

```bash
git add visualizer.py
git commit -m "feat: make context section user-collapsable with persisted state"
```

---

### Task 3: Manual verification

There is no automated UI test. Verify the feature behaves as the spec describes by exercising it in a live run.

**Files:** none (verification only).

- [ ] **Step 1: Reset any prior persisted preference (Windows)**

To make sure the run starts from a clean state and the default-expanded path is exercised at least once, delete the persisted key. Open PowerShell and run:

```powershell
Remove-ItemProperty -Path "HKCU:\Software\ClaudeMonitor\Visualizer" -Name "context_section_expanded" -ErrorAction SilentlyContinue
```

(The `-ErrorAction SilentlyContinue` makes this a no-op if the key doesn't exist yet.)

- [ ] **Step 2: Launch the visualizer with no Claude sessions**

Run:

```bash
python visualizer.py
```

Expected: the panel appears, the "Context" section is **not visible** (no header, no rows). Tokens bar and Session time bar are unaffected.

- [ ] **Step 3: Start a Claude Code session in any project**

In another terminal, start a Claude Code session (e.g., `claude` in some directory and exchange one message so a JSONL file exists in `~/.claude/projects`).

Expected (within ~one polling cycle of `SessionScanner`): the panel grows; a header reading `▾ CONTEXT · 1 SESSION` appears, with the per-session row + bar below it. Hovering the header shows a pointing-hand cursor.

- [ ] **Step 4: Click the header — collapse**

Click anywhere on the `▾ CONTEXT · 1 SESSION` header.

Expected: the per-session row + bar disappear. The header text becomes `▸ CONTEXT · 1 SESSION`. The panel shrinks to the new height.

- [ ] **Step 5: Click again — expand**

Click the header again.

Expected: rows reappear. Header reverts to `▾ CONTEXT · 1 SESSION`. Panel grows back.

- [ ] **Step 6: Persist across restart**

Click the header once so the section is **collapsed** (header reads `▸ …`). Close the panel (× button or right-click). Relaunch:

```bash
python visualizer.py
```

Expected: when the session reappears, the section comes up **collapsed** — header `▸ CONTEXT · 1 SESSION` only, no rows. (Confirms `QSettings` round-trip.)

- [ ] **Step 7: Empty-state preserves preference**

While the section is collapsed, end the Claude Code session (close that terminal). Wait for the next scan.

Expected: the entire context section disappears (auto-hide).

Now start a new Claude Code session.

Expected: the section reappears **still collapsed** — header `▸ CONTEXT · 1 SESSION` only.

- [ ] **Step 8: Plural / count update**

Start a second Claude Code session in another project (so two are alive at once). With the section expanded, expected: header reads `▾ CONTEXT · 2 SESSIONS` and there are two row+bar pairs. With one session, header reads `▾ CONTEXT · 1 SESSION` (singular). Confirms count + pluralization.

- [ ] **Step 9: Commit nothing**

This task is verification only — no files change. If you found a bug, fix it in Task 2 (or add a follow-up commit) and re-run the verification steps.

---

## Self-Review

Checked the plan against the spec:

- **Spec § Widget structure** → Task 2 Step 2 (split into outer container + persistent `_context_header` + separate `_context_rows_container`).
- **Spec § State and persistence** → Task 2 Step 1 (init from QSettings) + Task 2 Step 3 (toggle method writes via QSettings).
- **Spec § Interaction & visual details** (chevrons `▾`/`▸`, center alignment, GREY 9px, PointingHandCursor, snap show/hide) → Task 2 Step 2 (cursor + style on header) + Task 2 Step 3 (`_refresh_context_header` chevron logic).
- **Spec § Empty-state behavior** → Task 2 Step 4 rewritten `_on_sessions`: empty list path hides outer container; non-empty path calls `_apply_context_expanded_state` after rebuild so the persisted preference is honored when sessions reappear.
- **Spec § First-ever launch** → Task 2 Step 1 uses `True` default in `settings.value(...)` — no special case needed.
- **Spec § App close** → no shutdown hook; QSettings writes synchronously in `_toggle_context_section` (Task 2 Step 3).
- **Spec § Testing (manual)** → Task 3 covers all six verification points from the spec, plus a chevron/plural sanity check (Step 8).

Placeholder scan: no TBD/TODO/"add error handling"/"similar to" patterns. All code blocks are full.

Type/name consistency check:
- `_context_expanded` (bool) — set in init, flipped in `_toggle_context_section`, read in `_apply_context_expanded_state` and `_refresh_context_header`. Consistent.
- `_context_session_count` (int) — init to 0, set in `_on_sessions`, read in `_refresh_context_header`. Consistent.
- `_context_header` (`_ClickableLabel`), `_context_container` (`QWidget`), `_context_rows_container` (`QWidget`), `_context_rows_layout` (`QVBoxLayout`) — all introduced in `_build_ui`, used consistently in the three new methods and rewritten `_on_sessions`. Old `_context_layout` is fully removed (Task 2 Step 6 verifies).
- QSettings key `"context_section_expanded"` and org/app `("ClaudeMonitor", "Visualizer")` — same string used in init read and in toggle write. Consistent.
- `_ClickableLabel.clicked` signal — declared in Task 1, connected in Task 2 Step 2.

No issues found.
