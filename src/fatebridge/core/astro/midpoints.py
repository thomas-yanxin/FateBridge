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
from typing import Any, Dict, Mapping

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    geographic_pole_angle_definition,
    native_ecliptic_horizon_angle_definition,
)
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.fictitious_elements import fictitious_element_source
from fatebridge.core.astro.meridian_houses import (
    native_meridian_houses,
    unavailable_meridian_houses,
)
from fatebridge.core.astro.meridian_placement import attach_factor_placement
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.reference_angles import (
    qualify_reference_geometry,
    reference_angle_basis,
)
from fatebridge.core.astro.sensitive import SOURCE as SENSITIVE_SOURCE
from fatebridge.core.astro.sensitive import (
    original_example_reading,
    sensitive_equivalence,
)
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "hamburg_midpoint_geometry_v3"
PHYSICAL_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)
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
SOURCES: list[Dict[str, Any]] = [
    SENSITIVE_SOURCE,
    {
        "id": "rudolph_1979_17laws",
        "author": "Ludwig Rudolph",
        "title": "17 Gesetze fuer Planetenbilder, Hamburger Hefte 1979/2, no.74, p.1, article 823",
        "url": "https://www.witte-verlag.com/hamburger-hefte-menu/datenbank/823.html",
        "sections": ["3", "7", "13", "14", "15", "16"],
        "scope": "Geometric propositions only; not adoption of interpretive or empirical claims",
    },
    {
        "id": "witte_instruments",
        "author": "Witte-Verlag Hamburg",
        "title": "Arbeitsgeraete: 360, 90 and 45 degree dials and midpoint ruler",
        "url": "https://witte-verlag.com/produkte/arbeitsmittel.html",
        "scope": "Published dial instruments; not the full interpretation rulebook",
    },
    {
        "id": "swiss_programmer",
        "author": "Astrodienst AG",
        "title": "Swiss Ephemeris Programmer's Manual",
        "url": "https://www.astro.com/swisseph/swephprg.htm",
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
        "url": "https://www.astro.com/swisseph/swisseph.pdf",
        "scope": "James Neely revised mathematical elements; no observed physical bodies",
    },
]


def _angle(value: float) -> Fraction:
    if not math.isfinite(value):
        raise ValueError("Midpoint coordinates must be finite")
    return Fraction(value) % 360


def midpoint_axis(first: float, second: float) -> Dict[str, Any]:
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


def _residual(first: Fraction, second: Fraction, period: int) -> Fraction:
    return (first - second + Fraction(period, 2)) % period - Fraction(period, 2)


def midpoint_geometry(
    longitudes: Mapping[str, float], *, orb_degrees: float = 1.0
) -> Dict[str, Any]:
    """Both dial geometries; fixed, inclusive one-degree policy by default.

    Two-factor contacts use each unordered pair once per dial. Three-factor
    contacts require three distinct factors; four-factor contacts require four.
    Self midpoints remain in the catalogue, but algebraic identities and reduced
    contacts cannot inflate the three/four-factor counts.
    No contact count or orb is a probability or a measure of personal ability.
    """
    if not math.isfinite(orb_degrees) or not 0 <= orb_degrees <= 5:
        raise ValueError("Midpoint orb must be within 0..5 degrees")
    points = {name: _angle(value) for name, value in longitudes.items()}
    axes = []
    catalogue = []
    for a, b in combinations_with_replacement(points, 2):
        axis = ((points[a] + points[b]) / 2) % 180
        axes.append((a, b, axis))
        catalogue.append(
            {
                "id_a": a,
                "id_b": b,
                **midpoint_axis(longitudes[a], longitudes[b]),
                "self_midpoint": a == b,
                "rule_id": "hamburg.midpoint_axis.v1",
            }
        )
    orb = Fraction(orb_degrees)
    dials: Dict[str, Dict[str, Any]] = {}
    for period in (90, 45):
        doubles, triples, quadruples = [], [], []
        for a, b in combinations(sorted(points), 2):
            difference = points[a] - points[b]
            delta = _residual(points[a], points[b], period)
            if abs(delta) <= orb:
                # A-B is an oriented full-circle difference. Keep its nearest
                # dial multiple separate from the actual smaller separation:
                # a folded match is not necessarily a conjunction.
                offset = int((difference - delta) % 360)
                doubles.append(
                    {
                        "id_a": a,
                        "id_b": b,
                        "equation": f"{a}={b}",
                        "orb": float(abs(delta)),
                        "signed_orb": float(delta),
                        "factor_offset_degrees": offset,
                        "aspect_degrees": min(offset, 360 - offset),
                        "separation_degrees": float(
                            abs(_residual(points[a], points[b], 360))
                        ),
                        "rule_id": "hamburg.two_factor_hard_contacts.v1",
                    }
                )
        for a, b, axis in axes:
            if a == b:
                continue
            for point, value in points.items():
                if point in (a, b):
                    continue
                delta = _residual(value, axis, period)
                if abs(delta) <= orb:
                    triples.append(
                        {
                            "point": point,
                            "id_a": a,
                            "id_b": b,
                            "equation": f"{point}={a}/{b}",
                            "orb": float(abs(delta)),
                            "signed_orb": float(delta),
                            "axis_offset_degrees": int(
                                (round((value - axis) / period) * period) % 180
                            ),
                            "rule_id": "hamburg.three_factor_symmetry.v1",
                        }
                    )
        for (a, b, left), (c, d, right) in combinations(axes, 2):
            if len({a, b, c, d}) != 4:
                continue
            delta = _residual(left, right, period)
            if abs(delta) <= orb:
                quadruples.append(
                    {
                        "id_a": a,
                        "id_b": b,
                        "id_c": c,
                        "id_d": d,
                        "equation": f"{a}/{b}={c}/{d}",
                        "orb": float(abs(delta)),
                        "signed_orb": float(delta),
                        "axis_offset_degrees": int(
                            (round((left - right) / period) * period) % 180
                        ),
                        "rule_id": "hamburg.four_factor_symmetry.v1",
                        "sensitive_point": sensitive_equivalence(
                            a, b, c, d, points, midpoint_period=period, midpoint_orb=orb
                        ),
                        **(
                            {"source_interpretation": reading}
                            if (
                                reading := original_example_reading(
                                    a, b, c, d, points, axis_orb=orb
                                )
                            )
                            is not None
                            else {}
                        ),
                    }
                )
        for contacts in (doubles, triples, quadruples):
            contacts.sort(key=lambda row: (row["orb"], row["equation"]))
        dials[str(period)] = {
            "period_degrees": period,
            "two_factor_contacts": doubles,
            "three_factor_contacts": triples,
            "four_factor_contacts": quadruples,
        }
    unique_pairs = {
        (row["id_a"], row["id_b"])
        for dial in dials.values()
        for row in dial["two_factor_contacts"]
    }
    return {
        "midpoint_axes": catalogue,
        "dials": dials,
        "unique_two_factor_pair_count": len(unique_pairs),
    }


def _native_factors(
    birth: AstroBirthInfo,
    sidereal: bool,
    *,
    include_hypothetical: bool = True,
    include_meridian_houses: bool = False,
) -> Dict[str, Any]:
    swe = runtime.swe
    if swe is None:
        raise ValueError("Native midpoint factors require Swiss Ephemeris")
    times = ephemeris_time(birth.require_utc_datetime)
    if times.jd_tt is None:
        raise ValueError("Native midpoint factors require dynamical TT")
    jd_tt, jd_ut1 = times.jd_tt, times.jd_ut1
    factors = []
    meridian_inputs = []
    models = set()
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        physical_trace = PhysicalEphemerisTrace()
        element_source = (
            fictitious_element_source()
            if include_hypothetical
            else {
                "status": "not_used",
                "filename": None,
                "sha256": None,
                "scope": "Physical/reference factor probe; no fictitious orbit elements read",
            }
        )
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0.0, 0.0)
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
            coords, flag = runtime.ephemeris_call("calc", jd_tt, body_id, flags)
            if flag < 0 or not math.isfinite(coords[0]):
                raise ValueError(
                    f"Swiss Ephemeris cannot calculate midpoint factor {name}"
                )
            if name in PHYSICAL_BODIES:
                models.add(runtime.ephemeris_model_from_retflag(flag))
            if name in PHYSICAL_BODIES:
                physical_trace.observe(name, runtime.ephemeris_model_from_retflag(flag))
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
                    **(
                        {"native_return_flags": int(flag)}
                        if name == "North Node"
                        else {}
                    ),
                }
            )
            if include_meridian_houses:
                if (
                    len(coords) < 2
                    or isinstance(coords[1], bool)
                    or not isinstance(coords[1], (int, float))
                    or not math.isfinite(coords[1])
                    or not -90 <= coords[1] <= 90
                ):
                    raise RuntimeError(
                        "Native meridian factor has no valid ecliptic latitude"
                    )
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
        _, angles = runtime.ephemeris_call(
            "houses_ex",
            jd_ut1,
            birth.latitude,
            birth.longitude,
            reference_house_code,
            reference_house_flags,
        )
        angle_definition = geographic_pole_angle_definition(birth.latitude) or (
            native_ecliptic_horizon_angle_definition(
                julian_day_ut1=jd_ut1, latitude=birth.latitude, armc=float(angles[2])
            )
        )
        # Aries Point is the tropical equinox, including in a sidereal display.
        # Treating it as sidereal 0 would change its physical reference point.
        if sidereal:
            ayan_flag, ayan = runtime.ephemeris_call(
                "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
            )
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
                julian_day_tt=jd_tt,
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
        if include_hypothetical and fictitious_element_source() != element_source:
            raise EphemerisSourceError("fictitious_changed_during")
        physical_source = physical_trace.finish()
    return {
        "factors": factors,
        "reference_angle_model": {
            "house_code": reference_house_code.decode("ascii"),
            "house_flags": int(reference_house_flags),
            "cusp_output_used": False,
            "role": "reference_angles_only",
            "used_reference_outputs": ["Ascendant", "Midheaven", "ARMC"],
        },
        **({"angle_definition": angle_definition} if angle_definition else {}),
        "ephemeris_models": sorted(models),
        "ephemeris_model_scope": "physical_bodies",
        "julian_day_tt": jd_tt,
        "julian_day_ut1": jd_ut1,
        "julian_day_utc": times.jd_utc,
        "time_scale_method": times.method,
        "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
        "swisseph_version": str(swe.version),
        "hypothetical_element_source": element_source,
        "physical_ephemeris_source": physical_source,
        **({"meridian_houses": meridian} if include_meridian_houses else {}),
    }


def build_midpoint_analysis(
    birth: AstroBirthInfo, base: Dict[str, Any]
) -> Dict[str, Any]:
    """A native geometry layer beside the retained seven-planet legacy view."""
    sidereal = base["chart_profile"]["zodiac"] == "sidereal"
    if runtime.swe is None:
        return {
            "status": "unavailable",
            "ruleset_id": RULESET,
            "reason": "Swiss Ephemeris is required for native unrounded factors",
            "meridian_houses": unavailable_meridian_houses(),
            "sources": SOURCES,
            "real_world_efficacy": "not_tested",
        }
    native = _native_factors(birth, sidereal, include_meridian_houses=True)
    result = midpoint_geometry(
        {row["id"]: row["longitude"] for row in native["factors"]}
    )
    qualify_reference_geometry(result, native.get("angle_definition"))
    for row in result["midpoint_axes"]:
        row["contains_hypothetical"] = any(
            row[key] in HYPOTHETICAL_BODIES for key in ("id_a", "id_b")
        )
    counts = {}
    interpretations = {}
    for dial, data in result["dials"].items():
        for field in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            for row in data[field]:
                if "source_interpretation" in row:
                    reading = row["source_interpretation"]
                    interpretations[reading["claim_id"]] = reading
                row["contains_hypothetical"] = any(
                    value in HYPOTHETICAL_BODIES
                    for key, value in row.items()
                    if key in {"point", "id_a", "id_b", "id_c", "id_d"}
                )
        counts[dial] = {
            "two_factor": len(data["two_factor_contacts"]),
            "three_factor": len(data["three_factor_contacts"]),
            "four_factor": len(data["four_factor_contacts"]),
        }
    return {
        "status": "computed",
        "ruleset_id": RULESET,
        "version": "3",
        "profile": {
            "zodiac": "sidereal_lahiri" if sidereal else "tropical",
            "calendar": "proleptic_gregorian",
            "time_scale": "shared ephemeris_time: TT for factors, estimated UT1 for angles; future leap assumption reported",
            "orb_degrees": 1.0,
            "orb_policy": "inclusive; implementation choice, not a unique original rule",
            "coordinate_rounding_before_comparison": False,
            "factor_count": len(native["factors"]),
            "contact_policy": "two distinct factors per unordered pair / three distinct factors / four distinct factors; self midpoints catalogued only; cross-dial pair duplicates counted once in unique_two_factor_pair_count",
            "hypothetical_model": "Swiss Ephemeris fictitious elements; external seorbel.txt may override defaults",
            "aries_point": "tropical equinox transformed to the selected display zodiac",
            "node_mode": "mean",
            "legacy_view": "top-level midpoints/midpoint_aspects: seven-planet 360-degree view from unrounded coordinates",
            "sensitive_point_policy": "midpoint period/orb multiplied by two in sum form; full-circle direct occupancy assessed separately",
            **{
                key: value
                for key, value in native.items()
                if key not in {"factors", "meridian_houses"}
            },
        },
        "meridian_houses": native["meridian_houses"],
        "factors": native["factors"],
        **result,
        "contact_counts": counts,
        "interpretations": [interpretations[key] for key in sorted(interpretations)],
        "reading_guide": {
            "axis": "A/B 是两个因素的中点轴；轴线两端相隔180度，不能把端点选择当成另一组独立证据。",
            "two_factor": "A=B 表示两个不同因素在所选折叠度盘上接近；aspect_degrees 是最接近的0/45/90/135/180度硬相位，separation_degrees 是原始圆上的实际较小夹角，不能把折叠重合都叫合相。factor_offset_degrees 表示 A-B 方向的最近度盘倍数；unique_two_factor_pair_count 跨两盘按因素对去重，不是独立预测证据数。",
            "three_factor": "C=A/B 表示 C 在所选折叠度盘上接近 A/B 轴；90度盘合并四分相位，45度盘还合并八分相位。",
            "four_factor": "A/B=C/D 表示两条中点轴在所选度盘上接近；本版本仅统计四个不同因素。",
            "orb": "orb 是几何偏差的度数，越小仅表示越接近对称式；命中数量和偏差均不是吉凶分数或事件概率。",
            "sensitive_point": "敏感点 A+B-C=D 与 A/B=C/D 等价时，周期与容许度均需乘二；folded_only 不表示原始360度圆上的直接占据。只有实际匹配的原书示例才返回其限定象征解释。",
            "meridian_houses": "meridian_houses 是 Witte 1923 赤经等分的本命宫头几何；第一宫宫头为赤道上升点，不代替 factors 中的实际上升点或 base_chart 的宫制。它不提供完整推运钥匙或事件解释。",
        },
        "rulesets": [
            {
                "id": RULESET,
                "version": "3",
                "author": "FateBridge",
                "source_ids": [row["id"] for row in SOURCES],
            }
        ],
        "sources": SOURCES,
        "rule_trace": [
            {
                "rule_id": "hamburg.sensitive_point_equivalence.v1",
                "source_id": SENSITIVE_SOURCE["id"],
                "source_sections": ["printed p.14"],
                "formula": "A+B-C=D modulo 2*P; sum orb=2*midpoint orb; full-circle direct occupancy kept distinct",
                "scope": "equivalence of computed four-factor contacts; no event activation inferred",
            },
            {
                "rule_id": "hamburg.udo1996.symbolic_example.v1",
                "source_id": SENSITIVE_SOURCE["id"],
                "source_sections": ["printed p.14"],
                "formula": "Mars+Jupiter-Zeus=Midheaven; Midheaven/Zeus=Mars/Jupiter",
                "scope": "source-authored symbolic example only; requires direct full-circle occupancy under stated implementation orb",
            },
            {
                "rule_id": "hamburg.midpoint_axis.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["3"],
                "formula": "2*axis = A+B modulo 360; axis represented modulo 180",
                "scope": "geometry",
            },
            {
                "rule_id": "hamburg.two_factor_hard_contacts.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["13", "16"],
                "formula": "A=B modulo selected dial period; oriented A-B offset retained modulo 360; smaller full-circle separation reported separately",
                "scope": "geometry; two distinct factors, one unordered pair per dial; fixed implementation orb; reference and hypothetical factors explicitly identified",
            },
            {
                "rule_id": "hamburg.three_factor_symmetry.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["13", "14", "16"],
                "formula": "C=(A+B)/2 modulo selected dial period",
                "scope": "geometry; three distinct factors; fixed implementation orb",
            },
            {
                "rule_id": "hamburg.four_factor_symmetry.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["3", "15", "16"],
                "formula": "(A+B)/2=(C+D)/2 modulo selected dial period",
                "scope": "geometry; four distinct factors; fixed implementation orb",
            },
            {
                "rule_id": "hamburg.aries_point.v1",
                "source_id": "rudolph_1979_17laws",
                "source_sections": ["7"],
                "formula": "tropical equinox, transformed with all other factors when the display zodiac changes",
                "scope": "reference-point identity",
            },
        ],
        "limitations": [
            "Geometric subset plus one attributed symbolic example; full original Rules for Planetary Pictures and interpretive keywords have not been audited",
            "Hypothetical factors are mathematical constructions, not observed celestial bodies or JPL-validated planets",
            "The selected 1923 natal meridian-house geometry does not implement all Hamburg house systems, a complete progression time key or validated event forecasts",
            "1961-1971 UTC uses IERS rate/offset changes; earlier input is treated as UT1; birth-location and birth-time uncertainty are not assessed",
        ],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
    }
