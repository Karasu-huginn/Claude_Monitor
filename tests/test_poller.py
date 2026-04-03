import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from poller import read_credentials, parse_response, format_countdown, get_bar_color, compute_time_utilization


# --- read_credentials ---

def test_read_credentials_returns_token(tmp_path):
    p = tmp_path / ".credentials.json"
    p.write_text(json.dumps({"claudeAiOauth": {"accessToken": "sk-ant-oat01-test"}}))
    assert read_credentials(p) == "sk-ant-oat01-test"

def test_read_credentials_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_credentials(tmp_path / "no_such_file.json")

def test_read_credentials_raises_on_wrong_schema(tmp_path):
    p = tmp_path / ".credentials.json"
    p.write_text('{"other": {}}')
    with pytest.raises(KeyError):
        read_credentials(p)


# --- parse_response ---

def test_parse_response_returns_utilization_and_reset_at():
    data = {"five_hour": {"utilization": 73.0, "resets_at": "2026-04-02T16:00:00Z"}}
    utilization, reset_at = parse_response(data)
    assert utilization == pytest.approx(0.73)
    assert reset_at == datetime(2026, 4, 2, 16, 0, 0, tzinfo=timezone.utc)

def test_parse_response_raises_on_missing_five_hour():
    with pytest.raises(KeyError):
        parse_response({})

def test_parse_response_raises_on_missing_utilization():
    with pytest.raises(KeyError):
        parse_response({"five_hour": {"resets_at": "2026-04-02T16:00:00Z"}})

def test_parse_response_raises_on_missing_reset_at():
    with pytest.raises(KeyError):
        parse_response({"five_hour": {"utilization": 50.0}})

def test_parse_response_raises_value_error_when_resets_at_is_none():
    data = {"five_hour": {"utilization": 0.0, "resets_at": None}}
    with pytest.raises(ValueError, match="Session not started yet"):
        parse_response(data)


# --- format_countdown ---

def test_format_countdown_hours_and_minutes():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=2, minutes=14, seconds=30)
    assert format_countdown(reset_at) == "2h 14m"

def test_format_countdown_minutes_only():
    reset_at = datetime.now(timezone.utc) + timedelta(minutes=7, seconds=55)
    assert format_countdown(reset_at) == "7m"

def test_format_countdown_expired_returns_now():
    reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert format_countdown(reset_at) == "now"

def test_format_countdown_less_than_one_minute():
    reset_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    assert format_countdown(reset_at) == "<1m"


# --- compute_time_utilization ---

def test_compute_time_utilization_2h_remaining():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=2)
    assert compute_time_utilization(reset_at) == pytest.approx(0.60)

def test_compute_time_utilization_full_session_remaining():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=5)
    assert compute_time_utilization(reset_at) == pytest.approx(0.0, abs=1e-4)

def test_compute_time_utilization_expired_returns_1():
    reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert compute_time_utilization(reset_at) == pytest.approx(1.0)

def test_compute_time_utilization_clamps_when_over_5h():
    reset_at = datetime.now(timezone.utc) + timedelta(hours=10)
    assert compute_time_utilization(reset_at) == pytest.approx(0.0)


# --- get_bar_color ---

def test_get_bar_color_green_below_60():
    assert get_bar_color(0.0) == "#00b894"
    assert get_bar_color(0.59) == "#00b894"

def test_get_bar_color_yellow_60_to_80():
    assert get_bar_color(0.6) == "#fdcb6e"
    assert get_bar_color(0.79) == "#fdcb6e"

def test_get_bar_color_orange_80_to_90():
    assert get_bar_color(0.8) == "#e17055"
    assert get_bar_color(0.89) == "#e17055"

def test_get_bar_color_red_90_and_above():
    assert get_bar_color(0.9) == "#d63031"
    assert get_bar_color(1.0) == "#d63031"
