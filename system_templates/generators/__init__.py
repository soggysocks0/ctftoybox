"""
Per-OS script generators for system templates.

Each generator emits the master setup script (PowerShell or bash) plus
any helpers, then `dispatch.py` adds the shared README and
VULNERABILITIES.md.
"""