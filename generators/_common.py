"""
Common helpers for generators: writing files, generating flags,
formatting Docker resource limits.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from instances.models import Instance


class GenerationError(Exception):
    """Raised when something goes wrong while writing instance files."""


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str, *, executable: bool = False):
    """Write text with LF newlines and optionally chmod +x."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if executable:
        try:
            os.chmod(path, 0o755)
        except OSError:
            # Windows ignores chmod; that's fine.
            pass


def realize_flag(flag_template: str, *, challenge_slug: str = "challenge") -> str:
    """
    Materialize a flag template into a real flag string.

    Supported placeholders:
      {challenge} — slugified challenge/instance name
      {rand}      — 8 random hex chars (per-instance uniqueness)

    Doubled braces in the template (`bluebox{{...}}`) are collapsed back
    to single braces, since some generators pass these through `.format`.
    """
    realized = (
        flag_template
        .replace("{challenge}", _safe_slug(challenge_slug))
        .replace("{rand}", secrets.token_hex(4))
    )
    return realized.replace("{{", "{").replace("}}", "}")


def _safe_slug(text: str) -> str:
    """Lowercase + collapse to [a-z0-9_]. Used inside flag bodies."""
    out = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("_")
    cleaned = "".join(out).strip("_")
    # Collapse multiple underscores
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "challenge"


def docker_run_args(instance: Instance) -> str:
    """Compose the resource/port portion of a `docker run` command."""
    parts: list[str] = []
    parts.append(f"--cpus={instance.resources.cpu_cores}")
    parts.append(f"--memory={instance.resources.memory_mb}m")
    for host_port, container_port in instance.resources.port_mappings:
        parts.append(f"-p {host_port}:{container_port}")
    return " ".join(parts)


def write_run_scripts(
    folder: Path,
    image_tag: str,
    container_name: str,
    instance: Instance,
):
    """
    Drop in helper scripts the user (or future deploy backend) can run:
      build.sh / build.bat   — `docker build`
      run.sh   / run.bat     — `docker run` with resource limits
      stop.sh  / stop.bat    — `docker stop && docker rm`
    """
    run_args = docker_run_args(instance)

    # --- POSIX ---
    write_text(folder / "build.sh", (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'docker build -t "{image_tag}" "$(dirname "$0")"\n'
    ), executable=True)

    write_text(folder / "run.sh", (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'docker rm -f "{container_name}" >/dev/null 2>&1 || true\n'
        f'docker run -d --name "{container_name}" {run_args} "{image_tag}"\n'
    ), executable=True)

    write_text(folder / "stop.sh", (
        "#!/usr/bin/env bash\n"
        f'docker stop "{container_name}" >/dev/null 2>&1 || true\n'
        f'docker rm   "{container_name}" >/dev/null 2>&1 || true\n'
    ), executable=True)

    # --- Windows (.bat) ---
    write_text(folder / "build.bat", (
        "@echo off\r\n"
        f'docker build -t {image_tag} "%~dp0."\r\n'
    ))

    write_text(folder / "run.bat", (
        "@echo off\r\n"
        f"docker rm -f {container_name} >nul 2>&1\r\n"
        f"docker run -d --name {container_name} {run_args} {image_tag}\r\n"
    ))

    write_text(folder / "stop.bat", (
        "@echo off\r\n"
        f"docker stop {container_name} >nul 2>&1\r\n"
        f"docker rm   {container_name} >nul 2>&1\r\n"
    ))