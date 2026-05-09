"""
Add-ons page.

Two halves:
  - Top: drop zone for users importing their own template bundles
         (drag and drop is wired visually; actual import logic lands later).
  - Bottom: the bundled "starter scaffolds" — one customizable template per
            CTF category — that users can download to a folder of their choice
            as a starting point for building their own templates.
"""

from __future__ import annotations

import os
import shutil
import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QDesktopServices
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QListWidget,
    QListWidgetItem, QSizePolicy, QPushButton, QFileDialog, QMessageBox,
)

from ui.pages.base_page import BasePage


# ---------------------------------------------------------------------------
# Drop zone (unchanged from the previous iteration)
# ---------------------------------------------------------------------------

class DropZone(QFrame):
    def __init__(self, on_files_dropped):
        super().__init__()
        self.setObjectName("dropZone")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptDrops(True)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._on_files_dropped = on_files_dropped

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("⤓")
        icon.setObjectName("dropZoneIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Drop add-on folders here")
        title.setObjectName("dropZoneTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(
            "Drag a customized template folder (with <b>template.json</b> + "
            "<b>Dockerfile</b>) into this area to import it as a template."
        )
        hint.setObjectName("dropZoneHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(hint)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hover", True)
            self.style().unpolish(self); self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("hover", False)
        self.style().unpolish(self); self.style().polish(self)
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self._on_files_dropped(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


# ---------------------------------------------------------------------------
# Bundled scaffold metadata
# ---------------------------------------------------------------------------

# Resolve the addon_templates/ folder shipped alongside the app code.
def _bundled_templates_root() -> Path:
    """
    Returns the addon_templates directory regardless of whether we're running
    from source or from a PyInstaller bundle.

    PyInstaller's --onefile mode extracts data to a temp directory exposed
    via sys._MEIPASS. In dev/source mode, __file__ is the path of this
    module and addon_templates/ sits two parents up (ui/pages/ -> ui/ ->
    project_root/).
    """
    # Frozen build: PyInstaller sets sys._MEIPASS to the extraction root.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "addon_templates"
    return Path(__file__).resolve().parent.parent.parent / "addon_templates"


# (folder_name, display_name, summary)
_BUNDLED_SCAFFOLDS: tuple[tuple[str, str, str], ...] = (
    ("re",     "Reverse Engineering scaffold",
                "C `strcmp` crackme — edit the password, the prompts, and the metadata."),
    ("pwn",    "Binary Exploitation scaffold",
                "Stack-overflow → ret2win in C, served via socat. Edit the source and the listening port."),
    ("web",    "Web Exploitation scaffold",
                "Flask app with a deliberately-naive SQL-injection-vulnerable login form."),
    ("for",    "Forensics scaffold",
                "Python builder that hides the flag inside a JPEG's metadata + appended bytes."),
    ("custom", "Custom (free-form) scaffold",
                "Minimal Dockerfile + flag.txt. Use for anything that doesn't fit the other categories."),
)


class ScaffoldRow(QFrame):
    """One row showing a downloadable scaffold."""

    def __init__(self, folder_name: str, display_name: str, summary: str,
                 on_download, on_open):
        super().__init__()
        self.setObjectName("scaffoldRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._folder_name = folder_name

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(display_name)
        title.setObjectName("systemTemplateName")
        text_col.addWidget(title)

        sub = QLabel(summary)
        sub.setObjectName("systemTemplateSummary")
        sub.setWordWrap(True)
        text_col.addWidget(sub)

        outer.addLayout(text_col, stretch=1)

        open_btn = QPushButton("Open in folder")
        open_btn.setObjectName("cardActionGhost")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(lambda: on_open(folder_name))

        download_btn = QPushButton("Save copy…")
        download_btn.setObjectName("cardActionPrimary")
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.clicked.connect(lambda: on_download(folder_name))

        outer.addWidget(open_btn)
        outer.addWidget(download_btn)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class AddonsPage(BasePage):
    def __init__(self):
        super().__init__(
            title="Add-ons",
            subtitle=(
                "Import user-made CTF templates by drag & drop, or grab a "
                "starter scaffold to customize."
            )
        )

        # ---- Drop zone ----
        self._drop_zone = DropZone(on_files_dropped=self._on_files_dropped)
        self.add_content(self._drop_zone)

        # ---- Recently dropped ----
        recent_header = QLabel("Recently dropped")
        recent_header.setObjectName("addonsSectionHeader")
        self.add_content(recent_header)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("addonsRecentList")
        self._recent_list.setMaximumHeight(120)
        self.add_content(self._recent_list)

        self._empty_recent = QLabel("Nothing imported yet.")
        self._empty_recent.setObjectName("placeholderText")
        self._recent_list.hide()
        self.add_content(self._empty_recent)

        # ---- Starter scaffolds ----
        scaffold_header = QLabel("Starter scaffolds")
        scaffold_header.setObjectName("addonsSectionHeader")
        self.add_content(scaffold_header)

        scaffold_hint = QLabel(
            "One customizable template per CTF category. Save a copy, edit "
            "the metadata + sources to match your scenario, then drag the "
            "edited folder back onto this page to import it."
        )
        scaffold_hint.setObjectName("dropZoneHint")
        scaffold_hint.setWordWrap(True)
        self.add_content(scaffold_hint)

        for folder_name, display_name, summary in _BUNDLED_SCAFFOLDS:
            self.add_content(
                ScaffoldRow(
                    folder_name, display_name, summary,
                    on_download=self._on_scaffold_download,
                    on_open=self._on_scaffold_open,
                )
            )

        self.add_stretch()

    # ------------------------------------------------------------------
    # Drop handler — visual only for now
    # ------------------------------------------------------------------

    def _on_files_dropped(self, paths: list[str]):
        """
        Visually acknowledge the drop. Real import logic — validating the
        template.json, copying into the user templates folder, registering in
        the registry — is a later task.
        """
        self._empty_recent.hide()
        self._recent_list.show()
        for p in paths:
            self._recent_list.addItem(QListWidgetItem(f"  •  {p}"))

    # ------------------------------------------------------------------
    # Scaffold download / open
    # ------------------------------------------------------------------

    def _on_scaffold_download(self, folder_name: str):
        src = _bundled_templates_root() / folder_name
        if not src.is_dir():
            QMessageBox.warning(
                self, "Scaffold missing",
                f"Couldn't find the scaffold folder at:\n{src}"
            )
            return

        suggested_dir = str(Path.home() / f"ctfmgr-{folder_name}-template")
        target = QFileDialog.getExistingDirectory(
            self,
            "Choose where to save the template copy",
            str(Path.home()),
        )
        if not target:
            return

        dest = Path(target) / src.name
        if dest.exists():
            confirm = QMessageBox.question(
                self, "Folder exists",
                f"<code>{dest}</code> already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            try:
                shutil.rmtree(dest)
            except OSError as e:
                QMessageBox.critical(self, "Couldn't overwrite", str(e))
                return

        try:
            shutil.copytree(src, dest)
        except OSError as e:
            QMessageBox.critical(self, "Couldn't copy", str(e))
            return

        # Confirm + offer to open
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Saved")
        msg.setText(
            f"Saved a copy of the <b>{folder_name}</b> scaffold to:<br>"
            f"<code>{dest}</code><br><br>"
            "Edit <b>template.json</b> first, then the source files, then drop "
            "the folder back here to import."
        )
        open_btn  = msg.addButton("Open folder", QMessageBox.ButtonRole.AcceptRole)
        msg.addButton("Close",       QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() is open_btn:
            self._open_in_filemanager(str(dest))

    def _on_scaffold_open(self, folder_name: str):
        path = _bundled_templates_root() / folder_name
        if not path.is_dir():
            QMessageBox.warning(
                self, "Scaffold missing",
                f"Couldn't find the scaffold folder at:\n{path}"
            )
            return
        self._open_in_filemanager(str(path))

    @staticmethod
    def _open_in_filemanager(path: str):
        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            pass