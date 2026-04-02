# poller.py
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import requests
from PyQt6.QtCore import QThread, pyqtSignal

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://claude.ai/api/oauth/usage"
POLL_INTERVAL = 60      # seconds between normal polls
BACKOFF_INTERVAL = 300  # seconds to wait after a 429


def read_credentials(path: Path = CREDENTIALS_PATH) -> str:
    """Return the OAuth access token from the credentials file."""
    with open(path) as f:
        data = json.load(f)
    return data["claudeAiOauth"]["accessToken"]


def parse_response(data: dict) -> Tuple[float, datetime]:
    """Return (utilization 0–1, reset_at UTC datetime) from the API response dict."""
    five_hour = data["five_hour"]
    utilization = float(five_hour["utilization"])
    reset_at = datetime.fromisoformat(five_hour["reset_at"].replace("Z", "+00:00"))
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
    pass  # implemented in Task 4
