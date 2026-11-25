"""Solar horizon observations and event definitions on one physical epoch pair.

The Hindu convention retains the source's apparent ecliptic longitude with
zero ecliptic latitude. The topocentric centre uses the physical WGS84 receiver
in the source light path and its full velocity in the SOFA aberration map.
Neither mode substitutes a source-native observer for the physical receiver.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import erfa

from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import LIGHT_SPEED_AU_PER_DAY
from fatebridge.core.astro.cartesian import CartesianState, Vector3
from fatebridge.core.astro.earth_attitude import earth_attitude, physical_equator
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.reference_frames import dot, mv
from fatebridge.core.astro.solar_altitude_search import solar_altitude_nodes
from fatebridge.core.astro.solar_observer import (
    FileSolarSource,
    NativeSolarSource,
    SolarSource,
    precise_solar_direction,
    select_solar_source,
)
from fatebridge.core.astro.source_session import coherent_ephemeris_sources
from fatebridge.core.astro.terrestrial_observer import (
    native_observer_site,
    terrestrial_frame,
    terrestrial_observer,
)
from fatebridge.core.astro.time_scales import resolve_tt_from_ut1, tt_from_ut1
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.utils.errors import EphemerisSourceError

SolarDefinition = Literal["hindu_geometric_center", "apparent_topocentric_center"]
SOURCE_MASK = 7  # Original SEFLG_EPHMASK; all other requested flags must agree.
SOLAR_EVENT_MODEL = "fatebridge.physical_solar_horizon_crossing.v4"


@dataclass(frozen=True)
class SolarObservation:
    julian_day_ut1: float
    julian_day_tt: float
    altitude_degrees: float
    physical_equatorial_direction: Vector3
    ephemeris_model: str
    ephemeris_flags: int | None
    definition: SolarDefinition


@dataclass(frozen=True)
class SolarEvent:
    julian_day_ut1: float
    julian_day_tt: float
    ephemeris_model: str
    ephemeris_flags: int | None
    definition: SolarDefinition
    bracket_ut1: tuple[float, float]
    geometric_altitude_degrees: float
    geometric_horizon_degrees: float
    observation_evaluations: int
    rising: bool


def _cartesian_state(jd_tt: float, body: int, flags: int) -> tuple[CartesianState, int]:
    """Validate the native Cartesian/speed boundary once before using a state."""
    coordinates: Sequence[float]
    coordinates, returned = runtime.ephemeris_call("calc", jd_tt, body, flags)
    if (
        returned < 0
        or returned & SOURCE_MASK not in (1, 2, 4)
        or returned & ~SOURCE_MASK != flags & ~SOURCE_MASK
    ):
        raise EphemerisSourceError("coordinate_contract_changed")
    else:
        pass
    if len(coordinates) < 6:
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    x, y, z, vx, vy, vz = (float(v) for v in coordinates[:6])
    if not all(math.isfinite(v) for v in (x, y, z, vx, vy, vz)):
        raise EphemerisSourceError("coordinate_values_unavailable")
    else:
        pass
    return CartesianState((x, y, z), (vx, vy, vz)), returned & SOURCE_MASK


@coherent_ephemeris_sources
def solar_observation(
    julian_day_ut1: float,
    *,
    longitude: float,
    latitude: float,
    height: float,
    definition: SolarDefinition,
    julian_day_tt: float | None = None,
    ephemeris_flags: int | None = None,
    source: SolarSource | None = None,
) -> SolarObservation:
    """Geometric solar altitude before refraction, with declared source optics.

    Coefficient sources use one native-TDB light cone and analytic Earth velocity.
    Explicit native sources retain their declared light path; topocentric
    native aberration is replaced by one SOFA boost with the physical station.
    Selected EOP enters the shared receiver and ENU frame. Geoid, dynamical
    accuracy and atmosphere remain outside this geometric altitude model.
    """
    module = runtime.swe
    if module is None:
        raise ModuleNotFoundError("Swiss Ephemeris is required for solar events")
    else:
        pass
    if source is not None and ephemeris_flags is not None:
        raise ValueError("Choose a solar source or native flags, not both")
    else:
        pass
    with runtime.preserve_ephemeris_path():
        epoch = (
            resolve_tt_from_ut1(julian_day_ut1)
            if julian_day_tt is None
            else TTInstant.from_float(julian_day_tt)
        )
        tt = epoch.as_float()
        selected = (
            select_solar_source(tt, tt, native_flags=ephemeris_flags)
            if source is None
            else source
        )
        actual_source: int | None
        try:
            if isinstance(selected, NativeSolarSource):
                requested = selected.requested_flags
                if definition == "hindu_geometric_center":
                    coordinates, returned = runtime.ephemeris_call(
                        "calc", tt, module.SUN, requested | module.FLG_SPEED
                    )
                    solar_longitude, _, _ = require_spherical_coordinates(
                        coordinates, returned, native=module
                    )
                    actual_source = returned & SOURCE_MASK
                    if actual_source not in (1, 2, 4):
                        raise EphemerisSourceError("coordinate_contract_changed")
                    else:
                        pass
                    attitude = earth_attitude(
                        module, julian_day_ut1, julian_day_tt=epoch
                    )
                    equator = attitude.equator
                    angle = math.radians(solar_longitude)
                    x, y, z = mv(
                        attitude.reduction.ecliptic_to_target,
                        (math.cos(angle), math.sin(angle), 0.0),
                    )
                else:
                    common = (
                        module.FLG_EQUATORIAL
                        | module.FLG_XYZ
                        | module.FLG_J2000
                        | module.FLG_ICRS
                        | module.FLG_NONUT
                        | module.FLG_SPEED
                        | module.FLG_NOABERR
                        | module.FLG_NOGDEFL
                    )
                    geometric_sun, actual_source = _cartesian_state(
                        tt, module.SUN, requested | common | module.FLG_TRUEPOS
                    )
                    equator = physical_equator(
                        module, julian_day_ut1, julian_day_tt=epoch
                    )
                    receiver = terrestrial_observer(
                        equator, longitude=longitude, latitude=latitude, height=height
                    )
                    source_site = native_observer_site(
                        module, equator, receiver, ephemeris_flags=actual_source
                    )
                    module.set_topo(*source_site)
                    try:
                        natural_sun, natural_source = _cartesian_state(
                            tt, module.SUN, actual_source | common | module.FLG_TOPOCTR
                        )
                    finally:
                        module.set_topo(longitude, latitude, height)
                    earth, earth_source = _cartesian_state(
                        tt,
                        module.EARTH,
                        actual_source
                        | common
                        | module.FLG_TRUEPOS
                        | (
                            module.FLG_HELCTR
                            if actual_source == module.FLG_MOSEPH
                            else module.FLG_BARYCTR
                        ),
                    )
                    if natural_source != actual_source or earth_source != actual_source:
                        raise EphemerisSourceError("coordinate_model_changed")
                    else:
                        pass
                    distance = math.hypot(*natural_sun.position)
                    solar_distance = math.hypot(
                        *(
                            a - b
                            for a, b in zip(geometric_sun.position, receiver.position)
                        )
                    )
                    beta = tuple(
                        (a + b) / LIGHT_SPEED_AU_PER_DAY
                        for a, b in zip(earth.velocity, receiver.velocity)
                    )
                    bm2 = 1 - dot(beta, beta)
                    if distance == 0 or solar_distance == 0 or bm2 <= 0:
                        raise EphemerisSourceError("coordinate_values_unavailable")
                    else:
                        pass
                    apparent = erfa.ab(
                        tuple(v / distance for v in natural_sun.position),
                        beta,
                        solar_distance,
                        math.sqrt(bm2),
                    )
                    x, y, z = mv(equator.matrix, tuple(float(v) for v in apparent))
                actual_model = runtime.ephemeris_model_from_retflag(actual_source)
            else:
                equator = physical_equator(module, julian_day_ut1, julian_day_tt=epoch)
                receiver = (
                    terrestrial_observer(
                        equator, longitude=longitude, latitude=latitude, height=height
                    )
                    if definition == "apparent_topocentric_center"
                    else CartesianState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
                )
                direction = precise_solar_direction(epoch, receiver, selected)
                x, y, z = mv(equator.matrix, direction)
                if definition == "hindu_geometric_center":
                    attitude = earth_attitude(
                        module, julian_day_ut1, julian_day_tt=epoch
                    )
                    ecliptic = mv(attitude.reduction.target_to_ecliptic, (x, y, z))
                    angle = math.atan2(ecliptic[1], ecliptic[0])
                    x, y, z = mv(
                        attitude.reduction.ecliptic_to_target,
                        (math.cos(angle), math.sin(angle), 0.0),
                    )
                else:
                    pass
                actual_source = None
                actual_model = selected.value
        except module.Error as error:
            raise EphemerisSourceError("unavailable_during") from error
        frame = terrestrial_frame(equator, longitude=longitude, latitude=latitude)
        east = dot(frame.east, (x, y, z))
        north = dot(frame.north, (x, y, z))
        up = dot(frame.up, (x, y, z))
        return SolarObservation(
            julian_day_ut1,
            tt,
            math.degrees(math.atan2(up, math.hypot(east, north))),
            (x, y, z),
            actual_model,
            actual_source,
            definition,
        )


@coherent_ephemeris_sources
def solar_crossings_in_window(
    start_ut1: float,
    end_ut1: float,
    *,
    longitude: float,
    latitude: float,
    definition: SolarDefinition,
    ephemeris_flags: int | None = None,
    source: SolarSource | None = None,
    ephemeris_policy: Literal["auto", "require_data_files"] = "auto",
) -> list[SolarEvent]:
    """All directed centre crossings in the closed, declared UT1 interval.

    A spectral height interpolant locates every resolved extremum, including
    pairs within one two-hour segment. Physical signs, rather than polynomial
    zeros, bracket the events, then bisection reaches adjacent UT1 dates.
    An exact zero needs opposite signs at both adjacent UT1 points. A zero
    on an unresolved run of equal values does not give an isolated event.
    The root coordinate is the lower endpoint of its adjacent-float bracket;
    this gives half-open daily partitions one consistent event owner.
    Source, clock and convergence failures propagate; an empty list means
    only that this valid window contains no resolved directed crossing.
    Atmosphere for the apparent-centre preset is fixed at sea level,
    1013.25 hPa, 0 Celsius and lapse rate 0.0065 K/m, as declared by its caller.
    """
    module = runtime.swe
    if module is None:
        raise ModuleNotFoundError("Swiss Ephemeris is required for solar events")
    else:
        pass
    if (
        not math.isfinite(start_ut1)
        or not math.isfinite(end_ut1)
        or end_ut1 <= start_ut1
    ):
        raise ValueError(
            "Solar event window must have finite, increasing UT1 endpoints"
        )
    else:
        pass
    if source is not None and ephemeris_flags is not None:
        raise ValueError("Choose a solar source or native flags, not both")
    else:
        pass
    with runtime.preserve_ephemeris_path():
        fixed_source = (
            select_solar_source(
                tt_from_ut1(start_ut1),
                tt_from_ut1(end_ut1),
                native_flags=ephemeris_flags,
                require_data_files=ephemeris_policy == "require_data_files",
            )
            if source is None
            else source
        )
        horizon = (
            float(
                module.refrac_extended(
                    0.0, 0.0, 1013.25, 0.0, 0.0065, module.APP_TO_TRUE
                )[0]
            )
            if definition == "apparent_topocentric_center"
            else 0.0
        )
        observations: dict[float, SolarObservation] = {}
        observed_source: tuple[str, int | None] | None = None
        rotation_source = active_ut1.get()
        rotation_bounds = (
            rotation_source.ut1_bounds if rotation_source is not None else None
        )

        def value(ut1: float) -> float:
            nonlocal observed_source
            if ut1 not in observations:
                sample = solar_observation(
                    ut1,
                    longitude=longitude,
                    latitude=latitude,
                    height=0.0,
                    definition=definition,
                    source=fixed_source,
                )
                identity = sample.ephemeris_model, sample.ephemeris_flags
                if observed_source is None:
                    observed_source = identity
                elif identity != observed_source:
                    raise EphemerisSourceError("coordinate_model_changed")
                else:
                    pass
                if (
                    ephemeris_policy == "require_data_files"
                    and sample.ephemeris_model
                    not in {"swieph", "jpl", FileSolarSource.value}
                ):
                    raise ValueError(
                        "require_data_files requires file-backed solar ephemerides"
                    )
                else:
                    pass
                observations[ut1] = sample
            else:
                pass
            return math.sin(
                math.radians(observations[ut1].altitude_degrees)
            ) - math.sin(math.radians(horizon))

        def zero_neighbors(
            point: float,
        ) -> tuple[tuple[float, float], tuple[float, float]]:
            left = math.nextafter(point, -math.inf)
            right = math.nextafter(point, math.inf)
            # An unavailable neighbor supplies no strict sign.
            before = (
                value(left)
                if rotation_bounds is None or rotation_bounds[0] <= left
                else 0.0
            )
            after = (
                value(right)
                if rotation_bounds is None or right <= rotation_bounds[1]
                else 0.0
            )
            return (left, before), (right, after)

        def sign_change(before: float, after: float) -> bool:
            return before < 0 < after or after < 0 < before

        crossings: list[SolarEvent] = []

        def record_crossing(lower: float, upper: float, rising: bool) -> None:
            sample = observations[lower]
            crossings.append(
                SolarEvent(
                    lower,
                    sample.julian_day_tt,
                    sample.ephemeris_model,
                    sample.ephemeris_flags,
                    definition,
                    (lower, upper),
                    sample.altitude_degrees,
                    horizon,
                    len(observations),
                    rising,
                )
            )

        def refine_crossing(
            left: tuple[float, float], right: tuple[float, float], steps: int = 64
        ) -> None:
            lower, low_value = left
            upper, high_value = right
            if lower >= upper or not sign_change(low_value, high_value):
                return
            else:
                pass
            for remaining in range(steps - 1, -1, -1):
                middle = lower + (upper - lower) / 2
                if middle in (lower, upper):
                    record_crossing(lower, upper, low_value < 0)
                    return
                else:
                    pass
                current = value(middle)
                if current == 0:
                    # Partition the known bracket at the zero. Its own direction
                    # does not decide whether either side contains a crossing.
                    before, after = zero_neighbors(middle)
                    refine_crossing((lower, low_value), before, remaining)
                    if sign_change(before[1], after[1]):
                        record_crossing(middle, middle, after[1] > 0)
                    else:
                        pass
                    refine_crossing(after, (upper, high_value), remaining)
                    return
                else:
                    pass
                if (current < 0) == (low_value < 0):
                    lower, low_value = middle, current
                else:
                    upper, high_value = middle, current
            raise RuntimeError("Solar event crossing did not converge")

        grid = [
            point
            for index in range(math.ceil((end_ut1 - start_ut1) * 12))
            if (point := start_ut1 + index / 12) < end_ut1
        ]
        grid.append(end_ut1)
        nodes = sorted(
            {
                point
                for lower, upper in zip(grid, grid[1:])
                for point in solar_altitude_nodes(value, lower, upper)
            }
        )
        previous: tuple[float, float] | None = None
        for point in nodes:
            sample = (point, value(point))
            if sample[1] != 0:
                if previous is not None:
                    refine_crossing(previous, sample)
                else:
                    pass
                previous = sample
                continue
            else:
                pass
            before, after = zero_neighbors(point)
            if previous is not None:
                refine_crossing(previous, before)
            else:
                pass
            if sign_change(before[1], after[1]):
                record_crossing(point, point, after[1] > 0)
            else:
                pass
            # A neighbor beyond the search window may classify the zero but
            # cannot start another event bracket in this window.
            previous = after if after[0] <= end_ut1 else None
        return crossings


@coherent_ephemeris_sources
def next_solar_event(
    julian_day_ut1: float,
    *,
    longitude: float,
    latitude: float,
    rising: bool,
    definition: SolarDefinition,
    ephemeris_flags: int | None = None,
    source: SolarSource | None = None,
    ephemeris_policy: Literal["auto", "require_data_files"] = "auto",
) -> SolarEvent | None:
    """First requested crossing in the closed 26-hour window, or valid absence."""
    return next(
        (
            event
            for event in solar_crossings_in_window(
                julian_day_ut1,
                julian_day_ut1 + 26 / 24,
                longitude=longitude,
                latitude=latitude,
                definition=definition,
                ephemeris_flags=ephemeris_flags,
                source=source,
                ephemeris_policy=ephemeris_policy,
            )
            if event.rising == rising
        ),
        None,
    )
