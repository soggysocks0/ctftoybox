"""
Dockerfile / batch-script generators.

Each generator takes a Vulnerability template + an Instance config and
writes a buildable folder of files (Dockerfile, sources, helper scripts).

Add a new template? Either reuse an existing generator if the shape
matches, or add a new module here and register it in `dispatch`.
"""

from generators.dispatch import generate_for_instance, GenerationError

__all__ = ["generate_for_instance", "GenerationError"]