"""Relationship mode/focus selection and final payload orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from pydantic import JsonValue

from fatebridge.core.astro.aspects import (
    _build_directional_relative_antiscia,
    _build_directional_relative_aspects,
    _build_directional_relative_midpoints,
    _count_directional_relative_midpoint_hits,
    _flatten_directional_relative_aspects,
)
from fatebridge.core.astro.birth import AstroBirthInfo, require_resolved_birth_timezone
from fatebridge.core.astro.profiles import (
    _derive_engine_profile,
    _precision_label_zh,
    _resolve_relative_house_system,
    _resolve_relative_zodiacal_mode,
)
from fatebridge.core.astro.reference import (
    RELATIONSHIP_FOCUS_ALIASES,
    RELATIONSHIP_FOCUS_DEFS,
    RELATIVE_MODE_EXACT_ALIASES,
    RELATIVE_MODE_FALLBACK_ALIASES,
    RELATIVE_MODE_LABELS_ZH,
    RELATIVE_MODE_NUMERIC_MAP,
)
from fatebridge.core.astro.relationship_charts import (
    _build_marks_chart,
    _build_relative_base_chart,
    _build_relative_influence_pair,
    _build_timespace_chart,
    _composite_chart,
)
from fatebridge.core.astro.relationship_geometry import DAVISON_VARIANTS, davison_birth


@dataclass(frozen=True, kw_only=True)
class RelativeModeSelection:
    selector: int | str
    resolution: str
    mode: str


class RelationshipFocusFacts(TypedDict):
    focus: str
    focus_label_zh: str
    emphasis_houses: list[int]
    emphasis_bodies: list[str]
    note: str
    focused_synastry_aspects: list[dict[str, JsonValue]]
    focused_aspect_count: int


def _normalize_relative_mode(value: int | str | None) -> RelativeModeSelection:
    mode_selector = 0 if value is None or value == "" else value
    normalized: str | None = None
    resolution = "default"

    if isinstance(mode_selector, int) and mode_selector in RELATIVE_MODE_NUMERIC_MAP:
        normalized = RELATIVE_MODE_NUMERIC_MAP[mode_selector]
        resolution = "numeric"
    elif isinstance(mode_selector, str):
        stripped = mode_selector.strip()
        if stripped.isdigit():
            numeric_value = int(stripped)
            normalized = RELATIVE_MODE_NUMERIC_MAP.get(numeric_value)
            if normalized is not None:
                resolution = "numeric_string"
        if normalized is None:
            normalized = RELATIVE_MODE_EXACT_ALIASES.get(stripped)
            if normalized is not None:
                resolution = "exact_alias"
        lowered = stripped.lower()
        if normalized is None:
            normalized = RELATIVE_MODE_FALLBACK_ALIASES.get(stripped)
            if normalized is not None:
                resolution = "fallback_alias"
        if normalized is None:
            normalized = RELATIVE_MODE_FALLBACK_ALIASES.get(lowered)
            if normalized is not None:
                resolution = "fallback_alias_casefold"

    if normalized is None:
        if mode_selector not in (None, "", 0, "0"):
            raise ValueError(
                "relative_mode 无效，请使用 Compare、Synastry、Composite，"
                "或使用 0/1/2 数值别名。"
            )
        normalized = "compare"
        resolution = "default_compare_fallback"

    return RelativeModeSelection(
        selector=mode_selector, resolution=resolution, mode=normalized
    )


def relationship_focus_block(
    focus: str | None, synastry_aspects: list[dict[str, JsonValue]]
) -> RelationshipFocusFacts:
    """Retain contacts involving either of the selected focus's significators."""
    normalized = (
        "general"
        if focus is None
        else RELATIONSHIP_FOCUS_ALIASES.get(str(focus).strip().casefold())
    )
    if normalized is None:
        raise ValueError(
            "relationship_focus 无效，请使用 marriage/婚姻、romance/恋爱或 general/泛"
        )
    elif normalized == "general":
        return {
            "focus": "general",
            "focus_label_zh": "泛",
            "emphasis_houses": [],
            "emphasis_bodies": [],
            "note": "未指定关系取向，未对 synastry 相位做意图过滤。",
            "focused_synastry_aspects": [],
            "focused_aspect_count": 0,
        }
    else:
        focus_definition = RELATIONSHIP_FOCUS_DEFS[normalized]
        significators = set(focus_definition["bodies"])
        focused_aspects = [
            aspect
            for aspect in synastry_aspects
            if aspect.get("inner") in significators
            or aspect.get("outer") in significators
        ]
        return {
            "focus": normalized,
            "focus_label_zh": focus_definition["label_zh"],
            "emphasis_houses": list(focus_definition["houses"]),
            "emphasis_bodies": list(focus_definition["bodies"]),
            "note": focus_definition["note"],
            "focused_synastry_aspects": focused_aspects,
            "focused_aspect_count": len(focused_aspects),
        }


def build_relative_payload(
    inner_birth: AstroBirthInfo,
    outer_birth: AstroBirthInfo,
    relative_mode: int | str | None = None,
    hsys: int = 3,
    zodiacal: int = 0,
    relationship_focus: str | None = None,
    davison_variant: str = "uncorrected",
    composite_house_method: str = "midpoint",
    high_latitude_fallback: str = "error",
) -> dict[str, Any]:
    """Calculate both natal charts and the selected relationship layer."""
    require_resolved_birth_timezone(inner_birth.timezone_source)
    require_resolved_birth_timezone(outer_birth.timezone_source)
    mode_selection = _normalize_relative_mode(relative_mode)
    relative_house_system = _resolve_relative_house_system(hsys)
    zodiacal_info = _resolve_relative_zodiacal_mode(zodiacal)
    inner_chart = _build_relative_base_chart(
        inner_birth,
        house_system_info=relative_house_system,
        zodiacal_info=zodiacal_info,
        high_latitude_fallback=high_latitude_fallback,
    )
    outer_chart = _build_relative_base_chart(
        outer_birth,
        house_system_info=relative_house_system,
        zodiacal_info=zodiacal_info,
        high_latitude_fallback=high_latitude_fallback,
    )
    inner_to_outer_aspects = _build_directional_relative_aspects(
        inner_chart["planets"], outer_chart["planets"]
    )
    outer_to_inner_aspects = _build_directional_relative_aspects(
        outer_chart["planets"], inner_chart["planets"]
    )
    synastry_aspects = _flatten_directional_relative_aspects(
        inner_to_outer_aspects, source_key="inner", target_key="outer"
    )
    synastry_aspects = sorted(
        synastry_aspects,
        key=lambda item: (item["orb"], item["inner"], item["outer"]),
    )
    normalized_mode = mode_selection.mode
    if davison_variant not in DAVISON_VARIANTS:
        raise ValueError("davison_variant必须为uncorrected、corrected或spherical")
    if (
        normalized_mode not in {"timespace", "marks"}
        and davison_variant != "uncorrected"
    ):
        raise ValueError("davison_variant仅适用于TimeSpace和Marks，不能静默忽略")
    marks_charts: dict[str, dict[str, Any]] = {}
    if normalized_mode == "composite":
        primary_chart = _composite_chart(
            inner_chart,
            outer_chart,
            house_system=relative_house_system["key"],
            zodiacal_info=zodiacal_info,
            composite_house_method=composite_house_method,
            midpoint_latitude=(inner_birth.latitude + outer_birth.latitude) / 2.0,
        )
    elif normalized_mode == "timespace":
        primary_chart = _build_timespace_chart(
            inner_birth,
            outer_birth,
            house_system_info=relative_house_system,
            zodiacal_info=zodiacal_info,
            davison_variant=davison_variant,
        )
    elif normalized_mode == "marks":
        relationship_birth, _ = davison_birth(
            inner_birth, outer_birth, variant=davison_variant
        )
        marks_charts = {
            role: _build_marks_chart(
                person,
                relationship_birth,
                house_system_info=relative_house_system,
                zodiacal_info=zodiacal_info,
                davison_variant=davison_variant,
            )
            for role, person in (("inner", inner_birth), ("outer", outer_birth))
        }
        primary_chart = marks_charts["inner"]
    else:
        primary_chart = {}
    inner_influence, outer_influence = _build_relative_influence_pair(
        inner_chart,
        outer_chart,
        house_system=relative_house_system["key"],
        zodiacal_info=zodiacal_info,
    )
    inner_to_outer_midpoint = _build_directional_relative_midpoints(
        inner_chart["planets"], outer_chart["planets"]
    )
    outer_to_inner_midpoint = _build_directional_relative_midpoints(
        outer_chart["planets"], inner_chart["planets"]
    )
    inner_to_outer_antiscia = _build_directional_relative_antiscia(
        inner_chart["planets"], outer_chart["planets"]
    )
    outer_to_inner_antiscia = _build_directional_relative_antiscia(
        outer_chart["planets"], inner_chart["planets"]
    )
    inner_to_outer_contra_antiscia = _build_directional_relative_antiscia(
        inner_chart["planets"], outer_chart["planets"], contra=True
    )
    outer_to_inner_contra_antiscia = _build_directional_relative_antiscia(
        outer_chart["planets"], inner_chart["planets"], contra=True
    )
    inner_chart_profile = inner_chart["chart_profile"]
    outer_chart_profile = outer_chart["chart_profile"]
    primary_chart_profile = primary_chart.get("chart_profile", {})
    engine_profile = _derive_engine_profile(
        inner_chart_profile, outer_chart_profile, primary_chart_profile
    )
    precision_label = _precision_label_zh(engine_profile["engine_precision"])

    if normalized_mode == "compare":
        primary_layer = "directional_synastry"
        summary = [
            "已生成 FateBridge 比较盘分析。",
            f"A对B相位主体数：{len(inner_to_outer_aspects)}。",
            f"B对A相位主体数：{len(outer_to_inner_aspects)}。",
            f"A对B中点相位命中：{_count_directional_relative_midpoint_hits(inner_to_outer_midpoint)}。",
            f"A对B映点命中：{len(inner_to_outer_antiscia)}。",
            "影响图盘、中点相位与映点/反映点均已提供" f"{precision_label}结果。",
        ]
    elif normalized_mode == "composite":
        primary_layer = "composite_chart"
        summary = [
            "已生成 FateBridge 组合盘分析。",
            f"合成盘行星数量：{len(primary_chart['planets'])}。",
            f"A对B相位主体数：{len(inner_to_outer_aspects)}。",
            f"A对B中点相位命中：{_count_directional_relative_midpoint_hits(inner_to_outer_midpoint)}。",
            f"A对B映点命中：{len(inner_to_outer_antiscia)}。",
            "影响图盘、中点相位与映点/反映点均已提供" f"{precision_label}结果。",
        ]
    elif normalized_mode == "influence":
        primary_layer = "influence_chart_pair"
        summary = [
            "已生成 FateBridge 影响盘分析。",
            f"A视角影响图盘星体数：{len(inner_influence['chart']['planets'])}。",
            f"B视角影响图盘星体数：{len(outer_influence['chart']['planets'])}。",
            f"A对B相位主体数：{len(inner_to_outer_aspects)}。",
            "影响盘主层由 inner / outer 中双方视角图盘构成。",
        ]
    elif normalized_mode == "timespace":
        primary_layer = "timespace_chart"
        summary = [
            "已生成 FateBridge 时空中点盘分析。",
            f"时空中点盘行星数量：{len(primary_chart['planets'])}。",
            f"A对B相位主体数：{len(inner_to_outer_aspects)}。",
            (
                "主盘采用双方出生时间与地理位置中点生成的"
                f"{_precision_label_zh(primary_chart_profile['engine_precision'])}盘。"
            ),
        ]
    else:
        assert normalized_mode == "marks"
        primary_layer = "marks_chart_pair"
        summary = [
            f"已生成{inner_birth.name}、{outer_birth.name}各自的马克斯盘；摘要主盘对应{inner_birth.name}。",
            f"内方／外方星体数：{len(marks_charts['inner']['planets'])}／{len(marks_charts['outer']['planets'])}。",
            f"A对B相位主体数：{len(inner_to_outer_aspects)}。",
            (
                "各个人盘由本人与双方Davison时空数据再次计算Davison得到。"
                "这是现代关系占星的派生方法，其数值可复现性不代表现实关系结论。"
            ),
        ]

    relationship_profile: dict[str, Any] = {
        "chart_type": "relative",
        "relative_mode_input": mode_selection.selector,
        "relative_mode_resolution": mode_selection.resolution,
        "relative_mode_normalized": normalized_mode,
        "relative_mode_label_zh": RELATIVE_MODE_LABELS_ZH[normalized_mode],
        "hsys": hsys,
        "house_system": relative_house_system["key"],
        "house_system_label_zh": relative_house_system["label_zh"],
        "zodiacal": zodiacal,
        "zodiac_mode": zodiacal_info["zodiac"],
        "zodiac_label_zh": zodiacal_info["label_zh"],
        **engine_profile,
        "primary_layer": primary_layer,
        "mode_status": "implemented",
    }
    if normalized_mode == "marks":
        relationship_profile["primary_chart_role"] = "inner"
    if normalized_mode in {"timespace", "marks"}:
        relationship_profile["davison_variant"] = davison_variant
    if primary_chart:
        relationship_profile["derivation_policy"] = primary_chart_profile[
            "derivation_policy"
        ]
    relationship_profile["relative_midpoint_policy"] = (
        "unrounded shorter-arc points; exact diametric pairs retain both undecided candidates"
    )
    relationship_profile["focus"] = relationship_focus_block(
        relationship_focus, synastry_aspects
    )
    payload = {
        "relationship_profile": relationship_profile,
        "inner_chart": inner_chart,
        "outer_chart": outer_chart,
        "synastry_aspects": synastry_aspects,
        "in_to_out_aspects": inner_to_outer_aspects,
        "out_to_in_aspects": outer_to_inner_aspects,
        "in_to_out_midpoint": inner_to_outer_midpoint,
        "out_to_in_midpoint": outer_to_inner_midpoint,
        "in_to_out_antiscia": inner_to_outer_antiscia,
        "out_to_in_antiscia": outer_to_inner_antiscia,
        "in_to_out_contra_antiscia": inner_to_outer_contra_antiscia,
        "out_to_in_contra_antiscia": outer_to_inner_contra_antiscia,
        "chart": primary_chart,
        # note (projection): The shared response schema includes an empty Marks pair for other modes.
        "marks_charts": marks_charts,
        "inner": inner_influence,
        "outer": outer_influence,
        "summary": summary,
    }
    if normalized_mode == "composite" and primary_chart.get("planets"):
        payload["composite_to_inner_aspects"] = _build_directional_relative_aspects(
            primary_chart["planets"], inner_chart["planets"]
        )
        payload["composite_to_outer_aspects"] = _build_directional_relative_aspects(
            primary_chart["planets"], outer_chart["planets"]
        )
    return payload
