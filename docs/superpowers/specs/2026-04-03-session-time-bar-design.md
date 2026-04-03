# Session Time Progress Bar — Design Spec

**Date:** 2026-04-03

## Overview

Add a second progress bar alongside the existing tokens bar showing how much of the 5-hour Claude Code session has elapsed. Replace the large percentage label with compact labeled-bar rows to keep the panel within its current 300 × 160 px footprint.

---

## UI Layout

Remove the big centered percentage label (`_pct_label`, 34pt). Replace the subtitle row with two labeled-bar rows stacked vertically:

```
┌──────────────────────────────────────────────┐
│ Claude Code · 5h Session                    × │
│ Tokens — 73% used                             │
│ ████████████████░░░░░░░░░░░░░░░░░░            │
│ Session time — resets in 2h                   │
│ ██████████████████████░░░░░░░░░░░             │
│ updated 14:22:05                            ● │
└──────────────────────────────────────────────┘
```

- Each bar is preceded by a single-line label (`9px`, `MUTED` color).
- Bar heights stay at 18 px (unchanged from the tokens bar).
- Window size stays **300 × 160 px** — no resize needed.
- The spinner during loading is shown in the tokens label text instead of the removed big number.

### Label text

| State        | Tokens label             | Time label                         |
|--------------|--------------------------|------------------------------------|
| State        | Tokens label                     | Time label                              |
|--------------|----------------------------------|-----------------------------------------|
| Loading      | `Tokens — ⠋` (spinner animates) | `Session time — …`                      |
| Normal       | `Tokens — 73% used`              | `Session time — resets in 2h 14m`       |
| Offline      | `Tokens — offline`               | live: `Session time — resets in 2h 14m` |
| Rate-limited | `Tokens — rate limited`          | live: `Session time — resets in 2h 14m` |
| Auth error   | *(cleared)*                      | *(cleared)*                             |

The time label and time bar continue updating every second in all states where `reset_at` is known (including offline and rate-limited), because the reset clock is unaffected by connectivity. Only an auth error clears `reset_at` and stops the time bar.

The spinner (`_tick_spinner`) animates the tokens label text during loading (`"Tokens — ⠋"`, `"Tokens — ⠙"`, …) instead of the removed `_pct_label`.

---

## Data & Computation

### New utility function in `poller.py`

```python
def compute_time_utilization(reset_at: datetime, session_hours: float = 5.0) -> float:
    """Return fraction of session elapsed (0–1). 2h remaining → 0.60."""
    remaining = (reset_at - datetime.now(timezone.utc)).total_seconds()
    remaining = max(0.0, min(remaining, session_hours * 3600))
    return 1.0 - remaining / (session_hours * 3600)
```

- Called inside `_update_countdown` (fires every second) to keep the time bar live.
- Reuses `get_bar_color()` with the same thresholds as the tokens bar (green < 60%, yellow 60–80%, orange 80–90%, red ≥ 90%), so color shifts as the session nears reset.
- No new signals, no new timers, no changes to `Poller`.

---

## Changes by File

### `poller.py`
- Add `compute_time_utilization(reset_at, session_hours=5.0) -> float`
- No other changes.

### `visualizer.py`
- Remove `_pct_label` widget and all references to it.
- Remove the subtitle `QHBoxLayout` row (the `_used_label` / `_countdown_label` pair).
- Add `_tokens_label: QLabel` above the tokens `ColorBar`.
- Add `_time_bar: ColorBar` and `_time_label: QLabel` above it.
- Update `_on_data`: set `_tokens_label` text; clear `_countdown_label` is replaced by updating `_time_label` via the countdown timer.
- Update `_update_countdown`: also calls `_time_bar.set_value(compute_time_utilization(self._reset_at))` and updates `_time_label` text.
- Update `_on_error`: handle loading, offline, rate-limited, auth-error states for both labels.
- Update `_tick_spinner`: animate the tokens label text during loading instead of `_pct_label`.
- `HEIGHT` constant updated from `160` to `160` (no change — layout fits).

### `tests/test_poller.py`
- Add tests for `compute_time_utilization`: exact 2h remaining → 0.60, full remaining → 0.0, expired → 1.0, clamp above 5h → 0.0.

---

## Error & Loading States

- **Loading (before first poll):** both bars grey. Tokens label animates spinner frames (`"Tokens — ⠋"` etc.). Time label shows static `"Session time — …"`.
- **Auth error / unknown:** both bars grey, both labels cleared (`""`), `reset_at` set to `None`. Footer dot red.
- **Offline:** tokens label shows `"Tokens — offline"` (red). Tokens bar value preserved. Time bar and label continue updating live every second (reset clock is unaffected).
- **Rate-limited:** tokens label shows `"Tokens — rate limited"` (yellow). Same as offline for time bar.
