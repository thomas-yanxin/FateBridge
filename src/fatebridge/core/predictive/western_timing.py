"""西占综合时序聚合（Western Timing）。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    build_lot_payloads,
    build_natal_subject,
    calculate_age_years,
    determine_sect,
    extract_reference_points,
    sect_label,
)
from fatebridge.core.predictive.decennials import build_decennials_payload
from fatebridge.core.predictive.firdaria import build_firdaria_payload
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.core.predictive.primary_directions import (
    build_primary_direction_analysis,
    build_primary_direction_chart_payload,
    build_primary_directions_payload,
)
from fatebridge.core.predictive.profections import (
    build_annual_profection_payload,
    build_given_year_payload,
)
from fatebridge.core.predictive.progressions import build_secondary_progression_payload
from fatebridge.core.predictive.returns import build_return_payload
from fatebridge.core.predictive.solar_arc import build_solar_arc_payload
from fatebridge.core.predictive.transit import build_transit_payload
from fatebridge.core.predictive.zodiacal_releasing import (
    _unresolved_lot_payload,
    build_zodiacal_releasing_payload,
)
from fatebridge.utils.house_systems import house_system_fields


def _resolve_western_timing_return_location(
    birth_info: AstroBirthInfo,
    *,
    return_longitude: float | None = None,
    return_latitude: float | None = None,
    return_timezone: str | None = None,
) -> dict[str, Any]:
    return {
        "longitude": (
            birth_info.longitude if return_longitude is None else return_longitude
        ),
        "latitude": birth_info.latitude if return_latitude is None else return_latitude,
        "timezone": return_timezone or birth_info.timezone,
    }


def _build_western_timing_natal_reference(
    natal_subject: NativeSubject,
) -> dict[str, Any]:
    natal_reference = extract_reference_points(natal_subject)
    natal_reference["calculation_basis"] = natal_subject.calculation_basis
    sect = determine_sect(natal_subject)
    natal_reference["sect"] = {"key": sect, "label": sect_label(sect)}
    if is_ascendant_resolved(natal_subject):
        natal_reference["lots"] = build_lot_payloads(natal_subject)
    else:
        natal_reference["lots"] = {
            lot_key: _unresolved_lot_payload(lot_key)
            for lot_key in ("lot_of_fortune", "lot_of_spirit")
        }
    return natal_reference


def _build_western_timing_analysis_context(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
    house_system: str,
    zodiac_type: str,
    return_location: dict[str, Any],
) -> dict[str, Any]:
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


def _build_primary_direction_pair(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
    pd_method: str,
    pd_time_key: str,
    pd_type: int,
    pd_aspects: list[int] | None,
    show_pd_bounds: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    directions = build_primary_direction_analysis(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
    )
    primary_directions_payload = directions.payload
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
        current_arc_degrees=directions.current_arc,
        current_hits=primary_directions_payload["current_window"],
        show_pd_bounds=show_pd_bounds,
    )
    return primary_directions_payload, primary_direction_chart_payload


def _return_event_label(payload: Mapping[str, Any]) -> str:
    return (
        payload["return_datetime"]
        or payload["return_datetime_utc"]
        or f"TT JD {payload['solver']['julian_day_tt']}"
    )


def _build_western_timing_module_summary(
    technique: str,
    payload: Mapping[str, Any],
    *,
    analysis_datetime: datetime,
) -> str:
    prefix = analysis_datetime.strftime("%Y-%m-%d")

    if technique in {"solarreturn", "lunarreturn"}:
        body = "太阳" if technique == "solarreturn" else "月亮"
        event_label = _return_event_label(payload)
        return f"{prefix} 西占{body}返照：返照发生于 {event_label}。"
    else:
        pass

    if technique == "transit":
        top_hit = payload["hits"][0] if payload.get("hits") else None
        summary = f"{prefix} 西占行运：行运太阳 {payload['sun']['sign_label']}"
        if top_hit:
            summary += (
                f"，最紧密命中 "
                f"{top_hit['source_label']}{top_hit['aspect_label']}{top_hit['target_label']}"
            )
        else:
            pass
        return summary + "。"
    else:
        pass

    if technique == "solararc":
        return f"{prefix} 西占太阳弧：当前太阳弧 {payload['arc_degrees']:.2f}°。"
    else:
        pass

    if technique == "givenyear":
        annual_profection = payload.get("annual_profection", {})
        asc_label = (payload.get("ascendant") or {}).get("sign_label") or "未解析"
        activated_sign_label = annual_profection.get("activated_sign_label")
        if activated_sign_label:
            return (
                f"{prefix} 西占指定年盘：上升 {asc_label}，"
                f"年小限落第{annual_profection.get('activated_house')}宫"
                f"{activated_sign_label}。"
            )
        else:
            pass
        return (
            f"{prefix} 西占指定年盘：上升 {asc_label}，"
            f"年小限落第{annual_profection.get('activated_house')}宫"
            "（本命上升未解析，落座与主星待定）。"
        )
    else:
        pass

    if technique == "profection":
        if (
            payload.get("status") == "underdetermined_ascendant"
            or payload.get("activated_sign_label") is None
        ):
            return (
                f"{prefix} 西占年小限：落第{payload['activated_house']}宫"
                "（本命上升未解析，落座与主星待定）。"
            )
        else:
            pass
        return (
            f"{prefix} 西占年小限：落第{payload['activated_house']}宫"
            f"{payload['activated_sign_label']}，主星 {payload['lord_label']}。"
        )
    else:
        pass

    if technique == "primarydirect":
        return (
            f"{prefix} 西占主限：{payload['direction_mode_label']} "
            f"{payload['time_key_label']} {payload['coordinate_label']} "
            f"{payload['current_arc_degrees']:.2f}°。"
        )
    else:
        pass

    if technique == "primarydirchart":
        return (
            f"{prefix} 西占主限法盘：{payload['direction_mode_label']} "
            f"{payload['time_key_label']} {payload['coordinate_label']} "
            f"{payload['current_arc_degrees']:.2f}°。"
        )
    else:
        pass

    if technique in {"zodialrelease", "zodiacal_releasing"}:
        if payload.get("status") == "underdetermined_ascendant":
            return f"{prefix} 西占黄道释放：本命上升未解析，无法计算福点与精神点释放。"
        else:
            pass
        spirit_level_1 = payload["spirit"].get("current_level_1") or {}
        return (
            f"{prefix} 西占黄道释放：Spirit L1 "
            f"{spirit_level_1.get('sign_label', '未知')}。"
        )
    else:
        pass

    if technique == "firdaria":
        current_major = payload.get("current_major") or {}
        current_sub = payload.get("current_sub") or {}
        return (
            f"{prefix} 西占法达星限："
            f"{current_major.get('planet_label', '未知')}/"
            f"{current_sub.get('planet_label', '未知')}。"
        )
    else:
        pass

    if technique == "decennials":
        current_level_1 = payload.get("current_level_1") or {}
        current_level_2 = payload.get("current_level_2") or {}
        summary = (
            f"{prefix} 西占十年星限：L1 "
            f"{current_level_1.get('planet_label', '未知')}"
        )
        if current_level_2:
            summary += f"，L2 {current_level_2.get('planet_label', '未知')}"
        else:
            pass
        return summary + "。"
    else:
        pass

    raise ValueError(f"Unsupported western timing technique: {technique}")


def build_western_timing_module_payload(
    birth_info: AstroBirthInfo,
    *,
    technique: str,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: float | None = None,
    return_latitude: float | None = None,
    return_timezone: str | None = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    show_pd_bounds: bool = True,
) -> dict[str, Any]:
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

    result: dict[str, Any] = {
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
    else:
        pass

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
    else:
        pass

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
            progression_options=progression_payload["calculation_options"],
        )
        result["directions"] = {"solar_arc": solar_arc_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            solar_arc_payload,
            analysis_datetime=analysis_datetime,
        )
        return result
    else:
        pass

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
    else:
        pass

    if technique == "primarydirchart":
        _, primary_direction_chart_payload = _build_primary_direction_pair(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            pd_aspects=pd_aspects,
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
    else:
        pass

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
    else:
        pass

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
    else:
        pass

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
    else:
        pass

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
    else:
        pass

    if technique == "decennials":
        # Period allocation uses sect and natal longitude order. Keep chart
        # provenance without embedding the per-planet derivative sampling trace.
        basis = natal_subject.calculation_basis
        natal_reference["calculation_basis"] = {
            **basis,
            "longitude_motion": {
                key: value
                for key, value in basis["longitude_motion"].items()
                if key != "complete_position_derivatives"
            },
        }
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
    else:
        pass

    raise ValueError(f"Unsupported western timing technique: {technique}")


def build_western_timing_payload(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: float | None = None,
    return_latitude: float | None = None,
    return_timezone: str | None = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    show_pd_bounds: bool = True,
) -> dict[str, Any]:
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

    returns_payload = build_return_payload(
        natal_subject,
        analysis_datetime=analysis_datetime,
        return_longitude=return_location["longitude"],
        return_latitude=return_location["latitude"],
        return_timezone=return_location["timezone"],
    )
    progression_payload = build_secondary_progression_payload(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    progressed_subject = progression_payload.pop("subject")
    solar_arc_payload = build_solar_arc_payload(
        natal_subject,
        progressed_subject,
        progression_options=progression_payload["calculation_options"],
    )
    primary_directions_payload, primary_direction_chart_payload = (
        _build_primary_direction_pair(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            pd_aspects=pd_aspects,
            show_pd_bounds=show_pd_bounds,
        )
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
        return_longitude=return_location["longitude"],
        return_latitude=return_location["latitude"],
        return_timezone=return_location["timezone"],
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
        transit_longitude=return_location["longitude"],
        transit_latitude=return_location["latitude"],
        transit_timezone=return_location["timezone"],
        house_system=house_system,
        zodiac_type=zodiac_type,
    )

    firdaria_current = firdaria_payload["current_major"]
    zr_spirit_current = (zodiacal_releasing_payload.get("spirit") or {}).get(
        "current_level_1"
    )
    zr_label = (
        zr_spirit_current["sign_label"]
        if zr_spirit_current
        else (
            "未解析(ASC未定)"
            if zodiacal_releasing_payload.get("status") == "underdetermined_ascendant"
            else "未知"
        )
    )
    given_year_asc_label = (given_year_payload.get("ascendant") or {}).get(
        "sign_label"
    ) or "未解析"
    profection_sign_label = (
        profection_payload.get("activated_sign_label") or "（ASC未定）"
    )
    transit_top_hit = transit_payload["hits"][0] if transit_payload["hits"] else None
    summary = (
        f"{analysis_datetime.strftime('%Y-%m-%d')} 西占时运："
        f"太阳返照 {_return_event_label(returns_payload['solar_return'])}，"
        f"月返 {_return_event_label(returns_payload['lunar_return'])}，"
        f"主限 {primary_directions_payload['direction_mode_label']} "
        f"{primary_directions_payload['time_key_label']} "
        f"{primary_directions_payload['coordinate_label']}"
        f" {primary_directions_payload['current_arc_degrees']:.2f}°，"
        f"指定年盘上升 {given_year_asc_label}，"
        f"年小限落第{profection_payload['activated_house']}宫"
        f"{profection_sign_label}，"
        f"法达 {firdaria_current['planet_label'] if firdaria_current else '未知'}"
        f"/{(firdaria_payload['current_sub'] or {}).get('planet_label', '无小运')}，"
        f"Spirit 黄道释放 L1 {zr_label}，"
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
        "analysis_context": _build_western_timing_analysis_context(
            birth_info,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type=zodiac_type,
            return_location=return_location,
        ),
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
