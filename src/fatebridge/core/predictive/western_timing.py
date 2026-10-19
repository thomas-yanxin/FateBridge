"""西占综合时序聚合（Western Timing）。"""

from __future__ import annotations

from fatebridge.utils.house_systems import house_system_fields

from ._common import (
    Any,
    AstroBirthInfo,
    Dict,
    List,
    Optional,
    build_lot_payloads,
    build_natal_subject,
    calculate_age_years,
    datetime,
    determine_sect,
    extract_reference_points,
    sect_label,
)
from .decennials import build_decennials_payload
from .firdaria import build_firdaria_payload
from .primary_directions import (
    build_primary_direction_chart_payload,
    build_primary_directions_payload,
)
from .profections import (
    build_annual_profection_payload,
    build_given_year_payload,
    build_monthly_profections_payload,
)
from .progressions import build_secondary_progression_payload
from .returns import build_return_payload
from .solar_arc import build_solar_arc_payload
from .transit import build_transit_payload
from .zodiacal_releasing import build_zodiacal_releasing_payload


def _resolve_western_timing_return_location(
    birth_info: AstroBirthInfo,
    *,
    return_longitude: Optional[float] = None,
    return_latitude: Optional[float] = None,
    return_timezone: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "longitude": (
            birth_info.longitude if return_longitude is None else return_longitude
        ),
        "latitude": birth_info.latitude if return_latitude is None else return_latitude,
        "timezone": return_timezone or birth_info.timezone,
    }


def _build_western_timing_natal_reference(natal_subject: Any) -> Dict[str, Any]:
    natal_reference = extract_reference_points(natal_subject)
    sect = determine_sect(natal_subject)
    natal_reference["sect"] = {"key": sect, "label": sect_label(sect)}
    natal_reference["lots"] = build_lot_payloads(natal_subject)
    return natal_reference


def _build_western_timing_analysis_context(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
    house_system: str,
    zodiac_type: str,
    return_location: Dict[str, Any],
) -> Dict[str, Any]:
    age_years = calculate_age_years(birth_info, analysis_datetime)
    return {
        "name": birth_info.name,
        "birth_place": birth_info.birth_place,
        "birth_datetime": birth_info.local_datetime.isoformat(),
        "analysis_datetime": analysis_datetime.isoformat(),
        "age_years": round(age_years, 4),
        **house_system_fields(house_system),
        "zodiac_type": zodiac_type,
        "return_location": return_location,
    }


def _build_western_timing_module_summary(
    technique: str,
    payload: Dict[str, Any],
    *,
    analysis_datetime: datetime,
) -> str:
    prefix = analysis_datetime.strftime("%Y-%m-%d")

    if technique == "solarreturn":
        return f"{prefix} 西占太阳返照：返照发生于 {payload['return_datetime']}。"

    if technique == "lunarreturn":
        return f"{prefix} 西占月亮返照：返照发生于 {payload['return_datetime']}。"

    if technique == "transit":
        top_hit = payload["hits"][0] if payload.get("hits") else None
        summary = f"{prefix} 西占行运：行运太阳 {payload['sun']['sign_label']}"
        if top_hit:
            summary += (
                f"，最紧密命中 "
                f"{top_hit['source_label']}{top_hit['aspect_label']}{top_hit['target_label']}"
            )
        return summary + "。"

    if technique == "solararc":
        return f"{prefix} 西占太阳弧：当前太阳弧 {payload['arc_degrees']:.2f}°。"

    if technique == "givenyear":
        annual_profection = payload.get("annual_profection", {})
        return (
            f"{prefix} 西占指定年盘：上升 {payload['ascendant']['sign_label']}，"
            f"年小限落第{annual_profection.get('activated_house')}宫"
            f"{annual_profection.get('activated_sign_label')}。"
        )

    if technique == "profection":
        return (
            f"{prefix} 西占年小限：落第{payload['activated_house']}宫"
            f"{payload['activated_sign_label']}，主星 {payload['lord_label']}。"
        )

    if technique == "primarydirect":
        return (
            f"{prefix} 西占主限：{payload['direction_mode_label']} "
            f"{payload['time_key_label']} {payload['coordinate_label']} "
            f"{payload['current_arc_degrees']:.2f}°。"
        )

    if technique == "primarydirchart":
        return (
            f"{prefix} 西占主限法盘：{payload['direction_mode_label']} "
            f"{payload['time_key_label']} {payload['coordinate_label']} "
            f"{payload['current_arc_degrees']:.2f}°。"
        )

    if technique in {"zodialrelease", "zodiacal_releasing"}:
        spirit_level_1 = payload["spirit"].get("current_level_1") or {}
        return (
            f"{prefix} 西占黄道释放：Spirit L1 "
            f"{spirit_level_1.get('sign_label', '未知')}。"
        )

    if technique == "firdaria":
        current_major = payload.get("current_major") or {}
        current_sub = payload.get("current_sub") or {}
        return (
            f"{prefix} 西占法达星限："
            f"{current_major.get('planet_label', '未知')}/"
            f"{current_sub.get('planet_label', '未知')}。"
        )

    if technique == "decennials":
        current_level_1 = payload.get("current_level_1") or {}
        current_level_2 = payload.get("current_level_2") or {}
        summary = (
            f"{prefix} 西占十年星限：L1 "
            f"{current_level_1.get('planet_label', '未知')}"
        )
        if current_level_2:
            summary += f"，L2 {current_level_2.get('planet_label', '未知')}"
        return summary + "。"

    raise ValueError(f"Unsupported western timing technique: {technique}")


def build_western_timing_module_payload(
    birth_info: AstroBirthInfo,
    *,
    technique: str,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: Optional[float] = None,
    return_latitude: Optional[float] = None,
    return_timezone: Optional[str] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: Optional[List[int]] = None,
    show_pd_bounds: bool = True,
) -> Dict[str, Any]:
    natal_subject = build_natal_subject(
        birth_info,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    natal_reference = _build_western_timing_natal_reference(natal_subject)
    return_location = _resolve_western_timing_return_location(
        birth_info,
        return_longitude=return_longitude,
        return_latitude=return_latitude,
        return_timezone=return_timezone,
    )
    analysis_context = _build_western_timing_analysis_context(
        birth_info,
        analysis_datetime=analysis_datetime,
        house_system=house_system,
        zodiac_type=zodiac_type,
        return_location=return_location,
    )

    result: Dict[str, Any] = {
        "analysis_type": "西占推运与返照分析",
        "analysis_context": analysis_context,
        "natal_reference": natal_reference,
    }

    if technique in {"solarreturn", "lunarreturn"}:
        return_key = "solar_return" if technique == "solarreturn" else "lunar_return"
        returns_payload = build_return_payload(
            natal_subject,
            analysis_datetime=analysis_datetime,
            return_longitude=return_location["longitude"],
            return_latitude=return_location["latitude"],
            return_timezone=return_location["timezone"],
            include=[return_key],
        )
        result["returns"] = returns_payload
        result["summary"] = _build_western_timing_module_summary(
            technique,
            returns_payload[return_key],
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "transit":
        transit_payload = build_transit_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            transit_longitude=return_location["longitude"],
            transit_latitude=return_location["latitude"],
            transit_timezone=return_location["timezone"],
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        result["transits"] = {"current_transit": transit_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            transit_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "solararc":
        progression_payload = build_secondary_progression_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        solar_arc_payload = build_solar_arc_payload(
            natal_subject,
            progression_payload["subject"],
        )
        result["directions"] = {"solar_arc": solar_arc_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            solar_arc_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "primarydirect":
        primary_directions_payload = build_primary_directions_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            pd_aspects=pd_aspects,
        )
        result["directions"] = {"primary_directions": primary_directions_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            primary_directions_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "primarydirchart":
        primary_directions_payload = build_primary_directions_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            pd_aspects=pd_aspects,
        )
        primary_direction_chart_payload = build_primary_direction_chart_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            coordinate_system=primary_directions_payload["coordinate_system"],
            coordinate_label=primary_directions_payload["coordinate_label"],
            approximation=primary_directions_payload["approximation"],
            approximation_label=primary_directions_payload["approximation_label"],
            coordinate_precision=primary_directions_payload["coordinate_precision"],
            coordinate_backend=primary_directions_payload["coordinate_backend"],
            coordinate_diagnostics=primary_directions_payload["coordinate_diagnostics"],
            coordinate_points=primary_directions_payload["coordinate_points"],
            coordinate_lots=primary_directions_payload["coordinate_lots"],
            current_coordinate_points=primary_directions_payload[
                "current_coordinate_points"
            ],
            current_coordinate_lots=primary_directions_payload[
                "current_coordinate_lots"
            ],
            current_arc_degrees=primary_directions_payload["current_arc_degrees"],
            current_hits=primary_directions_payload["current_window"],
            show_pd_bounds=show_pd_bounds,
        )
        result["directions"] = {
            "primary_direction_chart": primary_direction_chart_payload
        }
        result["summary"] = _build_western_timing_module_summary(
            technique,
            primary_direction_chart_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "profection":
        profection_payload = build_annual_profection_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
        )
        result["time_lords"] = {"annual_profection": profection_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            profection_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "givenyear":
        profection_payload = build_annual_profection_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
        )
        given_year_payload = build_given_year_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            annual_profection=profection_payload,
            return_longitude=return_location["longitude"],
            return_latitude=return_location["latitude"],
            return_timezone=return_location["timezone"],
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        result["directions"] = {"given_year": given_year_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            given_year_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique in {"zodialrelease", "zodiacal_releasing"}:
        zodiacal_releasing_payload = build_zodiacal_releasing_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
        )
        result["time_lords"] = {"zodiacal_releasing": zodiacal_releasing_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            zodiacal_releasing_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "firdaria":
        firdaria_payload = build_firdaria_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            firdaria_night_order=firdaria_night_order,
            firdaria_year_basis=firdaria_year_basis,
        )
        result["time_lords"] = {"firdaria": firdaria_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            firdaria_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    if technique == "decennials":
        decennials_payload = build_decennials_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
        )
        result["time_lords"] = {"decennials": decennials_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            decennials_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

    raise ValueError(f"Unsupported western timing technique: {technique}")


def build_western_timing_payload(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: Optional[float] = None,
    return_latitude: Optional[float] = None,
    return_timezone: Optional[str] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: Optional[List[int]] = None,
    show_pd_bounds: bool = True,
) -> Dict[str, Any]:
    natal_subject = build_natal_subject(
        birth_info,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    natal_reference = extract_reference_points(natal_subject)
    sect = determine_sect(natal_subject)
    natal_reference["sect"] = {"key": sect, "label": sect_label(sect)}
    natal_reference["lots"] = build_lot_payloads(natal_subject)

    effective_return_longitude = (
        birth_info.longitude if return_longitude is None else return_longitude
    )
    effective_return_latitude = (
        birth_info.latitude if return_latitude is None else return_latitude
    )
    effective_return_timezone = return_timezone or birth_info.timezone

    returns_payload = build_return_payload(
        natal_subject,
        analysis_datetime=analysis_datetime,
        return_longitude=effective_return_longitude,
        return_latitude=effective_return_latitude,
        return_timezone=effective_return_timezone,
    )
    progression_payload = build_secondary_progression_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    progressed_subject = progression_payload.pop("subject")
    solar_arc_payload = build_solar_arc_payload(natal_subject, progressed_subject)
    primary_directions_payload = build_primary_directions_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
    )
    primary_direction_chart_payload = build_primary_direction_chart_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        coordinate_system=primary_directions_payload["coordinate_system"],
        coordinate_label=primary_directions_payload["coordinate_label"],
        approximation=primary_directions_payload["approximation"],
        approximation_label=primary_directions_payload["approximation_label"],
        coordinate_precision=primary_directions_payload["coordinate_precision"],
        coordinate_backend=primary_directions_payload["coordinate_backend"],
        coordinate_diagnostics=primary_directions_payload["coordinate_diagnostics"],
        coordinate_points=primary_directions_payload["coordinate_points"],
        coordinate_lots=primary_directions_payload["coordinate_lots"],
        current_coordinate_points=primary_directions_payload[
            "current_coordinate_points"
        ],
        current_coordinate_lots=primary_directions_payload["current_coordinate_lots"],
        current_arc_degrees=primary_directions_payload["current_arc_degrees"],
        current_hits=primary_directions_payload["current_window"],
        show_pd_bounds=show_pd_bounds,
    )
    profection_payload = build_annual_profection_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
    )
    given_year_payload = build_given_year_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        annual_profection=profection_payload,
        return_longitude=effective_return_longitude,
        return_latitude=effective_return_latitude,
        return_timezone=effective_return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    firdaria_payload = build_firdaria_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        firdaria_night_order=firdaria_night_order,
        firdaria_year_basis=firdaria_year_basis,
    )
    decennials_payload = build_decennials_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
    )
    zodiacal_releasing_payload = build_zodiacal_releasing_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
    )
    transit_payload = build_transit_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        transit_longitude=effective_return_longitude,
        transit_latitude=effective_return_latitude,
        transit_timezone=effective_return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )

    age_years = calculate_age_years(birth_info, analysis_datetime)
    zr_spirit_current = zodiacal_releasing_payload["spirit"]["current_level_1"]
    transit_top_hit = transit_payload["hits"][0] if transit_payload["hits"] else None
    summary = (
        f"{analysis_datetime.strftime('%Y-%m-%d')} 西占时运："
        f"太阳返照 {returns_payload['solar_return']['return_datetime']}，"
        f"月返 {returns_payload['lunar_return']['return_datetime']}，"
        f"主限 {primary_directions_payload['direction_mode_label']} "
        f"{primary_directions_payload['time_key_label']} "
        f"{primary_directions_payload['coordinate_label']}"
        f" {primary_directions_payload['current_arc_degrees']:.2f}°，"
        f"指定年盘上升 {given_year_payload['ascendant']['sign_label']}，"
        f"年小限落第{profection_payload['activated_house']}宫"
        f"{profection_payload['activated_sign_label']}，"
        f"法达 {firdaria_payload['current_major']['planet_label']}"
        f"/{(firdaria_payload['current_sub'] or {}).get('planet_label', '无小运')}，"
        f"Spirit 黄道释放 L1 {zr_spirit_current['sign_label']}，"
        f"太阳弧 {solar_arc_payload['arc_degrees']:.2f}°，"
        f"行运太阳 {transit_payload['sun']['sign_label']}"
        + (
            f"，最紧密命中 "
            f"{transit_top_hit['source_label']}{transit_top_hit['aspect_label']}{transit_top_hit['target_label']}"
            if transit_top_hit
            else ""
        )
        + "。"
    )

    return {
        "analysis_type": "西占推运与返照分析",
        "analysis_context": {
            "name": birth_info.name,
            "birth_place": birth_info.birth_place,
            "birth_datetime": birth_info.local_datetime.isoformat(),
            "analysis_datetime": analysis_datetime.isoformat(),
            "age_years": round(age_years, 4),
            **house_system_fields(house_system),
            "zodiac_type": zodiac_type,
            "return_location": {
                "longitude": effective_return_longitude,
                "latitude": effective_return_latitude,
                "timezone": effective_return_timezone,
            },
        },
        "natal_reference": natal_reference,
        "returns": returns_payload,
        "transits": {
            "current_transit": transit_payload,
        },
        "directions": {
            "secondary_progression": progression_payload,
            "solar_arc": solar_arc_payload,
            "primary_directions": primary_directions_payload,
            "primary_direction_chart": primary_direction_chart_payload,
            "given_year": given_year_payload,
        },
        "time_lords": {
            "annual_profection": profection_payload,
            "firdaria": firdaria_payload,
            "decennials": decennials_payload,
            "zodiacal_releasing": zodiacal_releasing_payload,
        },
        "summary": summary,
    }
