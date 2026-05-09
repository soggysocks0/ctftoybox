"""
Instance management.

An "instance" is a configured deployment of a vulnerability template:
a name, resource allocation, the template it was built from, and a
folder on disk containing the generated Dockerfile/scripts.

The store handles persistence — instances live under
~/.ctf_manager/instances/<id>/ as folders containing both metadata.json
and the generated build artifacts.
"""

from instances.models import Instance, InstanceStatus, ResourceSpec
from instances.store import InstanceStore, get_store

__all__ = [
    "Instance",
    "InstanceStatus",
    "ResourceSpec",
    "InstanceStore",
    "get_store",
]