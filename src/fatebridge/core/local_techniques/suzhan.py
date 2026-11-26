"""Build a Su Zhan chart and its source-bound calendrical reading."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.local_techniques.chart import (
    _build_birth_info,
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_time_text,
)
from fatebridge.core.local_techniques.snapshot import join_lines, render_snapshot_text
from fatebridge.core.sukuyo.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo.suzhan_astronomy import (
    METHOD,
    apply_equatorial_mansions,
    build_equatorial_mansions,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def _build_suzhan_snapshot_text(
    input_normalized: Dict[str, Any], response: Dict[str, Any]
) -> str:
    chart = response.get("chart") or {}
    houses = chart.get("houses") or []
    objects = chart.get("objects") or []
    params = response.get("params") or {}
    longitude = params.get("birthLongitude")
    latitude = params.get("birthLatitude")
    if longitude is None:
        longitude = input_normalized.get("gpsLon")
    if latitude is None:
        latitude = input_normalized.get("gpsLat")
    if longitude is None:
        longitude = input_normalized.get("lon", "未提供")
    if latitude is None:
        latitude = input_normalized.get("lat", "未提供")
    astronomy = response.get("astronomy") or {}
    epoch_text = (
        join_lines(
            [
                f"物理时刻参考标签（UTC记法）：{astronomy['utc_datetime']}",
                "UTC标签与当地输入表示同一时刻；年编号跨界不改写出生输入。",
                f"TT儒略日：{astronomy['julian_day_tt']}；UT1儒略日：{astronomy['julian_day_ut1']}",
                "两种时标不可直接互换；历史时标按所声明模型处理，参考标签不认证古代当地钟时。",
            ]
        )
        + "\n"
        if astronomy
        else ""
    )
    validation = response.get("validation") or {}
    phase = astronomy.get("lunar_phase_reference") or {}
    phase_text = "现代月日黄经差未计算；此模式未取得所需同次天文坐标。"
    if phase:
        tithi = phase["modern_tithi"]
        phase_text = join_lines(
            [
                f"同次TT月日视黄经差：{phase['elongation_degrees']}现代度；"
                f"现代12度角距tithi第{tithi['index']}段（{tithi['half_zh']}分{tithi['half_tithi_index']}）。",
                f"半开区间：[{tithi['lower_degrees_inclusive']}°, {tithi['upper_degrees_exclusive']}°)；"
                "精确180°起现代黑分第一段，原典以月满名白十五的用语另存。",
                "本段的现代白黑分是瞬时角距命名；历日段白黑月是T1299日号命名，两者分别交付。",
                "下文历日层所说未计算月相或tithi仅限该历日层；本段已算黄经差与角距分段，"
                "未算月宿合、日出历日或tithi终止时刻，未判定T1796仪轨条件。",
                phase["scope"],
            ]
        )
    house_groups = [
        (
            f"宫位：{house['id']}",
            [item for item in objects if item.get("house") == house["id"]],
        )
        for house in houses
    ]
    unassigned = [item for item in objects if item.get("house") is None]
    if unassigned:
        house_groups.append(("参考宫位未定；以下星曜未分配落宫", unassigned))
    house_lines: List[str] = []
    for heading, in_house in house_groups:
        house_lines.append(heading)
        if not in_house:
            house_lines.append("星曜：无")
            house_lines.append("")
            continue
        for item in in_house:
            su28 = str(item.get("su28") or "").strip()
            # A zodiac-sign degree is not a degree within a 360/28 band.
            value = (
                (item["su28_degree"]) if su28 else item.get("signlon", item.get("lon"))
            )
            if su28:
                # Some real RA mansion bands exceed 30 degrees; do not apply
                # the zodiac-sign modulo.
                if value is None:
                    raise ValueError("宿位缺少可显示的宿内度数")
                degree = int(float(value))
                minute = int((float(value) - degree) * 60)
            else:
                sign_degree = float(value) % 30
                degree = int(sign_degree)
                minute = int((sign_degree - degree) * 60)
            star_text = f"{degree}˚{su28}{minute}分" if su28 else f"{degree}˚{minute}分"
            house_lines.append(f"星曜：{item.get('id')} {star_text}".strip())
        house_lines.append("")

    return render_snapshot_text(
        [
            (
                "起盘信息",
                join_lines(
                    [
                        f"日期：{input_normalized['date']} {input_normalized['time']}",
                        f"时区：{input_normalized['zone']}",
                        f"经纬度：{longitude} {latitude}",
                        f"外盘：{input_normalized.get('szchart', 0)}",
                        f"盘型：{input_normalized.get('szshape', 0)}",
                        f"宫制：{((response.get('params') or {}).get('houseSystemResolved') or '未提供')}",
                        ((params.get("angleDefinition") or {}).get("note_zh") or ""),
                        (
                            (params.get("housePositionProjection") or {}).get("note_zh")
                            or ""
                        ),
                        params.get("houseGeometryNote") or "",
                        f"黄道：{((response.get('params') or {}).get('zodiacLabelZh') or (response.get('params') or {}).get('zodiacMode') or 'tropical')}",
                    ]
                ),
            ),
            (
                "宿盘宫位与二十八宿星曜",
                (
                    "未标注天文宿位。\n"
                    if not (input_normalized.get("doubingSu28", True))
                    else "现代距星研究口径：当日视赤经与不等宽宿界。\n"
                )
                + epoch_text
                + (join_lines(house_lines) or "无"),
            ),
            (
                "现代月日黄经差参考",
                phase_text,
            ),
            (
                "历日二十七宿",
                (response.get("sukuyo") or {}).get("reading_text")
                or str(response.get("sukuyo", {})),
            ),
            *(
                [
                    (
                        "星图来源与适用范围",
                        join_lines(validation["chart_source"]["limitations"]),
                    )
                ]
                if "chart_source" in validation
                else []
            ),
        ]
    )


def build_suzhan_result(
    *,
    date: str,
    time: Optional[str] = None,
    zone: Optional[str] = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    szchart: int = 0,
    szshape: int = 0,
    house_start_mode: int = 1,
    doubing_su28: bool = True,
    hsys: int = 8,
    zodiacal: int = 0,
    leap_month_policy: str = "unresolved",
    natal_mansion: Optional[str] = None,
    activity: Optional[str] = None,
    activity_details: Optional[List[str]] = None,
    calendar_profile: str = "t1299_fullmoon27",
    calendar_day_part: Optional[str] = None,
    textual_pada: Optional[int] = None,
    calendar_basis: str = "chinese_hko_utc08",
    chart_requested: bool = False,
) -> Dict[str, Any]:
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
        snapshot = render_snapshot_text(
            [
                (
                    "起盘信息",
                    join_lines(
                        [
                            f"日期：{input_normalized['date']}",
                            (
                                f"钟时：{input_normalized['time']}"
                                if clock_known
                                else "钟时：未知，未补造出生时刻。"
                            ),
                            f"输入时区：{input_normalized['zone']}",
                            "经纬度与星图选项未用于本次历法计算。",
                        ]
                    ),
                ),
                ("历日二十七宿", evidence["reading_text"]),
                ("天文宿位与宫位", reason),
            ]
        )
        return {
            "analysis_type": "宿占 / 宿盘",
            "input_normalized": input_normalized,
            "params": params,
            "chart": None,
            "sukuyo": evidence,
            "astronomy": None,
            "rulesets": rulesets(calendar_profile, calendar_basis),
            "validation": validation,
            "snapshot_text": snapshot,
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
        include_su28=False,
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
    snapshot_text = _build_suzhan_snapshot_text(
        input_normalized,
        {**response, "astronomy": astronomy, "validation": validation},
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
        "snapshot_text": snapshot_text,
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
