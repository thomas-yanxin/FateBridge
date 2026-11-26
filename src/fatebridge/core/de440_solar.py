"""Dependency-free evaluation of losslessly extracted DE440 type2 records.

Geocentric ERFA dtdb is adapted from ERFA/SOFA; the full BSD conditions are
in data/astronomy/erfa-license.txt. No provider endorses FateBridge.
Runtime data are original position coefficients, never event-time references.
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
from typing import Any, TypedDict

from fatebridge.core.analytic_solar import (
    C_AU_DAY,
    aberration,
    apparent_ecliptic,
)
from fatebridge.core.astro.chebyshev import chebyshev_kinematics
from fatebridge.core.astro.coefficient_storage import RecordBlock, unpack_records
from fatebridge.core.astro.tdb import Parameters as TDBParameters
from fatebridge.core.astro.tdb import fairhead_seconds
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "fatebridge_de440_solar_v1"
HISTORICAL_MODEL_ID = "fatebridge_de440_solar_historical_v1"
EXTENDED_MODEL_ID = "fatebridge_de440_solar_extended_v1"
CANPING_MODEL_ID = "fatebridge_de440_solar_canping_v1"
CANPING_EXTENDED_MODEL_ID = "fatebridge_de440_solar_canping_extended_v1"
ATLAS_BASENAME = "de440-solar-record-atlas-v1"
PROFILE_FILES = {
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


class SolarManifest(TypedDict):
    model_id: str
    version: str
    source: dict[str, str]
    storage: str
    file: str
    uncompressed_bytes: int
    segments: list[RecordSegment]
    derived_product_producer: dict[str, str | bool]
    software_solar_term_years: list[int]
    public_auto_and_de440_input_years: list[int]
    projection_origin_civil_years: list[int]


class _AtlasManifest(TypedDict):
    file: str
    segments: list[RecordSegment]


@lru_cache(maxsize=1)
def _coefficient_data() -> bytes:
    folder = files("fatebridge").joinpath("data/astronomy")
    try:
        metadata = folder.joinpath(ATLAS_BASENAME + ".json").read_bytes()
        manifest: _AtlasManifest = json.loads(metadata)
        packed = folder.joinpath(manifest["file"]).read_bytes()
        data = unpack_records(
            packed,
            [
                RecordBlock(s["record_count"], s["record_size_doubles"] * 8)
                for s in manifest["segments"]
            ],
        )
    except (OSError, ValueError, EOFError, zlib.error) as error:
        raise EphemerisSourceError("solar_de440_invalid") from error
    return data


@dataclass(frozen=True)
class _Profile:
    manifest: SolarManifest
    data: bytes
    tdb: TDBParameters


@lru_cache(maxsize=5)
def _profile(profile_id: str = MODEL_ID) -> _Profile:
    folder = files("fatebridge").joinpath("data/astronomy")
    try:
        basename = PROFILE_FILES[profile_id]
        metadata = folder.joinpath(basename + ".json").read_bytes()
        manifest: SolarManifest = json.loads(metadata)
        tdb_raw = folder.joinpath("geocentric-tdb-v1.json").read_bytes()
        tdb: TDBParameters = json.loads(tdb_raw)
    except (OSError, ValueError, KeyError) as error:
        raise EphemerisSourceError("solar_de440_invalid") from error
    return _Profile(manifest, _coefficient_data(), tdb)


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
    days_from_j2000: float | Fraction, *, profile_id: str = MODEL_ID
) -> float:
    """Same Fairhead series with its relative epoch supplied directly."""
    if not math.isfinite(days_from_j2000):
        raise ValueError("TT relative epoch must be finite")
    rows = _selected_profile(profile_id).tdb["fairhead_terms"]
    return fairhead_seconds(days_from_j2000, rows)


def state(
    pair: tuple[int, int],
    tdb_days_from_j2000: float | Fraction,
    *,
    profile_id: str = MODEL_ID,
    fractional_day: float = 0.0,
    need_velocity: bool = True,
) -> tuple[Vector, Vector]:
    """Original type2 position in km and derivative in km/TDB-day.

    The epoch may be exact or supplied in binary64 parts."""
    if not math.isfinite(fractional_day) or (
        not isinstance(tdb_days_from_j2000, Fraction)
        and not math.isfinite(tdb_days_from_j2000)
    ):
        raise ValueError("TDB epoch must be finite")
    p = _selected_profile(profile_id)
    s = next(
        (s for s in p.manifest["segments"] if (s["center"], s["target"]) == pair),
        None,
    )
    if s is None:
        raise ValueError("Unsupported DE440 solar body pair")
    initial, span = s["initial_seconds_from_j2000_tdb"], s["interval_seconds"]
    # Select the original record from the supplied epoch before rounding.
    # A rounded seconds sum can cross a source edge before local evaluation.
    span_exact = Fraction(span)
    elapsed = (
        Fraction(tdb_days_from_j2000) + Fraction(fractional_day)
    ) * 86400 - Fraction(initial)
    index, offset = divmod(elapsed, span_exact)
    if index == s["record_count"] and offset == 0:
        index -= 1
        offset += span_exact
    if not 0 <= index < s["record_count"]:
        raise EphemerisSourceError("solar_de440_range")
    size = s["record_size_doubles"]
    record = struct.unpack_from(
        "<" + "d" * size, p.data, s["offset_bytes"] + index * size * 8
    )
    midpoint = initial + (index + 0.5) * span
    if record[0] != midpoint or record[1] != span / 2:
        raise EphemerisSourceError("solar_de440_invalid")
    x = 2 * offset / span_exact - 1
    count = (size - 2) // 3
    positions, velocities = [], []
    derivs = 1 if need_velocity else 0
    for axis in range(3):
        coefficients = record[2 + axis * count : 2 + (axis + 1) * count]
        kinematics = chebyshev_kinematics(coefficients, x, derivatives=derivs)
        value, velocity, _ = kinematics.scaled(172800 / span)
        positions.append(value)
        velocities.append(velocity)
    if not all(math.isfinite(v) for v in positions + velocities):
        raise EphemerisSourceError("solar_de440_invalid")
    return (positions[0], positions[1], positions[2]), (
        velocities[0],
        velocities[1],
        velocities[2],
    )


def solar_longitude(jd_tt: float, *, profile_id: str = MODEL_ID) -> float:
    """Geocentric apparent Sun in the true ecliptic/equinox of date, degrees."""
    return solar_longitude_parts(jd_tt, 0.0, profile_id=profile_id)


def solar_longitude_parts(
    day: float, fraction: float, *, profile_id: str = MODEL_ID
) -> float:
    """Geocentric apparent Sun at an explicit two-part TT point."""
    if not all(math.isfinite(value) for value in (day, fraction)):
        raise ValueError("TT epoch parts must be finite")
    relative = Fraction(day) - 2451545 + Fraction(fraction)
    correction = geocentric_tdb_minus_tt_relative(relative, profile_id=profile_id)
    # Keep the received and emitted epochs exact until the source record owns them.
    tdb = relative + Fraction(correction) / 86400
    emb, embv = state((0, 3), tdb, profile_id=profile_id)
    earth, earthv = state((3, 399), tdb, profile_id=profile_id)
    bary = tuple((a + b) / AU_KM for a, b in zip(emb, earth))
    velocity = tuple((a + b) / AU_KM / C_AU_DAY for a, b in zip(embv, earthv))
    sun_km = state((0, 10), tdb, profile_id=profile_id, need_velocity=False)[0]
    sun = tuple(v / AU_KM for v in sun_km)
    vector = tuple(s - e for s, e in zip(sun, bary))
    distance_helio = math.sqrt(math.fsum(v * v for v in vector))
    for _ in range(3):
        delay = math.sqrt(math.fsum(v * v for v in vector)) / C_AU_DAY
        emitted = tdb - Fraction(delay)
        sun_km = state((0, 10), emitted, profile_id=profile_id, need_velocity=False)[0]
        sun = tuple(v / AU_KM for v in sun_km)
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
    return (profile_id, p.manifest["version"])


def source_receipt(profile_id: str = MODEL_ID) -> dict[str, Any]:
    p = _selected_profile(profile_id)
    return deepcopy(
        {
            "model_id": profile_id,
            "version": p.manifest["version"],
            "coefficient_storage": p.manifest["storage"],
            "coefficient_product_producer": p.manifest["derived_product_producer"],
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
            },
            "native_moshier_relabelled": False,
            "reference_event_table_used": False,
            "accuracy_certified": False,
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
