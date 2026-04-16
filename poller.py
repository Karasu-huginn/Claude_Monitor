# poller.py
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
POLL_INTERVAL = 300     # seconds between normal polls (endpoint rate-limits ~5 req/token; usage only changes every few hours)
BACKOFF_INTERVAL = 600  # seconds to wait after a 429


def read_credentials(path: Path = CREDENTIALS_PATH) -> str:
    """Return the OAuth access token from the credentials file."""
    with open(path) as f:
        data = json.load(f)
    return data["claudeAiOauth"]["accessToken"]


def parse_response(data: dict) -> Tuple[float, datetime]:
    """Return (utilization 0–1, reset_at UTC datetime) from the API response dict."""
    five_hour = data["five_hour"]
    utilization = float(five_hour["utilization"]) / 100.0
    resets_at = five_hour["resets_at"]
    if resets_at is None:
        raise ValueError("Session not started yet")
    reset_at = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    return utilization, reset_at


def format_countdown(reset_at: datetime) -> str:
    """Format time remaining until reset_at as 'Xh Ym', 'Xm', '<1m', or 'now'."""
    remaining = (reset_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return "now"
    total_minutes = int(remaining // 60)
    if total_minutes == 0:
        return "<1m"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def compute_time_utilization(reset_at: datetime, session_hours: float = 5.0) -> float:
    """Return fraction of the 5-hour session elapsed (0–1). 2h remaining → 0.60."""
    session_seconds = session_hours * 3600
    remaining = (reset_at - datetime.now(timezone.utc)).total_seconds()
    remaining = max(0.0, min(remaining, session_seconds))
    return 1.0 - remaining / session_seconds


def get_bar_color(utilization: float) -> str:
    """Return the hex progress-bar color for the given utilization (0–1)."""
    if utilization < 0.6:
        return "#00b894"
    if utilization < 0.8:
        return "#fdcb6e"
    if utilization < 0.9:
        return "#e17055"
    return "#d63031"


class Poller(QThread):
    """Background thread that polls the usage API and emits signals."""

    # Emitted on success: (utilization float, reset_at datetime)
    data_ready = pyqtSignal(float, object)
    # Emitted on any error: short human-readable message string
    error = pyqtSignal(str)

    def __init__(self, credentials_path: Path = CREDENTIALS_PATH) -> None:
        super().__init__()
        self._credentials_path = credentials_path
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            sleep_seconds = POLL_INTERVAL
            try:
                token = read_credentials(self._credentials_path)
                resp = requests.get(
                    USAGE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "anthropic-beta": "oauth-2025-04-20",
                        "Content-Type": "application/json",
                        "User-Agent": "claude-monitor/1.0",
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    utilization, reset_at = parse_response(resp.json())
                    self.data_ready.emit(utilization, reset_at)
                elif resp.status_code == 429:
                    sleep_seconds = BACKOFF_INTERVAL
                    self.error.emit("rate limited")
                elif resp.status_code in (401, 403):
                    self.error.emit("auth error — reopen Claude Code")
                else:
                    self.error.emit(f"HTTP {resp.status_code}")
            except FileNotFoundError:
                self.error.emit("auth error — reopen Claude Code")
            except requests.RequestException:
                self.error.emit("offline")
            except Exception as e:
                self.error.emit(str(e))

            # Sleep in 1-second ticks so stop() is responsive
            for _ in range(sleep_seconds):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
