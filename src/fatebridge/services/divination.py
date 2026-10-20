"""
FateBridge divination services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fatebridge.core.almanac import build_calendar_context
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.divination import build_meihua_interpretation, lookup_gua
from fatebridge.core.gua_meanings import caution_phrase
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.local_techniques.sanshi import build_sanshiunited_result
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.local_techniques.suzhan import build_suzhan_result
from fatebridge.core.local_techniques.tongshefa import build_tongshefa_result
from fatebridge.core.sukuyo import su28_to_su27, sukuyo_relation
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_lines as _render_snapshot_text,
)
from fatebridge.services.structured_snapshot import render_structured_snapshot_text
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def _build_gua_lookup_snapshot_text(
    *,
    query: str,
    lookup_mode: str,
    result: Dict[str, Any],
) -> str:
    query_lines = [
        f"查询：{query}",
        f"模式：{lookup_mode}",
        f"命中类型：{result.get('lookup_type', '未知')}",
        f"命中卦名：{result.get('name', '未知')}",
        f"匹配文本：{result.get('matched_query', query)}",
        f"卦码：{result.get('code') or result.get('binary_code') or '无'}",
    ]
    upper = result.get("upper") or {}
    lower = result.get("lower") or {}
    structure_lines = [
        f"符号：{result.get('symbol', '无')}",
        f"卦爻：{''.join(str(item) for item in result.get('lines', []) or []) or '无'}",
    ]
    if upper:
        structure_lines.append(
            f"上卦：{upper.get('name', '无')} / {upper.get('nature', '无')} / "
            f"{upper.get('element', '无')} / {upper.get('keywords', '无')}"
        )
    if lower:
        structure_lines.append(
            f"下卦：{lower.get('name', '无')} / {lower.get('nature', '无')} / "
            f"{lower.get('element', '无')} / {lower.get('keywords', '无')}"
        )

    meaning_lines = [
        f"主题：{result.get('theme', '无')}",
    ]
    if result.get("judgement"):
        meaning_lines.append(f"判断：{result['judgement']}")
    if result.get("guidance"):
        meaning_lines.append(f"建议：{result['guidance']}")
    if result.get("image"):
        meaning_lines.append(f"卦象：{result['image']}")
    if result.get("favorable"):
        meaning_lines.append(f"可为：{result['favorable']}")
    if result.get("caution"):
        meaning_lines.append(f"风险：{result['caution']}")
    if result.get("summary"):
        meaning_lines.append(f"摘要：{result['summary']}")

    source_lines = [
        "来源：FateBridge 离线卦义库",
        "引用：fatebridge.core.gua_meanings / lookup_gua",
    ]

    return _render_snapshot_text(
        [
            ("查询信息", query_lines),
            ("卦象结构", structure_lines),
            ("义理摘要", meaning_lines),
            ("来源", source_lines),
        ]
    )


def _build_gua_meiyi_snapshot_text(
    *,
    queries: List[str],
    results: Dict[str, Dict[str, Any]],
    summary: str,
) -> str:
    overview_lines = [
        f"查询数量：{len(queries)}",
        f"原始请求：{'、'.join(queries) or '无'}",
        f"摘要：{summary}",
    ]
    result_lines: list[str] = []
    for query in queries:
        item = results.get(query) or {}
        result_lines.append(
            f"{query} -> {item.get('name', '未知')} ({item.get('lookup_type', '未知')})"
        )
        if item.get("theme"):
            result_lines.append(f"主题：{item['theme']}")
        if item.get("judgement"):
            result_lines.append(f"判断：{item['judgement']}")
        if item.get("guidance"):
            result_lines.append(f"建议：{item['guidance']}")
        if item.get("desc"):
            result_lines.append(f"摘要：{item['desc']}")
        result_lines.append("")
    if result_lines and result_lines[-1] == "":
        result_lines.pop()

    source_lines = [
        "来源：FateBridge 离线卦义库",
        "引用：fatebridge.core.gua_meanings / lookup_gua",
    ]
    return _render_snapshot_text(
        [
            ("查询概览", overview_lines),
            ("批量结果", result_lines or ["无"]),
            ("来源", source_lines),
        ]
    )


@calculation_guard("梅花时卦分析")
def calculate_meihua_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_timezone: Optional[str] = None,
    question: Optional[str] = None,
) -> Dict:
    """
    梅花时卦分析工具 - 按指定时刻生成本卦、变卦、互卦、错卦、综卦与体用关系。
    """
    timezone_name = analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    analysis_datetime = datetime(
        analysis_year,
        analysis_month,
        analysis_day,
        analysis_hour,
        analysis_minute,
    )

    pillars = BaZiCalendar.get_four_pillars(
        analysis_datetime,
        timezone_name=timezone_name,
    )
    calendar_context = build_calendar_context(
        analysis_datetime,
        timezone_name=timezone_name,
        pillars=pillars,
    )
    lunar_calendar = calendar_context.get("lunar_calendar") or {}
    meihua = lunar_calendar.get("meihua")

    if not meihua:
        # A missing lunar context is a runtime-dependency problem, not a
        # user-input problem, so surface it as 503 with an explicit
        # error_code so clients and the HTTP layer can distinguish it.
        return {
            "error": "当前环境缺少农历上下文，无法生成梅花时卦。",
            "analysis_type": "梅花时卦分析",
            "error_code": "dependency_missing",
            "status_code": 503,
            "retryable": False,
        }

    interpretation = build_meihua_interpretation(meihua, question or "")

    return {
        "analysis_type": "梅花时卦分析",
        "analysis_context": {
            "analysis_datetime": calendar_context["solar_datetime"],
            "timezone": timezone_name,
            "question": question or "",
            "lunar_display": lunar_calendar.get("display"),
            "current_jieqi": calendar_context["current_solar_term"]["name"],
            "next_jieqi": calendar_context["next_solar_term"]["name"],
        },
        "four_pillars": create_pillar_dict(pillars),
        "calendar_context": calendar_context,
        "meihua": meihua,
        "interpretation": interpretation,
        "summary": interpretation["comprehensive_judgement"],
    }


@calculation_guard("卦义检索")
def calculate_gua_lookup(
    *,
    query: str,
    lookup_mode: str = "auto",
    selected_sections: Optional[List[str]] = None,
) -> Dict:
    """
    卦义检索工具 - 支持六十四卦与八卦的离线义理查询。
    """
    result = lookup_gua(query, lookup_mode=lookup_mode)
    snapshot_text = _build_gua_lookup_snapshot_text(
        query=query,
        lookup_mode=lookup_mode,
        result=result,
    )
    snapshot_export = _build_snapshot_export(
        technique="gua_lookup",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "卦义检索",
        "query": query,
        "lookup_mode": lookup_mode,
        "result": result,
        "summary": result["summary"],
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("梅易卦义")
def calculate_gua_meiyi(
    *,
    name: List[str],
    selected_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    梅易卦义辅助工具 - 批量返回偏梅花易数语境的卦义说明。
    """
    queries = [item.strip() for item in (name or []) if item and item.strip()]
    if not queries:
        raise ValueError("name 至少需要提供一个卦名或卦码。")

    results: Dict[str, Dict[str, Any]] = {}
    ordered_names: List[str] = []
    for query in queries:
        item = lookup_gua(query, lookup_mode="auto")
        desc = (
            f"{item['name']}：{item.get('theme', '当前之势')}。"
            f"{item.get('judgement') or item.get('guidance', '')}"
            f"宜{item.get('favorable', '顺势推进')}，"
            f"忌{caution_phrase(item.get('caution', '失衡冒进'))}。"
        )
        results[query] = {
            "name": item["name"],
            "lookup_type": item["lookup_type"],
            "theme": item.get("theme"),
            "judgement": item.get("judgement"),
            "guidance": item.get("guidance"),
            "desc": desc,
            "text": desc,
        }
        ordered_names.append(item["name"])

    summary = f"共查询{len(queries)}项梅易卦义：{'、'.join(ordered_names)}。"
    snapshot_text = _build_gua_meiyi_snapshot_text(
        queries=queries,
        results=results,
        summary=summary,
    )
    snapshot_export = _build_snapshot_export(
        technique="gua_meiyi",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )

    return {
        "analysis_type": "梅易卦义",
        "queries": queries,
        "results": results,
        "summary": summary,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("统摄法分析")
def calculate_tongshefa_analysis(
    *,
    taiyin: Optional[str] = None,
    taiyang: Optional[str] = None,
    shaoyang: Optional[str] = None,
    shaoyin: Optional[str] = None,
) -> Dict[str, Any]:
    """统摄法分析工具。"""
    return build_tongshefa_result(
        taiyin=taiyin,
        taiyang=taiyang,
        shaoyang=shaoyang,
        shaoyin=shaoyin,
    )


@calculation_guard("邵子参评数分析")
def calculate_canping_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    gender: Optional[str] = None,
    method: str = "ming",
    use_true_solar_time: bool = True,
) -> Dict[str, Any]:
    """邵子参评数 / 金锁银匙分析工具。"""
    return build_canping_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        gender=gender,
        method=method,
        use_true_solar_time=use_true_solar_time,
    )


@calculation_guard("河洛理数分析")
def calculate_heluo_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    gender: Optional[str] = None,
    use_true_solar_time: bool = True,
) -> Dict[str, Any]:
    """河洛理数分析工具。"""
    return build_heluo_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        gender=gender,
        use_true_solar_time=use_true_solar_time,
    )


@calculation_guard("六爻分析")
def calculate_sixyao_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    question: Optional[str] = None,
    gua_code: Optional[str] = None,
    changed_code: Optional[str] = None,
    lines: Optional[List[Dict[str, Any]]] = None,
    method: str = "auto",
    coins: Optional[List[int]] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """六爻 / 易卦分析工具。"""
    return build_sixyao_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        question=question,
        gua_code=gua_code,
        changed_code=changed_code,
        lines=lines,
        method=method,
        coins=coins,
        seed=seed,
    )


@calculation_guard("宿占分析")
def calculate_suzhan_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    szchart: int = 0,
    szshape: int = 0,
    house_start_mode: int = 1,
    doubing_su28: bool = True,
    hsys: int = 8,
    zodiacal: int = 0,
) -> Dict[str, Any]:
    """宿占 / 宿盘分析工具。"""
    return build_suzhan_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        szchart=szchart,
        szshape=szshape,
        house_start_mode=house_start_mode,
        doubing_su28=doubing_su28,
        hsys=hsys,
        zodiacal=zodiacal,
    )


def _natal_su_from_suzhan(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
) -> Dict[str, Any]:
    """从宿占盘取月所在宿（本命宿）及其黄经，作为宿曜相性的输入。"""
    result = build_suzhan_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        doubing_su28=True,
    )
    objects = (result.get("chart") or {}).get("objects") or []
    moon = next((item for item in objects if item.get("id") == "Moon"), None)
    if not moon or not moon.get("su28"):
        raise ValueError("无法从宿占盘获取月宿（Moon su28）。")
    su28 = str(moon["su28"])
    longitude = round(float(moon.get("lon", 0.0)), 4)
    return {
        "su28": su28,
        "su27": su28_to_su27(su28, longitude),
        "moon_longitude": longitude,
    }


@calculation_guard("宿曜双人相性")
def calculate_sukuyo_compatibility(
    *,
    person1_name: str = "甲方",
    person1_date: str,
    person1_time: str,
    person1_zone: Optional[str] = None,
    person1_lat: Optional[str] = None,
    person1_lon: Optional[str] = None,
    person1_gps_lat: Optional[float] = None,
    person1_gps_lon: Optional[float] = None,
    person2_name: str = "乙方",
    person2_date: str,
    person2_time: str,
    person2_zone: Optional[str] = None,
    person2_lat: Optional[str] = None,
    person2_lon: Optional[str] = None,
    person2_gps_lat: Optional[float] = None,
    person2_gps_lon: Optional[float] = None,
) -> Dict[str, Any]:
    """宿曜（二十七宿）双人相性分析 / 三九の秘法。

    以双方各自宿占盘中月所在之宿为本命宿，按二十七宿循环距离判定有向关系
    （正反向互为配对）。本命宿口径与 suzhan 工具完全一致（二十八宿去牛→27）。
    """
    person1 = _natal_su_from_suzhan(
        date=person1_date,
        time=person1_time,
        zone=person1_zone,
        lat=person1_lat,
        lon=person1_lon,
        gps_lat=person1_gps_lat,
        gps_lon=person1_gps_lon,
    )
    person2 = _natal_su_from_suzhan(
        date=person2_date,
        time=person2_time,
        zone=person2_zone,
        lat=person2_lat,
        lon=person2_lon,
        gps_lat=person2_gps_lat,
        gps_lon=person2_gps_lon,
    )

    forward = sukuyo_relation(
        person1["su28"],
        person2["su28"],
        person1["moon_longitude"],
        person2["moon_longitude"],
    )
    reverse = sukuyo_relation(
        person2["su28"],
        person1["su28"],
        person2["moon_longitude"],
        person1["moon_longitude"],
    )

    summary = (
        f"{person1_name}本命宿{person1['su27']}，{person2_name}本命宿"
        f"{person2['su27']}，互为「{forward['pair']}」相性。"
        f"{person1_name}看{person2_name}为{forward['relation']}"
        f"（{forward['distance'] or '同宿'}）；{person2_name}看{person1_name}为"
        f"{reverse['relation']}（{reverse['distance'] or '同宿'}）。"
    )

    result: Dict[str, Any] = {
        "analysis_type": "宿曜双人相性 / 三九の秘法",
        "su27_basis": "su28_drop_niu",
        "person1": {
            "name": person1_name,
            "natal_su28": person1["su28"],
            "natal_su27": person1["su27"],
            "moon_longitude": person1["moon_longitude"],
        },
        "person2": {
            "name": person2_name,
            "natal_su28": person2["su28"],
            "natal_su27": person2["su27"],
            "moon_longitude": person2["moon_longitude"],
        },
        "pair": forward["pair"],
        "person1_to_person2": forward,
        "person2_to_person1": reverse,
        "summary": summary,
    }
    snapshot_text = render_structured_snapshot_text(
        result, title="宿曜双人相性 / 三九の秘法"
    )
    result["snapshot_text"] = snapshot_text
    result["snapshot_export"] = _build_snapshot_export(
        technique="generic", snapshot_text=snapshot_text
    )
    return result


@calculation_guard("占星骰子分析")
def calculate_otherbu_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    tradition: bool = False,
    sign: Optional[str] = None,
    house: int = 0,
    planet: Optional[str] = None,
    question: Optional[str] = None,
    hsys: int = 8,
    zodiacal: int = 0,
) -> Dict[str, Any]:
    """西洋游戏 / 占星骰子分析工具。"""
    return build_otherbu_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        tradition=tradition,
        sign=sign,
        house=house,
        planet=planet,
        question=question,
        hsys=hsys,
        zodiacal=zodiacal,
    )


@calculation_guard("三式合一分析")
def calculate_sanshiunited_analysis(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    lat: Optional[str] = None,
    lon: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    qimen_options: Optional[Dict[str, Any]] = None,
    taiyi_options: Optional[Dict[str, Any]] = None,
    liureng_yue: Optional[str] = None,
    liureng_is_diurnal: Optional[bool] = None,
    selected_sections: Optional[List[str]] = None,
    use_true_solar_time: bool = True,
) -> Dict[str, Any]:
    """三式合一本地聚合工具。"""
    result = build_sanshiunited_result(
        date=date,
        time=time,
        zone=zone,
        lat=lat,
        lon=lon,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        qimen_options=qimen_options,
        taiyi_options=taiyi_options,
        liureng_yue=liureng_yue,
        liureng_is_diurnal=liureng_is_diurnal,
        use_true_solar_time=use_true_solar_time,
    )
    snapshot_text = result.get("snapshot_text")
    if isinstance(snapshot_text, str) and snapshot_text.strip():
        result["snapshot_export"] = _build_snapshot_export(
            technique="sanshiunited",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
    return result
