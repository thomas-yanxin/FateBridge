"""西占综合时序聚合（Western Timing）。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from fatebridge.core.astro.angle_definitions import is_ascendant_resolved
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    build_lot_payloads,
    build_natal_subject,
    build_subject,
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
from fatebridge.core.predictive.transit import (
    build_transit_analysis,
    build_transit_payload,
)
from fatebridge.core.predictive.zodiacal_releasing import (
    _unresolved_lot_payload,
    build_zodiacal_releasing_payload,
)
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.house_systems import house_system_fields
from fatebridge.utils.timezones import parse_timezone_name

ALL_WESTERN_TIMING_TECHNIQUES = frozenset(
    {
        "firdaria",
        "profection",
        "solar_return",
        "lunar_return",
        "transit",
        "given_year",
        "secondary_progression",
        "solar_arc",
        "primary_directions",
        "primary_direction_chart",
        "decennials",
        "zodiacal_releasing",
    }
)


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
    *,
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    natal_reference = extract_reference_points(natal_subject)
    sect = determine_sect(natal_subject)
    natal_reference["sect"] = {"key": sect, "label": sect_label(sect)}
    if is_ascendant_resolved(natal_subject):
        natal_reference["lots"] = (
            {key: dict(value) for key, value in natal_lots.items()}
            if natal_lots is not None
            else build_lot_payloads(natal_subject)
        )
    else:
        natal_reference["lots"] = {
            lot_key: _unresolved_lot_payload(lot_key)
            for lot_key in ("lot_of_fortune", "lot_of_spirit", "lot_of_eros")
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
    pd_direction_mode: str = "zodiacal",
    natal_lots: Mapping[str, dict[str, Any]] | None = None,
    include_full_timelines: bool = True,
    embedded_in_western_timing: bool = False,
    include_shared_primary_directions: bool = False,
    build_chart: bool = True,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    directions = build_primary_direction_analysis(
        birth_info,
        natal_subject,
        analysis_datetime=analysis_datetime,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
        direction_mode=pd_direction_mode,
        natal_lots=natal_lots,
        include_full_timelines=include_full_timelines,
    )
    primary_directions_payload = directions.payload
    if not build_chart:
        return primary_directions_payload, None
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
        natal_lots=directions.natal_lots,
        context=directions.context,
        equatorial=directions.equatorial,
        embedded_in_western_timing=embedded_in_western_timing,
        include_shared_primary_directions=include_shared_primary_directions,
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

    if technique == "transit":
        top_hit = payload["hits"][0] if payload.get("hits") else None
        summary = f"{prefix} 西占行运：行运太阳 {payload['sun']['sign_label']}"
        if top_hit:
            summary += (
                f"，最紧密命中 "
                f"{top_hit['source_label']}{top_hit['aspect_label']}{top_hit['target_label']}"
            )
        timeline = payload.get("transit_timeline")
        if isinstance(timeline, list):
            exact_count = sum(len(step.get("exact_hits") or ()) for step in timeline)
            summary += f"，扫描 {len(timeline)} 天共 {exact_count} 次精确命中"
        return summary + "。"

    if technique == "solararc":
        return f"{prefix} 西占太阳弧：当前太阳弧 {payload['arc_degrees']:.2f}°。"

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
        return (
            f"{prefix} 西占指定年盘：上升 {asc_label}，"
            f"年小限落第{annual_profection.get('activated_house')}宫"
            "（本命上升未解析，落座与主星待定）。"
        )

    if technique == "profection":
        if (
            payload.get("status") == "underdetermined_ascendant"
            or payload.get("activated_sign_label") is None
        ):
            return (
                f"{prefix} 西占年小限：落第{payload['activated_house']}宫"
                "（本命上升未解析，落座与主星待定）。"
            )
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
        if payload.get("status") == "underdetermined_ascendant":
            return f"{prefix} 西占黄道释放：本命上升未解析，无法计算福点与精神点释放。"
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
    return_longitude: float | None = None,
    return_latitude: float | None = None,
    return_timezone: str | None = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "placidus",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    show_pd_bounds: bool = True,
    high_latitude_fallback: str = "error",
    pd_direction_mode: str = "zodiacal",
    scan_days: int | None = None,
) -> dict[str, Any]:
    natal_subject = build_natal_subject(
        birth_info,
        house_system=house_system,
        zodiac_type=zodiac_type,
        high_latitude_fallback=high_latitude_fallback,
    )
    natal_lots = (
        build_lot_payloads(natal_subject)
        if is_ascendant_resolved(natal_subject)
        else {}
    )
    natal_reference = _build_western_timing_natal_reference(
        natal_subject, natal_lots=natal_lots
    )
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
            scan_days=scan_days,
            high_latitude_fallback=high_latitude_fallback,
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
            progression_options=progression_payload["calculation_options"],
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
            direction_mode=pd_direction_mode,
            natal_lots=natal_lots,
        )
        result["directions"] = {"primary_directions": primary_directions_payload}
        result["summary"] = _build_western_timing_module_summary(
            technique,
            primary_directions_payload,
            analysis_datetime=analysis_datetime,
        )
        return result

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
            pd_direction_mode=pd_direction_mode,
            natal_lots=natal_lots,
            embedded_in_western_timing=False,
        )
        assert primary_direction_chart_payload is not None
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
            natal_lots=natal_lots,
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


def _build_aggregate_summary(
    analysis_datetime: datetime,
    *,
    selected: frozenset[str],
    returns_payload: dict[str, Any] | None,
    transit_payload: dict[str, Any] | None,
    solar_arc_payload: dict[str, Any] | None,
    primary_directions_payload: dict[str, Any] | None,
    primary_direction_chart_payload: dict[str, Any] | None,
    given_year_payload: dict[str, Any] | None,
    profection_payload: dict[str, Any] | None,
    firdaria_payload: dict[str, Any] | None,
    decennials_payload: Mapping[str, Any] | None,
    zodiacal_releasing_payload: dict[str, Any] | None,
) -> str:
    prefix = analysis_datetime.strftime("%Y-%m-%d")
    if selected == ALL_WESTERN_TIMING_TECHNIQUES:
        assert returns_payload is not None
        assert transit_payload is not None
        assert solar_arc_payload is not None
        assert primary_directions_payload is not None
        assert given_year_payload is not None
        assert profection_payload is not None
        assert firdaria_payload is not None
        assert zodiacal_releasing_payload is not None
        firdaria_current = firdaria_payload["current_major"]
        zr_spirit_current = (zodiacal_releasing_payload.get("spirit") or {}).get(
            "current_level_1"
        )
        zr_label = (
            zr_spirit_current["sign_label"]
            if zr_spirit_current
            else (
                "未解析(ASC未定)"
                if zodiacal_releasing_payload.get("status")
                == "underdetermined_ascendant"
                else "未知"
            )
        )
        given_year_asc_label = (given_year_payload.get("ascendant") or {}).get(
            "sign_label"
        ) or "未解析"
        profection_sign_label = (
            profection_payload.get("activated_sign_label") or "（ASC未定）"
        )
        transit_top_hit = (
            transit_payload["hits"][0] if transit_payload["hits"] else None
        )
        return (
            f"{prefix} 西占时运："
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

    parts: list[str] = []
    if returns_payload:
        if "solar_return" in returns_payload:
            parts.append(
                f"太阳返照 {_return_event_label(returns_payload['solar_return'])}"
            )
        if "lunar_return" in returns_payload:
            parts.append(f"月返 {_return_event_label(returns_payload['lunar_return'])}")
    if primary_directions_payload is not None:
        parts.append(
            f"主限 {primary_directions_payload['direction_mode_label']} "
            f"{primary_directions_payload['time_key_label']} "
            f"{primary_directions_payload['coordinate_label']} "
            f"{primary_directions_payload['current_arc_degrees']:.2f}°"
        )
    elif primary_direction_chart_payload is not None:
        parts.append(
            f"主限法盘 {primary_direction_chart_payload['direction_mode_label']} "
            f"{primary_direction_chart_payload['time_key_label']} "
            f"{primary_direction_chart_payload['current_arc_degrees']:.2f}°"
        )
    if given_year_payload is not None:
        asc_label = (given_year_payload.get("ascendant") or {}).get(
            "sign_label"
        ) or "未解析"
        parts.append(f"指定年盘上升 {asc_label}")
    if "profection" in selected and profection_payload is not None:
        sign_lbl = profection_payload.get("activated_sign_label") or "（ASC未定）"
        parts.append(f"年小限落第{profection_payload['activated_house']}宫{sign_lbl}")
    if firdaria_payload is not None:
        cm = firdaria_payload["current_major"]
        cs = firdaria_payload["current_sub"]
        parts.append(
            f"法达 {cm['planet_label'] if cm else '未知'}"
            f"/{(cs or {}).get('planet_label', '无小运')}"
        )
    if decennials_payload is not None:
        l1 = (decennials_payload.get("current_level_1") or {}).get(
            "planet_label", "未知"
        )
        parts.append(f"十年星限 L1 {l1}")
    if zodiacal_releasing_payload is not None:
        zr_spirit = (zodiacal_releasing_payload.get("spirit") or {}).get(
            "current_level_1"
        )
        zr_lbl = (
            zr_spirit["sign_label"]
            if zr_spirit
            else (
                "未解析(ASC未定)"
                if zodiacal_releasing_payload.get("status")
                == "underdetermined_ascendant"
                else "未知"
            )
        )
        parts.append(f"Spirit 黄道释放 L1 {zr_lbl}")
    if solar_arc_payload is not None:
        parts.append(f"太阳弧 {solar_arc_payload['arc_degrees']:.2f}°")
    if transit_payload is not None:
        top = transit_payload["hits"][0] if transit_payload["hits"] else None
        text = f"行运太阳 {transit_payload['sun']['sign_label']}"
        if top:
            text += f"，最紧密命中 {top['source_label']}{top['aspect_label']}{top['target_label']}"
        parts.append(text)
    return f"{prefix} 西占时运：" + "，".join(parts) + "。"


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
    pd_method: str = "placidus",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: list[int] | None = None,
    show_pd_bounds: bool = True,
    high_latitude_fallback: str = "error",
    pd_direction_mode: str = "zodiacal",
    techniques: Sequence[str] | None = None,
    include_full_timelines: bool = False,
) -> dict[str, Any]:
    if techniques is None:
        selected = ALL_WESTERN_TIMING_TECHNIQUES
    else:
        if not techniques:
            raise ValueError("techniques 不能为空列表")
        unknown = [t for t in techniques if t not in ALL_WESTERN_TIMING_TECHNIQUES]
        if unknown:
            raise ValueError(f"Unsupported western timing techniques: {unknown}")
        selected = frozenset(techniques)

    natal_subject = build_natal_subject(
        birth_info,
        house_system=house_system,
        zodiac_type=zodiac_type,
        high_latitude_fallback=high_latitude_fallback,
    )
    natal_lots = (
        build_lot_payloads(natal_subject)
        if is_ascendant_resolved(natal_subject)
        else {}
    )
    natal_reference = _build_western_timing_natal_reference(
        natal_subject, natal_lots=natal_lots
    )
    return_location = _resolve_western_timing_return_location(
        birth_info,
        return_longitude=return_longitude,
        return_latitude=return_latitude,
        return_timezone=return_timezone,
    )

    returns_include: list[str] = [
        key for key in ("solar_return", "lunar_return") if key in selected
    ]
    returns_payload = (
        build_return_payload(
            natal_subject,
            analysis_datetime=analysis_datetime,
            return_longitude=return_location["longitude"],
            return_latitude=return_location["latitude"],
            return_timezone=return_location["timezone"],
            include=returns_include,
        )
        if returns_include
        else None
    )

    analysis_subject: NativeSubject | None = None
    if "transit" in selected or "given_year" in selected:
        analysis_zone = parse_timezone_name(return_location["timezone"])
        analysis_local = ZonedCalendar(
            utc_calendar(analysis_datetime), analysis_zone
        ).require_datetime()
        analysis_subject = build_subject(
            name=f"{birth_info.name}-analysis",
            local_datetime=analysis_local,
            longitude=return_location["longitude"],
            latitude=return_location["latitude"],
            timezone_name=return_location["timezone"],
            house_system=house_system,
            zodiac_type=zodiac_type,
            high_latitude_fallback=high_latitude_fallback,
        )

    transit_payload: dict[str, Any] | None = None
    all_transit_hits: list[dict[str, Any]] | None = None
    if "transit" in selected:
        transit_payload, all_transit_hits = build_transit_analysis(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            transit_longitude=return_location["longitude"],
            transit_latitude=return_location["latitude"],
            transit_timezone=return_location["timezone"],
            house_system=house_system,
            zodiac_type=zodiac_type,
            transit_subject=analysis_subject,
            include_natal_reference=False,
            high_latitude_fallback=high_latitude_fallback,
        )

    directions_section: dict[str, Any] = {}
    solar_arc_payload: dict[str, Any] | None = None
    if "secondary_progression" in selected or "solar_arc" in selected:
        progression_payload = build_secondary_progression_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        progressed_subject = progression_payload.pop("subject")
        if "secondary_progression" in selected:
            directions_section["secondary_progression"] = progression_payload
        if "solar_arc" in selected:
            solar_arc_payload = build_solar_arc_payload(
                natal_subject,
                progressed_subject,
                progression_options=progression_payload["calculation_options"],
            )
            directions_section["solar_arc"] = solar_arc_payload

    primary_directions_payload: dict[str, Any] | None = None
    primary_direction_chart_payload: dict[str, Any] | None = None
    if "primary_directions" in selected or "primary_direction_chart" in selected:
        pd_payload, pd_chart_payload = _build_primary_direction_pair(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            pd_method=pd_method,
            pd_time_key=pd_time_key,
            pd_type=pd_type,
            pd_aspects=pd_aspects,
            show_pd_bounds=show_pd_bounds,
            pd_direction_mode=pd_direction_mode,
            natal_lots=natal_lots,
            include_full_timelines=include_full_timelines,
            embedded_in_western_timing=True,
            include_shared_primary_directions=("primary_directions" in selected),
            build_chart=("primary_direction_chart" in selected),
        )
        if "primary_directions" in selected:
            primary_directions_payload = pd_payload
            directions_section["primary_directions"] = pd_payload
        if "primary_direction_chart" in selected and pd_chart_payload is not None:
            primary_direction_chart_payload = pd_chart_payload
            directions_section["primary_direction_chart"] = pd_chart_payload

    profection_payload: dict[str, Any] | None = None
    if "profection" in selected or "given_year" in selected:
        profection_payload = build_annual_profection_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
        )
    given_year_payload: dict[str, Any] | None = None
    if "given_year" in selected:
        assert profection_payload is not None
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
            analysis_subject=analysis_subject,
            transit_hits=all_transit_hits,
        )
        directions_section["given_year"] = given_year_payload

    time_lords_section: dict[str, Any] = {}
    if "profection" in selected and profection_payload is not None:
        time_lords_section["annual_profection"] = profection_payload
    firdaria_payload: dict[str, Any] | None = None
    if "firdaria" in selected:
        firdaria_payload = build_firdaria_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            firdaria_night_order=firdaria_night_order,
            firdaria_year_basis=firdaria_year_basis,
            include_full_timelines=include_full_timelines,
        )
        time_lords_section["firdaria"] = firdaria_payload
    decennials_payload: Mapping[str, Any] | None = None
    if "decennials" in selected:
        decennials_payload = build_decennials_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            include_full_timelines=include_full_timelines,
        )
        time_lords_section["decennials"] = decennials_payload
    zodiacal_releasing_payload: dict[str, Any] | None = None
    if "zodiacal_releasing" in selected:
        zodiacal_releasing_payload = build_zodiacal_releasing_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            natal_lots=natal_lots,
            include_full_timelines=include_full_timelines,
        )
        time_lords_section["zodiacal_releasing"] = zodiacal_releasing_payload

    summary = _build_aggregate_summary(
        analysis_datetime,
        selected=selected,
        returns_payload=returns_payload,
        transit_payload=transit_payload,
        solar_arc_payload=solar_arc_payload,
        primary_directions_payload=primary_directions_payload,
        primary_direction_chart_payload=primary_direction_chart_payload,
        given_year_payload=given_year_payload,
        profection_payload=profection_payload,
        firdaria_payload=firdaria_payload,
        decennials_payload=decennials_payload,
        zodiacal_releasing_payload=zodiacal_releasing_payload,
    )

    result: dict[str, Any] = {
        "analysis_type": "西占推运与返照分析",
        "analysis_context": _build_western_timing_analysis_context(
            birth_info,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type=zodiac_type,
            return_location=return_location,
        ),
        "natal_reference": natal_reference,
    }
    if returns_payload is not None:
        result["returns"] = returns_payload
    if transit_payload is not None:
        result["transits"] = {"current_transit": transit_payload}
    if directions_section:
        result["directions"] = directions_section
    if time_lords_section:
        result["time_lords"] = time_lords_section
    result["summary"] = summary
    return result
