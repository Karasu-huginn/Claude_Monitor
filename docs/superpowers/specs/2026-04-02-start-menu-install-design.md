# Start Menu Installer — Design Spec

**Date:** 2026-04-02
**Status:** Approved

---

## Overview

A single `install.py` script at the project root. Run once with `python install.py` to create a Windows Start Menu shortcut that launches the visualizer without a terminal window.

---

## Behaviour

1. Derive `pythonw.exe` from `sys.executable` (same Python installation; suppresses the console window on launch).
2. Resolve the project directory from `__file__`.
3. Locate the user-level Start Menu folder via `%APPDATA%\Microsoft\Windows\Start Menu\Programs\`.
4. Shell out to PowerShell to create `Claude Tokens Visualizer.lnk` with:
   - **Target:** `pythonw.exe`
   - **Arguments:** `"<abs-path-to-visualizer.py>"`
   - **Working directory:** project root
   - **Description:** `"Claude Code token usage visualizer"`
5. Print a single success line showing the shortcut path, or a descriptive error message.

---

## Error Handling

| Condition | Behaviour |
|-----------|-----------|
| `pythonw.exe` not found beside `python.exe` | Exit with error message |
| PowerShell exits non-zero | Print stderr and exit with error message |
| Start Menu path does not exist | Exit with error message |

---

## Out of Scope

- Custom icon
- Uninstall command (user deletes `Claude Tokens Visualizer.lnk` manually)
- Per-machine (All Users) Start Menu
- Arguments or configuration

---

## Files Changed

| File | Change |
|------|--------|
| `install.py` | New file — the installer script |
