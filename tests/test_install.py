import pytest
from pathlib import Path
from install import get_pythonw, get_start_menu


# --- get_pythonw ---

def test_get_pythonw_returns_sibling_pythonw(tmp_path):
    # Simulate a python.exe next to a pythonw.exe
    fake_python = tmp_path / "python.exe"
    fake_python.touch()
    fake_pythonw = tmp_path / "pythonw.exe"
    fake_pythonw.touch()

    assert get_pythonw(str(fake_python)) == fake_pythonw


def test_get_pythonw_raises_when_missing(tmp_path):
    fake_python = tmp_path / "python.exe"
    fake_python.touch()
    # no pythonw.exe created

    with pytest.raises(FileNotFoundError, match="pythonw.exe not found"):
        get_pythonw(str(fake_python))


# --- get_start_menu ---

def test_get_start_menu_returns_path(tmp_path, monkeypatch):
    start_menu = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu.mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert get_start_menu() == start_menu


def test_get_start_menu_raises_when_appdata_missing(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)

    with pytest.raises(EnvironmentError, match="APPDATA"):
        get_start_menu()


def test_get_start_menu_raises_when_path_missing(tmp_path, monkeypatch):
    # APPDATA set but the Programs folder does not exist
    monkeypatch.setenv("APPDATA", str(tmp_path))

    with pytest.raises(FileNotFoundError, match="Start Menu not found"):
        get_start_menu()
