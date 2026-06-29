from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


class BusResolutionError(RuntimeError):
    """Raised when a default bus path cannot be derived."""


def safe_project_slug(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9.]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip(".-")
    return slug or "project"


def project_key(value: str) -> str:
    normalized = _project_key_source(value)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{safe_project_slug(normalized)}-{digest}"


def canonical_origin(value: str) -> str:
    origin = value.strip()
    if not origin:
        raise BusResolutionError("git origin is empty; pass --project or --bus")

    parsed = urlparse(origin)
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.netloc:
        host = _canonical_url_host(parsed)
        path = parsed.path.lstrip("/")
        return _canonical_host_path(host, path)

    scp_like = re.match(r"^(?:(?P<user>[^@/:]+)@)?(?P<host>[^:]+):(?P<path>.+)$", origin)
    if scp_like:
        return _canonical_host_path(scp_like.group("host").lower(), scp_like.group("path"))

    raise BusResolutionError("unsupported git origin format; pass --project or --bus")


def resolve_bus_path(
    bus: str | os.PathLike[str] | None,
    project: str | None,
    cwd: str | os.PathLike[str] | None = None,
) -> Path:
    if bus is not None:
        return Path(bus).expanduser()

    env_bus = os.environ.get("AGENT_COMM_BUS")
    if env_bus:
        return Path(env_bus).expanduser()

    if project:
        return _default_bus_path(project)

    origin = _git_origin(Path(cwd) if cwd is not None else Path.cwd())
    if origin is None:
        raise BusResolutionError("Could not determine project; pass --project or --bus")

    return _default_bus_path(canonical_origin(origin))


def _project_key_source(value: str) -> str:
    try:
        return canonical_origin(value)
    except BusResolutionError:
        return value.strip()


def _default_bus_path(value: str) -> Path:
    return Path.home() / ".agent-comm" / "projects" / project_key(value) / "bus.sqlite"


def _canonical_url_host(parsed) -> str:
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    default_ports = {"ssh": 22, "git": 22, "http": 80, "https": 443}
    if port is not None and port != default_ports[parsed.scheme]:
        return f"{hostname}:{port}"
    return hostname


def _canonical_host_path(host: str, path: str) -> str:
    normalized_path = path.strip().rstrip("/")
    if normalized_path.endswith(".git"):
        normalized_path = normalized_path[:-4]
    normalized_path = normalized_path.strip("/")
    if not host or not normalized_path:
        raise BusResolutionError("unsupported git origin format; pass --project or --bus")
    return f"{host}/{normalized_path}".lower()


def _git_origin(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
