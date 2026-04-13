# Session Status Indicator — Design Spec

## Problem

The visualizer shows active Claude Code sessions with context fill percentages, but doesn't indicate whether Claude is waiting for instructions or actively working. The user has to check each terminal tab to know which sessions need attention.

## Solution

Color the session name/percentage labels based on whether Claude is idle (waiting for user input) or busy (processing). Infer the state from the JSONL message log — no window title parsing or new polling threads needed.

## Status Detection

**Data source:** The session JSONL file at `~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl`.

**Algorithm:**
1. Read the last ~4KB of the JSONL file.
2. Scan backwards for the last entry where `type == "assistant"`.
3. If `message.stop_reason == "end_turn"` → session is **waiting**.
4. Otherwise (`stop_reason == "tool_use"`, no assistant message found, or file unreadable) → session is **working** (or unknown, treated as working).

**Rationale:** When Claude finishes a turn with `end_turn`, it's done and waiting for user input. When it finishes with `tool_use`, it's mid-turn executing tools. If we can't determine the state, we default to "working" since that's the safer assumption (avoids false "ready" signals).

## Visual Treatment

- **Waiting sessions:** Name label and percentage label turn green `#00b894` (same green as the ONLINE ping indicator).
- **Working sessions:** Name label and percentage label stay muted `#aaaacc` (current behavior, unchanged).
- Context fill bars are not affected — only the text labels change color.

## Data Model Change

The `sessions_ready` signal changes from:
```
list of (project_name: str, model: str, fill_pct: float)
```
to:
```
list of (project_name: str, model: str, fill_pct: float, is_waiting: bool)
```

## Changes

### `session_scanner.py`

**New function: `read_session_status()`**
- Signature: `read_session_status(projects_dir: Path, cwd: str, session_id: str) -> bool`
- Returns `True` if the session is waiting for instructions, `False` otherwise.
- Reads last ~4KB of JSONL, scans backwards for last `type == "assistant"` entry, checks `stop_reason`.
- Returns `False` on any error (file missing, unreadable, no assistant message).

**Modified: `SessionScanner.run()`**
- After calling `read_context_usage()`, also call `read_session_status()`.
- Emit 4-tuple `(project_name, model, fill, is_waiting)` instead of 3-tuple.

### `visualizer.py`

**Modified: `_on_sessions()`**
- Unpack `is_waiting` from each session tuple.
- Set label color to `#00b894` when `is_waiting` is `True`, `MUTED` otherwise.
- Applied to both the name label and the percentage label.

### `tests/test_session_scanner.py`

**New tests for `read_session_status()`:**
- `end_turn` → returns `True`
- `tool_use` → returns `False`
- Empty/missing file → returns `False`
- No assistant message in file → returns `False`

## Polling

No changes to polling. The status check runs as part of the existing 15-second `SessionScanner` cycle, reading the same JSONL file that `read_context_usage()` already opens.
