"""Confirmed UTC leap-second birth labels, without datetime normalization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Any

from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock


@dataclass(frozen=True)
class BirthClock:
    local_anchor: datetime
    utc_anchor: datetime
    local_label: str
    utc_label: str
    leap_second: bool
    jd_tt: float | None
    evidence: dict[str, Any] | None


def resolve_birth_clock(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_second: int = 0,
    birth_timezone: str,
) -> BirthClock:
    if type(birth_second) is not int or not 0 <= birth_second <= 60:
        raise ValueError("出生秒须为0至60的整数；60仅用于已公布UTC闰秒")
    local = datetime(
        birth_year,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
        59 if birth_second == 60 else birth_second,
        tzinfo=parse_timezone_name(birth_timezone),
    )
    validate_local_clock(local)
    utc = local.astimezone(timezone.utc)
    if birth_second != 60:
        return BirthClock(
            local, utc, local.isoformat(), utc.isoformat(), False, None, None
        )
    if (utc.hour, utc.minute, utc.second) != (23, 59, 59):
        raise ValueError("当地60秒未对应UTC闰秒分钟，不能归并到下一秒")
    effective = utc + timedelta(seconds=1)
    entries = leap_table()["entries"]
    pair = next(
        (
            (a, b)
            for a, b in zip(entries, entries[1:])
            if b["effective_date"] == effective.date().isoformat()
            and b["tai_minus_utc_seconds"] - a["tai_minus_utc_seconds"] == 1
        ),
        None,
    )
    if pair is None:
        raise ValueError("冻结IERS记录未确认该UTC闰秒，不推测未来插秒")
    previous, following = pair
    jd = _julian_day(effective)
    tt = jd + (previous["tai_minus_utc_seconds"] + 32.184) / 86400
    local_label = local.isoformat()[:17] + "60" + local.isoformat()[19:]
    utc_label = utc.isoformat()[:17] + f"60.{utc.microsecond:06d}+00:00"
    table_sha = hashlib.sha256(
        files("fatebridge.data")
        .joinpath("knowledge/western-leap-seconds.json")
        .read_bytes()
    ).hexdigest()
    evidence = {
        "method_id": "human_design_confirmed_birth_leap_second_v1",
        "input": {
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_day": birth_day,
            "birth_hour": birth_hour,
            "birth_minute": birth_minute,
            "birth_second": birth_second,
            "birth_timezone": birth_timezone,
        },
        "local_label": local_label,
        "utc_label": utc_label,
        "jd_tt": tt,
        "following_utc_midnight": effective.replace(microsecond=0).isoformat(),
        "tai_minus_utc_during_leap_seconds": previous["tai_minus_utc_seconds"],
        "tai_minus_utc_after_leap_seconds": following["tai_minus_utc_seconds"],
        "source_url": leap_table()["source_url"],
        "source_document_sha256": leap_table()["source_sha256"],
        "source_table_sha256": table_sha,
        "source_table_expires_at": leap_table()["expires_at"],
        "birth_record_authenticated": False,
        "scope": "只确认所填民用标签属于冻结IERS的正闰秒，并转换为连续TT；不认证出生记录、实测UT1或星历精度。二进制TT儒略日保留原有浮点分辨率。",
    }
    return BirthClock(local, utc, local_label, utc_label, True, tt, evidence)


def birth_clock_reading(proof: dict[str, Any]) -> str:
    return (
        f"当地出生标签{proof['local_label']}对应UTC {proof['utc_label']}，已按冻结IERS记录确认正闰秒。"
        "该秒单独转换为连续TT，不借datetime归并到下一分钟；当秒TAI−UTC仍取插秒前的偏移。"
        "其后的设计根、交点与后端比较沿用同一出生TT。标签合法性不证明出生记录准确，也不认证实测UT1或星历的物理误差。"
    )


def verify_birth_clock(payload: dict[str, Any]) -> None:
    """Bind a leap label and its source witness to the actual selected TT.

    This is replay of a frozen calendar convention, not a birth certificate or
    an independent certification of the astronomical position producer.
    """
    proof = payload.get("birth_clock_evidence")
    time = payload["time_scales"]["personality"]
    utc_label = payload["birth_utc"]
    policy = payload.get("calculation_policy", {})
    has_leap_label = isinstance(utc_label, str) and utc_label[17:19] == "60"
    if proof is None:
        if (
            has_leap_label
            or time.get("utc_is_leap_second") is True
            or (
                isinstance(policy.get("birth_local"), str)
                and policy["birth_local"][17:19] == "60"
            )
        ):
            raise ValueError("闰秒出生缺少冻结日历见证")
        return
    from fatebridge.validation.claims import _same_value

    clock = resolve_birth_clock(**proof["input"])
    if (
        not clock.leap_second
        or not _same_value(proof, clock.evidence)
        or utc_label != clock.utc_label
        or time["jd_tt"] != clock.jd_tt
        or time.get("utc_is_leap_second") is not True
        or time.get("method") != proof["method_id"]
        or policy.get("birth_local") != clock.local_label
        or policy.get("birth_timezone") != proof["input"]["birth_timezone"]
    ):
        raise ValueError("闰秒标签、来源、当地钟或选定TT不一致")
