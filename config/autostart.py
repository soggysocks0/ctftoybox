r"""
Cross-platform "open on startup" helper.

  Windows: HKCU\Software\Microsoft\Windows\CurrentVersion\Run registry value
  macOS:   ~/Library/LaunchAgents/com.ctfmanager.plist
  Linux:   ~/.config/autostart/ctfmanager.desktop  (XDG Autostart)

All operations are best-effort and return False on any error so the
Settings UI can show the user what happened without exception traffic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


_APP_NAME = "CTFManager"


# ---------------------------------------------------------------------------
# Resolve the command Windows / Linux / macOS should run on login.
# ---------------------------------------------------------------------------

def _launch_command() -> str:
    """The command line to run at login. Quoted for the OS that needs it."""
    py = sys.executable
    # Resolve main.py relative to this file (../main.py from config/).
    main_path = Path(__file__).resolve().parent.parent / "main.py"
    if sys.platform == "win32":
        return f'"{py}" "{main_path}"'
    return f'"{py}" "{main_path}"'


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _set_windows(enabled: bool) -> bool:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        )
        try:
            if enabled:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass  # already absent
        finally:
            winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _is_set_windows() -> bool:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Linux (XDG Autostart)
# ---------------------------------------------------------------------------

def _linux_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / "ctfmanager.desktop"


def _set_linux(enabled: bool) -> bool:
    path = _linux_autostart_path()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={_APP_NAME}\n"
                f"Exec={_launch_command()}\n"
                "X-GNOME-Autostart-enabled=true\n"
                "Terminal=false\n"
            )
            path.write_text(content, encoding="utf-8")
        else:
            if path.exists():
                path.unlink()
        return True
    except OSError:
        return False


def _is_set_linux() -> bool:
    return _linux_autostart_path().exists()


# ---------------------------------------------------------------------------
# macOS (LaunchAgent)
# ---------------------------------------------------------------------------

def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.ctfmanager.plist"


def _set_mac(enabled: bool) -> bool:
    path = _mac_plist_path()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            py = sys.executable
            main_path = Path(__file__).resolve().parent.parent / "main.py"
            plist = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.ctfmanager</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py}</string>
        <string>{main_path}</string>
    </array>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
"""
            path.write_text(plist, encoding="utf-8")
        else:
            if path.exists():
                path.unlink()
        return True
    except OSError:
        return False


def _is_set_mac() -> bool:
    return _mac_plist_path().exists()


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

def set_open_on_startup(enabled: bool) -> bool:
    """Enable or disable opening on system login. Returns True on success."""
    if sys.platform == "win32":
        return _set_windows(enabled)
    if sys.platform == "darwin":
        return _set_mac(enabled)
    return _set_linux(enabled)


def is_open_on_startup() -> bool:
    """Whether the OS-level autostart entry currently exists."""
    if sys.platform == "win32":
        return _is_set_windows()
    if sys.platform == "darwin":
        return _is_set_mac()
    return _is_set_linux()