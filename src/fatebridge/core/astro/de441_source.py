"""One bounded DE441 Earth/Moon/planetary source on the original TDB grid.

Every selected original binary64 coefficient byte, axis and time cell is retained.
Lossless time-chunk storage applies no coefficient quantization.
Source-time chunks change storage only. Earth and Moon use the original EMB,
geocentric Moon and EMRAT, with one source clock and fixed frame convention.
These are source-family computations, not physical accuracy certification.
"""

from __future__ import annotations

import json
import math
import os
import sys
import zlib
from array import array
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple, TypedDict

from fatebridge.core.astro.cartesian import Vector3, rotate_vector
from fatebridge.core.astro.chebyshev import chebyshev_kinematics
from fatebridge.core.astro.coefficient_storage import RecordBlock, unpack_records
from fatebridge.core.astro.de441_storage import BASENAME, MODEL_ID
from fatebridge.core.astro.tdb import geocentric_tdb_state
from fatebridge.utils.errors import EphemerisSourceError

SOURCE_VERSION = "JPL DE441, Park-Folkner-Williams-Boggs 2021"


class Group(TypedDict):
    offset_words: int
    coefficient_count: int
    subintervals: int


class Chunk(TypedDict):
    file: str
    record_count: int


class FrameBias(TypedDict):
    ICRF_to_mean_J2000: list[list[float]]


class Parameters(TypedDict):
    source_TDB_JD_bounds: list[float]
    source_AU_km: float
    source_EMRAT: float
    record_days: float
    record_count: int
    record_size_words: int
    records_per_chunk: int
    groups: dict[str, Group]
    chunks: list[Chunk]
    frame_bias: FrameBias


class SourceKinematics(NamedTuple):
    """AU p/v/a on the native TDB day, with its caller's TDB/TT day ratio.

    Derivatives belong to the selected polynomial: right-hand source cell
    at internal boundaries, left-hand cell at the final source endpoint.
    This does not assert global differentiability of rounded source records.
    """

    position: Vector3
    velocity: Vector3
    acceleration: Vector3
    tdb_rate: float = 1.0


@lru_cache(maxsize=1)
def _parameters() -> Parameters:
    try:
        raw = (
            files("fatebridge")
            .joinpath("data/astronomy")
            .joinpath(BASENAME + ".json")
            .read_bytes()
        )
        result: Parameters = json.loads(raw)
    except (OSError, ValueError) as error:
        raise EphemerisSourceError("jpl_kinematics_invalid") from error
    return result


def coefficient_files_available() -> bool:
    """Check whether every coefficient chunk is present before loading any."""
    archive_dir = os.getenv("FATEBRIDGE_DE441_DIR")
    base = (
        Path(archive_dir)
        if archive_dir
        else files("fatebridge").joinpath("data/astronomy")
    )
    try:
        return all(
            base.joinpath(chunk["file"]).is_file() for chunk in _parameters()["chunks"]
        )
    except (EphemerisSourceError, OSError):
        return False


def source_details() -> dict[str, object]:
    """Describe the verified loaded representation, separately from JPL's file."""
    parameters = _parameters()
    return {
        "source_model_id": MODEL_ID,
        "source_version": SOURCE_VERSION,
        "source_TDB_JD_bounds": list(parameters["source_TDB_JD_bounds"]),
        "source_AU_km": parameters["source_AU_km"],
        "source_EMRAT": parameters["source_EMRAT"],
        "source_representation": "original_DE441_selected_binary64_words_lossless",
        "source_product_producer": "FateBridge; selected JPL original binary64 coefficient bytes retained losslessly on their bounded source grid",
        "original_JPL_file_loaded_at_runtime": False,
    }


@lru_cache(maxsize=2)
def _coefficients(index: int, archive_dir: str | None) -> array[float]:
    parameters = _parameters()
    chunk = parameters["chunks"][index]
    try:
        base = (
            Path(archive_dir)
            if archive_dir
            else files("fatebridge").joinpath("data/astronomy")
        )
        packed = base.joinpath(chunk["file"]).read_bytes()
        data = unpack_records(
            packed,
            [RecordBlock(chunk["record_count"], parameters["record_size_words"] * 8)],
        )
    except (FileNotFoundError, NotADirectoryError) as error:
        raise EphemerisSourceError("de441_archive_missing") from error
    except (OSError, ValueError, EOFError, zlib.error) as error:
        raise EphemerisSourceError("jpl_kinematics_invalid") from error
    result = array("d")
    result.frombytes(data)
    if sys.byteorder != "little":
        result.byteswap()
    return result


def barycentric_state(
    body: str, tdb_days_from_j2000: float | Fraction, *, derivatives: int = 2
) -> SourceKinematics:
    """ICRF AU, AU/TDB-day and AU/TDB-day² on the original source grid."""
    p = _parameters()
    start, end = (jd - 2451545.0 for jd in p["source_TDB_JD_bounds"])
    if not math.isfinite(tdb_days_from_j2000):
        raise ValueError("TDB relative epoch must be finite")
    epoch = Fraction(tdb_days_from_j2000)
    if not start <= epoch <= end:
        raise EphemerisSourceError("jpl_kinematics_outside_source")
    span = p["record_days"]
    index = min(
        int((epoch - Fraction(start)) // Fraction(span)),
        p["record_count"] - 1,
    )
    chunk, local = divmod(index, p["records_per_chunk"])
    words = _coefficients(chunk, os.getenv("FATEBRIDGE_DE441_DIR") or None)
    elapsed = epoch - Fraction(start + index * span)
    states = []
    names = (
        ("EarthMoonBarycenter", "MoonGeocentric")
        if body in {"Earth", "Moon"}
        else (body,)
    )
    for name in names:
        group = p["groups"][name]
        width = span / group["subintervals"]
        subcell = min(int(elapsed // Fraction(width)), group["subintervals"] - 1)
        x = 2 * (elapsed - subcell * Fraction(width)) / Fraction(width) - 1
        count = group["coefficient_count"]
        offset = (
            local * p["record_size_words"] + group["offset_words"] + 3 * subcell * count
        )
        axes = []
        for axis in range(3):
            at = offset + axis * count
            axes.append(
                chebyshev_kinematics(
                    words[at : at + count], x, derivatives=derivatives
                ).in_units(2 / width, p["source_AU_km"])
            )
        states.append(axes)
    if body in {"Earth", "Moon"}:
        emb, moon = states
        resolved = [e.minus(m, 1 + p["source_EMRAT"]) for e, m in zip(emb, moon)]
        if body == "Moon":
            resolved = [e.plus(m) for e, m in zip(resolved, moon)]
    else:
        resolved = states[0]
    vectors = [axis.rounded() for axis in resolved]
    return SourceKinematics(
        (vectors[0][0], vectors[1][0], vectors[2][0]),
        (vectors[0][1], vectors[1][1], vectors[2][1]),
        (vectors[0][2], vectors[1][2], vectors[2][2]),
    )


def mean_j2000_state(
    body: str,
    tt_days_from_j2000: float | Fraction,
    offset_days: float = 0.0,
    *,
    derivatives: int = 2,
) -> SourceKinematics:
    """TT-tagged p/v/a in mean J2000, retaining the native TDB derivatives.

    The velocity supplied to Lorentz aberration is the source coordinate
    velocity, AU/TDB-day. The explicit TDB/TT ratio propagates position and
    observer-velocity derivatives through the full TT and optical mapping.
    """
    # Preserve small nominal offsets and retarded delays before rounding the
    # local source coordinate, rather than adding them to a coarse epoch.
    tt_days = Fraction(tt_days_from_j2000) + Fraction(offset_days)
    clock = geocentric_tdb_state(tt_days, need_rate=derivatives > 0)
    days = tt_days + Fraction(clock.seconds) / 86400
    state = barycentric_state(body, days, derivatives=derivatives)
    bias = _parameters()["frame_bias"]["ICRF_to_mean_J2000"]
    zero = (0.0, 0.0, 0.0)
    return SourceKinematics(
        rotate_vector(state.position, bias),
        rotate_vector(state.velocity, bias) if derivatives >= 1 else zero,
        rotate_vector(state.acceleration, bias) if derivatives == 2 else zero,
        1 + clock.rate_seconds_per_TT_day / 86400,
    )
