"""
Audit log.

Append-only event log per instance. Each event is one JSON object on its
own line in `<instance.working_dir>/audit.log`. Designed to be cheap to
write and easy to tail from the Management page.

Events are also fanned out via a Qt signal so the UI can update live
without polling the file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class AuditKind(str, Enum):
    """The kinds of events we log. Keep additive — old logs must keep parsing."""
    CREATED       = "created"
    BUILD_STARTED = "build_started"
    BUILD_OK      = "build_ok"
    BUILD_FAILED  = "build_failed"
    START_OK      = "start_ok"
    START_FAILED  = "start_failed"
    STOP_OK       = "stop_ok"
    STOP_FAILED   = "stop_failed"
    REMOVED       = "removed"
    INFO          = "info"
    WARNING       = "warning"
    ERROR         = "error"


@dataclass
class AuditEvent:
    instance_id: str
    kind:        str            # AuditKind value (kept as str for forward-compat)
    message:     str
    timestamp:   str = ""       # ISO-8601 UTC

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLog(QObject):
    """Singleton audit log writer + signal hub."""

    event_recorded = pyqtSignal(object)  # AuditEvent

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _path_for(instance_working_dir: str) -> Path:
        return Path(instance_working_dir) / "audit.log"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, instance_working_dir: str, kind: AuditKind | str, message: str) -> AuditEvent:
        """
        Append an event for the given instance, emit the signal.
        Safe to call from background threads — file append + signal emit
        are both thread-safe for our purposes (PyQt queues cross-thread signals).
        """
        kind_value = kind.value if isinstance(kind, AuditKind) else str(kind)
        evt = AuditEvent(
            instance_id=Path(instance_working_dir).name,
            kind=kind_value,
            message=message,
        )

        path = self._path_for(instance_working_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(evt.to_dict()) + "\n")
        except OSError:
            # Don't let logging failures crash the workflow; just emit anyway.
            pass

        self.event_recorded.emit(evt)
        return evt

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self, instance_working_dir: str, *, tail: int | None = None) -> list[AuditEvent]:
        """
        Read events for an instance, optionally returning only the last `tail` items.
        Returns an empty list if the file doesn't exist yet.
        """
        path = self._path_for(instance_working_dir)
        if not path.exists():
            return []

        events: list[AuditEvent] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        events.append(AuditEvent(
                            instance_id=data.get("instance_id", ""),
                            kind=data.get("kind", "info"),
                            message=data.get("message", ""),
                            timestamp=data.get("timestamp", ""),
                        ))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        if tail is not None and tail >= 0:
            events = events[-tail:]
        return events


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_log: AuditLog | None = None


def get_audit_log() -> AuditLog:
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog()
    return _audit_log