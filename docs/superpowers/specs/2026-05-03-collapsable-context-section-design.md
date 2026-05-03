# Collapsable Context Section — Design

## Goal

Make the per-session "Context" section in `visualizer.py` user-collapsable: clicking the section header toggles whether the per-session rows are shown. The user's collapsed/expanded preference persists across app restarts.

## Current behavior (baseline)

In `visualizer.py`, the context section is built around `self._context_container` (`visualizer.py:232-239`). Each `_on_sessions(...)` call (`visualizer.py:364-416`) clears the container, rebuilds the header label `"CONTEXT · N SESSION(S)"` plus per-session rows + bars, and toggles the container's visibility based on whether any sessions exist.

The section auto-hides when the sessions list is empty and auto-shows when it isn't. There is no user control over visibility.

## Design

### Widget structure

Split the existing single container into two nested widgets:

- **Outer**: `self._context_container` — kept. Visible whenever the sessions list is non-empty (current auto-hide behavior preserved).
- **Header**: a new `_ClickableLabel(QLabel)` subclass that emits a `clicked` signal from `mousePressEvent`. Built **once** in `_build_ui` (no longer rebuilt on each `_on_sessions` call). Its text is updated on each `_on_sessions` call and on each toggle to reflect the current chevron and session count:
  - Expanded: `"▾ CONTEXT · 2 SESSIONS"`
  - Collapsed: `"▸ CONTEXT · 2 SESSIONS"`
  - Cursor on hover: `Qt.CursorShape.PointingHandCursor`.
- **Rows container**: a new `self._context_rows_container` (a `QWidget` with its own `QVBoxLayout`). Holds the per-session label rows + `ContextBar` widgets. The current rebuild logic in `_on_sessions` moves into this child container. Its `setVisible(...)` is driven by `self._context_expanded`.

### State and persistence

- New attribute: `self._context_expanded: bool`, initialized in `__init__` from
  `QSettings("ClaudeMonitor", "Visualizer").value("context_section_expanded", True, type=bool)`.
- New method `_toggle_context_section()`: flips `self._context_expanded`, writes the new value to `QSettings`, then calls `_apply_context_expanded_state()`.
- New helper `_apply_context_expanded_state()`: refreshes the header text (chevron char), calls `self._context_rows_container.setVisible(self._context_expanded)`, then `self.adjustSize()`.
- `_ClickableLabel.clicked` is wired to `_toggle_context_section` once in `_build_ui`.

QSettings on Windows writes to the registry under `HKCU\Software\ClaudeMonitor\Visualizer`. No new files, no new dependencies.

### Interaction & visual details

- **Chevron characters**: `▾` (U+25BE) for expanded, `▸` (U+25B8) for collapsed. Compact, render consistently on Windows without an emoji font.
- **Header alignment / style**: unchanged from the current header (`Qt.AlignmentFlag.AlignCenter`, `color: GREY; font-size: 9px; background: transparent;`). Only addition: `setCursor(Qt.CursorShape.PointingHandCursor)`.
- **Click target**: full QLabel rectangle (full panel width). No overlap risk with the static tokens/time bars above or per-session bars below.
- **Animation**: none. Snap show/hide + `adjustSize()`. Matches the rest of the panel.

### Empty-state behavior

- `_on_sessions([])` keeps the existing behavior: hide the entire `_context_container`, then `adjustSize()`. The header is not shown. The `_context_expanded` value remains in memory and in QSettings, untouched.
- When sessions reappear: rebuild rows into `_context_rows_container`, call `_apply_context_expanded_state()` so the rows container honors the persisted preference, then `_context_container.setVisible(True)`. If the user had collapsed before the empty period, the section reappears collapsed (header + count visible, rows hidden).

### First-ever launch

QSettings returns the default `True` → expanded. No first-run special case.

### App close

Nothing extra. QSettings writes synchronously on each toggle, so no shutdown hook is needed.

## File changes

- **`visualizer.py`** — only file touched.
  - Add `_ClickableLabel(QLabel)` subclass at module scope.
  - In `__init__`: read `_context_expanded` from `QSettings`.
  - In `_build_ui`: build the header label and the rows container as separate widgets inside `_context_container`; wire the click signal.
  - Add `_toggle_context_section()` and `_apply_context_expanded_state()` methods.
  - Modify `_on_sessions(...)` to:
    - clear and rebuild only `_context_rows_container`'s children (not the header),
    - update the header text with the current chevron + count,
    - call `_apply_context_expanded_state()` before showing the outer container.

No changes to `poller.py`, `ping_poller.py`, `session_scanner.py`, `install.py`, or any test file.

## Testing

There is no `tests/test_visualizer.py` — the existing suite covers the data layer (poller, ping_poller, session_scanner, install). PyQt UI is awkward to unit-test and the project has no established pattern for it, so this change does not introduce a UI test file.

Verification is manual:

1. Launch `visualizer.py` with no Claude sessions running → section is hidden.
2. Start a Claude session → section appears, expanded by default, with `▾` chevron.
3. Click the header → rows hide, chevron flips to `▸`, panel shrinks.
4. Click again → rows reappear, chevron flips to `▾`, panel grows.
5. Close and relaunch the app while collapsed → section reappears collapsed (header only).
6. Stop all sessions while collapsed → section auto-hides; restart sessions → section reappears collapsed (preference preserved across the empty period).

## Out of scope

- Animated expand/collapse transitions.
- Collapse state for any other section of the panel.
- A UI test harness for `visualizer.py`.
- Changes to which sessions are tracked or how their data is rendered when expanded.
