"""
Base page providing a consistent layout: header bar (title + optional
right-side actions like a Deploy button), subtitle, divider, and a
content area filled by subclasses.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt


class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("page")

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(32, 28, 32, 28)
        self._root.setSpacing(12)

        # ---- Header bar: title on left, optional action widgets on right ----
        header_bar = QWidget()
        header_bar.setObjectName("pageHeaderBar")
        self._header_layout = QHBoxLayout(header_bar)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        self._header_layout.addWidget(title_label)
        self._header_layout.addStretch()  # actions get inserted before this

        self._root.addWidget(header_bar)

        # ---- Subtitle ----
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("pageSubtitle")
            subtitle_label.setWordWrap(True)
            self._root.addWidget(subtitle_label)

        # ---- Divider ----
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("pageDivider")
        self._root.addWidget(divider)

    # ------------------------------------------------------------------
    # API for subclasses
    # ------------------------------------------------------------------

    def add_header_action(self, widget: QWidget):
        """
        Add a widget to the right side of the header bar (e.g. a Deploy button).
        Inserted before the trailing stretch so multiple actions stack right-aligned.
        """
        # Insert just before the trailing stretch (last item)
        last = self._header_layout.count() - 1
        self._header_layout.insertWidget(last, widget)

    def add_content(self, widget: QWidget, stretch: int = 0):
        self._root.addWidget(widget, stretch=stretch)

    def add_stretch(self):
        self._root.addStretch()