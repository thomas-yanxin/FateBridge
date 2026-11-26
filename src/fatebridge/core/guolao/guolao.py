"""Core Guolao Xingzong chart calculation: 7 luminaries, 4 extras, 命度, 身宫, 化曜, 33神煞, 恩用难仇."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from typing import Any, Literal

from fatebridge.core.astro import runtime
from fatebridge.core.astro.astrology_tables import (
    ELEMENT_BY_SIGN,
    MODALITY_BY_SIGN,
    SIGN_LABELS_ZH,
)
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.geometry import _degree_in_sign, _sign_name, _week_ruler
from fatebridge.core.astro.parts import _build_houses, _build_planet_record
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.guolao import classical, ephemeris, moira
from fatebridge.core.guolao.classical import (
    BRANCHES,
    CN,
    PALACE_BRANCHES,
    PALACE_LORDS,
    body_relation_role,
    compute_all_33_gods,
    counting_anchor,
    dongwei_daxian,
    en_yong_nan_chou_table,
    hua_yao_for_stem,
)
from fatebridge.core.guolao.classical import life_branch as compute_life_branch
from fatebridge.core.guolao.classical import palace_branches as compute_palace_branches
from fatebridge.core.guolao.classical import relation
from fatebridge.core.guolao.ephemeris import (
    DATA,
    MansionFrame,
    fast_lichun_year,
    mansion_at,
    positions,
)

POLICIES = (
    "term_instants",
    "source_solar_days_winter_exclusive",
    "source_solar_days_winter_inclusive",
)
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.timezones import validate_local_clock

RULESET = "guolao_classical_v8"
EDITION = "tohoku_luwei_10020000001141"

LifeDegreeMethod = Literal["sun_degree_in_palace", "ascendant"]


def _season(solar_longitude: float) -> str:
    angle = solar_longitude % 360
    if 315 <= angle or angle < 45:
        return "春"
    if 45 <= angle < 135:
        return "夏"
    if 135 <= angle < 225:
        return "秋"
    return "冬"


def _jie_month_branch(tropical_sun_longitude: float) -> str:
    idx = int(((tropical_sun_longitude - 315.0) % 360.0) // 30.0)
    return "寅卯辰巳午未申酉戌亥子丑"[idx]


def _utc_label(birth: AstroBirthInfo) -> str:
    return utc_calendar(birth.recorded_datetime or birth.local_datetime).isoformat()


def body_placement(
    name: str,
    state: dict[str, Any],
    boundaries: list[dict[str, Any]],
    ayanamsha: float,
    *,
    mansion_frame: MansionFrame = "modern_equatorial",
) -> dict[str, Any]:
    """Place a planet or lunar extra into a 12-palace longitude and 28-mansion frame."""
    chinese = CN.get(name, name)
    source_longitude = Fraction(state["longitude"])
    right_ascension = Fraction(state["right_ascension"])
    if state.get("derived_from") == "罗":
        source_longitude = (Fraction(state["derivation_source_longitude"]) + 180) % 360
        right_ascension = (
            Fraction(state["derivation_source_right_ascension"]) + 180
        ) % 360
    exact = (source_longitude - Fraction(ayanamsha)) % 360
    index = int(exact // 30)
    longitude = min(float(exact), math.nextafter(float(30 * (index + 1)), -math.inf))
    coord = (
        exact
        if mansion_frame in ("modern_ecliptic", "shoushi_ecliptic")
        else right_ascension
    )
    mansion = mansion_at(coord, boundaries, frame=mansion_frame)
    lord = PALACE_LORDS[index]
    return {
        "id": name,
        "name_zh": chinese,
        **state,
        "zodiac_longitude": longitude,
        "palace_branch": PALACE_BRANCHES[index],
        "palace_lord": lord,
        "mansion": mansion,
        "in_own_palace": chinese == lord,
        "in_own_mansion": chinese == mansion["degree_lord"],
    }


def _life_mansion(
    life_longitude: float,
    ayanamsha: float,
    obliquity: float,
    boundaries: list[dict[str, Any]],
    mansion_frame: MansionFrame,
) -> dict[str, Any]:
    """Compute the 28-mansion placement of 命度 in the selected mansion frame."""
    if mansion_frame in ("modern_ecliptic", "shoushi_ecliptic"):
        coord = life_longitude
    else:
        tropical_lon = (life_longitude + ayanamsha) % 360.0
        ra, _, _ = runtime.swe.cotrans((tropical_lon, 0.0, 1.0), -obliquity)
        coord = ra % 360.0
    return mansion_at(coord, boundaries, frame=mansion_frame)


def build_chart(
    birth: AstroBirthInfo,
    *,
    hsys: int | str | None = None,
    zodiacal: int | str | None = None,
    seasonal_anchor_policy: str | None = None,
    mansion_frame: MansionFrame = "modern_equatorial",
    life_degree_method: LifeDegreeMethod = "sun_degree_in_palace",
    moira_profile: Any = None,
    moira_provider: Any = None,
) -> dict[str, Any]:
    """Build a complete fast (<10 ms) Guolao Xingzong natal chart."""
    if seasonal_anchor_policy is not None and seasonal_anchor_policy not in POLICIES:
        raise ValueError("未知果老安命交节政策")
    if life_degree_method not in ("sun_degree_in_palace", "ascendant"):
        raise ValueError("life_degree_method 须为 sun_degree_in_palace 或 ascendant")
    require_resolved_birth_timezone(birth.timezone_source)
    validate_local_clock(
        birth.local_datetime, clock_label="出生钟时", allow_ambiguous=True
    )
    if birth.recorded_datetime is not None:
        birth = replace(
            birth,
            local_datetime=birth.recorded_datetime,
            utc_datetime=utc_calendar(birth.recorded_datetime).as_datetime(),
        )

    raw = positions(birth, hsys=hsys, zodiacal=zodiacal, mansion_frame=mansion_frame)
    shift = raw["ayanamsha"]
    layout = raw["zodiac_house_layout"]
    asc, mc = layout["ascendant"], layout["midheaven"]
    hi, zi = raw["house_info"], raw["zodiac_info"]
    cusps = layout["house_cusps"]

    planets: list[dict[str, Any]] = []
    mansions: list[dict[str, Any]] = []
    signs: dict[str, int] = {}
    bodies: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []

    for name, state in list(raw["states"].items()) + list(raw["extra"].items()):
        body = body_placement(
            name, state, raw["boundaries"], shift, mansion_frame=mansion_frame
        )
        chinese = body["name_zh"]
        signs[chinese] = int(body["zodiac_longitude"] // 30)
        mansion = body["mansion"]
        mansions.append({"id": name, **mansion})
        bodies.append(body)
        if name in CN:
            record = _build_planet_record(
                name,
                state["longitude"],
                state["latitude"],
                asc,
                hi["key"],
                house_cusps=cusps,
                sidereal=zi["sidereal"],
                ayanamsha=shift,
                zodiac_longitude=body["zodiac_longitude"],
                houses_resolved=bool(cusps),
            )
            record["dignity"] = None
            record["su28"] = mansion["su28"]
            planets.append(record)

    # 命宫 & 命度
    hour_branch = BRANCHES[((birth.local_datetime.hour + 1) // 2) % 12]
    birth_clock = birth.local_datetime.isoformat()
    sun_body = next(b for b in bodies if b["id"] == "Sun")
    moon_body = next(b for b in bodies if b["id"] == "Moon")
    sun_branch = sun_body["palace_branch"]
    anchor = counting_anchor(raw["states"]["Sun"]["longitude"])
    life_branch = compute_life_branch(sun_branch, hour_branch, anchor)
    life_idx = PALACE_BRANCHES.index(life_branch)
    life_lord = PALACE_LORDS[life_idx]

    sun_deg_in_palace = sun_body["zodiac_longitude"] % 30.0
    if life_degree_method == "ascendant" and asc is not None:
        life_lon = (asc - shift) % 360.0
        life_deg_in_palace = life_lon % 30.0
        life_mansion = _life_mansion(
            life_lon, shift, raw["obliquity"], raw["boundaries"], mansion_frame
        )
        degree_status = "resolved_ascendant"
    else:
        life_lon = (life_idx * 30.0 + sun_deg_in_palace) % 360.0
        life_mansion = _life_mansion(
            life_lon, shift, raw["obliquity"], raw["boundaries"], mansion_frame
        )
        degree_status = "resolved"

    life = {
        "longitude": round(life_lon, 6),
        "degree_in_palace": round(
            (
                sun_deg_in_palace
                if life_degree_method == "sun_degree_in_palace"
                else life_deg_in_palace
            ),
            6,
        ),
        "branch": life_branch,
        "palace_lord": life_lord,
        "mansion": life_mansion,
        "degree_lord": life_mansion["degree_lord"],
        "method": "source_hour_count_and_life_degree_v1",
        "life_degree_method": life_degree_method,
        "sun_palace_branch": sun_branch,
        "sun_palace_basis": "selected_30_degree_palaces",
        "birth_hour_branch": hour_branch,
        "birth_clock": birth_clock,
        "clock_basis": "recorded_civil_clock",
        "counting_anchor_branch": anchor,
        "seasonal_anchor_policy": seasonal_anchor_policy
        or "tropical_term_instants_half_open_270_300_90_105",
        "degree_status": degree_status,
    }

    # 身宫 (Body Palace = Moon palace in Guolao Xingzong)
    body_palace = {
        "branch": moon_body["palace_branch"],
        "palace_lord": moon_body["palace_lord"],
        "longitude": round(moon_body["zodiac_longitude"], 6),
        "degree_in_palace": round(moon_body["zodiac_longitude"] % 30.0, 6),
        "mansion": moon_body["mansion"],
        "degree_lord": moon_body["mansion"]["degree_lord"],
        "basis": "moon_palace_classic_guolao",
    }

    # Fast LiChun Year Pillar + 十干化曜 + 33 神煞
    selected_year = fast_lichun_year(birth.local_datetime, raw["julian_day_tt"])
    year_stem, year_branch = BaZiCalendar.calculate_year_pillar(selected_year)
    month_branch = _jie_month_branch(raw["states"]["Sun"]["longitude"])
    is_day = raw["solar_altitude"] >= 0
    hua_yao = hua_yao_for_stem(year_stem)
    all_33_gods = compute_all_33_gods(
        year_stem=year_stem,
        year_branch=year_branch,
        month_branch=month_branch,
        hour_branch=hour_branch,
        is_day=is_day,
        sun_branch=sun_branch,
        moon_branch=moon_body["palace_branch"],
    )
    gods_sign_idx = {
        name: PALACE_BRANCHES.index(br) for name, br in all_33_gods.items()
    }

    # 恩用难仇 (by 命宫主 & 命度主) + 12 functional palaces
    en_yong_nan_chou = {
        "life_palace_lord": life_lord,
        "life_degree_lord": life_mansion["degree_lord"],
        "by_life_palace": en_yong_nan_chou_table(life_lord),
        "by_life_degree": en_yong_nan_chou_table(life_mansion["degree_lord"]),
    }

    branches_map = compute_palace_branches(life_branch)
    branch_to_palace = {br: name for name, br in branches_map.items()}
    for b in bodies:
        b["natal_functional_palace"] = branch_to_palace[b["palace_branch"]]
        b["hua_yao"] = hua_yao["by_body"].get(b["name_zh"])
        b["role_vs_life_lord"] = body_relation_role(life_lord, b["name_zh"])
        b["role_vs_degree_lord"] = body_relation_role(
            life_mansion["degree_lord"], b["name_zh"]
        )

    palace_records = []
    for name, br in branches_map.items():
        idx = PALACE_BRANCHES.index(br)
        lord = PALACE_LORDS[idx]
        palace_records.append(
            {
                "palace": name,
                "branch": br,
                "lord": lord,
                "lord_sign_index": signs[lord],
                "lord_relations": {p: relation(lord, p) for p in "木火土金水"},
                "gods_in_palace": [g for g, g_br in all_33_gods.items() if g_br == br],
            }
        )

    # 洞微大限 (106-year natal sequence)
    dongwei = dongwei_daxian(
        life_branch_str=life_branch,
        sun_degree_in_palace=sun_deg_in_palace,
        birth_year=selected_year,
    )

    current_season = _season(raw["states"]["Sun"]["longitude"])
    patterns = moira.calculate(
        {
            "life_sign_idx": life_idx,
            "planet_signidx": signs,
            "god_signidx": gods_sign_idx,
            "is_day": is_day,
            "is_winter": current_season == "冬",
        }
    )
    for pattern in patterns:
        pattern["classical_acceptance"] = False
        pattern["basis"] = (
            "moira_compatibility_with_source_hour_count_and_research_placements"
        )

    trace.extend(
        [
            {
                "rule_id": "source_life_palace_hour_count",
                "source_id": EDITION,
                "locator": "卷一·安命、十二宫例",
                "inputs": {
                    "sun_palace_branch": sun_branch,
                    "birth_hour_branch": hour_branch,
                    "counting_anchor_branch": anchor,
                    "life_degree_method": life_degree_method,
                },
                "outputs": {
                    "life_branch": life_branch,
                    "life_longitude": life["longitude"],
                    "life_mansion": life_mansion["su28"],
                    "body_branch": body_palace["branch"],
                },
                "placement_classical_acceptance": False,
            },
            {
                "rule_id": moira.PATTERN_MODEL_ID,
                "source_id": "moira_software_conditions",
                "inputs": {
                    "life_sign_idx": life_idx,
                    "is_day": is_day,
                    "season": current_season,
                },
                "outputs": {
                    "matched_patterns": [
                        {
                            "name": p["name"],
                            "rule_id": p["rule_id"],
                            "source": p["source"],
                            "evidence": p["evidence"],
                        }
                        for p in patterns
                    ],
                },
                "placement_classical_acceptance": False,
            },
        ]
    )

    god_positions = {
        "year_stem": year_stem,
        "year_branch": year_branch,
        "month_branch": month_branch,
        "year_boundary_basis": "fast_solar_315_lichun",
        "branches": all_33_gods,
        "aliases": {"天贵": "天乙（昼贵）", "玉贵": "玉堂（夜贵）"},
        "selected_noble": "天贵" if is_day else "玉贵",
        "selected_noble_branch": all_33_gods["天贵" if is_day else "玉贵"],
        "source_id": EDITION,
        "locator": "馆藏卷1–2·神煞全表",
    }

    moon_mansion = next(m for m in mansions if m["id"] == "Moon")
    guolao = {
        "lunar_mansion_system": (
            "yuanshi_054_shoushi_1281"
            if mansion_frame.startswith("shoushi_")
            else "modern_research_anchors_v1"
        ),
        "mansion_frame": mansion_frame,
        "weekday_ruler": _week_ruler(birth.local_datetime),
        "planetary_mansions": mansions,
        "moon_mansion": moon_mansion["su28"],
        "si_yu_sign_index": {k: signs[k] for k in "孛罗计炁"},
        "god_sign_index": gods_sign_idx,
        "god_positions": god_positions,
        "hua_yao": hua_yao,
        "en_yong_nan_chou": en_yong_nan_chou,
        "dongwei_daxian": dongwei,
        "body_palace": body_palace,
        "life_palace": life,
        "palaces": palace_records,
        "moira_patterns": patterns,
        "bodies": bodies,
        "timing": {"status": "not_requested"},
        "conditions": {
            "is_day": is_day,
            "solar_altitude": raw["solar_altitude"],
            "day_night_basis": "geocentric_solar_center_geometric_altitude_ge_0_no_refraction",
            "season": current_season,
            "season_basis": "northern_solar_terms_315_45_135_225",
        },
        "profile": {
            "ruleset_id": RULESET,
            "pattern_model_id": moira.PATTERN_MODEL_ID,
            "calendar": "proleptic_gregorian",
            "utc_datetime": _utc_label(birth),
            "julian_day_tt": raw["julian_day_tt"],
            "julian_day_ut1": raw["julian_day_ut1"],
            "time_conversion": raw["time_conversion"],
            "future_leap_seconds_assumed_unchanged": raw[
                "future_leap_seconds_assumed_unchanged"
            ],
            "ephemeris_models": raw["models"],
            "mansion_unit": (
                "365.2575 du"
                if mansion_frame.startswith("shoushi_")
                else "360 modern degrees"
            ),
            "astronomical_house_role": "angles_houses_and_planets_house_are_reference_only_not_functional_palaces",
            "astronomical_house_frame": (
                "selected_lahiri_sidereal_zodiac"
                if zi["sidereal"]
                else "tropical_zodiac"
            ),
            "astronomical_house_method": layout["method"],
            "reference_geometry": layout["availability"],
            "functional_palace_basis": "source_reverse_twelve_palaces_from_hour_count_life_branch",
        },
        "mansion_boundaries": raw["boundaries"],
        "rulesets": [
            {
                "id": RULESET,
                "edition_id": EDITION,
                "title": "新编评注通玄先生张果星宗大全，陆位辑校，卷一至二",
                "verified_subset": "安命/命度/身宫/逆布十二宫/十干化曜/33神煞/恩用难仇/小限/洞微大限",
            },
            {
                "id": "yuanshi_054_shoushi_1281",
                "title": "元史历志·授时历二十八宿古度",
                "verified_subset": "365.2575古度闭合宿表",
            },
            {
                "id": "swiss_ephemeris_astronomy",
                "title": "Swiss Ephemeris Programmer's Manual",
                "verified_subset": "天文计算接口与时间尺度",
            },
        ],
        "rule_trace": trace,
        "validation": {
            "classical_acceptance_passed": False,
            "real_world_prediction_status": "not_tested",
            "full_marks_established": False,
            "limitations": [],
        },
    }

    def angle(value: float | None) -> dict[str, Any]:
        if value is None:
            return {"longitude": None, "sign": None, "sign_zh": None}
        sign = _sign_name(value)
        return {"longitude": value, "sign": sign, "sign_zh": SIGN_LABELS_ZH[sign]}

    return {
        "person_info": {
            "name": birth.name,
            "birth_place": birth.birth_place,
            "birth_timezone": birth.timezone,
            "birth_longitude": birth.longitude,
            "birth_latitude": birth.latitude,
            "birth_datetime": birth.local_datetime.isoformat(),
            "utc_datetime": _utc_label(birth),
            "true_solar": {
                "applied": bool(birth.applied_true_solar),
                "correction_minutes": birth.solar_correction_minutes,
                "changes_instant": False,
            },
        },
        "chart_profile": {
            "chart_type": "guolao_chart",
            "zodiac": zi["zodiac"],
            "zodiacal": zi["value"],
            "zodiac_label_zh": zi["label_zh"],
            "ayanamsha": shift,
            "house_system": hi["key"],
            "house_system_code": hi["value"],
            "house_system_label_zh": hi["label_zh"],
            "house_system_source": hi.get("source", "explicit"),
            "tradition": True,
            "engine_precision": "ephemeris_runtime_model",
            "engine_backend": "swisseph_api",
            "ephemeris_model": raw["models"][0] if len(raw["models"]) == 1 else "mixed",
        },
        "angles": {"ascendant": angle(asc), "midheaven": angle(mc)},
        "houses": _build_houses(asc, hi["key"], house_cusps=cusps) if cusps else [],
        "planets": planets,
        "guolao": guolao,
    }
