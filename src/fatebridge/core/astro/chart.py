"""Natal/chart-variant and midpoint payload assembly."""

from __future__ import annotations

import math
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
from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.ephemeris import (
    _build_planet_states,
    _planet_set,
    fast_swe_call,
)
from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.geometry import (
    _ayanamsha,
    _nakshatra,
    _sign_name,
    combine_longitudes,
    is_prograde_house_partition,
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
    RELATIVE_HOUSE_SYSTEM_SPECS,
)
from fatebridge.core.astro.reference_frames import analytic_ecliptic_frame
from fatebridge.core.astro.sectors import sector_profile, thirteen_sectors
from fatebridge.core.astro.seven_planets import seven_planet_view
from fatebridge.core.astro.solar_position import apparent_position_policy
from fatebridge.core.astro.terrestrial_observer import terrestrial_frame
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.zodiac import native_lahiri_positions
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.guolao.guolao import build_chart
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
    include_classical: bool = True,
    include_fixed_stars: bool = True,
    include_aspects: bool = True,
    node_mode: str = "mean",
    high_latitude_fallback: str = "error",
    include_minor_aspects: bool = False,
    max_aspects: int | None = None,
    extra_bodies: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
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
            lot_longitudes=lot_longitudes,
            guolao_seasonal_anchor_policy=guolao_seasonal_anchor_policy,
            include_planetary_hours=include_planetary_hours,
            include_classical=include_classical,
            include_fixed_stars=include_fixed_stars,
            include_aspects=include_aspects,
            node_mode=node_mode,
            high_latitude_fallback=high_latitude_fallback,
            include_minor_aspects=include_minor_aspects,
            max_aspects=max_aspects,
            extra_bodies=extra_bodies,
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
    include_classical: bool = True,
    include_fixed_stars: bool = True,
    include_aspects: bool = True,
    node_mode: str = "mean",
    high_latitude_fallback: str = "error",
    include_minor_aspects: bool = False,
    max_aspects: int | None = None,
    extra_bodies: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    if guolao_seasonal_anchor_policy is not None and chart_variant != "guolao_chart":
        raise ValueError(
            "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
        )
    if chart_variant == "guolao_chart":
        return build_chart(
            birth_info,
            hsys=hsys,
            zodiacal=zodiacal,
            seasonal_anchor_policy=guolao_seasonal_anchor_policy,
        )
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
        high_latitude_fallback=high_latitude_fallback,
    )
    fallback_system = layout.get("fallback_house_system")
    if fallback_system == "whole_sign":
        house_system_info = {
            **house_system_info,
            "key": "whole_sign",
            "value": 0,
            "label_zh": RELATIVE_HOUSE_SYSTEM_SPECS[0]["label_zh"],
            "source": "high_latitude_fallback",
        }
    elif fallback_system == "porphyry":
        house_system_info = {
            **house_system_info,
            "key": "porphyry",
            "value": None,
            "label_zh": "Porphyry",
            "source": "high_latitude_fallback",
        }
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
        node_mode=node_mode,
        extra_bodies=extra_bodies,
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
            motion_metadata=motion_metadata,
            source_trace=physical_trace,
            node_mode=node_mode,
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
                **state,
                **zodiac_states[name],
            }
            for name, state in planet_states.items()
        }
        if zodiac_states is not None
        else planet_states
    )
    obliquity: float | None = None
    if runtime.swe is not None:
        try:
            ecl_angles, ecl_flag = fast_swe_call(
                "calc",
                (
                    TTInstant.from_value(times.tt).as_float()
                    if times.tt is not None
                    else times.jd_ut1
                ),
                runtime.swe.ECL_NUT,
            )
            if ecl_flag >= 0:
                obliquity = float(ecl_angles[0])
        except Exception:
            obliquity = None
    if obliquity is None:
        frame_tt = (
            times.tt
            if times.tt is not None
            else fallback_julian_day_tt(times.jd_ut1, None)
        )
        obliquity = analytic_ecliptic_frame(frame_tt).true_obliquity
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
    angle_definition = geographic_pole_angle_definition(
        birth_info.latitude, frame=pole_frame
    ) or layout.get("angle_definition")
    ascendant_resolved = is_ascendant_resolved(angle_definition)
    if abs(birth_info.latitude) == 90.0 and not include_context_geometry:
        ascendant_resolved = False
    reference_ascendant = effective_ascendant if ascendant_resolved else None
    houses_resolved = ascendant_resolved or house_system_info["key"] == "equal_mc"
    planet_names = _planet_set(chart_variant, extra_bodies=extra_bodies)
    house_projection = (
        build_ecliptic_house_projection(
            julian_day_ut1=times.ut1,
            julian_day_tt=times.tt,
            geographic_latitude=birth_info.latitude,
            geographic_longitude=birth_info.longitude,
            house_code=house_system_info["swisseph_code"],
        )
        if houses_resolved
        and house_system_info.get("swisseph_code") is not None
        and not is_prograde_house_partition(layout["house_cusps"])
        else None
    )
    projected_coordinates = (
        {
            planet: house_projection.coordinate(planet_states[planet]["longitude"])
            for planet in planet_names
            if planet in planet_states
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
            longitude_speed=interpretation_states[planet].get("longitude_speed"),
            declination=planet_states[planet].get("declination"),
            obliquity=obliquity,
            houses_resolved=houses_resolved,
        )
        for planet in planet_names
        if planet in planet_states
    ]
    all_aspect_evidence = (
        _build_aspects(
            planets,
            include_evidence=True,
            include_minor_aspects=include_minor_aspects,
        )
        if include_aspects
        else []
    )
    aspects_total_count = len(all_aspect_evidence)
    aspect_evidence = (
        all_aspect_evidence[:max_aspects]
        if max_aspects is not None
        else all_aspect_evidence
    )
    all_aspects = [
        {key: item[key] for key in ("planet_a", "planet_b", "aspect", "orb")}
        for item in all_aspect_evidence
    ]
    aspects = all_aspects[:max_aspects] if max_aspects is not None else all_aspects
    house_list = (
        _build_houses(
            reference_ascendant,
            house_system_info["key"],
            house_cusps=house_cusps,
            midheaven=effective_midheaven,
        )
        if houses_resolved
        else []
    )
    if include_fixed_stars:
        fixed_stars, fixed_star_profile = _build_fixed_stars(
            planets,
            reference_ascendant,
            effective_midheaven,
            times.jd_ut1,
            julian_day_tt=times.tt,
            sidereal=sidereal,
        )
    else:
        fixed_stars, fixed_star_profile = [], {}
    ascendant_angle: dict[str, Any] = (
        {
            "longitude": reference_ascendant,
            "sign": _sign_name(reference_ascendant),
            "sign_zh": SIGN_LABELS_ZH[_sign_name(reference_ascendant)],
        }
        if reference_ascendant is not None
        else {
            "longitude": None,
            "sign": None,
            "sign_zh": None,
            "status": "underdetermined_ascendant",
        }
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
            "house_system": house_system_info["key"],
            "house_system_code": house_system_info["value"],
            "house_system_label_zh": house_system_info["label_zh"],
            "house_system_source": house_system_info.get("source", "explicit"),
            "node_mode": node_mode,
            "high_latitude_fallback": high_latitude_fallback,
            "tradition": chart_variant in {"hellen_chart", "guolao_chart"},
            "engine_precision": engine_precision,
            "engine_backend": engine_backend,
            "ephemeris_model": ephemeris_model,
            "calendar": "proleptic_gregorian",
            "time_scale": times.method,
            "julian_day_tt": times.jd_tt,
            "julian_day_ut1": times.jd_ut1,
            "horizon_method": horizon_method,
            "angle_method": layout["angle_method"],
            "sect_convention": "geocentric_solar_centre_true_altitude_ge_0",
            "aspect_policy": {
                "planet_orbs": dict(DEFAULT_PLANET_ORBS),
                "fallback_orb": 6.0,
                "exact_angles": dict(ASPECTS),
                "include_minor_aspects": include_minor_aspects,
            },
            **(
                {
                    "aspects_total_count": aspects_total_count,
                    "aspects_returned_count": len(aspects),
                }
                if include_aspects
                else {}
            ),
        },
        "angles": {
            "ascendant": ascendant_angle,
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
        "classical": (
            _build_classical_layer(
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
            )
            if include_classical
            else {}
        ),
        "classical_patterns": (
            _build_classical_patterns(
                planets, all_aspects, interpretation_states, chart_sect=chart_sect
            )
            if include_classical and include_aspects
            else []
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
    result["chart_profile"]["fixed_stars"] = {
        k: v
        for k, v in fixed_star_profile.items()
        if k in {"model_id", "status", "orb_limit", "unavailable_reason"}
    }
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
        assert batch.fallback is not None
        result["chart_profile"]["planetary_models"] = planetary_models
        result["chart_profile"]["orbital_fallback"] = {
            **batch.fallback.provenance(approximate_planets),
            "approximate_planets": approximate_planets,
            "accuracy_certified": False,
            "note_zh": "轨道近似天体：" + "、".join(approximate_planets) + "。",
        }
        result["summary"].append(
            "轨道近似天体：" + "、".join(approximate_planets) + "。"
        )
    elif include_physical_source:
        result["chart_profile"]["planetary_models"] = planetary_models
    if include_classical:
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
                **(
                    {
                        "sidereal_planetary_methods": {
                            name: (
                                "swisseph_calc_sidereal_lahiri"
                                if name in native_planets
                                else "ayanamsha_offset_approximation"
                            )
                            for name in planetary_models
                        }
                    }
                    if approximate_planets or include_physical_source
                    else {}
                ),
            }
        )
    if include_classical:
        result["classical"]["ptolemy"] = build_ptolemy_layer(
            {planet: state["longitude"] for planet, state in planet_states.items()},
            chart_sect,
            tropical=not sidereal,
            ascendant=reference_ascendant,
        )

    if angle_definition is not None:
        result["chart_profile"]["angle_definition"] = angle_definition
        result["summary"].append(angle_definition["note_zh"])

    if include_context_geometry:
        result["context_geometry"] = build_context_geometry(
            planet_states,
            planet_names,
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
    source = physical_trace.finish()
    if (
        chart_variant == "chart13"
        or include_physical_source
        or configured_jpl_file() is not None
    ):
        result["chart_profile"]["physical_ephemeris_source"] = source
    if include_physical_source:
        result["chart_profile"]["apparent_position_policy"] = apparent_position_policy(
            times.jd_tt, planetary_models, physical_trace
        )
    return result


def build_midpoint_payload(
    birth_info: AstroBirthInfo,
    *,
    hsys: Any = None,
    zodiacal: Any = None,
    high_latitude_fallback: str = "error",
    dial_degrees: str | None = None,
    sensitive_point_query: str | None = None,
    max_higher_factor_contacts: int | None = 12,
) -> dict[str, Any]:
    base_chart = build_core_chart_payload(
        birth_info,
        "chart",
        hsys=hsys,
        zodiacal=zodiacal,
        include_planetary_hours=False,
        include_classical=False,
        include_fixed_stars=False,
        include_aspects=False,
        high_latitude_fallback=high_latitude_fallback,
    )
    slim_base_chart = {
        k: v
        for k, v in base_chart.items()
        if k
        in {
            "person_info",
            "chart_profile",
            "angles",
            "houses",
            "planets",
            "summary",
        }
    }
    engine_profile = _derive_engine_profile(base_chart.get("chart_profile", {}))
    midpoint_analysis = build_midpoint_analysis(
        birth_info,
        base_chart,
        dial_degrees=dial_degrees,
        sensitive_point_query=sensitive_point_query,
        max_higher_factor_contacts=max_higher_factor_contacts,
    )
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
        "base_chart": slim_base_chart,
        "planets": base_chart["planets"],
        "midpoint_analysis": midpoint_analysis,
        "midpoints": midpoints,
        "midpoint_aspects": midpoint_aspects,
    }
