"""
Runtime services: Docker backend, audit log, container monitoring.

These live outside the UI tree and run on background threads so the
GUI stays responsive while builds/runs are in flight.
"""

from runtime.audit import AuditLog, AuditEvent, get_audit_log
from runtime.docker_backend import (
    DockerBackend, DockerNotAvailable, DockerError, get_backend,
    ContainerStats,
)
from runtime.workers import (
    BuildAndStartWorker, StopWorker, RemoveWorker, StatsPoller,
)

__all__ = [
    "AuditLog", "AuditEvent", "get_audit_log",
    "DockerBackend", "DockerNotAvailable", "DockerError", "get_backend",
    "ContainerStats",
    "BuildAndStartWorker", "StopWorker", "RemoveWorker", "StatsPoller",
]