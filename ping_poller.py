# ping_poller.py
from __future__ import annotations

import platform
import re
import subprocess
import threading
import time
from typing import Tuple, Optional

from PyQt6.QtCore import QThread, pyqtSignal

TARGET = "8.8.8.8"
TIMEOUT = 1
PING_INTERVAL = 2  # seconds between pings

LATENCY_RE = re.compile(r'time[=<](\d+\.?\d*)\s*ms', re.IGNORECASE)


def ping(target: str = TARGET, timeout: int = TIMEOUT) -> Tuple[bool, Optional[float]]:
    """Ping target once. Return (success, latency_ms_or_None)."""
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), target]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), target]

    try:
        kwargs: dict = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout + 1,
        )
        if system == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
        if result.returncode != 0:
            return False, None
        match = LATENCY_RE.search(result.stdout or "")
        ms = float(match.group(1)) if match else None
        return True, ms
    except Exception:
        return False, None


class PingPoller(QThread):
    """Background thread that pings and emits results."""

    ping_ready = pyqtSignal(bool, object)  # (online, latency_ms_or_None)

    def __init__(self, target: str = TARGET, interval: int = PING_INTERVAL) -> None:
        super().__init__()
        self._target = target
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            ok, ms = ping(self._target)
            self.ping_ready.emit(ok, ms)
            for _ in range(self._interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
