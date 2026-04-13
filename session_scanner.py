# session_scanner.py
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import threading
import time
from pathlib import Path
from typing import List, Tuple, Optional

from PyQt6.QtCore import QThread, pyqtSignal

CLAUDE_DIR = Path.home() / ".claude"
SESSIONS_DIR = CLAUDE_DIR / "sessions"
PROJECTS_DIR = CLAUDE_DIR / "projects"

MODEL_CONTEXT_LIMITS = {
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 1_000_000,
}
DEFAULT_CONTEXT_LIMIT = 1_000_000

SCAN_INTERVAL = 15  # seconds between scans


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

    Replaces path separators, colons, underscores, and spaces with dashes.
    E.g. 'C:\\Users\\erwan\\my_project' -> 'C--Users-erwan-my-project'
    """
    return re.sub(r'[\\/:_ ]', '-', cwd).rstrip('-')


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
        read_size = min(file_size, 65536)
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
