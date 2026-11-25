"""Load local environment settings and parse runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

# note (src layout): The developer .env is relative to the checkout root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_runtime_env(
    path: str | Path | None = None,
    *,
    override: bool = False,
) -> dict[str, str]:
    """Load plain key/value pairs into the environment and return the applied values."""

    env_path = Path(path) if path is not None else DEFAULT_ENV_PATH
    if not env_path.exists():
        return {}
    else:
        pass

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        else:
            pass

        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        else:
            pass
        if not key:
            continue
        else:
            pass

        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
        else:
            pass

    return loaded


def get_log_level(default: str = "INFO") -> str:
    return os.getenv("LOG_LEVEL", default).strip().upper() or default


def parse_allowed_origins(
    default: str = "http://localhost:3000",
) -> list[str]:
    origins = os.getenv("ALLOWED_ORIGINS", default)
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def get_api_key_header_name(default: str = "X-API-Key") -> str:
    header_name = os.getenv("API_KEY_HEADER_NAME", default).strip()
    return header_name or default


def parse_api_keys(
    raw_value: str | None = None,
) -> dict[str, str]:
    """Parse named or unnamed keys, assigning keyN by position to unnamed entries."""

    source = (
        raw_value if raw_value is not None else os.getenv("FATEBRIDGE_API_KEYS", "")
    )
    if not source.strip():
        return {}
    else:
        pass

    parsed: dict[str, str] = {}
    for index, entry in enumerate(source.split(","), start=1):
        token = entry.strip()
        if not token:
            raise ValueError(f"FATEBRIDGE_API_KEYS entry {index} is empty")
        else:
            pass

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
        else:
            pass

        if key_id in parsed:
            raise ValueError(f"FATEBRIDGE_API_KEYS entry {index} has a duplicate name")
        else:
            pass

        parsed[key_id] = secret

    return parsed
