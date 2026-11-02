"""
Runtime configuration helpers for FateBridge.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

# src layout: this module is ``<repo>/src/fatebridge/utils/runtime.py``, so the
# repo root (which holds the developer-only ``.env``) is three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_runtime_env(
    path: Optional[str | Path] = None,
    *,
    override: bool = False,
) -> Dict[str, str]:
    """
    Load key/value pairs from a local .env file into os.environ.

    The parser intentionally stays minimal: FateBridge only needs plain
    ``KEY=value`` pairs for local runtime configuration.
    """

    env_path = Path(path) if path is not None else DEFAULT_ENV_PATH
    if not env_path.exists():
        return {}

    loaded: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not key:
            continue

        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value

    return loaded


def get_log_level(default: str = "INFO") -> str:
    return os.getenv("LOG_LEVEL", default).strip().upper() or default


def parse_allowed_origins(
    default: str = "http://localhost:3000",
) -> List[str]:
    origins = os.getenv("ALLOWED_ORIGINS", default)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_api_key_header_name(default: str = "X-API-Key") -> str:
    header_name = os.getenv("API_KEY_HEADER_NAME", default).strip()
    return header_name or default


def parse_api_keys(
    raw_value: Optional[str] = None,
) -> Dict[str, str]:
    """
    Parse configured API keys from ``FATEBRIDGE_API_KEYS``.

    Supports either ``name:secret`` entries or unnamed ``secret`` entries.
    Unnamed entries are assigned stable ``keyN`` identifiers based on position.
    """

    source = (
        raw_value if raw_value is not None else os.getenv("FATEBRIDGE_API_KEYS", "")
    )
    if not source.strip():
        return {}

    parsed: Dict[str, str] = {}
    for index, item in enumerate(source.split(","), start=1):
        token = item.strip()
        if not token:
            raise ValueError(f"FATEBRIDGE_API_KEYS entry {index} is empty")

        if ":" in token:
            key_id, secret = token.split(":", 1)
            key_id = key_id.strip()
            secret = secret.strip()
        else:
            key_id = f"key{index}"
            secret = token

        if not key_id or not secret:
            raise ValueError(
                f"FATEBRIDGE_API_KEYS entry {index} requires a name and secret"
            )

        if key_id in parsed:
            raise ValueError(f"FATEBRIDGE_API_KEYS entry {index} has a duplicate name")

        parsed[key_id] = secret

    return parsed
