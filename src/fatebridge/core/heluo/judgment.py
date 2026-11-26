"""Consolidated Heluo judgment, seasonal context, Jiehou, Najia, body, and evidence."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fatebridge.core.almanac import (
    SolarTerm,
    _term_window,
    get_solar_term_environment_key,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.core.heluo.chart import (
    YUANTANG_RULESET_ID,
    _san_cai,
    _ying,
    assess_nayin_relation,
    hexagram_najia,
)
from fatebridge.core.heluo.texts import (
    GAN,
    TRIGRAM_BITS,
    ZHI,
    _gua_tables,
    _trigram_of,
    gua_lines,
    lines_to_gua,
    yao_name,
)
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar
from fatebridge.utils.data import get_nayin
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.timezones import parse_timezone_name

MonthAssignmentMethod = Literal["intro_preferred_v1", "volume_one_table_v1"]
DEFAULT_MONTH_ASSIGNMENT: MonthAssignmentMethod = "intro_preferred_v1"

_HELUO_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "heluo"

SOLAR_POLICY_ID = "heluo_shared_solar_context_v1"
BODY_RULESET_ID = "heluo_wenming_nayin_body_relations_v1"
LINE_RULESET_ID = "heluo_wenming_line_conditions_v1"
MONTH_RULESET_ID = "heluo_wenming_assigned_month_and_windows_v2"
NAJIA_RULESET_ID = "heluo_wenming_najia_sources_v1"
OPPOSITION_RULESET_ID = "heluo_wenming_yuanqi_opposition_v1"
QI_RULESET_ID = "heluo_wenming_phase_qi_v1"
SEASONAL_RULESET_ID = "heluo_wenming_number_conditions_v1"
STRUCTURE_RULESET_ID = "heluo_wenming_jian_structure_v1"
JIEHOU_RULESET_ID = "heluo_wenming_jiehou_v1"

LI_TERMS = frozenset({"立春", "立夏", "立秋", "立冬"})
MONTH_BRANCHES = "寅卯辰巳午未申酉戌亥子丑"

GAN_YUAN: dict[str, str] = {
    "甲": "乾",
    "壬": "乾",
    "乙": "坤",
    "癸": "坤",
    "庚": "震",
    "辛": "巽",
    "戊": "坎",
    "己": "離",
    "丙": "艮",
    "丁": "兌",
}
GAN_FAN: dict[str, str] = {
    "甲": "坤",
    "壬": "坤",
    "乙": "乾",
    "癸": "乾",
    "庚": "巽",
    "辛": "震",
    "戊": "離",
    "己": "坎",
    "丙": "兌",
    "丁": "艮",
}
ZHI_YUAN: dict[str, str] = {
    "亥": "乾",
    "戌": "乾",
    "未": "坤",
    "申": "坤",
    "卯": "震",
    "辰": "巽",
    "巳": "巽",
    "子": "坎",
    "午": "離",
    "丑": "艮",
    "寅": "艮",
    "酉": "兌",
}
ZHI_FAN: dict[str, str] = {
    "亥": "坤",
    "戌": "坤",
    "未": "乾",
    "申": "乾",
    "卯": "巽",
    "辰": "震",
    "巳": "震",
    "子": "離",
    "午": "坎",
    "丑": "兌",
    "寅": "兌",
    "酉": "艮",
}

QUARTER_HG: dict[str, dict[str, str]] = {
    "震": {"hg": "震", "fh": "巽"},
    "離": {"hg": "離", "fh": "坎"},
    "兌": {"hg": "兌", "fh": "艮"},
    "坎": {"hg": "坎", "fh": "離"},
}
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

MONTH_GUA: dict[str, list[str]] = {
    "寅": ["大有", "同人", "泰", "既濟", "咸", "恆", "蠱", "漸"],
    "卯": ["大壯", "晉", "小過", "大過", "革", "訟", "睽", "井"],
    "辰": ["夬", "履", "渙"],
    "巳": ["乾", "艮", "巽", "離"],
    "午": ["姤", "旅", "困", "豫"],
    "未": ["家人", "萃", "遯", "屯"],
    "申": ["比", "隨", "益", "損", "師", "歸妹", "否", "未濟"],
    "酉": ["中孚", "觀", "明夷", "無妄", "升", "蹇", "蒙", "需", "頤"],
    "戌": ["豐", "謙", "噬嗑", "剝"],
    "亥": ["坎", "坤", "兌", "震"],
    "子": ["小畜", "賁", "復", "節"],
    "丑": ["大畜", "解", "鼎", "臨"],
}

ELEMENTS = {
    "乾": "金",
    "兌": "金",
    "離": "火",
    "震": "木",
    "巽": "木",
    "坎": "水",
    "艮": "土",
    "坤": "土",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
BODY_POSITIONS = (
    ("lower", [1, 2, 3]),
    ("lower_nuclear", [2, 3, 4]),
    ("upper_nuclear", [3, 4, 5]),
    ("upper", [4, 5, 6]),
)

SEASON_WINDOWS = (
    ("yang_insufficient", "阳数不及", "tian", "冬至", "雨水", "below_reference"),
    ("yang_middle", "阳数得中", "tian", "立春", "春分", "middle_not_quantified"),
    ("yang_high", "阳数太过", "tian", "清明", "小满", "range_40_60"),
    ("yin_insufficient", "阴数不及", "di", "夏至", "处暑", "below_reference"),
    ("yin_middle", "阴数得中", "di", "立秋", "秋分", "middle_not_quantified"),
    ("yin_high", "阴数太过", "di", "寒露", "小雪", "at_least_50"),
)

OPERATORS = (
    ("lower", (1, 2, 3)),
    ("upper", (4, 5, 6)),
    ("lower_reversed", (3, 2, 1)),
    ("upper_reversed", (6, 5, 4)),
    ("upper_nuclear", (3, 4, 5)),
    ("lower_nuclear", (2, 3, 4)),
    ("third_to_top", (1, 2, 4, 5, 6, 3)),
    ("reverse_then_third_to_top", (6, 5, 3, 2, 1, 4)),
)

JIEHOU_ALIASES = {
    "谷雨": "穀雨",
    "小满": "小滿",
    "芒种": "芒種",
    "处暑": "處暑",
    "惊蛰": "驚蟄",
}
JIEHOU_MODELS = ("continuous_yao_from_yi_four", "six_days_per_gua_caption_first")


@lru_cache(maxsize=1)
def _line_source() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "line-rules-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _month_front_table() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "volume-one-month-table-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _month_collation() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "month-collation-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _najia_source() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "najia-collation-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _opposition_source() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "yuanqi-opposition-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _structure_source() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "body-structure-v1.json").read_bytes())


@lru_cache(maxsize=1)
def _jiehou_source() -> dict[str, Any]:
    return json.loads((_HELUO_DATA_DIR / "jiehou-v1.json").read_bytes())


@dataclass(frozen=True)
class ResolvedSolarContext:
    current_term: SolarTerm
    preceding_solstice: SolarTerm
    next_four_li: SolarTerm
    local_year: int
    zone: str
    birth_utc: UTCCalendar

    def to_record(self) -> dict[str, Any]:
        return {
            "policy_id": SOLAR_POLICY_ID,
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
        }


def resolve_solar_context(anchor: datetime, zone: str) -> ResolvedSolarContext:
    local = localize_datetime(anchor, zone)
    if local.utcoffset() is None:
        raise ValueError("节气上下文需要带时区的真实时刻。")
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
    return ResolvedSolarContext(
        selected[0][1], selected[1][1], selected[2][1], local.year, zone, birth_utc
    )


def _record_day(record: dict[str, Any]) -> Any:
    return ZonedCalendar.from_isoformat(
        record["datetime_with_offset"]
    ).utc.julian_day_exact()


def bind_solar_context(
    solar: dict[str, Any], calendar_context: dict[str, Any], birth: datetime
) -> None:
    try:
        if birth.utcoffset() is None:
            raise ValueError("出生时刻必须带时区。")
        context = solar["boundary_context"]
        current, solstice, following = context["dependencies"]
        instant = utc_calendar(birth)
        at = instant.julian_day_exact()
        end = _record_day(following["record"])
        start = end - 18
        end_label = ZonedCalendar.from_isoformat(following["instant_utc"]).utc
        start_label = UTCCalendar(end_label.ordinal - 18, end_label.microseconds_of_day)
        if (
            [r["role"] for r in context["dependencies"]]
            != ["current_term", "preceding_solstice", "next_four_li"]
            or current["record"] != calendar_context.get("current_solar_term")
            or context["context_timezone"] != calendar_context.get("timezone")
            or context["context_local_year"]
            != localize_datetime(birth, context["context_timezone"]).year
            or ZonedCalendar.from_isoformat(context["birth_instant_utc"]).utc != instant
            or ZonedCalendar.from_isoformat(solar["anchor_utc"]).utc != instant
            or context["environment_unchanged_at_observation_points"] is not True
            or current["record"]["name"] != solar["term"]
            or solstice["record"]["name"] not in {"冬至", "夏至"}
            or following["record"]["name"] not in LI_TERMS
            or solar["yang_ling"] != (solstice["record"]["name"] == "冬至")
            or _record_day(current["record"]) > at
            or _record_day(solstice["record"]) > at
            or end <= at
            or ZonedCalendar.from_isoformat(solar["tuyong_start_utc"]).utc
            != start_label
            or ZonedCalendar.from_isoformat(solar["tuyong_end_utc"]).utc != end_label
            or solar["tuyong"] != (start <= at < end)
        ):
            raise ValueError("所用节气上下文、出生瞬间与分类结果不一致。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
    context["calendar_context_match"] = True


def bind_seasonal_context(solar: dict[str, Any], seasonal: dict[str, Any]) -> None:
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
            or rows[0]["start_at"] != solstice["instant_utc"]
        ):
            raise ValueError("二数时令与化工／阴阳令不是同一节气上下文。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc


def solar_term_huagong(prev_jieqi_name: str, tuyong: bool) -> dict[str, Any]:
    if type(tuyong) is not bool:
        raise ValueError("土用标志须为布尔值。")
    quarter = JIEQI_QUARTER.get(prev_jieqi_name)
    base = (
        QUARTER_HG.get(quarter, {"hg": "", "fh": ""})
        if quarter
        else {"hg": "", "fh": ""}
    )
    hg = [base["hg"]] if base["hg"] else []
    fh = [base["fh"]] if base["fh"] else []
    if quarter == "震":
        fh.insert(0, "離")
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
    anchor = birth_datetime or localize_datetime(
        datetime(year, month, day), timezone_name
    )
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("节气计算需要带时区的出生时刻。")
    context = resolve_solar_context(anchor, timezone_name)
    prev_name = context.current_term.name
    next_li = context.next_four_li.point
    next_label = context.next_four_li.calendar.utc
    start_label = UTCCalendar(next_label.ordinal - 18, next_label.microseconds_of_day)
    at = context.birth_utc.julian_day_exact()
    start_day = next_li.day - 18
    tuyong = start_day <= at < next_li.day
    result = solar_term_huagong(prev_name, tuyong)
    result["term"] = prev_name
    solstice = context.preceding_solstice.name
    result.update(
        {
            "yang_ling": solstice == "冬至",
            "boundary_context": context.to_record(),
            "anchor_utc": context.birth_utc.isoformat(),
            "precision": (
                "birth_instant"
                if birth_datetime is not None
                else "date_midnight_approximation"
            ),
            "tuyong_policy": "18_nominal_gregorian_days_before_four_li_v1",
            "tuyong_start_utc": start_label.isoformat(),
            "tuyong_end_utc": next_label.isoformat(),
        }
    )
    return result


def element_relation(body: str, natal: str) -> str:
    if body not in GENERATES or natal not in GENERATES:
        raise ValueError("卦体与纳音五行必须明确。")
    if body == natal:
        return "same_element"
    if GENERATES[body] == natal:
        return "body_generates_nayin"
    if GENERATES[natal] == body:
        return "nayin_generates_body"
    if CONTROLS[body] == natal:
        return "body_controls_nayin"
    return "nayin_controls_body"


def body_evidence(
    year_ganzhi: str,
    phases: dict[str, dict[str, Any]],
    yuan_trigrams: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(year_ganzhi, str) or len(year_ganzhi) != 2:
        raise ValueError("纳音关系需要完整年干支。")
    nayin = get_nayin(year_ganzhi[0], year_ganzhi[1])
    if nayin == "未知纳音" or nayin[-1] not in GENERATES:
        raise ValueError("纳音关系需要有效六十甲子年干支。")
    if set(yuan_trigrams) != {"tian", "di"} or any(
        t not in ELEMENTS for t in yuan_trigrams.values()
    ):
        raise ValueError("纳音关系需要明确的年命天地元气卦。")
    rows = []
    for phase in ("xian", "hou"):
        trigrams = phases[phase]["trigrams"]
        if len(trigrams) != 4 or any(t not in ELEMENTS for t in trigrams):
            raise ValueError("纳音关系需要本卦实际上下体与两互体。")
        for (kind, positions), trigram in zip(BODY_POSITIONS, trigrams):
            relation = element_relation(ELEMENTS[trigram], nayin[-1])
            rows.append(
                {
                    "body_id": f"{phase}.{kind}",
                    "phase": phase,
                    "gua": phases[phase]["gua"],
                    "kind": kind,
                    "line_positions": list(positions),
                    "trigram": trigram,
                    "element": ELEMENTS[trigram],
                    "relation": relation,
                    "yuanqi_kinds": [
                        k for k, t in yuan_trigrams.items() if t == trigram
                    ],
                }
            )
    absence = not any(r["yuanqi_kinds"] for r in rows)
    generating = [r["body_id"] for r in rows if r["relation"] == "body_generates_nayin"]
    reverse = [r["body_id"] for r in rows if r["relation"] == "nayin_generates_body"]
    return {
        "ruleset_id": BODY_RULESET_ID,
        "year_ganzhi": year_ganzhi,
        "nayin": nayin,
        "nayin_element": nayin[-1],
        "same_element_body_ids": [
            r["body_id"] for r in rows if r["relation"] == "same_element"
        ],
        "yuanqi_absent": absence,
        "generating_qi": {
            "direction": "body_generates_nayin",
            "body_ids": generating,
            "relation_present": bool(generating),
            "yuanqi_absence_required": True,
            "condition_match": absence and bool(generating),
        },
        "mutual_generation": {
            "body_generates_nayin_ids": generating,
            "nayin_generates_body_ids": reverse,
            "relation_present": bool(generating or reverse),
        },
        "bodies": [
            {
                "body_id": r["body_id"],
                "trigram": r["trigram"],
                "relation": r["relation"],
            }
            for r in rows
        ],
        "present": None,
        "complete_assessment": False,
    }


def opposition_evidence(
    year_ganzhi: str,
    bodies: list[dict[str, Any]],
    yuan: dict[str, str],
    fan: dict[str, str],
) -> dict[str, Any]:
    source = _opposition_source()
    cycle = {GAN[i % 10] + ZHI[i % 12] for i in range(60)}
    if not isinstance(year_ganzhi, str) or year_ganzhi not in cycle:
        raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")
    targets = {}
    for kind, symbol in zip(("tian", "di"), year_ganzhi):
        mapping = next(r for r in source["mappings"] if symbol in r["symbols"])
        targets[kind] = mapping
    if yuan != {k: r["yuan"] for k, r in targets.items()} or fan != {
        k: r["fan"] for k, r in targets.items()
    }:
        raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")
    if not isinstance(bodies, list) or len(bodies) != 8:
        raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")
    phases = []
    try:
        for phase in ("xian", "hou"):
            rows = [r for r in bodies if r["phase"] == phase]
            kinds = [kind for kind, _ in BODY_POSITIONS]
            if len(rows) != 4 or [r["kind"] for r in rows] != kinds:
                raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")
            by_kind = {r["kind"]: r for r in rows}
            bits = gua_lines(by_kind["upper"]["trigram"], by_kind["lower"]["trigram"])
            name = lines_to_gua(bits)["name"]
            for row, (kind, positions) in zip(rows, BODY_POSITIONS):
                if (
                    row["body_id"] != f"{phase}.{kind}"
                    or row["gua"] != name
                    or row["line_positions"] != positions
                    or any(type(p) is not int for p in row["line_positions"])
                    or row["trigram"] != _trigram_of([bits[p - 1] for p in positions])
                ):
                    raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")
            conditions = []
            for kind, mapping in targets.items():
                original = [
                    r["body_id"] for r in rows if r["trigram"] == mapping["yuan"]
                ]
                opposite = [
                    r["body_id"] for r in rows if r["trigram"] == mapping["fan"]
                ]
                direct = {r["body_id"] for r in rows if r["kind"] in {"lower", "upper"}}
                conditions.append(
                    {
                        "kind": kind,
                        "yuan_trigram": mapping["yuan"],
                        "fan_trigram": mapping["fan"],
                        "yuan_body_ids": original,
                        "fan_body_ids": opposite,
                        "yuan_absent": not original,
                        "fan_present": bool(opposite),
                        "condition_match": not original and bool(opposite),
                        "direct_only_condition_match": not direct.intersection(original)
                        and bool(direct.intersection(opposite)),
                        "rescue_match": None,
                    }
                )
            phases.append({"phase": phase, "gua": name, "conditions": conditions})
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict") from exc
    return {
        "ruleset_id": source["ruleset_id"],
        "version": source["version"],
        "year_ganzhi": year_ganzhi,
        "phases": phases,
        "full_rescue_assessment": False,
    }


def phase_qi_evidence(
    bodies: list[dict[str, Any]],
    yuan: dict[str, str],
    fan_yuan: dict[str, str],
    hg: list[str],
    fh: list[str],
    solar: dict[str, Any] | None,
    *,
    year_ganzhi: str,
) -> dict[str, Any]:
    opposition = opposition_evidence(year_ganzhi, bodies, yuan, fan_yuan)
    targets = {
        "yuan_tian": [yuan["tian"]],
        "yuan_di": [yuan["di"]],
        "fan_yuan_tian": [fan_yuan["tian"]],
        "fan_yuan_di": [fan_yuan["di"]],
        "huagong": hg[:],
        "fanhua": fh[:],
    }
    phases = []
    for phase in ("xian", "hou"):
        rows = [row for row in bodies if row["phase"] == phase]
        facts = {}
        for kind, trigrams in targets.items():
            direct = [
                r["body_id"]
                for r in rows
                if r["kind"] in {"lower", "upper"} and r["trigram"] in trigrams
            ]
            nuclear = [
                r["body_id"]
                for r in rows
                if r["kind"] in {"lower_nuclear", "upper_nuclear"}
                and r["trigram"] in trigrams
            ]
            facts[kind] = {
                "trigrams": trigrams[:],
                "direct_body_ids": direct,
                "nuclear_body_ids": nuclear,
                "present": bool(direct or nuclear) if trigrams else None,
            }
        phases.append({"phase": phase, "gua": rows[0]["gua"], "matches": facts})
    transitions = []
    for kind in targets:
        a, b = (row["matches"][kind]["present"] for row in phases)
        status = (
            "not_evaluated"
            if a is None or b is None
            else "retained" if a and b else "lost" if a else "gained" if b else "absent"
        )
        transitions.append(
            {"kind": kind, "xian_present": a, "hou_present": b, "change": status}
        )
    return {
        "ruleset_id": QI_RULESET_ID,
        "transitions": transitions,
        "complete_assessment": False,
    }


def _window(source: dict[str, Any], month: int) -> dict[str, Any]:
    uncertain = source.get("uncertain_month_numbers", [])
    label_match = None if month in uncertain else month in source["month_numbers"]
    qualifiers = source.get("qualifiers", [])
    match = None if qualifiers else label_match
    result = {
        "rule_id": source["id"],
        "source_pdf_page": source["page"],
        "kind": source["kind"],
        "meaning": source["meaning"],
        "month_numbers": list(source["month_numbers"]),
        "uncertain_month_numbers": list(uncertain),
        "month_label_match": label_match,
        "qualifiers": list(qualifiers),
        "qualifier_status": "not_evaluated" if qualifiers else "none",
        "match": match,
        "status": (
            "endpoint_boundary_unresolved"
            if label_match is None
            else ("qualifier_not_evaluated" if qualifiers else "month_label_only")
        ),
    }
    if source.get("natal_najia_clause_id"):
        result["natal_najia_clause_id"] = source["natal_najia_clause_id"]
    for key in (
        "first_month_number",
        "last_month_number",
        "first_month_inclusive",
        "last_month_inclusive",
    ):
        if key in source:
            result[key] = source[key]
    return result


def month_affinity(
    chart: dict[str, Any],
    month_branch: str,
    assigned_table: dict[str, list[str]],
    *,
    najia_assessments: list[dict[str, Any]] | None = None,
    assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> dict[str, Any]:
    if (
        not isinstance(month_branch, str)
        or len(month_branch) != 1
        or month_branch not in MONTH_BRANCHES
    ):
        raise ValueError("卦月匹配需要明确的出生月支。")
    if assignment_method not in ("intro_preferred_v1", "volume_one_table_v1"):
        raise ValueError("卦属月方法须明确为intro_preferred_v1或volume_one_table_v1。")
    birth_month = MONTH_BRANCHES.index(month_branch) + 1
    data = _month_collation()
    front = _month_front_table()
    najia = (
        {
            item["phase"]: item
            for item in najia_assessments
            if isinstance(item, dict) and item.get("phase") in {"xian", "hou"}
        }
        if najia_assessments
        else {}
    )
    phases = []
    for phase in ("xian", "hou"):
        name = chart[phase]["name"]
        anchor = next((r for r in data["assigned_months"] if r["gua"] == name), None)
        table_anchor = next(
            (r for r in front["assigned_months"] if r["gua"] == name), None
        )
        if table_anchor is None:
            raise NumerologySourceError("invalid_month_source_data")
        selected_section = (
            "hexagram_intro"
            if assignment_method == "intro_preferred_v1" and anchor is not None
            else "volume_one_table"
        )
        selected = anchor if selected_section == "hexagram_intro" else table_anchor
        assert selected is not None
        assigned_number = selected["month"]
        assigned = MONTH_BRANCHES[assigned_number - 1]
        if assignment_method == "intro_preferred_v1":
            short = name[0] if name[1] == "為" else name[2:]
            legacy = [b for b, names in assigned_table.items() if short in names]
            if legacy != [assigned]:
                raise NumerologySourceError("runtime_month_assignment_conflict")
        readings = [
            {
                "section": "hexagram_intro",
                "month_number": anchor["month"] if anchor else None,
                "source_pdf_page": anchor["page"] if anchor else 177,
                "month_label_match": birth_month == anchor["month"] if anchor else None,
                "status": "explicit_month" if anchor else "month_not_explicit",
            },
            {
                "section": "volume_one_table",
                "month_number": table_anchor["month"],
                "source_pdf_page": table_anchor["page"],
                "month_label_match": birth_month == table_anchor["month"],
                "status": "explicit_month",
            },
        ]
        source_match_values = [r["month_label_match"] for r in readings]
        consensus = (
            source_match_values[0]
            if None not in source_match_values and len(set(source_match_values)) == 1
            else None
        )
        windows = [_window(w, birth_month) for w in data["windows"] if w["gua"] == name]
        matched_windows = [w for w in windows if w["month_label_match"] is True]
        timely = [w["rule_id"] for w in matched_windows if w["meaning"] == "timely"]
        untimely = [w["rule_id"] for w in matched_windows if w["meaning"] == "untimely"]
        clause_source = next(
            (c for c in data["natal_najia_clauses"] if c["gua"] == name), None
        )
        clause = (
            None
            if clause_source is None
            else {
                "rule_id": clause_source["id"],
                "source_pdf_page": clause_source["page"],
                "month_numbers": clause_source["month_numbers"][:],
                "month_label_match": birth_month in clause_source["month_numbers"],
                "qualifier_status": (
                    "current_phase_facts_available"
                    if phase in najia
                    else "not_evaluated_missing_najia"
                ),
                "connector_status": clause_source["connector_status"],
                "match": None,
            }
        )
        phases.append(
            {
                "phase": phase,
                "gua": name,
                "assigned_month_number": assigned_number,
                "assigned_month_branch": assigned,
                "assigned_month_match": month_branch == assigned,
                "source_pdf_page": selected["page"],
                "selected_month_source": selected_section,
                "source_months_agree": (
                    anchor["month"] == table_anchor["month"] if anchor else None
                ),
                "source_consensus_match": consensus,
                **({"additional_windows": matched_windows} if matched_windows else {}),
                **({"natal_najia_clause": clause} if clause is not None else {}),
                "opposed_month_conditions": bool(timely and untimely),
                **(
                    {"conflict_rule_ids": timely + untimely}
                    if timely and untimely
                    else {}
                ),
            }
        )
    return {
        "ruleset_id": MONTH_RULESET_ID,
        "assignment_method": assignment_method,
        "source_consensus_match": (
            True
            if any(p["source_consensus_match"] is True for p in phases)
            else (
                None
                if any(p["source_consensus_match"] is None for p in phases)
                else False
            )
        ),
        "birth_month_branch": month_branch,
        "birth_month_number": birth_month,
        "phases": phases,
        "complete_assessment": False,
    }


def annotate_najia_positions(
    gua: str, lines: list[int], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    data = _najia_source()
    if (
        not isinstance(lines, list)
        or len(lines) != 6
        or any(type(bit) is not int or bit not in (0, 1) for bit in lines)
        or not isinstance(entries, list)
        or len(entries) != 6
        or any(not isinstance(e, dict) for e in entries)
        or [e.get("pos") for e in entries] != list(range(1, 7))
        or any(type(e["pos"]) is not int for e in entries)
    ):
        raise ValueError("河洛纳甲取证须有六个明确爻位及其实际计算结果。")
    by_bits = {tuple(p["bits"]): p for p in data["pure_tables"]}
    anchor = next((a for a in data["hexagram_entries"] if a["lines"] == lines), None)
    if anchor is not None and anchor["gua"] != gua:
        raise NumerologySourceError("hexagram_mismatch")
    result = deepcopy(entries)
    for e in result:
        pos = e["pos"]
        component = by_bits[tuple(lines[:3] if pos <= 3 else lines[3:])]
        if (
            e.get("trigram") != component["trigram"]
            or e.get("direct") != component["direct"][pos - 1]
            or e.get("borrowed") != component["borrowed"][pos - 1]
        ):
            raise NumerologySourceError("runtime_assignment_conflict")
    issues = [i for i in data["order_issues"] if i["gua"] == gua]
    return {"lines": result, "source_issues": deepcopy(issues) if issues else []}


def line_conditions(chart: dict[str, Any]) -> dict[str, Any]:
    source = _line_source()
    support = source["clauses"]["support"]
    rows = []
    for phase in ("xian", "hou"):
        selected = chart[phase]
        bits, pos = selected["lines"], selected["yuan"]
        if (
            not isinstance(bits, list)
            or len(bits) != 6
            or any(type(bit) is not int or bit not in (0, 1) for bit in bits)
            or type(pos) is not int
            or pos not in range(1, 7)
        ):
            raise ValueError("河洛爻位规则需要六个明确阴阳爻与1至6的实际元堂。")
        yang_count = sum(bits)
        minority = 1 if yang_count == 1 else 0 if yang_count == 5 else None
        minority_pos = bits.index(minority) + 1 if minority is not None else None
        order = 1 if pos == 5 else 2 if pos == 2 else 3 if pos in (3, 4) else 4
        corresponding_pos = pos + 3 if pos <= 3 else pos - 3
        selected_yang = bool(bits[pos - 1])
        corresponding_yang = bool(bits[corresponding_pos - 1])
        rows.append(
            {
                "phase": phase,
                "gua": selected["name"],
                "pos": pos,
                "yang": selected_yang,
                "position_polarity_match": (pos % 2 == 1) == selected_yang,
                "position_preference_order": order,
                "ruler_minister_seat": {"match": pos in (2, 5)},
                "zhongzong": {
                    "minority_pos": minority_pos,
                    "match": minority_pos is not None and pos == minority_pos,
                },
                "source_youyuan": {
                    "selected_pos": pos,
                    "selected_yang": selected_yang,
                    "corresponding_pos": corresponding_pos,
                    "corresponding_yang": corresponding_yang,
                    "polarity_opposed": selected_yang != corresponding_yang,
                    "clause_match": (
                        selected_yang is support["required_selected_yang"]
                        and corresponding_yang is support["required_corresponding_yang"]
                    ),
                },
            }
        )
    return {
        "phases": rows,
        "complete_assessment": False,
        "ten_condition_score": None,
    }


def _number_fact(
    value: int,
    reference: int,
    weak: tuple[int, int],
    high: int,
    high_upper: int | None = None,
) -> dict[str, Any]:
    high_match = value >= high and (high_upper is None or value <= high_upper)
    weak_match = weak[0] <= value <= weak[1]
    return {
        "value": value,
        "reference": reference,
        "difference": value - reference,
        "comparison": (
            "正数" if value == reference else ("不足" if value < reference else "有余")
        ),
        "extreme_band": ("至弱" if weak_match else ("太过" if high_match else None)),
    }


def numerical_conditions(tian: int, di: int) -> list[dict[str, Any]]:
    if any(type(n) is not int or n <= 0 for n in (tian, di)):
        raise ValueError("天地数须为正整数，不能用布尔或去正数后的余数代替。")
    cases = (
        (
            "lone_yang_unpaired",
            "孤阳不耦",
            69,
            "26<=天<=40; (天-25)%2=1; 地=30",
            26 <= tian <= 40 and (tian - 25) % 2 == 1 and di == 30,
        ),
        (
            "lone_yin_back_yang",
            "孤阴背阳",
            70,
            "32<=地<=60; (地-30)%2=0; 天=25",
            32 <= di <= 60 and (di - 30) % 2 == 0 and tian == 25,
        ),
        (
            "lone_yang_self_pair",
            "孤阳自耦",
            70,
            "天 in {30,40,50}; 地=30",
            tian in {30, 40, 50} and di == 30,
        ),
        (
            "lone_yin_toward_yang",
            "孤阴向阳",
            71,
            "天=25; 40<=地<=60",
            tian == 25 and 40 <= di <= 60,
        ),
        ("yang_partial", "阳偏", 72, "4<=天<=24; 地=30", 4 <= tian <= 24 and di == 30),
        ("yin_partial", "阴偏", 72, "18<=地<=28; 天=25", 18 <= di <= 28 and tian == 25),
        (
            "strong_subdues_weak",
            "以强伏弱",
            72,
            "天 in {30,40,50}; 地<=30",
            tian in {30, 40, 50} and di <= 30,
        ),
        (
            "weak_opposes_strong",
            "以弱敌强",
            73,
            "天=24; 30<=地<=60",
            tian == 24 and 30 <= di <= 60,
        ),
        (
            "peaceful_exact_numbers",
            "安和自宁",
            73,
            "天=25; 地=30",
            tian == 25 and di == 30,
        ),
        ("both_deficient", "天地俱羸", 74, "天<25; 地<30", tian < 25 and di < 30),
        ("both_excess", "阴阳战胜", 74, "天>25; 地>30", tian > 25 and di > 30),
    )
    return [
        {
            "rule_id": key,
            "label": label,
            "source_pdf_page": page,
            "condition": expression,
            "matched": matched,
        }
        for key, label, page, expression, matched in cases
    ]


def seasonal_number_evidence(
    tian: int,
    di: int,
    birth: datetime | ZonedCalendar | None,
    *,
    context_timezone: str = "+00:00",
) -> dict[str, Any]:
    if any(type(n) is not int or n <= 0 for n in (tian, di)):
        raise ValueError("天地数须为正整数，不能用布尔或去正数后的余数代替。")
    birth_clock = (
        birth
        if isinstance(birth, ZonedCalendar) or birth is None
        else ZonedCalendar.from_datetime(birth)
    )
    conditions = numerical_conditions(tian, di)
    result: dict[str, Any] = {
        "ruleset_id": SEASONAL_RULESET_ID,
        "numbers": {
            "tian": _number_fact(tian, 25, (4, 8), 40, 60),
            "di": _number_fact(di, 30, (8, 12), 50),
        },
        "matched_pattern_ids": [c["rule_id"] for c in conditions if c["matched"]],
        "seasonal_status": (
            "not_evaluated_missing_birth_instant" if birth is None else "evaluated"
        ),
        "birth_instant_utc": (
            None if birth_clock is None else birth_clock.utc.isoformat()
        ),
        "seasonal_windows": [],
        "complete_assessment": False,
    }
    if birth_clock is None:
        return result
    anchor = birth_clock.utc.julian_day_exact()
    local = ZonedCalendar(
        birth_clock.utc, parse_timezone_name(context_timezone)
    ).require_datetime()
    local_year = local.year
    environment = get_solar_term_environment_key(year=local_year)
    terms = _term_window(local, context_timezone)
    windows = []
    for key, label, axis, start_name, end_name, band in SEASON_WINDOWS:
        try:
            start = max(
                (t for t in terms if t.name == start_name and t.point.day <= anchor),
                key=lambda t: t.point.day,
            )
            end = min(
                (
                    t
                    for t in terms
                    if t.name == end_name and t.point.day > start.point.day
                ),
                key=lambda t: t.point.day,
            )
        except ValueError as exc:
            raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
        for term in (start, end):
            try:
                require_calculated_solar_term(term)
            except RuntimeError as exc:
                raise NumerologySourceError(
                    "runtime_heluo_solar_context_conflict"
                ) from exc
        active = start.point.day <= anchor < end.point.day
        value, reference = (tian, 25) if axis == "tian" else (di, 30)
        band_match = (
            value < reference
            if band == "below_reference"
            else (
                40 <= value <= 60
                if band == "range_40_60"
                else value >= 50 if band == "at_least_50" else None
            )
        )
        band_status = (
            "not_quantified" if band == "middle_not_quantified" else "compared"
        )
        if band == "range_40_60" and value > 60:
            band_match = None
            band_status = "outside_cited_high_range"
        windows.append(
            {
                "rule_id": key,
                "label": label,
                "start_term": start_name,
                "start_at": start.calendar.utc.isoformat(),
                "end_at": end.calendar.utc.isoformat(),
                "active": active,
                "numeric_band_match": band_match,
                "numeric_band_status": band_status,
            }
        )
    result["seasonal_windows"] = windows
    result["context_timezone"] = context_timezone
    result["context_local_year"] = local_year
    if get_solar_term_environment_key(year=local_year) != environment:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict")
    return result


def _structure_name(bits: list[int]) -> str:
    return _trigram_of(bits) if len(bits) == 3 else lines_to_gua(bits)["name"]


def body_structure(chart: dict[str, Any]) -> dict[str, Any]:
    source = _structure_source()
    phases = []
    for phase in ("xian", "hou"):
        original = chart[phase]
        bits = original["lines"]
        if (
            not isinstance(bits, list)
            or len(bits) != 6
            or any(type(b) is not int or b not in (0, 1) for b in bits)
            or _structure_name(bits) != original["name"]
        ):
            raise ValueError("卦体结构需要同阶段一致的卦名与六个整数阴阳爻。")
        literal_case = original["name"] == source["source_case_gua"]
        records = []
        for kind, positions in OPERATORS:
            selected = [bits[p - 1] for p in positions]
            records.append({"kind": kind, "name": _structure_name(selected)})
        reversed_bits = bits[::-1]
        reversed_name = _structure_name(reversed_bits)
        phases.append(
            {
                "phase": phase,
                "gua": original["name"],
                **({"records": records} if literal_case else {}),
                "whole_reversal": {"name": reversed_name},
                "literal_case_match": literal_case,
                **(
                    {
                        "literal_names_reproduced": (
                            [r["name"] for r in records] == source["source_case_names"]
                            and reversed_name == source["source_case_reversed_name"]
                        )
                    }
                    if literal_case
                    else {}
                ),
            }
        )
    return {
        "ruleset_id": STRUCTURE_RULESET_ID,
        "phases": phases,
        "complete_futi_assessment": False,
        "complete_assessment": False,
    }


def _jiehou_term(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("节候查表需要明确节气名，不能猜候或出生时间。")
    name = JIEHOU_ALIASES.get(name, name)
    if name not in {row["term"] for row in _jiehou_source()["term_rows"]}:
        raise ValueError("所选底本没有该节气名。")
    return name


def _jiehou_form(gua: str, position: int) -> dict[str, Any]:
    pair = _gua_tables()[0][gua]
    lines = gua_lines(pair["up"], pair["low"])
    return dict(gua=gua, lines=lines, position=position, yao=yao_name(lines, position))


def term_assignment(name: str) -> dict[str, Any]:
    name = _jiehou_term(name)
    row = next(r for r in _jiehou_source()["term_rows"] if r["term"] == name)
    return {**deepcopy(row), **_jiehou_form(row["gua"], row["position"])}


def literal_hou_table() -> list[dict[str, Any]]:
    result = []
    for row in _jiehou_source()["hou_rows"]:
        position = 4 if row["raw_yao"] == "六四" else 1
        form = _jiehou_form(row["gua"], position)
        result.append(
            dict(
                **deepcopy(row),
                printed_position=position,
                canonical_yao=form["yao"],
                yao_polarity_agrees=row["raw_yao"] == form["yao"],
            )
        )
    return result


def nominal_hou_day(day_offset: int, *, model: str) -> dict[str, Any]:
    if type(day_offset) is not int or not 0 <= day_offset < 360:
        raise ValueError("候卦名义日序须明确为0至359的整数；不静默进年。")
    if not isinstance(model, str) or model not in JIEHOU_MODELS:
        raise ValueError("须明确指定具名候卦重建模型；不按吻合程度暗选。")
    if model == "continuous_yao_from_yi_four":
        offset = (day_offset + 3) % 360
        gua_index, position = offset // 6, offset % 6 + 1
    else:
        gua_index = day_offset // 6
        position = ((day_offset + 3) % 6 + 1) if gua_index == 0 else day_offset % 6 + 1
    gua = _jiehou_source()["gua_order"][gua_index]
    return dict(
        **_jiehou_form(gua, position),
        model=model,
        day_offset=day_offset,
        origin="printed_winter_solstice_yi_six_four; no_civil_instant",
        basis="sixty_gua_order_and_one_yao_per_nominal_day_reconstruction",
        derived_only=True,
        physical_date_applied=False,
        extra_ke_applied=False,
    )


def jiehou_evidence(solar: dict[str, Any]) -> dict[str, Any]:
    source = _jiehou_source()
    try:
        term = term_assignment(solar["term"])
        anchor_text = solar["anchor_utc"]
        anchor = ZonedCalendar.from_isoformat(anchor_text)
        if (
            anchor.offset != timedelta(0)
            or solar["quarter"] != term["gua"][0]
            or solar["precision"]
            not in {"birth_instant", "date_midnight_approximation"}
        ):
            raise ValueError("节气标签、已算象限或瞬间来源不一致。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_jiehou_context_conflict") from exc
    return {
        "ruleset_id": source["ruleset_id"],
        "upstream_term_label": solar["term"],
        "anchor_utc": anchor_text,
        "anchor_precision": solar["precision"],
        "selected_term_gua": {
            k: term[k]
            for k in ("term", "gua", "position", "yao", "source_pdf_page")
            if k in term
        },
        "selected_hou": None,
        "huagong_assessment": None,
        "selected_reconstruction_model": None,
        "historical_term_instants_established": False,
        "hou_physical_date_mapping_complete": False,
    }


def judge(
    chart: dict[str, Any],
    four_pillars: dict[str, str],
    month_zhi: str,
    hg_override: dict[str, Any] | None = None,
    *,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
    birth_datetime: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate Najia, Yuanqi, Huagong, month/season, sovereign hexagram, and Nayin relations."""
    y_gz = four_pillars["year"]
    t_yuan = GAN_YUAN[y_gz[0]]
    d_yuan = ZHI_YUAN[y_gz[1]]
    t_fan = GAN_FAN[y_gz[0]]
    d_fan = ZHI_FAN[y_gz[1]]

    sc_xian = _san_cai(chart["xian"]["lines"])
    sc_hou = _san_cai(chart["hou"]["lines"])
    bodies_xian = [
        {"phase": "xian", "part": label, "trigram": sc_xian[idx]}
        for idx, label in enumerate(["下体", "下互", "上互", "上体"])
    ]
    bodies_hou = [
        {"phase": "hou", "part": label, "trigram": sc_hou[idx]}
        for idx, label in enumerate(["下体", "下互", "上互", "上体"])
    ]
    all_bodies = bodies_xian + bodies_hou

    def _find_gua(tri: str) -> list[dict[str, Any]]:
        return [b for b in all_bodies if b["trigram"] == tri]

    yuan = {
        "tian": {
            "gua": t_yuan,
            "present": len(_find_gua(t_yuan)) > 0,
            "locations": _find_gua(t_yuan),
        },
        "di": {
            "gua": d_yuan,
            "present": len(_find_gua(d_yuan)) > 0,
            "locations": _find_gua(d_yuan),
        },
    }
    fan_yuan = {
        "tian": {
            "gua": t_fan,
            "present": len(_find_gua(t_fan)) > 0,
            "locations": _find_gua(t_fan),
        },
        "di": {
            "gua": d_fan,
            "present": len(_find_gua(d_fan)) > 0,
            "locations": _find_gua(d_fan),
        },
    }

    if hg_override:
        hg_list = list(hg_override.get("hg", []))
        fh_list = list(hg_override.get("fh", []))
    else:
        hg_list, fh_list = [], []

    hg_loc = [b for g in hg_list for b in _find_gua(g)]
    fh_loc = [b for g in fh_list for b in _find_gua(g)]
    huagong = {"candidates": hg_list, "present": hg_loc}
    fanhua = {"candidates": fh_list, "present": fh_loc}

    najia = []
    for phase in ("xian", "hou"):
        annotated = annotate_najia_positions(
            chart[phase]["name"],
            chart[phase]["lines"],
            hexagram_najia(chart[phase]["lines"]),
        )
        entries = annotated["lines"]
        matches: list[dict[str, Any]] = []
        for e in entries:
            if e["direct"] == y_gz:
                matches.append({"pos": e["pos"], "kind": "direct"})
            elif y_gz in e["borrowed"]:
                matches.append({"pos": e["pos"], "kind": "borrowed"})
        najia.append(
            {
                "phase": phase,
                "gua": chart[phase]["name"],
                "year_ganzhi": y_gz,
                "lines": entries,
                "matches": matches,
                "present": bool(matches),
            }
        )
    de_shi = any(item["present"] for item in najia)
    month_evidence = month_affinity(
        chart,
        month_zhi,
        MONTH_GUA,
        najia_assessments=najia,
        assignment_method=month_assignment_method,
    )
    de_time = any(row["assigned_month_match"] for row in month_evidence["phases"])
    de_ti_full = body_evidence(
        y_gz,
        {
            phase: {
                "gua": chart[phase]["name"],
                "trigrams": _san_cai(chart[phase]["lines"]),
            }
            for phase in ("xian", "hou")
        },
        {"tian": yuan["tian"]["gua"], "di": yuan["di"]["gua"]},
    )
    de_ti_bodies = [
        {
            "body_id": r["body_id"],
            "phase": r["body_id"].split(".")[0],
            "gua": chart[r["body_id"].split(".")[0]]["name"],
            "kind": r["body_id"].split(".")[1],
            "line_positions": {
                "lower": [1, 2, 3],
                "lower_nuclear": [2, 3, 4],
                "upper_nuclear": [3, 4, 5],
                "upper": [4, 5, 6],
            }[r["body_id"].split(".")[1]],
            "trigram": r["trigram"],
        }
        for r in de_ti_full["bodies"]
    ]
    qi_phases = phase_qi_evidence(
        de_ti_bodies,
        {k: v["gua"] for k, v in yuan.items()},
        {k: v["gua"] for k, v in fan_yuan.items()},
        hg_list,
        fh_list,
        hg_override,
        year_ganzhi=y_gz,
    )
    de_ti = {k: v for k, v in de_ti_full.items() if k != "bodies"}
    xie = (
        yuan["tian"]["present"] or yuan["di"]["present"] or len(huagong["present"]) > 0
    )
    er_shu = {
        "tian": chart["tian"],
        "di": chart["di"],
        "tianState": (
            "有余" if chart["tian"] > 25 else ("不足" if chart["tian"] < 25 else "正数")
        ),
        "diState": (
            "有余" if chart["di"] > 30 else ("不足" if chart["di"] < 30 else "正数")
        ),
    }
    y_pos = chart["xian"]["yuan"]
    y_yang = chart["xian"]["lines"][y_pos - 1] == 1
    ying_pos = _ying(y_pos)
    line_evidence = line_conditions(chart)
    yuan_tang_info = {
        "pos": y_pos,
        "yang": y_yang,
        "position_polarity_match": line_evidence["phases"][0][
            "position_polarity_match"
        ],
        "youYing": chart["xian"]["lines"][ying_pos - 1]
        != chart["xian"]["lines"][y_pos - 1],
        "heLi": chart["yangLing"] == y_yang if chart["yangLing"] is not None else None,
    }
    sovereign = chart.get("sovereign_hexagram")
    nayin_fortune = {
        "natal": {
            "year_ganzhi": y_gz,
            "nayin": de_ti["nayin"],
            "nayin_element": de_ti["nayin_element"],
            "generating_body_ids": de_ti["generating_qi"]["body_ids"],
            "same_element_body_ids": de_ti["same_element_body_ids"],
            "body_favorable": bool(
                de_ti["generating_qi"]["body_ids"]
                or de_ti["same_element_body_ids"]
                or de_ti["mutual_generation"]["nayin_generates_body_ids"]
            ),
        },
        "pillar_pairs": {
            "year_vs_day": assess_nayin_relation(y_gz, four_pillars["day"]),
            "year_vs_month": assess_nayin_relation(y_gz, four_pillars["month"]),
        },
    }
    return {
        "assessment_status": "partial",
        "najia": najia,
        "yuan": yuan,
        "fanYuan": fan_yuan,
        "huagong": huagong,
        "fanhua": fanhua,
        "qi_phases": qi_phases,
        "deSheng": de_shi,
        "deTime": de_time,
        "month_affinity": month_evidence,
        "deTi": de_ti,
        "xie": xie,
        "erShu": er_shu,
        "seasonal_numbers": seasonal_number_evidence(
            chart["tian"],
            chart["di"],
            (
                birth_datetime
                if birth_datetime is not None
                else (
                    ZonedCalendar.from_isoformat(hg_override["anchor_utc"])
                    if hg_override and hg_override.get("precision") == "birth_instant"
                    else None
                )
            ),
            context_timezone=(hg_override or {})
            .get("boundary_context", {})
            .get("context_timezone", "+00:00"),
        ),
        "yuanTang": yuan_tang_info,
        "line_conditions": line_evidence,
        "body_structure": body_structure(chart),
        "sovereign_hexagram": sovereign,
        "nayin_fortune": nayin_fortune,
    }


def heluo_evidence(
    chart: dict[str, Any],
    judgment: dict[str, Any],
    solar: dict[str, Any],
    four_pillars: dict[str, str],
) -> dict[str, Any]:
    """Build compact non-duplicated evidence metadata for Heluo."""
    del four_pillars
    return {
        "rulesets": [
            {
                "ruleset_id": YUANTANG_RULESET_ID,
                "version": "1.0.0",
                "source_title": "河洛理數（上海文明書局印行本）卷一",
                "source_status": "single_visual_review",
            },
            {
                "ruleset_id": MONTH_RULESET_ID,
                "version": "3.0.0",
                "source_title": "河洛理數（上海文明書局印行本）卷一・卦月",
                "source_status": "single_visual_review",
            },
            {
                "ruleset_id": JIEHOU_RULESET_ID,
                "version": "1.0.0",
                "source_title": "河洛理數（上海文明書局印行本）卷一定節候卦說",
                "source_status": "single_visual_review",
            },
        ],
        "selected_texts": [
            {
                "phase": phase,
                "gua": chart[phase]["name"],
                "pos": chart[phase]["yuan"],
                "corpus_key": f"{chart[phase]['name']}.yao.{chart[phase]['yuan']}",
            }
            for phase in ("xian", "hou")
        ],
        "rule_trace": [],
    }


def attach_solar_context(evidence: dict[str, Any], solar: dict[str, Any]) -> None:
    del solar
    evidence["rulesets"].append(
        {
            "ruleset_id": SOLAR_POLICY_ID,
            "version": "1.0.0",
            "source_title": "现代节气黄经交点上下文及河洛至点／四立取用",
            "source_status": "actual_consumed_boundary_provenance",
        }
    )


def attach_jiehou_evidence(evidence: dict[str, Any], jiehou: dict[str, Any]) -> None:
    evidence["rulesets"].append(
        {
            "ruleset_id": jiehou["ruleset_id"],
            "version": jiehou.get("version", "1.0.0"),
            "source_title": "河洛理數（上海文明書局印行本）卷一定節候卦說",
            "source_status": "single_visual_review",
        }
    )
