"""Explicit historical year adapter from a complete frozen printed cohort.

It never extends the general lunar provider or silently selects itself.
The table is not a reconstruction of ancient astronomical constants.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from .taiyi_historical import julian_to_proleptic_gregorian

TaiyiYearProfile = Literal[
    "jinjing_year_lunar_civil_v1",
    "jinjing_year_historical_table_v1",
    "jinjing_year_qiliang_table_v1",
]
DEFAULT_YEAR_PROFILE = "jinjing_year_lunar_civil_v1"
HISTORICAL_YEAR_PROFILE = "jinjing_year_historical_table_v1"
QILIANG_YEAR_PROFILE = "jinjing_year_qiliang_table_v1"
HISTORICAL_YEAR_PROFILES = {HISTORICAL_YEAR_PROFILE, QILIANG_YEAR_PROFILE}
YEAR_PROFILES = {DEFAULT_YEAR_PROFILE, *HISTORICAL_YEAR_PROFILES}
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


@lru_cache(maxsize=2)
def historical_month_table(
    profile: str = HISTORICAL_YEAR_PROFILE,
) -> tuple[dict[str, Any], tuple[date, ...], str]:
    if profile not in HISTORICAL_YEAR_PROFILES:
        raise ValueError("year_profile须明确选择已发布历史年计配置")
    filename = (
        "taiyi-qiliang-year-months-v1.json"
        if profile == QILIANG_YEAR_PROFILE
        else "taiyi-historical-year-months-v1.json"
    )
    path = Path(__file__).resolve().parents[2] / "data/classical" / filename
    raw = path.read_bytes()
    data = json.loads(raw)
    rows = data["months"]
    dates = tuple(
        julian_to_proleptic_gregorian(*map(int, row["julian_start"].split("-")))
        for row in rows
    )
    if any((b - a).days not in (29, 30) for a, b in zip(dates, dates[1:])):
        raise ValueError("历史月首表不是连续大小月，不能补算缺行")
    for row, day in zip(rows, dates):
        jdn = day.toordinal() + 1721425
        if (
            day.weekday() != row["printed_week_counter"]
            or (jdn + 49) % 60 != row["printed_cycle_counter"]
        ):
            raise ValueError("历史月首的原印星期/干支与日期不一致")
    lower, upper = data["supported_years"]
    for year in range(lower, upper + 1):
        selected = [r for r in rows if r["year"] == year]
        if [r["month"] for r in selected if not r["is_leap_month"]] != list(
            range(1, 13)
        ):
            raise ValueError("历史年须保留正月至十二月的全部原表月份")
        previous = None
        for row in selected:
            if row["is_leap_month"] and (
                previous is None
                or previous["month"] != row["month"]
                or previous["is_leap_month"]
            ):
                raise ValueError("历史闰月须保留原表粗体重号，不能重新编号")
            previous = row
    if (
        rows[-1].get("role") != "exclusive_end_sentinel"
        or rows[-1]["year"] != upper + 1
    ):
        raise ValueError("历史范围缺少次年正月终界")
    return data, dates, hashlib.sha256(raw).hexdigest()


def historical_year_context(
    civil_date: date, *, profile: str = HISTORICAL_YEAR_PROFILE
) -> dict[str, Any]:
    data, dates, digest = historical_month_table(profile)
    if not dates[0] <= civil_date < dates[-1]:
        raise ValueError(
            f"所选太乙历史历表仅覆盖推算公历{dates[0].isoformat()}至{dates[-1].isoformat()}之前；不向未覆盖年代套用现代农历或回退算法"
        )
    i = bisect_right(dates, civil_date) - 1
    row = data["months"][i]
    day = (civil_date - dates[i]).days + 1
    year = row["year"]
    starts = {
        r["year"]: (r, d)
        for r, d in zip(data["months"], dates)
        if r["month"] == 1 and not r["is_leap_month"]
    }
    first, year_start = starts[year]
    following, year_end = starts[year + 1]
    index = (row["printed_cycle_counter"] + day - 1) % 60
    gz = STEMS[(year - 4) % 10] + BRANCHES[(year - 4) % 12]
    source = data["source"]
    result = {
        "provider": "frozen_printed_historical_month_table",
        "calendar_title": source["title"],
        "calendar_authors": source["authors"],
        "calendar_edition": source["edition"],
        "source_url": source["url"],
        "source_data_sha256": digest,
        "calendar_tradition": data["calendar_tradition"],
        "supported_start": dates[0].isoformat(),
        "supported_end_exclusive": dates[-1].isoformat(),
        "civil_date": civil_date.isoformat(),
        "year": year,
        "month": row["month"],
        "day": day,
        "is_leap_month": row["is_leap_month"],
        "year_ganzhi": gz,
        "day_ganzhi": STEMS[index % 10] + BRANCHES[index % 12],
        "weekday_sunday_zero": (row["printed_week_counter"] + day) % 7,
        "printed_week_counter": row["printed_week_counter"],
        "printed_cycle_counter": row["printed_cycle_counter"],
        "source_month_start_julian": row["julian_start"],
        "month_start_gregorian": dates[i].isoformat(),
        "next_month_start_gregorian": dates[i + 1].isoformat(),
        "source_year_start_julian": first["julian_start"],
        "year_start_gregorian": year_start.isoformat(),
        "source_next_year_start_julian": following["julian_start"],
        "next_year_start_gregorian": year_end.isoformat(),
        "source_pdf_page": row["pdf_page"],
        "source_printed_page": row["printed_page"],
        "display": (
            f"史历表{year}年{gz} {'闰' if row['is_leap_month'] else ''}{row['month']}月{day}日"
            if profile == QILIANG_YEAR_PROFILE
            else f"晋太元{row['regnal_year']}年{gz} {'闰' if row['is_leap_month'] else ''}{row['month']}月{day}日"
        ),
        "counter_policy": data["counter_policy"],
        "date_basis": "所选钟面民用日期零时分日；历史日期与现代四柱的23时/太阳钟边界分开，未复原古代地点与钟制",
        "scope": data["scope"],
    }
    if profile == QILIANG_YEAR_PROFILE:
        result.update(
            profile_id=profile,
            year_label_basis=data["year_label_basis"],
            source_disagreements=[
                {**deepcopy(r), "affects_selected_year": r["year"] == year}
                for r in data["source_disagreements"]
            ],
            calendar_algorithm_identity_adjudicated=False,
        )
    return result


def historical_year_text(context: dict[str, Any]) -> str:
    text = (
        f"历史历表日期：{context['display']}；日期干支{context['day_ganzhi']}。"
        f"本年月首原儒略历{context['source_month_start_julian']}，推算公历{context['month_start_gregorian']}；"
        f"岁首{context['year_start_gregorian']}，次年岁首{context['next_year_start_gregorian']}（不含）。"
        f"来源：{context['calendar_authors']}《{context['calendar_title']}》{context['calendar_edition']}第{context['source_printed_page']}页；{context['source_url']}。"
        + str(context["calendar_tradition"])
        + "。"
        + str(context["date_basis"])
        + "。"
        + str(context["scope"])
    )
    if context.get("year_label_basis"):
        text += "。" + str(context["year_label_basis"])
    for disagreement in context.get("source_disagreements", []):
        text += (
            "。历表分歧："
            + disagreement["scope"]
            + (
                "本次位于该争议年。"
                if disagreement["affects_selected_year"]
                else "本次不在该争议年。"
            )
        )
    return text
