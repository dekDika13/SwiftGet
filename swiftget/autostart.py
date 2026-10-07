"""Jalankan SwiftGet otomatis saat login (Windows: registry Run, macOS: LaunchAgent, Linux: autostart)."""
import os, sys
from pathlib import Path

NAME = "SwiftGet"


def _command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--background"]
    return [sys.executable, str(Path(__file__).resolve().parent.parent / "run.py"), "--background"]


def enable(on: bool) -> bool:
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE) as k:
                if on:
                    winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, " ".join(f'"{c}"' for c in _command()))
                else:
                    try:
                        winreg.DeleteValue(k, NAME)
                    except FileNotFoundError:
                        pass
        elif sys.platform == "darwin":
            p = Path.home() / "Library" / "LaunchAgents" / "com.swiftget.app.plist"
            if on:
                args = "".join(f"<string>{c}</string>" for c in _command())
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                             '"http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>'
                             f'<key>Label</key><string>com.swiftget.app</string><key>ProgramArguments</key><array>{args}</array>'
                             '<key>RunAtLoad</key><true/></dict></plist>')
            elif p.exists():
                p.unlink()
        else:
            p = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "swiftget.desktop"
            if on:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("[Desktop Entry]\nType=Application\nName=SwiftGet\nExec=" +
                             " ".join(f'"{c}"' for c in _command()) + "\nX-GNOME-Autostart-enabled=true\n")
            elif p.exists():
                p.unlink()
        return True
    except Exception:
        return False


def is_enabled() -> bool:
    """Status sebenarnya di OS (bukan hanya di pengaturan), karena installer Windows juga bisa mengaktifkannya."""
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, NAME)
                return True
        if sys.platform == "darwin":
            return (Path.home() / "Library" / "LaunchAgents" / "com.swiftget.app.plist").exists()
        return (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "swiftget.desktop").exists()
    except OSError:
        return False
