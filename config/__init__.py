"""Application configuration — runtime settings, links, etc."""

from config.settings import (
    AppConfig,
    AVAILABLE_LANGUAGES,
    get_config,
    load_from_disk,
    save,
    set_theme,
    set_language,
    set_github_faq_url,
    set_open_on_startup,
)

__all__ = [
    "AppConfig",
    "AVAILABLE_LANGUAGES",
    "get_config",
    "load_from_disk",
    "save",
    "set_theme",
    "set_language",
    "set_github_faq_url",
    "set_open_on_startup",
]