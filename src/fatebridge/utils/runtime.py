"""Load local environment settings and parse runtime configuration."""

from __future__ import annotations

import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)

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

    loaded: dict[str, str] = {}
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


def parse_allowed_origins() -> list[str]:
    origins = os.getenv("ALLOWED_ORIGINS", "")
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

    parsed: dict[str, str] = {}
    for index, entry in enumerate(source.split(","), start=1):
        token = entry.strip()
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


def get_api_host(default: str = "0.0.0.0") -> str:
    return os.getenv("API_HOST", default).strip() or default


def get_api_port(default: int = 8010) -> int:
    raw = os.getenv("API_PORT")
    if raw is None or not raw.strip():
        return default
    return int(raw)


def get_mcp_families() -> str | None:
    raw = os.getenv("FATEBRIDGE_MCP_FAMILIES", "").strip()
    return raw or None


def is_strict_output_validation_enabled() -> bool:
    return os.getenv("FATEBRIDGE_STRICT_OUTPUT_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_heavy_calc_max_concurrency(default: int) -> int:
    fallback = max(1, default)
    raw = os.getenv("FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY")
    if raw is None:
        return fallback
    try:
        return max(1, int(raw))
    except ValueError:
        LOGGER.warning(f"Invalid heavy calculation limit; using {fallback}")
        return fallback


def get_de441_dir() -> str | None:
    raw = os.getenv("FATEBRIDGE_DE441_DIR", "").strip()
    return raw or None


def get_jpl_file() -> str | None:
    return os.getenv("FATEBRIDGE_JPL_FILE") or None


def get_solar_term_model(default: str = "auto") -> str:
    return os.getenv("FATEBRIDGE_SOLAR_TERM_MODEL", default).strip().lower()


def get_codex_cli_path() -> str | None:
    raw = os.getenv("CODEX_CLI_PATH", "").strip()
    return raw or None


def is_codex_desktop_originator() -> bool:
    return os.getenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") == "Codex Desktop"
