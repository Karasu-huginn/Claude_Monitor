# Session Status Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show whether each Claude Code session is waiting for instructions or actively working, by coloring the session name green (waiting) or muted grey (working).

**Architecture:** Add a `read_session_status()` function to `session_scanner.py` that reads the last assistant message's `stop_reason` from the JSONL file. Pipe the result through the existing `SessionScanner` signal as a 4th tuple element. Color labels in `visualizer.py` based on that boolean.

**Tech Stack:** Python, PyQt6 (existing stack — no new dependencies)

---

### Task 1: Add `read_session_status()` with TDD

**Files:**
- Create tests in: `tests/test_session_scanner.py` (append to existing)
- Implement in: `session_scanner.py:77` (add new function before `read_context_usage`)

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_session_scanner.py`:

```python
# At the top, add read_session_status to the import:
from session_scanner import (
    is_pid_alive,
    encode_cwd,
    scan_sessions,
    read_context_usage,
    read_session_status,
    compute_fill_pct,
    MODEL_CONTEXT_LIMITS,
)


# --- read_session_status ---

def test_read_session_status_end_turn_returns_true(tmp_path):
    """Session whose last assistant message has stop_reason=end_turn is waiting."""
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    lines = [
        json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}),
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "role": "assistant",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 100, "cache_creation_input_tokens": 0,
                          "cache_read_input_tokens": 0, "output_tokens": 50},
            },
        }),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n")

    assert read_session_status(projects_dir, "C:\\Users\\erwan\\my_project", "abc-123") is True


def test_read_session_status_tool_use_returns_false(tmp_path):
    """Session whose last assistant message has stop_reason=tool_use is working."""
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-6",
                "role": "assistant",
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 100, "cache_creation_input_tokens": 0,
                          "cache_read_input_tokens": 0, "output_tokens": 50},
            },
        }),
        json.dumps({"type": "user", "message": {"role": "user", "content": "tool result"}}),
    ]
    jsonl_file.write_text("\n".join(lines) + "\n")

    assert read_session_status(projects_dir, "C:\\Users\\erwan\\my_project", "abc-123") is False


def test_read_session_status_missing_file_returns_false(tmp_path):
    """Missing JSONL file defaults to not-waiting (working)."""
    assert read_session_status(tmp_path, "C:\\no\\such", "bad-id") is False


def test_read_session_status_no_assistant_message_returns_false(tmp_path):
    """JSONL with only user messages defaults to not-waiting."""
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    jsonl_file.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
    )

    assert read_session_status(projects_dir, "C:\\Users\\erwan\\my_project", "abc-123") is False


def test_read_session_status_empty_file_returns_false(tmp_path):
    """Empty JSONL file defaults to not-waiting."""
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "C--Users-erwan-my-project"
    project_dir.mkdir(parents=True)

    jsonl_file = project_dir / "abc-123.jsonl"
    jsonl_file.write_text("")

    assert read_session_status(projects_dir, "C:\\Users\\erwan\\my_project", "abc-123") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_session_scanner.py -k "read_session_status" -v`
Expected: FAIL — `ImportError: cannot import name 'read_session_status'`

- [ ] **Step 3: Implement `read_session_status()`**

Add this function to `session_scanner.py`, right before `read_context_usage()` (before line 77):

```python
def read_session_status(
    projects_dir: Path,
    cwd: str,
    session_id: str,
) -> bool:
    """Check if a session is waiting for user instructions.

    Returns True if the last assistant message has stop_reason='end_turn',
    meaning Claude finished its turn and is waiting for input.
    Returns False on any error or if the session appears to be working.
    """
    encoded = encode_cwd(cwd)
    jsonl_path = projects_dir / encoded / f"{session_id}.jsonl"
    if not jsonl_path.is_file():
        return False

    try:
        file_size = jsonl_path.stat().st_size
        read_size = min(file_size, 4096)
        with open(jsonl_path, "r", encoding="utf-8") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
                f.readline()  # skip partial line
            lines = f.readlines()
    except OSError:
        return False

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "assistant":
            return entry.get("message", {}).get("stop_reason") == "end_turn"

    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_session_scanner.py -k "read_session_status" -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/test_session_scanner.py -v`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add session_scanner.py tests/test_session_scanner.py
git commit -m "feat: add read_session_status() to detect idle sessions"
```

---

### Task 2: Update SessionScanner signal to emit `is_waiting`

**Files:**
- Modify: `session_scanner.py:151-162` (`SessionScanner.run()` method)

- [ ] **Step 1: Update `SessionScanner.run()` to include `is_waiting` in the emitted tuple**

In `session_scanner.py`, modify the `run()` method of `SessionScanner`. Change the loop body to also call `read_session_status()` and append the result as a 4th element:

```python
    def run(self) -> None:
        while not self._stop_event.is_set():
            results: List[Tuple[str, str, float, bool]] = []
            for _pid, session_id, cwd in scan_sessions(self._sessions_dir):
                usage = read_context_usage(self._projects_dir, cwd, session_id)
                if usage is None:
                    continue
                model, total_tokens = usage
                fill = compute_fill_pct(model, total_tokens)
                project_name = Path(cwd).name
                is_waiting = read_session_status(
                    self._projects_dir, cwd, session_id
                )
                results.append((project_name, model, fill, is_waiting))
            self.sessions_ready.emit(results)

            for _ in range(self._interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)
```

Also update the type comment on the signal:

```python
    # Emitted each cycle: list of (project_name, model, fill_pct, is_waiting) tuples
    sessions_ready = pyqtSignal(list)
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/test_session_scanner.py -v`
Expected: all tests PASS (signal type is `list` so the 4-tuple change is transparent)

- [ ] **Step 3: Commit**

```bash
git add session_scanner.py
git commit -m "feat: emit is_waiting flag from SessionScanner signal"
```

---

### Task 3: Color session labels by status in the visualizer

**Files:**
- Modify: `visualizer.py:364-415` (`_on_sessions()` method)

- [ ] **Step 1: Update `_on_sessions()` to use `is_waiting` for label color**

In `visualizer.py`, modify the `_on_sessions()` method. Change the for-loop to unpack the 4th element and set label colors accordingly:

```python
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
```

- [ ] **Step 2: Manually verify the widget**

Run: `pythonw visualizer.py`

Check:
- Sessions that are idle (other tabs where Claude finished) show green labels
- The current session (this one, actively working) shows muted grey labels
- Context bars are unchanged
- Widget resizes correctly

- [ ] **Step 3: Commit**

```bash
git add visualizer.py
git commit -m "feat: color session labels green when Claude is waiting for instructions"
```
