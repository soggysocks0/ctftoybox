"""
System templates.

Generates OS-level setup scripts (PowerShell / bash) that configure a real
host into a vulnerable lab environment for pentest practice. Unlike the
challenge templates under ./generators, these do NOT spin up Docker
containers — the user runs the produced scripts on a (disposable) target
machine.

Public entry points:
  - REGISTRY: list of all available templates
  - get_template(id): look up a single template
  - generate(template, services, output_dir): write the bundle to disk
"""

from system_templates.registry import (
    SystemTemplate,
    TargetOS,
    Tier,
    Vulnerability,
    Defense,
    REGISTRY,
    get_template,
)
from system_templates.services import (
    LiveService,
    AVAILABLE_SERVICES,
    get_service,
)
from system_templates.dispatch import generate_template_bundle, GenerationError

__all__ = [
    "SystemTemplate", "TargetOS", "Tier",
    "Vulnerability", "Defense",
    "REGISTRY", "get_template",
    "LiveService", "AVAILABLE_SERVICES", "get_service",
    "generate_template_bundle", "GenerationError",
]