# Start Menu Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `install.py` — a script that creates a Windows Start Menu shortcut launching `visualizer.py` via `pythonw.exe` (no terminal window).

**Architecture:** One new file (`install.py`) with three pure helper functions (`get_pythonw`, `get_start_menu`, `create_shortcut`) and a `main()` entry point. Helpers are unit-tested; the PowerShell call is covered by the helpers' tests and verified manually.

**Tech Stack:** Python stdlib only (`subprocess`, `sys`, `os`, `pathlib`). Tests use `pytest` and `monkeypatch`.

---

### Task 1: Write failing tests for the two pure helpers

**Files:**
- Modify: `tests/test_poller.py` — no, wrong file
- Create: `tests/test_install.py`

- [ ] **Step 1: Create `tests/test_install.py` with failing tests**

```python
# tests/test_install.py
import pytest
from pathlib import Path


# --- get_pythonw ---

def test_get_pythonw_returns_sibling_pythonw(tmp_path):
    # Simulate a python.exe next to a pythonw.exe
    fake_python = tmp_path / "python.exe"
    fake_python.touch()
    fake_pythonw = tmp_path / "pythonw.exe"
    fake_pythonw.touch()

    from install import get_pythonw
    assert get_pythonw(str(fake_python)) == fake_pythonw


def test_get_pythonw_raises_when_missing(tmp_path):
    fake_python = tmp_path / "python.exe"
    fake_python.touch()
    # no pythonw.exe created

    from install import get_pythonw
    with pytest.raises(FileNotFoundError, match="pythonw.exe not found"):
        get_pythonw(str(fake_python))


# --- get_start_menu ---

def test_get_start_menu_returns_path(tmp_path, monkeypatch):
    start_menu = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu.mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from install import get_start_menu
    assert get_start_menu() == start_menu


def test_get_start_menu_raises_when_appdata_missing(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)

    from install import get_start_menu
    with pytest.raises(EnvironmentError, match="APPDATA"):
        get_start_menu()


def test_get_start_menu_raises_when_path_missing(tmp_path, monkeypatch):
    # APPDATA set but the Programs folder does not exist
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from install import get_start_menu
    with pytest.raises(FileNotFoundError, match="Start Menu not found"):
        get_start_menu()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_install.py -v
```

Expected: 5 errors — `ModuleNotFoundError: No module named 'install'`

---

### Task 2: Implement `install.py`

**Files:**
- Create: `install.py`

- [ ] **Step 1: Write `install.py`**

```python
# install.py
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_pythonw(executable: str) -> Path:
    """Return the pythonw.exe path beside the given python executable."""
    pythonw = Path(executable).parent / "pythonw.exe"
    if not pythonw.exists():
        raise FileNotFoundError(f"pythonw.exe not found at {pythonw}")
    return pythonw


def get_start_menu() -> Path:
    """Return the user-level Start Menu Programs folder."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise EnvironmentError("APPDATA environment variable is not set")
    path = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if not path.exists():
        raise FileNotFoundError(f"Start Menu not found at {path}")
    return path


def create_shortcut(shortcut_path: Path, pythonw: Path, script: Path, workdir: Path) -> None:
    """Create a Windows .lnk shortcut via PowerShell's WScript.Shell COM object."""
    ps = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{pythonw}"; '
        f'$s.Arguments = \'"{script}"\'; '
        f'$s.WorkingDirectory = "{workdir}"; '
        f'$s.Description = "Claude Code token usage visualizer"; '
        f'$s.Save()'
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell failed:\n{result.stderr.strip()}")


def main() -> None:
    try:
        pythonw = get_pythonw(sys.executable)
        start_menu = get_start_menu()
        script = Path(__file__).resolve().parent / "visualizer.py"
        workdir = script.parent
        shortcut = start_menu / "Claude Tokens Visualizer.lnk"
        create_shortcut(shortcut, pythonw, script, workdir)
        print(f"Shortcut created: {shortcut}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the tests**

```
pytest tests/test_install.py -v
```

Expected: 5 passed

- [ ] **Step 3: Run the full test suite to confirm nothing is broken**

```
pytest -v
```

Expected: all tests pass (previously 15, now 20)

- [ ] **Step 4: Commit**

```bash
git add install.py tests/test_install.py
git commit -m "feat: install.py creates Start Menu shortcut for visualizer"
```

---

### Task 3: Smoke test

- [ ] **Step 1: Run the installer**

```
python install.py
```

Expected output (path will differ):
```
Shortcut created: C:\Users\<you>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Claude Tokens Visualizer.lnk
```

- [ ] **Step 2: Verify the shortcut appears in Start Menu**

Open Start Menu and type "Claude Tokens Visualizer" — the shortcut should appear.

- [ ] **Step 3: Launch from Start Menu**

Click the shortcut. The visualizer window should appear with no terminal window behind it.
