"""One bounded DE441 Earth/Moon/planetary source on the original TDB grid.

Every source coefficient slot, axis and time cell is retained. Fixed binary
quanta bound representation error; small coefficients can round to zero.
Source-time chunks change storage only. Earth and Moon use the original EMB,
geocentric Moon and EMRAT, with one source clock and fixed frame convention.
These are source-family computations, not physical accuracy certification.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import zlib
from array import array
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import NamedTuple, TypedDict

from fatebridge.core.astro.cartesian import Vector3, rotate_vector
from fatebridge.core.astro.coefficient_storage import RecordBlock, unpack_records
from fatebridge.core.astro.jpl_kinematics import chebyshev_kinematics
from fatebridge.core.astro.tdb import geocentric_tdb_state
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "bounded_de441_planetary_source_v3"
SOURCE_VERSION = "JPL DE441, Park-Folkner-Williams-Boggs 2021"
SOURCE_URL = (
    "https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/linux_m13000p17000.441"
)
PAPER_URL = "https://doi.org/10.3847/1538-3881/abd414"
FRAME_URL = "https://github.com/liberfa/erfa/blob/v2.0.1/src/bp06.c"
MANIFEST_SHA256 = "b9761f8beed103b9c65cb27e16bded8313c45291b6c53d50526c910b4d1abd08"
_BASENAME = "de441-planetary-0001-9999-v3"


class Group(TypedDict):
    offset_words: int
    coefficient_count: int
    subintervals: int
    quantum_binary_exponent_km: int


class Chunk(TypedDict):
    file: str
    record_count: int
    compressed_sha256: str
    uncompressed_sha256: str


class FrameBias(TypedDict):
    ICRF_to_mean_J2000: list[list[float]]


class Parameters(TypedDict):
    source_file_sha256: str
    source_manifest_sha256: str
    source_header_sha256: str
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
            .joinpath(_BASENAME + ".json")
            .read_bytes()
        )
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError("DE441 source identity changed")
        result: Parameters = json.loads(raw)
    except (OSError, ValueError) as error:
        raise EphemerisSourceError("jpl_kinematics_invalid") from error
    return result


def source_details() -> dict[str, object]:
    """Describe the verified loaded representation, separately from JPL's file."""
    parameters = _parameters()
    return {
        "source_model_id": MODEL_ID,
        "source_url": SOURCE_URL,
        "source_version": SOURCE_VERSION,
        "source_paper_url": PAPER_URL,
        "coefficient_sha256": MANIFEST_SHA256,
        "source_file_sha256": parameters["source_file_sha256"],
        "source_manifest_sha256": parameters["source_manifest_sha256"],
        "source_header_sha256": parameters["source_header_sha256"],
        "source_TDB_JD_bounds": list(parameters["source_TDB_JD_bounds"]),
        "source_AU_km": parameters["source_AU_km"],
        "source_EMRAT": parameters["source_EMRAT"],
        "source_representation": "original_DE441_cells_and_slots_bounded_binary_coefficient_quanta",
        "source_product_producer": "FateBridge; JPL original coefficient records retained on their source grid with bounded coefficient quantization",
        "original_JPL_file_loaded_at_runtime": False,
    }


@lru_cache(maxsize=2)
def _coefficients(index: int) -> array[int]:
    parameters = _parameters()
    chunk = parameters["chunks"][index]
    try:
        packed = (
            files("fatebridge")
            .joinpath("data/astronomy")
            .joinpath(chunk["file"])
            .read_bytes()
        )
        if hashlib.sha256(packed).hexdigest() != chunk["compressed_sha256"]:
            raise ValueError("DE441 coefficient archive changed")
        data = unpack_records(
            packed,
            [RecordBlock(chunk["record_count"], parameters["record_size_words"] * 8)],
        )
        if hashlib.sha256(data).hexdigest() != chunk["uncompressed_sha256"]:
            raise ValueError("DE441 coefficient words changed")
    except (OSError, ValueError, EOFError, zlib.error) as error:
        raise EphemerisSourceError("jpl_kinematics_invalid") from error
    result = array("q")
    result.frombytes(data)
    if sys.byteorder != "little":
        result.byteswap()
    return result


def barycentric_state(
    body: str, tdb_days_from_j2000: float | Fraction
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
    words = _coefficients(chunk)
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
        x = float(2 * (elapsed - subcell * Fraction(width)) / Fraction(width) - 1)
        count = group["coefficient_count"]
        offset = (
            local * p["record_size_words"] + group["offset_words"] + 3 * subcell * count
        )
        axes = []
        for axis in range(3):
            at = offset + axis * count
            position, velocity, acceleration = chebyshev_kinematics(
                [
                    math.ldexp(value, group["quantum_binary_exponent_km"])
                    for value in words[at : at + count]
                ],
                x,
            )
            axes.append(
                (
                    position / p["source_AU_km"],
                    velocity * 2 / width / p["source_AU_km"],
                    acceleration * (2 / width) ** 2 / p["source_AU_km"],
                )
            )
        states.append(
            SourceKinematics(
                (axes[0][0], axes[1][0], axes[2][0]),
                (axes[0][1], axes[1][1], axes[2][1]),
                (axes[0][2], axes[1][2], axes[2][2]),
            )
        )
    if body in {"Earth", "Moon"}:
        emb, moon = states
        vectors = []
        for ev, mv in zip(
            (emb.position, emb.velocity, emb.acceleration),
            (moon.position, moon.velocity, moon.acceleration),
        ):
            x, y, z = (e - m / (1 + p["source_EMRAT"]) for e, m in zip(ev, mv))
            if body == "Moon":
                x, y, z = (e + m for e, m in zip((x, y, z), mv))
            vectors.append((x, y, z))
        return SourceKinematics(vectors[0], vectors[1], vectors[2])
    return states[0]


def mean_j2000_state(
    body: str, tt_days_from_j2000: float, offset_days: float = 0.0
) -> SourceKinematics:
    """TT-tagged p/v/a in mean J2000, retaining the native TDB derivatives.

    The velocity supplied to Lorentz aberration is the source coordinate
    velocity, AU/TDB-day. The explicit TDB/TT ratio propagates position and
    observer-velocity derivatives through the full TT and optical mapping.
    """
    # Preserve small nominal offsets and retarded delays before rounding the
    # local source coordinate, rather than adding them to a coarse epoch.
    clock = geocentric_tdb_state(tt_days_from_j2000 + offset_days)
    days = (
        Fraction(tt_days_from_j2000)
        + Fraction(offset_days)
        + Fraction(clock.seconds) / 86400
    )
    state = barycentric_state(body, days)
    bias = _parameters()["frame_bias"]["ICRF_to_mean_J2000"]
    return SourceKinematics(
        rotate_vector(state.position, bias),
        rotate_vector(state.velocity, bias),
        rotate_vector(state.acceleration, bias),
        1 + clock.rate_seconds_per_TT_day / 86400,
    )
