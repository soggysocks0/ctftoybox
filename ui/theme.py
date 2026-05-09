"""
Theme manager.

Loads `.qss` files from ui/themes/ and applies them to the QApplication.
Emits a signal when the theme changes so widgets that need to refresh
(e.g. icons drawn from code) can react.
"""

from __future__ import annotations

import os
import sys
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


def _themes_dir() -> str:
    """Locate ui/themes/ in dev and in a PyInstaller --onefile bundle."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "ui", "themes")
    return os.path.join(os.path.dirname(__file__), "themes")


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)  # emits "dark" or "light"

    AVAILABLE = ("dark", "light")

    def __init__(self, initial: str = "dark"):
        super().__init__()
        self._current = initial

    @property
    def current(self) -> str:
        return self._current

    def apply(self, theme: str):
        """Load and apply the named theme. Falls back to dark on any error."""
        if theme not in self.AVAILABLE:
            theme = "dark"

        path = os.path.join(_themes_dir(), f"{theme}.qss")
        try:
            with open(path, "r", encoding="utf-8") as f:
                qss = f.read()
        except OSError:
            qss = ""

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)

        self._current = theme

        # Persist to settings — best-effort; don't crash on import-time call.
        try:
            from config import set_theme
            set_theme(theme)
        except Exception:
            pass

        self.theme_changed.emit(theme)

    def toggle(self):
        """Flip between dark and light."""
        self.apply("light" if self._current == "dark" else "dark")


# Singleton accessor — there's only one theme at a time application-wide.
_theme_manager: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager