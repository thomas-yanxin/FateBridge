"""Natal/chart-variant and midpoint payload assembly."""

from __future__ import annotations

from typing import Any, Dict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import geographic_pole_angle_definition
from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.classical import (
    _build_classical_layer,
    _build_classical_patterns,
    _build_fixed_stars,
    _fortune_lot,
    _planetary_hours,
    _sect,
)
from fatebridge.core.astro.ephemeris import (
    _build_planet_states,
    _planet_set,
)
from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.geometry import (
    _nakshatra,
    _sign_name,
    combine_longitudes,
    is_prograde_house_partition,
)
from fatebridge.core.astro.horizon import populate_horizon
from fatebridge.core.astro.house_positions import build_ecliptic_house_projection
from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.layout import _relative_house_layout
from fatebridge.core.astro.midpoints import build_midpoint_analysis
from fatebridge.core.astro.parts import (
    _balance,
    _build_houses,
    _build_planet_record,
    _build_thirteen_sectors,
    _summary,
)
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    assert_physical_configuration,
)
from fatebridge.core.astro.profiles import (
    _derive_engine_profile,
    _resolve_core_chart_house_system,
    _resolve_core_chart_zodiacal_mode,
)
from fatebridge.core.astro.reference import (
    ASPECTS,
    BALANCE_BASIS,
    DEFAULT_PLANET_ORBS,
    NODE_BODIES,
)
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.seven_planets import seven_planet_view
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.core.astro_models import earth_rotation_policy
from fatebridge.core.astrology_tables import RULER_BY_SIGN as RULER_BY_SIGN
from fatebridge.core.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.ptolemy import build_ptolemy_layer


def build_core_chart_payload(
    birth_info: AstroBirthInfo,
    chart_variant: str,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
    include_context_geometry: bool = False,
    context_fortune_method: str = "sect_reversing",
    include_physical_source: bool = False,
    guolao_seasonal_anchor_policy: str | None = None,
) -> Dict[str, Any]:
    """Keep one physical chart on one managed ephemeris configuration."""
    if chart_variant != "guolao_chart":
        require_resolved_birth_timezone(birth_info.timezone_source)
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path()
        result = _build_core_chart_payload(
            birth_info,
            chart_variant,
            hsys=hsys,
            zodiacal=zodiacal,
            include_context_geometry=include_context_geometry,
            context_fortune_method=context_fortune_method,
            include_physical_source=include_physical_source,
            **(
                {"guolao_seasonal_anchor_policy": guolao_seasonal_anchor_policy}
                if guolao_seasonal_anchor_policy is not None
                else {}
            ),
        )
        assert_physical_configuration(selected)
        return result


def _build_core_chart_payload(
    birth_info: AstroBirthInfo,
    chart_variant: str,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
    include_context_geometry: bool = False,
    context_fortune_method: str = "sect_reversing",
    include_physical_source: bool = False,
    guolao_seasonal_anchor_policy: str | None = None,
) -> Dict[str, Any]:
    if guolao_seasonal_anchor_policy is not None and chart_variant != "guolao_chart":
        raise ValueError(
            "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
        )
    if chart_variant == "guolao_chart":
        from fatebridge.core.guolao import build_chart

        return build_chart(
            birth_info,
            hsys=hsys,
            zodiacal=zodiacal,
            **(
                {"seasonal_anchor_policy": guolao_seasonal_anchor_policy}
                if guolao_seasonal_anchor_policy is not None
                else {}
            ),
        )
    times = ephemeris_time(birth_info.physical_datetime)
    julian_day = times.jd_ut1
    day_number = julian_day - 2451543.5
    house_system_info = _resolve_core_chart_house_system(
        hsys,
        chart_variant=chart_variant,
    )
    zodiacal_info = _resolve_core_chart_zodiacal_mode(
        zodiacal,
        chart_variant=chart_variant,
    )
    sidereal = zodiacal_info["sidereal"]
    layout = _relative_house_layout(
        birth_info,
        house_system_info=house_system_info,
        zodiacal_info=zodiacal_info,
    )
    effective_ascendant = layout["ascendant"]
    effective_midheaven = layout["midheaven"]
    ayanamsha = layout["ayanamsha"] or 0.0
    house_cusps = (
        None if house_system_info["key"] == "whole_sign" else layout["house_cusps"]
    )
    physical_trace = PhysicalEphemerisTrace()
    motion_metadata: Dict[str, Any] = {}
    (
        planet_states,
        engine_precision,
        engine_backend,
        ephemeris_model,
        planetary_models,
    ) = _build_planet_states(
        chart_variant,
        julian_day,
        day_number,
        julian_day_tt=times.jd_tt,
        source_trace=physical_trace,
        motion_metadata=motion_metadata,
    )
    horizon_method = populate_horizon(
        planet_states, julian_day, birth_info.longitude, birth_info.latitude
    )
    if engine_precision == "ephemeris_runtime_model" and (
        horizon_method != "swisseph_true_altitude"
        or layout["angle_method"] != "swisseph"
    ):
        engine_precision = "mixed_precision_runtime_model"
        engine_backend = "swisseph_api_with_approximate_geometry"
    chart_sect = _sect(planet_states["Sun"]["altitude"])
    native_planets = [
        name
        for name, model in planetary_models.items()
        if model != "fatebridge_approximate_orbital_model"
    ]
    approximate_planets = [
        name for name in planetary_models if name not in native_planets
    ]
    zodiac_states = (
        native_lahiri_positions(
            native_planets,
            julian_day_ut1=times.jd_ut1,
            julian_day_tt=times.jd_tt,
            lunar_adjustments={
                name: (
                    state["longitude_speed_light_time_correction"],
                    planetary_models[name],
                    state["longitude_speed_spatial_aberration_correction"],
                    state.get("longitude_speed_lunar_source_remainder_correction"),
                )
                for name, state in planet_states.items()
                if "longitude_speed_light_time_correction" in state
            },
            motion_metadata=motion_metadata,
            source_trace=physical_trace,
        )
        if sidereal and native_planets
        else None
    )
    if zodiac_states is not None:
        for name in approximate_planets:
            zodiac_states[name] = {
                **planet_states[name],
                "longitude": combine_longitudes(
                    planet_states[name]["longitude"], -ayanamsha
                ),
            }
    interpretation_states = (
        {
            name: {
                **{
                    key: value
                    for key, value in state.items()
                    if not key.startswith("longitude_speed")
                },
                **zodiac_states[name],
            }
            for name, state in planet_states.items()
        }
        if zodiac_states is not None
        else planet_states
    )
    house_projection = (
        build_ecliptic_house_projection(
            julian_day_ut1=times.jd_ut1,
            julian_day_tt=times.jd_tt,
            geographic_latitude=birth_info.latitude,
            geographic_longitude=birth_info.longitude,
            house_code=house_system_info["swisseph_code"],
        )
        if not is_prograde_house_partition(layout["house_cusps"])
        else None
    )
    planets = [
        _build_planet_record(
            planet,
            planet_states[planet]["longitude"],
            interpretation_states[planet]["latitude"],
            effective_ascendant,
            house_system_info["key"],
            house_cusps=house_cusps,
            sidereal=sidereal,
            ayanamsha=ayanamsha,
            include_sector13=chart_variant == "chart13",
            include_nakshatra=chart_variant == "india_chart",
            include_su28=chart_variant == "guolao_chart",
            zodiac_longitude=(
                zodiac_states[planet]["longitude"]
                if zodiac_states is not None
                else None
            ),
            projected_house_position=(
                house_projection.position(planet_states[planet]["longitude"])
                if house_projection is not None
                else None
            ),
        )
        for planet in _planet_set(chart_variant)
    ]
    aspect_evidence = _build_aspects(planets, include_evidence=True)
    aspects = [
        {key: item[key] for key in ("planet_a", "planet_b", "aspect", "orb")}
        for item in aspect_evidence
    ]
    house_list = _build_houses(
        effective_ascendant,
        house_system_info["key"],
        house_cusps=house_cusps,
    )
    fixed_stars, fixed_star_profile = _build_fixed_stars(
        planets,
        effective_ascendant,
        effective_midheaven,
        julian_day,
        julian_day_tt=times.jd_tt,
        sidereal=sidereal,
    )
    result: Dict[str, Any] = {
        "person_info": {
            "name": birth_info.name,
            "birth_place": birth_info.birth_place,
            "birth_timezone": birth_info.timezone,
            **(
                {"timezone_source": birth_info.timezone_source}
                if chart_variant != "india_chart"
                else {}
            ),
            "birth_longitude": birth_info.longitude,
            "birth_latitude": birth_info.latitude,
            "birth_datetime": birth_info.local_datetime.isoformat(),
            "utc_datetime": birth_info.utc_isoformat,
            **(
                {"clock_conversion": dict(birth_info.clock_conversion)}
                if birth_info.clock_conversion is not None
                else {}
            ),
            "true_solar": {
                "applied": birth_info.applied_true_solar,
                "correction_minutes": birth_info.solar_correction_minutes,
                **(
                    {"time_reference": dict(birth_info.solar_time_reference)}
                    if birth_info.solar_time_reference is not None
                    else {}
                ),
            },
        },
        "chart_profile": {
            "chart_type": chart_variant,
            "zodiac": zodiacal_info["zodiac"],
            "zodiacal": zodiacal_info["value"],
            "zodiac_label_zh": zodiacal_info["label_zh"],
            "ayanamsha": ayanamsha,
            "coordinate_precision": "unrounded_computation_and_numeric_output",
            "aspect_policy": {
                "rule_id": "fatebridge_modern_dynamic_orbs_v1",
                "planet_orbs": dict(DEFAULT_PLANET_ORBS),
                "fallback_orb": 6.0,
                "combination": "arithmetic_mean",
                "exact_angles": dict(ASPECTS),
                "sextile_square_scale": 0.8,
            },
            "house_system": house_system_info["key"],
            "house_system_code": house_system_info["value"],
            "house_system_label_zh": house_system_info["label_zh"],
            "house_system_source": house_system_info.get("source", "explicit"),
            "tradition": chart_variant in {"hellen_chart", "guolao_chart"},
            "engine_precision": engine_precision,
            "engine_backend": engine_backend,
            "ephemeris_model": ephemeris_model,
            "ephemeris_model_scope": "physical_bodies",
            "nonphysical_factor_models": {
                name: model
                for name, model in planetary_models.items()
                if name in NODE_BODIES
            },
            "calendar": "proleptic_gregorian",
            "time_scale": times.method,
            "earth_rotation": (
                earth_rotation_policy(times.jd_tt, times.jd_ut1)
                if layout["angle_method"] == "swisseph"
                else None
            ),
            "julian_day_tt": times.jd_tt,
            "julian_day_ut1": times.jd_ut1,
            "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
            "horizon_method": horizon_method,
            "angle_method": layout["angle_method"],
            "sect_convention": "geocentric_solar_centre_true_altitude_ge_0",
            "longitude_motion": {
                **motion_metadata,
                "display_frame": (
                    "lahiri_sidereal_ecliptic_of_date"
                    if sidereal
                    else "tropical_ecliptic_of_date"
                ),
                "display_rotation_correction_applied": not sidereal
                and motion_metadata.get("tropical_rotation", {}).get("status")
                == "applied",
                "scope": "Source-derived longitude-rate corrections with raw native values retained. Positions and symbolic dice rules are unchanged; not a universal motion or prediction certification.",
            },
        },
        "angles": {
            "ascendant": {
                "longitude": effective_ascendant,
                "sign": _sign_name(effective_ascendant),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(effective_ascendant)],
            },
            "midheaven": {
                "longitude": effective_midheaven,
                "sign": _sign_name(effective_midheaven),
                "sign_zh": SIGN_LABELS_ZH[_sign_name(effective_midheaven)],
            },
        },
        "houses": house_list,
        "planets": planets,
        "aspects": aspects,
        "aspect_evidence": aspect_evidence,
        "classical": _build_classical_layer(
            planets,
            house_list,
            effective_ascendant,
            states=interpretation_states,
            julian_day=julian_day,
            julian_day_tt=times.jd_tt,
            sidereal=sidereal,
            chart_sect=chart_sect,
        ),
        "classical_patterns": _build_classical_patterns(
            planets, aspects, interpretation_states, chart_sect=chart_sect
        ),
        "planetary_hours": _planetary_hours(
            julian_day,
            birth_info.longitude,
            birth_info.latitude,
            birth_info.timezone,
        ),
        "fixed_stars": fixed_stars,
        "element_balance": _balance(planets, "element"),
        "modality_balance": _balance(planets, "modality"),
        "balance_basis": BALANCE_BASIS,
        "summary": _summary(
            chart_variant,
            planets,
            aspects,
            engine_precision=engine_precision,
        ),
    }
    result["chart_profile"]["fixed_stars"] = fixed_star_profile
    if chart_variant in {"chart", "hellen_chart", "chart13"}:
        result["chart_profile"]["ephemeris_reference_points"] = (
            ephemeris_reference_points(
                planetary_models,
                [f"angles.{key}" for key in result["angles"]]
                + [f"classical.lots.{key}" for key in result["classical"]["lots"]],
            )
        )
    if house_projection is not None:
        result["chart_profile"][
            "house_position_projection"
        ] = house_projection.metadata()
        projection_note = result["chart_profile"]["house_position_projection"].get(
            "note_zh"
        )
        if projection_note:
            result["summary"].append(projection_note)
    if layout.get("house_axis_convention") is not None:
        result["chart_profile"]["house_axis_convention"] = layout[
            "house_axis_convention"
        ]
        result["summary"].append(layout["house_axis_convention"]["note_zh"])
    if approximate_planets:
        result["chart_profile"]["planetary_models"] = planetary_models
        result["chart_profile"]["orbital_fallback"] = {
            "approximate_planets": approximate_planets,
            "time_argument": "UT1_day_number_ignoring_TT_difference",
            "source_path": "src/fatebridge/core/astro/orbits.py",
            "method_reference_url": "https://stjarnhimlen.se/comp/ppcomp.html",
            # Planning takes a public civil year and already includes both
            # neighbours. At a UTC label in year0/10000, the unchanged local
            # year and its neighbours cover that boundary without clipping
            # the epoch or feeding an out-of-contract year to the planner.
            "candidate_file_year": birth_info.local_datetime.year,
            "candidate_file_utc_calendar_year": birth_info.utc_calendar.date_parts[0],
            "candidate_file_plan_basis": "local_civil_year_including_adjacent_years",
            "candidate_files": list(
                ephemeris_files_for_years([birth_info.local_datetime.year])
            ),
            "note_zh": (
                "部分天体的原生星历不可用，已保留其他天体的原生位置；"
                "所列近似天体使用UT日数轨道近似，未计TT差异，远期外推误差未认证。"
                "使用近似位置的派生计算也继承其误差。"
                if native_planets
                else "天体位置使用UT日数轨道近似，未计TT差异，远期外推误差未认证。"
                "使用近似位置的派生计算也继承其误差。"
            ),
        }
        result["summary"].append(
            "轨道近似天体：" + "、".join(approximate_planets) + "。"
        )
    result["classical"]["source_profile"] = "mixed_dorothean_egyptian_lilly"
    if sidereal:
        result["chart_profile"].update(
            {
                "sidereal_position_method": (
                    "mixed_native_lahiri_and_ayanamsha_offset_approximation"
                    if native_planets and approximate_planets
                    else (
                        "swisseph_calc_sidereal_lahiri"
                        if zodiac_states is not None
                        else "ayanamsha_offset_approximation"
                    )
                ),
                "sidereal_house_method": layout.get(
                    "sidereal_house_method", "ayanamsha_offset_approximation"
                ),
                "ayanamsha_mean": layout.get("ayanamsha_mean"),
                "ayanamsha_includes_nutation": layout.get(
                    "ayanamsha_includes_nutation", False
                ),
            }
        )
        if native_planets and approximate_planets:
            result["chart_profile"]["sidereal_planetary_methods"] = {
                name: (
                    "swisseph_calc_sidereal_lahiri"
                    if name in native_planets
                    else "ayanamsha_offset_approximation"
                )
                for name in planetary_models
            }
    result["classical"]["ptolemy"] = build_ptolemy_layer(
        {planet: state["longitude"] for planet, state in planet_states.items()},
        chart_sect,
        tropical=not sidereal,
        ascendant=effective_ascendant,
    )

    angle_definition = geographic_pole_angle_definition(
        birth_info.latitude
    ) or layout.get("angle_definition")
    if angle_definition is not None:
        result["chart_profile"]["angle_definition"] = angle_definition
        result["summary"].append(angle_definition["note_zh"])

    if include_context_geometry:
        from fatebridge.core.astro.context_geometry import build_context_geometry

        result["context_geometry"] = build_context_geometry(
            planet_states,
            _planet_set(chart_variant),
            ascendant=effective_ascendant,
            midheaven=effective_midheaven,
            house_system=house_system_info["key"],
            house_cusps=layout["house_cusps"],
            ayanamsha=ayanamsha,
            chart_sect=chart_sect,
            fortune_method=context_fortune_method,
            zodiac_longitudes=(
                {name: state["longitude"] for name, state in zodiac_states.items()}
                if zodiac_states is not None
                else None
            ),
            house_projection=house_projection,
            planetary_models=planetary_models,
            motion_rates={
                name: state.get("longitude_speed")
                for name, state in interpretation_states.items()
            },
            motion_states=interpretation_states,
            motion_frame=(
                "lahiri_sidereal_ecliptic_of_date"
                if sidereal
                else "tropical_ecliptic_of_date"
            ),
            motion_derivative_policies=motion_metadata.get(
                "complete_position_derivatives", {}
            ),
        )
    if chart_variant == "chart13":
        from fatebridge.core.astro.sectors import sector_profile

        result["thirteen_sectors"] = _build_thirteen_sectors(effective_ascendant)
        result["sector_profile"] = sector_profile(effective_ascendant)
        if angle_definition:
            result["sector_profile"]["angle_definition"] = angle_definition
            for planet in result["planets"]:
                planet["sector13_evidence"]["angle_definition"] = angle_definition
            if angle_definition.get("geometric_ascendant_resolved") is False:
                profile = result["sector_profile"]
                profile.update(
                    status="underdetermined_ascendant",
                    anchor_longitude=None,
                    backend_convention_anchor_longitude=effective_ascendant,
                    backend_convention_sectors=result["thirteen_sectors"],
                )
                result["thirteen_sectors"] = []
                for planet in result["planets"]:
                    planet["sector13_evidence"].update(
                        assignment_status="underdetermined_ascendant",
                        backend_convention_sector=planet["sector13"],
                    )
                    planet["sector13"] = None
    if chart_variant == "hellen_chart":
        asc_sign = _sign_name(effective_ascendant)
        result["hellenistic"] = {
            "sect": chart_sect,
            "lot_of_fortune": _fortune_lot(
                planets, effective_ascendant, chart_sect=chart_sect
            ),
            "ascendant_ruler": RULER_BY_SIGN[asc_sign],
            "angular_planets": [
                item["id"] for item in planets if item["house"] in {1, 4, 7, 10}
            ],
        }
    if chart_variant == "india_chart":
        result["india"] = {
            "ayanamsha": round(ayanamsha, 4),
            "rising_nakshatra": _nakshatra(effective_ascendant),
            "moon_nakshatra": next(
                (item["nakshatra"] for item in planets if item["id"] == "Moon"),
                None,
            ),
        }
    result["chart_profile"]["apparent_position_policy"] = apparent_position_policy(
        times.jd_tt, planetary_models, physical_trace
    )
    source = physical_trace.finish()
    if (
        chart_variant == "chart13"
        or include_physical_source
        or configured_jpl_file() is not None
    ):
        result["chart_profile"]["physical_ephemeris_source"] = source
    return result


def build_midpoint_payload(
    birth_info: AstroBirthInfo,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
) -> Dict[str, Any]:
    base_chart = build_core_chart_payload(
        birth_info,
        "chart",
        hsys=hsys,
        zodiacal=zodiacal,
        include_physical_source=True,
    )
    engine_profile = _derive_engine_profile(base_chart.get("chart_profile", {}))
    midpoint_analysis = build_midpoint_analysis(birth_info, base_chart)
    if midpoint_analysis["status"] == "computed":
        raw_factors = midpoint_analysis["factors"]
        coordinate_source = "native_unrounded_same_instant"
    else:
        from fatebridge.core.astro.geometry import _ayanamsha

        jd = _julian_day(birth_info.physical_datetime)
        raw_states, _, _, _, _ = _build_planet_states("chart", jd, jd - 2451543.5)
        ayan = (
            _ayanamsha(jd)
            if base_chart["chart_profile"]["zodiac"] == "sidereal"
            else 0.0
        )
        raw_factors = [
            {"id": name, "longitude": (state["longitude"] - ayan) % 360}
            for name, state in raw_states.items()
        ]
        coordinate_source = "approximate_raw_orbits"
    seven = seven_planet_view(raw_factors)
    midpoints, midpoint_aspects = seven["midpoints"], seven["midpoint_aspects"]
    return {
        "chart_profile": {
            "chart_type": "germany",
            "analysis_focus": "midpoints",
            "midpoint_coordinate_source": coordinate_source,
            "midpoint_antipodal_policy": "unordered axis with both endpoints when exactly antipodal",
            "house_system": base_chart["chart_profile"]["house_system"],
            "house_system_code": base_chart["chart_profile"].get("house_system_code"),
            "house_system_label_zh": base_chart["chart_profile"].get(
                "house_system_label_zh"
            ),
            "zodiac": base_chart["chart_profile"]["zodiac"],
            "zodiacal": base_chart["chart_profile"].get("zodiacal"),
            "zodiac_label_zh": base_chart["chart_profile"].get("zodiac_label_zh"),
            "ayanamsha": base_chart["chart_profile"].get("ayanamsha"),
            **engine_profile,
        },
        "base_chart": base_chart,
        "planets": base_chart["planets"],
        "midpoint_analysis": midpoint_analysis,
        "midpoints": midpoints,
        "midpoint_aspects": midpoint_aspects,
        "summary": [
            "已生成 FateBridge 量化盘 / 中点盘。",
            f"中点数量：{len(midpoints)}。",
            f"中点相位数量：{len(midpoint_aspects)}。",
            f"原生中点几何层：{midpoint_analysis['status']}；传统解释符合度和现实预测效力尚未验证。",
        ],
    }
