"""Astrodice symbols with a separate, optional astronomical context chart."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fatebridge.core.astro.context_geometry import FORTUNE_METHODS
from fatebridge.core.astrodice import (
    EDITORIAL_RULESET,
    build_symbolic_evidence,
    normalize_house,
    normalize_planet,
    normalize_sign,
    validate_context,
)
from fatebridge.core.astrology_tables import SIGNS

from .chart import (
    _build_house_ring,
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_time_text,
    _render_snapshot_text,
)


def _quote_question(question: str) -> str:
    # JSON quoting protects ASCII line separators and quotes; Python's section
    # parser also treats these three Unicode characters as line boundaries.
    return (
        json.dumps(question, ensure_ascii=False)
        .replace("\u0085", "\\u0085")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _motion_snapshot_line(obj: Dict[str, Any]) -> str:
    motion = obj["motion"]
    labels = {
        "direct": "瞬时顺行",
        "retrograde": "瞬时逆行",
        "zero_instantaneous_rate": "瞬时零日速",
        "not_computed": "未计算",
    }
    speed = motion["longitude_speed"]
    value = "未提供速度" if speed is None else f"{speed} 度/日"
    line = f"{obj['id']} / {value} / {labels[motion['direction']]} / {motion['basis']}"
    if "native_longitude_speed" in motion:
        line += f"；原生日速 {motion['native_longitude_speed']} 度/日"
        if "light_time_correction" in motion:
            line += f"，光行时链式修正 {motion['light_time_correction']} 度/日"
        if "spatial_aberration_correction" in motion:
            line += f"，空间光行差修正 {motion['spatial_aberration_correction']} 度/日"
        if "lunar_source_remainder_correction" in motion:
            line += f"，月球固定框架源导数余项 {motion['lunar_source_remainder_correction']} 度/日"
        if "sidereal_origin_wrap_correction" in motion:
            line += f"，恒星黄道原点整圈差分修正 {motion['sidereal_origin_wrap_correction']} 度/日"
        if "rotation_correction" in motion:
            line += f"，黄道旋转导数修正 {motion['rotation_correction']} 度/日"
        if "analytic_frame_correction" in motion:
            line += (
                f"，日期框架解析导数修正 {motion['analytic_frame_correction']} 度/日"
            )
        if "position_derivative_correction" in motion:
            line += (
                f"，完整视位置导数余项 {motion['position_derivative_correction']} 度/日"
            )
    return line


def _solar_position_snapshot(policy: Dict[str, Any]) -> str:
    """Render the computed convention receipt without inventing visibility."""
    domains = {
        "behind_solar_disc": "太阳盘后方；视位置来自透明太阳质量模型的虚拟延拓",
        "foreground_of_solar_disc": "太阳盘前方；与盘后延拓分开处理",
        "outside_solar_disc": "未穿过模型太阳盘",
        "sun_behind_observer": "太阳位于观测者后方",
        "solar_limb_ambiguous": "模型太阳边缘，几何分类未决",
        "target_on_model_sphere_ambiguous": "目标位于模型球面边界，几何分类未决",
        "target_inside_model_sphere": "目标位于模型太阳内部，几何分类未决",
    }
    verified = policy["solar_deflection_model"] == "native_extended_solar_mass"
    lines = [
        (
            "太阳引力偏折采用 Swiss Ephemeris 的有限太阳质量模型。"
            if verified
            else "当前原生太阳引力偏折模型未经版本核验。"
        ),
        "JPL 数据后端仍由 Swiss Ephemeris 计算视位置；不代表采用 Horizons 的全部视位置约定。",
    ]
    for body, geometry in policy["bodies"].items():
        if geometry["status"] != "computed":
            text = "几何未计算：" + geometry["reason"]
        else:
            text = domains[geometry["unbent_ray_domain"]]
        lines.append(f"{body}：{text}")
    lines.extend(
        [
            "以上是题问时刻的模型几何，不是可见性、遮掩接触时刻或观测精度证明；不用于改写骰面或定位应期。",
            f"依据：{policy['source_url']} {policy['source_section']}；原生版本 {policy['native_version']}。",
        ]
    )
    return "\n".join(lines)


def build_otherbu_result(
    *,
    date: Optional[str] = None,
    time: Optional[str] = None,
    zone: Optional[str] = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    tradition: bool = False,
    sign: Optional[str] = None,
    house: Optional[int] = None,
    planet: Optional[str] = None,
    question: Optional[str] = None,
    hsys: int = 8,
    zodiacal: int = 0,
    fortune_method: str = "sect_reversing",
) -> Dict[str, Any]:
    normalized_sign = normalize_sign(sign)
    normalized_planet = normalize_planet(planet)
    normalized_house = normalize_house(house)
    if type(hsys) is not int or hsys not in range(9):
        raise ValueError("hsys必须为0..8的整数，仅用于附加天象盘")
    if type(zodiacal) is not int or zodiacal not in {0, 1}:
        raise ValueError("zodiacal必须为0或1的整数，仅用于附加天象盘")
    if fortune_method not in FORTUNE_METHODS:
        raise ValueError("fortune_method必须为sect_reversing或ptolemy_iii10")
    validate_context(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    inputs = {
        "date": _normalize_date_text(date) if date is not None else None,
        "time": _normalize_time_text(time) if time is not None else None,
        "zone": zone,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "tradition": tradition,
        "sign": normalized_sign,
        "house": normalized_house,
        "planet": normalized_planet,
        "question": question,
        "hsys": hsys,
        "zodiacal": zodiacal,
        "fortune_method": fortune_method,
    }
    evidence = build_symbolic_evidence(
        normalized_planet, normalized_sign, normalized_house
    )
    first_longitude = ((SIGNS.index(normalized_sign) - normalized_house) % 12) * 30.0
    # A die encodes a sign, not an exact longitude. Never copy sky bodies into it.
    dice_chart = {
        "params": {
            "chartKind": "symbolic_whole_sign_diagram",
            "houseSystemResolved": "symbolic_whole_sign",
            "engineBackend": "symbolic_rules",
            "enginePrecision": "sign_and_house_only",
            "diceHouse1Longitude": first_longitude,
            "diceTargetHouse": f"House{normalized_house + 1}",
            "longitudeMeaning": "宫首经度仅为假设整宫轮坐标；非观测宫头或真实上升点。",
        },
        "chart": {
            "ok": True,
            "houses": _build_house_ring(first_longitude),
            "objects": [
                {
                    "id": normalized_planet,
                    "sign": normalized_sign,
                    "house": f"House{normalized_house + 1}",
                }
            ],
            "angles": {},
        },
    }
    base_chart = None
    if date is not None and time is not None:
        base_chart = _build_local_chart_response(
            date_text=inputs["date"],
            time_text=inputs["time"],
            timezone_name=zone,
            lat=lat,
            lon=lon,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            tradition=tradition,
            include_su28=False,
            hsys=hsys,
            zodiacal=zodiacal,
            allow_extended_hsys=True,
            include_calculation_metadata=True,
            preserve_context_geometry=True,
            context_fortune_method=fortune_method,
        )
        base_chart["params"]["chartKind"] = "astronomical_context_only"
        evidence["validation"]["calendar"] = "separate_astronomical_context_computed"
    interpretation = evidence["interpretation"]
    if question:
        interpretation["question_adjustment"] = (
            f"围绕用户问题（JSON引用）{_quote_question(question)}核对上述议题；问题文本不改变骰面或规则。"
        )
        interpretation["evidence"]["question_adjustment"] = {
            "text_path": "interpretation.question_adjustment",
            "kind": "user_context",
            "fact_paths": ["question"],
            "rule_ids": [],
            "ruleset_ids": [EDITORIAL_RULESET],
        }
    snapshot = [
        (
            "骰子结果",
            f"行星：{normalized_planet}\n星座：{normalized_sign}\n宫位：House{normalized_house + 1}\n问题原文（JSON引用）：{_quote_question(question) if question is not None else '未填写'}",
        ),
        (
            "骰子盘宫位与星体",
            f"符号示意：{normalized_planet} / {normalized_sign} / House{normalized_house + 1}；无精确度数、上升点或天顶。",
        ),
        (
            "符号解释",
            "\n".join(
                [
                    interpretation["summary"],
                    *interpretation["condition_meanings"],
                    interpretation["dispositor_meaning"],
                    interpretation["house_condition_meaning"],
                    interpretation["triplicity_meaning"],
                    interpretation["planet_sect_meaning"],
                    interpretation["symbolic_links"],
                ]
            ),
        ),
        ("现实核对", interpretation["reality_check"]),
        (
            "依据与边界",
            "\n".join(
                f"{r['author']} | {r['version']} | {r.get('source_url') or r['source_path']}"
                for r in evidence["rulesets"]
            )
            + "\n"
            + interpretation["limits"],
        ),
    ]
    if base_chart is not None:
        params = base_chart["params"]
        snapshot.append(
            (
                "天象盘宫位与星体",
                f"独立天象背景，不用于改写骰面或推断应期。\n日期：{inputs['date']} {inputs['time']}\n时区：{zone}\n"
                f"经纬度：{params['birthLongitude']} {params['birthLatitude']}\n宫制：{params['houseSystemResolved']}\n黄道：{params['zodiacMode']}\n"
                f"福点公式：{params['fortuneDefinition']['method']} / {params['fortuneDefinition']['formula']}\n"
                f"福点依据：{params['fortuneDefinition'].get('source_url') or params['fortuneDefinition'].get('source_path')}（仅公式范围）\n"
                + (
                    params["ephemerisReferencePoints"]["note_zh"] + "\n"
                    if "ephemerisReferencePoints" in params
                    else ""
                )
                + (
                    params["chart_profile"]["orbital_fallback"]["note_zh"]
                    + "\n近似天体："
                    + "、".join(
                        params["chart_profile"]["orbital_fallback"][
                            "approximate_planets"
                        ]
                    )
                    + "\n"
                    if "orbital_fallback" in params["chart_profile"]
                    else ""
                )
                + (
                    params["chart_profile"]["angle_definition"]["note_zh"] + "\n"
                    if "angle_definition" in params["chart_profile"]
                    else ""
                )
                + (
                    params["chart_profile"]["house_axis_convention"]["note_zh"] + "\n"
                    if "house_axis_convention" in params["chart_profile"]
                    else ""
                )
                + (
                    params["housePositionProjection"].get(
                        "note_zh",
                        "落宫方法：非单圈顺行宫头，采用原生黄纬0°投影；不是计入星体实际黄纬的空间落宫。",
                    )
                    + "\n"
                    + f"投影依据：{params['housePositionProjection']['source_url']} §16\n"
                    if "housePositionProjection" in params
                    else ""
                )
                + "\n".join(
                    f"{obj['id']} / {obj['sign']} / {obj['lon']}° / {obj['house']}"
                    for obj in base_chart["chart"]["objects"]
                ),
            )
        )
        if "motionPolicy" in params:
            snapshot.append(
                (
                    "天象瞬时黄经运动",
                    f"参考系：{params['motionPolicy']['reference_frame']}。"
                    "只说明该时刻显示黄道下的日速；不改写骰面条件，也不定位留站或应期。\n"
                    + "\n".join(
                        _motion_snapshot_line(obj)
                        for obj in base_chart["chart"]["objects"]
                    ),
                )
            )
        solar_policy = params["chart_profile"].get("apparent_position_policy")
        if solar_policy is not None:
            snapshot.append(("天象视位置约定", _solar_position_snapshot(solar_policy)))
    return {
        "analysis_type": "西洋游戏 / 占星骰子",
        "input_normalized": inputs,
        "planet": normalized_planet,
        "sign": normalized_sign,
        "house": normalized_house,
        "diceChart": dice_chart,
        "chart": base_chart,
        "question": question,
        **evidence,
        "snapshot_text": _render_snapshot_text(snapshot),
        "summary": f"星骰符号：{normalized_planet} / {normalized_sign} / 第{normalized_house + 1}宫。{interpretation['summary']}",
    }
