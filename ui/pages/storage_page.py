"""
Storage page.

Browse and download generated artifacts. Two collections live under
~/.ctf_manager/:
  - instances/         (CTF challenge bundles)
  - system_templates/  (System template script bundles)

Layout:
  Left  — collection tree: two top-level groups, each with one row per folder
  Right — selected folder's contents + actions (open, download zip, delete)
"""

from __future__ import annotations

import os
import shutil
import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QPushButton,
    QTreeWidget, QTreeWidgetItem, QStackedWidget, QFileDialog,
    QMessageBox, QSizePolicy,
)

from ui.pages.base_page import BasePage
from instances.store import get_data_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_size(num: int) -> str:
    n = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _folder_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _open_in_filemanager(path: str) -> None:
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


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class StoragePage(BasePage):
    # Tree node roles
    ROLE_KIND = Qt.ItemDataRole.UserRole       # "group" | "folder"
    ROLE_PATH = Qt.ItemDataRole.UserRole + 1   # absolute path str

    GROUP_INSTANCES = "instances"
    GROUP_TEMPLATES = "system_templates"

    def __init__(self):
        super().__init__(
            title="Storage",
            subtitle="Browse, download, or delete generated CTF instances and system-template bundles."
        )

        # ----- Body ------
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        # Left: tree + refresh button
        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        # Header row with refresh
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        list_label = QLabel("Stored artifacts")
        list_label.setObjectName("storageSectionHeader")
        header_row.addWidget(list_label)
        header_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("cardActionGhost")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_tree)
        header_row.addWidget(refresh_btn)
        left_col.addLayout(header_row)

        self._tree = QTreeWidget()
        self._tree.setObjectName("storageTree")
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(280)
        self._tree.setMaximumWidth(360)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        left_col.addWidget(self._tree, stretch=1)

        body_layout.addLayout(left_col)

        # Right: detail / empty state stack
        self._detail_stack = QStackedWidget()
        self._detail_stack.addWidget(self._build_empty_state())  # 0
        self._detail_stack.addWidget(self._build_detail_view())  # 1
        body_layout.addWidget(self._detail_stack, stretch=1)

        self.add_content(body, stretch=1)

        # State
        self._selected_path: Path | None = None

        self._refresh_tree()

    def showEvent(self, event):
        # When the user navigates to this page, re-scan the disk so anything
        # new (or recently deleted from elsewhere) shows up without a manual
        # refresh.
        super().showEvent(event)
        self._refresh_tree()

    # ------------------------------------------------------------------
    # Right-side builders
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(0, 60, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No artifact selected")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Pick something from the tree on the left to inspect it.")
        hint.setObjectName("placeholderText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(hint)
        return empty

    def _build_detail_view(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Header line — name + path + size
        self._detail_header = QLabel()
        self._detail_header.setObjectName("storageDetailHeader")
        self._detail_header.setWordWrap(True)
        self._detail_header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._detail_header)

        # File listing
        contents_label = QLabel("Contents")
        contents_label.setObjectName("storageSectionHeader")
        layout.addWidget(contents_label)

        self._files_tree = QTreeWidget()
        self._files_tree.setObjectName("storageFilesTree")
        self._files_tree.setHeaderLabels(["Name", "Size"])
        self._files_tree.setRootIsDecorated(True)
        self._files_tree.setColumnWidth(0, 320)
        layout.addWidget(self._files_tree, stretch=1)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._open_btn = QPushButton("Open folder")
        self._open_btn.setObjectName("cardActionGhost")
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._on_open)

        self._download_btn = QPushButton("Download as ZIP…")
        self._download_btn.setObjectName("cardActionPrimary")
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.clicked.connect(self._on_download)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName("cardActionDanger")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setMinimumWidth(80)
        self._delete_btn.setText("Delete")
        self._delete_btn.clicked.connect(self._on_delete)

        actions.addWidget(self._open_btn)
        actions.addWidget(self._download_btn)
        actions.addStretch()
        actions.addWidget(self._delete_btn)
        layout.addLayout(actions)

        return host

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _refresh_tree(self):
        self._tree.clear()
        previous = str(self._selected_path) if self._selected_path else None

        # Two top-level groups, regardless of whether they have children.
        instances_root = get_data_root() / "instances"
        templates_root = get_data_root() / "system_templates"

        instances_node = self._make_group_node(
            "Challenge instances",
            instances_root,
            self.GROUP_INSTANCES,
        )
        templates_node = self._make_group_node(
            "System templates",
            templates_root,
            self.GROUP_TEMPLATES,
        )

        self._tree.addTopLevelItem(instances_node)
        self._tree.addTopLevelItem(templates_node)
        instances_node.setExpanded(True)
        templates_node.setExpanded(True)

        # Restore selection if the previous path still exists
        if previous:
            it = self._find_item_for_path(previous)
            if it is not None:
                self._tree.setCurrentItem(it)
                return

        self._selected_path = None
        self._detail_stack.setCurrentIndex(0)

    def _make_group_node(self, label: str, root: Path, group_id: str) -> QTreeWidgetItem:
        # Count + total size for the group label
        if root.exists():
            children = [c for c in root.iterdir() if c.is_dir()]
        else:
            children = []
        size_total = sum(_folder_size(c) for c in children) if children else 0

        suffix = (
            f"  ({len(children)} item{'s' if len(children) != 1 else ''}, "
            f"{_fmt_size(size_total)})"
            if children else "  (empty)"
        )
        node = QTreeWidgetItem([label + suffix])
        node.setData(0, self.ROLE_KIND, "group")
        node.setData(0, self.ROLE_PATH, str(root))
        # Group rows aren't selectable on their own
        node.setFlags(node.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        for child in sorted(children, key=lambda p: p.name.lower()):
            child_node = QTreeWidgetItem([child.name])
            child_node.setData(0, self.ROLE_KIND, "folder")
            child_node.setData(0, self.ROLE_PATH, str(child))
            node.addChild(child_node)

        return node

    def _find_item_for_path(self, target_path: str) -> QTreeWidgetItem | None:
        target_norm = os.path.normcase(os.path.abspath(target_path))
        for top in range(self._tree.topLevelItemCount()):
            top_item = self._tree.topLevelItem(top)
            for c in range(top_item.childCount()):
                child = top_item.child(c)
                p = child.data(0, self.ROLE_PATH)
                if p and os.path.normcase(os.path.abspath(p)) == target_norm:
                    return child
        return None

    # ------------------------------------------------------------------
    # Selection -> detail view
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        items = self._tree.selectedItems()
        if not items:
            self._selected_path = None
            self._detail_stack.setCurrentIndex(0)
            return

        item = items[0]
        kind = item.data(0, self.ROLE_KIND)
        if kind != "folder":
            self._selected_path = None
            self._detail_stack.setCurrentIndex(0)
            return

        path = Path(item.data(0, self.ROLE_PATH))
        self._selected_path = path
        self._populate_detail(path)
        self._detail_stack.setCurrentIndex(1)

    def _populate_detail(self, path: Path):
        size = _folder_size(path)
        self._detail_header.setText(
            f"<b>{path.name}</b>"
            f"<br><span style='font-size:11px;'>{path}</span>"
            f"<br><span style='font-size:11px;'>{_fmt_size(size)} on disk</span>"
        )

        self._files_tree.clear()
        self._populate_files(path, parent_item=None)
        self._files_tree.expandToDepth(1)

    def _populate_files(self, folder: Path, parent_item: QTreeWidgetItem | None):
        if not folder.exists():
            return
        try:
            entries = sorted(
                folder.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            return

        for entry in entries:
            if entry.is_dir():
                node = QTreeWidgetItem([entry.name + "/", ""])
                if parent_item is None:
                    self._files_tree.addTopLevelItem(node)
                else:
                    parent_item.addChild(node)
                # Recurse (cheap — instance folders are tiny)
                self._populate_files(entry, node)
            else:
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                node = QTreeWidgetItem([entry.name, _fmt_size(size)])
                if parent_item is None:
                    self._files_tree.addTopLevelItem(node)
                else:
                    parent_item.addChild(node)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_open(self):
        if self._selected_path is None:
            return
        _open_in_filemanager(str(self._selected_path))

    def _on_download(self):
        if self._selected_path is None:
            return

        # Ask the user where to save the zip
        suggested = str(Path.home() / f"{self._selected_path.name}.zip")
        target, _ = QFileDialog.getSaveFileName(
            self, "Save bundle as…", suggested, "ZIP archives (*.zip)"
        )
        if not target:
            return

        # shutil.make_archive wants the path WITHOUT the .zip suffix
        target_path = Path(target)
        if target_path.suffix.lower() == ".zip":
            base = str(target_path.with_suffix(""))
        else:
            base = str(target_path)

        try:
            zip_path = shutil.make_archive(
                base_name=base,
                format="zip",
                root_dir=str(self._selected_path.parent),
                base_dir=self._selected_path.name,
            )
        except OSError as e:
            QMessageBox.critical(self, "Couldn't create ZIP", str(e))
            return

        # Friendly success: offer to reveal in file manager
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Download ready")
        msg.setText(f"Saved to:<br><code>{zip_path}</code>")
        open_btn  = msg.addButton("Open folder", QMessageBox.ButtonRole.AcceptRole)
        close_btn = msg.addButton("Close",       QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() is open_btn:
            _open_in_filemanager(str(Path(zip_path).parent))

    def _on_delete(self):
        if self._selected_path is None:
            return

        confirm = QMessageBox.question(
            self, "Delete folder",
            f"Delete <b>{self._selected_path.name}</b> from disk?<br><br>"
            f"This removes everything in:<br>"
            f"<code>{self._selected_path}</code><br><br>"
            "Running containers won't be stopped — use the Instances page "
            "for that. This only deletes the on-disk folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.rmtree(self._selected_path, ignore_errors=False)
        except OSError as e:
            QMessageBox.critical(self, "Couldn't delete", str(e))
            return

        # If this was a CTF instance, the instance store should also drop it.
        try:
            from instances import get_store
            store = get_store()
            for inst in store.all():
                if Path(inst.working_dir) == self._selected_path:
                    store.remove(inst.id, delete_files=False)
                    break
        except Exception:
            pass

        self._refresh_tree()