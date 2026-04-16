# Claude Tokens Visualizer — Design Spec

**Date:** 2026-04-02
**Status:** Approved

---

## Overview

A standalone Python desktop widget that displays Claude Code's 5-hour session token utilization in real time. It sits in a corner of the screen and refreshes automatically by polling Anthropic's OAuth usage API.

---

## Architecture

### Structure

Single Python file. Two threads:

- **Main thread**: PyQt6 UI. Receives data via Qt signals and redraws.
- **Poller thread**: Background `QThread` that polls the usage API on a fixed interval. Reads credentials fresh from disk on every poll so it picks up token refreshes that Claude Code manages automatically.

### Data Source

**Endpoint**: `GET https://claude.ai/api/oauth/usage`

**Authentication**: Bearer token read from `~/.claude/.credentials.json` on each poll. Claude Code refreshes this file automatically; reading it fresh every cycle avoids token expiry issues.

Credentials file structure:
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "expiresAt": 1234567890000
  }
}
```
Token key path: `credentials["claudeAiOauth"]["accessToken"]`. `expiresAt` is a Unix timestamp in **milliseconds**. If the token is expired, treat it as an auth error (Claude Code will refresh it on next use).

**Response fields used**:
- `five_hour.utilization` — float 0–1, session usage percentage
- `five_hour.reset_at` — ISO 8601 timestamp, when the 5-hour window resets

### Poll Interval

- Normal: **60 seconds**
- After a 429 response: **5 minutes**
- Countdown timer updates every **1 second** locally from the last known `reset_at` — no extra API calls

---

## Visual Design

### Window

- Frameless, always-on-top PyQt6 window
- Size: ~300×160px
- Default position: bottom-right corner of primary screen, 16px margin
- Draggable by clicking anywhere on the panel
- Position is not persisted between runs

### Layout (top to bottom)

| Element | Description |
|---|---|
| **Header row** | "Claude Code · 5h Session" label (left) + `×` close button (right) |
| **Progress bar** | Full width, rounded, color-coded by utilization |
| **Big percentage** | Large centered text, color matches the bar |
| **Subtitle row** | "X% used" (left) · "resets in Xh Ym" (right, live countdown) |
| **Footer** | Tiny "last updated HH:MM:SS" + pulsing dot while polling |

### Color Scheme

| Range | Color | Hex |
|---|---|---|
| 0–60% | Green | `#00b894` |
| 60–80% | Yellow | `#fdcb6e` |
| 80–90% | Orange | `#e17055` |
| 90–100% | Red | `#d63031` |

Background: `#1a1a2e` · Text: `#ffffff`

### Displayed Metric

The API returns utilization as a percentage only (no raw token counts). The widget shows:
- Utilization percentage (e.g., `73%`)
- Live reset countdown (e.g., `resets in 2h 14m`)

Raw token counts are not shown (plan ceiling not available from the API).

---

## Error States

| Condition | Behavior |
|---|---|
| Credentials file missing / token absent | Bar goes grey · text: "Auth error — reopen Claude Code" |
| Network error | Keeps last known values · footer shows "offline" in orange |
| API 429 (rate limited) | Backs off to 5-minute interval · footer shows "rate limited" |
| First launch (no data yet) | Loading spinner in place of the bar |

---

## Interaction

- **Drag**: click and drag anywhere on the panel to reposition
- **Close**: click `×` button or right-click anywhere → quit
- **No tray icon, no system menu, no persistence**

---

## Dependencies

- `PyQt6` — UI framework
- `requests` — HTTP polling
- Standard library only beyond those two (`json`, `threading`, `datetime`, `pathlib`)

---

## Out of Scope

- Raw token count display (plan ceiling not exposed by API)
- Multi-monitor awareness beyond primary screen default position
- Tray icon or minimization
- Configuration UI (poll interval, position, etc.)
- Support for API-key-based auth (only OAuth / claude.ai accounts)
