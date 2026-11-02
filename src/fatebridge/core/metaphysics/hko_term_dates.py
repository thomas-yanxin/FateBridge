"""Published HKO dates as references, never replacements for computed roots."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Mapping

CATALOGUE_SHA = "5fc1439a2ecd1e8b2c0794af7517d357c711e751e3916f54068739c4fd7750db"
CLOCK = timezone(timedelta(hours=8))
TERMS = "小寒 大寒 立春 雨水 惊蛰 春分 清明 谷雨 立夏 小满 芒种 夏至 小暑 大暑 立秋 处暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至".split()


@lru_cache(maxsize=1)
def _catalogue() -> Mapping[str, tuple[str, str, str]]:
    raw = (
        files("fatebridge")
        .joinpath("data/astronomy/hko-term-dates-v1.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA:
        raise RuntimeError("香港天文台节气日期资料散列不符")
    data = json.loads(raw)
    if set(data["terms"]) != {f"{y}:{n}" for y in range(1901, 2101) for n in TERMS}:
        raise RuntimeError("香港天文台节气日期资料分母不完整")
    return MappingProxyType(
        {
            k: (v["published_date"], v["source_url"], v["source_sha256"])
            for k, v in data["terms"].items()
        }
    )


def published_date_reference(name: str, moment: datetime) -> dict[str, Any]:
    if name not in TERMS or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("官方节气日期对照需要有效节气名与有时区的交气瞬间")
    local = moment.astimezone(CLOCK)
    day = local.date().isoformat()
    item = _catalogue().get(f"{local.year}:{name}")
    equal = day == item[0] if item else None
    return dict(
        reference_id="hko_published_term_dates_v1",
        catalogue_sha256=CATALOGUE_SHA,
        term_name=name,
        hko_year=local.year,
        comparison_clock="fixed_UTC+08:00",
        computed_hko_moment=local.isoformat(),
        computed_hko_date=day,
        published_date=item[0] if item else None,
        dates_equal=equal,
        status=(
            ("date_match" if equal else "date_mismatch")
            if item
            else "outside_published_range"
        ),
        source_url=item[1] if item else None,
        source_sha256=item[2] if item else None,
        comparison_scope="published_day_only_not_crossing_instant",
        instant_accuracy_certified=False,
    )
