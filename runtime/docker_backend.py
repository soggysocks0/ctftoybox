"""
Docker backend.

Thin, synchronous wrapper around the docker SDK. All long-running calls
(`build`, `run`, `stats`) are still synchronous here — workers in
`runtime.workers` run them off the UI thread.

Two failure modes the UI must handle gracefully:
  - Docker daemon isn't running / not installed -> DockerNotAvailable
  - Operation failed (build error, container missing, etc.) -> DockerError
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

try:
    import docker                                    # type: ignore[import-untyped]
    from docker.errors import (                      # type: ignore[import-untyped]
        APIError, BuildError, ImageNotFound, NotFound, DockerException,
    )
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

from instances.models import Instance


# ---------------------------------------------------------------------------
# Naming conventions — keep these stable; they're what we look up by later.
# ---------------------------------------------------------------------------

def image_tag_for(instance: Instance) -> str:
    return f"ctfmgr/{instance.id}:latest"


def container_name_for(instance: Instance) -> str:
    return f"ctfmgr_{instance.id}"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class DockerNotAvailable(RuntimeError):
    """Raised when the SDK isn't installed or the daemon isn't reachable."""


class DockerError(RuntimeError):
    """Generic catch-all for backend operation failures."""


# ---------------------------------------------------------------------------
# Stats payload
# ---------------------------------------------------------------------------

@dataclass
class ContainerStats:
    """A snapshot of container resource usage."""
    cpu_percent:    float          # 0–100 * online_cpus
    memory_bytes:   int            # current usage
    memory_limit:   int            # limit (or host total if unlimited)
    network_rx:     int            # cumulative bytes since container start
    network_tx:     int
    pids:           int
    online_cpus:    int

    @property
    def memory_mb(self) -> float:
        return self.memory_bytes / (1024 * 1024)

    @property
    def memory_limit_mb(self) -> float:
        return self.memory_limit / (1024 * 1024)

    @property
    def memory_percent(self) -> float:
        if self.memory_limit <= 0:
            return 0.0
        return (self.memory_bytes / self.memory_limit) * 100.0


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class DockerBackend:
    """Wraps a docker.DockerClient. Lazy-initialized so import doesn't fail."""

    def __init__(self):
        self._client = None  # docker.DockerClient | None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _client_or_raise(self):
        if not _SDK_AVAILABLE:
            raise DockerNotAvailable(
                "The 'docker' Python package isn't installed. "
                "Run: pip install docker"
            )
        if self._client is None:
            try:
                self._client = docker.from_env()
                # Ping to make sure the daemon is actually responsive.
                self._client.ping()
            except DockerException as e:
                self._client = None
                raise DockerNotAvailable(
                    "Could not connect to the Docker daemon. "
                    "Is Docker running?\n\nDetails: " + str(e)
                ) from e
        return self._client

    def is_available(self) -> bool:
        """Cheap check — does NOT raise."""
        try:
            self._client_or_raise()
            return True
        except DockerNotAvailable:
            return False

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, instance: Instance) -> Iterator[str]:
        """
        Build the image for an instance. Yields log lines as they come in
        so workers can stream them to audit log / UI.

        Raises DockerNotAvailable / DockerError.
        """
        client = self._client_or_raise()
        path = instance.working_dir
        if not Path(path, "Dockerfile").exists():
            raise DockerError(f"No Dockerfile found at {path}")

        tag = image_tag_for(instance)
        try:
            # build returns (image, build_log_stream).
            _image, log_stream = client.images.build(
                path=path,
                tag=tag,
                rm=True,
                forcerm=True,
                pull=False,    # don't auto-pull base each time during dev
            )
            for chunk in log_stream:
                # Each chunk is a dict; 'stream' or 'error' keys are interesting.
                if not isinstance(chunk, dict):
                    continue
                if "stream" in chunk:
                    line = chunk["stream"].rstrip()
                    if line:
                        yield line
                elif "error" in chunk:
                    raise DockerError(chunk["error"])
        except BuildError as e:
            # BuildError carries .build_log we could stream too, but the
            # message is usually enough.
            raise DockerError(f"Build failed: {e}") from e
        except APIError as e:
            raise DockerError(f"Docker API error during build: {e}") from e

    # ------------------------------------------------------------------
    # Run / Stop / Remove
    # ------------------------------------------------------------------

    def start(self, instance: Instance) -> str:
        """
        Start a container from this instance's image. Removes any existing
        container with the same name first. Returns the new container id.
        """
        client = self._client_or_raise()
        name = container_name_for(instance)
        tag = image_tag_for(instance)

        # Remove a stale container with the same name, if any.
        self._safe_remove(name)

        # Translate ResourceSpec into Docker run kwargs.
        # cpu_period/cpu_quota lets us express fractional cores precisely.
        cpu_period = 100_000
        cpu_quota = max(1000, int(instance.resources.cpu_cores * cpu_period))

        port_mapping = {}
        for host_port, container_port in instance.resources.port_mappings:
            # docker SDK format: {'8080/tcp': 8080}
            port_mapping[f"{container_port}/tcp"] = host_port

        try:
            container = client.containers.run(
                image=tag,
                name=name,
                detach=True,
                mem_limit=f"{instance.resources.memory_mb}m",
                cpu_period=cpu_period,
                cpu_quota=cpu_quota,
                ports=port_mapping or None,
                # Don't auto-restart — challenges that crash should stay crashed
                # so the player can see the error.
                restart_policy={"Name": "no"},
            )
            return container.id
        except ImageNotFound as e:
            raise DockerError(
                f"Image {tag} not found — build the instance first."
            ) from e
        except APIError as e:
            raise DockerError(f"Failed to start container: {e}") from e

    def stop(self, instance: Instance, *, timeout: int = 5) -> None:
        client = self._client_or_raise()
        name = container_name_for(instance)
        try:
            container = client.containers.get(name)
        except NotFound:
            return  # already gone, nothing to do
        try:
            container.stop(timeout=timeout)
        except APIError as e:
            raise DockerError(f"Failed to stop container: {e}") from e

    def remove(self, instance: Instance) -> None:
        """Stop + remove the container, then remove the image."""
        client = self._client_or_raise()
        name = container_name_for(instance)
        tag = image_tag_for(instance)

        self._safe_remove(name)

        try:
            client.images.remove(tag, force=True)
        except (ImageNotFound, NotFound):
            pass
        except APIError as e:
            # Image removal failure is non-fatal — log but don't raise.
            raise DockerError(f"Could not remove image {tag}: {e}") from e

    def _safe_remove(self, container_name: str) -> None:
        client = self._client_or_raise()
        try:
            c = client.containers.get(container_name)
            try:
                c.stop(timeout=2)
            except APIError:
                pass
            c.remove(force=True)
        except NotFound:
            pass
        except APIError:
            # If we can't remove, we'll let the next start attempt deal with it.
            pass

    # ------------------------------------------------------------------
    # Status / Stats / Logs
    # ------------------------------------------------------------------

    def status(self, instance: Instance) -> str:
        """
        Return docker container status: 'running', 'exited', 'created', etc.
        Returns 'absent' if the container doesn't exist.
        """
        client = self._client_or_raise()
        try:
            c = client.containers.get(container_name_for(instance))
            c.reload()
            return c.status
        except NotFound:
            return "absent"
        except APIError as e:
            raise DockerError(str(e)) from e

    def stats(self, instance: Instance) -> ContainerStats | None:
        """
        One-shot stats snapshot. Returns None if the container isn't running.
        """
        client = self._client_or_raise()
        try:
            c = client.containers.get(container_name_for(instance))
            c.reload()
            if c.status != "running":
                return None
            raw = c.stats(stream=False)
        except NotFound:
            return None
        except APIError as e:
            raise DockerError(str(e)) from e

        return self._parse_stats(raw)

    @staticmethod
    def _parse_stats(raw: dict) -> ContainerStats:
        # CPU% calculation (Linux); on Windows it returns 0 sometimes — we
        # fall back to 0.0 in that case rather than crashing.
        try:
            cpu_stats   = raw.get("cpu_stats",   {}) or {}
            precpu      = raw.get("precpu_stats", {}) or {}
            cpu_total   = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            pre_total   = precpu.get("cpu_usage", {}).get("total_usage", 0)
            sys_now     = cpu_stats.get("system_cpu_usage", 0)
            sys_pre     = precpu.get("system_cpu_usage", 0)
            online_cpus = cpu_stats.get("online_cpus") or len(
                cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or []
            ) or 1

            cpu_delta = cpu_total - pre_total
            sys_delta = sys_now - sys_pre
            cpu_pct = 0.0
            if sys_delta > 0 and cpu_delta > 0:
                cpu_pct = (cpu_delta / sys_delta) * online_cpus * 100.0
        except Exception:
            cpu_pct = 0.0
            online_cpus = 1

        mem_stats = raw.get("memory_stats", {}) or {}
        mem_usage = int(mem_stats.get("usage", 0) or 0)
        # Subtract cache to match `docker stats` behavior on cgroup v1.
        cache = (mem_stats.get("stats", {}) or {}).get("cache", 0) or 0
        mem_usage = max(0, mem_usage - int(cache))
        mem_limit = int(mem_stats.get("limit", 0) or 0)

        nets = raw.get("networks", {}) or {}
        rx = sum(int((n or {}).get("rx_bytes", 0) or 0) for n in nets.values())
        tx = sum(int((n or {}).get("tx_bytes", 0) or 0) for n in nets.values())

        pids = int((raw.get("pids_stats", {}) or {}).get("current", 0) or 0)

        return ContainerStats(
            cpu_percent=cpu_pct,
            memory_bytes=mem_usage,
            memory_limit=mem_limit,
            network_rx=rx,
            network_tx=tx,
            pids=pids,
            online_cpus=int(online_cpus),
        )

    def logs(self, instance: Instance, *, tail: int = 200) -> str:
        client = self._client_or_raise()
        try:
            c = client.containers.get(container_name_for(instance))
            return c.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        except NotFound:
            return ""
        except APIError as e:
            raise DockerError(str(e)) from e


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_backend: DockerBackend | None = None


def get_backend() -> DockerBackend:
    global _backend
    if _backend is None:
        _backend = DockerBackend()
    return _backend