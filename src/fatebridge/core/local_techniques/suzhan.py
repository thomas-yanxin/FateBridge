"""Build a Su Zhan chart and its source-bound calendrical reading."""

from __future__ import annotations

from typing import Any

from fatebridge.core.local_techniques.chart import (
    _build_birth_info,
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_time_text,
)
from fatebridge.core.sukuyo.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo.suzhan_astronomy import (
    METHOD,
    apply_equatorial_mansions,
    build_equatorial_mansions,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def build_suzhan_result(
    *,
    date: str,
    time: str | None = None,
    zone: str | None = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    szchart: int = 0,
    szshape: int = 0,
    house_start_mode: int = 1,
    doubing_su28: bool = True,
    hsys: int = 8,
    zodiacal: int = 0,
    leap_month_policy: str = "unresolved",
    natal_mansion: str | None = None,
    activity: str | None = None,
    activity_details: list[str] | None = None,
    calendar_profile: str = "t1299_fullmoon27",
    calendar_day_part: str | None = None,
    textual_pada: int | None = None,
    calendar_basis: str = "chinese_hko_utc08",
    chart_requested: bool = False,
) -> dict[str, Any]:
    if time is not None and not time.strip():
        raise ValueError("钟时须为已知时间；未知请省略或用null，空字符串不能代替未知。")
    coordinates_supplied = any(
        value is not None for value in (lat, lon, gps_lat, gps_lon)
    )
    compute_chart = time is not None and (coordinates_supplied or chart_requested)
    if compute_chart and (
        (gps_lat is None and (lat is None or not str(lat).strip()))
        or (gps_lon is None and (lon is None or not str(lon).strip()))
    ):
        raise ValueError("计算宿占星图需要完整经纬度，请提供lat/lon或gps_lat/gps_lon。")
    normalized_szchart = 1 if szchart else 0
    normalized_szshape = 1 if szshape else 0
    normalized_house_start_mode = 2 if house_start_mode == 2 else 1
    include_su28 = bool(doubing_su28)
    chart_variant = "guolao_chart" if normalized_szchart else "chart"
    if compute_chart and normalized_szchart and (hsys != 8 or zodiacal != 0):
        raise ValueError("宿占果老盘模式暂仅支持固定离线宫制 / 黄道语义。")
    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time) if time is not None else None,
        "zone": zone or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "szchart": normalized_szchart,
        "szshape": normalized_szshape,
        "houseStartMode": normalized_house_start_mode,
        "doubingSu28": include_su28,
        "hsys": hsys,
        "zodiacal": zodiacal,
        "leap_month_policy": leap_month_policy,
        "natal_mansion": natal_mansion,
        "activity": activity,
        "activity_details": activity_details or [],
        "calendar_profile": calendar_profile,
        "calendar_day_part": calendar_day_part,
        "textual_pada": textual_pada,
    }
    if calendar_basis != "chinese_hko_utc08":
        input_normalized["calendar_basis"] = calendar_basis
    if not compute_chart:
        clock_known = time is not None
        layer_status = (
            "not_computed_missing_coordinates"
            if clock_known
            else "not_computed_birth_time_unknown"
        )
        reason = (
            "历日宿已按所给钟时和时区计算。排星图及天文宿位需提供完整经纬度。"
            if clock_known
            else "钟时未知，已交付历法与候选证据。排星图及天文宿位需确认钟时和经纬度。"
        )
        calendar = calendar_mansion(
            input_normalized["date"],
            input_normalized["time"],
            input_normalized["zone"],
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=calendar_day_part,
            calendar_basis=calendar_basis,
        )
        evidence = day_evidence(
            calendar,
            natal_mansion=natal_mansion,
            activity=activity,
            activity_details=activity_details,
            textual_pada=textual_pada,
        )
        validation = {
            "calculation_layers": {
                "calendar": calendar["status"],
                "chart": layer_status,
                "astronomy": layer_status,
            },
        }
        params = {
            "calculationMode": (
                "calendar_with_clock" if clock_known else "calendar_date_only"
            ),
            "birthTimeKnown": clock_known,
            "birthTimeImputed": False,
            "coordinatesApplied": False,
            "chartComputed": False,
            "astronomyComputed": False,
            "su28Method": layer_status,
            "su28AstronomicalAccuracy": "not_computed",
        }
        return {
            "analysis_type": "宿占 / 宿盘",
            "input_normalized": input_normalized,
            "params": params,
            "chart": None,
            "sukuyo": evidence,
            "astronomy": None,
            "rulesets": rulesets(calendar_profile, calendar_basis),
            "validation": validation,
            "summary": f"历日宿{evidence['day_mansion'] or '以候选为准'}。{reason}",
        }
    response = _build_local_chart_response(
        date_text=input_normalized["date"],
        time_text=input_normalized["time"],
        timezone_name=input_normalized["zone"],
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        tradition=False,
        chart_variant=chart_variant,
        house_start_mode=normalized_house_start_mode,
        shape_mode=normalized_szshape,
        hsys=hsys,
        zodiacal=zodiacal,
        allow_extended_hsys=not bool(normalized_szchart),
        extra_params={
            "szchart": normalized_szchart,
            "szshape": normalized_szshape,
            "houseStartMode": normalized_house_start_mode,
            "doubingSu28": include_su28,
            "hsys": hsys,
            "zodiacal": zodiacal,
        },
    )
    chart = response["chart"]
    astronomy = None
    if include_su28:
        birth, _, _ = _build_birth_info(
            date_text=input_normalized["date"],
            time_text=input_normalized["time"],
            timezone_name=input_normalized["zone"],
            lat=lat,
            lon=lon,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
        )
        astronomy = build_equatorial_mansions(birth)
        apply_equatorial_mansions(chart, astronomy)
    else:
        pass
    response["sukuyo"] = day_evidence(
        calendar_mansion(
            input_normalized["date"],
            input_normalized["time"],
            input_normalized["zone"],
            leap_month_policy=leap_month_policy,
            calendar_profile=calendar_profile,
            calendar_day_part=calendar_day_part,
            calendar_basis=calendar_basis,
        ),
        natal_mansion=natal_mansion,
        activity=activity,
        activity_details=activity_details,
        textual_pada=textual_pada,
    )
    response["params"]["su28Method"] = METHOD
    response["params"]["su28AstronomicalAccuracy"] = (
        "declared_modern_anchor_model_not_classical_certified"
        if astronomy
        else "not_computed"
    )
    calculation_layers = {
        "calendar": response["sukuyo"]["calendar"]["status"],
        "chart": "computed",
        "astronomy": "computed" if astronomy is not None else "not_computed",
    }
    validation = {
        "calculation_layers": calculation_layers,
    }
    if "validation" in response:
        validation["chart_source"] = response["validation"]
    if (
        response["params"].get("houseGeometryStatus")
        == "unavailable_selected_reference"
    ):
        calculation_layers.update(
            house_geometry="unavailable_selected_reference", planet_positions="computed"
        )
    return {
        "analysis_type": "宿占 / 宿盘",
        "input_normalized": input_normalized,
        "params": response["params"],
        "chart": chart,
        "sukuyo": response["sukuyo"],
        "astronomy": astronomy,
        "rulesets": {
            **rulesets(calendar_profile, calendar_basis),
            **({"chart": response["rulesets"]} if "rulesets" in response else {}),
        },
        "validation": validation,
        "summary": f"历日宿{response['sukuyo']['day_mansion'] or '未定（见历法档案候选）'}；已生成星图。"
        + (
            "天文宿位采用现代距星不等宽研究口径。"
            if astronomy
            else "按请求关闭了天文28宿标注。"
        )
        + (
            "所选参考宫位不可用，星体数据已保留。"
            if response["params"].get("houseGeometryStatus")
            == "unavailable_selected_reference"
            else ""
        ),
    }
