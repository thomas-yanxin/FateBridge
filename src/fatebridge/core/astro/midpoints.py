"""Versioned Hamburg-style midpoint geometry, with explicit astronomical inputs.

This is a geometric subset, not a transcription of the complete Rules for
Planetary Pictures. Hypothetical Hamburg factors are never physical planets.
All comparisons use unrounded coordinates; rational arithmetic preserves the
side of a dial boundary represented by the input floats.
"""

from __future__ import annotations

import math
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from typing import Any, Mapping

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    geographic_pole_angle_definition,
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.house_axes import canonical_house_axes
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.meridian_houses import (
    native_meridian_houses,
    unavailable_meridian_houses,
)
from fatebridge.core.astro.meridian_placement import attach_factor_placement
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.reference import PHYSICAL_BODIES
from fatebridge.core.astro.reference_angles import (
    qualify_reference_geometry,
    reference_angle_basis,
)
from fatebridge.core.astro.sensitive import SOURCE as SENSITIVE_SOURCE
from fatebridge.core.astro.sensitive import sensitive_equivalence
from fatebridge.core.astro.terrestrial_observer import terrestrial_frame
from fatebridge.utils.errors import EphemerisCalculationError, EphemerisSourceError

RULESET = "hamburg_midpoint_geometry_v3"
HYPOTHETICAL_BODIES = (
    "Cupido",
    "Hades",
    "Zeus",
    "Kronos",
    "Apollon",
    "Admetos",
    "Vulkanus",
    "Poseidon",
)
SOURCES: list[dict[str, Any]] = [
    SENSITIVE_SOURCE,
    {
        "id": "rudolph_1979_17laws",
        "author": "Ludwig Rudolph",
        "title": "17 Gesetze fuer Planetenbilder, Hamburger Hefte 1979/2, no.74, p.1, article 823",
        "sections": ["3", "7", "13", "14", "15", "16"],
        "scope": "Geometric propositions only; not adoption of interpretive or empirical claims",
    },
    {
        "id": "witte_instruments",
        "author": "Witte-Verlag Hamburg",
        "title": "Arbeitsgeraete: 360, 90 and 45 degree dials and midpoint ruler",
        "scope": "Published dial instruments; not the full interpretation rulebook",
    },
    {
        "id": "swiss_programmer",
        "author": "Astrodienst AG",
        "title": "Swiss Ephemeris Programmer's Manual",
        "sections": [
            "3.2.3 fictitious planets",
            "9.2 UTC and Julian day",
            "12 sidereal functions",
        ],
    },
    {
        "id": "swiss_hypothetical",
        "author": "Astrodienst AG",
        "title": "Swiss Ephemeris 2.10: 2.7.1 Uranian planets",
        "scope": "James Neely revised mathematical elements; no observed physical bodies",
    },
]


def _angle(value: float) -> Fraction:
    if not math.isfinite(value):
        raise ValueError("Midpoint coordinates must be finite")
    return Fraction(value) % 360


def midpoint_axis(first: float, second: float) -> dict[str, Any]:
    """The unordered pair of diametrically opposite midpoints.

    A 180-degree pair has no unique shorter-arc midpoint. Its symmetry axis is
    still defined modulo 180; swapping the input factors cannot change it.
    """
    a, b = _angle(first), _angle(second)
    axis = ((a + b) / 2) % 180
    return {
        "axis_longitude": min(float(axis), math.nextafter(180.0, 0.0)),
        "opposite_longitude": min(float(axis + 180), math.nextafter(360.0, 0.0)),
        "antipodal_inputs": (a - b) % 360 == 180,
        "dial_90": min(float(axis % 90), math.nextafter(90.0, 0.0)),
        "dial_45": min(float(axis % 45), math.nextafter(45.0, 0.0)),
    }


def _residual(
    first: Fraction, second: Fraction, period: int | float | Fraction
) -> Fraction:
    p = Fraction(str(period)) if isinstance(period, float) else Fraction(period)
    return (first - second + p / 2) % p - p / 2


def _evaluate_sensitive_point_query(
    query: str,
    points: Mapping[str, Fraction],
    periods: tuple[int | float, ...],
    orb: Fraction,
) -> dict[str, Any]:
    """Evaluate a sensitive point formula like 'Mars+Jupiter-Zeus' against natal factors."""
    tokens = query.replace("-", "+-").split("+")
    total = Fraction(0)
    parsed_terms: list[str] = []
    lookup = {k.casefold(): k for k in points}
    for raw in tokens:
        tok = raw.strip()
        if not tok:
            continue
        sign = -1 if tok.startswith("-") else 1
        name = tok.lstrip("+-").strip()
        canonical = lookup.get(name.casefold())
        if canonical is None:
            raise ValueError(
                f"Unknown factor '{name}' in sensitive_point_query '{query}'"
            )
        total += sign * points[canonical]
        parsed_terms.append(("-" if sign < 0 else "+") + canonical)
    target = total % 360
    hits: list[dict[str, Any]] = []
    for p in periods:
        p_frac = Fraction(str(p)) if isinstance(p, float) else Fraction(p)
        p_key = str(p)
        for name, val in points.items():
            delta = _residual(val, target, p_frac)
            if abs(delta) <= orb:
                hits.append(
                    {
                        "dial": p_key,
                        "factor": name,
                        "orb": float(abs(delta)),
                        "signed_orb": float(delta),
                    }
                )
    hits.sort(key=lambda r: (r["orb"], r["dial"], r["factor"]))
    return {
        "formula": "".join(parsed_terms).lstrip("+"),
        "longitude": float(target),
        "hits": hits,
    }


def midpoint_geometry(
    longitudes: Mapping[str, float],
    *,
    orb_degrees: float = 1.0,
    dial_degrees: str | None = None,
    sensitive_point_query: str | None = None,
    max_higher_factor_contacts: int | None = None,
) -> dict[str, Any]:
    """Sorted O(N log N) dial sweep across 90/45 (and optional 22.5) degree dials."""
    if not math.isfinite(orb_degrees) or not 0 <= orb_degrees <= 5:
        raise ValueError("Midpoint orb must be within 0..5 degrees")
    points = {name: _angle(value) for name, value in longitudes.items()}
    axes = []
    catalogue = []
    for a, b in combinations(points, 2):
        axis = ((points[a] + points[b]) / 2) % 180
        axes.append((a, b, axis))
        ax_f = min(float(axis), math.nextafter(180.0, 0.0))
        catalogue.append(
            {
                "id_a": a,
                "id_b": b,
                "axis_longitude": ax_f,
            }
        )
    orb = Fraction(orb_degrees)
    periods: tuple[int | float, ...] = (
        (90, 45, 22.5) if dial_degrees == "22.5" else (90, 45)
    )
    dials: dict[str, dict[str, Any]] = {}
    distinct_axes = [(a, b, axis) for a, b, axis in axes if a != b]
    point_items = list(points.items())

    for period in periods:
        p_frac = (
            Fraction(str(period)) if isinstance(period, float) else Fraction(period)
        )
        p_float = float(p_frac)
        half_p_f = p_float * 0.5
        orb_exact_f = float(orb_degrees)
        boundary_lo = orb_exact_f - 1e-8
        boundary_hi = orb_exact_f + 1e-8
        points_f = {name: float(val) % 360.0 for name, val in point_items}
        doubles, triples, quadruples = [], [], []
        for a, b in combinations(sorted(points), 2):
            delta_f = (points_f[a] - points_f[b] + half_p_f) % p_float - half_p_f
            abs_df = abs(delta_f)
            if abs_df > boundary_hi:
                continue
            if abs_df >= boundary_lo:
                delta_val = _residual(points[a], points[b], p_frac)
                if abs(delta_val) > orb:
                    continue
                delta_out = float(delta_val)
            else:
                delta_out = delta_f
            offset = int(round((points_f[a] - points_f[b] - delta_out) % 360.0))
            sep_f = abs((points_f[a] - points_f[b] + 180.0) % 360.0 - 180.0)
            doubles.append(
                {
                    "id_a": a,
                    "id_b": b,
                    "equation": f"{a}={b}",
                    "orb": abs(delta_out),
                    "signed_orb": delta_out,
                    "factor_offset_degrees": offset,
                    "aspect_degrees": min(offset, 360 - offset),
                    "separation_degrees": sep_f,
                }
            )
        point_mod = [
            (point, value, points_f[point] % p_float) for point, value in point_items
        ]
        for a, b, axis in distinct_axes:
            ax_f_raw = float(axis)
            ax_f = ax_f_raw % p_float
            for point, value, val_f in point_mod:
                if point in (a, b):
                    continue
                delta_f = (val_f - ax_f + half_p_f) % p_float - half_p_f
                abs_df = abs(delta_f)
                if abs_df > boundary_hi:
                    continue
                if abs_df >= boundary_lo:
                    delta_val = _residual(value, axis, p_frac)
                    if abs(delta_val) > orb:
                        continue
                    delta_out = float(delta_val)
                else:
                    delta_out = delta_f
                raw_offset = (points_f[point] - ax_f_raw - delta_out) % 180.0
                rounded_int = round(raw_offset)
                axis_offset: int | float = (
                    int(rounded_int)
                    if abs(raw_offset - rounded_int) < 1e-6
                    else round(raw_offset, 4)
                )
                triples.append(
                    {
                        "point": point,
                        "id_a": a,
                        "id_b": b,
                        "equation": f"{point}={a}/{b}",
                        "orb": abs(delta_out),
                        "signed_orb": delta_out,
                        "axis_offset_degrees": axis_offset,
                    }
                )

        # Single sorted circular sweep for four-factor axis hits: O(A log A + hits)
        sorted_axes = sorted(
            ((float(axis) % p_float, a, b, axis) for a, b, axis in distinct_axes),
            key=lambda item: item[0],
        )
        n_ax = len(sorted_axes)
        quadruples_seen: set[tuple[str, str, str, str]] = set()
        for i in range(n_ax):
            ax_i, a, b, left = sorted_axes[i]
            j = (i + 1) % n_ax
            steps = 0
            while steps < n_ax - 1:
                ax_j, c, d, right = sorted_axes[j]
                circ_diff = (ax_j - ax_i) % p_float
                if circ_diff > boundary_hi:
                    break
                if a != c and a != d and b != c and b != d:
                    pair_key = (a, b, c, d) if (a, b) < (c, d) else (c, d, a, b)
                    if pair_key not in quadruples_seen:
                        if (a, b) < (c, d):
                            delta_f = (ax_i - ax_j + half_p_f) % p_float - half_p_f
                        else:
                            delta_f = (ax_j - ax_i + half_p_f) % p_float - half_p_f
                        abs_df = abs(delta_f)
                        keep = True
                        if abs_df >= boundary_lo:
                            l_ax, r_ax = (
                                (left, right) if (a, b) < (c, d) else (right, left)
                            )
                            delta_val = _residual(l_ax, r_ax, p_frac)
                            if abs(delta_val) > orb:
                                keep = False
                            delta_out = float(delta_val)
                        else:
                            delta_out = delta_f
                        if keep:
                            quadruples_seen.add(pair_key)
                            quadruples.append(
                                {
                                    "id_a": pair_key[0],
                                    "id_b": pair_key[1],
                                    "id_c": pair_key[2],
                                    "id_d": pair_key[3],
                                    "equation": f"{pair_key[0]}/{pair_key[1]}={pair_key[2]}/{pair_key[3]}",
                                    "orb": abs(delta_out),
                                    "signed_orb": delta_out,
                                }
                            )
                j = (j + 1) % n_ax
                steps += 1

        for contacts in (doubles, triples, quadruples):
            contacts.sort(key=lambda row: (row["orb"], row["equation"]))
        total_three = len(triples)
        total_four = len(quadruples)
        returned_three = (
            triples[:max_higher_factor_contacts]
            if max_higher_factor_contacts is not None
            else triples
        )
        returned_four = (
            quadruples[:max_higher_factor_contacts]
            if max_higher_factor_contacts is not None
            else quadruples
        )
        dials[str(period)] = {
            "period_degrees": period,
            "two_factor_contacts": doubles,
            "three_factor_contacts": returned_three,
            "three_factor_returned_count": len(returned_three),
            "three_factor_total_count": total_three,
            "four_factor_contacts": returned_four,
            "four_factor_returned_count": len(returned_four),
            "four_factor_total_count": total_four,
        }
    unique_pairs = {
        (row["id_a"], row["id_b"])
        for dial in dials.values()
        for row in dial["two_factor_contacts"]
    }
    output: dict[str, Any] = {
        "midpoint_axes": catalogue,
        "dials": dials,
        "unique_two_factor_pair_count": len(unique_pairs),
    }
    if sensitive_point_query:
        output["sensitive_point_query"] = _evaluate_sensitive_point_query(
            sensitive_point_query, points, periods, orb
        )
    return output


def _native_factors(
    birth: AstroBirthInfo,
    sidereal: bool,
    *,
    include_hypothetical: bool = True,
    include_meridian_houses: bool = False,
    epoch: PhysicalEpoch | None = None,
) -> dict[str, Any]:
    swe = runtime.swe
    if swe is None:
        raise ValueError("Native midpoint factors require Swiss Ephemeris")
    times = epoch.time if epoch is not None else birth.time_scales
    tt = times.tt
    if tt is None:
        raise ValueError("Native midpoint factors require dynamical TT")
    jd_tt, jd_ut1 = tt.as_float(), times.ut1
    factors = []
    meridian_inputs = []
    models = set()
    trace = PhysicalEphemerisTrace()
    with runtime.preserve_ephemeris_path():
        fast_swe_call("set_sid_mode", swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | (swe.FLG_SIDEREAL if sidereal else 0)
        selected_hypotheticals = HYPOTHETICAL_BODIES if include_hypothetical else ()
        for name in (*PHYSICAL_BODIES, "North Node", *selected_hypotheticals):
            hypothetical = name in HYPOTHETICAL_BODIES
            body_id = (
                40 + HYPOTHETICAL_BODIES.index(name)
                if hypothetical
                else (
                    swe.MEAN_NODE
                    if name == "North Node"
                    else getattr(swe, name.upper())
                )
            )
            try:
                coords, flag = fast_swe_call("calc", jd_tt, body_id, flags)
            except swe.Error as error:
                raise EphemerisCalculationError(
                    "Native ephemeris factor calculation failed"
                ) from error
            if flag < 0 or not math.isfinite(coords[0]):
                raise ValueError(
                    f"Swiss Ephemeris cannot calculate midpoint factor {name}"
                )
            if name in PHYSICAL_BODIES:
                model = runtime.ephemeris_model_from_retflag(flag)
                models.add(model)
                trace.observe(name, model)
            element_name = None
            if hypothetical:
                element_name = swe.get_planet_name(body_id)
                allowed_names = (
                    {"vulkanus", "vulcanus"}
                    if name == "Vulkanus"
                    else {name.casefold()}
                )
                if element_name.strip().casefold() not in allowed_names:
                    raise EphemerisSourceError("fictitious_identity")
            factors.append(
                {
                    "id": name,
                    "longitude": float(coords[0]) % 360,
                    "kind": (
                        "hypothetical"
                        if hypothetical
                        else "lunar_node" if name == "North Node" else "physical_body"
                    ),
                    "model": (
                        "swisseph_fictitious_elements"
                        if hypothetical
                        else native_factor_model(body_id, flag)
                    ),
                    **({"element_name": element_name} if hypothetical else {}),
                }
            )
            if include_meridian_houses:
                meridian_inputs.append(
                    {
                        **{
                            key: factors[-1][key]
                            for key in ("id", "longitude", "kind", "model")
                        },
                        "latitude": float(coords[1]),
                    }
                )
        reference_house_code = b"E"
        reference_house_flags = swe.FLG_SIDEREAL if sidereal else 0
        _, angles = fast_swe_call(
            "houses_ex",
            jd_ut1,
            birth.latitude,
            birth.longitude,
            reference_house_code,
            reference_house_flags,
            _julian_day_tt=tt,
        )
        angles, _ = canonical_house_axes(
            julian_day_ut1=jd_ut1,
            julian_day_tt=tt,
            latitude=birth.latitude,
            longitude=birth.longitude,
            house_code=reference_house_code,
            native_angles=angles,
            flags=reference_house_flags,
        )
        pole_frame = (
            terrestrial_frame(
                physical_equator(runtime.swe, jd_ut1, julian_day_tt=tt),
                longitude=birth.longitude,
                latitude=birth.latitude,
            )
            if abs(birth.latitude) == 90 and active_ut1.get() is not None
            else None
        )
        angle_definition = geographic_pole_angle_definition(
            birth.latitude, frame=pole_frame
        ) or (
            native_ecliptic_horizon_angle_definition(
                julian_day_ut1=jd_ut1,
                julian_day_tt=tt,
                latitude=birth.latitude,
                longitude=birth.longitude,
                armc=float(angles[2]),
            )
        )
        if sidereal:
            ayan_flag, ayan = fast_swe_call("get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH)
            if ayan_flag < 0:
                raise ValueError("Swiss Ephemeris cannot calculate Lahiri ayanamsha")
        else:
            ayan = 0.0
        for name, longitude in (
            ("Ascendant", angles[0]),
            ("Midheaven", angles[1]),
            ("Aries Point", -ayan),
        ):
            factors.append(
                {
                    "id": name,
                    "longitude": float(longitude) % 360,
                    "kind": "reference_point",
                    "model": "swisseph_geometry",
                    **(
                        {
                            "coordinate_basis": basis,
                            "angle_definition": angle_definition,
                        }
                        if (basis := reference_angle_basis(angle_definition, name))
                        else {}
                    ),
                }
            )
        meridian = (
            native_meridian_houses(
                julian_day_ut1=jd_ut1,
                julian_day_tt=tt,
                latitude=birth.latitude,
                longitude=birth.longitude,
                sidereal=sidereal,
                physical_angles=angles,
            )
            if include_meridian_houses
            else None
        )
        if meridian is not None:
            attach_factor_placement(
                meridian, meridian_inputs, factor_ayanamsha=float(ayan)
            )
    return {
        "factors": factors,
        **({"angle_definition": angle_definition} if angle_definition else {}),
        "ephemeris_models": sorted(models),
        "physical_ephemeris_source": trace.finish(),
        "julian_day_tt": jd_tt,
        "julian_day_ut1": jd_ut1.as_float(),
        **({"meridian_houses": meridian} if include_meridian_houses else {}),
    }


def build_midpoint_analysis(
    birth: AstroBirthInfo,
    base: dict[str, Any],
    *,
    dial_degrees: str | None = None,
    sensitive_point_query: str | None = None,
    max_higher_factor_contacts: int | None = 12,
) -> dict[str, Any]:
    """Native Hamburg midpoint geometry without prose bloat."""
    sidereal = base["chart_profile"]["zodiac"] == "sidereal"
    if runtime.swe is None:
        return {
            "status": "unavailable",
            "ruleset_id": RULESET,
            "reason": "Swiss Ephemeris is required for native unrounded factors",
            "meridian_houses": unavailable_meridian_houses(),
        }
    native = _native_factors(birth, sidereal, include_meridian_houses=False)
    result = midpoint_geometry(
        {row["id"]: row["longitude"] for row in native["factors"]},
        dial_degrees=dial_degrees,
        sensitive_point_query=sensitive_point_query,
        max_higher_factor_contacts=max_higher_factor_contacts,
    )
    qualify_reference_geometry(result, native.get("angle_definition"))
    for row in result["midpoint_axes"]:
        row["contains_hypothetical"] = any(
            row[key] in HYPOTHETICAL_BODIES for key in ("id_a", "id_b")
        )
    counts = {}
    for dial, data in result["dials"].items():
        for field in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            for row in data[field]:
                row["contains_hypothetical"] = any(
                    value in HYPOTHETICAL_BODIES
                    for key, value in row.items()
                    if key in {"point", "id_a", "id_b", "id_c", "id_d"}
                )
        counts[dial] = {
            "two_factor": len(data["two_factor_contacts"]),
            "three_factor": data.get(
                "three_factor_total_count", len(data["three_factor_contacts"])
            ),
            "four_factor": data.get(
                "four_factor_total_count", len(data["four_factor_contacts"])
            ),
        }
    return {
        "status": "computed",
        "ruleset_id": RULESET,
        "version": "3",
        "profile": {
            "zodiac": "sidereal_lahiri" if sidereal else "tropical",
            "orb_degrees": 1.0,
            "dial_degrees": dial_degrees or "90_45",
            "factor_count": len(native["factors"]),
            **{
                key: value
                for key, value in native.items()
                if key not in {"factors", "meridian_houses"}
            },
        },
        "factors": native["factors"],
        **result,
        "contact_counts": counts,
    }
