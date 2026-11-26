"""Static Meihua JSON loaders, classical glosses, trigram imagery, and calendar-reference checks."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from importlib.resources import files
from typing import Any

VARIANT_PATTERN = re.compile(r"\{\{另\|([^{}|=<>\[\]]+)\|([^{}|=<>\[\]]+)\}\}")
UNRESOLVED_MARKERS = ("{{", "}}", "[[", "]]", "<", ">", "-{", "}-")

TERMS = frozenset(
    "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 "
    "小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
)
REFERENCE_OFFSET = timezone(timedelta(hours=8))
COMPARED = {"published_date_match", "published_date_disagreement"}

# Optional classical glosses (separated from structural symbols/relations)
TENDENCIES: dict[str, tuple[str, str]] = {
    "体用比和": ("比和", "体用同气，传统取协调之意"),
    "体生用": ("泄出", "体生外卦，传统提示主体有所耗泄"),
    "体克用": ("克出", "体制外卦，传统取可以制用之意"),
    "用生体": ("生入", "外卦生体，传统取有扶助之意"),
    "用克体": ("克入", "外卦克体，传统提示存在制约"),
}

# 八卦万物类象结构化查表（《梅花易数》卷一）
BAGUA_WANWU: dict[str, dict[str, Any]] = {
    "乾": {
        "nature": "天",
        "element": "金",
        "direction": "西北",
        "season": "秋冬之交",
        "color": "大赤/玄",
        "body": "首/骨/肺",
        "person": "老父/长官",
        "things": ["金玉", "宝珠", "圆物", "镜"],
    },
    "兑": {
        "nature": "泽",
        "element": "金",
        "direction": "西",
        "season": "秋",
        "color": "白",
        "body": "口/舌/肺",
        "person": "少女/妾",
        "things": ["刀斧", "乐器", "缺器", "水泽"],
    },
    "离": {
        "nature": "火",
        "element": "火",
        "direction": "南",
        "season": "夏",
        "color": "赤/紫",
        "body": "目/心",
        "person": "中女/文士",
        "things": ["文书", "灯烛", "甲胄", "干戈"],
    },
    "震": {
        "nature": "雷",
        "element": "木",
        "direction": "东",
        "season": "春",
        "color": "青/碧",
        "body": "足/肝",
        "person": "长男/动众",
        "things": ["竹木", "乐器", "舟车", "花草"],
    },
    "巽": {
        "nature": "风",
        "element": "木",
        "direction": "东南",
        "season": "春夏之交",
        "color": "青/洁白",
        "body": "股/肱/胆",
        "person": "长女/僧道",
        "things": ["绳索", "羽毛", "工巧器", "香草"],
    },
    "坎": {
        "nature": "水",
        "element": "水",
        "direction": "北",
        "season": "冬",
        "color": "黑",
        "body": "耳/肾/血",
        "person": "中男/江湖人",
        "things": ["水具", "酒醋", "弓轮", "盐"],
    },
    "艮": {
        "nature": "山",
        "element": "土",
        "direction": "东北",
        "season": "冬春之交",
        "color": "黄",
        "body": "手/指/脾",
        "person": "少男/闲人",
        "things": ["土石", "瓜果", "门阙", "床"],
    },
    "坤": {
        "nature": "地",
        "element": "土",
        "direction": "西南",
        "season": "夏秋之交",
        "color": "黑/黄",
        "body": "腹/脾胃",
        "person": "老母/众人",
        "things": ["布帛", "釜甑", "五谷", "方物"],
    },
}


@lru_cache(maxsize=None)
def load_meihua_json(filename: str) -> dict[str, Any]:
    """Load and cache a frozen JSON resource from fatebridge.data/meihua."""
    return json.loads(
        files("fatebridge.data")
        .joinpath(f"meihua/{filename}")
        .read_text(encoding="utf-8")
    )


def lookup_trigram_wanwu(name: str) -> dict[str, Any]:
    """Return structured 八卦万物类象 entry for a trigram name."""
    if name not in BAGUA_WANWU:
        raise ValueError(f"未识别的八卦名称：{name}")
    return dict(BAGUA_WANWU[name])


def meihua_ruleset() -> dict[str, Any]:
    """Return compact metadata for the selected time-cast ruleset."""
    profile = load_meihua_json("time-v1.json")
    return {
        "id": profile["id"],
        "version": profile["version"],
        "title": profile.get("title"),
    }


def explicit_ruleset(*, casting_method: str | None = None) -> dict[str, Any]:
    """Return compact metadata for explicit casting rulesets."""
    if casting_method == "observed_categories":
        selected = load_meihua_json("observed-categories-nlc1925-v1.json")
        return {
            "id": selected["id"],
            "version": selected["version"],
            "title": selected.get("title"),
        }
    extra = load_meihua_json("explicit-casts-v1.json")
    return {
        "id": extra.get("id", "meihua_explicit_v1"),
        "version": extra.get("version", "1.0.0"),
        "title": extra.get("title"),
    }


def render_yaoci_text(raw: str) -> dict[str, Any]:
    """Render Wikisource variant markers without dropping either reading."""
    profile = load_meihua_json("text-reference-wikisource-v1.json")
    pieces: list[str] = []
    remainder: list[str] = []
    variants: list[dict[str, Any]] = []
    offset = display_length = 0
    for match in VARIANT_PATTERN.finditer(raw):
        preceding = raw[offset : match.start()]
        pieces.append(preceding)
        remainder.append(preceding)
        display_length += len(preceding)
        main, alternative = match.groups()
        rendered = main + "〔一作「" + alternative + "」〕"
        variants.append(
            {
                "raw_start": match.start(),
                "raw_end": match.end(),
                "raw_template": match.group(),
                "main_reading": main,
                "alternative_reading": alternative,
                "display_start": display_length,
                "display_end": display_length + len(rendered),
            }
        )
        pieces.append(rendered)
        display_length += len(rendered)
        offset = match.end()
    pieces.append(raw[offset:])
    remainder.append(raw[offset:])
    unresolved = any(marker in "".join(remainder) for marker in UNRESOLVED_MARKERS)
    if unresolved:
        for variant in variants:
            variant["display_start"] = variant["display_end"] = None
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "raw_text": raw,
        "display_text": None if unresolved else "".join(pieces),
        "status": (
            "unresolved_markup" if unresolved else "rendered_literal_transcription"
        ),
        "variants": variants,
    }


def calendar_label_precision(solar_date: date) -> dict[str, Any]:
    """Return compact HKO new-moon review flag for solar_date."""
    profile = load_meihua_json("calendar-precision-v1.json")
    events = [
        dict(event)
        for event in profile["events"]
        if date.fromisoformat(event["review_start"])
        <= solar_date
        < date.fromisoformat(event["review_end_exclusive"])
    ]
    in_scope = (
        date.fromisoformat(profile["calendar_scope"]["start"])
        <= solar_date
        <= date.fromisoformat(profile["calendar_scope"]["end"])
    )
    return {
        "profile_id": profile["id"],
        "version": profile["version"],
        "selected_civil_date": solar_date.isoformat(),
        "status": (
            "named_month_start_review_required"
            if events
            else (
                "no_named_boundary_in_review_window"
                if in_scope
                else "outside_hko_annual_table_scope"
            )
        ),
        "matched_events": events,
    }


def _parse_iso_aware(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def compare_solar_term_date(term: Any, *, fact_path: str) -> dict[str, Any]:
    """Compare one solar term instant against published HKO UTC+08 dates."""
    profile = load_meihua_json("solar-dates-hko-v1.json")
    term = term if isinstance(term, Mapping) else {}
    actual = term.get("datetime_utc") or term.get("datetime_with_offset")
    event_name = term.get("name") if isinstance(term.get("name"), str) else None
    result: dict[str, Any] = {
        "event_name": event_name,
        "fact_path": fact_path,
        "computed_date": None,
        "published_date": None,
        "date_difference_days": None,
        "comparison_status": "actual_instant_unavailable",
        "publisher_named_near_midnight": None,
    }
    if not isinstance(actual, str):
        return result
    try:
        moment = _parse_iso_aware(actual)
        if moment.utcoffset() is None:
            return result
        at_reference = moment.astimezone(REFERENCE_OFFSET)
    except (ValueError, OverflowError):
        return result
    result["computed_datetime_at_reference_offset"] = at_reference.isoformat()
    result["computed_date"] = at_reference.date().isoformat()
    entry = profile["years"].get(str(at_reference.year))
    if entry is None:
        result["comparison_status"] = "outside_published_year_range"
        return result
    published = entry["terms"].get(event_name)
    if published is None:
        result["comparison_status"] = "term_not_in_reference"
        return result
    difference = (at_reference.date() - date.fromisoformat(published)).days
    result.update(
        published_date=published,
        date_difference_days=difference,
        comparison_status=(
            "published_date_match" if difference == 0 else "published_date_disagreement"
        ),
        publisher_named_near_midnight=any(
            e["year"] == at_reference.year and e["term"] == event_name
            for e in profile["publisher_named_events"]
        ),
    )
    return result


def solar_term_date_reference(calendar_context: Mapping[str, Any]) -> dict[str, Any]:
    """Compare adjacent solar terms and month boundaries compactly."""
    profile = load_meihua_json("solar-dates-hko-v1.json")
    boundary = calendar_context.get("bazi_month_boundary")
    boundary = boundary if isinstance(boundary, Mapping) else {}
    selected = [
        (
            calendar_context.get("current_solar_term"),
            "calendar_context.current_solar_term",
        ),
        (calendar_context.get("next_solar_term"), "calendar_context.next_solar_term"),
        (boundary.get("start_term"), "calendar_context.bazi_month_boundary.start_term"),
        (boundary.get("next_term"), "calendar_context.bazi_month_boundary.next_term"),
    ]
    events = [compare_solar_term_date(term, fact_path=path) for term, path in selected]
    compared = [e for e in events if e["comparison_status"] in COMPARED]
    groups: dict[tuple[str, str], set[str]] = {}
    for event in compared:
        key = (event["published_date"][:4], event["event_name"])
        groups.setdefault(key, set()).add(
            event["computed_datetime_at_reference_offset"]
        )
    inconsistent = any(len(instants) > 1 for instants in groups.values())
    disagreements = {
        (e["published_date"][:4], e["event_name"])
        for e in compared
        if e["comparison_status"] == "published_date_disagreement"
    }
    named = {
        (e["published_date"][:4], e["event_name"])
        for e in compared
        if e["publisher_named_near_midnight"] is True
    }
    complete = len(compared) == len(selected)
    compact_events = [
        {
            "event_name": e["event_name"],
            "computed_date": e["computed_date"],
            "published_date": e["published_date"],
            "comparison_status": e["comparison_status"],
            "publisher_named_near_midnight": e["publisher_named_near_midnight"],
        }
        for e in events
        if e["comparison_status"] == "published_date_disagreement"
        or e["publisher_named_near_midnight"] is True
        or e["comparison_status"] not in COMPARED
    ]
    return {
        "profile_id": profile["id"],
        "version": profile["version"],
        "events": compact_events,
        "status": (
            "inconsistent_returned_instants"
            if inconsistent
            else (
                "published_date_disagreement"
                if disagreements
                else (
                    "published_dates_match"
                    if complete
                    else "partially_compared" if compared else "not_compared"
                )
            )
        ),
        "compared_record_count": len(compared),
        "date_disagreement_count": len(disagreements),
        "publisher_named_event_count": len(named),
        "same_reference_event_has_multiple_instants": inconsistent,
    }


def solar_reference_notice(reference: Mapping[str, Any]) -> str | None:
    """Explain an actual disagreement or named near-midnight solar term."""
    if reference["same_reference_event_has_multiple_instants"]:
        return (
            "返回的同年同名节气记录含不同交节时刻；当前资料不足以确定一个一致的"
            "月令时间依据，须复核相关时刻来源。"
        )
    parts: list[str] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for event in reference["events"]:
        identity = (
            event["event_name"],
            event["computed_date"],
            event["published_date"],
        )
        if (
            event["comparison_status"] == "published_date_disagreement"
            and identity not in seen
        ):
            seen.add(identity)
            parts.append(
                f"{event['event_name']}计算日期{event['computed_date']}，"
                f"香港天文台固定年表标为{event['published_date']}。"
            )
    named = list(
        dict.fromkeys(
            e["published_date"][:4] + "年" + e["event_name"]
            for e in reference["events"]
            if e["publisher_named_near_midnight"] is True
        )
    )
    if named:
        parts.append(
            "香港天文台固定说明点名" + "、".join(named) + "为接近午夜的日期复核案例。"
        )
    if not parts:
        return None
    return (
        "节气日期对照（固定UTC+08）："
        + "".join(parts)
        + "本次仍按实际返回的交节时刻确定月令，起卦数沿用已返回的农历资料。"
    )
