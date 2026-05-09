"""
Sidebar navigation panel.

Top: branding + nav buttons (Instances, Settings, etc.).
Bottom: utility buttons — theme toggle and GitHub FAQ link.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QButtonGroup, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from config import get_config
from ui.theme import get_theme_manager


class NavButton(QPushButton):
    """Flat, checkable button for primary sidebar navigation."""

    def __init__(self, label: str, key: str, icon_char: str = "•"):
        super().__init__()
        self.key = key
        self.setText(f"  {icon_char}    {label}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("navButton")
        self.setFixedHeight(42)


class FooterButton(QPushButton):
    """Smaller, non-checkable utility button for the sidebar footer."""

    def __init__(self, label: str, icon_char: str = "•"):
        super().__init__()
        self.setText(f"  {icon_char}   {label}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("footerButton")
        self.setFixedHeight(32)


class Sidebar(QWidget):
    navigation_changed = pyqtSignal(str)  # emits the key of the selected nav item

    NAV_ITEMS = [
        ("Instances",        "instances",        "▣"),
        ("Settings",         "settings",         "⚙"),
        ("Networking",       "networking",       "⇄"),
        ("Storage",          "storage",          "▤"),
        ("Management",       "management",       "☰"),
        ("Add-ons",          "addons",           "⊕"),
        ("System Templates", "system_templates", "⌬"),
    ]

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header / branding ---
        layout.addWidget(self._build_header())

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("sidebarDivider")
        layout.addWidget(divider)

        # --- Primary navigation ---
        layout.addWidget(self._build_nav(), stretch=1)

        # --- Footer (theme + faq + version) ---
        layout.addWidget(self._build_footer())

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("sidebarHeader")
        header.setFixedHeight(64)
        h = QVBoxLayout(header)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(0)

        title = QLabel("CTFToyBox")
        title.setObjectName("sidebarTitle")
        subtitle = QLabel("Challenge Orchestrator")
        subtitle.setObjectName("sidebarSubtitle")

        h.addWidget(title)
        h.addWidget(subtitle)
        return header

    def _build_nav(self) -> QWidget:
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 12, 8, 12)
        nav_layout.setSpacing(4)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._buttons: dict[str, NavButton] = {}

        for label, key, icon in self.NAV_ITEMS:
            btn = NavButton(label, key, icon)
            btn.clicked.connect(lambda _, k=key: self.navigation_changed.emit(k))
            self.button_group.addButton(btn)
            nav_layout.addWidget(btn)
            self._buttons[key] = btn

        nav_layout.addStretch()
        return nav_container

    def _build_footer(self) -> QWidget:
        """Theme toggle + GitHub FAQ + version line."""
        container = QWidget()
        container.setObjectName("sidebarFooterContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(2)

        # Theme toggle button — label updates with current theme
        self.theme_btn = FooterButton("Light theme", icon_char="☾")
        self.theme_btn.setToolTip("Switch between dark and light themes")
        self.theme_btn.clicked.connect(self._on_theme_toggle)
        layout.addWidget(self.theme_btn)

        # GitHub FAQ button — opens configured URL when set
        self.faq_btn = FooterButton("GitHub FAQ", icon_char="❔")
        self.faq_btn.setToolTip("Open the project's GitHub FAQ page")
        self.faq_btn.clicked.connect(self._on_faq_clicked)
        layout.addWidget(self.faq_btn)

        # Version label
        version = QLabel("v0.1.0")
        version.setObjectName("sidebarFooter")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setFixedHeight(22)
        layout.addWidget(version)

        # Sync button label with current theme on startup, and on every change
        tm = get_theme_manager()
        self._sync_theme_button(tm.current)
        tm.theme_changed.connect(self._sync_theme_button)

        return container

    # ------------------------------------------------------------------
    # Slots / handlers
    # ------------------------------------------------------------------

    def _on_theme_toggle(self):
        get_theme_manager().toggle()

    def _sync_theme_button(self, theme: str):
        """Show the *target* theme on the button so the action is clear."""
        if theme == "dark":
            self.theme_btn.setText("  ☀   Light theme")
        else:
            self.theme_btn.setText("  ☾   Dark theme")

    def _on_faq_clicked(self):
        QDesktopServices.openUrl(QUrl("https://github.com/soggysocks0"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_default(self):
        first_key = self.NAV_ITEMS[0][1]
        self._buttons[first_key].setChecked(True)
        self.navigation_changed.emit(first_key)