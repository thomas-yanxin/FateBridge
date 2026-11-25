"""Bind Heluo's consumed boundaries to the shared civil-year term window."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Any

from fatebridge.core.almanac import (
    SolarTerm,
    _term_window,
    get_solar_term_environment_key,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.core.numerology.numerology_solar_sources import attach_solar_sources
from fatebridge.utils.civil_time import (
    CivilPoint,
    UTCCalendar,
    ZonedCalendar,
    utc_calendar,
)
from fatebridge.utils.errors import NumerologySourceError

POLICY_ID = "heluo_shared_solar_context_v1"
LI_TERMS = frozenset({"立春", "立夏", "立秋", "立冬"})
COMPARISON_POLICY = "retained_nominal_civil_point_v1"


@dataclass(frozen=True)
class ResolvedSolarContext:
    """The actual selected boundaries, before their JSON evidence boundary."""

    current_term: SolarTerm
    preceding_solstice: SolarTerm
    next_four_li: SolarTerm
    local_year: int
    zone: str
    birth_utc: UTCCalendar

    def to_record(self) -> dict:
        return {
            "policy_id": POLICY_ID,
            "comparison_policy": COMPARISON_POLICY,
            "context_local_year": self.local_year,
            "context_timezone": self.zone,
            "birth_instant_utc": self.birth_utc.isoformat(),
            "dependencies": [
                {
                    "role": role,
                    "record": term.as_dict(),
                    "instant_utc": term.calendar.utc.isoformat(),
                    "ephemeris_retflags": list(term.ephemeris_retflags),
                    "ephemeris_library_version": term.ephemeris_library_version,
                }
                for role, term in (
                    ("current_term", self.current_term),
                    ("preceding_solstice", self.preceding_solstice),
                    ("next_four_li", self.next_four_li),
                )
            ],
            "environment_unchanged_at_observation_points": True,
            "calendar_context_match": None,
            "scope": (
                "Same local-civil-year window as shared year/month calculation. "
                "Actual consumed providers/models and unrounded nominal civil "
                "points are retained; neighbouring roots do not extend public "
                "model years. Before/after environment observations do not "
                "prove atomic file reads, independent accuracy or historical UTC."
            ),
        }


def resolve_solar_context(anchor: datetime, zone: str) -> ResolvedSolarContext:
    """Retain exactly the current term, last solstice and next four-li used.

    The input's local civil year selects the canonical adjacent-year allowance.
    Neither a UTC year crossing nor a guarded cached year authorizes a separate
    out-of-range public year-grid request under an explicit model.
    """
    local = localize_datetime(anchor, zone)
    if local.utcoffset() is None:
        raise ValueError("节气上下文需要带时区的真实时刻。")
    else:
        pass
    birth_utc = utc_calendar(local)
    at = birth_utc.julian_day_exact()
    environment = get_solar_term_environment_key(year=local.year)
    window = _term_window(local, zone)
    before = [t for t in window if t.point.day <= at]
    after = [t for t in window if t.point.day > at]
    try:
        selected = (
            ("current_term", before[-1]),
            (
                "preceding_solstice",
                next(t for t in reversed(before) if t.name in {"冬至", "夏至"}),
            ),
            ("next_four_li", next(t for t in after if t.name in LI_TERMS)),
        )
        for _, term in selected:
            require_calculated_solar_term(term)
    except (IndexError, StopIteration, RuntimeError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
    if get_solar_term_environment_key(year=local.year) != environment:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict")
    else:
        pass
    return ResolvedSolarContext(
        selected[0][1], selected[1][1], selected[2][1], local.year, zone, birth_utc
    )


def _record_day(record: dict) -> Fraction:
    """Read complete binding facts; old label-only fixtures keep label semantics."""
    if "civil_point" in record:
        point = record["civil_point"]
        return Fraction(int(point["numerator"]), int(point["denominator"]))
    else:
        pass
    if record.get("comparison_policy") == COMPARISON_POLICY:
        raise ValueError("精确民用比较政策缺少已保留的主点。")
    else:
        pass
    return ZonedCalendar.from_isoformat(
        record["datetime_with_offset"]
    ).utc.julian_day_exact()


def bind_solar_context(solar: dict, calendar_context: dict, birth: datetime) -> None:
    try:
        if birth.utcoffset() is None:
            raise ValueError("出生时刻必须带时区。")
        else:
            pass
        context = solar["boundary_context"]
        current, solstice, following = context["dependencies"]
        instant = utc_calendar(birth)
        at = instant.julian_day_exact()
        end = _record_day(following["record"])
        start = end - 18
        end_label = ZonedCalendar.from_isoformat(following["instant_utc"]).utc
        start_label = UTCCalendar(end_label.ordinal - 18, end_label.microseconds_of_day)
        start_point = solar["tuyong_start_point"]
        end_point = solar["tuyong_end_point"]
        if (
            [r["role"] for r in context["dependencies"]]
            != ["current_term", "preceding_solstice", "next_four_li"]
            or current["record"] != calendar_context.get("current_solar_term")
            or context["context_timezone"] != calendar_context.get("timezone")
            or context["context_local_year"]
            != localize_datetime(birth, context["context_timezone"]).year
            or ZonedCalendar.from_isoformat(context["birth_instant_utc"]).utc != instant
            or ZonedCalendar.from_isoformat(solar["anchor_utc"]).utc != instant
            or context["comparison_policy"] != COMPARISON_POLICY
            or solar["comparison_policy"] != COMPARISON_POLICY
            or context["environment_unchanged_at_observation_points"] is not True
            or current["record"]["name"] != solar["term"]
            or solstice["record"]["name"] not in {"冬至", "夏至"}
            or following["record"]["name"] not in LI_TERMS
            or solar["yang_ling"] != (solstice["record"]["name"] == "冬至")
            or _record_day(current["record"]) > at
            or _record_day(solstice["record"]) > at
            or end <= at
            or Fraction(int(start_point["numerator"]), int(start_point["denominator"]))
            != start
            or Fraction(int(end_point["numerator"]), int(end_point["denominator"]))
            != end
            or ZonedCalendar.from_isoformat(solar["tuyong_start_utc"]).utc
            != start_label
            or ZonedCalendar.from_isoformat(solar["tuyong_end_utc"]).utc != end_label
            or solar["tuyong"] != (start <= at < end)
        ):
            raise ValueError("所用节气上下文、出生瞬间与分类结果不一致。")
        else:
            pass
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
    context["calendar_context_match"] = True


def bind_seasonal_context(solar: dict, seasonal: dict) -> None:
    try:
        context = solar["boundary_context"]
        solstice = context["dependencies"][1]
        rows = [
            r
            for r in seasonal["seasonal_windows"]
            if r["start_term"] == solstice["record"]["name"]
        ]
        if (
            seasonal["context_local_year"] != context["context_local_year"]
            or seasonal["context_timezone"] != context["context_timezone"]
            or seasonal["birth_instant_utc"] != context["birth_instant_utc"]
            or len(rows) != 1
            or rows[0]["start_source"] != solstice["record"]
        ):
            raise ValueError("二数时令与化工／阴阳令不是同一节气上下文。")
        else:
            pass
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc


def attach_solar_context(evidence: dict, solar: dict) -> None:

    evidence["rulesets"].append(
        {
            "ruleset_id": POLICY_ID,
            "version": "1.0.0",
            "source_title": "现代节气黄经交点上下文及河洛至点／四立取用",
            "source_url": None,
            "source_status": "actual_consumed_boundary_provenance; not_independent_accuracy_or_classical_calendar_certification",
        }
    )
    evidence["rule_trace"].append(
        {
            "rule_id": POLICY_ID,
            "source_section": "Shared modern solar context; current term, preceding solstice and next four-li",
            "facts": deepcopy(solar["boundary_context"]),
        }
    )
    attach_solar_sources(evidence, POLICY_ID, solar["boundary_context"]["dependencies"])


def solar_context_snapshot(context: dict) -> str:
    lines = ["[所用节气与至点来源]"]
    labels = {
        "current_term": "当前节气",
        "preceding_solstice": "最近至点",
        "next_four_li": "下一四立",
    }
    for row in context["dependencies"]:
        term = row["record"]
        lines.append(
            f"{labels[row['role']]}：{term['name']}，UTC {row['instant_utc']}；来源{term['resolution_provider']}／{term['ephemeris_model']}。"
        )
    lines.append(
        f"按民用时区{context['context_timezone']}的{context['context_local_year']}年上下文读取；相邻年边界不扩展公开模型年份，数值分辨率不等于实际精度认证。"
    )
    return "\n".join(lines)


QUARTER_HG: dict[str, dict[str, str]] = {
    "震": {"hg": "震", "fh": "巽"},
    "離": {"hg": "離", "fh": "坎"},
    "兌": {"hg": "兌", "fh": "艮"},
    "坎": {"hg": "坎", "fh": "離"},
}
# 节气(节/气名)→所属中气象限化工卦（繁简兼容）
JIEQI_QUARTER: dict[str, str] = {
    "春分": "震",
    "清明": "震",
    "穀雨": "震",
    "谷雨": "震",
    "立夏": "震",
    "小滿": "震",
    "小满": "震",
    "芒種": "震",
    "芒种": "震",
    "夏至": "離",
    "小暑": "離",
    "大暑": "離",
    "立秋": "離",
    "處暑": "離",
    "处暑": "離",
    "白露": "離",
    "秋分": "兌",
    "寒露": "兌",
    "霜降": "兌",
    "立冬": "兌",
    "小雪": "兌",
    "大雪": "兌",
    "冬至": "坎",
    "小寒": "坎",
    "大寒": "坎",
    "立春": "坎",
    "雨水": "坎",
    "驚蟄": "坎",
    "惊蛰": "坎",
}


def solar_term_huagong(prev_jieqi_name: str, tuyong: bool) -> dict[str, Any]:
    """据真实节气名 + 土用标志，返回 {hg,fh,quarter,tuyong} 化工/反化工候选。"""
    if type(tuyong) is not bool:
        raise ValueError("土用标志须为布尔值。")
    else:
        pass
    quarter = JIEQI_QUARTER.get(prev_jieqi_name)
    base = (
        QUARTER_HG.get(quarter, {"hg": "", "fh": ""})
        if quarter
        else {"hg": "", "fh": ""}
    )
    hg = [base["hg"]] if base["hg"] else []
    fh = [base["fh"]] if base["fh"] else []
    # NLC PDF35 / NAJDA volume-one image33 explicitly overlaps these clauses:
    # winter solstice -> summer solstice: Li; spring equinox -> summer: Xun.
    # Keep both literal conditions rather than assuming one opposite per quarter.
    if quarter == "震":
        fh.insert(0, "離")
    else:
        pass
    fanhua_rule_ids = {
        "坎": ["winter_to_summer_li"],
        "震": ["winter_to_summer_li", "spring_xun"],
        "離": ["summer_kan"],
        "兌": ["autumn_gen"],
    }.get(quarter or "", [])[:]
    if tuyong:
        hg += ["坤", "艮"]
        fh += ["乾", "兌"]
        fanhua_rule_ids.append("seasonal_earth_qian_dui")
    else:
        pass
    return {
        "hg": hg,
        "fh": fh,
        "quarter": quarter,
        "tuyong": tuyong,
        "fanhua_rule_ids": fanhua_rule_ids,
    }


def solar_term(
    year: int,
    month: int,
    day: int,
    timezone_name: str,
    *,
    birth_datetime: datetime | None = None,
) -> dict[str, Any]:
    """出生当下所处节气 + 土用，经 FateBridge 自有 24 节气引擎计算。

    取最近一个 ≤ 出生民用主点的节气，并以至点划分阴阳令。
    土用采用四立前十八个名义Gregorian日的显式约定；原文季月十八日尚待版本校勘。
    省略 birth_datetime 的旧调用仅按零点近似，返回 precision 明示限制。
    """
    anchor = birth_datetime or localize_datetime(
        datetime(year, month, day), timezone_name
    )
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("节气计算需要带时区的出生时刻。")
    else:
        pass
    context = resolve_solar_context(anchor, timezone_name)
    prev_name = context.current_term.name
    next_li = context.next_four_li.point
    # Numerical boundaries are unrounded nominal days. Display labels retain
    # the existing four-li label minus18days; a clock-domain cap is not shifted.
    start = CivilPoint(next_li.day - 18)
    next_label = context.next_four_li.calendar.utc
    start_label = UTCCalendar(next_label.ordinal - 18, next_label.microseconds_of_day)
    at = context.birth_utc.julian_day_exact()
    tuyong = start.day <= at < next_li.day
    result = solar_term_huagong(prev_name, tuyong)
    result["term"] = prev_name
    solstice = context.preceding_solstice.name
    result.update(
        {
            "yang_ling": solstice == "冬至",
            "boundary_context": context.to_record(),
            "comparison_policy": COMPARISON_POLICY,
            "anchor_utc": context.birth_utc.isoformat(),
            "precision": (
                "birth_instant"
                if birth_datetime is not None
                else "date_midnight_approximation"
            ),
            "tuyong_policy": "18_nominal_gregorian_days_before_four_li_v1",
            "tuyong_start_utc": start_label.isoformat(),
            "tuyong_end_utc": next_label.isoformat(),
            "tuyong_start_point": start.to_record(),
            "tuyong_end_point": next_li.to_record(),
        }
    )
    return result
