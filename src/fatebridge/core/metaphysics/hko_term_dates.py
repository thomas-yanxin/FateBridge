"""Published HKO dates as references, never replacements for computed roots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Literal, TypedDict

from fatebridge.utils.civil_time import ZonedCalendar

CATALOGUE_SHA = "5fc1439a2ecd1e8b2c0794af7517d357c711e751e3916f54068739c4fd7750db"
CLOCK = timezone(timedelta(hours=8))
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()
FIRST_PUBLISHED_YEAR = 1901
LAST_PUBLISHED_YEAR = 2100


@dataclass(frozen=True, kw_only=True)
class PublishedTermDate:
    date: str
    source_url: str
    source_sha256: str


PublishedDateStatus = Literal["date_match", "date_mismatch", "outside_published_range"]


class PublishedTermDateReference(TypedDict):
    reference_id: str
    catalogue_sha256: str
    term_name: str
    hko_year: int
    comparison_clock: str
    computed_hko_moment: str
    computed_hko_date: str
    published_date: str | None
    dates_equal: bool | None
    status: PublishedDateStatus
    source_url: str | None
    source_sha256: str | None
    comparison_scope: str
    instant_accuracy_certified: bool


@lru_cache(maxsize=1)
def _catalogue() -> Mapping[str, PublishedTermDate]:
    catalogue_bytes = (
        files("fatebridge")
        .joinpath("data/astronomy/hko-term-dates-v1.json")
        .read_bytes()
    )
    if hashlib.sha256(catalogue_bytes).hexdigest() != CATALOGUE_SHA:
        raise RuntimeError("香港天文台节气日期资料散列不符")
    else:
        pass
    terms = json.loads(catalogue_bytes)["terms"]
    expected_term_ids = {
        f"{year}:{term}"
        for year in range(FIRST_PUBLISHED_YEAR, LAST_PUBLISHED_YEAR + 1)
        for term in TERMS
    }
    if set(terms) != expected_term_ids:
        raise RuntimeError("香港天文台节气日期资料分母不完整")
    else:
        pass
    return MappingProxyType(
        {
            term_id: PublishedTermDate(
                date=term["published_date"],
                source_url=term["source_url"],
                source_sha256=term["source_sha256"],
            )
            for term_id, term in terms.items()
        }
    )


def published_date_reference(
    name: str, moment: datetime | ZonedCalendar
) -> PublishedTermDateReference:
    if name not in TERMS or (
        isinstance(moment, datetime) and moment.utcoffset() is None
    ):
        raise ValueError("官方节气日期对照需要有效节气名与有时区的交气瞬间")
    else:
        pass
    calendar = (
        moment
        if isinstance(moment, ZonedCalendar)
        else ZonedCalendar.from_datetime(moment)
    )
    local = ZonedCalendar(calendar.utc, CLOCK)
    hko_moment = local.isoformat()
    hko_date = hko_moment.partition("T")[0]
    hko_year = local.local_parts[0]
    published_term = _catalogue().get(f"{hko_year}:{name}")
    dates_equal = hko_date == published_term.date if published_term else None
    status: PublishedDateStatus
    if dates_equal is None:
        status = "outside_published_range"
    elif dates_equal:
        status = "date_match"
    else:
        status = "date_mismatch"
    return {
        "reference_id": "hko_published_term_dates_v1",
        "catalogue_sha256": CATALOGUE_SHA,
        "term_name": name,
        "hko_year": hko_year,
        "comparison_clock": "fixed_UTC+08:00",
        "computed_hko_moment": hko_moment,
        "computed_hko_date": hko_date,
        "published_date": published_term.date if published_term else None,
        "dates_equal": dates_equal,
        "status": status,
        "source_url": published_term.source_url if published_term else None,
        "source_sha256": published_term.source_sha256 if published_term else None,
        "comparison_scope": "published_day_only_not_crossing_instant",
        "instant_accuracy_certified": False,
    }
