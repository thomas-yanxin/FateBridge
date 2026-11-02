"""Explicit Swiss Sun file contexts without changing the physical epoch."""

from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from fatebridge.utils.errors import EphemerisSourceError

from .ephemeris_runtime import lock_ephemeris_configuration

POLICY_ID = (
    "same_epoch_moshier_preflight_then_requested_swiss_before_fixed_source_bisection_v1"
)
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c#L348-L380"


def _signature(path: Path) -> tuple[int, ...]:
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@lru_cache(maxsize=64)
def _digest(path: Path, signature: tuple[int, ...]) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    if _signature(path) != signature:
        raise EphemerisSourceError("solar_configuration_changed")
    return result.hexdigest()


def native_solar_file_context(native: Any) -> dict[str, Any] | None:
    """Observed slots, not a complete atomic read set or an accuracy proof."""
    getter = getattr(native, "get_current_file_data", None)
    if not callable(getter):
        return None
    windows = []
    for slot in (0, 1):
        filename, start, end, edition = getter(slot)
        if (
            not filename
            or not all(math.isfinite(x) for x in (start, end))
            or start >= end
        ):
            return None
        path = Path(filename).absolute()
        try:
            signature = _signature(path)
            digest = _digest(path, signature)
        except OSError as exc:
            raise EphemerisSourceError("solar_native_context_unavailable") from exc
        windows.append(
            dict(
                slot=slot,
                filename=path.name,
                sha256=digest,
                bytes=signature[2],
                start_jd_tt=float(start),
                end_jd_tt=float(end),
                de_number=int(edition),
            )
        )
    return dict(
        policy_id=POLICY_ID,
        selection_method="same_TT_Moshier_then_requested_Swiss",
        file_windows=windows,
        physical_target_epoch_shifted=False,
        preflight_state_returned_as_target=False,
        physical_accuracy_certified=False,
        source_url=SOURCE_URL,
        scope="Observed final-refinement Sun file contexts and metadata-keyed file digests; not atomic reads, complete dependency sets or independent physical accuracy",
    )


def prime_swiss_solar_context(
    jd_tt: float,
    *,
    native: Any,
    invoke: Callable[..., Any],
    capture_context: bool = True,
) -> tuple[Any, dict[str, Any] | None]:
    """Select the requested Swiss source at this same TT point via public APIs.

    Swiss closes computed states/files when its requested ephemeris changes.
    The built-in preflight's coordinate is discarded. No set_ephe_path,
    set_tid_acc, set_delta_t_userdef or private C state is changed here.
    Call only in the registered modern/guard solar-year interval, where the
    built-in Sun is available. Strict JPL and actual Moshier stay on their
    own paths. The caller checks the final returned model.
    """
    with lock_ephemeris_configuration():
        _, flags = invoke("calc", jd_tt, native.SUN, native.FLG_MOSEPH)
        if flags != native.FLG_MOSEPH:
            raise EphemerisSourceError("coordinate_contract_changed")
        result = invoke("calc", jd_tt, native.SUN, native.FLG_SWIEPH)
        context = (
            native_solar_file_context(native)
            if capture_context and result[1] == native.FLG_SWIEPH
            else None
        )
        return result, context
