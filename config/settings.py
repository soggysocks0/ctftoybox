"""
Application configuration.

Backed by QSettings so values survive across runs. Falls back to in-memory
defaults if QSettings can't be initialized (no QApplication yet, etc.) so
imports never blow up.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QSettings


# Settings keys live under the org/app namespace QApplication sets.
_ORG = "CTFManager"
_APP = "CTFManager"


# ---------------------------------------------------------------------------
# Available languages — only "en" actually functions today; the rest are
# placeholders for translations to land later.
# ---------------------------------------------------------------------------

AVAILABLE_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en",    "English"),
    ("es",    "Español"),
    ("fr",    "Français"),
    ("de",    "Deutsch"),
    ("ja",    "日本語"),
    ("zh-CN", "简体中文"),
)


# ---------------------------------------------------------------------------
# In-memory mirror — lets non-Qt code read settings without touching QSettings
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    theme:           str  = "dark"          # "dark" | "light"
    language:        str  = "en"            # ISO code; only "en" works for now
    github_faq_url:  str  = ""
    open_on_startup: bool = False


_config = AppConfig()
_loaded_from_disk = False


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def _qs() -> QSettings:
    return QSettings(_ORG, _APP)


def load_from_disk() -> AppConfig:
    """Pull values from QSettings into the in-memory mirror.

    Safe to call multiple times — last call wins. Called by main.py at
    startup once the QApplication exists.
    """
    global _loaded_from_disk
    qs = _qs()

    _config.theme           = str(qs.value("theme",          _config.theme))
    _config.language        = str(qs.value("language",       _config.language))
    _config.github_faq_url  = str(qs.value("github_faq_url", _config.github_faq_url))

    # QSettings on some platforms returns "true"/"false" strings instead of
    # bools. Normalize.
    raw_oos = qs.value("open_on_startup", _config.open_on_startup)
    if isinstance(raw_oos, str):
        _config.open_on_startup = raw_oos.lower() in ("1", "true", "yes")
    else:
        _config.open_on_startup = bool(raw_oos)

    _loaded_from_disk = True
    return _config


def save() -> None:
    qs = _qs()
    qs.setValue("theme",           _config.theme)
    qs.setValue("language",        _config.language)
    qs.setValue("github_faq_url",  _config.github_faq_url)
    qs.setValue("open_on_startup", _config.open_on_startup)
    qs.sync()


def get_config() -> AppConfig:
    """Return the current in-memory config. Read-only by convention."""
    return _config


# ---------------------------------------------------------------------------
# Setters (mutate + persist)
# ---------------------------------------------------------------------------

def set_theme(theme: str) -> None:
    _config.theme = theme
    save()


def set_language(lang: str) -> None:
    _config.language = lang
    save()


def set_github_faq_url(url: str) -> None:
    _config.github_faq_url = url.strip()
    save()


def set_open_on_startup(enabled: bool) -> None:
    _config.open_on_startup = bool(enabled)
    save()