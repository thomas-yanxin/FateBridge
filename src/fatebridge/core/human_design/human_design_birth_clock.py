"""Confirmed UTC leap-second birth labels, without datetime normalization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Any

from fatebridge.core.astro.julian_day import _julian_day
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.human_design.human_design_clock_observation import METHOD
from fatebridge.core.public_output import same_public_value
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


@dataclass(frozen=True)
class ConfirmedLeapSecond:
    """A confirmed UTC second 60, with second 59 as its datetime carrier."""

    utc_anchor: datetime
    offset_before: int
    offset_after: int

    @classmethod
    def from_utc_anchor(cls, utc: datetime) -> ConfirmedLeapSecond:
        if (utc.hour, utc.minute, utc.second) != (23, 59, 59):
            raise ValueError("当地60秒未对应UTC闰秒分钟，不能归并到下一秒")
        effective_date = (utc.date() + timedelta(days=1)).isoformat()
        entries = leap_table()["entries"]
        for previous, following in zip(entries, entries[1:]):
            before = previous["tai_minus_utc_seconds"]
            after = following["tai_minus_utc_seconds"]
            if following["effective_date"] == effective_date and after - before == 1:
                return cls(utc, before, after)
        raise ValueError("冻结IERS记录未确认该UTC闰秒，不推测未来插秒")

    @property
    def effective(self) -> datetime:
        return self.utc_anchor + timedelta(seconds=1)

    @property
    def tt(self) -> TTInstant:
        return TTInstant.from_utc(
            self.effective, tai_minus_utc_seconds=self.offset_before
        )

    @property
    def utc_label(self) -> str:
        utc = self.utc_anchor
        return utc.isoformat()[:17] + f"60.{utc.microsecond:06d}+00:00"


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
        tzinfo=parse_timezone_name(birth_timezone, issue_path="birth_timezone"),
    )
    validate_local_clock(local)
    utc = local.astimezone(timezone.utc)
    if birth_second != 60:
        return BirthClock(
            local, utc, local.isoformat(), utc.isoformat(), False, None, None
        )
    leap = ConfirmedLeapSecond.from_utc_anchor(utc)
    tt = leap.tt.as_float()
    local_label = local.isoformat()[:17] + "60" + local.isoformat()[19:]
    utc_label = leap.utc_label
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
        "following_utc_midnight": leap.effective.replace(microsecond=0).isoformat(),
        "tai_minus_utc_during_leap_seconds": leap.offset_before,
        "tai_minus_utc_after_leap_seconds": leap.offset_after,
        "source_url": leap_table()["source_url"],
        "source_document_sha256": leap_table()["source_sha256"],
        "source_table_sha256": table_sha,
        "source_table_expires_at": leap_table()["expires_at"],
        "birth_record_authenticated": False,
        "scope": "只确认所填民用标签属于冻结IERS的正闰秒，并转换为连续TT；不认证出生记录、实测UT1或星历精度。二进制TT儒略日保留原有浮点分辨率。",
    }
    return BirthClock(local, utc, local_label, utc_label, True, tt, evidence)


def replay_birth_clock(clock: BirthClock, *, method: str | None) -> BirthClock:
    """Reproduce the old scalar only when verifying an earlier receipt."""
    if clock.evidence is None or method != METHOD:
        return clock
    effective = clock.utc_anchor + timedelta(seconds=1)
    tt = (
        _julian_day(effective)
        + (clock.evidence["tai_minus_utc_during_leap_seconds"] + 32.184) / 86400
    )
    return replace(clock, jd_tt=tt, evidence={**clock.evidence, "jd_tt": tt})


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
    clock = replay_birth_clock(
        resolve_birth_clock(**proof["input"]),
        method=payload.get("clock_evidence", {}).get("method_id"),
    )
    if (
        not clock.leap_second
        or not same_public_value(proof, clock.evidence)
        or utc_label != clock.utc_label
        or time["jd_tt"] != clock.jd_tt
        or time.get("utc_is_leap_second") is not True
        or time.get("method") != proof["method_id"]
        or policy.get("birth_local") != clock.local_label
        or policy.get("birth_timezone") != proof["input"]["birth_timezone"]
    ):
        raise ValueError("闰秒标签、来源、当地钟或选定TT不一致")
