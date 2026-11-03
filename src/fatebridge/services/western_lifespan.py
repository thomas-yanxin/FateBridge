"""
Service surfaces for the western *lifespan* techniques.

Each ``calculate_*`` function turns request fields into the standard FateBridge
envelope: ``analysis_context`` (how the chart was cast), ``natal_reference``
(the natal points the technique reads), the technique payload under its own key,
a one-line ``summary``, and a human-readable ``snapshot_text``.

Computation lives in :mod:`fatebridge.core.astrology_lifespan`; this layer only
prepares the natal chart, dispatches to the right builder, and renders output.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astrology_lifespan import (
    build_age_point_payload,
    build_balbillus_payload,
    build_distributions_payload,
    build_harmonic_payload,
    build_jaynes_declination_payload,
    build_keypoints_payload,
    build_lunation_phase_payload,
    build_persian_directed_payload,
    build_planetary_ages_payload,
    build_planetary_arc_payload,
    build_triplicity_rulers_payload,
    build_vedic_progression_payload,
    build_yearsystem129_payload,
)
from fatebridge.core.predictive._common import (
    build_analysis_datetime,
    build_natal_subject,
    build_predictive_birth_info,
    calculate_age_years,
    determine_sect,
    extract_named_longitudes,
    extract_reference_longitudes,
    extract_reference_points,
    planet_label,
    point_absolute_position,
    sect_label,
)
from fatebridge.core.predictive.western_timing import (
    build_secondary_progression_payload,
)
from fatebridge.services.snapshot_builders import (
    render_snapshot_text as _render_snapshot_text,
)
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.house_systems import house_system_fields, normalize_house_system

# Natal targets FateBridge directs in 波斯向运: the ten visible bodies plus the 12
# house cusps (added by the core builder). This is the clean subset 星阙 shares —
# it deliberately omits 星阙's enriched objects (asteroids / midpoints / Arabic lots
# / 四余 / lunar nodes), which live in other FateBridge layers, not the natal chart.
_PERSIAN_TARGET_BODIES = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
]
# Bodies carried by the declination progression (赤纬推运) — the ten visible planets;
# nodes/angles sit on the ecliptic and aren't used for declination parallels.
_DECLINATION_BODIES = [name for name in PLANET_SWISSEPH_IDS if name != "North Node"]
# Ordered Koch house cusps (1st-12th) — 年龄推进点 sweeps these; index 0 = Ascendant.
_HOUSE_CUSP_POINTS = [
    "First_House",
    "Second_House",
    "Third_House",
    "Fourth_House",
    "Fifth_House",
    "Sixth_House",
    "Seventh_House",
    "Eighth_House",
    "Ninth_House",
    "Tenth_House",
    "Eleventh_House",
    "Twelfth_House",
]


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _prepare_chart(
    *,
    house_system: str,
    zodiac_type: str,
    **birth_kwargs: Any,
) -> Tuple[Any, Any, Dict[str, Any], str]:
    """Build birth info, natal subject, natal reference, and sect from kwargs."""
    house_system = normalize_house_system(house_system)
    birth_info = build_predictive_birth_info(
        birth_year=birth_kwargs["birth_year"],
        birth_month=birth_kwargs["birth_month"],
        birth_day=birth_kwargs["birth_day"],
        birth_hour=birth_kwargs["birth_hour"],
        birth_minute=birth_kwargs.get("birth_minute", 0),
        birth_timezone=birth_kwargs.get("birth_timezone"),
        birth_longitude=birth_kwargs["birth_longitude"],
        birth_latitude=birth_kwargs["birth_latitude"],
        name=birth_kwargs.get("name"),
        birth_place=birth_kwargs.get("birth_place"),
    )
    subject = build_natal_subject(
        birth_info, house_system=house_system, zodiac_type=zodiac_type
    )
    natal_reference = extract_reference_points(subject)
    sect = determine_sect(subject)
    return birth_info, subject, natal_reference, sect


def _analysis_context(
    *,
    label: str,
    birth_info: Any,
    sect: str,
    house_system: str,
    zodiac_type: str,
) -> Dict[str, Any]:
    return {
        "tool": label,
        "birth_datetime": birth_info.local_datetime.isoformat(),
        "timezone": birth_info.timezone,
        **house_system_fields(house_system),
        "zodiac_type": zodiac_type,
        "sect": sect,
        "sect_label": sect_label(sect),
        "engine": "fatebridge-offline",
    }


def _envelope(
    *,
    analysis_type: str,
    tool_name: str,
    context: Dict[str, Any],
    natal_reference: Dict[str, Any],
    payload: Dict[str, Any],
    summary: str,
    sections: List[Tuple[str, str]],
) -> Dict[str, Any]:
    return {
        "analysis_type": analysis_type,
        "engine": "fatebridge-offline",
        "analysis_context": context,
        "natal_reference": natal_reference,
        tool_name: payload,
        "summary": summary,
        "snapshot_text": _render_snapshot_text(sections),
    }


# ---------------------------------------------------------------------------
# 1. 调波盘 (astro_harmonic).
# ---------------------------------------------------------------------------


def calculate_harmonic_chart(
    *,
    harmonic: int = 9,
    orb: float = 2.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成调波盘（本命黄经 × 调波数）与同频合相。"""
    label = "调波盘"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_harmonic_payload(natal_reference, harmonic=harmonic, orb=orb)
        conjunction_count = len(payload["resonant_conjunctions"])
        summary = (
            f"{harmonic} 调波盘：检出 {conjunction_count} 组同频合相"
            f"（容许度 {orb}°）。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            ("调波位置", _json_block(payload["positions"])),
            ("同频合相", _json_block(payload["resonant_conjunctions"])),
        ]
        return _envelope(
            analysis_type="西占调波盘",
            tool_name="harmonic_chart",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 2. 行星年龄 (astro_planetary_ages).
# ---------------------------------------------------------------------------


def calculate_planetary_ages(
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成托勒密七年龄段；给定参照日期则标注当前所处年龄段。"""
    label = "行星年龄"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        current_age: Optional[float] = None
        if (
            analysis_year is not None
            or analysis_month is not None
            or analysis_day is not None
        ):
            analysis_datetime = build_analysis_datetime(
                birth_info,
                analysis_year=analysis_year,
                analysis_month=analysis_month,
                analysis_day=analysis_day,
            )
            current_age = calculate_age_years(birth_info, analysis_datetime)
        payload = build_planetary_ages_payload(
            natal_reference, current_age_years=current_age
        )
        if payload["active_planet"] is None:
            summary = "托勒密七年龄段：未指定参照日期，仅列出全生命周期分段。"
        else:
            summary = (
                f"托勒密七年龄段：约 {payload['current_age_years']} 岁，"
                f"当前由{payload['active_planet_label']}主管。"
            )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            ("年龄段表", _json_block(payload["bands"])),
        ]
        return _envelope(
            analysis_type="西占行星年龄",
            tool_name="planetary_ages",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 3. 三分主星推运 (astro_triplicity_rulers).
# ---------------------------------------------------------------------------


def calculate_triplicity_rulers(
    *,
    lifespan: float = 75.0,
    division: str = "thirds",
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成区间光体三分主星划分的人生阶段。"""
    label = "三分主星推运"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_triplicity_rulers_payload(
            natal_reference, sect=sect, lifespan=lifespan, division=division
        )
        rulers = "、".join(
            stage["ruler_label"] or "未定" for stage in payload["stages"]
        )
        summary = (
            f"{payload['sect_label']}以{payload['sect_light_label']}为区间光体，"
            f"{payload['element_label']}三分主星依次为 {rulers}。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "区间光体",
                _json_block(
                    {
                        "sect": payload["sect"],
                        "sect_label": payload["sect_label"],
                        "sect_light": payload["sect_light"],
                        "sect_light_label": payload["sect_light_label"],
                        "sect_light_sign": payload["sect_light_sign"],
                        "element": payload["element"],
                        "element_label": payload["element_label"],
                    }
                ),
            ),
            ("人生阶段", _json_block(payload["stages"])),
        ]
        return _envelope(
            analysis_type="西占三分主星推运",
            tool_name="triplicity_rulers",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 4. 月相推运 (astro_lunation_phase).
# ---------------------------------------------------------------------------


def calculate_lunation_phase(
    *,
    max_age_years: float = 90.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成次限月相推运八相时间轴。"""
    label = "月相推运"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_lunation_phase_payload(
            natal_reference, max_age_years=max_age_years
        )
        summary = (
            f"次限月相推运：本命{payload['natal_phase_label']}"
            f"（日月相位差 {payload['natal_elongation_degree']}°），"
            f"{max_age_years} 岁内共 {len(payload['phase_ingresses'])} 次相位转换。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "本命月相",
                _json_block(
                    {
                        "natal_phase": payload["natal_phase"],
                        "natal_phase_label": payload["natal_phase_label"],
                        "natal_elongation_degree": payload["natal_elongation_degree"],
                        "progression_rate_deg_per_year": payload[
                            "progression_rate_deg_per_year"
                        ],
                        "synodic_cycle_years": payload["synodic_cycle_years"],
                    }
                ),
            ),
            ("相位转换时间轴", _json_block(payload["phase_ingresses"])),
        ]
        return _envelope(
            analysis_type="西占月相推运",
            tool_name="lunation_phase",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 5. 界推运 / 分配法 (astro_distributions).
# ---------------------------------------------------------------------------


def calculate_distributions(
    *,
    time_key: str = "Ptolemy",
    max_age_years: float = 90.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成界推运（上升历经埃及界限）的分配主星时间轴。"""
    label = "界推运"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_distributions_payload(
            natal_reference, time_key=time_key, max_age_years=max_age_years
        )
        summary = (
            f"界推运（{time_key} 时间钥匙）：{max_age_years} 岁内"
            f"上升历经 {len(payload['periods'])} 段界限分配。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "分配设置",
                _json_block(
                    {
                        "time_key": payload["time_key"],
                        "rate_deg_per_year": payload["rate_deg_per_year"],
                        "ascendant_absolute_degree": payload[
                            "ascendant_absolute_degree"
                        ],
                        "max_age_years": payload["max_age_years"],
                    }
                ),
            ),
            ("界限分配时间轴", _json_block(payload["periods"])),
        ]
        return _envelope(
            analysis_type="西占界推运",
            tool_name="distributions",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 6. Balbillus 129年系统 (astro_balbillus).
# ---------------------------------------------------------------------------


def calculate_balbillus(
    *,
    start_planet: str = "Sun",
    mode: str = "nearest",
    max_age_years: float = 120.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成 Balbillus 129 年系统主限与子限时间轴。"""
    label = "Balbillus 129年系统"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_balbillus_payload(
            natal_reference,
            start_planet=start_planet,
            mode=mode,
            max_age_years=max_age_years,
        )
        summary = (
            f"Balbillus 129 年系统（{payload['mode_label']}）：自"
            f"{payload['start_planet_label']}起，{max_age_years} 岁内"
            f"共 {len(payload['periods'])} 段主限。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "系统设置",
                _json_block(
                    {
                        "start_planet": payload["start_planet"],
                        "mode": payload["mode"],
                        "mode_label": payload["mode_label"],
                        "zodiacal_order": payload["zodiacal_order"],
                        "max_age_years": payload["max_age_years"],
                    }
                ),
            ),
            ("主限·子限时间轴", _json_block(payload["periods"])),
        ]
        return _envelope(
            analysis_type="西占Balbillus 129年系统",
            tool_name="balbillus",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 7. 数字相位推运 (astro_keypoints).
# ---------------------------------------------------------------------------


def calculate_keypoints(
    *,
    release_mode: str = "soul",
    max_age_years: int = 120,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成数字相位推运（120 年关键点）激活时间轴。"""
    label = "数字相位推运"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_keypoints_payload(
            natal_reference, release_mode=release_mode, max_age_years=max_age_years
        )
        summary = (
            f"数字相位推运（释放点={payload['release_mode_label']}）："
            f"共 {len(payload['activations'])} 个激活年。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "星位挂钩",
                _json_block(
                    {
                        "release_mode": payload["release_mode"],
                        "release_mode_label": payload["release_mode_label"],
                        "positions": payload["positions"],
                    }
                ),
            ),
            ("激活时间轴", _json_block(payload["activations"])),
        ]
        return _envelope(
            analysis_type="西占数字相位推运",
            tool_name="keypoints",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 8. 129年系统 (astro_yearsystem129).
# ---------------------------------------------------------------------------


def calculate_yearsystem129(
    *,
    start_planet: str = "Sun",
    max_age_years: float = 129.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成 129 年系统（七星小年轮值）时间轴。"""
    label = "129年系统"
    try:
        birth_info, _subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        payload = build_yearsystem129_payload(
            natal_reference, start_planet=start_planet, max_age_years=max_age_years
        )
        summary = (
            f"129 年系统：自{payload['start_planet_label']}起，"
            f"{max_age_years} 岁内共 {len(payload['periods'])} 段小年轮值"
            f"（{payload['sequence_model_label']}）。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "系统设置",
                _json_block(
                    {
                        "start_planet": payload["start_planet"],
                        "sequence_model": payload["sequence_model"],
                        "total_cycle_years": payload["total_cycle_years"],
                        "zodiacal_order": payload["zodiacal_order"],
                        "max_age_years": payload["max_age_years"],
                    }
                ),
            ),
            ("小年轮值时间轴", _json_block(payload["periods"])),
        ]
        return _envelope(
            analysis_type="西占129年系统",
            tool_name="yearsystem129",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


# ---------------------------------------------------------------------------
# 9. 行星弧方向 (astro_planetaryarc).
# ---------------------------------------------------------------------------


def calculate_planetary_arc(
    *,
    arc_source: str = "Moon",
    orb: float = 1.0,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成行星弧方向盘（以 arc_source 的次限弧推动全盘）。"""
    label = "行星弧方向"
    try:
        birth_info, natal_subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        analysis_datetime = build_analysis_datetime(
            birth_info,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
        )
        progression = build_secondary_progression_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        payload = build_planetary_arc_payload(
            extract_reference_longitudes(natal_subject),
            extract_reference_longitudes(progression["subject"]),
            arc_source=arc_source,
            orb=orb,
        )
        age_years = calculate_age_years(birth_info, analysis_datetime)
        summary = (
            f"行星弧方向：以{payload['arc_source_label']}次限弧 "
            f"{payload['arc_degrees']}° 推动全盘（约 {round(age_years, 1)} 岁）。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        context["analysis_datetime"] = analysis_datetime.isoformat()
        context["age_years"] = round(age_years, 4)
        sections = [
            ("起盘信息", _json_block(context)),
            (
                "方向设置",
                _json_block(
                    {
                        "arc_source": payload["arc_source"],
                        "arc_degrees": payload["arc_degrees"],
                        "orb": payload["orb"],
                        "positions": payload["positions"],
                    }
                ),
            ),
            ("相位", _json_block(payload["hits"])),
        ]
        return _envelope(
            analysis_type="西占行星弧方向",
            tool_name="planetary_arc",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


def _persian_directed_table(payload: Dict[str, Any]) -> str:
    """Render the 波斯向运 hit list as 星阙's 应期 table."""
    hits = payload.get("hits", [])
    if not hits:
        return "（本盘无波斯向运应期）"
    lines = [
        "黄经象征向运(1°/年)：所有行星每年 +1°，本命宫头不动；下表为向运星触及本命的应期。"
        "（口径：10 行星 + 12 宫头；未含小行星/中点/福点/四余/交点。）",
        "",
        "| 年龄 | 日期 | 向运星 | 相位 | 本命对象 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for hit in hits:
        significator = hit["significator"]
        sig_name = (
            significator if "宫头" in str(significator) else planet_label(significator)
        )
        lines.append(
            f"| {hit['age']} | {hit['date'] or '-'} | {hit['promittor_label']} "
            f"| {hit['aspect']}° | {sig_name} |"
        )
    return "\n".join(lines)


def calculate_persian_directed(
    *,
    max_age_years: float = 90.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成波斯向运盘（符号 1°/年，向运星触及本命的应期表）。"""
    label = "波斯向运"
    try:
        birth_info, natal_subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        natal_longitudes = extract_named_longitudes(
            natal_subject, _PERSIAN_TARGET_BODIES
        )
        house_cusps = [
            point_absolute_position(natal_subject, point_name)
            for point_name in _HOUSE_CUSP_POINTS
        ]
        payload = build_persian_directed_payload(
            natal_longitudes,
            house_cusps,
            birth_datetime=birth_info.local_datetime,
            max_age_years=max_age_years,
        )
        summary = (
            f"波斯向运：7 政向运星每年 +1° 推动，"
            f"在 0–{round(max_age_years)} 岁内共 {payload['hit_count']} 个应期。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        context["max_age_years"] = max_age_years
        sections = [
            ("起盘信息", _json_block(context)),
            ("波斯向运（Persian Directed）", _persian_directed_table(payload)),
            ("应期明细", _json_block(payload["hits"])),
        ]
        return _envelope(
            analysis_type="西占波斯向运",
            tool_name="persian_directed",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


def _age_point_table(payload: Dict[str, Any]) -> str:
    """Render the 年龄推进点 timeline as 星阙's 落座/合本命 table."""
    points = payload.get("points", [])
    if not points:
        return "（本盘无年龄推进点数据）"
    contacts = payload.get("contacts", [])
    lines = [
        "年龄点自上升点起，沿 Koch 宫顺行，每宫 6 年、72 年回归上升；"
        "落于本命星处（合相）为人生关键节点。",
    ]
    if contacts:
        lines.append("")
        lines.append(
            "关键岁数（合本命）："
            + "；".join(f"{c['age']}岁合{c['body_label']}" for c in contacts)
        )
    lines.append("")
    lines.append("| 年龄 | 落座 | 宫 | 合本命 |")
    lines.append("| --- | --- | --- | --- |")
    for point in points:
        seat = f"{point['sign_label']} {point['signlon']}°"
        aspect_to = point["aspect_to_label"] or "—"
        lines.append(
            f"| {point['age']}岁 | {seat} | {point['house']}宫 | {aspect_to} |"
        )
    return "\n".join(lines)


def calculate_age_point(
    *,
    max_age_years: float = 72.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成年龄推进点盘（Huber Age Point，Koch 宫，6 年/宫，72 年回归上升）。

    Huber 法以 Koch 分宫制为基准，故本工具固定使用 Koch 宫；请求里的 ``house_system``
    会被接收但忽略（仅为消化统一的 lifespan 请求字段）。
    """
    label = "年龄推进点"
    house_system = "K"  # Huber Age Point is defined on Koch houses (override request).
    try:
        birth_info, natal_subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        natal_longitudes = extract_named_longitudes(
            natal_subject, _PERSIAN_TARGET_BODIES
        )
        koch_cusps = [
            point_absolute_position(natal_subject, point_name)
            for point_name in _HOUSE_CUSP_POINTS
        ]
        payload = build_age_point_payload(
            natal_longitudes,
            koch_cusps,
            max_age_years=max_age_years,
        )
        summary = (
            f"年龄推进点：自上升点起沿 Koch 宫每宫 6 年推进，"
            f"在 0–{round(max_age_years)} 岁内共 {len(payload['contacts'])} 次合本命。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        context["max_age_years"] = max_age_years
        sections = [
            ("起盘信息", _json_block(context)),
            ("年龄推进点（Age Point / Huber）", _age_point_table(payload)),
            ("合本命明细", _json_block(payload["contacts"])),
        ]
        return _envelope(
            analysis_type="西占年龄推进点",
            tool_name="age_point",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


def calculate_vedicprog(
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    orb: float = 1.5,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """原生Lahiri恒星黄道次限，推运点与同一黄道本命点比较。

    技法固定为Sidereal；兼容请求中的zodiac_type不改变该定义。
    本命与次限都由共享原生底盘求值，不调用可降级的线性岁差近似。
    """
    label = "恒星推运"
    try:
        birth_info, natal_subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type="Sidereal", **birth_kwargs
        )
        analysis_datetime = build_analysis_datetime(
            birth_info,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
        )
        age_years = calculate_age_years(birth_info, analysis_datetime)
        progression = build_secondary_progression_payload(
            birth_info,
            natal_subject,
            analysis_datetime=analysis_datetime,
            house_system=house_system,
            zodiac_type="Sidereal",
        )
        payload = build_vedic_progression_payload(
            extract_reference_longitudes(progression["subject"]),
            extract_reference_longitudes(natal_subject),
            orb=orb,
        )
        summary = (
            f"恒星推运：恒星黄道二次推运（约 {round(age_years, 1)} 岁），"
            f"检出 {len(payload['hits'])} 个推运相位（容许度 {orb}°）。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type="Sidereal",
        )
        context["ayanamsha"] = "Lahiri (Swiss Ephemeris native)"
        context["analysis_datetime"] = analysis_datetime.isoformat()
        context["age_years"] = round(age_years, 4)
        sections = [
            ("起盘信息", _json_block(context)),
            ("推运位置", _json_block(payload["positions"])),
            ("推运相位", _json_block(payload["hits"])),
        ]
        return _envelope(
            analysis_type="西占恒星推运",
            tool_name="vedic_progression",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)


def _body_declinations(utc_datetime: Any) -> Dict[str, float]:
    """Equatorial declination of each tracked body at a UTC moment (swisseph)."""
    times = ephemeris_time(utc_datetime)
    declinations: Dict[str, float] = {}
    for body in _DECLINATION_BODIES:
        state = _swisseph_planet_state(body, julian_day_tt=times.jd_tt)
        if state is not None and state[0].get("declination") is not None:
            declinations[body] = float(state[0]["declination"])
    return declinations


def calculate_jaynesprog(
    *,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    orb: float = 1.0,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    **birth_kwargs: Any,
) -> Dict[str, Any]:
    """生成赤纬推运盘（二次推运后看赤纬平行/反平行）。"""
    label = "赤纬推运"
    try:
        birth_info, _natal_subject, natal_reference, sect = _prepare_chart(
            house_system=house_system, zodiac_type=zodiac_type, **birth_kwargs
        )
        analysis_datetime = build_analysis_datetime(
            birth_info,
            analysis_year=analysis_year,
            analysis_month=analysis_month,
            analysis_day=analysis_day,
        )
        age_years = calculate_age_years(birth_info, analysis_datetime)
        # Secondary progression: a day after birth per year of life ("day for a year").
        progressed_utc = birth_info.require_utc_datetime + timedelta(days=age_years)
        payload = build_jaynes_declination_payload(
            _body_declinations(progressed_utc),
            _body_declinations(birth_info.require_utc_datetime),
            orb=orb,
        )
        summary = (
            f"赤纬推运：二次推运（约 {round(age_years, 1)} 岁）后，"
            f"检出 {len(payload['parallels'])} 组赤纬平行/反平行（容许度 {orb}°）。"
        )
        context = _analysis_context(
            label=label,
            birth_info=birth_info,
            sect=sect,
            house_system=house_system,
            zodiac_type=zodiac_type,
        )
        context["analysis_datetime"] = analysis_datetime.isoformat()
        context["age_years"] = round(age_years, 4)
        sections = [
            ("起盘信息", _json_block(context)),
            ("赤纬平行/反平行", _json_block(payload["parallels"])),
        ]
        return _envelope(
            analysis_type="西占赤纬推运",
            tool_name="jaynes_declination",
            context=context,
            natal_reference=natal_reference,
            payload=payload,
            summary=summary,
            sections=sections,
        )
    except Exception as exc:
        return handle_calculation_error(exc, label)
