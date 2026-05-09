"""
Settings page.

Three sections:
  - Appearance: theme + language (language is non-functional placeholder)
  - Startup:    open-on-startup toggle (writes to OS autostart)
  - About:      GitHub FAQ URL field

All settings persist via QSettings. Theme + autostart take effect immediately.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QPushButton,
    QComboBox, QCheckBox, QMessageBox, QSizePolicy,
)

from ui.pages.base_page import BasePage
from ui.theme import get_theme_manager
from config import (
    AVAILABLE_LANGUAGES,
    get_config,
    set_language,
    set_open_on_startup as save_open_on_startup,
)
from config import autostart


# ---------------------------------------------------------------------------
# Reusable section card
# ---------------------------------------------------------------------------

class SettingsSection(QFrame):
    """A bordered card with a title, description, and pluggable content."""

    def __init__(self, title: str, description: str = ""):
        super().__init__()
        self.setObjectName("settingsSection")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(8)

        header = QLabel(title)
        header.setObjectName("settingsSectionTitle")
        outer.addWidget(header)

        if description:
            desc = QLabel(description)
            desc.setObjectName("settingsSectionDesc")
            desc.setWordWrap(True)
            outer.addWidget(desc)

        # Subclasses fill into self._body
        self._body = QVBoxLayout()
        self._body.setSpacing(10)
        outer.addLayout(self._body)

    def add_row(self, label_text: str, control: QWidget,
                hint: str = "") -> None:
        """One label + one control + optional hint underneath."""
        row = QVBoxLayout()
        row.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(12)
        lbl = QLabel(label_text)
        lbl.setObjectName("settingsFieldLabel")
        lbl.setMinimumWidth(140)
        top.addWidget(lbl)
        top.addWidget(control, stretch=1)
        row.addLayout(top)

        if hint:
            h = QLabel(hint)
            h.setObjectName("settingsFieldHint")
            h.setWordWrap(True)
            h.setContentsMargins(140 + 12, 0, 0, 0)
            row.addWidget(h)

        self._body.addLayout(row)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class SettingsPage(BasePage):
    def __init__(self):
        super().__init__(
            title="Settings",
            subtitle="Configure application preferences and runtime defaults."
        )

        cfg = get_config()

        # ---------------- Appearance ----------------
        appearance = SettingsSection(
            "Appearance",
            "Visual preferences. Applied immediately and persisted across runs."
        )

        self._theme_combo = QComboBox()
        self._theme_combo.setObjectName("settingsCombo")
        self._theme_combo.addItem("Dark",  "dark")
        self._theme_combo.addItem("Light", "light")
        self._set_combo_value(self._theme_combo, cfg.theme)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance.add_row("Theme", self._theme_combo)

        self._lang_combo = QComboBox()
        self._lang_combo.setObjectName("settingsCombo")
        for code, label in AVAILABLE_LANGUAGES:
            display = label if code == "en" else f"{label}  (translation pending)"
            self._lang_combo.addItem(display, code)
        self._set_combo_value(self._lang_combo, cfg.language)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        appearance.add_row(
            "Language", self._lang_combo,
            hint="Translations aren't bundled yet — only English is functional. "
                 "Your selection is saved and will apply once translations land."
        )

        self.add_content(appearance)

        # ---------------- Startup ----------------
        startup = SettingsSection(
            "Startup",
            "Whether CTF Manager should launch automatically when you log in."
        )

        startup_row = QWidget()
        startup_row_layout = QHBoxLayout(startup_row)
        startup_row_layout.setContentsMargins(0, 0, 0, 0)
        startup_row_layout.setSpacing(10)

        self._startup_checkbox = QCheckBox("Open CTF Manager on system startup")
        self._startup_checkbox.setObjectName("settingsCheckbox")
        # Reflect the actual OS state, not just the persisted value, on first
        # paint — they can diverge if the user removed the entry manually.
        actual = autostart.is_open_on_startup()
        self._startup_checkbox.setChecked(actual or cfg.open_on_startup)
        self._startup_checkbox.toggled.connect(self._on_startup_toggled)
        startup_row_layout.addWidget(self._startup_checkbox)
        startup_row_layout.addStretch()

        startup.add_row("On login", startup_row,
                        hint="Off by default. Writes a per-user autostart entry "
                             "(registry on Windows, ~/.config/autostart on Linux, "
                             "LaunchAgents on macOS).")

        self.add_content(startup)

        # Keep the theme combo in sync if the sidebar toggle is used
        get_theme_manager().theme_changed.connect(self._on_external_theme_change)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_combo_value(combo: QComboBox, target_data) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == target_data:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_theme_changed(self, _idx: int):
        choice = self._theme_combo.currentData()
        if not choice:
            return
        # ThemeManager.apply persists to config + emits signal
        get_theme_manager().apply(choice)

    def _on_external_theme_change(self, theme: str):
        """Sidebar toggle changed the theme — update the combo without recursion."""
        if self._theme_combo.currentData() == theme:
            return
        self._theme_combo.blockSignals(True)
        self._set_combo_value(self._theme_combo, theme)
        self._theme_combo.blockSignals(False)

    def _on_language_changed(self, _idx: int):
        code = self._lang_combo.currentData()
        if code:
            set_language(code)

    def _on_startup_toggled(self, checked: bool):
        ok = autostart.set_open_on_startup(checked)
        save_open_on_startup(checked if ok else False)
        if not ok:
            self._startup_checkbox.blockSignals(True)
            self._startup_checkbox.setChecked(False)
            self._startup_checkbox.blockSignals(False)
            QMessageBox.warning(
                self, "Couldn't update autostart",
                "Could not write the OS-level autostart entry. "
                "On Windows this requires write access to "
                "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run; "
                "on Linux/macOS, write access to your home directory."
            )