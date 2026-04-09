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


def test_encode_cwd_windows_path_with_space():
    cwd = "C:\\Users\\erwan\\my project"
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
