"""
Instances page.

Hosts the list of generated instances and is responsible for:
  - launching the deploy wizard
  - kicking off build+start / stop / remove jobs (via QThread workers)
  - keeping each card's status in sync with the underlying Docker state
"""

from __future__ import annotations

import os
import sys
import subprocess

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QLabel, QVBoxLayout, QWidget, QScrollArea,
    QStackedWidget, QMessageBox,
)

from ui.pages.base_page import BasePage
from ui.widgets.deploy_button import DeployButton
from ui.widgets.deploy_wizard import DeployWizard
from ui.widgets.instance_card import InstanceCard
from instances import Instance, InstanceStatus, get_store
from vulnerabilities import Category
from runtime.workers import BuildAndStartWorker, StopWorker, RemoveWorker
from runtime.docker_backend import get_backend


class InstancesPage(BasePage):
    def __init__(self):
        super().__init__(
            title="Instances",
            subtitle="Deploy, monitor, and manage running CTF challenge instances."
        )

        # Deploy ▾ button in the header
        self.deploy_btn = DeployButton()
        self.deploy_btn.category_selected.connect(self._on_category_selected)
        self.add_header_action(self.deploy_btn)

        # Body: empty state OR scrollable card list
        self._body_stack = QStackedWidget()
        self._body_stack.addWidget(self._build_empty_state())   # 0
        self._body_stack.addWidget(self._build_list_view())     # 1
        self.add_content(self._body_stack, stretch=1)

        self._cards: dict[str, InstanceCard] = {}

        # Track active worker threads so they aren't GC'd mid-run.
        self._workers: dict[str, list] = {}

        store = get_store()
        store.instance_added.connect(self._on_instance_added)
        store.instance_removed.connect(self._on_instance_removed)
        store.instance_updated.connect(self._on_instance_updated)
        store.catalog_reloaded.connect(self._rebuild_all)

        self._rebuild_all()

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(0, 60, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No instances yet")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Click <b>Deploy</b> in the top-right to spin up your first challenge.")
        hint.setObjectName("placeholderText")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addSpacing(6)
        layout.addWidget(hint)
        return empty

    def _build_list_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("instanceScroll")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._list_container = QWidget()
        self._list_container.setObjectName("instanceListContainer")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 8, 0, 8)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch()  # keep cards top-aligned

        scroll.setWidget(self._list_container)
        return scroll

    # ------------------------------------------------------------------
    # Deploy flow
    # ------------------------------------------------------------------

    def _on_category_selected(self, category: Category):
        wizard = DeployWizard(category, self.window())
        wizard.exec()

    # ------------------------------------------------------------------
    # Store sync
    # ------------------------------------------------------------------

    def _rebuild_all(self):
        for card in list(self._cards.values()):
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        instances = get_store().all()
        if not instances:
            self._body_stack.setCurrentIndex(0)
            return

        self._body_stack.setCurrentIndex(1)
        for inst in instances:
            self._add_card(inst)

    def _add_card(self, instance: Instance):
        card = InstanceCard(instance)
        card.run_clicked.connect(self._on_run)
        card.stop_clicked.connect(self._on_stop)
        card.open_clicked.connect(self._on_open_folder)
        card.delete_clicked.connect(self._on_delete)
        # Insert before the trailing stretch
        self._list_layout.insertWidget(self._list_layout.count() - 1, card)
        self._cards[instance.id] = card

    def _on_instance_added(self, instance: Instance):
        if not self._cards:
            self._body_stack.setCurrentIndex(1)
        self._add_card(instance)

    def _on_instance_removed(self, instance_id: str):
        card = self._cards.pop(instance_id, None)
        if card is not None:
            card.setParent(None)
            card.deleteLater()
        if not self._cards:
            self._body_stack.setCurrentIndex(0)

    def _on_instance_updated(self, instance: Instance):
        card = self._cards.get(instance.id)
        if card is not None:
            card.update_from(instance)

    # ------------------------------------------------------------------
    # Actions — each kicks off a worker
    # ------------------------------------------------------------------

    def _check_docker(self) -> bool:
        """Show a friendly dialog if Docker isn't reachable. Returns True if OK."""
        if get_backend().is_available():
            return True
        QMessageBox.warning(
            self, "Docker not available",
            "Couldn't reach the Docker daemon.\n\n"
            "Make sure Docker Desktop (or your Docker engine) is installed "
            "and running, then try again."
        )
        return False

    def _on_run(self, instance_id: str):
        inst = get_store().get(instance_id)
        if inst is None or not self._check_docker():
            return

        # Don't double-start.
        if inst.status in (InstanceStatus.RUNNING, InstanceStatus.BUILDING):
            return

        worker = BuildAndStartWorker(inst, parent=self)
        worker.status_changed.connect(lambda s, i=instance_id: self._apply_status(i, s))
        worker.failed.connect(lambda msg, i=instance_id: self._on_run_failed(i, msg))
        worker.finished_ok.connect(lambda i=instance_id: self._on_run_ok(i))
        worker.finished.connect(lambda w=worker, i=instance_id: self._cleanup_worker(i, w))
        self._track_worker(instance_id, worker)
        worker.start()

    def _on_stop(self, instance_id: str):
        inst = get_store().get(instance_id)
        if inst is None or not self._check_docker():
            return

        worker = StopWorker(inst, parent=self)
        worker.finished_ok.connect(lambda i=instance_id: self._on_stop_ok(i))
        worker.failed.connect(lambda msg, i=instance_id: self._on_stop_failed(i, msg))
        worker.finished.connect(lambda w=worker, i=instance_id: self._cleanup_worker(i, w))
        self._track_worker(instance_id, worker)
        worker.start()

    def _on_delete(self, instance_id: str):
        inst = get_store().get(instance_id)
        if inst is None:
            return
        confirm = QMessageBox.question(
            self, "Delete instance",
            f"Delete <b>{inst.name}</b>?<br><br>"
            "This stops + removes the container and image (if Docker is running) "
            "and deletes the instance folder from disk. This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Try to clean up containers/images first (best-effort), then delete files.
        worker = RemoveWorker(inst, parent=self)
        # Once cleanup finishes (success or warning), remove from the store.
        worker.finished_ok.connect(lambda i=instance_id: get_store().remove(i, delete_files=True))
        worker.failed.connect(lambda msg, i=instance_id: get_store().remove(i, delete_files=True))
        worker.finished.connect(lambda w=worker, i=instance_id: self._cleanup_worker(i, w))
        self._track_worker(instance_id, worker)
        worker.start()

    def _on_open_folder(self, instance_id: str):
        inst = get_store().get(instance_id)
        if inst is None:
            return
        path = inst.working_dir
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Folder missing",
                                f"The instance folder no longer exists:\n{path}")
            return

        if QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            QMessageBox.warning(self, "Could not open folder", str(e))

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _apply_status(self, instance_id: str, status_value: str):
        inst = get_store().get(instance_id)
        if inst is None:
            return
        try:
            inst.status = InstanceStatus(status_value)
        except ValueError:
            return
        get_store().update(inst)

    def _on_run_ok(self, instance_id: str):
        # Status was already set to RUNNING by the worker's signal.
        pass

    def _on_run_failed(self, instance_id: str, msg: str):
        inst = get_store().get(instance_id)
        if inst is not None:
            inst.status = InstanceStatus.ERROR
            inst.last_error = msg
            get_store().update(inst)
        QMessageBox.critical(self, "Build/start failed", msg)

    def _on_stop_ok(self, instance_id: str):
        inst = get_store().get(instance_id)
        if inst is not None:
            inst.status = InstanceStatus.STOPPED
            get_store().update(inst)

    def _on_stop_failed(self, instance_id: str, msg: str):
        QMessageBox.critical(self, "Stop failed", msg)

    # ------------------------------------------------------------------
    # Worker tracking — keeps QThread refs alive until they finish
    # ------------------------------------------------------------------

    def _track_worker(self, instance_id: str, worker):
        self._workers.setdefault(instance_id, []).append(worker)

    def _cleanup_worker(self, instance_id: str, worker):
        lst = self._workers.get(instance_id)
        if lst and worker in lst:
            lst.remove(worker)
        worker.deleteLater()