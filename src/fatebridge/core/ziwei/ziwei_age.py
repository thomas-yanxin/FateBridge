"""Versioned age ordinals; placement labels are not civil instants.

The default is an explicit software convention: look up both physical instants
in the birth civil timezone using the existing East Asian date table. This is
not a reconstruction of a historical Ziwei age boundary or local lunations.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal, cast

from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

ZiweiAgeBasis = Literal["birth_civil_timezone"]


@lru_cache(maxsize=1)
def age_source_scope() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-age-source-scope.json")
            .read_text(encoding="utf-8")
        ),
    )


def nominal_age_calendar(
    *,
    birth_seed: MetaphysicsSeed | None,
    target_seed: MetaphysicsSeed,
    birth_placement_year: int,
    basis: str,
) -> dict[str, Any]:
    if basis != "birth_civil_timezone":
        raise ValueError("未知紫微岁序口径：" + basis)
    if birth_seed is None:
        raise ValueError("同区岁序需要实际出生时钟；不能仅从给定农历条件盘推断岁序")
    birth_instant = utc_calendar(birth_seed.input_datetime)
    target_instant = utc_calendar(target_seed.input_datetime)
    if target_instant.elapsed_since(birth_instant) < timedelta(0):
        raise ValueError("紫微运限目标时刻早于出生时刻")
    zone = parse_timezone_name(birth_seed.timezone)
    birth = ZonedCalendar(birth_instant, zone).require_datetime()
    target = ZonedCalendar(target_instant, zone).require_datetime()
    validate_local_clock(target, allow_ambiguous=True, clock_label="紫微岁序目标钟时")
    lunar_dates: list[dict[str, Any]] = []
    for label in (birth, target):
        lunar = get_lunar_context(label, timezone_name=birth_seed.timezone)
        if lunar is None or not isinstance(lunar.get("year"), int):
            raise ValueError("紫微岁序的出生时区日期超出农历支持范围")
        lunar_dates.append(
            {k: lunar[k] for k in ("year", "month", "day", "is_leap_month")}
        )
    birth_lunar, target_lunar = lunar_dates
    age = int(target_lunar["year"]) - int(birth_lunar["year"]) + 1
    if age < 1:
        raise ValueError("同区农历岁序小于1；保留边界失败，不能强制钳为1")
    target_civil_lunar = (
        target_lunar
        if target.date() == target_seed.input_datetime.date()
        else get_lunar_context(
            target_seed.input_datetime, timezone_name=target_seed.timezone
        )
    )
    return dict(
        method_id="ziwei_nominal_age_birth_civil_v1",
        basis=basis,
        rule="target_lunar_year_in_birth_timezone_minus_birth_civil_lunar_year_plus_one",
        timezone=birth_seed.timezone,
        birth_datetime=birth.isoformat(sep=" "),
        target_datetime=target.isoformat(sep=" "),
        birth_instant_utc=birth_instant.isoformat(),
        target_instant_utc=target_instant.isoformat(),
        physical_order_checked=True,
        birth_lunar_date=birth_lunar,
        target_lunar_date=target_lunar,
        birth_lunar_year=birth_lunar["year"],
        target_lunar_year=target_lunar["year"],
        birth_placement_lunar_year=birth_placement_year,
        target_civil_lunar_year=(
            target_civil_lunar["year"] if target_civil_lunar else None
        ),
        nominal_age=age,
        day_boundary="lunar_new_year_00:00_in_birth_civil_timezone",
        age_boundary_classically_verified=False,
        boundary_source_evidence=deepcopy(age_source_scope()),
        date_lookup_convention="fixed_east_asian_date_table_not_local_lunation_recalculation",
    )
