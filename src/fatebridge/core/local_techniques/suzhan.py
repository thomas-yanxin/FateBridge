"""
Su Zhan (宿占) local technique.

Pure relocation from the package facade.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fatebridge.core.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.suzhan_astronomy import (
    METHOD,
    apply_equatorial_mansions,
    build_equatorial_mansions,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE

from .chart import (
    _build_birth_info,
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_mode,
    _normalize_time_text,
    _split_degree,
    _su28_position,
)
from .snapshot import join_lines, render_snapshot_text


def _build_suzhan_snapshot_text(
    input_normalized: Dict[str, Any], response: Dict[str, Any]
) -> str:
    chart = response.get("chart", {}) if isinstance(response, dict) else {}
    houses = chart.get("houses") if isinstance(chart, dict) else []
    objects = chart.get("objects") if isinstance(chart, dict) else []
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
    missing_coordinates = any(
        input_normalized.get(gps_key) is None
        and input_normalized.get(legacy_key) in (None, "")
        for gps_key, legacy_key in (("gpsLon", "lon"), ("gpsLat", "lat"))
    )
    coordinate_note = (
        "未提供的经纬度分量沿用默认坐标；宫位按这些参数计算，不能视为已确认地点。"
        if missing_coordinates
        else ""
    )
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
    prediction_note = (
        "计算结果未建立现实预测效力；未获权威认证。"
        if validation.get("real_world_prediction") == "not_established"
        and validation.get("authority_certified") is False
        else ""
    )
    house_lines: List[str] = []
    for house in houses or []:
        if not isinstance(house, dict):
            continue
        house_id = house.get("id", "House")
        house_lines.append(f"宫位：{house_id}")
        in_house = [
            item
            for item in objects or []
            if isinstance(item, dict) and item.get("house") == house_id
        ]
        if not in_house:
            house_lines.append("星曜：无")
            house_lines.append("")
            continue
        for item in in_house:
            su28 = str(item.get("su28") or "").strip()
            # A zodiac-sign degree is not a degree within a 360/28 band.
            value = (
                (
                    item["su28_degree"]
                    if "su28_degree" in item
                    else _su28_position(float(item["lon"]))[1]
                )
                if su28
                else item.get("signlon", item.get("lon"))
            )
            if su28:
                # Some real RA mansion bands exceed 30 degrees; do not apply
                # the zodiac-sign modulo used by _split_degree.
                if value is None:
                    raise ValueError("宿位缺少可显示的宿内度数")
                degree = int(float(value))
                minute = int((float(value) - degree) * 60)
            else:
                degree, minute = _split_degree(value)
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
                        coordinate_note,
                        prediction_note,
                        f"外盘：{input_normalized.get('szchart', 0)}",
                        f"盘型：{input_normalized.get('szshape', 0)}",
                        f"宫制：{((response.get('params') or {}).get('houseSystemResolved') or 'equal')}",
                        f"黄道：{((response.get('params') or {}).get('zodiacLabelZh') or (response.get('params') or {}).get('zodiacMode') or 'tropical')}",
                    ]
                ),
            ),
            (
                "宿盘宫位与二十八宿星曜",
                (
                    "未标注天文宿位。\n"
                    if not (input_normalized.get("doubingSu28", True))
                    else (
                        "现代距星研究口径：当日视赤经、不等宽宿界；不等于唐代宿界复原。\n"
                        if (response.get("params") or {}).get("su28Method") == METHOD
                        else "旧版等分黄道示意，不是中国不等宽赤道宿度。\n"
                    )
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
    mansion_method: str = "equatorial_research28",
    activity: Optional[str] = None,
    activity_details: Optional[List[str]] = None,
    calendar_profile: str = "t1299_fullmoon27",
    calendar_day_part: Optional[str] = None,
    textual_pada: Optional[int] = None,
    calendar_basis: str = "chinese_hko_utc08",
) -> Dict[str, Any]:
    if time is not None and not time.strip():
        raise ValueError("钟时须为已知时间；未知请省略或用null，空字符串不能代替未知。")
    if mansion_method not in {"equatorial_research28", "legacy_equal28"}:
        raise ValueError("mansion_method仅支持equatorial_research28或legacy_equal28")
    normalized_szchart = 1 if _normalize_mode(szchart, default=0) else 0
    normalized_szshape = 1 if _normalize_mode(szshape, default=0) else 0
    normalized_house_start_mode = (
        2 if _normalize_mode(house_start_mode, default=1) == 2 else 1
    )
    include_su28 = bool(doubing_su28)
    normalized_hsys = 8 if hsys is None else int(hsys)
    normalized_zodiacal = 0 if zodiacal is None else int(zodiacal)
    chart_variant = "guolao_chart" if normalized_szchart else "chart"
    if (
        time is not None
        and normalized_szchart
        and (normalized_hsys != 8 or normalized_zodiacal != 0)
    ):
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
        "hsys": normalized_hsys,
        "zodiacal": normalized_zodiacal,
        "leap_month_policy": leap_month_policy,
        "natal_mansion": natal_mansion,
        "mansion_method": mansion_method,
        "activity": activity,
        "activity_details": activity_details or [],
        "calendar_profile": calendar_profile,
        "calendar_day_part": calendar_day_part,
        "textual_pada": textual_pada,
    }
    if calendar_basis != "chinese_hko_utc08":
        input_normalized["calendar_basis"] = calendar_basis
    if time is None:
        calendar = calendar_mansion(
            input_normalized["date"],
            None,
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
            "real_world_prediction": "not_established",
            "authority_certified": False,
            "calculation_layers": {
                "calendar": calendar["status"],
                "chart": "not_computed_birth_time_unknown",
                "astronomy": "not_computed_birth_time_unknown",
            },
        }
        params = {
            "calculationMode": "calendar_date_only",
            "birthTimeKnown": False,
            "birthTimeImputed": False,
            "coordinatesApplied": False,
            "chartComputed": False,
            "astronomyComputed": False,
            "su28Method": "not_computed_birth_time_unknown",
            "su28AstronomicalAccuracy": "not_computed",
        }
        snapshot = render_snapshot_text(
            [
                (
                    "起盘信息",
                    join_lines(
                        [
                            f"日期：{input_normalized['date']}",
                            "钟时：未知，未补造出生时刻。",
                            f"输入时区：{input_normalized['zone']}",
                            "经纬度与星图选项未用于本次历法计算。",
                        ]
                    ),
                ),
                ("历日二十七宿", evidence["reading_text"]),
                (
                    "天文宿位与宫位",
                    "出生时刻未知；星图、宫位、瞬时天文宿位及现代角距tithi均未计算。",
                ),
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
            "summary": f"历日宿{evidence['day_mansion'] or '未定（见历法档案候选）'}；钟时未知，已交付历法与候选证据，天文宿位及宫位未计算。",
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
        include_su28=include_su28,
        chart_variant=chart_variant,
        house_start_mode=normalized_house_start_mode,
        shape_mode=normalized_szshape,
        hsys=normalized_hsys,
        zodiacal=normalized_zodiacal,
        allow_extended_hsys=not bool(normalized_szchart),
        extra_params={
            "szchart": normalized_szchart,
            "szshape": normalized_szshape,
            "houseStartMode": normalized_house_start_mode,
            "doubingSu28": include_su28,
            "hsys": normalized_hsys,
            "zodiacal": normalized_zodiacal,
        },
    )
    chart = response["chart"]
    astronomy = None
    if include_su28 and mansion_method == "equatorial_research28":
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
    response["params"]["su28Method"] = (
        METHOD
        if mansion_method == "equatorial_research28"
        else "legacy_equal_ecliptic28_illustration"
    )
    response["params"]["su28AstronomicalAccuracy"] = (
        "declared_modern_anchor_model_not_classical_certified"
        if astronomy
        else "not_computed" if not include_su28 else "not_validated_as_chinese_mansions"
    )
    validation = {
        "real_world_prediction": "not_established",
        "authority_certified": False,
    }
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
        "rulesets": rulesets(calendar_profile, calendar_basis),
        "validation": validation,
        "snapshot_text": snapshot_text,
        "summary": f"历日宿{response['sukuyo']['day_mansion'] or '未定（见历法档案候选）'}；已生成星图。"
        + (
            "天文宿位采用现代距星不等宽研究口径。"
            if astronomy
            else (
                "未计算天文宿位。" if not include_su28 else "旧二十八等分标签仅为示意。"
            )
        ),
    }
