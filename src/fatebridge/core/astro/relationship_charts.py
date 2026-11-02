"""Derived chart assembly for composite, timespace, influence and marks modes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _sign_name
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
    COMPOSITE_SOURCE,
    davison_birth,
    marks_birth,
    unique_midpoint,
)
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH


def _composite_chart(
    inner_chart: Dict[str, Any],
    outer_chart: Dict[str, Any],
    *,
    house_system: str = "equal",
    zodiacal_info: Dict[str, Any],
) -> Dict[str, Any]:
    engine_profile = _derive_engine_profile(
        inner_chart.get("chart_profile", {}),
        outer_chart.get("chart_profile", {}),
    )
    inner_planets = {item["id"]: item for item in inner_chart["planets"]}
    outer_planets = {item["id"]: item for item in outer_chart["planets"]}
    house_cusps = (
        []
        if house_system == "whole_sign"
        else _midpoint_house_cusps(
            _house_cusp_values_from_payload(inner_chart),
            _house_cusp_values_from_payload(outer_chart),
        )
    )
    composite_planets: List[Dict[str, Any]] = []
    ascendant = unique_midpoint(
        inner_chart["angles"]["ascendant"]["longitude"],
        outer_chart["angles"]["ascendant"]["longitude"],
    )
    midheaven = unique_midpoint(
        inner_chart["angles"]["midheaven"]["longitude"],
        outer_chart["angles"]["midheaven"]["longitude"],
    )
    for planet in PLANET_SEQUENCE:
        if planet not in inner_planets or planet not in outer_planets:
            continue
        longitude = unique_midpoint(
            inner_planets[planet]["longitude"],
            outer_planets[planet]["longitude"],
        )
        composite_planets.append(
            _build_planet_record(
                planet,
                longitude,
                (inner_planets[planet]["latitude"] + outer_planets[planet]["latitude"])
                / 2.0,
                ascendant,
                house_system,
                house_cusps=house_cusps or None,
            )
        )
    aspect_evidence = _build_aspects(composite_planets, include_evidence=True)
    aspects = [
        {key: row[key] for key in ("planet_a", "planet_b", "aspect", "orb")}
        for row in aspect_evidence
    ]
    return {
        "person_info": {
            "name": f"{inner_chart['person_info']['name']} / {outer_chart['person_info']['name']} 组合盘",
            "birth_place": f"{inner_chart['person_info']['birth_place']} / {outer_chart['person_info']['birth_place']}",
            "birth_timezone": inner_chart["person_info"]["birth_timezone"],
        },
        "chart_profile": {
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
                "source_url": COMPOSITE_SOURCE,
                "source_kind": "first_party_implementation_documentation",
                "positions_from_single_instant": False,
                "longitude_policy": "unique shorter arc; exact diametric inputs are ambiguous",
                "latitude_policy": "symbolic arithmetic mean; not observed latitude",
                "house_policy": (
                    "whole_sign_from_composite_ASC"
                    if house_system == "whole_sign"
                    else "corresponding_cusp_short_arc_midpoints"
                ),
                "mercury_venus_policy": "no automatic 180-degree relocation",
            },
        },
        "angles": {
            "ascendant": {
                "longitude": ascendant,
                "sign": _sign_name(ascendant),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(ascendant)],
            },
            "midheaven": {
                "longitude": midheaven,
                "sign": _sign_name(midheaven),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(midheaven)],
            },
        },
        "houses": _build_houses(
            ascendant,
            house_system,
            house_cusps=house_cusps or None,
        ),
        "planets": composite_planets,
        "aspects": aspects,
        "aspect_evidence": aspect_evidence,
        "element_balance": _balance(composite_planets, "element"),
        "modality_balance": _balance(composite_planets, "modality"),
        "balance_basis": BALANCE_BASIS,
        "summary": [
            f"已生成 FateBridge 组合盘{_precision_label_zh(engine_profile['engine_precision'])}层。",
            f"行星数量：{len(composite_planets)}。",
            f"相位数量：{len(aspects)}。",
        ],
    }


def _build_relative_base_chart(
    birth_info: AstroBirthInfo,
    *,
    house_system_info: Dict[str, Any],
    zodiacal_info: Dict[str, Any],
) -> Dict[str, Any]:
    base_chart = build_core_chart_payload(
        birth_info,
        "chart",
        hsys=house_system_info["value"],
        zodiacal=zodiacal_info["value"],
    )
    # Preserve the same native zodiac positions, latitude-aware house placement
    # and time basis as the corresponding natal chart. Do not reproject a
    # separately cast tropical/default-house chart by hand.
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


def _planet_sort_key(item: Dict[str, Any]) -> Tuple[int, Any]:
    planet_id = item.get("id")
    if planet_id in PLANET_SEQUENCE:
        return (0, PLANET_SEQUENCE.index(planet_id))
    return (1, planet_id or "")


def _build_chart_from_positions(
    *,
    chart_type: str,
    person_info: Dict[str, Any],
    source_planets: List[Dict[str, Any]],
    ascendant: float,
    midheaven: float,
    house_system: str,
    house_cusps: Optional[List[float]] = None,
    summary_prefix: str,
    profile_overrides: Optional[Dict[str, Any]] = None,
    engine_profile: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    planets = [
        _build_planet_record(
            item["id"],
            item["longitude"],
            item.get("latitude", 0.0),
            ascendant,
            house_system,
            house_cusps=house_cusps,
        )
        for item in sorted(source_planets, key=_planet_sort_key)
    ]
    aspect_evidence = _build_aspects(planets, include_evidence=True)
    aspects = [
        {key: row[key] for key in ("planet_a", "planet_b", "aspect", "orb")}
        for row in aspect_evidence
    ]
    chart_profile = {
        "chart_type": chart_type,
        "zodiac": "tropical",
        "house_system": house_system,
        "tradition": False,
        "engine_precision": "approximate_orbital_model",
        "engine_backend": "fatebridge_approximate_orbital_model",
    }
    if engine_profile:
        chart_profile.update(engine_profile)
    if profile_overrides:
        chart_profile.update(profile_overrides)
    return {
        "person_info": person_info,
        "chart_profile": chart_profile,
        "angles": {
            "ascendant": {
                "longitude": ascendant,
                "sign": _sign_name(ascendant),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(ascendant)],
            },
            "midheaven": {
                "longitude": midheaven,
                "sign": _sign_name(midheaven),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(midheaven)],
            },
        },
        "houses": _build_houses(ascendant, house_system, house_cusps=house_cusps),
        "planets": planets,
        "aspects": aspects,
        "aspect_evidence": aspect_evidence,
        "element_balance": _balance(planets, "element"),
        "modality_balance": _balance(planets, "modality"),
        "balance_basis": BALANCE_BASIS,
        "summary": [
            summary_prefix,
            f"行星数量：{len(planets)}。",
            f"相位数量：{len(aspects)}。",
        ],
    }


def _build_timespace_chart(
    inner_birth: AstroBirthInfo,
    outer_birth: AstroBirthInfo,
    *,
    house_system_info: Dict[str, Any],
    zodiacal_info: Dict[str, Any],
    davison_variant: str = "uncorrected",
) -> Dict[str, Any]:
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
    role: str,
    house_chart: Dict[str, Any],
    source_chart: Dict[str, Any],
    house_system: str,
    zodiacal_info: Dict[str, Any],
) -> Dict[str, Any]:
    engine_profile = _derive_engine_profile(
        house_chart.get("chart_profile", {}),
        source_chart.get("chart_profile", {}),
    )
    target_name = house_chart["person_info"]["name"]
    source_name = source_chart["person_info"]["name"]
    house_cusps = (
        None
        if house_system == "whole_sign"
        else _house_cusp_values_from_payload(house_chart)
    )
    influence_chart = _build_chart_from_positions(
        chart_type=f"influence_{role}",
        person_info={
            **house_chart["person_info"],
            "name": f"{target_name}受{source_name}影响",
        },
        source_planets=source_chart["planets"],
        ascendant=house_chart["angles"]["ascendant"]["longitude"],
        midheaven=house_chart["angles"]["midheaven"]["longitude"],
        house_system=house_system,
        house_cusps=house_cusps,
        summary_prefix=f"已生成 {target_name} 视角的影响图盘。",
        engine_profile=engine_profile,
        profile_overrides={
            "aspect_policy": house_chart.get("chart_profile", {}).get("aspect_policy"),
            "house_overlay_policy": "source ecliptic longitude in target cusp sectors; not a physical horizon recast",
            "reference_frame": f"{source_name}_planets_in_{target_name}_houses",
            "tradition": house_chart.get("chart_profile", {}).get("tradition", False),
            "house_system_code": house_chart.get("chart_profile", {}).get(
                "house_system_code"
            ),
            "house_system_label_zh": house_chart.get("chart_profile", {}).get(
                "house_system_label_zh"
            ),
            **_relative_zodiac_profile_overrides(zodiacal_info),
        },
    )
    return {
        "chart_profile": {
            "chart_type": f"influence_{role}",
            "house_system": house_system,
            "house_system_code": house_chart.get("chart_profile", {}).get(
                "house_system_code"
            ),
            "house_system_label_zh": house_chart.get("chart_profile", {}).get(
                "house_system_label_zh"
            ),
            "zodiac": influence_chart["chart_profile"].get("zodiac", "tropical"),
            "zodiacal": zodiacal_info["value"],
            "zodiac_label_zh": zodiacal_info["label_zh"],
            "reference_frame": influence_chart["chart_profile"]["reference_frame"],
            **engine_profile,
        },
        "chart": influence_chart,
        "summary": [
            f"以 {target_name} 的宫位框架投影 {source_name} 的星体。",
            f"星体数量：{len(influence_chart['planets'])}。",
            f"相位数量：{len(influence_chart['aspects'])}。",
        ],
    }


def _build_relative_influence_pair(
    inner_chart: Dict[str, Any],
    outer_chart: Dict[str, Any],
    *,
    house_system: str,
    zodiacal_info: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
    house_system_info: Dict[str, Any],
    zodiacal_info: Dict[str, Any],
    davison_variant: str = "uncorrected",
) -> Dict[str, Any]:
    birth, policy = marks_birth(
        person_birth, relationship_birth, variant=davison_variant
    )
    chart = _build_relative_base_chart(
        birth, house_system_info=house_system_info, zodiacal_info=zodiacal_info
    )
    chart["chart_profile"].update(chart_type="marks", derivation_policy=policy)
    chart["summary"] = [f"已生成 {person_birth.name} 的个人马克斯盘。"]
    return chart
