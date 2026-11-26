"""Registered Lahiri position and natal-chart calculations with coherent sources."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.earth_attitude import earth_attitude
from fatebridge.core.astro.geometry import combine_longitudes
from fatebridge.core.astro.historical_utc import historical_utc_source
from fatebridge.core.astro.jyotish_continuous_state import continuous_state_evidence
from fatebridge.core.astro.jyotish_lunar_source_state import (
    source_derivative_state_evidence,
)
from fatebridge.core.astro.native_execution import context_evidence
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.profiles import native_factor_model
from fatebridge.core.astro.reference_frames import rotate_spherical
from fatebridge.core.astro.rotation_policy import earth_rotation_policy
from fatebridge.core.astro.sidereal_origin_motion import traditional_lahiri_origin_wrap
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.source_session import current_source_session
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.compressed_ephemeris import coordinate_context_evidence
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.jyotish.jyotish_ashtakavarga import (
    for_charts as ashtakavarga_for_charts,
)
from fatebridge.core.jyotish.jyotish_balas import (
    other_balas,
    resolve_directional_strength,
)
from fatebridge.core.jyotish.jyotish_charts import (
    GRAHAS,
    divisional_chart,
    partition_longitudes,
)
from fatebridge.core.jyotish.jyotish_clock import (
    clock_context,
    require_clock_policy,
    require_recorded_instant,
)
from fatebridge.core.jyotish.jyotish_dasha_levels import nakshatra as nakshatra
from fatebridge.core.jyotish.jyotish_display import normalize_solar_display
from fatebridge.core.jyotish.jyotish_evidence import birth_reading_basis
from fatebridge.core.jyotish.jyotish_kala import solar_packet, temporal_balas
from fatebridge.core.jyotish.jyotish_longitude_motion import (
    longitude_motion,
    node_motion,
)
from fatebridge.core.jyotish.jyotish_mean import MODEL as MOTION_MODEL
from fatebridge.core.jyotish.jyotish_mean import MODELS as MOTION_MODELS
from fatebridge.core.jyotish.jyotish_mean import SOURCE as MOTION_SOURCE
from fatebridge.core.jyotish.jyotish_mean import geometric_points
from fatebridge.core.jyotish.jyotish_panchanga import compute_panchanga
from fatebridge.core.jyotish.jyotish_rules import SOURCES, rule_trace
from fatebridge.core.jyotish.jyotish_sensitivity import (
    DashaGridObserver,
    PositionSampleObserver,
    birth_sensitivity,
)
from fatebridge.core.jyotish.jyotish_sources import (
    SourceComparison,
    coherent_sources,
    observe_physical,
    traced_positions,
)
from fatebridge.core.jyotish.jyotish_sthana import resolve_sthana
from fatebridge.core.jyotish.jyotish_strength import physical_state
from fatebridge.core.jyotish.jyotish_topics import topic_evidence
from fatebridge.core.jyotish.jyotish_vargas import SUPPORTED_DIVISIONS
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import validate_local_clock

RULESET = "parashari_lahiri_core_v29"


@coherent_sources
@traced_positions
def positions(
    birth: AstroBirthInfo,
    moment: datetime | PhysicalEpoch | None = None,
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
    instant = (
        moment.utc_datetime
        if isinstance(moment, PhysicalEpoch)
        else moment or birth.physical_datetime
    )
    if instant is not None and instant.utcoffset() is None:
        raise ValueError("印占计算时刻必须带时区。")
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
        if isinstance(moment, PhysicalEpoch):
            times = moment.time
        else:
            times = birth.time_scales if moment is None else ephemeris_time(moment)
        # Swiss builds may keep their C state per thread. Applying the path at
        # import time does not initialise a new REST/MCP worker's state.
        swe.set_ephe_path(configured_ephemeris_path() or "")
        tt, jd = times.tt, times.ut1
        if tt is None:
            raise ValueError("印占不以缺失的 TT 时间尺度计算星位。")
        jd_tt = tt.as_float()
        source_session = current_source_session()
        if source_session is None:
            raise RuntimeError(
                "India coordinate interpretation requires a source session"
            )
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0.0, 0.0)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        attitude = earth_attitude(swe, jd, julian_day_tt=tt)
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
                right_ascension, declination = rotate_spherical(
                    attitude.reduction.native_to_target, float(eq[0]), float(eq[1])
                )
                equatorial[planet] = {
                    "right_ascension": right_ascension,
                    "declination": declination,
                    "ephemeris_model": eq_model,
                }
        _, angles = runtime.ephemeris_call(
            "houses_ex",
            jd,
            birth.latitude,
            birth.longitude,
            b"W",
            swe.FLG_SIDEREAL,
            _julian_day_tt=tt,
        )
        ascendant = float(angles[0]) % 360.0
        local_meridian = (
            float(
                runtime.ephemeris_call("sidtime", jd, _julian_day_tt=tt) * 15
                + birth.longitude
            )
            % 360.0
        )
        rotation_policy = earth_rotation_policy(tt, jd)
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
    values["Ketu"] = combine_longitudes(values["Rahu"], 180.0)
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
    historical_source = {}
    utc_year = None
    if instant is not None:
        utc_year = utc_calendar(instant).date_parts[0]
        if 1960 <= utc_year < 1972:
            source = historical_utc_source(instant)
            historical_source = {
                "historical_utc_source": source["source_url"],
                "historical_utc_source_sha256": source["source_sha256"],
            }
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
        "julian_day_ut": jd.as_float(),
        "julian_day_tt": jd_tt,
        "julian_day_utc": (
            times.jd_utc if utc_year is not None and utc_year >= 1960 else None
        ),
        "time_scale_context": {
            "method": times.method,
            "planet_timescale": "TT",
            "houses_timescale": (
                "UT1_selected_final_C04_daily_series"
                if rotation_policy["measured_eop_applied"]
                else (
                    "UT1_model_estimate"
                    if utc_year is None or utc_year >= 1960
                    else "historical_UT1_input_assumption"
                )
            ),
            "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
            "leap_table_source": leap_table()["source_url"],
            "leap_table_sha256": leap_table()["source_sha256"],
            "leap_table_expires_at": leap_table()["expires_at"],
            "historical_input_convention": "1960 uses SOFA UTC rate/offset changes; 1961-1971 uses IERS; pre-1960 inputs are interpreted as UT1. Local clock realization is not authenticated",
            **historical_source,
            "scope": (
                rotation_policy["precision_scope"]
                if rotation_policy["measured_eop_applied"]
                else "future leap seconds and measured Earth rotation are not known; reported JD precision is numerical, not observational certainty"
            ),
        },
    }


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
    _sample_observer: PositionSampleObserver | None = None,
    _dasha_grid: DashaGridObserver | None = None,
) -> Dict[str, Any]:
    # The recorded UTC carrier identifies the selected fold branch.
    validate_local_clock(
        birth.local_datetime, clock_label="出生钟时", allow_ambiguous=True
    )
    selected = [9, 10] if divisions is None else divisions
    if any(d not in SUPPORTED_DIVISIONS for d in selected) or len(selected) != len(
        set(selected)
    ):
        raise ValueError(
            "divisions 仅接受不重复的十六分盘（2、3、4、7、9、10、12、16、20、24、27、30、40、45、60）；D1 始终计算。"
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
    nominal_longitudes = partition_longitudes(raw)
    nominal_nakshatras = {
        p: nakshatra(lon)
        for p, lon in {**nominal_longitudes, "Ascendant": raw["ascendant"]}.items()
    }
    charts = {
        f"D{d}": divisional_chart(raw, d, partition_longitudes=nominal_longitudes)
        for d in [1, *selected]
    }
    ashtakavarga = ashtakavarga_for_charts(charts)
    sthana_resolution = resolve_sthana(
        raw["longitudes"], raw["ascendant"], saptavargaja_profile, drekkana_profile
    )
    directional = resolve_directional_strength(
        raw["longitudes"], raw["ascendant"], raw["midheaven"]
    )
    sthana = sthana_resolution.record
    additional_balas = other_balas(raw, directional=directional)
    solar_context = solar_packet(
        raw["julian_day_ut"], birth.longitude, birth.latitude, ephemeris_policy
    )
    additional_balas.update(
        temporal_balas(
            raw,
            solar_context,
            birth.longitude,
            sthana=sthana_resolution,
            dig=directional,
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
    sensitivity = birth_sensitivity(
        birth,
        birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
        raw=raw,
        charts=charts,
        nominal_longitudes=nominal_longitudes,
        sthana_resolution=sthana_resolution,
        directional=directional,
        additional_balas=additional_balas,
        solar_context=solar_context,
        source_comparison=source_comparison,
        nominal_source_index=nominal_source_index,
        calculate_positions=positions,
        node_mode=node_mode,
        ephemeris_policy=ephemeris_policy,
        cheshta_model=cheshta_model,
        saptavargaja_profile=saptavargaja_profile,
        drekkana_profile=drekkana_profile,
        sample_observer=_sample_observer,
        dasha_grid=_dasha_grid,
    )
    panchanga = compute_panchanga(
        nominal_longitudes["Sun"],
        nominal_longitudes["Moon"],
        nominal_nakshatras["Moon"],
        local_datetime=birth.local_datetime,
        solar_context=additional_balas["kala_bala"].get("solar_context"),
    )
    return {
        "status": "complete",
        "ruleset_id": RULESET,
        "ayanamsha": raw["ayanamsha"],
        "moon_nakshatra": nakshatra(raw["longitudes"]["Moon"])["name"],
        "rising_nakshatra": nakshatra(raw["ascendant"])["name"],
        "panchanga": panchanga,
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
        "strengths": {
            "sthana_bala": sthana,
            **additional_balas,
        },
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
                "all_directed_solar_crossings_within_each_UT1_date",
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
                "vargas_other_than_D1_"
                + "_".join(f"D{division}" for division in SUPPORTED_DIVISIONS),
            ],
        },
        "interpretation_scope": "Parashari subset; sources describe traditional rules, not empirical prediction validity. Generic top-level Western fields are a separate public reference view.",
    }
