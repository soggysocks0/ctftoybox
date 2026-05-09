import os
import sys
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from config import load_from_disk
from ui.theme import get_theme_manager
from ui.main_window import MainWindow


def _icon_path() -> str:
    """Locate ui/resources/icon.png in dev and in a frozen build."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "ui", "resources", "icon.png")
    return os.path.join(os.path.dirname(__file__), "ui", "resources", "icon.png")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CTFToyBox")
    app.setOrganizationName("CTFToyBox")

    icon_path = _icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    cfg = load_from_disk()
    theme_manager = get_theme_manager()
    theme_manager.apply(cfg.theme)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()