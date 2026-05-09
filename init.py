"""
Vulnerability registry.

Stores template vulnerabilities for each CTF category. Each entry describes
a beginner-friendly, well-known challenge type that can later be turned into
a deployable instance (via Dockerfiles, batch scripts, etc.).

The registry is intentionally data-only (no deployment logic yet) so it can
be consumed by both the GUI (to populate menus) and any future build/deploy
backend.
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