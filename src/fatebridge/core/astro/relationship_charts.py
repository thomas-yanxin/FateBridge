"""Derived chart assembly for composite, timespace, influence and marks modes."""

from __future__ import annotations

import math
from typing import Any, Literal

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.ephemeris import fast_swe_call
from fatebridge.core.astro.geometry import _sign_name, normalize_angle
from fatebridge.core.astro.layout import (
    _house_cusp_values_from_payload,
    _midpoint_house_cusps,
)
from fatebridge.core.astro.parts import _balance, _build_houses, _build_planet_record
from fatebridge.core.astro.profiles import (
    _derive_engine_profile,
    _precision_label_zh,
    _relative_zodiac_profile_overrides,
)
from fatebridge.core.astro.reference import BALANCE_BASIS, PLANET_SEQUENCE
from fatebridge.core.astro.relationship_geometry import (
    davison_birth,
    marks_birth,
    unique_midpoint,
)
from fatebridge.utils.errors import EphemerisSourceError


def chart_angle(longitude_degrees: float) -> dict[str, float | str]:
    sign = _sign_name(longitude_degrees)
    return {
        "longitude": longitude_degrees,
        "sign": sign,
        "sign_zh": SIGN_LABELS_ZH[sign],
    }


def _composite_chart(
    inner_chart: dict[str, Any],
    outer_chart: dict[str, Any],
    *,
    house_system: str,
    zodiacal_info: dict[str, Any],
    composite_house_method: str = "midpoint",
    midpoint_latitude: float | None = None,
) -> dict[str, Any]:
    engine_profile = _derive_engine_profile(
        inner_chart.get("chart_profile", {}),
        outer_chart.get("chart_profile", {}),
    )
    is_inner_ascendant_resolved = is_ascendant_resolved(inner_chart)
    is_outer_ascendant_resolved = is_ascendant_resolved(outer_chart)
    are_both_ascendants_resolved = (
        is_inner_ascendant_resolved and is_outer_ascendant_resolved
    )
    are_houses_ascendant_dependent = house_system != "equal_mc"

    inner_planets = {item["id"]: item for item in inner_chart["planets"]}
    outer_planets = {item["id"]: item for item in outer_chart["planets"]}

    inner_mc = (inner_chart.get("angles") or {}).get("midheaven", {}).get("longitude")
    outer_mc = (outer_chart.get("angles") or {}).get("midheaven", {}).get("longitude")
    midheaven = (
        unique_midpoint(inner_mc, outer_mc)
        if inner_mc is not None and outer_mc is not None
        else None
    )
    ascendant = (
        unique_midpoint(
            inner_chart["angles"]["ascendant"]["longitude"],
            outer_chart["angles"]["ascendant"]["longitude"],
        )
        if are_both_ascendants_resolved
        else None
    )
    are_houses_resolved = (
        are_both_ascendants_resolved or not are_houses_ascendant_dependent
    ) and (are_both_ascendants_resolved or midheaven is not None)
    house_cusps: list[float] = []
    if (
        composite_house_method == "mc_latitude"
        and midheaven is not None
        and midpoint_latitude is not None
        and runtime.swe is not None
        and abs(midpoint_latitude) < 90.0
    ):
        eps_rad = math.radians(23.43929)
        mc_rad = math.radians(midheaven)
        armc = (
            math.degrees(
                math.atan2(math.sin(mc_rad) * math.cos(eps_rad), math.cos(mc_rad))
            )
            % 360.0
        )
        code_map = {
            "whole_sign": b"W",
            "alcabitus": b"B",
            "regiomontanus": b"R",
            "placidus": b"P",
            "koch": b"K",
            "vehlow_equal": b"V",
            "polich_page": b"T",
            "sripati": b"S",
            "equal_mc": b"D",
            "equal": b"E",
        }
        h_code = code_map.get(house_system, b"P")
        try:
            cusps_raw, ascmc_raw = fast_swe_call(
                "houses_armc", armc, midpoint_latitude, math.degrees(eps_rad), h_code
            )
            ascendant = normalize_angle(float(ascmc_raw[0]))
            house_cusps = (
                []
                if house_system == "whole_sign"
                else [normalize_angle(float(c)) for c in cusps_raw[:12]]
            )
            are_houses_resolved = True
            are_both_ascendants_resolved = True
        except EphemerisSourceError:
            raise
        except runtime.native_ephemeris_errors() as error:
            runtime._log_swe_runtime_failure("houses_armc(composite)", error)
            house_cusps = []
    if not house_cusps and are_houses_resolved and house_system != "whole_sign":
        house_cusps = _midpoint_house_cusps(
            _house_cusp_values_from_payload(inner_chart),
            _house_cusp_values_from_payload(outer_chart),
        )
    planet_asc_anchor = ascendant if ascendant is not None else 0.0
    sun_comp_lon: float | None = None
    if "Sun" in inner_planets and "Sun" in outer_planets:
        sun_comp_lon = unique_midpoint(
            inner_planets["Sun"]["longitude"],
            outer_planets["Sun"]["longitude"],
        )
    composite_planets: list[dict[str, Any]] = []
    for planet in PLANET_SEQUENCE:
        if planet not in inner_planets or planet not in outer_planets:
            continue
        lon_a = inner_planets[planet]["longitude"]
        lon_b = outer_planets[planet]["longitude"]
        antipodal = abs((lon_b - lon_a) % 360.0 - 180.0) < 1e-9
        longitude = unique_midpoint(lon_a, lon_b)
        flipped_elongation = False
        if planet in ("Mercury", "Venus") and sun_comp_lon is not None:
            sep = abs(math.remainder(longitude - sun_comp_lon, 360.0))
            if sep > 90.0:
                longitude = normalize_angle(longitude + 180.0)
                flipped_elongation = True
        record = _build_planet_record(
            planet,
            longitude,
            (inner_planets[planet]["latitude"] + outer_planets[planet]["latitude"])
            / 2.0,
            planet_asc_anchor,
            house_system if are_houses_resolved else "whole_sign",
            house_cusps=house_cusps or None,
            houses_resolved=are_houses_resolved,
        )
        if antipodal:
            record["antipodal_midpoint"] = True
        if flipped_elongation:
            record["flipped_for_sun_elongation"] = True
        composite_planets.append(record)
    aspect_evidence = _build_aspects(composite_planets, include_evidence=True)
    aspects = [
        {key: row[key] for key in ("planet_a", "planet_b", "aspect", "orb")}
        for row in aspect_evidence
    ]
    house_policy = (
        "whole_sign_from_composite_ASC"
        if are_houses_resolved and house_system == "whole_sign"
        else (
            "corresponding_cusp_short_arc_midpoints"
            if are_houses_resolved
            else "omitted_due_to_unresolved_ascendant"
        )
    )
    chart_profile: dict[str, Any] = {
        "chart_type": "composite",
        "aspect_policy": inner_chart.get("chart_profile", {}).get("aspect_policy"),
        "tradition": inner_chart.get("chart_profile", {}).get("tradition", False),
        "house_system": house_system,
        "house_system_code": inner_chart.get("chart_profile", {}).get(
            "house_system_code"
        ),
        "house_system_label_zh": inner_chart.get("chart_profile", {}).get(
            "house_system_label_zh"
        ),
        **_relative_zodiac_profile_overrides(zodiacal_info),
        **engine_profile,
        "derivation_policy": {
            "method_id": "composite_corresponding_midpoints_v2",
            "source_kind": "first_party_implementation_documentation",
            "positions_from_single_instant": False,
            "longitude_policy": "unique shorter arc; exact diametric inputs are ambiguous",
            "latitude_policy": "symbolic arithmetic mean; not observed latitude",
            "house_policy": house_policy,
            "mercury_venus_policy": "no automatic 180-degree relocation",
        },
    }
    summary = [
        f"已生成 FateBridge 组合盘{_precision_label_zh(engine_profile['engine_precision'])}层。",
        f"行星数量：{len(composite_planets)}。",
        f"相位数量：{len(aspects)}。",
    ]
    if not are_both_ascendants_resolved:
        chart_profile.update(
            ascendant_resolved=False,
            ascendant_status="underdetermined_ascendant",
            inner_ascendant_resolved=is_inner_ascendant_resolved,
            outer_ascendant_resolved=is_outer_ascendant_resolved,
        )
        summary.append(
            "因参与方上升点未解析，组合盘未计算 ASC 及依赖 ASC 的宫位。"
            if not are_houses_resolved
            else "因参与方上升点未解析，组合盘未计算 ASC；已保留基于天顶（MC）的等宫宫位。"
        )
    result: dict[str, Any] = {
        "person_info": {
            "name": f"{inner_chart['person_info']['name']} / {outer_chart['person_info']['name']} 组合盘",
            "birth_place": f"{inner_chart['person_info']['birth_place']} / {outer_chart['person_info']['birth_place']}",
            "birth_timezone": inner_chart["person_info"]["birth_timezone"],
        },
        "chart_profile": chart_profile,
        "angles": {
            "ascendant": (
                chart_angle(ascendant)
                if ascendant is not None
                else {
                    "longitude": None,
                    "sign": None,
                    "sign_zh": None,
                    "status": "underdetermined_ascendant",
                }
            ),
            "midheaven": (
                chart_angle(midheaven)
                if midheaven is not None
                else {
                    "longitude": None,
                    "sign": None,
                    "sign_zh": None,
                    "status": "unavailable",
                }
            ),
        },
        "houses": (
            _build_houses(
                planet_asc_anchor,
                house_system,
                house_cusps=house_cusps or None,
                midheaven=midheaven,
            )
            if are_houses_resolved
            else []
        ),
        "planets": composite_planets,
        "aspects": aspects,
        "aspect_evidence": aspect_evidence,
        "element_balance": _balance(composite_planets, "element"),
        "modality_balance": _balance(composite_planets, "modality"),
        "balance_basis": BALANCE_BASIS,
        "summary": summary,
    }
    if not are_both_ascendants_resolved:
        result.update(
            status="underdetermined_ascendant",
            ascendant_resolved=False,
            unavailable_reason="unresolved_source_ascendant",
        )
    return result


def _build_relative_base_chart(
    birth_info: AstroBirthInfo,
    *,
    house_system_info: dict[str, Any],
    zodiacal_info: dict[str, Any],
    high_latitude_fallback: str = "error",
) -> dict[str, Any]:
    base_chart = build_core_chart_payload(
        birth_info,
        "chart",
        hsys=house_system_info["value"],
        zodiacal=zodiacal_info["value"],
        include_planetary_hours=False,
        high_latitude_fallback=high_latitude_fallback,
    )
    # note (recast): A derived event uses the same native zodiac, houses, and time basis as a natal chart.
    return {
        key: base_chart[key]
        for key in (
            "person_info",
            "chart_profile",
            "angles",
            "houses",
            "planets",
            "aspects",
            "aspect_evidence",
            "element_balance",
            "modality_balance",
            "balance_basis",
            "summary",
        )
    }


def planet_display_order(item: dict[str, Any]) -> tuple[int, int | str]:
    planet_id: str = item["id"]
    if planet_id in PLANET_SEQUENCE:
        return (0, PLANET_SEQUENCE.index(planet_id))
    return (1, planet_id)


def _build_timespace_chart(
    inner_birth: AstroBirthInfo,
    outer_birth: AstroBirthInfo,
    *,
    house_system_info: dict[str, Any],
    zodiacal_info: dict[str, Any],
    davison_variant: str = "uncorrected",
) -> dict[str, Any]:
    midpoint_birth, policy = davison_birth(
        inner_birth, outer_birth, variant=davison_variant
    )
    midpoint_chart = _build_relative_base_chart(
        midpoint_birth,
        house_system_info=house_system_info,
        zodiacal_info=zodiacal_info,
    )
    midpoint_chart["chart_profile"].update(
        chart_type="timespace", derivation_policy=policy
    )
    midpoint_chart["summary"] = [f"已生成 FateBridge 时空中点盘（{davison_variant}）。"]
    return midpoint_chart


def _build_influence_chart_wrapper(
    *,
    role: Literal["inner", "outer"],
    house_chart: dict[str, Any],
    source_chart: dict[str, Any],
    house_system: str,
    zodiacal_info: dict[str, Any],
) -> dict[str, Any]:
    target_profile = house_chart["chart_profile"]
    ascendant_resolved = is_ascendant_resolved(house_chart)
    house_system_code = target_profile["house_system_code"]
    houses_resolved = ascendant_resolved or house_system == "equal_mc"

    engine_profile = _derive_engine_profile(
        target_profile, source_chart["chart_profile"]
    )
    target_name = house_chart["person_info"]["name"]
    source_name = source_chart["person_info"]["name"]
    ascendant = house_chart["angles"]["ascendant"]["longitude"]
    midheaven = house_chart["angles"]["midheaven"]["longitude"]
    house_cusps = (
        None
        if house_system == "whole_sign"
        else _house_cusp_values_from_payload(house_chart)
    )
    planets = [
        _build_planet_record(
            planet["id"],
            planet["longitude"],
            planet["latitude"],
            ascendant,
            house_system,
            house_cusps=house_cusps,
        )
        for planet in sorted(source_chart["planets"], key=planet_display_order)
    ]
    if not houses_resolved:
        for planet in planets:
            planet["house"] = None
    aspect_evidence = _build_aspects(planets, include_evidence=True)
    aspects = [
        {field: contact[field] for field in ("planet_a", "planet_b", "aspect", "orb")}
        for contact in aspect_evidence
    ]
    chart_type = f"influence_{role}"
    reference_frame = f"{source_name}_planets_in_{target_name}_houses"
    profile_house_fields = {
        "house_system": house_system,
        "house_system_code": house_system_code,
        "house_system_label_zh": target_profile["house_system_label_zh"],
    }
    profile_zodiac_fields = _relative_zodiac_profile_overrides(zodiacal_info)
    influence_chart = {
        "person_info": {
            **house_chart["person_info"],
            "name": f"{target_name}受{source_name}影响",
        },
        "chart_profile": {
            "chart_type": chart_type,
            "zodiac": profile_zodiac_fields["zodiac"],
            "house_system": house_system,
            "tradition": target_profile.get("tradition", False),
            **engine_profile,
            "aspect_policy": target_profile.get("aspect_policy"),
            "house_overlay_policy": "source ecliptic longitude in target cusp sectors; not a physical horizon recast",
            "reference_frame": reference_frame,
            **(
                {"angle_definition": target_profile["angle_definition"]}
                if "angle_definition" in target_profile
                else {}
            ),
            **profile_house_fields,
            **profile_zodiac_fields,
        },
        "angles": {
            "ascendant": (
                chart_angle(ascendant)
                if ascendant_resolved
                else {"longitude": None, "sign": None, "sign_zh": None}
            ),
            "midheaven": chart_angle(midheaven),
        },
        "houses": (
            _build_houses(ascendant, house_system, house_cusps=house_cusps)
            if houses_resolved
            else []
        ),
        "planets": planets,
        "aspects": aspects,
        "aspect_evidence": aspect_evidence,
        "element_balance": _balance(planets, "element"),
        "modality_balance": _balance(planets, "modality"),
        "balance_basis": BALANCE_BASIS,
        "summary": [
            f"已生成 {target_name} 视角的影响图盘。",
            f"行星数量：{len(planets)}。",
            f"相位数量：{len(aspects)}。",
        ],
    }
    return {
        "chart_profile": {
            "chart_type": chart_type,
            **profile_house_fields,
            **profile_zodiac_fields,
            "reference_frame": reference_frame,
            **engine_profile,
        },
        "chart": influence_chart,
        "summary": [
            (
                f"以 {target_name} 的宫位框架投影 {source_name} 的星体。"
                if houses_resolved
                else f"{target_name} 的上升未定，影响图保留 {source_name} 的星体和相位。"
            ),
            f"星体数量：{len(planets)}。",
            f"相位数量：{len(aspects)}。",
        ],
    }


def _build_relative_influence_pair(
    inner_chart: dict[str, Any],
    outer_chart: dict[str, Any],
    *,
    house_system: str,
    zodiacal_info: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        _build_influence_chart_wrapper(
            role="inner",
            house_chart=inner_chart,
            source_chart=outer_chart,
            house_system=house_system,
            zodiacal_info=zodiacal_info,
        ),
        _build_influence_chart_wrapper(
            role="outer",
            house_chart=outer_chart,
            source_chart=inner_chart,
            house_system=house_system,
            zodiacal_info=zodiacal_info,
        ),
    )


def _build_marks_chart(
    person_birth: AstroBirthInfo,
    relationship_birth: AstroBirthInfo,
    *,
    house_system_info: dict[str, Any],
    zodiacal_info: dict[str, Any],
    davison_variant: str = "uncorrected",
) -> dict[str, Any]:
    birth, policy = marks_birth(
        person_birth, relationship_birth, variant=davison_variant
    )
    chart = _build_relative_base_chart(
        birth, house_system_info=house_system_info, zodiacal_info=zodiacal_info
    )
    chart["chart_profile"].update(chart_type="marks", derivation_policy=policy)
    chart["summary"] = [f"已生成 {person_birth.name} 的个人马克斯盘。"]
    return chart
