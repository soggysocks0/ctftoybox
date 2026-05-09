"""
Main application window.
Layout: Left sidebar (navigation) + Right content area (page stack).
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QFrame
)

from ui.sidebar import Sidebar
from ui.pages.instances_page import InstancesPage
from ui.pages.settings_page import SettingsPage
from ui.pages.networking_page import NetworkingPage
from ui.pages.storage_page import StoragePage
from ui.pages.management_page import ManagementPage
from ui.pages.addons_page import AddonsPage
from ui.pages.system_templates_page import SystemTemplatesPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CTFToyBox")
        self.resize(1200, 750)
        self.setMinimumSize(900, 600)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigation_changed.connect(self._on_nav_changed)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName("verticalSeparator")

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")

        # Pages keyed by sidebar nav key
        self.pages = {
            "instances":        InstancesPage(),
            "settings":         SettingsPage(),
            "networking":       NetworkingPage(),
            "storage":          StoragePage(),
            "management":       ManagementPage(),
            "addons":           AddonsPage(),
            "system_templates": SystemTemplatesPage(),
        }
        for page in self.pages.values():
            self.content_stack.addWidget(page)

        layout.addWidget(self.sidebar)
        layout.addWidget(separator)
        layout.addWidget(self.content_stack, stretch=1)

        self.sidebar.select_default()

    def _on_nav_changed(self, key: str):
        if key in self.pages:
            self.content_stack.setCurrentWidget(self.pages[key])