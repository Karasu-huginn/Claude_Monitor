# Claude Monitor

A lightweight desktop widget that gives you at-a-glance monitoring of your [Claude Code](https://docs.anthropic.com/en/docs/claude-code) sessions. Track token usage, session time, network status, and context window fill — all from a sleek, always-on-top panel.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-6.4+-41cd52?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blue?style=flat-square)

## Overview

Claude Code gives you a 5-hour sliding window of token usage, but there's no built-in way to see how much you've consumed or when it resets. Claude Monitor fills that gap with a frameless, draggable desktop widget that polls the Anthropic OAuth API and scans your local session files to surface:

- **Token usage** — color-coded progress bar showing consumption within the 5-hour window
- **Session countdown** — live timer until your usage window resets
- **Network status** — real-time ping with latency display
- **Context window fill** — per-session percentage of the model's context used, with a compaction threshold marker
- **Session activity** — visual indicator of whether Claude is waiting for input or actively working

## Features

- Frameless, always-on-top widget that stays out of your way
- Drag anywhere to reposition
- Color-coded thresholds (green / yellow / orange / red) for quick scanning
- Auto-discovers active Claude Code sessions
- Multi-session context tracking with auto-expanding list
- Windows Start Menu integration via installer script
- Zero configuration — reads credentials from your existing Claude Code setup

## Prerequisites

- **Python 3.10+**
- **An active Claude Code installation** — the monitor reads OAuth credentials from `~/.claude/.credentials.json`, which Claude Code manages automatically

## Getting started

1. **Clone the repository**

   ```bash
   git clone https://github.com/ermusic/claude-monitor.git
   cd claude-monitor
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the monitor**

   ```bash
   python visualizer.py
   ```

   The widget appears in the top-right corner of your screen.

### Windows Start Menu shortcut

```bash
python install.py
```

This creates a shortcut in your Start Menu so you can launch Claude Monitor like any other app.

## How it works

Claude Monitor is built from four independent components that run as background threads:

| Component | File | What it does |
|---|---|---|
| **Token Poller** | `poller.py` | Polls `api.anthropic.com/api/oauth/usage` every 5 minutes for token utilization and reset time |
| **Ping Monitor** | `ping_poller.py` | Pings `8.8.8.8` every 2 seconds to track network connectivity and latency |
| **Session Scanner** | `session_scanner.py` | Scans `~/.claude/sessions/` every 15 seconds to discover active sessions and read context usage from JSONL logs |
| **Visualizer** | `visualizer.py` | PyQt6 UI that composes all data into the desktop widget |

> [!NOTE]
> The monitor is read-only — it never writes to Claude Code's files or sends any data beyond the OAuth usage API call that Claude Code itself uses.

## Running tests

```bash
pytest
```

All 50 tests cover credential reading, API response parsing, ping handling, session discovery, context extraction, and the installation script.
