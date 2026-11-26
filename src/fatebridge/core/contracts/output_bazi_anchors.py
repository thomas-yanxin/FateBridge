"""Required full-service BaZi facts; projected models stay partial."""

from __future__ import annotations

from typing import Any

from fatebridge.utils.data import TenGod

TOPICS = (
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
)
BAZI_ANCHOR_TOOLS = frozenset(
    ("bazi_overview", "bazi_birth_chart", *("bazi_" + t for t in TOPICS))
)
POSITIONS = ("year", "month", "day", "hour")


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("完整八字结果缺少计算依据对象")
    return value


def _keys(
    value: Any, names: str, *, nullable: set[str] | None = None
) -> dict[str, Any]:
    obj = _object(value)
    for key in names.split():
        if key not in obj or (obj[key] is None and key not in (nullable or set())):
            raise ValueError("完整八字结果缺少计算依据字段：" + key)
        if isinstance(obj[key], str) and not obj[key].strip():
            raise ValueError("完整八字计算依据不能为空字符串：" + key)
    return obj


def _calendar(value: Any) -> None:
    c = _keys(
        value,
        "timezone solar_datetime current_solar_term next_solar_term solar_term_delta bazi_month_boundary lunar_calendar lunar_calendar_support",
        nullable={"lunar_calendar"},
    )
    support = _keys(c["lunar_calendar_support"], "supported supported_range")
    _keys(support["supported_range"], "start end")
    if support["supported"] is True:
        _keys(c["lunar_calendar"], "year month day is_leap_month day_ganzhi")
    elif support["supported"] is False:
        _keys(support, "reason")
        if c["lunar_calendar"] is not None:
            raise ValueError("表外农历不能以完整计算结果交付")
    else:
        raise ValueError("完整八字结果须明示农历支持状态")
    month = _keys(
        c["bazi_month_boundary"],
        "branch month_index comparison_datetime elapsed_basis elapsed_seconds_since_start elapsed_seconds_until_next days_since_start days_until_next start_term next_term",
    )
    for term in (
        c["current_solar_term"],
        c["next_solar_term"],
        month["start_term"],
        month["next_term"],
    ):
        evidence = _keys(term, "name timezone resolution_provider ephemeris_model")
        if evidence.get("datetime_utc") is not None:
            _keys(evidence, "datetime_utc civil_point comparison_policy")
        else:
            _keys(evidence, "datetime datetime_with_offset utc_offset_seconds fold")
    _keys(c["solar_term_delta"], "days_since_current days_until_next description")


def _timing(value: Any) -> None:
    t = _keys(
        value,
        "source dayun_pillar liunian_pillar overridden",
        nullable={"dayun_pillar"},
    )
    _keys(t["overridden"], "dayun_pillar liunian_pillar")
    if t["source"] != "explicit_pillar_overrides":
        _keys(
            t,
            "analysis_date analysis_datetime timezone input_granularity anchor_policy year_boundary_policy boundary_status boundaries_on_date",
        )


def require_complete_bazi_anchors(key: str, result: dict[str, Any]) -> None:
    """Validate required anchors on full successful BaZi results."""
    if key not in BAZI_ANCHOR_TOOLS:
        return
    if key in {"bazi_overview", "bazi_birth_chart"}:
        root = result if key == "bazi_overview" else result.get("bazi_birth")
        r = _keys(
            root,
            "person_info four_pillars day_master element_distribution favorable_elements favorable_elements_status ten_gods patterns calendar_context structure_profile intra_month_duty",
        )
        _keys(
            r["person_info"],
            "name gender birth_datetime normalized_birth_datetime birth_timezone zi_hour_policy",
        )
        pillars = _keys(r["four_pillars"], "year month day hour")
        for name in POSITIONS:
            _keys(pillars[name], "stem branch")
        dm = _keys(
            r["day_master"],
            "stem element polarity strength classical_adjudication",
        )
        _keys(r["ten_gods"], "year month day hour")
        profile = _keys(
            r["structure_profile"],
            "assessment_status dominant_structure useful_elements avoid_elements seasonal_climate classical_adjudication",
        )
        if dm["classical_adjudication"] != profile["classical_adjudication"]:
            raise ValueError("日主与格局须复用同次力量裁定")
        if key == "bazi_birth_chart":
            _keys(
                r,
                "three_origins taixi kongwang shensha three_origins_shensha timing_overview",
            )
    else:
        topic = key.removeprefix("bazi_")
        r = _keys(
            result.get(topic + "_analysis"),
            "calendar_context timing_context topic_facts",
        )
        _timing(r["timing_context"])
        facts = _keys(
            r["topic_facts"],
            "topic four_pillars day_master favorable_elements dominant_structure natal_stars markers timing_layers",
        )
        if facts["topic"] != topic:
            raise ValueError("完整专题依据须对应实际专题")
    _calendar(r["calendar_context"])
