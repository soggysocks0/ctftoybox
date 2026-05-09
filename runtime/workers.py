"""
QThread workers wrapping the Docker backend.

Each worker emits signals to report progress, success, and failure. The UI
listens for these signals and updates the corresponding card / page.

Workers are one-shot — create, start, let them finish, dispose. We don't
try to be clever about a worker pool; CTF deployments are infrequent
enough that one thread per click is fine and easier to reason about.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from instances.models import Instance, InstanceStatus
from runtime.audit import get_audit_log, AuditKind
from runtime.docker_backend import (
    get_backend, DockerNotAvailable, DockerError, ContainerStats,
)


# ---------------------------------------------------------------------------
# Build + start (one button = both steps for the user)
# ---------------------------------------------------------------------------

class BuildAndStartWorker(QThread):
    """
    Runs `docker build` then `docker run`. Emits:
      - log_line(str)        : streamed build line
      - status_changed(str)  : new InstanceStatus value
      - finished_ok()
      - failed(str)
    """

    log_line       = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    finished_ok    = pyqtSignal()
    failed         = pyqtSignal(str)

    def __init__(self, instance: Instance, parent=None):
        super().__init__(parent)
        self._instance = instance

    def run(self):
        backend = get_backend()
        audit   = get_audit_log()
        wd      = self._instance.working_dir

        # ---- Build ----
        self.status_changed.emit(InstanceStatus.BUILDING.value)
        audit.record(wd, AuditKind.BUILD_STARTED, "docker build started")

        try:
            for line in backend.build(self._instance):
                self.log_line.emit(line)
        except DockerNotAvailable as e:
            audit.record(wd, AuditKind.BUILD_FAILED, str(e))
            self.failed.emit(str(e))
            return
        except DockerError as e:
            audit.record(wd, AuditKind.BUILD_FAILED, str(e))
            self.failed.emit(str(e))
            return

        audit.record(wd, AuditKind.BUILD_OK, "image built successfully")

        # ---- Start ----
        try:
            container_id = backend.start(self._instance)
        except DockerNotAvailable as e:
            audit.record(wd, AuditKind.START_FAILED, str(e))
            self.failed.emit(str(e))
            return
        except DockerError as e:
            audit.record(wd, AuditKind.START_FAILED, str(e))
            self.failed.emit(str(e))
            return

        audit.record(
            wd, AuditKind.START_OK,
            f"container started (id={container_id[:12]})",
        )
        self.status_changed.emit(InstanceStatus.RUNNING.value)
        self.finished_ok.emit()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

class StopWorker(QThread):
    finished_ok = pyqtSignal()
    failed      = pyqtSignal(str)

    def __init__(self, instance: Instance, parent=None):
        super().__init__(parent)
        self._instance = instance

    def run(self):
        backend = get_backend()
        audit   = get_audit_log()
        wd      = self._instance.working_dir
        try:
            backend.stop(self._instance)
        except DockerNotAvailable as e:
            audit.record(wd, AuditKind.STOP_FAILED, str(e))
            self.failed.emit(str(e))
            return
        except DockerError as e:
            audit.record(wd, AuditKind.STOP_FAILED, str(e))
            self.failed.emit(str(e))
            return

        audit.record(wd, AuditKind.STOP_OK, "container stopped")
        self.finished_ok.emit()


# ---------------------------------------------------------------------------
# Remove (full cleanup — used when user deletes an instance)
# ---------------------------------------------------------------------------

class RemoveWorker(QThread):
    finished_ok = pyqtSignal()
    failed      = pyqtSignal(str)

    def __init__(self, instance: Instance, parent=None):
        super().__init__(parent)
        self._instance = instance

    def run(self):
        backend = get_backend()
        audit   = get_audit_log()
        wd      = self._instance.working_dir
        try:
            backend.remove(self._instance)
        except DockerNotAvailable as e:
            # Don't propagate this as a failure — if Docker isn't available,
            # there's nothing to remove anyway.
            audit.record(wd, AuditKind.WARNING, f"docker unavailable: {e}")
        except DockerError as e:
            audit.record(wd, AuditKind.ERROR, f"remove warning: {e}")
            # Continue — we want to allow the on-disk delete even if cleanup fails.

        audit.record(wd, AuditKind.REMOVED, "container/image removal attempted")
        self.finished_ok.emit()


# ---------------------------------------------------------------------------
# Stats poller — periodically samples a running container
# ---------------------------------------------------------------------------

class StatsPoller(QThread):
    """
    Polls `docker stats` for one container at a fixed interval until told to
    stop. Designed for the Management page detail view.
    """

    stats_ready = pyqtSignal(object)  # ContainerStats
    error       = pyqtSignal(str)

    def __init__(self, instance: Instance, interval_ms: int = 2000, parent=None):
        super().__init__(parent)
        self._instance = instance
        self._interval_ms = interval_ms
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        backend = get_backend()
        while not self._stop:
            try:
                stats = backend.stats(self._instance)
                if stats is not None:
                    self.stats_ready.emit(stats)
            except DockerNotAvailable as e:
                self.error.emit(str(e))
                return
            except DockerError as e:
                self.error.emit(str(e))
                # don't return — transient errors shouldn't kill the poller
            # Sleep in small chunks so stop() reacts quickly.
            slept = 0
            while slept < self._interval_ms and not self._stop:
                self.msleep(100)
                slept += 100