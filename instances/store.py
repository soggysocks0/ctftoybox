"""
InstanceStore — the in-memory + on-disk registry of all generated instances.

Persistence layout:
    ~/.ctf_manager/
    └── instances/
        └── <instance_id>/
            ├── metadata.json     ← serialized Instance
            ├── Dockerfile        ← (whatever the generator wrote)
            ├── build.sh / .bat
            └── …

The store scans this directory on startup so instances survive across
app restarts. It emits Qt signals when the catalog changes so the UI can
refresh reactively.
"""

from __future__ import annotations

import json
import os
import shutil
import secrets
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from instances.models import Instance, InstanceStatus


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

def get_data_root() -> Path:
    """Top-level directory where everything user-generated lives."""
    return Path.home() / ".ctf_manager"


def get_instances_root() -> Path:
    return get_data_root() / "instances"


def make_instance_id(template_id: str) -> str:
    """Generate a short, unique-ish instance id like 'pwn-ret2win-basic-a3f1c2'."""
    return f"{template_id}-{secrets.token_hex(3)}"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class InstanceStore(QObject):
    """Tracks all known instances. Singleton (use `get_store`)."""

    instance_added   = pyqtSignal(object)  # emits Instance
    instance_removed = pyqtSignal(str)     # emits instance id
    instance_updated = pyqtSignal(object)  # emits Instance
    catalog_reloaded = pyqtSignal()        # bulk reload

    def __init__(self):
        super().__init__()
        self._instances: dict[str, Instance] = {}
        get_instances_root().mkdir(parents=True, exist_ok=True)
        self.reload()

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def reload(self):
        """Scan the instances directory and rebuild the in-memory catalog."""
        self._instances.clear()
        root = get_instances_root()
        if not root.exists():
            self.catalog_reloaded.emit()
            return

        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            meta_path = entry / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                inst = Instance.from_dict(data)
                self._instances[inst.id] = inst
            except (OSError, json.JSONDecodeError, KeyError):
                # Corrupt or partial — skip; future cleanup pass can prune it.
                continue

        self.catalog_reloaded.emit()

    def _save(self, instance: Instance):
        """Persist a single instance's metadata.json."""
        meta_path = Path(instance.working_dir) / "metadata.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(instance.to_dict(), f, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def all(self) -> list[Instance]:
        # Newest first
        return sorted(
            self._instances.values(),
            key=lambda i: i.created_at,
            reverse=True,
        )

    def get(self, instance_id: str) -> Instance | None:
        return self._instances.get(instance_id)

    def add(self, instance: Instance):
        self._instances[instance.id] = instance
        self._save(instance)
        self.instance_added.emit(instance)

    def update(self, instance: Instance):
        self._instances[instance.id] = instance
        self._save(instance)
        self.instance_updated.emit(instance)

    def remove(self, instance_id: str, *, delete_files: bool = True):
        inst = self._instances.pop(instance_id, None)
        if inst is None:
            return
        if delete_files:
            try:
                shutil.rmtree(inst.working_dir, ignore_errors=True)
            except OSError:
                pass
        self.instance_removed.emit(instance_id)

    # ------------------------------------------------------------------
    # Helpers used by the deploy wizard
    # ------------------------------------------------------------------

    @staticmethod
    def working_dir_for(instance_id: str) -> Path:
        return get_instances_root() / instance_id


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_store: InstanceStore | None = None


def get_store() -> InstanceStore:
    global _store
    if _store is None:
        _store = InstanceStore()
    return _store