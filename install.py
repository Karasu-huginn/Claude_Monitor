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
