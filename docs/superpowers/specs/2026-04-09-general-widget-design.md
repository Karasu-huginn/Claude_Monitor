# General Widget Expansion — Design Spec

**Date:** 2026-04-09

## Overview

Expand the Claude tokens visualizer into a general-purpose desktop monitor ("Claude Monitor") by adding two features:

1. **Ping monitor** — always-visible row showing network status (ONLINE/OFFLINE) with latency
2. **Context compaction bars** — one bar per active Claude Code session showing context window fill %, auto-collapsing when no sessions are running

---

## Widget Layout

Width stays at 300px. Height grows dynamically based on active Claude Code sessions.

```
┌─────────────────────────────────┐
│ Claude Monitor                × │
│ ● ONLINE 12ms                   │  ← ping row (always visible)
│ Tokens — 73% used               │
│ ████████████████░░░░░░░░░░░░░  │  ← 16px bar
│ Session time — resets in 2h 14m │
│ ██████████████░░░░░░░░░░░░░░░  │  ← 16px bar
│ ─── Context · 2 sessions ───    │  ← auto-collapse section
│ visualizer · opus         68%   │
│ █████████████░░░░░░|░░░░░░░░░  │  ← 12px bar, threshold mark at ~80%
│ ping_monitor · sonnet     42%   │
│ ████████░░░░░░░░░░|░░░░░░░░░░  │
│ updated 14:22:05              ● │
└─────────────────────────────────┘
```

### Height calculation

| Component               | Height |
|--------------------------|--------|
| Base (ping + tokens + time + footer) | ~170px |
| Context section header   | ~20px  |
| Each context session (label + bar) | ~30px |

- 0 sessions: ~170px (context section hidden)
- 2 sessions: ~250px
- 4 sessions: ~310px

### Title

Renamed from "Claude Code · 5h Session" to "Claude Monitor".

---

## Feature 1: Ping Monitor

### What it does

Pings `8.8.8.8` every 2 seconds and displays ONLINE/OFFLINE status with latency.

### UI row

`QHBoxLayout` containing:
- **Dot**: `QLabel` styled as a 10px colored circle (green online, red offline)
- **Status text**: `QLabel`, bold, colored (green "ONLINE" / red "OFFLINE")
- **Latency**: `QLabel`, grey `#555577`, smaller font, shows "12ms" or "---"

Always visible — no collapse.

### Ping function

Ported from `ping_monitor/ping_monitor.py`:
- Calls OS `ping` binary: `ping -n 1 -w 1000 8.8.8.8` (Windows) / `ping -c 1 -W 1 8.8.8.8` (Unix)
- `CREATE_NO_WINDOW` flag on Windows to suppress console flash
- Regex `r'time[=<](\d+\.?\d*)\s*ms'` to extract latency
- Returns `(bool, float | None)` — (success, latency_ms)

### Threading

Dedicated `QThread` subclass (`PingPoller`):
- Loops: call `ping()`, emit `ping_ready(bool, float)`, sleep 2 seconds (in 1-second ticks for responsive stop)
- Signal: `ping_ready(bool, object)` → `(online, latency_ms_or_None)`

### Error states

| State   | Dot     | Text                | Latency |
|---------|---------|---------------------|---------|
| Online  | green `#00b894` | green "ONLINE"  | grey "12ms" |
| Offline | red `#d63031`   | red "OFFLINE"   | grey "---"  |

---

## Feature 2: Context Compaction Bars

### What it does

Shows one progress bar per active Claude Code session, displaying what percentage of the context window is filled. A threshold mark at ~80% indicates the approximate compaction point.

### Data source

No API — purely local file reads.

**Session detection** — `~/.claude/sessions/<PID>.json`:
```json
{
  "pid": 26416,
  "sessionId": "6d9d9f65-e226-4308-b215-c98eeca24380",
  "cwd": "C:\\Users\\erwan\\...\\claude_tokens_visualizer",
  "startedAt": 1775730657047,
  "kind": "interactive"
}
```

**Context usage** — `~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl`:
- `<encoded-cwd>` uses dashes replacing path separators and colons, e.g. `C--Users-erwan-Desktop-FOLDERS-python-utile-claude-tokens-visualizer`
- Each line is a JSON object. Only assistant message entries contain a `message.usage` field with `input_tokens`.
- Scan backwards from end of file for the last entry that has `message.usage.input_tokens` — that value represents the current context size.
- The model name is in `message.model` on the same entry (e.g. `"claude-opus-4-6"`)

**Fill percentage**: `input_tokens / MODEL_CONTEXT_LIMITS[model]`

### Model context limits (hardcoded)

| Model              | Max tokens |
|--------------------|------------|
| `claude-opus-4-6`    | 200,000    |
| `claude-sonnet-4-6`  | 200,000    |
| `claude-haiku-4-5`   | 200,000    |

These are defaults. Extended context (1M for opus) is an edge case we can handle later if needed.

### Session liveness check

- Read PID from session JSON filename
- Windows: `ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)` — returns 0 if dead
- Unix: `os.kill(pid, 0)` — raises `OSError` if dead
- Dead sessions are filtered out of the display

### Compaction threshold mark

A thin vertical line drawn at 80% on each context bar. This is a visual reference — Claude Code's actual compaction point may vary, but 80% is a useful approximation.

### Threading

Single `QThread` subclass (`SessionScanner`):
- Poll interval: 15 seconds
- Each cycle:
  1. Scan `~/.claude/sessions/` for `.json` files
  2. Filter to alive PIDs
  3. For each alive session, read last JSONL entry, extract `input_tokens` and model
  4. Compute fill %
- Signal: `sessions_ready(list)` → list of `(project_name, model, fill_pct)` tuples
- On error (file missing, permission error): skip that session, try again next cycle

### UI components

**Section header**: centered text "Context · N sessions" with horizontal rule lines on each side. Styled in `#555577`, 10px, uppercase.

**Per-session row**:
- `QLabel`: `"project_folder · model"` left-aligned, `"68%"` right-aligned, 11px, `#aaa`
- `ColorBar`: 12px height (thinner than the 16px tokens/time bars), same color scale (green/yellow/orange/red), plus a white threshold mark at 80%

### Auto-collapse

- **Show**: when `len(alive_sessions) > 0` — section header + all session rows visible
- **Hide**: when `len(alive_sessions) == 0` — section header + all session rows removed
- No animation — instant show/hide via `setVisible()`
- Widget calls `adjustSize()` after changes to shrink/grow the window

---

## Changes by File

### `poller.py`
- No changes to existing code.

### `visualizer.py`
- Rename window title from "Claude Code · 5h Session" to "Claude Monitor"
- Add ping row (dot + status label + latency label) between header and tokens row
- Add context section (header + dynamic session bars) between time bar and footer
- Remove hardcoded `HEIGHT` — use dynamic sizing via layout + `adjustSize()`
- Handle `PingPoller.ping_ready` signal → update ping row
- Handle `SessionScanner.sessions_ready` signal → rebuild context section

### New file: `ping_poller.py`
- `ping(target, timeout)` function (ported from `ping_monitor/ping_monitor.py`)
- `PingPoller(QThread)` class — pings every 2s, emits `ping_ready(bool, object)`

### New file: `session_scanner.py`
- `scan_sessions(sessions_dir)` → list of `(pid, session_id, cwd)` for alive sessions
- `read_context_usage(projects_dir, cwd, session_id)` → `(model, input_tokens)` from last JSONL entry
- `is_pid_alive(pid)` → bool (platform-aware)
- `SessionScanner(QThread)` class — scans every 15s, emits `sessions_ready(list)`
- `MODEL_CONTEXT_LIMITS` dict

### `tests/test_ping_poller.py`
- Test `ping()` regex extraction (reuse cases from `ping_monitor/tests/test_ping.py`)

### `tests/test_session_scanner.py`
- Test `scan_sessions` with mock session files
- Test `read_context_usage` with mock JSONL data
- Test `is_pid_alive` with current PID (should be alive)
- Test fill % computation

---

## Error & Loading States

### Ping
- Starts immediately on launch. First result within ~2 seconds.
- If ping subprocess fails (no network interface), treated as offline.

### Context section
- On launch: hidden (no sessions scanned yet). First scan at ~15s.
- If `~/.claude/sessions/` doesn't exist: section stays hidden.
- If a session's JSONL file is missing or unreadable: skip that session silently.
- If all sessions die between scans: section collapses on next scan.

### Existing behavior (tokens + time bars)
- Unchanged. All existing error states (loading, offline, rate-limited, auth error) work as before.

---

## Dependencies

- **PyQt6** — already required
- **requests** — already required
- **No new dependencies** — ping uses OS subprocess, session scanner uses stdlib file I/O

---

## Out of Scope

- Tray icon or system notifications
- Configurable ping target or interval
- Extended context (1M) detection — can be added later
- Compaction threshold customization
- Animation on section show/hide
- Multi-monitor positioning
