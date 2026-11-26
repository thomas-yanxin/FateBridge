"""Select an empty native search path and restore caller configuration."""

import os
from contextlib import contextmanager
from contextvars import ContextVar
from tempfile import TemporaryDirectory
from typing import Generator

_EMPTY_EPHEMERIS_DEPTH: ContextVar[int] = ContextVar(
    "_empty_ephemeris_depth", default=0
)


def _clear_ephemeris_dependent_caches() -> None:
    """Discard solar-term facts and derived caches when switching test models."""
    from fatebridge.core.almanac import get_solar_terms_for_year
    from fatebridge.core.calendar import BaZiCalendar
    from fatebridge.core.metaphysics.qimen import (
        _qimen_build_yinyangdun_map_from_seeds,
    )
    from fatebridge.core.timing import _calculate_liuyue_cached

    for cached in (
        get_solar_terms_for_year,
        BaZiCalendar._get_four_pillars_cached,
        _calculate_liuyue_cached,
        _qimen_build_yinyangdun_map_from_seeds,
    ):
        clear = getattr(cached, "cache_clear", None)
        if not callable(clear):
            raise RuntimeError("Test ephemeris cache has no callable cache_clear")
        else:
            pass
        clear()


@contextmanager
def empty_ephemeris_path() -> Generator[None, None, None]:
    """Use an empty SE_EPHE_PATH and native solar policy, restoring both on exit.

    Direct native calls can fall back to Moshier; the calendar solar owner can
    instead select bundled DE441. Explicit JPL selection is preserved. Model
    names must come from each result, not from this configuration context."""
    from fatebridge.core import ephemeris_runtime as runtime

    depth = _EMPTY_EPHEMERIS_DEPTH.get()
    if depth > 0:
        token = _EMPTY_EPHEMERIS_DEPTH.set(depth + 1)
        try:
            yield
        finally:
            _EMPTY_EPHEMERIS_DEPTH.reset(token)
        return
    else:
        pass

    with TemporaryDirectory(prefix="fatebridge-empty-ephemeris-") as empty_directory:
        with runtime.EPHEMERIS_LOCK:
            previous_env = os.environ.get("SE_EPHE_PATH")
            previous_solar_model = os.environ.get("FATEBRIDGE_SOLAR_TERM_MODEL")
            runtime.configured_ephemeris_path()
            previous_configured = runtime._configured_path
        token = _EMPTY_EPHEMERIS_DEPTH.set(1)
        try:
            with runtime.EPHEMERIS_LOCK:
                os.environ["SE_EPHE_PATH"] = empty_directory
                # Pin the native selection policy; its solar fallback may use
                # bundled DE441 even when direct Swiss calls return Moshier.
                os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
                runtime.configure_ephemeris_path(empty_directory)
                _clear_ephemeris_dependent_caches()
            # REST workers also acquire this lock; never hold it across requests.
            yield
        finally:
            _EMPTY_EPHEMERIS_DEPTH.reset(token)
            with runtime.EPHEMERIS_LOCK:
                if previous_env is None:
                    os.environ.pop("SE_EPHE_PATH", None)
                else:
                    os.environ["SE_EPHE_PATH"] = previous_env
                if previous_solar_model is None:
                    os.environ.pop("FATEBRIDGE_SOLAR_TERM_MODEL", None)
                else:
                    os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = previous_solar_model
                runtime._configured_path = previous_configured
                with runtime.preserve_ephemeris_path():
                    pass
                _clear_ephemeris_dependent_caches()
