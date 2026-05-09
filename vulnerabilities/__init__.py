"""
Vulnerability registry.

Stores template vulnerabilities for each CTF category. Each entry describes
a beginner-friendly, well-known challenge type that can later be turned into
a deployable instance (via Dockerfiles, batch scripts, etc.).
"""

from vulnerabilities.registry import (
    Category,
    Difficulty,
    Vulnerability,
    REGISTRY,
    get_category,
    get_vulnerabilities,
    get_vulnerability,
)

__all__ = [
    "Category",
    "Difficulty",
    "Vulnerability",
    "REGISTRY",
    "get_category",
    "get_vulnerabilities",
    "get_vulnerability",
]