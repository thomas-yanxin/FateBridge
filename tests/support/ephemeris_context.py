"""Select a real Moshier model for current tests and restore caller state."""

import os
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Generator


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
        clear()


@contextmanager
def moshier_ephemeris() -> Generator[None, None, None]:
    """Force Moshier despite repo-local data, restoring shared state on exit."""
    from fatebridge.core import ephemeris_runtime as runtime

    with TemporaryDirectory(prefix="fatebridge-moshier-") as empty_directory:
        with runtime._EPHEMERIS_LOCK:
            previous_env = os.environ.get("SE_EPHE_PATH")
            previous_solar_model = os.environ.get("FATEBRIDGE_SOLAR_TERM_MODEL")
            previous_path = runtime.configured_ephemeris_path()
            previous_configured = runtime._configured_path
        try:
            with runtime._EPHEMERIS_LOCK:
                os.environ["SE_EPHE_PATH"] = empty_directory
                # Auto may choose an analytic Sun even when a direct Swiss
                # probe falls back to Moshier. Pin the actual term solver too.
                os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] = "native"
                runtime.configure_ephemeris_path(empty_directory)
                _clear_ephemeris_dependent_caches()
            # REST workers also acquire this lock; never hold it across requests.
            yield
        finally:
            with runtime._EPHEMERIS_LOCK:
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
