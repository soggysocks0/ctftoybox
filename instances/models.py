"""
Data model for deployed CTF instances.

Kept lean and serializable so we can round-trip through JSON for persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class InstanceStatus(str, Enum):
    """Lifecycle states for a generated instance.

    Values that the future container backend will set:
      - GENERATED: files written to disk, not yet built
      - BUILDING:  `docker build` in progress
      - STOPPED:   image built but no container running
      - RUNNING:   container is up
      - ERROR:     last operation failed (see Instance.last_error)
    """
    GENERATED = "generated"
    BUILDING  = "building"
    STOPPED   = "stopped"
    RUNNING   = "running"
    ERROR     = "error"

    @property
    def display_name(self) -> str:
        return {
            InstanceStatus.GENERATED: "Generated",
            InstanceStatus.BUILDING:  "Building…",
            InstanceStatus.STOPPED:   "Stopped",
            InstanceStatus.RUNNING:   "Running",
            InstanceStatus.ERROR:     "Error",
        }[self]


@dataclass
class ResourceSpec:
    """How much of the host the instance is allowed to use."""

    # CPU as a fractional core count. 0.5 = half a core.
    cpu_cores: float = 1.0

    # Memory in megabytes.
    memory_mb: int = 512

    # Optional: ports the instance binds on the host. Each entry is a tuple
    # (host_port, container_port). Empty for offline challenges.
    port_mappings: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "port_mappings": [list(pm) for pm in self.port_mappings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceSpec":
        return cls(
            cpu_cores=float(data.get("cpu_cores", 1.0)),
            memory_mb=int(data.get("memory_mb", 512)),
            port_mappings=[tuple(pm) for pm in data.get("port_mappings", [])],
        )


@dataclass
class Instance:
    """
    A generated CTF challenge instance.

    `working_dir` is the folder where Dockerfile + helpers were written.
    The store knows how to resolve this from `id`.
    """
    id:           str         # short stable slug, e.g. "pwn-ret2win-basic-a3f1c2"
    name:         str         # user-supplied display name
    template_id:  str         # vulnerabilities.Vulnerability.id
    category:     str         # vulnerabilities.Category.value (string for JSON)
    resources:    ResourceSpec
    working_dir:  str         # absolute path to instance folder
    status:       InstanceStatus = InstanceStatus.GENERATED
    created_at:   str = ""    # ISO-8601 UTC timestamp
    last_error:   str = ""    # populated when status == ERROR

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          self.id,
            "name":        self.name,
            "template_id": self.template_id,
            "category":    self.category,
            "resources":   self.resources.to_dict(),
            "working_dir": self.working_dir,
            "status":      self.status.value,
            "created_at":  self.created_at,
            "last_error":  self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instance":
        return cls(
            id=data["id"],
            name=data["name"],
            template_id=data["template_id"],
            category=data["category"],
            resources=ResourceSpec.from_dict(data.get("resources", {})),
            working_dir=data["working_dir"],
            status=InstanceStatus(data.get("status", "generated")),
            created_at=data.get("created_at", ""),
            last_error=data.get("last_error", ""),
        )