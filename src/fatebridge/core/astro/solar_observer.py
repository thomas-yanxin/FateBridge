"""Coherent Sun/Earth coefficient states and fixed-reception solar optics.

The original DE440 coefficient owner and bounded DE441 source are reused;
neither event roots nor a second trajectory theory are stored here. Native
queries remain explicit so a packaged source never borrows native flags.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import ClassVar, TypedDict

import erfa

from fatebridge.core import de440_solar
from fatebridge.core.astro import runtime
from fatebridge.core.astro.cartesian import CartesianState, Vector3
from fatebridge.core.astro.de441_source import MODEL_ID as DE441_MODEL_ID
from fatebridge.core.astro.de441_source import SOURCE_VERSION as DE441_SOURCE_VERSION
from fatebridge.core.astro.de441_source import barycentric_state
from fatebridge.core.astro.jpl_kinematics import source_kinematics
from fatebridge.core.astro.light_cone import LIGHT_SPEED_AU_DAY, solve_light_cone
from fatebridge.core.astro.tdb import geocentric_tdb_state
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.jpl_ephemeris import configured_jpl_file

SOLAR_SOURCE_POLICY = "fatebridge.solar_horizon_source_selection.v2"
DE440_START_TT = date(1700, 1, 1).toordinal() + 1721424.5
DE440_END_TT = date(2301, 1, 1).toordinal() + 1721424.5


class SolarSourceReference(TypedDict):
    author: str
    source_version: str | None
    calculation_library: str
    time_argument: str
    coefficient_representation: str
    coefficient_profile: str | None


@dataclass(frozen=True)
class NativeSolarSource:
    requested_flags: int


class PackagedSolarSource(Enum):
    DE440 = "fatebridge_solar_horizon_de440_v1"
    DE441 = "fatebridge_solar_horizon_de441_v1"


@dataclass(frozen=True)
class FileSolarSource:
    path: Path
    value: ClassVar[str] = "fatebridge_solar_horizon_de441_file_v1"


SolarCoefficientSource = PackagedSolarSource | FileSolarSource
SolarSource = NativeSolarSource | SolarCoefficientSource


def select_solar_source(
    start_tt: float,
    end_tt: float,
    *,
    native_flags: int | None = None,
    require_data_files: bool = False,
) -> SolarSource:
    """Choose once for the complete calculation interval, including empty days.

    The modern window is the existing DE440 source profile's declared input
    range, not an assertion that all horizon inputs have been certified.
    A configured JPL file is admitted by the managed native boundary, then
    read on its actual TDB grid through the existing coefficient reader.
    Strict mode continues to require actual file-backed calculations.
    The solar-term environment selector belongs to a different consumer.
    """
    if native_flags is not None:
        return NativeSolarSource(native_flags)
    if configured_jpl_file() is not None:
        module = runtime.swe
        if module is None:
            raise ModuleNotFoundError(
                "Swiss Ephemeris is required for selected-file admission"
            )
        # Reuse native file selection/header/fallback admission. The returned
        # approximate TT-as-TDB coordinates are not used for solar optics.
        runtime.ephemeris_call("calc", start_tt, module.SUN, module.FLG_JPLEPH)
        return FileSolarSource(Path(module.get_current_file_data(0)[0]))
    if require_data_files:
        return NativeSolarSource(2)  # SEFLG_SWIEPH; callers reject a native fallback.
    if DE440_START_TT <= start_tt <= end_tt < DE440_END_TT:
        return PackagedSolarSource.DE440
    return PackagedSolarSource.DE441


def precise_solar_direction(
    julian_day_tt: TTInstant,
    receiver: CartesianState,
    source: SolarCoefficientSource,
) -> Vector3:
    """ICRF solar direction from one source clock, light cone and velocity.

    Receiver coordinates are the declared physical station relative to Earth;
    its velocity is the existing nominal instantaneous rotation convention.
    Earth and the emitting Sun use one TDB clock derived from the retained TT.
    The source's analytic TDB velocity and station velocity supply aberration.
    """
    relative = julian_day_tt.days - 2451545
    tdb = relative + Fraction(geocentric_tdb_state(relative).seconds) / 86400
    if source is PackagedSolarSource.DE440:
        emb, embv = de440_solar.state(
            (0, 3),
            tdb,
            profile_id=de440_solar.EXTENDED_MODEL_ID,
        )
        geo, geov = de440_solar.state(
            (3, 399),
            tdb,
            profile_id=de440_solar.EXTENDED_MODEL_ID,
        )
        x, y, z = ((a + b) / de440_solar.AU_KM for a, b in zip(emb, geo))
        vx, vy, vz = ((a + b) / de440_solar.AU_KM for a, b in zip(embv, geov))
        earth = CartesianState((x, y, z), (vx, vy, vz))
    else:
        if isinstance(source, FileSolarSource):
            values, _ = source_kinematics(source.path, 2451545 + tdb, "Earth")
            x, y, z, vx, vy, vz = values[:6]
            earth = CartesianState((x, y, z), (vx, vy, vz))
        else:
            state = barycentric_state("Earth", tdb)
            earth = CartesianState(state.position, state.velocity)
    observer = tuple(a + b for a, b in zip(earth.position, receiver.position))
    beta = tuple(
        (a + b) / LIGHT_SPEED_AU_DAY for a, b in zip(earth.velocity, receiver.velocity)
    )

    def sun(delay: float) -> tuple[Vector3, None]:
        if source is PackagedSolarSource.DE440:
            position, _ = de440_solar.state(
                (0, 10),
                tdb + Fraction(delay),
                profile_id=de440_solar.EXTENDED_MODEL_ID,
            )
            x, y, z = (v / de440_solar.AU_KM for v in position)
            return (x, y, z), None
        if isinstance(source, FileSolarSource):
            values, _ = source_kinematics(
                source.path, 2451545 + tdb + Fraction(delay), "Sun"
            )
            x, y, z = values[:3]
            return (x, y, z), None
        state = barycentric_state("Sun", tdb + Fraction(delay))
        return state.position, None

    solution = solve_light_cone(0.0, observer, sun)
    natural = tuple(a - b for a, b in zip(solution.upper.coordinates, observer))
    distance = math.hypot(*natural)
    current_sun, _ = sun(0.0)
    apparent = erfa.ab(
        tuple(v / distance for v in natural),
        beta,
        math.dist(current_sun, observer),
        math.sqrt(1 - math.fsum(v * v for v in beta)),
    )
    x, y, z = (float(v) for v in apparent)
    return x, y, z


def solar_source_reference(model_id: str, native_version: str) -> SolarSourceReference:
    """Published source identity."""
    if model_id == PackagedSolarSource.DE440.value:
        return {
            "author": "NASA/JPL; Park, Folkner, Williams and Boggs",
            "source_version": "DE440 (2020; published 2021)",
            "calculation_library": "FateBridge original-record reader; SOFA/ERFA optics",
            "time_argument": "TDB from declared TT via geocentric Fairhead model",
            "coefficient_representation": "original type2 coefficient records, lossless storage",
            "coefficient_profile": de440_solar.EXTENDED_MODEL_ID,
        }
    if model_id == PackagedSolarSource.DE441.value:
        return {
            "author": "NASA/JPL; Park, Folkner, Williams and Boggs",
            "source_version": DE441_SOURCE_VERSION,
            "calculation_library": "FateBridge original-word bounded-span reader; SOFA/ERFA optics",
            "time_argument": "TDB from declared TT via geocentric Fairhead model",
            "coefficient_representation": "selected original binary64 source words with lossless storage",
            "coefficient_profile": DE441_MODEL_ID,
        }
    if model_id == FileSolarSource.value:
        return {
            "author": "NASA/JPL; Park, Folkner, Williams and Boggs",
            "source_version": DE441_SOURCE_VERSION,
            "calculation_library": "FateBridge selected-file reader; SOFA/ERFA optics",
            "time_argument": "TDB from declared TT via geocentric Fairhead model",
            "coefficient_representation": "original selected-file records; exact split source epoch",
            "coefficient_profile": None,
        }
    if model_id not in {"jpl", "swieph", "moshier"}:
        raise ValueError("Unknown solar source model")
    return {
        "author": "Astrodienst native reader; JPL or Moshier source as recorded",
        "source_version": (
            "DE404 analytical fit"
            if model_id == "moshier"
            else (
                "DE441"
                if model_id == "jpl" and configured_jpl_file() is not None
                else None
            )
        ),
        "calculation_library": "Swiss Ephemeris " + native_version,
        "time_argument": "Declared TT at the native calc entry",
        "coefficient_representation": (
            "Moshier analytical series"
            if model_id == "moshier"
            else "native source files; actual file edition is in shared ephemeris provenance"
        ),
        "coefficient_profile": None,
    }
