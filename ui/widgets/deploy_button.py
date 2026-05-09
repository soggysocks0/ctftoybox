"""
DeployButton — primary action button on the Instances page.

Behaves like a split-button menu: clicking it pops up a list of CTF
categories drawn from the vulnerability registry. Selecting a category
emits `category_selected(Category)` so the parent page can act on it.

We deliberately keep this presentation-only — no deployment logic here.
The page that hosts this widget decides what to do when a category is
chosen (open a deploy wizard, list templates, etc.).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolButton, QMenu

from vulnerabilities import Category


# Icons per category — single-char glyphs keep us font-only for now.
# Swap for QIcon(svg) later if/when we want proper iconography.
_CATEGORY_ICONS: dict[Category, str] = {
    Category.REVERSE_ENGINEERING: "⚙",
    Category.BINARY_EXPLOITATION: "⚡",
    Category.WEB_EXPLOITATION:    "🌐",
    Category.FORENSICS:           "🔍",
    Category.CUSTOM:              "✦",
}


class DeployButton(QToolButton):
    """Primary 'Deploy ▾' button that drops down a category menu."""

    category_selected = pyqtSignal(object)  # emits a Category enum value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("deployButton")
        self.setText("  Deploy")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumHeight(36)
        self.setMinimumWidth(130)

        self._menu = QMenu(self)
        self._populate_menu()
        self.setMenu(self._menu)

    def _populate_menu(self):
        """Build menu entries from the Category enum.

        Custom is separated from the standard categories with a divider
        so it reads as a distinct option ("bring your own challenge").
        """
        standard = [c for c in Category if c is not Category.CUSTOM]
        for cat in standard:
            self._menu.addAction(self._make_action(cat))

        self._menu.addSeparator()
        self._menu.addAction(self._make_action(Category.CUSTOM))

    def _make_action(self, category: Category) -> QAction:
        icon = _CATEGORY_ICONS.get(category, "•")
        action = QAction(f"  {icon}    {category.display_name}", self)
        action.setToolTip(category.description)
        action.triggered.connect(lambda _, c=category: self.category_selected.emit(c))
        return action