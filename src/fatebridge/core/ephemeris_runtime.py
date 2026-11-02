"""Shared Swiss Ephemeris runtime helpers.

This module is the single import point for the optional ``swisseph`` dependency.
Centralising it lets FateBridge do two things consistently across every module
that touches the ephemeris (charts, almanac, predictive directions):

* Apply an operator-supplied data-file path in each calling thread via the
  ``SE_EPHE_PATH`` environment variable. Swiss Ephemeris silently falls back to
  its built-in Moshier analytical model when no ``.se1`` data files are
  reachable; official files enable data-backed ``SWIEPH`` calculations. The
  underlying DE edition must be read from the active file headers.
* Translate a ``calc_ut`` return flag into the reported top-level model, and
  qualify required physical file contexts separately. A Swiss top-level flag
  can coexist with an analytical lunar dependency in the native library.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import RLock, local
from typing import Any, Iterator, Optional

from fatebridge.core.astro_models import native_rotation_call
from fatebridge.core.compressed_ephemeris import compressed_endpoint_call
from fatebridge.core.ephemeris_installation import (
    MAX_EPHEMERIS_PATH_BYTES,
    verified_user_ephemeris_dir,
)
from fatebridge.core.jpl_ephemeris import (
    check_jpl_result,
    configured_jpl_file,
    prepare_jpl_call,
)
from fatebridge.utils.errors import EphemerisSourceError

try:  # pragma: no cover - optional runtime dependency
    import swisseph as swe
except ImportError:  # pragma: no cover - exercised only in minimal installs
    swe = None  # type: ignore[assignment]

# Repo root that holds the optional ``ephe/`` data directory (gitignored .se1
# files, never redistributed, so they live outside the package). Module lives at
# ``<root>/src/fatebridge/core/ephemeris_runtime.py``, so the root is three
# parents up.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_EPHEMERIS_LOCK = RLock()
_configured_path: Optional[str] = None
_THREAD_STATE = local()
# Swiss 2.10's AS_MAXCH=256 reserves a trailing separator and file-name space.
# Longer inputs are silently replaced by the library's compiled default path.
_MAX_EPHE_PATH_BYTES = MAX_EPHEMERIS_PATH_BYTES


def _validated_ephemeris_path(path: Optional[str]) -> Optional[str]:
    if path and ("\0" in path or len(os.fsencode(path)) > _MAX_EPHE_PATH_BYTES):
        raise ValueError(
            "Swiss Ephemeris search path must contain no NUL and fit within "
            f"{_MAX_EPHE_PATH_BYTES} encoded bytes; otherwise the library silently uses its default"
        )
    return path or None


def default_ephe_dir() -> Optional[str]:
    """Prefer project-local files, then a complete verified user-cache profile.

    Lets a checkout that ran ``python -m fatebridge.fetch_ephe`` pick up full
    precision with zero configuration — no environment variable required. The
    directory is only reported when it actually contains ``.se1`` files, so an
    empty folder does not mask cache discovery or the Moshier fallback. Explicit
    environment or function paths are handled by configure_ephemeris_path first.
    """
    candidate = _PROJECT_ROOT / "ephe"
    if candidate.is_dir() and any(candidate.glob("*.se1")):
        return str(candidate)
    return verified_user_ephemeris_dir()


def configured_ephemeris_path() -> Optional[str]:
    """Return the selected path, including Swiss's nonempty environment override."""
    with _EPHEMERIS_LOCK:
        return _validated_ephemeris_path(
            os.environ.get("SE_EPHE_PATH") or _configured_path
        )


def effective_ephemeris_search_path() -> Optional[str]:
    """Include the loaded library's compiled defaults when no path was selected.

    These defaults can include the current directory and optional auxiliary
    files even when physical bodies fall back to Moshier.
    """
    with _EPHEMERIS_LOCK:
        return configured_ephemeris_path() or getattr(swe, "EPHE_PATH", None)


def configure_ephemeris_path(path: Optional[str] = None) -> Optional[str]:
    """Point Swiss Ephemeris at ``.se1`` data files, if any can be located.

    Resolution order: nonempty ``SE_EPHE_PATH`` (the C library's override), then
    the explicit ``path`` argument, then a project-local ``ephe/`` directory (see
    :func:`default_ephe_dir`). Returns the path that was applied, or ``None``
    when none was found (or swisseph is unavailable), in which case swisseph
    keeps using its built-in Moshier model.

    Some Swiss Ephemeris builds keep their C state in thread-local storage.
    Direct calls also initialise the path in their calling thread; configuring
    the importing thread alone is insufficient for a fresh REST worker.
    """
    global _configured_path
    with _EPHEMERIS_LOCK:
        if swe is None:
            return None
        resolved = _validated_ephemeris_path(
            os.environ.get("SE_EPHE_PATH")
            or (path if path is not None else default_ephe_dir())
        )
        # Initialisation and reset also matter with no custom data directory.
        swe.set_ephe_path(resolved or "")
        _THREAD_STATE.signature = (id(swe), resolved)
        _configured_path = resolved
        return resolved


@contextmanager
def lock_ephemeris_configuration() -> Iterator[None]:
    """Pin managed configuration without touching the caller's native state."""
    with _EPHEMERIS_LOCK:
        yield


@contextmanager
def preserve_ephemeris_path() -> Iterator[None]:
    """Isolate third-party configuration changes from FateBridge calculations.

    Kerykeion changes the shared Swiss Ephemeris data path. Hold the same lock
    used by direct ephemeris calls until its calculation and path restoration
    finish, including when the third-party call raises.
    """
    with _EPHEMERIS_LOCK:
        try:
            yield
        finally:
            if swe is not None:
                selected = configured_ephemeris_path()
                swe.set_ephe_path(selected or "")
                _THREAD_STATE.signature = (id(swe), selected)


def ephemeris_call(operation: str, *args: Any, **kwargs: Any) -> Any:
    """Run a direct Swiss Ephemeris call outside third-party path changes."""
    from fatebridge.core.physical_source_observation import native_call_policy

    with (
        _EPHEMERIS_LOCK,
        native_call_policy(
            swe,
            operation,
            args,
            kwargs,
            probe_call=ephemeris_call,
            model_from_retflag=ephemeris_model_from_retflag,
        ) as observe,
    ):
        if swe is None:
            raise ImportError("swisseph is unavailable")
        selected = configured_ephemeris_path()
        signature = (id(swe), selected)
        if getattr(_THREAD_STATE, "signature", None) != signature:
            # deltat_ex requires initialisation even with no .se1 files.
            # Apply once per thread/path, avoiding a cache reset on every call.
            swe.set_ephe_path(selected or "")
            _THREAD_STATE.signature = signature
        jpl = configured_jpl_file()
        if jpl is None:
            return observe(
                compressed_endpoint_call(
                    swe,
                    operation,
                    args,
                    kwargs,
                    native_rotation_call,
                    configured_path=configured_ephemeris_path,
                )
            )
        try:
            args, kwargs, strict_result = prepare_jpl_call(
                swe, jpl, operation, args, kwargs
            )
            result = native_rotation_call(swe, operation, args, kwargs)
        except EphemerisSourceError:
            raise
        except Exception as error:
            raise EphemerisSourceError("jpl_native_failed") from error
        if strict_result:
            check_jpl_result(swe, result, operation)
        return observe(result)


def ephemeris_model_from_retflag(retflag: int) -> str:
    """Map a ``swisseph.calc_ut`` return flag to the model that produced it.

    swisseph echoes its top-level ephemeris in the returned flag, which
    may differ from the one requested (e.g. ``FLG_SWIEPH`` requested but the data
    files are missing, so it quietly downgraded to Moshier). This alone does
    not identify every internal dependency: inspected sweplan() can use a
    Moshier Moon with a SWIEPH planet/Earth context. Managed physical calls
    separately qualify the required observed file windows. Possible values:

    * ``"swieph"``  – Swiss Ephemeris compressed data files
    * ``"moshier"`` – built-in Moshier analytical model (no data files needed)
    * ``"jpl"``     – JPL ephemeris data files
    * ``"error"``   – swisseph reported a soft failure (``retflag < 0``)
    * ``"unknown"`` – flag set none of the recognised ephemeris bits
    * ``"unavailable"`` – swisseph itself is not installed
    """
    if swe is None:
        return "unavailable"
    if retflag < 0:
        return "error"
    if retflag & swe.FLG_MOSEPH:
        return "moshier"
    if retflag & swe.FLG_JPLEPH:
        return "jpl"
    if retflag & swe.FLG_SWIEPH:
        return "swieph"
    return "unknown"


# Apply any operator-supplied ephemeris path at import time so it is in effect
# before the first calc_ut call, regardless of which module imports swe first.
configure_ephemeris_path()
