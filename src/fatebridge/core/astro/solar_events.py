"""Solar horizon observations and event definitions on one physical epoch pair.

The Hindu convention retains the source's apparent ecliptic longitude with
zero ecliptic latitude. The topocentric centre uses the physical WGS84 receiver
in the source light path and its full velocity in the SOFA aberration map.
Neither mode substitutes a source-native observer for the physical receiver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Literal, Sequence

import erfa

from fatebridge.core.astro import runtime
from fatebridge.core.astro.aberration_math import LIGHT_SPEED_AU_PER_DAY
from fatebridge.core.astro.cartesian import CartesianState, Vector3
from fatebridge.core.astro.earth_attitude import earth_attitude, physical_equator
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.astro.reference_frames import dot, mv
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
    terrestrial_observer,
)
from fatebridge.core.astro.time_scales import tt_from_ut1
from fatebridge.utils.errors import EphemerisSourceError

SolarDefinition = Literal["hindu_geometric_center", "apparent_topocentric_center"]
SOURCE_MASK = 7  # Original SEFLG_EPHMASK; all other requested flags must agree.
SOLAR_EVENT_MODEL = "fatebridge.physical_solar_horizon_crossing.v4"
MOSHIER_SIGN_SCAN_SECONDS = 0.02  # Original adjacent-UT1 diagnostic radius.
MOSHIER_MAX_LOCAL_SIGN_CHANGES = 2  # Admit a resolved rise/set pair near tangency.


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
    if len(coordinates) < 6:
        raise EphemerisSourceError("coordinate_values_unavailable")
    x, y, z, vx, vy, vz = (float(v) for v in coordinates[:6])
    if not all(math.isfinite(v) for v in (x, y, z, vx, vy, vz)):
        raise EphemerisSourceError("coordinate_values_unavailable")
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
    Polar motion, geoid, dynamical accuracy and atmosphere remain separate.
    """
    module = runtime.swe
    if module is None:
        raise ImportError("Swiss Ephemeris is required for solar events")
    if source is not None and ephemeris_flags is not None:
        raise ValueError("Choose a solar source or native flags, not both")
    with runtime.preserve_ephemeris_path():
        tt = tt_from_ut1(julian_day_ut1) if julian_day_tt is None else julian_day_tt
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
                    attitude = earth_attitude(module, julian_day_ut1, julian_day_tt=tt)
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
                    equator = physical_equator(module, julian_day_ut1, julian_day_tt=tt)
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
                    apparent = erfa.ab(
                        tuple(v / distance for v in natural_sun.position),
                        beta,
                        solar_distance,
                        math.sqrt(bm2),
                    )
                    x, y, z = mv(equator.matrix, tuple(float(v) for v in apparent))
                actual_model = runtime.ephemeris_model_from_retflag(actual_source)
            else:
                equator = physical_equator(module, julian_day_ut1, julian_day_tt=tt)
                receiver = (
                    terrestrial_observer(
                        equator, longitude=longitude, latitude=latitude, height=height
                    )
                    if definition == "apparent_topocentric_center"
                    else CartesianState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
                )
                direction = precise_solar_direction(tt, receiver, selected)
                x, y, z = mv(equator.matrix, direction)
                if definition == "hindu_geometric_center":
                    attitude = earth_attitude(module, julian_day_ut1, julian_day_tt=tt)
                    ecliptic = mv(attitude.reduction.target_to_ecliptic, (x, y, z))
                    angle = math.atan2(ecliptic[1], ecliptic[0])
                    x, y, z = mv(
                        attitude.reduction.ecliptic_to_target,
                        (math.cos(angle), math.sin(angle), 0.0),
                    )
                actual_source = None
                actual_model = selected.value
        except module.Error as error:
            raise EphemerisSourceError("unavailable_during") from error
        local = math.radians(equator.greenwich_sidereal_degrees + longitude)
        phi = math.radians(latitude)
        east = math.fsum((-math.sin(local) * x, math.cos(local) * y))
        north = math.fsum(
            (
                -math.sin(phi) * math.cos(local) * x,
                -math.sin(phi) * math.sin(local) * y,
                math.cos(phi) * z,
            )
        )
        up = math.fsum(
            (
                math.cos(phi) * math.cos(local) * x,
                math.cos(phi) * math.sin(local) * y,
                math.sin(phi) * z,
            )
        )
        return SolarObservation(
            julian_day_ut1,
            tt,
            math.degrees(math.atan2(up, math.hypot(east, north))),
            (x, y, z),
            actual_model,
            actual_source,
            definition,
        )


def _solar_extremum(
    value: Callable[[float], float], lower: float, upper: float, *, maximum: bool
) -> float:
    """Refine a bracketed solar-height extremum without clipping latitude."""
    ratio = (math.sqrt(5) - 1) / 2
    left = upper - ratio * (upper - lower)
    right = lower + ratio * (upper - lower)
    sign = -1 if maximum else 1
    left_value, right_value = sign * value(left), sign * value(right)
    for _ in range(96):
        if left == right or left == lower or right == upper:
            break
        if left_value < right_value:
            upper, right, right_value = right, left, left_value
            left = upper - ratio * (upper - lower)
            left_value = sign * value(left)
        else:
            lower, left, left_value = left, right, right_value
            right = lower + ratio * (upper - lower)
            right_value = sign * value(right)
    else:
        raise RuntimeError("Solar altitude extremum did not converge")
    return min((lower, left, right, upper), key=lambda point: sign * value(point))


def _chebyshev_value(coefficients: list[float], x: float) -> float:
    """Clenshaw evaluation, including close roots without a power-basis change."""
    first = second = 0.0
    for coefficient in reversed(coefficients[1:]):
        first, second = math.fsum((coefficient, 2 * x * first, -second)), first
    return math.fsum((coefficients[0], x * first, -second))


def _chebyshev_derivative(coefficients: list[float]) -> list[float]:
    degree = len(coefficients) - 1
    if degree == 0:
        return [0.0]
    derivative = [0.0] * degree
    for index in range(degree - 1, -1, -1):
        derivative[index] = 2 * (index + 1) * coefficients[index + 1]
        if index + 2 < degree:
            derivative[index] += derivative[index + 2]
    derivative[0] /= 2
    return derivative


def _chebyshev_roots(coefficients: list[float]) -> list[float]:
    """Isolate real roots on [-1,1] by the derivative's monotone intervals.

    Rolle's theorem supplies the partitions recursively. The interpolant only
    proposes height extrema; physical observations decide every event bracket.
    """
    if len(coefficients) == 1:
        return []
    stationary = _chebyshev_roots(_chebyshev_derivative(coefficients))
    nodes = [-1.0, *stationary, 1.0]
    values = [_chebyshev_value(coefficients, point) for point in nodes]
    roots = [point for point, value in zip(nodes, values) if value == 0]
    for lower, upper, low_value, high_value in zip(
        nodes, nodes[1:], values, values[1:]
    ):
        if not (low_value < 0 < high_value or high_value < 0 < low_value):
            continue
        for _ in range(64):
            middle = lower + (upper - lower) / 2
            if middle == lower or middle == upper:
                break
            score = _chebyshev_value(coefficients, middle)
            if score == 0:
                lower = upper = middle
                break
            if (score < 0) == (low_value < 0):
                lower, low_value = middle, score
            else:
                upper = middle
        roots.append(lower + (upper - lower) / 2)
    return sorted(set(roots))


def _solar_height_nodes(
    value: Callable[[float], float], lower: float, upper: float
) -> list[float]:
    """Resolve the smooth vertical component, allowing clustered extrema.

    Chebyshev interpolation avoids assuming one extremum per sampling interval.
    Its high-order tail controls subdivision; the tolerance includes rounding
    the absolute UT1 date to binary64. This is a numerical resolution check,
    not an interval-arithmetic proof for arbitrarily small tangent arcs.
    See https://www.chebfun.org/docs/guide/guide03.html for spectral rootfinding.
    """
    degree = 12
    pending = [(lower, upper, 0)]
    nodes: set[float] = set()
    while pending:
        lower, upper, depth = pending.pop()
        middle = lower + (upper - lower) / 2
        radius = (upper - lower) / 2
        points = [
            (
                upper
                if index == 0
                else (
                    lower
                    if index == degree
                    else middle + radius * math.cos(index * math.pi / degree)
                )
            )
            for index in range(degree + 1)
        ]
        scores = [value(point) for point in points]
        coefficients = [
            math.fsum(
                (0.5 if index in (0, degree) else 1.0)
                * score
                * math.cos(index * order * math.pi / degree)
                for index, score in enumerate(scores)
            )
            * 2
            / degree
            * (0.5 if order in (0, degree) else 1.0)
            for order in range(degree + 1)
        ]
        uncertainty = 32 * math.ulp(1.0) + 32 * (max(scores) - min(scores)) * math.ulp(
            middle
        ) / (upper - lower)
        tail = math.fsum(abs(c) for c in coefficients[-4:])
        nodes.update(points)
        # |T_k(x)| <= 1 gives the interpolant's complete range. A band
        # separated from zero needs no extremum localization. In particular,
        # do not subdivide coordinate roundoff at a polar solstice tens of
        # degrees from the horizon. The tail is a numerical estimate, not a
        # certified enclosure of an arbitrary underlying ephemeris function.
        if abs(coefficients[0]) - math.fsum(abs(c) for c in coefficients[1:]) > (
            8 * tail + uncertainty
        ):
            continue
        if tail > uncertainty:
            if depth == 20 or middle in (lower, upper):
                raise RuntimeError("Solar altitude interpolation did not converge")
            pending.extend(((lower, middle, depth + 1), (middle, upper, depth + 1)))
            continue
        while len(coefficients) > 1 and abs(coefficients[-1]) <= uncertainty:
            coefficients.pop()
        derivative = _chebyshev_derivative(coefficients)
        extrema = [x for x in _chebyshev_roots(derivative) if -1 < x < 1]
        partitions = [-1.0, *extrema, 1.0]
        for index, estimate in enumerate(extrema, start=1):
            left = (partitions[index - 1] + estimate) / 2
            right = (estimate + partitions[index + 1]) / 2
            before = _chebyshev_value(derivative, left)
            after = _chebyshev_value(derivative, right)
            if before * after < 0:
                nodes.add(
                    _solar_extremum(
                        value,
                        middle + radius * left,
                        middle + radius * right,
                        maximum=before > 0,
                    )
                )
    return sorted(nodes)


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
    An exactly zero endpoint needs one-sided context to classify direction.
    The root coordinate is the lower endpoint of its adjacent-float bracket;
    this gives half-open daily partitions one consistent event owner.
    Source, clock and convergence failures propagate; an empty list means
    only that this valid window contains no resolved directed crossing.
    Native Moshier roots are checked on adjacent UT1 dates within 20 milliseconds,
    including neighboring crossings outside the requested window. A resolved
    rise/set pair is admitted; additional or unresolved sign changes are rejected.
    This local admission policy does not certify continuity or physical accuracy.
    Atmosphere for the apparent-centre preset is fixed at sea level,
    1013.25 hPa, 0 Celsius and lapse rate 0.0065 K/m, as declared by its caller.
    """
    module = runtime.swe
    if module is None:
        raise ImportError("Swiss Ephemeris is required for solar events")
    if (
        not math.isfinite(start_ut1)
        or not math.isfinite(end_ut1)
        or end_ut1 <= start_ut1
    ):
        raise ValueError(
            "Solar event window must have finite, increasing UT1 endpoints"
        )
    if source is not None and ephemeris_flags is not None:
        raise ValueError("Choose a solar source or native flags, not both")
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
                if (
                    ephemeris_policy == "require_data_files"
                    and sample.ephemeris_model
                    not in {"swieph", "jpl", FileSolarSource.value}
                ):
                    raise ValueError(
                        "require_data_files requires file-backed solar ephemerides"
                    )
                observations[ut1] = sample
            return math.sin(
                math.radians(observations[ut1].altitude_degrees)
            ) - math.sin(math.radians(horizon))

        search_start_ut1, search_end_ut1 = start_ut1, end_ut1
        if isinstance(fixed_source, NativeSolarSource):
            value(start_ut1)
            if observed_source is not None and observed_source[0] == "moshier":
                search_start_ut1 -= MOSHIER_SIGN_SCAN_SECONDS / 86400
                search_end_ut1 += MOSHIER_SIGN_SCAN_SECONDS / 86400
            else:
                pass
        else:
            pass
        grid = [
            point
            for index in range(math.ceil((search_end_ut1 - search_start_ut1) * 12))
            if (point := search_start_ut1 + index / 12) < search_end_ut1
        ]
        grid.append(search_end_ut1)
        nodes = sorted(
            {
                point
                for lower, upper in zip(grid, grid[1:])
                for point in _solar_height_nodes(value, lower, upper)
            }
        )
        scores = [value(point) for point in nodes]
        crossings = []
        for index, lower in enumerate(nodes):
            low_value = scores[index]
            if low_value == 0:
                previous_score = next(
                    (v for v in reversed(scores[:index]) if v != 0), None
                )
                following_score = next((v for v in scores[index + 1 :] if v != 0), None)
                # Only exact endpoint zeros require a source-sided context.
                # Start with the nearest representable date, rather than a
                # fixed cursor that can skip a complete polar visibility arc.
                for direction in (-1, 1):
                    if (
                        previous_score if direction < 0 else following_score
                    ) is not None:
                        continue
                    offset = math.ulp(lower)
                    while offset <= 1 / 12:
                        score = value(lower + direction * offset)
                        if score != 0:
                            if direction < 0:
                                previous_score = score
                            else:
                                following_score = score
                            break
                        offset *= 2
                if (
                    previous_score is not None
                    and following_score is not None
                    and previous_score * following_score < 0
                ):
                    sample = observations[lower]
                    crossings.append(
                        SolarEvent(
                            lower,
                            sample.julian_day_tt,
                            sample.ephemeris_model,
                            sample.ephemeris_flags,
                            definition,
                            (lower, lower),
                            sample.altitude_degrees,
                            horizon,
                            len(observations),
                            previous_score < 0,
                        )
                    )
                continue
            if index + 1 == len(nodes):
                continue
            upper, high_value = nodes[index + 1], scores[index + 1]
            if low_value * high_value >= 0:
                continue
            rising = low_value < 0
            for _ in range(64):
                middle = lower + (upper - lower) / 2
                if middle == lower or middle == upper:
                    break
                current = value(middle)
                if current == 0:
                    lower = upper = middle
                    break
                if (current < 0) == (low_value < 0):
                    lower, low_value = middle, current
                else:
                    upper, high_value = middle, current
            else:
                raise RuntimeError("Solar event crossing did not converge")
            event = lower
            sample = observations[event]
            crossings.append(
                SolarEvent(
                    event,
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
        for crossing in crossings:
            if (
                crossing.ephemeris_model == "moshier"
                and start_ut1 <= crossing.julian_day_ut1 <= end_ut1
            ):
                scan_ut1 = crossing.julian_day_ut1 - MOSHIER_SIGN_SCAN_SECONDS / 86400
                scan_end_ut1 = (
                    crossing.julian_day_ut1 + MOSHIER_SIGN_SCAN_SECONDS / 86400
                )
                resolved_crossing_count = sum(
                    scan_ut1 <= neighbor.julian_day_ut1 <= scan_end_ut1
                    for neighbor in crossings
                )
                allowed_sign_changes = min(
                    MOSHIER_MAX_LOCAL_SIGN_CHANGES, resolved_crossing_count
                )
                previous_sign = 0
                sign_changes = 0
                while scan_ut1 <= scan_end_ut1:
                    score = value(scan_ut1)
                    current_sign = (score > 0) - (score < 0)
                    if current_sign:
                        if previous_sign and current_sign != previous_sign:
                            sign_changes += 1
                        else:
                            pass
                        previous_sign = current_sign
                    else:
                        pass
                    if sign_changes > allowed_sign_changes:
                        raise EphemerisSourceError("solar_horizon_sign_unstable")
                    else:
                        scan_ut1 = math.nextafter(scan_ut1, math.inf)
            else:
                pass
        crossings = [
            crossing
            for crossing in crossings
            if start_ut1 <= crossing.julian_day_ut1 <= end_ut1
        ]
        if crossings and crossings[0].ephemeris_model == "moshier":
            crossings = [
                replace(crossing, observation_evaluations=len(observations))
                for crossing in crossings
            ]
        else:
            pass
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
