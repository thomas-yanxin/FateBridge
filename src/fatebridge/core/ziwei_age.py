"""Versioned age ordinals; placement labels are not civil instants.

The default is an explicit software convention: look up both physical instants
in the birth civil timezone using the existing East Asian date table. This is
not a reconstruction of a historical Ziwei age boundary or local lunations.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal, cast

from fatebridge.core.almanac import get_lunar_context, localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.timezones import parse_timezone_name

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
    target_civil_year: int,
    basis: str,
) -> dict[str, Any]:
    if basis not in {"birth_civil_timezone"}:
        raise ValueError("未知紫微岁序口径：" + basis)
    birth_instant = target_instant = None
    if birth_seed is not None:
        birth_instant = utc_instant(
            localize_datetime(birth_seed.input_datetime, birth_seed.timezone)
        )
        target_instant = utc_instant(
            localize_datetime(target_seed.input_datetime, target_seed.timezone)
        )
        if target_instant < birth_instant:
            raise ValueError("紫微运限目标时刻早于出生时刻")

    receipt: dict[str, Any] = dict(
        basis=basis,
        birth_placement_lunar_year=birth_placement_year,
        target_civil_lunar_year=target_civil_year,
        birth_instant_utc=birth_instant.isoformat() if birth_instant else None,
        target_instant_utc=target_instant.isoformat() if target_instant else None,
        physical_order_checked=birth_instant is not None,
        age_boundary_classically_verified=False,
        boundary_source_evidence=deepcopy(age_source_scope()),
        timezone=None,
        birth_datetime=None,
        target_datetime=None,
        birth_lunar_date=None,
        target_lunar_date=None,
        date_lookup_convention="fixed_east_asian_date_table_not_local_lunation_recalculation",
    )
    if birth_seed is None or birth_instant is None or target_instant is None:
        raise ValueError("同区岁序需要实际出生时钟；不能仅从给定农历条件盘推断岁序")
    zone = parse_timezone_name(birth_seed.timezone)
    birth = birth_instant.astimezone(zone)
    target = target_instant.astimezone(zone)
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
    receipt.update(
        method_id="ziwei_nominal_age_birth_civil_v1",
        rule="target_lunar_year_in_birth_timezone_minus_birth_civil_lunar_year_plus_one",
        timezone=birth_seed.timezone,
        birth_datetime=birth.isoformat(sep=" "),
        target_datetime=target.isoformat(sep=" "),
        birth_lunar_date=birth_lunar,
        target_lunar_date=target_lunar,
        birth_lunar_year=birth_lunar["year"],
        target_lunar_year=target_lunar["year"],
        day_boundary="lunar_new_year_00:00_in_birth_civil_timezone",
    )
    receipt.update(nominal_age=age)
    return receipt
