"""Natal/chart-variant and midpoint payload assembly."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import (
    geographic_pole_angle_definition,
    is_ascendant_resolved,
)
from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.astrology_tables import RULER_BY_SIGN as RULER_BY_SIGN
from fatebridge.core.astro.astrology_tables import SIGN_LABELS_ZH as SIGN_LABELS_ZH
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.classical import (
    _build_classical_layer,
    _build_classical_patterns,
    _build_fixed_stars,
    _planetary_hours,
    _sect,
)
from fatebridge.core.astro.context_geometry import build_context_geometry
from fatebridge.core.astro.continuous_lahiri import apparent_lahiri_origin
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.ephemeris import (
    _build_planet_states,
    _planet_set,
)
from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.geometry import (
    _ayanamsha,
    _nakshatra,
    _sign_name,
    combine_longitudes,
    is_prograde_house_partition,
    native_lahiri_ayanamsha,
)
from fatebridge.core.astro.horizon import populate_horizon
from fatebridge.core.astro.house_positions import build_ecliptic_house_projection
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.layout import _relative_house_layout
from fatebridge.core.astro.midpoints import build_midpoint_analysis
from fatebridge.core.astro.orbits import FALLBACK_MODELS
from fatebridge.core.astro.parts import (
    _balance,
    _build_houses,
    _build_planet_record,
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
from fatebridge.core.astro.ptolemy import build_ptolemy_layer
from fatebridge.core.astro.reference import (
    ASPECTS,
    BALANCE_BASIS,
    DEFAULT_PLANET_ORBS,
    NODE_BODIES,
)
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.astro.rotation_policy import earth_rotation_policy
from fatebridge.core.astro.sectors import sector_profile, thirteen_sectors
from fatebridge.core.astro.seven_planets import seven_planet_view
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.terrestrial_observer import terrestrial_frame
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.astro.utc_policy import utc_definition_evidence
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.timezones import format_local_time_or_utc


def build_core_chart_payload(
    birth_info: AstroBirthInfo,
    chart_variant: str,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
    include_context_geometry: bool = False,
    context_fortune_method: str = "sect_reversing",
    include_physical_source: bool = False,
    lot_longitudes: dict[str, Fraction] | None = None,
    guolao_seasonal_anchor_policy: str | None = None,
    include_planetary_hours: bool = True,
) -> dict[str, Any]:
    """Keep one physical chart on one managed ephemeris configuration."""
    if chart_variant != "guolao_chart":
        require_resolved_birth_timezone(birth_info.timezone_source)
    else:
        pass
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
            lot_longitudes=lot_longitudes,
            guolao_seasonal_anchor_policy=guolao_seasonal_anchor_policy,
            include_planetary_hours=include_planetary_hours,
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
    lot_longitudes: dict[str, Fraction] | None = None,
    guolao_seasonal_anchor_policy: str | None = None,
    include_planetary_hours: bool = True,
) -> dict[str, Any]:
    if guolao_seasonal_anchor_policy is not None and chart_variant != "guolao_chart":
        raise ValueError(
            "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
        )
    else:
        pass
    if chart_variant == "guolao_chart":
        from fatebridge.core.guolao.guolao import build_chart

        return build_chart(
            birth_info,
            hsys=hsys,
            zodiacal=zodiacal,
            seasonal_anchor_policy=guolao_seasonal_anchor_policy,
        )
    else:
        pass
    times = birth_info.time_scales
    julian_day = times.ut1
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
    motion_metadata: dict[str, Any] = {}
    batch = _build_planet_states(
        chart_variant,
        times.jd_ut1,
        julian_day_tt=times.tt,
        source_trace=physical_trace,
        motion_metadata=motion_metadata,
    )
    planet_states = batch.states
    engine_precision = batch.precision
    engine_backend = batch.backend
    ephemeris_model = batch.physical_model
    planetary_models = batch.models
    horizon_method = populate_horizon(
        planet_states,
        julian_day,
        birth_info.longitude,
        birth_info.latitude,
        julian_day_tt=times.tt,
    )
    if engine_precision == "ephemeris_runtime_model" and (
        horizon_method != "swisseph_true_altitude"
        or layout["angle_method"] != "swisseph"
    ):
        engine_precision = "mixed_precision_runtime_model"
        engine_backend = "swisseph_api_with_approximate_geometry"
    else:
        pass
    chart_sect = _sect(planet_states["Sun"]["altitude"])
    native_planets = [
        name for name, model in planetary_models.items() if model not in FALLBACK_MODELS
    ]
    approximate_planets = [
        name for name in planetary_models if name not in native_planets
    ]
    zodiac_states = (
        native_lahiri_positions(
            native_planets,
            julian_day_ut1=times.jd_ut1,
            julian_day_tt=times.tt,
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
    else:
        pass
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
    fallback_origin_rate = 0.0
    if sidereal and approximate_planets:
        if runtime.swe is not None:
            assert times.tt is not None
            offsets = [
                (
                    native_lahiri_ayanamsha(
                        times.jd_ut1,
                        julian_day_tt=times.tt.shifted_by(step * 0.01),
                    )
                    - ayanamsha
                    + 180.0
                )
                % 360.0
                - 180.0
                for step in (-2, -1, 1, 2)
            ]
            fallback_origin_rate = (
                offsets[0] - 8 * offsets[1] + 8 * offsets[2] - offsets[3]
            ) / 0.12
        else:
            fallback_origin_rate = apparent_lahiri_origin(
                fallback_julian_day_tt(times.jd_ut1, times.tt)
            )[1]
        interpretation_states = dict(interpretation_states)
        for name in approximate_planets:
            state = interpretation_states[name]
            if "longitude_speed" not in state:
                continue
            else:
                pass
            interpretation_states[name] = {
                **state,
                "longitude_speed_tropical": state["longitude_speed"],
                "longitude_speed_sidereal_origin_correction": -fallback_origin_rate,
                "longitude_speed": state["longitude_speed"] - fallback_origin_rate,
            }
    else:
        pass
    house_projection = (
        build_ecliptic_house_projection(
            julian_day_ut1=times.ut1,
            julian_day_tt=times.tt,
            geographic_latitude=birth_info.latitude,
            geographic_longitude=birth_info.longitude,
            house_code=house_system_info["swisseph_code"],
        )
        if not is_prograde_house_partition(layout["house_cusps"])
        else None
    )
    projected_coordinates = (
        {
            planet: house_projection.coordinate(planet_states[planet]["longitude"])
            for planet in _planet_set(chart_variant)
        }
        if house_projection is not None
        else {}
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
                projected_coordinates[planet].position
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
    pole_frame = None
    if (
        abs(birth_info.latitude) == 90
        and layout["angle_method"] == "swisseph"
        and active_ut1.get() is not None
    ):
        pole_frame = terrestrial_frame(
            physical_equator(runtime.swe, times.ut1, julian_day_tt=times.tt),
            longitude=birth_info.longitude,
            latitude=birth_info.latitude,
        )
    else:
        pass
    angle_definition = geographic_pole_angle_definition(
        birth_info.latitude, frame=pole_frame
    ) or layout.get("angle_definition")
    ascendant_resolved = is_ascendant_resolved(angle_definition)
    reference_ascendant = effective_ascendant if ascendant_resolved else None
    houses_resolved = ascendant_resolved or house_system_info["key"] == "equal_mc"
    fixed_stars, fixed_star_profile = _build_fixed_stars(
        planets,
        reference_ascendant,
        effective_midheaven,
        times.jd_ut1,
        julian_day_tt=times.tt,
        sidereal=sidereal,
    )
    result: dict[str, Any] = {
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
            "birth_datetime": format_local_time_or_utc(birth_info.local_datetime),
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
                earth_rotation_policy(times.tt, times.ut1)
                if layout["angle_method"] == "swisseph"
                else None
            ),
            "julian_day_tt": times.jd_tt,
            "julian_day_ut1": times.jd_ut1,
            "future_leap_seconds_assumed_unchanged": times.future_leap_seconds_assumed_unchanged,
            "utc_definition": utc_definition_evidence(),
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
            reference_ascendant,
            states=interpretation_states,
            source_ecliptic_coordinates={
                name: (state["longitude"], state["latitude"])
                for name, state in planet_states.items()
            },
            julian_day=julian_day,
            julian_day_tt=times.tt,
            sidereal=sidereal,
            chart_sect=chart_sect,
            lot_longitudes=lot_longitudes,
            houses_resolved=houses_resolved,
        ),
        "classical_patterns": _build_classical_patterns(
            planets, aspects, interpretation_states, chart_sect=chart_sect
        ),
        "planetary_hours": (
            _planetary_hours(
                julian_day,
                birth_info.longitude,
                birth_info.latitude,
                birth_info.timezone,
                weekday_clock_basis=(
                    birth_info.clock_conversion["input_clock_basis"]
                    if birth_info.clock_conversion is not None
                    else "civil"
                ),
            )
            if include_planetary_hours
            else None
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
    else:
        pass
    if house_projection is not None:
        result["chart_profile"][
            "house_position_projection"
        ] = house_projection.metadata()
        projection_note = result["chart_profile"]["house_position_projection"].get(
            "note_zh"
        )
        if projection_note:
            result["summary"].append(projection_note)
        else:
            pass
    else:
        pass
    if layout.get("house_axis_convention") is not None:
        result["chart_profile"]["house_axis_convention"] = layout[
            "house_axis_convention"
        ]
        result["summary"].append(layout["house_axis_convention"]["note_zh"])
    else:
        pass
    if approximate_planets:
        assert batch.fallback is not None
        result["chart_profile"]["planetary_models"] = planetary_models
        result["chart_profile"]["orbital_fallback"] = {
            **batch.fallback.provenance(approximate_planets),
            "longitude_motion_origin_rate_degrees_per_day": fallback_origin_rate,
            "accuracy_certified": False,
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
                (
                    "部分天体的原生星历不可用，已保留其他天体的原生位置。"
                    if native_planets
                    else "原生星历不可用。"
                )
                + "物理天体回退使用同源JPL DE441有界系数表示、固定接收时刻光行时、"
                "有限距离太阳偏折和Lorentz光行差；月球由地月质心及地心月球位置构成，"
                "行星保留对应系统质心。统一使用长周期Vondrak标量黄道和77项章动，"
                "无原生引擎时，地平与宫轴使用匹配的源真赤道和GAST；这些计算不构成完整物理精度认证。"
                "北交点若回退，采用Moshier平根数及已发布DE431修正的TT解析平均交点；"
                "这是理论平滑点，不是JPL直接提供的观测位置。"
                "物理天体在古代和远期仍有已知超线；派生计算继承对应模型限制。"
                + (
                    "平均交点修正模型在此折点没有唯一瞬时日速，相关运动判断保留未知。"
                    if batch.fallback.uncomputed_motion_reasons
                    else ""
                )
                + (
                    "缺少原生时标时，TT采用Astronomy Engine的Espenak–Meeus模型估计，非观测钟时。"
                    if times.jd_tt is None
                    else ""
                )
            ),
        }
        result["summary"].append(
            "轨道近似天体：" + "、".join(approximate_planets) + "。"
        )
    else:
        pass
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
        else:
            pass
    else:
        pass
    result["classical"]["ptolemy"] = build_ptolemy_layer(
        {planet: state["longitude"] for planet, state in planet_states.items()},
        chart_sect,
        tropical=not sidereal,
        ascendant=reference_ascendant,
    )

    if angle_definition is not None:
        result["chart_profile"]["angle_definition"] = angle_definition
        result["summary"].append(angle_definition["note_zh"])
    else:
        pass

    if include_context_geometry:
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
            ascendant_resolved=ascendant_resolved,
            houses_resolved=houses_resolved,
            zodiac_longitudes=(
                {name: state["longitude"] for name, state in zodiac_states.items()}
                if zodiac_states is not None
                else None
            ),
            house_projection=house_projection,
            house_coordinates=projected_coordinates,
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
    else:
        pass
    if chart_variant == "chart13":
        result["thirteen_sectors"] = thirteen_sectors(effective_ascendant)
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
            else:
                pass
        else:
            pass
    else:
        pass
    if chart_variant == "hellen_chart":
        fortune = result["classical"]["lots"].get("fortune")
        result["hellenistic"] = {
            "sect": chart_sect,
            "lot_of_fortune": (
                {
                    "longitude": fortune["longitude"],
                    "sign": fortune["sign"],
                    "sign_zh": SIGN_LABELS_ZH[fortune["sign"]],
                    "degree_in_sign": fortune["degree_in_sign"],
                }
                if fortune is not None
                else None
            ),
            "ascendant_ruler": (
                RULER_BY_SIGN[_sign_name(reference_ascendant)]
                if reference_ascendant is not None
                else None
            ),
            "angular_planets": (
                [item["id"] for item in planets if item["house"] in {1, 4, 7, 10}]
                if houses_resolved
                else None
            ),
        }
    else:
        pass
    if chart_variant == "india_chart":
        result["india"] = {
            "ayanamsha": round(ayanamsha, 4),
            "rising_nakshatra": (
                _nakshatra(reference_ascendant)
                if reference_ascendant is not None
                else None
            ),
            "moon_nakshatra": next(
                (item["nakshatra"] for item in planets if item["id"] == "Moon"),
                None,
            ),
        }
    else:
        pass
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
    else:
        pass
    return result


def build_midpoint_payload(
    birth_info: AstroBirthInfo,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
) -> dict[str, Any]:
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
        times = birth_info.time_scales
        raw_states = _build_planet_states(
            "chart", times.jd_ut1, julian_day_tt=times.tt
        ).states
        ayan = (
            _ayanamsha(times.jd_ut1, julian_day_tt=times.tt)
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
