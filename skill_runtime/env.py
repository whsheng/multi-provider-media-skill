"""
Local environment file loader.
"""

import os
from pathlib import Path
from typing import Optional

_LOADED = False


def load_local_env(filename: str = ".env.local", override: bool = False) -> Optional[Path]:
    """
    Load key=value pairs from the project-local environment file.

    Existing environment variables win by default.
    """
    global _LOADED

    if _LOADED:
        return None

    env_path = Path(__file__).resolve().parent.parent / filename
    if not env_path.exists():
        _LOADED = True
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _normalize_value(value.strip())

        if not key:
            continue

        if key in os.environ and not override:
            continue

        os.environ[key] = value

    _LOADED = True
    return env_path


def _normalize_value(value: str) -> str:
    if not value:
        return value

    if value[0] == value[-1] and value[0] in {"'", '"'} and len(value) >= 2:
        return value[1:-1]

    # Remove inline comments for unquoted values: KEY=value # comment
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()

    return value
