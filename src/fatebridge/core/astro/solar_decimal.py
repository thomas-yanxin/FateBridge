"""Stable auxiliary reduction of the pinned apparent-position source models.

Small solar separations make the native binary64 subtraction 1+q.e and
sqrt(1-(u.e)^2) ill-conditioned. This uses equivalent vector identities and
50-digit arithmetic on the observed geometric states. It neither replaces
displayed positions nor supplies an independent physical ephemeris.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from importlib.resources import files
from typing import Any, Sequence, TypedDict

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import moshier_lunar_geometry, reference_frames, runtime
from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.polynomial_stencils import polynomial_weights
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.compressed_ephemeris import preserve_native_dependency_context
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

METHOD_ID = "native_geometric_decimal_apparent_reduction_v2"
PRECISION = 50
PROFILE_SHA256 = "ad8dd7126d5e1a4b2e6cbcef6aa13d5a4bbc51778db0c037f430a3fac50e8b36"
SOURCE_URL = "https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/sweph.c"
FRAME_BODIES = ("Mercury", "Mars", "Pluto")
MOSHIER_PLANETS = frozenset(
    {"Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
)
MOSHIER_SOURCE_TARGETS = MOSHIER_PLANETS | {"Sun", "Moon"}
MOSHIER_METHOD_ID = "native_moshier_nominal_backward_speed_decimal_reduction_v1"
MOSHIER_LUNAR_METHOD_ID = (
    "native_moshier_forward_moon_backward_earth_decimal_reduction_v1"
)
Vector = Sequence[Decimal]
MoshierGeometricStates = dict[tuple[float, int, int], tuple[Decimal, ...]]


class SourceVelocityReceipt(TypedDict):
    method_id: str
    interpolation_step_days: float
    nominal_interval_days: float
    native_rounded_interval_days: float
    polynomial_degree: int
    node_count: int
    maximum_abscissa_roundoff_days: float


class LunarSourceVelocityReceipt(SourceVelocityReceipt):
    lunar_operator: SourceVelocityReceipt
    lunar_geometry: dict[str, str]


class ReductionReceipt(TypedDict):
    frame_orthogonality_error: float
    epoch_remainder_days: float
    solar_interpolation_branch: dict[str, object]
    ephemeris_model: str
    source_velocity: SourceVelocityReceipt | None


def mass_profile() -> list[tuple[Decimal, Decimal]]:
    """Check the reviewed source table on every fallback sample, without caching."""
    try:
        raw = (
            files("fatebridge")
            .joinpath("data/astro/native-solar-mass-v1.json")
            .read_bytes()
        )
        if hashlib.sha256(raw).hexdigest() != PROFILE_SHA256:
            raise ValueError("Changed finite-Sun source profile")
        data = json.loads(raw)
        return [(Decimal(r), Decimal(m)) for r, m in data["radius_mass_pairs"]]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error


def dot(a: Vector, b: Vector) -> Decimal:
    return sum((x * y for x, y in zip(a, b)), Decimal(0))


def add(a: Vector, b: Vector) -> list[Decimal]:
    return [x + y for x, y in zip(a, b)]


def sub(a: Vector, b: Vector) -> list[Decimal]:
    return [x - y for x, y in zip(a, b)]


def scale(a: Vector, value: Decimal) -> list[Decimal]:
    return [x * value for x in a]


def cross(a: Vector, b: Vector) -> list[Decimal]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def norm(a: Vector) -> Decimal:
    return dot(a, a).sqrt()


def unit(a: Vector) -> list[Decimal]:
    size = norm(a)
    if not size.is_finite() or size <= 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    return scale(a, Decimal(1) / size)


def stable_interpolation_cell(
    impact: Decimal, angular_radius: Decimal, observer_to_target_ratio: Decimal
) -> dict[str, Any]:
    """Classify the stable reduction's cell, retaining its arithmetic margin.

    The cross product avoids sqrt(1-dot²)'s inverse-radius-squared loss.
    This finite-arithmetic scale is not an observational/source-error bound.
    """
    if (
        not all(
            v.is_finite() for v in (impact, angular_radius, observer_to_target_ratio)
        )
        or impact < 0
        or angular_radius <= 0
        or observer_to_target_ratio <= 0
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    pad = (
        64
        * Decimal.from_float(math.ulp(1.0))
        / angular_radius
        * (1 + observer_to_target_ratio)
    )
    cell = min(100, int(impact * 100))
    lower, upper = impact - pad, impact + pad
    interior = lower > Decimal(cell) / 100 and (
        cell == 100 or upper < Decimal(cell + 1) / 100
    )
    return {
        "method_id": "decimal_continuous_source_cross_product_cell_v1",
        "status": "interior_sampled_cell" if interior else "boundary_ambiguous",
        "cell": cell if interior else None,
        "impact_solar_radius_fraction": float(impact),
        "arithmetic_margin_fraction": float(pad),
        "scope": "Stable auxiliary source reduction cell; finite arithmetic scale, not continuous-interval or physical ephemeris accuracy certification.",
    }


@runtime.preserve_ephemeris_path()
def reduced_longitude(
    planet: str,
    epoch: float,
    *,
    sidereal: bool,
    trace: PhysicalEphemerisTrace,
    contexts: dict[str, Any],
    prefix: str,
    center_source: dict[str, Any],
    model: str = "swieph",
    source_step_days: float = 0.0625,
    moshier_geometric_states: MoshierGeometricStates | None = None,
) -> tuple[float, ReductionReceipt]:
    """Reduce shared Swiss geometric states, retaining the center file cohort.

    Swiss/JPL use their two iterations and geometric retarded state, restoring
    its lost epoch fraction to first order. Moshier planets retain their one
    linearized iteration; its Sun has neither that iteration nor self-deflection.
    Its Moon retains the forward-biased three-point lunar source-speed operator
    and geocentric light time, without subtracting heliocentric Earth twice.
    The source-speed operators use checked geometric polynomials.
    Shared high-precision deflection and aberration are
    transformed by native frame pairs. This is source arithmetic, not an
    independent ephemeris or a physical accuracy bound. The Moshier caller may
    share checked native geometry across samples of one locked derivative.
    """
    swe = runtime.swe
    if (
        not math.isfinite(epoch)
        or planet
        not in (
            MOSHIER_SOURCE_TARGETS
            if model == "moshier"
            else {"Mercury", "Venus", "Mars"}
        )
        or model not in {"swieph", "jpl", "moshier"}
    ):
        raise EphemerisSourceError("coordinate_motion_unavailable")
    selected = configured_ephemeris_path()
    base = (
        (swe.FLG_MOSEPH if model == "moshier" else swe.FLG_SWIEPH)
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_TRUEPOS
    )
    fixed = base | swe.FLG_EQUATORIAL | swe.FLG_J2000 | swe.FLG_ICRS
    display = base | (swe.FLG_SIDEREAL if sidereal else 0)
    mask = 0
    for name in COORDINATE_FLAGS:
        mask |= getattr(swe, name)

    def state(at: float, body: int, flags: int, suffix: str) -> list[Decimal]:
        key = (at, body, flags)
        geometry = (
            moshier_geometric_states.get(key)
            if moshier_geometric_states is not None
            else None
        )
        if geometry is None:
            values, returned = runtime.ephemeris_call("calc", at, body, flags)
            assert_physical_configuration(selected)
            expected = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
            if flags & (swe.FLG_J2000 | swe.FLG_SIDEREAL):
                expected |= swe.FLG_NONUT
            if (
                returned < 0
                or returned & mask != expected & mask
                or not returned & swe.FLG_SPEED
            ):
                raise EphemerisSourceError("coordinate_contract_changed")
            if runtime.ephemeris_model_from_retflag(returned) != model:
                raise EphemerisSourceError("model_changed")
            if len(values) != 6 or not all(math.isfinite(x) for x in values):
                raise EphemerisSourceError("coordinate_values_unavailable")
            geometry = tuple(Decimal.from_float(float(x)) for x in values)
            if moshier_geometric_states is not None:
                moshier_geometric_states[key] = geometry
        else:
            assert_physical_configuration(selected)
        factor = prefix + suffix
        context = trace.observe(factor, model, record_factor=False)
        contexts[factor] = context
        if context != center_source:
            raise EphemerisSourceError("dependency_source_window_incoherent")
        return list(geometry)

    with (
        localcontext() as ctx,
        preserve_native_dependency_context(
            epoch, epoch, model, native=ephemeris_runtime.swe
        ),
    ):
        ctx.prec = PRECISION
        au, light, day = Decimal(149597870700), Decimal(299792458), Decimal(86400)
        body = PLANET_SWISSEPH_IDS[planet]
        origin = swe.FLG_HELCTR if model == "moshier" else swe.FLG_BARYCTR
        initial = (
            [Decimal(0)] * 6
            if model == "moshier" and planet == "Sun"
            else state(
                epoch, body, fixed | (0 if planet == "Moon" else origin), "_initial"
            )
        )
        earth = state(epoch, swe.EARTH, fixed | origin, "_earth")
        if planet == "Moon":
            initial[:3] = moshier_lunar_geometry.equatorial(epoch, epoch)
        source_velocity: SourceVelocityReceipt | None = None
        if model == "moshier":
            # swi_moshplan uses a short backward difference inside light time
            # and aberration. Evaluating its small numerator directly injects
            # source roundoff into the apparent *position*. Evaluate the
            # nominal operator on the same geometric source polynomial;
            # keep its rounded native offset as a diagnostic only.
            interval = epoch - (epoch - 0.0001)
            offsets = tuple(
                (epoch + i * source_step_days) - epoch for i in range(-3, 4)
            )
            for identifier, target, role in (
                (body, initial, "body"),
                (swe.EARTH, earth, "earth"),
            ):
                if planet == "Sun" and role == "body":
                    # The analytical model's heliocentric Sun is the origin.
                    continue
                lunar = planet == "Moon" and role == "body"
                interval_days = 0.00005 if lunar else 0.0001
                operator_at = Fraction(interval_days) / Fraction(source_step_days)
                weights = [
                    Decimal(w.numerator) / Decimal(w.denominator)
                    for w in polynomial_weights(
                        tuple(
                            Fraction(x) / Fraction(source_step_days) for x in offsets
                        ),
                        tuple(
                            (
                                Fraction(3, 2) * operator_at**i
                                + Fraction(1, 2) * (-operator_at) ** i
                                - 2 * Fraction(i == 0)
                                if lunar
                                else Fraction(i == 0) - (-operator_at) ** i
                            )
                            / Fraction(interval_days)
                            for i in range(7)
                        ),
                    )
                ]
                positions = [
                    state(
                        epoch + i * source_step_days,
                        identifier,
                        fixed | (0 if lunar else origin),
                        f"_source_velocity_{role}_{i:+d}",
                    )
                    for i in range(-3, 4)
                ]
                if lunar:
                    for i, position in zip(range(-3, 4), positions):
                        position[:3] = moshier_lunar_geometry.equatorial(
                            epoch + i * source_step_days, epoch
                        )
                target[3:] = [
                    sum(
                        (
                            w * (position[axis] - positions[3][axis])
                            for w, position in zip(weights, positions)
                        ),
                        Decimal(0),
                    )
                    for axis in range(3)
                ]
            sun = [Decimal(0)] * 6
            source_velocity = {
                "method_id": MOSHIER_METHOD_ID,
                "interpolation_step_days": source_step_days,
                "nominal_interval_days": 0.0001,
                "native_rounded_interval_days": interval,
                "polynomial_degree": 6,
                "node_count": 7,
                "maximum_abscissa_roundoff_days": max(
                    abs(x - i * source_step_days) for i, x in zip(range(-3, 4), offsets)
                ),
            }
            if planet == "Moon":
                lunar_velocity: LunarSourceVelocityReceipt = {
                    **source_velocity,
                    "lunar_geometry": {
                        "method_id": moshier_lunar_geometry.METHOD_ID,
                        "coefficient_sha256": moshier_lunar_geometry.COEFFICIENT_SHA256,
                        "source_url": moshier_lunar_geometry.SOURCE_URL,
                        "frame_model": reference_frames.NATIVE_TROPICAL_MODEL,
                    },
                    "lunar_operator": {
                        **source_velocity,
                        "method_id": "native_moshier_forward_biased_three_point_source_velocity_v1",
                        "nominal_interval_days": 0.00005,
                        "native_rounded_interval_days": (epoch + 0.00005) - epoch,
                    },
                }
                source_velocity = lunar_velocity
        else:
            sun = state(epoch, swe.SUN, fixed | origin, "_sun")
        rough = initial[:3]
        delay = Decimal(0)
        for _ in range(
            0 if planet in {"Sun", "Moon"} else 1 if model == "moshier" else 2
        ):
            delay = norm(sub(rough, earth[:3])) * au / light / day
            rough = sub(initial[:3], scale(initial[3:], delay))
        if model == "moshier":
            if planet == "Moon":
                # app_pos_etc_moon first adds Earth, propagates the combined
                # state once, then subtracts the reception observer. Cancel
                # Earth algebraically before the small geocentric reduction.
                delay = norm(initial[:3]) * au / light / day
                ray = sub(initial[:3], scale(add(initial[3:], earth[3:]), delay))
            else:
                ray = sub(rough, earth[:3])
            remainder = Decimal(0)
        else:
            at = float(Decimal.from_float(epoch) - delay)
            remainder = Decimal.from_float(epoch) - Decimal.from_float(at) - delay
            with preserve_native_dependency_context(
                epoch, at, model, native=ephemeris_runtime.swe
            ):
                retarded = state(at, body, fixed | origin, "_retarded")
            ray = sub(add(retarded[:3], scale(retarded[3:], remainder)), earth[:3])
        if planet in {"Sun", "Moon"}:
            # app_pos_etc_sun has no solar self-deflection. There is no
            # effective-mass knot in this model, rather than a selected cell.
            deflected = ray
            source_cell: dict[str, object] = {
                "method_id": "moshier_solar_no_self_deflection_v1",
                "status": "not_in_source_model",
                "cell": "no_solar_deflection",
                "scope": "The geocentric Moshier solar source omits self-deflection; only source-range qualification restricts this sampled branch.",
            }
            if planet == "Moon":
                source_cell.update(
                    method_id="moshier_lunar_no_solar_deflection_v1",
                    scope="The geocentric Moshier lunar source omits solar deflection; its Moon/Earth geometric source-range intersection restricts this sampled branch.",
                )
        else:
            mass = mass_profile()
            radius = norm(ray)
            u = unit(ray)
            eh = sub(earth[:3], sun[:3])
            re = norm(eh)
            e = unit(eh)
            q = unit(sub(add(ray, earth[:3]), sub(sun[:3], scale(sun[3:], delay))))
            impact = norm(cross(u, e)) / (
                Decimal.from_float(math.radians(959.63 / 3600)) / re
            )
            source_cell = stable_interpolation_cell(
                impact,
                Decimal.from_float(math.radians(959.63 / 3600)) / re,
                re / radius,
            )
            if impact <= 0:
                fraction = Decimal(0)
            elif impact >= 1:
                fraction = Decimal(1)
            else:
                for (r0, m0), (r1, m1) in zip(mass, mass[1:]):
                    if impact >= r1:
                        fraction = m0 + (impact - r0) * (m1 - m0) / (r1 - r0)
                        break
                else:
                    raise EphemerisSourceError("coordinate_values_unavailable")
            strength = (
                2 * Decimal("1.32712440017987e20") * fraction / light**2 / au / re
            )
            denominator = dot(add(q, e), add(q, e)) / 2
            if denominator <= 0:
                raise EphemerisSourceError("coordinate_motion_unavailable")
            deflected = scale(
                add(u, scale(cross(u, cross(e, q)), strength / denominator)), radius
            )
        beta = scale(earth[3:], au / light / day)
        r = norm(deflected)
        lorentz = (1 - dot(beta, beta)).sqrt()
        f = dot(deflected, beta) / r
        apparent = scale(
            add(scale(deflected, lorentz), scale(beta, (1 + f / (1 + lorentz)) * r)),
            1 / (1 + f),
        )
        pairs = [
            (
                state(epoch, PLANET_SWISSEPH_IDS[name], fixed, f"_basis_{name}_fixed"),
                state(
                    epoch, PLANET_SWISSEPH_IDS[name], display, f"_basis_{name}_display"
                ),
            )
            for name in FRAME_BODIES
        ]
        # Build the known frame directly. Native body pairs witness its model;
        # recovering it by inversion amplifies their nearly coplanar roundoff.
        angles, returned = runtime.ephemeris_call(
            "calc", epoch, swe.ECL_NUT, swe.FLG_MOSEPH
        )
        if returned < 0 or not all(math.isfinite(v) for v in angles[:4]):
            raise EphemerisSourceError("coordinate_values_unavailable")
        true_epsilon, mean_epsilon, psi, deps = angles[:4]
        matrix = reference_frames.mm(
            reference_frames.ecliptic_rotation(
                math.radians(mean_epsilon if sidereal else true_epsilon)
            )[0],
            reference_frames.native_equatorial_frame(
                epoch,
                mean_epsilon,
                0.0 if sidereal else psi,
                0.0 if sidereal else deps,
            ),
        )
        if sidereal:
            returned, ayanamsa = runtime.ephemeris_call(
                "get_ayanamsa_ex", epoch, swe.FLG_MOSEPH | swe.FLG_NONUT
            )
            if returned < 0 or not math.isfinite(ayanamsa):
                raise EphemerisSourceError("coordinate_values_unavailable")
            c, s = math.cos(math.radians(ayanamsa)), math.sin(math.radians(ayanamsa))
            matrix = reference_frames.mm(
                ((c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0)), matrix
            )
        decimal_matrix = [[Decimal.from_float(v) for v in row] for row in matrix]
        orthogonal = max(
            abs(
                sum(
                    (decimal_matrix[k][i] * decimal_matrix[k][j] for k in range(3)),
                    Decimal(0),
                )
                - int(i == j)
            )
            for i in range(3)
            for j in range(3)
        )
        model_error = max(
            norm(
                sub(
                    [dot(row, unit(before[:3])) for row in decimal_matrix],
                    unit(after[:3]),
                )
            )
            for before, after in pairs
        )
        determinant = dot(
            decimal_matrix[0], cross(decimal_matrix[1], decimal_matrix[2])
        )
        if max(orthogonal, model_error, abs(determinant - 1)) > Decimal("1e-10"):
            raise EphemerisSourceError("coordinate_contract_changed")
        displayed = [dot(row, apparent) for row in decimal_matrix]
        longitude = (
            math.degrees(math.atan2(float(displayed[1]), float(displayed[0]))) % 360
        )
        return longitude, {
            "frame_orthogonality_error": float(orthogonal),
            "epoch_remainder_days": float(remainder),
            "solar_interpolation_branch": source_cell,
            "ephemeris_model": model,
            "source_velocity": source_velocity,
        }
