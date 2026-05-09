"""
Routes a (Instance, Vulnerability) pair to the right generator module.
"""

from __future__ import annotations

from instances.models import Instance
from vulnerabilities import Vulnerability, Category
from generators._common import GenerationError

from generators import (
    reverse_engineering,
    binary_exploitation,
    web_exploitation,
    forensics,
    custom,
)


_DISPATCH = {
    Category.REVERSE_ENGINEERING: reverse_engineering.generate,
    Category.BINARY_EXPLOITATION: binary_exploitation.generate,
    Category.WEB_EXPLOITATION:    web_exploitation.generate,
    Category.FORENSICS:           forensics.generate,
    Category.CUSTOM:              custom.generate,
}


def generate_for_instance(instance: Instance, vuln: Vulnerability) -> None:
    """
    Pick the right generator and run it. Raises GenerationError on failure.
    """
    fn = _DISPATCH.get(vuln.category)
    if fn is None:
        raise GenerationError(f"No generator registered for category {vuln.category}")
    try:
        fn(instance, vuln)
    except OSError as e:
        raise GenerationError(f"Filesystem error while generating: {e}") from e