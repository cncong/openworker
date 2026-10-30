"""Process-level `.env` loading for local server configuration."""

from __future__ import annotations

import os
from pathlib import Path


def load_root_dotenv(*, start: Path | None = None, override: bool = False) -> Path | None:
    """Load the nearest project-root `.env` into ``os.environ``.

    Real environment variables keep priority by default, so Docker/Kubernetes/systemd
    secrets are not overwritten by a checked-out working tree.
    """
    explicit = os.environ.get("COWORKER_ENV_FILE")
    if explicit:
        path = Path(explicit).expanduser()
        return _load_file(path, override=override)

    root = _project_root(start or Path.cwd())
    path = root / ".env"
    return _load_file(path, override=override)


def _project_root(start: Path) -> Path:
    here = start.expanduser().resolve()
    if here.is_file():
        here = here.parent
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists():
            return parent

    package_root = Path(__file__).resolve().parents[1]
    for parent in (package_root, *package_root.parents):
        if (parent / "pyproject.toml").is_file() or (parent / ".git").exists():
            return parent
    return here


def _load_file(path: Path, *, override: bool) -> Path | None:
    if not path.is_file():
        return None
    for key, value in _parse(path).items():
        if override or key not in os.environ:
            os.environ[key] = value
    return path


def _parse(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        out[key] = _clean_value(value.strip())
    return out


def _clean_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value

