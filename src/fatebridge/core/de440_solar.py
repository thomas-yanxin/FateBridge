"""Dependency-free evaluation of losslessly extracted DE440 type2 records.

Geocentric ERFA dtdb is adapted from ERFA/SOFA; the full BSD conditions are
in data/astronomy/erfa-license.txt. No provider endorses FateBridge.
Runtime data are original position coefficients, never event-time references.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, TypedDict

from fatebridge.core.analytic_solar import (
    C_AU_DAY,
    aberration,
    apparent_ecliptic,
)
from fatebridge.core.analytic_solar import profile as frame_profile
from fatebridge.core.astro.coefficient_storage import RecordBlock, unpack_records
from fatebridge.core.astro.tdb import COEFFICIENT_SHA256 as TDB_SHA256
from fatebridge.core.astro.tdb import Parameters as TDBParameters
from fatebridge.core.astro.tdb import fairhead_state
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "fatebridge_de440_solar_v1"
HISTORICAL_MODEL_ID = "fatebridge_de440_solar_historical_v1"
EXTENDED_MODEL_ID = "fatebridge_de440_solar_extended_v1"
CANPING_MODEL_ID = "fatebridge_de440_solar_canping_v1"
CANPING_EXTENDED_MODEL_ID = "fatebridge_de440_solar_canping_extended_v1"
ATLAS_BASENAME = "de440-solar-record-atlas-v1"
ATLAS_MANIFEST_SHA256 = (
    "b05993b79f7dc4cd695f36ee9e3a92d0306052e4d410d4d25c09f05ab8dd9183"
)
_MANIFEST_SHA256 = {
    "fatebridge_de440_solar_canping_extended_v1": "077ac65e3134162e7f76a4275fbe1b3f4a5c72a9b7686e97c5f85eb197ad687d",
    "fatebridge_de440_solar_canping_v1": "a74949e48aadcdcd7af99c6f128acd12aa5713d4f3df68fd6299e1ce48b40c4b",
    "fatebridge_de440_solar_extended_v1": "eb5d7bba7902142702f209183d057e15180a994bc792e6ab6ad40a4586bd03f5",
    "fatebridge_de440_solar_historical_v1": "e073acaf81593b21078706a9efe95073efebc2e42712c384788fa6f14e7d9e95",
    "fatebridge_de440_solar_v1": "2bdda66ee61ca065401888629dd4434df6ccc535fdfe20f0c68b3c5a56752145",
}
_PROFILE_FILES = {
    MODEL_ID: "de440-solar-v1",
    HISTORICAL_MODEL_ID: "de440-solar-historical-v1",
    EXTENDED_MODEL_ID: "de440-solar-extended-v1",
    CANPING_MODEL_ID: "de440-solar-canping-v1",
    CANPING_EXTENDED_MODEL_ID: "de440-solar-canping-extended-v1",
}
AU_KM = 149597870.7
Vector = tuple[float, float, float]


class RecordSegment(TypedDict):
    center: int
    target: int
    initial_seconds_from_j2000_tdb: float
    interval_seconds: float
    record_size_doubles: int
    record_count: int
    offset_bytes: int
    bytes: int
    sha256: str


class SolarManifest(TypedDict):
    model_id: str
    version: str
    source: dict[str, str]
    storage: str
    file: str
    compressed_sha256: str
    uncompressed_sha256: str
    uncompressed_bytes: int
    tdb_coefficient_sha256: str
    segments: list[RecordSegment]
    derived_product_producer: dict[str, str | bool]
    software_solar_term_years: list[int]
    public_auto_and_de440_input_years: list[int]
    projection_origin_civil_years: list[int]


class _AtlasManifest(TypedDict):
    file: str
    compressed_sha256: str
    uncompressed_sha256: str
    segments: list[RecordSegment]


@lru_cache(maxsize=1)
def _coefficient_data() -> bytes:
    folder = files("fatebridge").joinpath("data/astronomy")
    try:
        metadata = folder.joinpath(ATLAS_BASENAME + ".json").read_bytes()
        if hashlib.sha256(metadata).hexdigest() != ATLAS_MANIFEST_SHA256:
            raise ValueError("DE440 source record atlas identity changed")
        manifest: _AtlasManifest = json.loads(metadata)
        packed = folder.joinpath(manifest["file"]).read_bytes()
        if hashlib.sha256(packed).hexdigest() != manifest["compressed_sha256"]:
            raise ValueError("DE440 source record archive changed")
        data = unpack_records(
            packed,
            [
                RecordBlock(s["record_count"], s["record_size_doubles"] * 8)
                for s in manifest["segments"]
            ],
        )
        if hashlib.sha256(data).hexdigest() != manifest["uncompressed_sha256"]:
            raise ValueError("DE440 source coefficient words changed")
    except (OSError, ValueError, EOFError, zlib.error) as error:
        raise EphemerisSourceError("solar_de440_invalid") from error
    return data


@dataclass(frozen=True)
class _Profile:
    manifest: SolarManifest
    data: bytes
    manifest_sha256: str
    tdb: TDBParameters
    tdb_sha256: str


@lru_cache(maxsize=5)
def _profile(profile_id: str = MODEL_ID) -> _Profile:
    folder = files("fatebridge").joinpath("data/astronomy")
    try:
        basename = _PROFILE_FILES[profile_id]
        metadata = folder.joinpath(basename + ".json").read_bytes()
        if hashlib.sha256(metadata).hexdigest() != _MANIFEST_SHA256[profile_id]:
            raise ValueError("DE440 selected profile identity changed")
        manifest: SolarManifest = json.loads(metadata)
        tdb_raw = folder.joinpath("geocentric-tdb-v1.json").read_bytes()
        if hashlib.sha256(tdb_raw).hexdigest() != TDB_SHA256:
            raise ValueError("Geocentric TDB source terms changed")
        tdb: TDBParameters = json.loads(tdb_raw)
    except (OSError, ValueError, KeyError) as error:
        raise EphemerisSourceError("solar_de440_invalid") from error
    return _Profile(
        manifest,
        _coefficient_data(),
        hashlib.sha256(metadata).hexdigest(),
        tdb,
        TDB_SHA256,
    )


def _selected_profile(profile_id: str) -> _Profile:
    # Preserve the established zero-argument default loader (and its source
    # failure contract); historical data have a distinct cache entry.
    return _profile() if profile_id == MODEL_ID else _profile(profile_id)


def geocentric_tdb_minus_tt(jd_tt: float, *, profile_id: str = MODEL_ID) -> float:
    """Full geocentric ERFA Fairhead model, seconds; no observer terms."""
    if not math.isfinite(jd_tt):
        raise ValueError("TT epoch must be finite")
    return geocentric_tdb_minus_tt_relative(jd_tt - 2451545.0, profile_id=profile_id)


def geocentric_tdb_minus_tt_relative(
    days_from_j2000: float, *, profile_id: str = MODEL_ID
) -> float:
    """Same Fairhead series with its relative epoch supplied directly."""
    if not math.isfinite(days_from_j2000):
        raise ValueError("TT relative epoch must be finite")
    rows = _selected_profile(profile_id).tdb["fairhead_terms"]
    return fairhead_state(days_from_j2000, rows).seconds


def state(
    pair: tuple[int, int],
    tdb_days_from_j2000: float,
    *,
    profile_id: str = MODEL_ID,
    fractional_day: float = 0.0,
) -> tuple[Vector, Vector]:
    """Original type2 Chebyshev position km and derivative km/day."""
    if not all(math.isfinite(v) for v in (tdb_days_from_j2000, fractional_day)):
        raise ValueError("TDB epoch must be finite")
    p = _selected_profile(profile_id)
    s = next(
        (s for s in p.manifest["segments"] if (s["center"], s["target"]) == pair),
        None,
    )
    if s is None:
        raise ValueError("Unsupported DE440 solar body pair")
    initial, span = s["initial_seconds_from_j2000_tdb"], s["interval_seconds"]
    # Separate quotient/remainder before adding large epochs, preserving the
    # fractional second at the same interval grid as the original SPK reader.
    i0, o0 = divmod(-initial, span)
    i1, o1 = divmod(tdb_days_from_j2000 * 86400, span)
    # Do not add the small fraction to the large elapsed epoch. The default
    # zero fraction retains the scalar evaluator's arithmetic unchanged.
    i2, offset = divmod(o0 + o1 + fractional_day * 86400, span)
    index = int(i0 + i1 + i2)
    if index == s["record_count"] and offset == 0:
        index -= 1
        offset += span
    if not 0 <= index < s["record_count"]:
        raise EphemerisSourceError("solar_de440_range")
    size = s["record_size_doubles"]
    record = struct.unpack_from(
        "<" + "d" * size, p.data, s["offset_bytes"] + index * size * 8
    )
    midpoint = initial + (index + 0.5) * span
    if record[0] != midpoint or record[1] != span / 2:
        raise EphemerisSourceError("solar_de440_invalid")
    x = 2 * offset / span - 1
    count = (size - 2) // 3
    positions, velocities = [], []
    # Direct Chebyshev recurrence and its analytic derivative, separate from
    # jplephem's Clenshaw evaluator used as the interpolation comparator.
    for axis in range(3):
        coefficients = record[2 + axis * count : 2 + (axis + 1) * count]
        previous, current, dprevious, dcurrent = 1.0, x, 0.0, 1.0
        value = coefficients[0] + coefficients[1] * x
        derivative = coefficients[1]
        for coefficient in coefficients[2:]:
            following = 2 * x * current - previous
            dfollowing = 2 * current + 2 * x * dcurrent - dprevious
            value += coefficient * following
            derivative += coefficient * dfollowing
            previous, current = current, following
            dprevious, dcurrent = dcurrent, dfollowing
        positions.append(value)
        velocities.append(derivative * 2 / span * 86400)
    if not all(math.isfinite(v) for v in positions + velocities):
        raise EphemerisSourceError("solar_de440_invalid")
    return (positions[0], positions[1], positions[2]), (
        velocities[0],
        velocities[1],
        velocities[2],
    )


def solar_longitude(jd_tt: float, *, profile_id: str = MODEL_ID) -> float:
    """Geocentric apparent Sun in the true ecliptic/equinox of date, degrees."""
    tdb2 = (
        jd_tt
        - 2451545.0
        + geocentric_tdb_minus_tt(jd_tt, profile_id=profile_id) / 86400
    )
    emb, embv = state((0, 3), tdb2, profile_id=profile_id)
    earth, earthv = state((3, 399), tdb2, profile_id=profile_id)
    bary = tuple((a + b) / AU_KM for a, b in zip(emb, earth))
    velocity = tuple((a + b) / AU_KM / C_AU_DAY for a, b in zip(embv, earthv))
    sun = tuple(v / AU_KM for v in state((0, 10), tdb2, profile_id=profile_id)[0])
    vector = tuple(s - e for s, e in zip(sun, bary))
    distance_helio = math.sqrt(math.fsum(v * v for v in vector))
    for _ in range(3):
        delay = math.sqrt(math.fsum(v * v for v in vector)) / C_AU_DAY
        sun = tuple(
            v / AU_KM for v in state((0, 10), tdb2 - delay, profile_id=profile_id)[0]
        )
        vector = tuple(s - e for s, e in zip(sun, bary))
    distance = math.sqrt(math.fsum(v * v for v in vector))
    apparent = aberration(
        (vector[0] / distance, vector[1] / distance, vector[2] / distance),
        (velocity[0], velocity[1], velocity[2]),
        distance_helio,
    )
    ecliptic = apparent_ecliptic(apparent, jd_tt)
    return math.degrees(math.atan2(ecliptic[1], ecliptic[0])) % 360


def solar_longitude_parts(
    day: float, fraction: float, *, profile_id: str = MODEL_ID
) -> float:
    """Same model at an explicit two-part TT point; never collapse the JD.

    This is a separate numerical path. More digits do not certify the
    physical model or justify replacing an existing reference/acceptance gate.
    """
    if not all(math.isfinite(v) for v in (day, fraction)):
        raise ValueError("TT epoch parts must be finite")
    # The Fairhead argument is centuries from J2000; round only at that
    # small relative argument, rather than at the full Julian date.
    relative = math.fsum((day - 2451545.0, fraction))
    tdb = geocentric_tdb_minus_tt_relative(relative, profile_id=profile_id)
    whole = math.floor(day - 2451545.0)
    remainder = math.fsum((day - 2451545.0 - whole, fraction, tdb / 86400))
    carry, remainder = divmod(remainder, 1.0)
    whole += int(carry)

    def vector_state(
        pair: tuple[int, int], shift: float = 0.0
    ) -> tuple[Vector, Vector]:
        return state(
            pair, whole, fractional_day=remainder + shift, profile_id=profile_id
        )

    emb, embv = vector_state((0, 3))
    earth, earthv = vector_state((3, 399))
    bary = tuple((a + b) / AU_KM for a, b in zip(emb, earth))
    velocity = tuple((a + b) / AU_KM / C_AU_DAY for a, b in zip(embv, earthv))
    sun = tuple(v / AU_KM for v in vector_state((0, 10))[0])
    vector = tuple(s - e for s, e in zip(sun, bary))
    distance_helio = math.sqrt(math.fsum(v * v for v in vector))
    for _ in range(3):
        delay = math.sqrt(math.fsum(v * v for v in vector)) / C_AU_DAY
        sun = tuple(v / AU_KM for v in vector_state((0, 10), -delay)[0])
        vector = tuple(s - e for s, e in zip(sun, bary))
    distance = math.sqrt(math.fsum(v * v for v in vector))
    apparent = aberration(
        (vector[0] / distance, vector[1] / distance, vector[2] / distance),
        (velocity[0], velocity[1], velocity[2]),
        distance_helio,
    )
    ecliptic = apparent_ecliptic(apparent, day, fraction)
    return math.degrees(math.atan2(ecliptic[1], ecliptic[0])) % 360


def cache_key(profile_id: str = MODEL_ID) -> tuple[str, ...]:
    p = _selected_profile(profile_id)
    return (
        p.manifest_sha256,
        p.manifest["uncompressed_sha256"],
        p.tdb_sha256,
        str(frame_profile()["loaded_sha256"]),
    )


def source_receipt(profile_id: str = MODEL_ID) -> dict[str, Any]:
    p = _selected_profile(profile_id)
    return deepcopy(
        {
            "model_id": profile_id,
            "version": p.manifest["version"],
            "source_kernel_sha256": p.manifest["source"]["kernel_sha256"],
            "coefficient_manifest_sha256": p.manifest_sha256,
            "coefficient_sha256": p.manifest["uncompressed_sha256"],
            "compressed_coefficient_sha256": p.manifest["compressed_sha256"],
            "frame_coefficient_sha256": frame_profile()["loaded_sha256"],
            "tdb_coefficient_sha256": p.tdb_sha256,
            "coefficient_storage": p.manifest["storage"],
            "coefficient_product_producer": p.manifest["derived_product_producer"],
            "source_url": p.manifest["source"]["url"],
            "source_format_url": p.manifest["source"]["format_url"],
            "spk_frame_id": 1,
            "segment_coverage_tdb_jd": {
                f"{s['center']}->{s['target']}": [
                    2451545.0 + s["initial_seconds_from_j2000_tdb"] / 86400,
                    2451545.0
                    + (
                        s["initial_seconds_from_j2000_tdb"]
                        + s["record_count"] * s["interval_seconds"]
                    )
                    / 86400,
                ]
                for s in p.manifest["segments"]
            },
            "time_argument": "TDB from TT via full geocentric ERFA Fairhead dtdb",
            "tdb_model_author_comparison_years": [1950, 2050],
            "position_frame": "BCRS then IAU2006/P03 and IAU2000B true ecliptic of date",
            "light_time_iterations": 3,
            "apparent_direction_model": {
                "tdb": "fatebridge_geocentric_erfa_dtdb_v1",
                "tdb_observer_u_v_km": [0, 0],
                "aberration": "ERFA_ab",
                "solar_gravitational_potential_in_aberration": True,
                "finite_distance_light_deflection": "not_applied",
                "precession": "IAU2006_P03",
                "nutation": "IAU2000B",
                "physical_accuracy_certified": False,
            },
            "native_moshier_relabelled": False,
            "reference_event_table_used": False,
            "accuracy_certified": False,
            "source_identity_scope": "Loaded original orbit coefficients and declared frame/time models; not provider endorsement, independent observations or full civil UTC certification",
            **(
                {
                    "software_solar_term_years": list(
                        p.manifest["software_solar_term_years"]
                    ),
                    "projection_origin_civil_years": list(
                        p.manifest["projection_origin_civil_years"]
                    ),
                    "maximum_projection_horizon_years": 120,
                    "admitted_projection_events": ["立春"],
                }
                if profile_id == CANPING_EXTENDED_MODEL_ID
                else {}
            ),
            **(
                {
                    "software_solar_term_years": list(
                        p.manifest["software_solar_term_years"]
                    ),
                    "public_auto_and_de440_input_years": list(
                        p.manifest["public_auto_and_de440_input_years"]
                    ),
                }
                if profile_id == EXTENDED_MODEL_ID
                else {}
            ),
        }
    )


def longitude_crossing_tt(
    target: float, low: float, high: float, *, profile_id: str = MODEL_ID
) -> dict[str, Any]:
    if not all(math.isfinite(x) for x in (target, low, high)) or low >= high:
        raise ValueError("DE440 crossing requires a finite increasing TT bracket")

    def residual(epoch: float) -> float:
        return math.remainder(
            solar_longitude(epoch, profile_id=profile_id) - target, 360
        )

    flo, fhi = residual(low), residual(high)
    if not flo < 0 <= fhi or fhi - flo >= 90:
        raise ValueError("DE440 TT bracket does not contain a forward crossing")
    iterations = 0
    for _ in range(40):
        middle = (low + high) / 2
        if middle == low or middle == high:
            break
        if residual(middle) < 0:
            low = middle
        else:
            high = middle
        iterations += 1
    return {
        "jd_tt": (low + high) / 2,
        "bracket_tt": [low, high],
        "bracket_seconds": (high - low) * 86400,
        "iterations": iterations,
        "numerical_resolution_is_physical_accuracy": False,
        "model": source_receipt(profile_id),
    }


def longitude_crossing_tt_parts(
    target: float, low: float, high: float, *, profile_id: str = MODEL_ID
) -> dict[str, Any]:
    """Explicit two-part alternative; scalar/default callers stay unchanged."""
    if not all(math.isfinite(v) for v in (target, low, high)) or low >= high:
        raise ValueError("DE440 crossing requires a finite increasing TT bracket")
    base = float(math.floor(low))
    a, b = low - base, high - base

    def residual(offset: float) -> float:
        return math.remainder(
            solar_longitude_parts(base, offset, profile_id=profile_id) - target, 360
        )

    flo, fhi = residual(a), residual(b)
    if not flo < 0 <= fhi or fhi - flo >= 90:
        raise ValueError("DE440 TT bracket does not contain a forward crossing")
    iterations = 0
    for _ in range(48):
        middle = (a + b) / 2
        if middle in (a, b):
            break
        if residual(middle) < 0:
            a = middle
        else:
            b = middle
        iterations += 1
    fraction = (a + b) / 2
    return {
        "jd_tt": base + fraction,
        "tt_parts": [base, fraction],
        "tt_bracket_parts": [[base, a], [base, b]],
        "bracket_seconds": (b - a) * 86400,
        "iterations": iterations,
        "numerical_epoch_representation": "explicit_two_part_tt",
        "numerical_resolution_is_physical_accuracy": False,
        "model": source_receipt(profile_id),
    }
