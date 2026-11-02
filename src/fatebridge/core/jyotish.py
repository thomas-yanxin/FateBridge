"""Versioned Parashari subset: Lahiri D1/D9/D10 and Moon Vimshottari.

Formulas are implemented from the published sources identified below. No
third-party astrology implementation is imported. All period arithmetic uses
elapsed UTC seconds, including across daylight-saving transitions.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional

from dateutil import tz

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.historical_utc import historical_utc_source
from fatebridge.core.astro.jyotish_continuous_state import continuous_state_evidence
from fatebridge.core.astro.jyotish_lunar_source_state import (
    source_derivative_state_evidence,
)
from fatebridge.core.astro.native_execution import context_evidence
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.reference import NAKSHATRAS
from fatebridge.core.astro.sidereal_origin_motion import traditional_lahiri_origin_wrap
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.astro_models import earth_rotation_policy
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH, SIGNS
from fatebridge.core.compressed_ephemeris import coordinate_context_evidence
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.jyotish_aiyar_ashtakavarga import RULE as AIYAR_BAV_RULE
from fatebridge.core.jyotish_aiyar_ashtakavarga import SOURCE as AIYAR_BAV_SOURCE
from fatebridge.core.jyotish_aiyar_reductions import RULE as AIYAR_REDUCTION_RULE
from fatebridge.core.jyotish_aiyar_reductions import SOURCE as AIYAR_REDUCTION_SOURCE
from fatebridge.core.jyotish_ashtakavarga import RULE as ASHTAKAVARGA_RULE
from fatebridge.core.jyotish_ashtakavarga import SOURCE as ASHTAKAVARGA_SOURCE
from fatebridge.core.jyotish_ashtakavarga import SampleGrid as AshtakavargaGrid
from fatebridge.core.jyotish_ashtakavarga import for_charts as ashtakavarga_for_charts
from fatebridge.core.jyotish_ashtakavarga import (
    topic_factor as ashtakavarga_topic_factor,
)
from fatebridge.core.jyotish_balas import other_balas, verify_drik_evidence
from fatebridge.core.jyotish_clock import (
    birth_grid,
    clock_context,
    require_clock_policy,
    require_recorded_instant,
)
from fatebridge.core.jyotish_dasha_levels import (
    QUANTIZATION_METHOD,
    QUANTIZATION_RULE,
    QUANTIZATION_SOURCE,
)
from fatebridge.core.jyotish_dasha_levels import RULE as RECURSIVE_DASHA_RULE
from fatebridge.core.jyotish_dasha_levels import SOURCE as RECURSIVE_DASHA_SOURCE
from fatebridge.core.jyotish_dasha_levels import active_levels
from fatebridge.core.jyotish_display import normalize_solar_display
from fatebridge.core.jyotish_evidence import (
    birth_reading_basis,
    cheshta_ruler_provenance,
    strength_context,
    strength_text,
)
from fatebridge.core.jyotish_kala import solar_packet, temporal_balas
from fatebridge.core.jyotish_longitude_motion import RULE as LONGITUDE_MOTION_RULE
from fatebridge.core.jyotish_longitude_motion import longitude_motion, node_motion
from fatebridge.core.jyotish_mean import MODEL as MOTION_MODEL
from fatebridge.core.jyotish_mean import MODELS as MOTION_MODELS
from fatebridge.core.jyotish_mean import SOURCE as MOTION_SOURCE
from fatebridge.core.jyotish_mean import geometric_points
from fatebridge.core.jyotish_pinda import RULE as PINDA_RULE
from fatebridge.core.jyotish_pinda import SOURCE as PINDA_SOURCE
from fatebridge.core.jyotish_relationships import SOURCE as RELATIONSHIP_SOURCE
from fatebridge.core.jyotish_relationships import SOURCE_ID as RELATIONSHIP_SOURCE_ID
from fatebridge.core.jyotish_relationships import relationship
from fatebridge.core.jyotish_sources import (
    SourceComparison,
    coherent_sources,
    observe_physical,
    traced_positions,
)
from fatebridge.core.jyotish_sthana import RAMAN_SOURCE, calculate_sthana
from fatebridge.core.jyotish_strength import SOURCE as STRENGTH_SOURCE
from fatebridge.core.jyotish_strength import SOURCE_ID as STRENGTH_SOURCE_ID
from fatebridge.core.jyotish_strength import physical_state
from fatebridge.core.jyotish_vargas import RASI_LORDS as LORDS
from fatebridge.core.jyotish_vargas import SUPPORTED_DIVISIONS
from fatebridge.core.jyotish_vargas import longitude_ratio as _longitude_ratio
from fatebridge.core.jyotish_vargas import (
    varga_coordinates,
    varga_longitude,
    varga_sign,
)
from fatebridge.core.jyotish_war import SOURCE as WAR_SOURCE
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "parashari_lahiri_core_v29"
SOURCES = [
    ASHTAKAVARGA_SOURCE,
    PINDA_SOURCE,
    AIYAR_REDUCTION_SOURCE,
    AIYAR_BAV_SOURCE,
    RECURSIVE_DASHA_SOURCE,
    STRENGTH_SOURCE,
    RELATIONSHIP_SOURCE,
    RAMAN_SOURCE,
    WAR_SOURCE,
    {
        "id": "iers_leap_seconds",
        "title": "IERS Bulletin C leap-second table (version frozen in the package)",
        "url": "https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat",
        "scope": "TAI minus UTC from 1972; last offset held fixed beyond table expiry as an explicit assumption",
    },
    {
        "id": "pvr_2000",
        "title": "P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach (2000)",
        "url": "https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf",
        "sections": [
            "2 Rasis",
            "3 Planets",
            "4 Houses",
            "6 Divisional Charts",
            "10 Aspects and Argalas",
            "16 Vimsottari Dasa",
        ],
    },
    {
        "id": "swiss_ephemeris",
        "title": "Swiss Ephemeris Programmer's Manual: sidereal positions, UTC and solar clocks",
        "url": "https://www.astro.com/swisseph/swephprg.htm",
    },
]
GRAHAS = [
    "Sun",
    "Moon",
    "Mars",
    "Mercury",
    "Jupiter",
    "Venus",
    "Saturn",
    "Rahu",
    "Ketu",
]
LABELS = dict(
    zip(
        GRAHAS, ["太阳", "月亮", "火星", "水星", "木星", "金星", "土星", "罗睺", "计都"]
    )
)
DASHA_ORDER = [
    "Ketu",
    "Venus",
    "Sun",
    "Moon",
    "Mars",
    "Rahu",
    "Jupiter",
    "Saturn",
    "Mercury",
]
DASHA_YEARS = dict(zip(DASHA_ORDER, [7, 20, 6, 10, 7, 18, 16, 19, 17]))
YEAR_DAYS = {
    "sidereal_365_25636": 365.25636,
    "tropical_365_2425": 365.2425,
    "savana_360": 360.0,
}
EXALTATION = {
    "Sun": 0,
    "Moon": 1,
    "Mars": 9,
    "Mercury": 5,
    "Jupiter": 3,
    "Venus": 11,
    "Saturn": 6,
}
ASPECT_OFFSETS = {"Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}
HOUSE_MEANINGS = [
    "自我呈现与行动方式",
    "积累、语言与家庭资源",
    "沟通、练习与主动尝试",
    "居所与内在安定",
    "学习、创造与表达",
    "日常任务、服务与竞争",
    "伴侣、合作与协商",
    "共享资源与变化",
    "深造、价值观与远行",
    "职责、工作与公共角色",
    "群体、目标与所得",
    "远地、独处与支出",
]
DIGNITY_MEANINGS = {
    "exalted": "传统称入旺，表示该星在此星座的表达条件受到强调；不等于现实能力或必然好结果。",
    "debilitated": "传统称落陷，表示该星的表达需要更多条件配合；不直接判定失败。",
    "own_sign": "传统称本垣，表示该星在自身所主星座较自然地发挥其象征。",
    "other": "未落入本规则所列入旺、落陷或本垣；不能据此断言无力。",
    "not_assigned": "本规则未给该点分配尊贵状态。",
}
SOLAR_ORB_MEANINGS = {
    "within_orb": "该宫主符合 Santhanam 注释表的太阳角距条件，传统称燃烧；应与宫位及其他状态合读，不直接等于现实失能、真实不可见或所有 Yoga 失效。",
    "outside_orb": "该宫主位于 Santhanam 注释表的太阳角距范围之外，本条件未触发；这不证明其综合力量强或现实结果一定有利。",
    "at_orb_boundary": "该宫主恰在所选角度阈值；原表未规定端点包含关系，此项保留未裁定，不补写为燃烧或非燃烧。",
    "stationary_direction_ambiguous": "该宫主黄经速度为零，而原表两方向阈值不同；无法据此选定范围，此项保留未裁定。",
    "direction_not_covered": "原表没有列出该宫主本次运动方向的太阳角距阈值；此项未覆盖，不按另一个方向猜测。",
}


def validate_clock(moment: datetime, label: str) -> None:
    if not tz.datetime_exists(moment):
        raise ValueError(f"{label}为夏令时跳过的不存在钟时；请提供有效钟时。")
    if tz.datetime_ambiguous(moment):
        raise ValueError(f"{label}处于夏令时重复区间；请用明确 UTC 偏移消除歧义。")


def nakshatra(longitude: float) -> Dict[str, Any]:
    numerator, denominator = _longitude_ratio(longitude)
    index, remainder = divmod(numerator * 3, denominator * 40)
    fraction = min(remainder / (denominator * 40), math.nextafter(1.0, 0.0))
    return {
        "index": index + 1,
        "name": NAKSHATRAS[index],
        "lord": DASHA_ORDER[index % 9],
        "pada": remainder * 4 // (denominator * 40) + 1,
        "fraction_elapsed": fraction,
    }


def dignity(planet: str, sign: int) -> Dict[str, Any]:
    if planet not in EXALTATION:
        state = "not_assigned"
    elif sign == EXALTATION[planet]:
        state = "exalted"
    elif sign == (EXALTATION[planet] + 6) % 12:
        state = "debilitated"
    elif LORDS[sign] == planet:
        state = "own_sign"
    else:
        state = "other"
    return {
        "state": state,
        "own_sign": LORDS[sign] == planet,
        "rule_id": "jyotish.sign_dignity.v1",
        "scope": "sign-level only; no shadbala, moolatrikona degree ranges or node dignity doctrine",
    }


@coherent_sources
@traced_positions
def positions(
    birth: AstroBirthInfo,
    moment: Optional[datetime] = None,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    cheshta_model: str = "unadjudicated",
) -> Dict[str, Any]:
    require_recorded_instant(birth)
    if node_mode not in {"mean", "true"}:
        raise ValueError("node_mode 必须为 mean 或 true。")
    if ephemeris_policy not in {"auto", "require_data_files"}:
        raise ValueError("ephemeris_policy 必须为 auto 或 require_data_files。")
    require_clock_policy(birth, ephemeris_policy)
    if cheshta_model not in MOTION_MODELS:
        raise ValueError("不支持的五星运动力模型。")
    if runtime.swe is None:
        raise ValueError(
            "印占核心需要可用的 Swiss Ephemeris；不以近似轨道生成分盘或达沙。"
        )
    swe = runtime.swe
    instant = moment or birth.require_utc_datetime
    if instant.utcoffset() is None:
        raise ValueError("印占计算时刻必须带时区。")
    instant = instant.astimezone(timezone.utc)
    models = set()
    values: Dict[str, float] = {}
    equatorial: Dict[str, Dict[str, Any]] = {}
    states = {}
    motion = {}
    body_models = {}
    node_flags = {}
    coordinate_contexts = {}
    node_origin_metadata: Dict[str, Any] = {}
    # set_sid_mode is global C state. Keep the shared runtime lock through ALL
    # dependent positions and houses, including parallel REST requests.
    with runtime.preserve_ephemeris_path():
        selected_path = configured_ephemeris_path()
        selected_jpl = configured_jpl_file()
        times = ephemeris_time(instant)
        # Swiss builds may keep their C state per thread. Applying the path at
        # import time does not initialise a new REST/MCP worker's state.
        swe.set_ephe_path(configured_ephemeris_path() or "")
        jd_tt, jd = times.jd_tt, times.jd_ut1
        if jd_tt is None:
            raise ValueError("印占不以缺失的 TT 时间尺度计算星位。")
        source_session = current_source_session()
        if source_session is None:
            raise RuntimeError(
                "India coordinate interpretation requires a source session"
            )
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        ayan, ayanamsha = runtime.ephemeris_call(
            "get_ayanamsa_ex", jd_tt, swe.FLG_SWIEPH
        )
        if ayan < 0:
            raise ValueError("Swiss Ephemeris 无法计算 Lahiri 岁差。")
        for planet in GRAHAS[:-1]:
            planet_id = (
                (swe.MEAN_NODE if node_mode == "mean" else swe.TRUE_NODE)
                if planet == "Rahu"
                else getattr(swe, planet.upper())
            )
            coords, flag = runtime.ephemeris_call("calc", jd_tt, planet_id, flags)
            context = coordinate_context_evidence()
            if planet != "Rahu" and context is not None:
                coordinate_contexts[f"ecliptic_{planet}"] = context
            if flag < 0 or not all(math.isfinite(coords[i]) for i in (0, 1, 3)):
                raise ValueError(f"Swiss Ephemeris 无法计算 {planet}。")
            model = runtime.ephemeris_model_from_retflag(flag)
            if planet != "Rahu":
                models.add(model)
            else:
                node_flags[planet] = int(flag)
            body_models[planet] = native_factor_model(planet_id, flag)
            if planet != "Rahu":
                observe_physical(f"ecliptic_{planet}", model)
            if (
                ephemeris_policy == "require_data_files"
                and planet != "Rahu"
                and model not in {"swieph", "jpl"}
            ):
                raise ValueError(
                    f"{planet} 实际使用 {model}；require_data_files 禁止星历降级，请配置覆盖目标日期的数据文件。"
                )
            values[planet] = float(coords[0]) % 360.0
            continuous = (
                continuous_state_evidence(
                    planet,
                    jd_tt,
                    coords,
                    int(flag),
                    model,
                    source_trace=source_session.trace,
                )
                if planet != "Rahu"
                else None
            )
            # Observe the displayed coordinate before auxiliary derivative
            # samples. They run in this same source transaction and retain
            # the raw native rate; no model recomputes motion in prose.
            if planet == "Rahu":
                traditional_lahiri_origin_wrap(jd_tt, node_origin_metadata)
                motion[planet] = node_motion(
                    jd_tt,
                    float(coords[3]),
                    node_mode,
                    origin_wrap_policy=node_origin_metadata.get(
                        "traditional_sidereal_origin_wrap"
                    ),
                )
            else:
                motion[planet] = longitude_motion(
                    planet,
                    jd_tt,
                    coords,
                    model,
                    source_trace=source_session.trace,
                )
                motion[planet]["longitude_motion_context"][
                    "continuous_frame_state"
                ] = continuous
                if planet == "Moon" and continuous is not None:
                    light_time_policy = motion[planet]["longitude_motion_context"].get(
                        "lunar_light_time", {}
                    )
                    continuous["source_derivative_state"] = (
                        source_derivative_state_evidence(
                            jd_tt,
                            continuous,
                            light_time_policy.get(
                                "fixed_frame_source_derivative", light_time_policy
                            ),
                        )
                    )
            states[planet] = (
                float(coords[1]),
                motion[planet]["longitude_speed_degrees_per_day"],
            )
            if planet in GRAHAS[:7]:
                eq, eq_flag = runtime.ephemeris_call(
                    "calc", jd_tt, planet_id, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
                )
                context = coordinate_context_evidence()
                if context is not None:
                    coordinate_contexts[f"equatorial_{planet}"] = context
                if eq_flag < 0 or not all(math.isfinite(eq[i]) for i in (0, 1)):
                    raise ValueError(f"Swiss Ephemeris 无法计算 {planet} 赤道坐标。")
                eq_model = runtime.ephemeris_model_from_retflag(eq_flag)
                observe_physical(f"equatorial_{planet}", eq_model)
                if ephemeris_policy == "require_data_files" and eq_model not in {
                    "swieph",
                    "jpl",
                }:
                    raise ValueError(
                        f"{planet} 赤道坐标实际使用 {eq_model}；require_data_files 禁止星历降级。"
                    )
                models.add(eq_model)
                equatorial[planet] = {
                    "right_ascension": float(eq[0]) % 360.0,
                    "declination": float(eq[1]),
                    "ephemeris_model": eq_model,
                }
        _, angles = runtime.ephemeris_call(
            "houses_ex", jd, birth.latitude, birth.longitude, b"W", swe.FLG_SIDEREAL
        )
        ascendant = float(angles[0]) % 360.0
        local_meridian = (
            float(runtime.ephemeris_call("sidtime", jd) * 15 + birth.longitude) % 360.0
        )
        rotation_policy = earth_rotation_policy(jd_tt, jd)
        # The optional motion coordinates belong to this same TT/source
        # transaction, even though their geometric frame is different.
        motion_true = (
            geometric_points(jd_tt, ephemeris_policy)
            if cheshta_model == MOTION_MODEL
            else {}
        )
        known_backends = {
            p: {
                "ecliptic": body_models[p],
                "equatorial": equatorial[p]["ephemeris_model"],
                **(
                    {"geometric_j2000": motion_true[p]["ephemeris_model"]}
                    if p in motion_true
                    else {}
                ),
            }
            for p in GRAHAS[:7]
        }
        position_policy = apparent_position_policy(
            jd_tt,
            {
                p: (
                    body_models[p]
                    if len(set(backends.values())) == 1
                    else "mixed_coordinate_backends"
                )
                for p, backends in known_backends.items()
            },
            source_session.trace,
        )
        for p, interpretation in position_policy["bodies"].items():
            if len(set(known_backends[p].values())) != 1:
                interpretation.update(
                    reason=(
                        "ecliptic_equatorial_backend_mismatch"
                        if body_models[p] != equatorial[p]["ephemeris_model"]
                        else "geometric_coordinate_backend_mismatch"
                    ),
                    coordinate_backends=known_backends[p],
                )
        if (
            configured_ephemeris_path() != selected_path
            or configured_jpl_file() != selected_jpl
        ):
            raise EphemerisSourceError("physical_configuration_changed")
    values["Ketu"] = (values["Rahu"] + 180.0) % 360.0
    states["Ketu"] = (-states["Rahu"][0], states["Rahu"][1])
    motion["Ketu"] = node_motion(
        jd_tt,
        motion["Rahu"]["longitude_speed_native_degrees_per_day"],
        node_mode,
        antipode=True,
        origin_wrap_policy=node_origin_metadata.get("traditional_sidereal_origin_wrap"),
    )
    body_models["Ketu"] = "derived_antipode_of_Rahu"
    models.update(point["ephemeris_model"] for point in motion_true.values())
    fallback = [
        p
        for p in GRAHAS[:7]
        if body_models[p] not in {"swieph", "jpl"}
        or equatorial[p]["ephemeris_model"] not in {"swieph", "jpl"}
        or (
            p in motion_true
            and motion_true[p]["ephemeris_model"] not in {"swieph", "jpl"}
        )
    ]
    return {
        "longitudes": values,
        "native_execution_context": context_evidence(),
        "native_coordinate_contexts": coordinate_contexts,
        "apparent_position_policy": position_policy,
        "ascendant": ascendant,
        "midheaven": float(angles[1]) % 360.0,
        "equatorial": equatorial,
        "cheshta_model": cheshta_model,
        "motion_true_j2000": motion_true,
        "local_apparent_sidereal_meridian": local_meridian,
        "earth_rotation": rotation_policy,
        "ayanamsha": float(ayanamsha),
        "ephemeris_models": sorted(models),
        "ephemeris_model_scope": "physical_bodies",
        "physical_backend_policy": "strict_jpl" if selected_jpl else "auto",
        "ephemeris_by_body": body_models,
        "nonphysical_factor_models": {
            name: body_models[name] for name in ("Rahu", "Ketu")
        },
        "native_node_return_flags": node_flags,
        "ephemeris_quality": {
            "policy": ephemeris_policy,
            "status": "analytical_fallback" if fallback else "data_files_used",
            "fallback_bodies": fallback,
            "equatorial_ephemeris_by_body": {
                p: equatorial[p]["ephemeris_model"] for p in GRAHAS[:7]
            },
            "motion_ephemeris_by_body": {
                p: point["ephemeris_model"] for p, point in motion_true.items()
            },
            "scope": "Ecliptic/equatorial and selected motion geometric-frame backend provenance; secular means are a separately declared model. Supporting solar event provenance is in kala_bala.solar_events; not an accuracy certificate or prediction evidence",
        },
        "physical_states": {
            p: physical_state(
                p,
                values[p],
                values["Sun"],
                *states[p],
                native_speed=motion[p]["longitude_speed_native_degrees_per_day"],
                motion_context=motion[p]["longitude_motion_context"],
            )
            for p in GRAHAS
        },
        "julian_day_ut": jd,
        "julian_day_tt": jd_tt,
        "julian_day_utc": times.jd_utc if instant.year >= 1960 else None,
        "time_scale_context": {
            "method": times.method,
            "planet_timescale": "TT",
            "houses_timescale": (
                "UT1_selected_final_C04_daily_series"
                if rotation_policy["measured_eop_applied"]
                else (
                    "UT1_model_estimate"
                    if instant.year >= 1960
                    else "historical_UT1_input_assumption"
                )
            ),
            "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
            "leap_table_source": leap_table()["source_url"],
            "leap_table_sha256": leap_table()["source_sha256"],
            "leap_table_expires_at": leap_table()["expires_at"],
            "historical_input_convention": "1960 uses SOFA UTC rate/offset changes; 1961-1971 uses IERS; pre-1960 inputs are interpreted as UT1. Local clock realization is not authenticated",
            "historical_utc_source": historical_utc_source(instant)["source_url"],
            "historical_utc_source_sha256": historical_utc_source(instant)[
                "source_sha256"
            ],
            "scope": (
                "Selected final daily C04 UT1 and declared interpolation are applied; polar motion, CIP offsets and subdaily tides are not applied. Reported JD resolution is not a complete physical uncertainty bound."
                if rotation_policy["measured_eop_applied"]
                else "future leap seconds and measured Earth rotation are not known; reported JD precision is numerical, not observational certainty"
            ),
        },
    }


def point_record(
    planet: str,
    longitude: Optional[float],
    asc_sign: int,
    *,
    sign_index: Optional[int] = None,
) -> Dict[str, Any]:
    if sign_index is None:
        if longitude is None:
            raise ValueError("无盘内经度时必须明确分盘星座。")
        sign_index = int(longitude // 30.0)
    sign = sign_index
    return {
        "id": planet,
        "label_zh": LABELS.get(planet, "上升"),
        "longitude": longitude,
        "sign": SIGNS[sign],
        "sign_zh": SIGN_LABELS_ZH[SIGNS[sign]],
        "degree_in_sign": longitude % 30.0 if longitude is not None else None,
        "house": (sign - asc_sign) % 12 + 1,
        "dignity": dignity(planet, sign),
    }


def divisional_chart(raw: Dict[str, Any], division: int) -> Dict[str, Any]:
    asc_sign = varga_sign(raw["ascendant"], division)
    asc = None if division == 30 else varga_longitude(raw["ascendant"], division)
    planets = []
    for p in GRAHAS:
        sign, _ = varga_coordinates(raw["longitudes"][p], division)
        longitude = (
            None if division == 30 else varga_longitude(raw["longitudes"][p], division)
        )
        planets.append(point_record(p, longitude, asc_sign, sign_index=sign))
    if division == 1:
        signs = {p["id"]: int(p["longitude"] // 30) for p in planets}
        for planet in planets:
            interpretation = (
                raw.get("apparent_position_policy", {})
                .get("bodies", {})
                .get(planet["id"])
            )
            if interpretation is not None:
                planet["native_position_interpretation"] = interpretation
            if planet["id"] in raw.get("physical_states", {}):
                planet["physical_state"] = raw["physical_states"][planet["id"]]
            if planet["id"] in EXALTATION:
                planet["dispositor_relationship"] = relationship(
                    planet["id"], LORDS[signs[planet["id"]]], signs
                )
    houses = []
    for house in range(1, 13):
        sign = (asc_sign + house - 1) % 12
        lord = LORDS[sign]
        placed = next(p for p in planets if p["id"] == lord)
        houses.append(
            {
                "house": house,
                "sign": SIGNS[sign],
                "lord": lord,
                "lord_house": placed["house"],
                "lord_dignity": placed["dignity"],
                "occupants": [p["id"] for p in planets if p["house"] == house],
            }
        )
    aspects = []
    for planet in planets:
        if planet["id"] in {"Rahu", "Ketu"}:
            continue  # Node aspect doctrines differ; this ruleset assigns none.
        for distance in ASPECT_OFFSETS.get(planet["id"], [7]):
            target = (planet["house"] + distance - 2) % 12 + 1
            aspects.append(
                {
                    "from_planet": planet["id"],
                    "from_house": planet["house"],
                    "distance": distance,
                    "target_house": target,
                    "target_planets": [
                        p["id"] for p in planets if p["house"] == target
                    ],
                    "rule_id": "jyotish.graha_drishti.v1",
                }
            )
    return {
        "division": division,
        "method": {
            1: "rasi_whole_sign",
            2: "parashari_hora_sun_moon",
            3: "parashari_drekkana_trines",
            7: "parashari_saptamsa",
            9: "parashari_navamsa",
            10: "parashari_dasamsa",
            12: "parashari_dvadasamsa",
            30: "parashari_trimsamsa_unequal_signs_only",
        }[division],
        "coordinate_scope": (
            "sign assignment only; source does not specify a unique within-sign degree"
            if division == 30
            else (
                "linearly transformed varga coordinates; not physical sky longitude"
                if division != 1
                else "sidereal ecliptic longitude"
            )
        ),
        "ascendant": point_record("Ascendant", asc, asc_sign, sign_index=asc_sign),
        "planets": planets,
        "houses": houses,
        "graha_aspects": aspects,
        "rule_ids": [
            (
                "jyotish.extended_varga.v1"
                if division in {2, 3, 7, 12, 30}
                else "jyotish.varga.v1"
            ),
            "jyotish.house_lords.v1",
            "jyotish.sign_dignity.v1",
            "jyotish.graha_drishti.v1",
            *(
                [
                    "jyotish.bphs_degree_zones.v1",
                    "jyotish.bphs_uchcha_bala.v1",
                    "jyotish.bphs_baladi.v1",
                    LONGITUDE_MOTION_RULE,
                    "jyotish.satyacharya_relationships.v1",
                    "jyotish.santhanam_solar_orb.v1",
                ]
                if division == 1
                else []
            ),
        ],
    }


def rule_trace() -> List[Dict[str, Any]]:
    return [
        {"rule_id": rule, "source_id": source, "section": section}
        for rule, source, section in [
            (
                "jyotish.lahiri.v1",
                "swiss_ephemeris",
                "swe_set_sid_mode / SE_SIDM_LAHIRI / SEFLG_SIDEREAL",
            ),
            (
                "jyotish.recorded_instant.v1",
                "swiss_ephemeris",
                "9.3 UTC conversions; 9.4 local solar clocks; FateBridge preserves the recorded instant",
            ),
            (
                "jyotish.birth_clock_source_coherence.v1",
                "swiss_ephemeris",
                "9.4 solar clocks, 10.1 Delta-T; FateBridge checks clock/native Sun contexts and a same-label replay under one managed configuration; not a classical prediction rule or atomic read proof",
            ),
            (
                "jyotish.time_scales.v2",
                "iers_leap_seconds",
                "TAI-UTC table; TT=TAI+32.184 seconds; model UT1 from Swiss Delta-T",
            ),
            ("jyotish.nakshatra.v1", "pvr_2000", "2 Rasis; 16 Vimsottari Dasa"),
            ("jyotish.varga.v1", "pvr_2000", "6.2.9 Navamsa; 6.2.10 Dasamsa"),
            (
                "jyotish.extended_varga.v1",
                STRENGTH_SOURCE_ID,
                "6.5-8, 6.10-15, 6.27-28; D30 sign table only",
            ),
            (
                "jyotish.sthana_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.1-6, printed pp.263-267",
            ),
            (
                "jyotish.dig_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.7, printed p.267; physical cardinal angles",
            ),
            (
                "jyotish.naisargika_bala.v1",
                STRENGTH_SOURCE_ID,
                "27.14, printed p.276; exact multiples of60/7",
            ),
            (
                "jyotish.quantitative_drishti.v1",
                RAMAN_SOURCE["id"],
                "113-115, printed pp.82-86; directed base plus additive special, no cap",
            ),
            (
                "jyotish.drik_bala_conditional.v2",
                RAMAN_SOURCE["id"],
                "53 and116-120; lunar nature author readings and Mercury association retained as branches",
            ),
            (
                "jyotish.moon_nature_readings.v1",
                RAMAN_SOURCE["id"],
                "53 versus117-118; eighth-tithi boundaries unadjudicated",
            ),
            (
                "jyotish.kala_components.v1",
                STRENGTH_SOURCE_ID,
                "27.8-17; printed268-283; commentary and implementation choices declared",
            ),
            (
                "jyotish.solar_component_dependencies.v1",
                STRENGTH_SOURCE_ID,
                "27.12 day/night thirds and27.13 sunrise-to-sunrise; independent availability checks are a FateBridge implementation choice",
            ),
            (
                "jyotish.solar_event_enumeration.v1",
                STRENGTH_SOURCE_ID,
                "27.12-13 need chronological solar events; successive next-event searches within each UT1 date are a FateBridge implementation, not a new classical rule",
            ),
            (
                "jyotish.yuddha_raman_76_77.v1",
                WAR_SOURCE["id"],
                "76-77 printed60-61/PDF65-66; fixed Bimba divisor and through-Hora inputs; upstream source profiles retained",
            ),
            (
                "jyotish.luminary_cheshta.v1",
                STRENGTH_SOURCE_ID,
                "27.18; printed284; five-star mean model separately declared",
            ),
            (
                "jyotish.cheshta_arc.v1",
                STRENGTH_SOURCE_ID,
                "27.24-25; printed285; angular stage needs a separately admitted mean model",
            ),
            (
                "jyotish.cheshta_ruler_provenance.v1",
                STRENGTH_SOURCE_ID,
                "27.18 versus27.24-25; FateBridge maps each ruler to actual same-run upstream inputs, not a global selected model",
            ),
            (
                "jyotish.saptavargaja_profiles.v1",
                STRENGTH_SOURCE_ID,
                "27.2-4 literal seven-sign reading; alternative Raman section30 independently labeled",
            ),
            (
                "jyotish.saptavargaja_raman.v1",
                RAMAN_SOURCE["id"],
                "30, printed22-24/PDF27-29; fixed scan, selected page images verified",
            ),
            (
                "jyotish.drekkana_profiles.v1",
                STRENGTH_SOURCE_ID,
                "27.6, printed266/PDF265; Santhanam grouping",
            ),
            (
                "jyotish.drekkana_profiles.v1",
                RAMAN_SOURCE["id"],
                "36-39 and Example12 printed27-28/PDF32-33; selected15 versus conflicting summary105/PDF110 value60",
            ),
            ("jyotish.house_lords.v1", "pvr_2000", "3 Planets: ownership of rasis"),
            (
                "jyotish.sign_dignity.v1",
                "pvr_2000",
                "3 Planets: exaltation and debilitation",
            ),
            ("jyotish.graha_drishti.v1", "pvr_2000", "10.2 Graha Drishti"),
            (
                ASHTAKAVARGA_RULE,
                ASHTAKAVARGA_SOURCE["id"],
                "12.2-12.6; Tables19-27; unreduced counts on separately declared varga signs",
            ),
            (
                PINDA_RULE,
                PINDA_SOURCE["id"],
                "3.1 and12.7.1-12.7.3; selected seven-graha occupancy; unspecified equal single-occupied cells remain null",
            ),
            (
                AIYAR_REDUCTION_RULE,
                AIYAR_REDUCTION_SOURCE["id"],
                "Chapter IX English N.B. commentary, printed101-104/PDF145-148; separate reduction comparison on the same raw BAV, not a Rao patch or Pinda weighting",
            ),
            (
                AIYAR_BAV_RULE,
                AIYAR_BAV_SOURCE["id"],
                "IX.1-7, printed97-99/PDF141-143; separate seven planetary BAV tables and their own English-note reductions. Six literal cells differ from Rao; no Ascendant target inferred.",
            ),
            (
                "jyotish.vimshottari.v1",
                "pvr_2000",
                "16 Vimsottari Dasa: Moon seed, balance, antardasa",
            ),
            (
                RECURSIVE_DASHA_RULE,
                RECURSIVE_DASHA_SOURCE["id"],
                "16.1-16.3 Table38; complete parent periods recursively weighted through Deha; microsecond quantization is declared separately",
            ),
            ("jyotish.bphs_degree_zones.v1", STRENGTH_SOURCE_ID, "3.49-54"),
            ("jyotish.bphs_uchcha_bala.v1", STRENGTH_SOURCE_ID, "27.1"),
            ("jyotish.bphs_baladi.v1", STRENGTH_SOURCE_ID, "45.3-4"),
            (
                "jyotish.santhanam_solar_orb.v1",
                STRENGTH_SOURCE_ID,
                "7.28-29 translator commentary, printed p.100 / PDF p.99",
            ),
            (
                LONGITUDE_MOTION_RULE,
                "swiss_ephemeris",
                "Native swe_calc speed plus qualified FateBridge apparent-position/chain derivatives; per-body D1 longitude_motion_context records coverage, TT epoch and retained raw speed",
            ),
            (
                "jyotish.satyacharya_relationships.v1",
                RELATIONSHIP_SOURCE_ID,
                "II.16-18, pp.21-22",
            ),
            (
                "jyotish.physical_source_cohort.v1",
                "swiss_ephemeris",
                "2.6 current physical file contexts;3.3.2 returned backends; FateBridge per-body/frame grid coherence and endpoint file hashes, not an atomic read-set proof",
            ),
        ]
    ]


def topic_evidence(
    charts: Dict[str, Any],
    sthana: Optional[Dict[str, Any]] = None,
    additional_balas: Optional[Dict[str, Any]] = None,
    ashtakavarga: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if "D1" in charts and additional_balas is not None:
        verify_drik_evidence(additional_balas["drik_bala"], charts["D1"])
    topics = {}
    for topic, scopes, meaning in [
        (
            "personality",
            [("D1", 1)],
            "第一宫与宫主用于讨论自我呈现和做事方式；属于传统象征视角。",
        ),
        (
            "career",
            [("D1", 10), ("D10", 10)],
            "第十宫及其宫主用于讨论职责、工作表达与公共角色；D10 为相关传统分盘视角。",
        ),
        (
            "relationship",
            [("D1", 7), ("D9", 7)],
            "第七宫及其宫主用于讨论本人在伴侣关系中的传统象征；D9 同时涉及 dharma，不能当作双人互动证据或单独推定婚姻结局。",
        ),
    ]:
        facts = []
        factors: List[Dict[str, Any]] = []
        for name, house in scopes:
            if name in charts:
                fact = charts[name]["houses"][house - 1]
                facts.append({"chart": name, **fact})
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.house_lords.v1",
                        "fact": f"第{house}宫主{LABELS[fact['lord']]}位于第{fact['lord_house']}宫。",
                        "traditional_interpretation": f"可将该主题与{HOUSE_MEANINGS[fact['lord_house'] - 1]}联系讨论。",
                        "source_id": "pvr_2000",
                        "source_section": "4 Houses; 6 Divisional Charts",
                    }
                )
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.sign_dignity.v1",
                        "fact": {"planet": fact["lord"], **fact["lord_dignity"]},
                        "traditional_interpretation": DIGNITY_MEANINGS[
                            fact["lord_dignity"]["state"]
                        ],
                        "source_id": "pvr_2000",
                        "source_section": "3 Planets: dignities",
                    }
                )
                placed = next(
                    p for p in charts[name]["planets"] if p["id"] == fact["lord"]
                )
                if ashtakavarga is not None:
                    factors.append(
                        ashtakavarga_topic_factor(
                            name, charts[name], house, ashtakavarga
                        )
                    )
                state = placed.get("physical_state")
                if name == "D1" and sthana is not None:
                    values = sthana["summary"][fact["lord"]]
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.sthana_bala.v1",
                            "fact_path": f"india.strengths.sthana_bala.summary.{fact['lord']}",
                            "fact": values,
                            "source_id": STRENGTH_SOURCE_ID,
                            "source_section": "27.1,27.4-5; Saptavargaja and Drekkana use their separately declared profiles",
                            "component_profile_paths": [
                                "india.strengths.sthana_bala.profile.id",
                                "india.strengths.sthana_bala.profile.drekkana_profile",
                            ],
                            "traditional_interpretation": f"该宫主在所选 {sthana['profile']['id']}／{sthana['profile']['drekkana_profile']['id']} 口径下的位置力量为 {values['total_virupa']:.6g} Virupa，由五个位置分量相加；分盘计分使用 D1 星体关系。它不等于完整六力，不直接判定功能吉凶、现实能力或成功概率。原典读法和作者分歧保留在 profile、profile_comparison、drekkana_profile_comparison 与 source_reading_conflicts。",
                        }
                    )
                if name == "D1" and additional_balas is not None:
                    for key, rule_id, description in [
                        (
                            "dig_bala",
                            "jyotish.dig_bala.v1",
                            "方向力按实际上升、天顶等角点计算；与整宫落宫分开。",
                        ),
                        (
                            "naisargika_bala",
                            "jyotish.naisargika_bala.v1",
                            "自然力为所有命盘相同的传统固定系数，不能单独区别个人能力。",
                        ),
                        (
                            "drik_bala",
                            "jyotish.drik_bala_conditional.v2",
                            "相位力按Raman所列有方向的角度和附加值计算；原书算例的角度、合计存在冲突，来源页图及未裁定项见同run的source_witness与source_reading_conflicts。数值为null时须读scenarios，按未裁定的月亮／水星性质分别解释，不能当零值或挑较高分。",
                        ),
                        (
                            "kala_bala",
                            "jyotish.kala_components.v1",
                            "时间力量按已声明口径分项计算；星战公式另据Raman76-77及本次前置力量，同一月亮／水星分类分支保持关联。未裁定参与者保留缺失，不能把胜负名称解释为现实胜负。",
                        ),
                        (
                            "cheshta_bala",
                            "jyotish.luminary_cheshta.v1",
                            "运动力量目前只计算太阳与月亮；其余五星的平位置模型未完成，不以顺逆行标签或零值代替。",
                        ),
                    ]:
                        component = additional_balas[key]
                        provenance = (
                            cheshta_ruler_provenance(
                                fact["lord"], component, additional_balas["kala_bala"]
                            )
                            if key == "cheshta_bala"
                            else None
                        )
                        if provenance is not None:
                            rule_id = provenance["rule_id"]
                            description = provenance["description"]
                        value = component["summary"][fact["lord"]]
                        context = strength_context(key, fact["lord"], component)
                        if provenance is not None:
                            context["method_context"] = provenance["method_context"]
                        factors.append(
                            {
                                "chart": name,
                                "rule_id": rule_id,
                                "fact_path": f"india.strengths.{key}.summary.{fact['lord']}",
                                "fact": value,
                                "calculation_context": context,
                                "source_id": component["source_id"],
                                "source_section": (
                                    provenance["source_section"]
                                    if provenance is not None
                                    else component["source_section"]
                                ),
                                **(
                                    {
                                        "supporting_source_id": provenance[
                                            "supporting_source_id"
                                        ]
                                    }
                                    if provenance is not None
                                    and "supporting_source_id" in provenance
                                    else (
                                        {"supporting_source_id": WAR_SOURCE["id"]}
                                        if key == "kala_bala"
                                        else {}
                                    )
                                ),
                                "traditional_interpretation": strength_text(context)
                                + description
                                + "这些分量不等于完整六力、现实吉凶或事件概率。",
                            }
                        )
                if "dispositor_relationship" in placed:
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.satyacharya_relationships.v1",
                            "fact_path": f"india.charts.{name}.planets.{charts[name]['planets'].index(placed)}.dispositor_relationship",
                            "fact": placed["dispositor_relationship"],
                            "source_id": RELATIONSHIP_SOURCE_ID,
                            "source_section": "II.16-18, pp.21-22",
                            "traditional_interpretation": "按该版本，宫主与所在星座主星的自然关系和临时关系分开计算，再合成五级关系；这是星体关系，不能当作人与人的友敌、信用或事件成功率。",
                        }
                    )
                if state is not None:
                    point_path = f"india.charts.{name}.planets.{charts[name]['planets'].index(placed)}.physical_state"
                    condition = state["degree_condition"]
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": "jyotish.bphs_degree_zones.v1",
                            "fact_path": point_path + ".degree_condition",
                            "fact": condition,
                            "source_id": STRENGTH_SOURCE_ID,
                            "source_section": "3.49-54; 27.1; 45.3-4",
                            "traditional_interpretation": f"该宫主实际度数对应 {condition['degree_zone']}，Baladi 为 {condition['baladi_avastha']['state']}；Uchcha Bala 是独立的 0–60 Virupa 分量，不能当作完整力量、现实能力或成功概率。星座级标签不替代此度数条件。",
                        }
                    )
                    factors.append(
                        {
                            "chart": name,
                            "rule_id": LONGITUDE_MOTION_RULE,
                            "fact_path": point_path + ".motion",
                            "fact": state["motion"],
                            "source_id": "swiss_ephemeris",
                            "source_section": "D1 reported rate; calculation basis in physical_state.longitude_motion_context",
                            "traditional_interpretation": "顺逆行按所报 D1 黄经速度的符号读取；原生值、修正方法与适用范围见同一 physical_state。逆行不自动等于强、吉或坏；太阳间距条件按返回的作者规则读取。",
                        }
                    )
                    if "combustion" in state:
                        factors.append(
                            {
                                "chart": name,
                                "rule_id": "jyotish.santhanam_solar_orb.v1",
                                "fact_path": point_path + ".combustion",
                                "fact": state["combustion"],
                                "source_id": STRENGTH_SOURCE_ID,
                                "source_section": "7.28-29 translator commentary, printed p.100 / PDF p.99",
                                "traditional_interpretation": SOLAR_ORB_MEANINGS[
                                    state["combustion"]["status"]
                                ],
                            }
                        )
                influences = [
                    a
                    for a in charts[name]["graha_aspects"]
                    if a["target_house"] == house
                ]
                factors.append(
                    {
                        "chart": name,
                        "rule_id": "jyotish.graha_drishti.v1",
                        "fact": influences,
                        "traditional_interpretation": "这些是所选整宫 graha drishti 规则作用到主题宫的实际星体；需结合各星落点解释，不套用西占角度容许度或统一吉凶评分。",
                        "source_id": "pvr_2000",
                        "source_section": "10.2 Graha Drishti",
                    }
                )
        topics[topic] = {
            "engine_facts": facts,
            "traditional_meaning": meaning,
            "factors": factors,
            "interpretation_kind": "source_attributed_traditional_reference",
            "source_id": "pvr_2000",
            "source_section": "6 Divisional Charts; houses and planets",
            "rule_ids": sorted(
                {"jyotish.varga.v1", *(factor["rule_id"] for factor in factors)}
            ),
            "application_scope": "single-person structure; no event dates, partner intent, outcome probability or ability certification",
        }
    return topics


@coherent_sources
def build_india(
    birth: AstroBirthInfo,
    *,
    node_mode: str = "mean",
    divisions: Optional[List[int]] = None,
    birth_time_uncertainty_minutes: Optional[float] = None,
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "unadjudicated",
    _sample_observer: Optional[Callable[[float, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    validate_clock(birth.local_datetime, "出生钟时")
    selected = [9, 10] if divisions is None else divisions
    if any(d not in SUPPORTED_DIVISIONS for d in selected) or len(selected) != len(
        set(selected)
    ):
        raise ValueError(
            "divisions 仅接受不重复的 2、3、7、9、10、12、30；D1 始终计算。"
        )
    if (
        birth_time_uncertainty_minutes is not None
        and not 0 <= birth_time_uncertainty_minutes <= 120
    ):
        raise ValueError("出生时间不确定范围须在 0–120 分钟内。")
    birth, display_context = normalize_solar_display(birth, ephemeris_policy)
    raw = positions(
        birth,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        cheshta_model=cheshta_model,
    )
    source_comparison = SourceComparison()
    nominal_source_index = source_comparison.add(raw)
    nominal_nakshatras = {
        p: nakshatra(lon)
        for p, lon in {**raw["longitudes"], "Ascendant": raw["ascendant"]}.items()
    }
    charts = {f"D{d}": divisional_chart(raw, d) for d in [1, *selected]}
    ashtakavarga = ashtakavarga_for_charts(charts)
    sthana = calculate_sthana(raw, saptavargaja_profile, drekkana_profile)
    additional_balas = other_balas(raw)
    solar_context = solar_packet(
        raw["julian_day_ut"], birth.longitude, birth.latitude, ephemeris_policy
    )
    additional_balas.update(
        temporal_balas(
            raw,
            solar_context,
            birth.longitude,
            sthana=sthana,
            dig=additional_balas["dig_bala"],
        )
    )
    motion_missing = bool(additional_balas["cheshta_bala"]["missing_planets"])
    additional_balas["shadbala_assessment"].update(
        {
            "conditional": [
                "drik_bala",
                "kala_bala",
                *([] if motion_missing else ["cheshta_bala"]),
            ],
            "partial": ["cheshta_bala"] if motion_missing else [],
            "missing": [
                *(["cheshta_bala_five_star_mean_model"] if motion_missing else []),
                *[
                    f"kala_bala.{key}"
                    for key in additional_balas["kala_bala"]["missing_components"]
                ],
            ],
        }
    )
    sthana["remaining_shadbala"] = [
        "kala_bala_or_drik_classification_adjudication",
        *(["cheshta_bala_five_star_mean_model"] if motion_missing else []),
    ]
    sensitivity: Dict[str, Any] = {
        "status": "not_assessed",
        "uncertainty_minutes": birth_time_uncertainty_minutes,
        "scope": "birth instant uncertainty; coordinates and ruleset held fixed",
        "limitation": "未给不确定范围不表示出生时刻精确；分盘上升与宫位对时刻敏感。",
    }
    if birth_time_uncertainty_minutes is not None:
        ashtakavarga_grid = AshtakavargaGrid(list(charts))
        source_samples = []
        offsets, clock_interval = birth_grid(
            birth, birth_time_uncertainty_minutes, ephemeris_policy
        )
        if clock_interval:
            sensitivity["clock_interval"] = clock_interval
            sensitivity["scope"] = (
                "recorded solar-wall uncertainty interval converted to physical UTC; coordinates and ruleset held fixed"
            )
        seen: Dict[str, Dict[str, set]] = {
            name: {p: set() for p in ["Ascendant", *GRAHAS]} for name in charts
        }
        condition_samples: Dict[str, set] = {p: set() for p in GRAHAS[:7]}
        bala_samples: Dict[str, List[float]] = {p: [] for p in GRAHAS[:7]}
        sampled_fallback = set(raw["ephemeris_quality"]["fallback_bodies"])
        sampled_future_time_assumption = raw["time_scale_context"][
            "future_leap_seconds_assumed_unchanged"
        ]
        strength_samples: Dict[str, Dict[str, List[float]]] = {
            p: {key: [] for key in values} for p, values in sthana["summary"].items()
        }
        dig_samples: Dict[str, List[float]] = {p: [] for p in GRAHAS[:7]}
        drik_samples: Dict[str, Dict[str, List[float]]] = {}
        temporal_samples: Dict[str, Dict[str, Dict[str, List[float]]]] = {
            "kala_bala": {},
            "cheshta_bala": {},
            "yuddha_bala": {},
        }
        time_lord_samples: Dict[str, set[str]] = {
            key: set()
            for key in (
                "tribhaga_bala",
                "abda_bala",
                "masa_bala",
                "dina_bala",
                "hora_bala",
            )
        }
        moon_nature_samples = set()
        solar_bracket_states: Dict[tuple[str, str], int] = {}
        motion_model_samples = set()
        war_state_samples = set()
        nak_samples: Dict[str, Dict[tuple, int]] = {
            p: {} for p in ["Ascendant", *GRAHAS]
        }
        moon_samples = []
        for offset in offsets:
            sample = (
                raw
                if offset == 0
                else positions(
                    birth,
                    birth.require_utc_datetime + timedelta(seconds=offset),
                    node_mode,
                    ephemeris_policy,
                    cheshta_model,
                )
            )
            source_index = (
                nominal_source_index if offset == 0 else source_comparison.add(sample)
            )
            source_samples.append(
                {"offset_seconds": offset, "source_index": source_index}
            )
            if _sample_observer is not None:
                _sample_observer(offset, sample)
            ashtakavarga_grid.observe(offset, sample)
            for name in charts:
                d = int(name[1:])
                asc_sign = varga_sign(sample["ascendant"], d)
                seen[name]["Ascendant"].add((asc_sign, 1))
                for p in GRAHAS:
                    sign = varga_sign(sample["longitudes"][p], d)
                    seen[name][p].add((sign, (sign - asc_sign) % 12 + 1))
            for p, lon in {
                **sample["longitudes"],
                "Ascendant": sample["ascendant"],
            }.items():
                star = nakshatra(lon)
                label = (star["index"], star["name"], star["lord"], star["pada"])
                nak_samples[p][label] = nak_samples[p].get(label, 0) + 1
            sampled_fallback.update(sample["ephemeris_quality"]["fallback_bodies"])
            sampled_future_time_assumption |= sample["time_scale_context"][
                "future_leap_seconds_assumed_unchanged"
            ]
            sample_strength = (
                sthana
                if offset == 0
                else calculate_sthana(sample, saptavargaja_profile, drekkana_profile)
            )
            sampled_balas = additional_balas if offset == 0 else other_balas(sample)
            if offset != 0:
                sampled_balas.update(
                    temporal_balas(
                        sample,
                        solar_context,
                        birth.longitude,
                        sthana=sample_strength,
                        dig=sampled_balas["dig_bala"],
                    )
                )
            solar_state = sampled_balas["kala_bala"]["solar_context"]
            bracket_state = (
                solar_state["sunrise_day_status"],
                solar_state["active_arc_status"],
            )
            solar_bracket_states[bracket_state] = (
                solar_bracket_states.get(bracket_state, 0) + 1
            )
            for p, value in sampled_balas["dig_bala"]["summary"].items():
                dig_samples[p].append(value)
            moon_nature_samples.add(
                tuple(sampled_balas["drik_bala"]["nature_context"]["moon_options"])
            )
            motion_model_samples.add(
                sampled_balas["cheshta_bala"]["model_context"]["status"]
            )
            war = sampled_balas["kala_bala"]["components"]["yuddha_bala"]
            war_state_samples.add(
                tuple(
                    (tuple(pair["planets"]), pair["status"], pair["winner"])
                    for pair in war["pairs"]
                )
            )
            for scenario, data in sampled_balas["drik_bala"]["scenarios"].items():
                bucket = drik_samples.setdefault(scenario, {p: [] for p in GRAHAS[:7]})
                for p, value in data["summary"].items():
                    bucket[p].append(value)
            for key in temporal_samples:
                component = war if key == "yuddha_bala" else sampled_balas[key]
                for scenario, values in component["scenarios"].items():
                    bucket = temporal_samples[key].setdefault(
                        scenario, {p: [] for p in GRAHAS[:7]}
                    )
                    for p, value in values.items():
                        if value is not None:
                            bucket[p].append(value)
            for key in time_lord_samples:
                time_lord_samples[key].add(
                    sampled_balas["kala_bala"]["components"][key]["ruler"]
                    or "not_available"
                )
            for p, values in sample_strength["summary"].items():
                for key, value in values.items():
                    strength_samples[p][key].append(value)
            for p in GRAHAS[:7]:
                state = sample["physical_states"][p]
                degree = state["degree_condition"]
                condition_samples[p].add(
                    (
                        degree["degree_zone"],
                        degree["baladi_avastha"]["state"],
                        state["motion"],
                        state.get("combustion", {}).get("status", "not_applicable"),
                        state.get("longitude_motion_context", {}).get(
                            "rate_basis", "unspecified"
                        ),
                    )
                )
                bala_samples[p].append(degree["uchcha_bala"]["value"])
            if offset in {offsets[0], 0.0, offsets[-1]}:
                moon_samples.append(
                    {
                        "offset_seconds": offset,
                        "longitude": sample["longitudes"]["Moon"],
                    }
                )
        alternatives = {
            name: {
                p: [{"sign": SIGNS[s], "house": h} for s, h in sorted(values)]
                for p, values in points.items()
                if len(values) > 1
            }
            for name, points in seen.items()
        }
        condition_alternatives = {
            p: [
                {
                    "degree_zone": zone,
                    "baladi_avastha": age,
                    "motion": motion,
                    "solar_orb_status": orb_status,
                    "longitude_motion_basis": basis,
                }
                for zone, age, motion, orb_status, basis in sorted(values)
            ]
            for p, values in condition_samples.items()
            if len(values) > 1
        }
        discrete_strength_alternatives = {
            p: {
                key: sorted(set(values))
                for key, values in components.items()
                if key
                in {
                    "saptavargaja_bala",
                    "ojayugma_bala",
                    "kendradi_bala",
                    "drekkana_bala",
                }
                and len(set(values)) > 1
            }
            for p, components in strength_samples.items()
        }
        discrete_strength_alternatives = {
            p: values for p, values in discrete_strength_alternatives.items() if values
        }
        nak_alternatives = {
            p: [
                {
                    "index": index,
                    "name": name,
                    "lord": lord,
                    "pada": pada,
                    "sample_count": count,
                }
                for (index, name, lord, pada), count in sorted(options.items())
            ]
            for p, options in nak_samples.items()
            if len(options) > 1
        }
        sensitivity.update(
            {
                "status": (
                    "changes_detected"
                    if any(alternatives.values())
                    or condition_alternatives
                    or discrete_strength_alternatives
                    or len(moon_nature_samples) > 1
                    or len(motion_model_samples) > 1
                    or len(war_state_samples) > 1
                    or len(solar_bracket_states) > 1
                    or nak_alternatives
                    or any(len(values) > 1 for values in time_lord_samples.values())
                    else "no_change_on_sample_grid"
                ),
                "method": "UTC interval grid including endpoints and supplied instant; max 30-second step",
                "sample_count": len(offsets),
                "ashtakavarga_variants": ashtakavarga_grid.result(),
                "alternatives": alternatives,
                "nakshatra_alternatives": nak_alternatives,
                "nakshatra_sampled_points": list(nak_samples),
                "nakshatra_sample_scope": "Nakshatra, ruler and Pada on the same max30-second UTC grid. Alternative counts are coverage, never probabilities; absence of a change on the grid is not interval-wide proof.",
                "physical_condition_alternatives": condition_alternatives,
                "dig_bala_sample_ranges": {
                    p: {"minimum": min(values), "maximum": max(values)}
                    for p, values in dig_samples.items()
                },
                "drik_bala_scenario_sample_ranges": {
                    scenario: {
                        p: {
                            "minimum": min(values),
                            "maximum": max(values),
                            "sample_count": len(values),
                        }
                        for p, values in planets.items()
                    }
                    for scenario, planets in drik_samples.items()
                },
                "drik_moon_nature_options_on_grid": [
                    list(options) for options in sorted(moon_nature_samples)
                ],
                "cheshta_model_statuses_on_grid": sorted(motion_model_samples),
                "yuddha_states_on_grid": [
                    [
                        {"planets": list(planets), "status": status, "winner": winner}
                        for planets, status, winner in state
                    ]
                    for state in sorted(war_state_samples, key=repr)
                ],
                "additional_bala_sample_scope": "directional continuous ranges and conditional Drik branches on the same UTC grid; Naisargika coefficients are constant. Branch counts are coverage, not probabilities.",
                "temporal_bala_scenario_sample_ranges": {
                    key: {
                        scenario: {
                            p: {
                                "minimum": min(values),
                                "maximum": max(values),
                                "sample_count": len(values),
                            }
                            for p, values in planets.items()
                            if values
                        }
                        for scenario, planets in scenarios.items()
                    }
                    for key, scenarios in temporal_samples.items()
                },
                "time_lord_alternatives": {
                    key: sorted(values)
                    for key, values in time_lord_samples.items()
                    if len(values) > 1
                },
                "solar_bracket_states_on_grid": [
                    {
                        "sunrise_day_status": sunrise,
                        "active_arc_status": arc,
                        "sample_count": count,
                    }
                    for (sunrise, arc), count in sorted(solar_bracket_states.items())
                ],
                "solar_bracket_scope": "Same UTC grid; component dependencies are independent. Coverage counts are not probabilities or continuous interval proofs.",
                "sthana_discrete_component_alternatives": discrete_strength_alternatives,
                "status_scope": "categorical states including Nakshatra/Pada, war pair candidates/decisions and discrete positional components; continuous strengths are reported in sample ranges",
                "uchcha_bala_sample_range": {
                    p: {
                        "minimum": min(values),
                        "maximum": max(values),
                        "unit": "virupa",
                    }
                    for p, values in bala_samples.items()
                },
                "sampled_ephemeris_fallback_bodies": sorted(sampled_fallback),
                "source_comparison": {
                    **source_comparison.result(),
                    "sample_source_indices": source_samples,
                },
                "sampled_future_leap_seconds_assumed_unchanged": sampled_future_time_assumption,
                "sthana_bala_sample_ranges": {
                    p: {
                        key: {"minimum": min(values), "maximum": max(values)}
                        for key, values in components.items()
                    }
                    for p, components in strength_samples.items()
                },
                "moon_samples": moon_samples,
                "limitation": "抽样未见变化不保证区间内无边界；不确定范围之外及地点误差未评估。",
            }
        )
    return {
        "status": "complete",
        "ruleset_id": RULESET,
        "ayanamsha": raw["ayanamsha"],
        "moon_nakshatra": nakshatra(raw["longitudes"]["Moon"])["name"],
        "rising_nakshatra": nakshatra(raw["ascendant"])["name"],
        "profile": {
            "engine": "swisseph_api",
            "native_execution_context": context_evidence(),
            "native_coordinate_contexts": raw["native_coordinate_contexts"],
            "apparent_position_policy": raw["apparent_position_policy"],
            "earth_rotation": raw["earth_rotation"],
            "local_apparent_sidereal_meridian_degrees": raw[
                "local_apparent_sidereal_meridian"
            ],
            "ephemeris_model": (
                raw["ephemeris_models"][0]
                if len(raw["ephemeris_models"]) == 1
                else "mixed"
            ),
            "zodiac": "sidereal",
            "ayanamsha_id": "swiss_lahiri_sidm_1",
            "position_method": "native_SEFLG_SIDEREAL_ecliptic_of_date",
            "house_system": "whole_sign",
            "node_mode": node_mode,
            "swisseph_version": str(runtime.swe.version),
            "ephemeris_models": raw["ephemeris_models"],
            "ephemeris_model_scope": raw["ephemeris_model_scope"],
            "physical_backend_policy": raw["physical_backend_policy"],
            "ephemeris_by_body": raw["ephemeris_by_body"],
            "nonphysical_factor_models": raw["nonphysical_factor_models"],
            "native_node_return_flags": raw["native_node_return_flags"],
            "ephemeris_quality": raw["ephemeris_quality"],
            "physical_ephemeris_source": raw["physical_ephemeris_source"],
            "julian_day_ut": raw["julian_day_ut"],
            "julian_day_tt": raw["julian_day_tt"],
            "julian_day_utc": raw["julian_day_utc"],
            "time_scale_context": raw["time_scale_context"],
            "time_conversion": raw["time_scale_context"]["method"],
            "clock": "resolved_input_instant" if birth.clock_conversion else "civil",
            "clock_context": {
                **clock_context(birth, display_context),
                **(
                    {"source_comparison": raw["clock_source_comparison"]}
                    if birth.clock_conversion is not None
                    else {}
                ),
            },
            "ruleset_id": RULESET,
            "saptavargaja_profile": saptavargaja_profile,
            "drekkana_profile": drekkana_profile,
            "cheshta_model": cheshta_model,
        },
        "nakshatras": nominal_nakshatras,
        "reading_basis": birth_reading_basis(charts, nominal_nakshatras, sensitivity),
        "charts": charts,
        "strengths": {"sthana_bala": sthana, **additional_balas},
        "ashtakavarga": ashtakavarga,
        "topic_evidence": topic_evidence(
            charts, sthana, additional_balas, ashtakavarga
        ),
        "birth_time_sensitivity": sensitivity,
        "rulesets": [
            *SOURCES,
            *([MOTION_SOURCE] if cheshta_model == MOTION_MODEL else []),
        ],
        "rule_trace": [
            *rule_trace(),
            *(
                [
                    {
                        "rule_id": "jyotish.cheshta_simon1994.v1",
                        "source_id": MOTION_SOURCE["id"],
                        "section": "5.8 mean elements + Santhanam27.24-25 angular formula; validated1900-2050 TT only",
                    }
                ]
                if cheshta_model == MOTION_MODEL
                else []
            ),
        ],
        "coverage": {
            "implemented": [
                "nine_grahas",
                "nakshatra_pada_lord",
                "whole_sign_lords",
                "sign_dignities",
                "D1_degree_dignities",
                "D1_uchcha_bala_component_60_virupa",
                "D1_baladi_avastha",
                "D1_physical_motion_and_sun_separation",
                "D1_dispositor_natural_temporary_compound_relationships",
                "D1_Santhanam_commentary_solar_orb_criterion",
                "five_sthana_bala_components_under_declared_saptavargaja_reading",
                "independently_selected_drekkana_source_and_retained_summary_conflict",
                "independent_sunrise_day_and_active_arc_component_availability",
                "successive_solar_event_enumeration_within_each_UT1_date",
                "dig_bala_actual_cardinal_angles",
                "naisargika_exact_sevenths",
                "Raman_quantitative_drishti_and_conditional_planetary_drik_bala",
                "kala_eight_components_and_conditional_war_coverage",
                "Sun_Moon_cheshta_from_Ayana_Paksha",
                *(
                    ["five_star_cheshta_explicit_Simon1994_secular_model"]
                    if not motion_missing
                    else []
                ),
                "graha_drishti",
                "Rao2000_unreduced_PAV_BAV_SAV_for_each_returned_varga",
                "Ashtakavarga_per_contributor_claims_and_own_sign_birth_grid_variants",
                "Rao2000_reductions_and_Pinda_declared_seven_graha_occupancy_with_source_gaps",
                *charts,
                "physical_source_coherence_across_birth_samples",
                "birth_clock_conversion_and_native_source_coherence",
            ],
            "not_implemented": [
                "shadbala",
                "physical_heliacal_visibility",
                "other_author_combustion_profiles",
                "ashtakavarga_unique_occupancy_and_equal_single_occupied_rule",
                "ashtakavarga_transit_event_prediction",
                "yoga_acceptance",
                "node_dignities_and_aspects",
                "birth_time_rectification",
                "vargas_other_than_D1_D2_D3_D7_D9_D10_D12_D30",
            ],
        },
        "interpretation_scope": "Parashari subset; sources describe traditional rules, not empirical prediction validity. Generic top-level Western fields are a separate legacy reference.",
    }


def vimshottari(
    birth_utc: datetime,
    moon_longitude: float,
    analysis: datetime,
    *,
    year_basis: str = "sidereal_365_25636",
    dasha_depth: int = 2,
) -> Dict[str, Any]:
    if type(dasha_depth) is not int or not 2 <= dasha_depth <= 6:
        raise ValueError("Vimshottari 层数须为2至6的整数。")
    if year_basis not in YEAR_DAYS:
        raise ValueError("不支持的 Vimshottari 年长口径。")
    if birth_utc.tzinfo is None or analysis.tzinfo is None:
        raise ValueError("达沙的出生与分析时刻必须带时区。")
    origin = birth_utc.astimezone(timezone.utc)
    target = analysis.astimezone(timezone.utc)
    if target < origin:
        raise ValueError("分析时刻不能早于出生时刻。")
    seed = nakshatra(moon_longitude)
    first = DASHA_ORDER.index(seed["lord"])
    year_microseconds = round(YEAR_DAYS[year_basis] * 86_400_000_000)
    numerator, denominator = _longitude_ratio(moon_longitude)
    _, remainder = divmod(numerator * 3, denominator * 40)
    elapsed_fraction = Fraction(remainder, denominator * 40)
    first_years = DASHA_YEARS[seed["lord"]]
    elapsed_years_exact = elapsed_fraction * first_years
    first_offset = -elapsed_years_exact * year_microseconds

    def edge(offset: Fraction) -> datetime:
        return origin + timedelta(microseconds=round(offset))

    start = edge(first_offset)
    cycle_duration = timedelta(microseconds=120 * year_microseconds)
    cycle_index = (target - start) // cycle_duration
    active_start = start + cycle_index * cycle_duration
    active_offset = first_offset + cycle_index * 120 * year_microseconds
    timeline = []
    cumulative = 0
    current_major = current_sub = None
    current_major_offset = None
    # Derive each boundary from a shared origin; do not compound rounded dates.
    for step in range(9):
        lord = DASHA_ORDER[(first + step) % 9]
        years = DASHA_YEARS[lord]
        major_offset = active_offset + cumulative * year_microseconds
        major_start = edge(major_offset)
        major_end = edge(major_offset + years * year_microseconds)
        major: Dict[str, Any] = {
            "lord": lord,
            "start": major_start.isoformat(),
            "end": major_end.isoformat(),
            "duration_years": years,
        }
        subs = []
        sub_total = 0
        for substep in range(9):
            sublord = DASHA_ORDER[(first + step + substep) % 9]
            sub_start = edge(
                major_offset + Fraction(years * sub_total * year_microseconds, 120)
            )
            sub_total += DASHA_YEARS[sublord]
            sub_end = (
                major_end
                if substep == 8
                else edge(
                    major_offset + Fraction(years * sub_total * year_microseconds, 120)
                )
            )
            sub = {
                "lord": sublord,
                "major_lord": lord,
                "start": sub_start.isoformat(),
                "end": sub_end.isoformat(),
                "duration_years": years * DASHA_YEARS[sublord] / 120.0,
            }
            subs.append(sub)
            if sub_start <= target < sub_end:
                current_sub = dict(sub)
        if major_start <= target < major_end:
            current_major = dict(major)
            current_major_offset = major_offset
        timeline.append({**major, "antardashas": subs})
        cumulative += years
    if current_major is None or current_sub is None or current_major_offset is None:
        raise ValueError("达沙日期边界超出可计算范围。")
    birth_end = edge(first_offset + first_years * year_microseconds)
    elapsed_microseconds = round(elapsed_years_exact * year_microseconds)
    result: Dict[str, Any] = {
        "method_id": "moon_nakshatra_vimshottari_v1",
        "year_basis": year_basis,
        "year_days": YEAR_DAYS[year_basis],
        "analysis_datetime": analysis.isoformat(),
        "boundary_convention": "start_inclusive_end_exclusive_UTC_elapsed",
        "elapsed_time_convention": "UTC calendar labels with Python datetime/timedelta: nominal 86400-second days, leap-second labels unrepresented; not a claim of continuous atomic SI elapsed time",
        "seed": {**seed, "moon_longitude": moon_longitude},
        "birth_balance": {
            "lord": seed["lord"],
            "elapsed_years": float(elapsed_years_exact),
            "remaining_years": float((1 - elapsed_fraction) * first_years),
            "elapsed_microseconds": elapsed_microseconds,
            "remaining_microseconds": first_years * year_microseconds
            - elapsed_microseconds,
            "major_start": start.isoformat(),
            "major_end": birth_end.isoformat(),
        },
        "current_major": current_major,
        "current_sub": current_sub,
        "timeline": timeline,
        "timeline_scope": {
            "cycle_index": cycle_index,
            "start": active_start.isoformat(),
            "end": timeline[-1]["end"],
            "cycle_years": 120,
            "meaning": "formal system cycle; not a lifespan estimate",
        },
        "time_quantization": {
            "method_id": QUANTIZATION_METHOD,
            "source_id": QUANTIZATION_SOURCE["id"],
            "reference_epoch_utc": origin.isoformat(),
            "source_mansion_fraction_exact": {
                "numerator": str(elapsed_fraction.numerator),
                "denominator": str(elapsed_fraction.denominator),
            },
            "year_microseconds": year_microseconds,
            "quantum_microseconds": 1,
            "rounding": "nearest_integer_ties_to_even_at_each_final_edge",
            "scope": QUANTIZATION_SOURCE["scope"],
        },
        "rule_ids": [
            "jyotish.nakshatra.v1",
            "jyotish.vimshottari.v1",
            QUANTIZATION_RULE,
        ],
        "interpretation_scope": "Period rulers and boundaries only; no event guarantee or probability. Year basis is a declared implementation choice.",
    }
    if dasha_depth > 2:
        subdivisions = active_levels(
            current_major["lord"],
            datetime.fromisoformat(current_major["start"]),
            analysis,
            year_basis=year_basis,
            depth=dasha_depth,
            _reference_epoch=origin,
            _major_start_offset_us=current_major_offset,
        )
        for original, nested in zip(
            (current_major, current_sub), subdivisions["current_levels"][:2]
        ):
            if any(original[key] != nested[key] for key in ("lord", "start", "end")):
                raise ValueError("嵌套分期与同次主运／次运边界不一致。")
        result["subdivisions"] = subdivisions
        result["rule_ids"].append(RECURSIVE_DASHA_RULE)
    return result
