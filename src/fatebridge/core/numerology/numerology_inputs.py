"""Known birth clocks, pillar links, and explicit longitude for numerology."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

CLOCK_POLICY_ID = "numerology_explicit_longitude_clock_v1"
CLOCK_INPUT_POLICY_ID = "numerology_clock_text_provenance_v1"
CLOCK_INPUT_SCOPE = (
    "记录所给钟时分量与计算补位；文本格式不认证出生记录的实际精度，不据此推定误差区间。"
)
DISPLAY_SCOPE = (
    "输出日期的小数或秒位不提升出生记录的实际精度；未据文本格式推定误差区间。"
)
NUMEROLOGY_DEFAULT_TIMEZONE = "+08:00"
TIMEZONE_POLICY_ID = "numerology_fixed_default_explicit_region_v1"
BIRTH_OFFSET_POLICY_ID = "numerology_confirmed_civil_offset_v1"
BIRTH_OFFSET_DESCRIPTION = (
    "Optional confirmed birth UTC offset ±HH:MM[:SS]. With an IANA zone, verifies "
    "or selects the occurrence of a repeated birth clock while retaining regional "
    "rules for later boundaries. Never infer an unknown offset; cannot make a "
    "nonexistent local time valid or replace birth-record precision."
)
NUMEROLOGY_DATE_DESCRIPTION = (
    "Birth date YYYY-MM-DD in the proleptic Gregorian calendar, including before "
    "1582; no automatic Julian/Gregorian cutover or historical lunar/era conversion. "
    "Historical source dates require a separately evidenced conversion."
)
NUMEROLOGY_TIME_DESCRIPTION = (
    "Known birth local time HH:MM[:SS[.ffffff]], up to six fractional digits; "
    "required, blank is not midnight; timezone goes in timezone. Supplied components "
    "are retained separately from zero calculation defaults. Textual digits "
    "do not certify birth-record precision or imply an uncertainty interval."
)

PILLAR_RULESET_ID = "heluo_volume7_pillar_links_v1"
PILLAR_SOURCE_PATH = (
    Path(__file__).resolve().parents[2] / "data/numerology/pillar-links-v1.json"
)
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = {GAN[i % 10] + ZHI[i % 12] for i in range(60)}
LINK_HEADS = {
    "month": ("丙寅", "戊寅", "庚寅", "壬寅", "甲寅") * 2,
    "hour": ("甲子", "丙子", "戊子", "庚子", "壬子") * 2,
}
LINK_GROUPS = ("甲己", "乙庚", "丙辛", "丁壬", "戊癸") * 2


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedBirthClock:
    supplied_text: str
    normalized_clock: str
    has_explicit_seconds: bool
    fractional_digits: int


def parse_birth_clock(value: object) -> ParsedBirthClock:
    """Parse a supplied local clock and retain the components actually given."""
    if not isinstance(value, str):
        raise ValueError("河洛与参评需要明确的出生时间，不能补默认零点。")
    supplied_text = value.strip()
    match = re.fullmatch(
        r"([0-9]{1,2}):([0-9]{1,2})(?::([0-9]{1,2})(\.[0-9]{1,6})?)?", supplied_text
    )
    if match is None:
        raise ValueError(
            "出生时间须为已知的HH:MM或HH:MM:SS；未知时刻不能补零点，时区请单独提供。"
        )
    hour_text, minute_text, second_text, fraction_text = match.groups()
    hour, minute, second = int(hour_text), int(minute_text), int(second_text or 0)
    time(hour, minute, second)
    return ParsedBirthClock(
        supplied_text=supplied_text,
        normalized_clock=f"{hour:02d}:{minute:02d}:{second:02d}{fraction_text or ''}",
        has_explicit_seconds=second_text is not None,
        fractional_digits=len(fraction_text) - 1 if fraction_text is not None else 0,
    )


def require_birth_clock(value: object) -> str:
    """Return the normalized calculation clock for the shared input policy."""
    return parse_birth_clock(value).normalized_clock


def resolve_numerology_timezone(value: object) -> str:
    """Keep omitted/null zones consistent with the published fixed-offset default."""
    if value is None:
        return NUMEROLOGY_DEFAULT_TIMEZONE
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "出生时区timezone须为非空IANA名称或UTC偏移；未知时区不能用空白代替。"
        )
    zone = value.strip()
    parse_timezone_name(zone)
    return zone


def normalize_numerology_utc_offset(value: object) -> str | None:
    """Accept a separately confirmed offset, without inferring a birth region."""
    if value is None:
        return None
    match = (
        re.fullmatch(r"([+-])([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?", value.strip())
        if type(value) is str
        else None
    )
    if match is None:
        raise ValueError("birth_utc_offset须为已确认的±HH:MM或±HH:MM:SS；未知时不填。")
    sign, hour, minute, second = match.groups()
    h, m, s = int(hour), int(minute), int(second or 0)
    if h >= 24 or m >= 60 or s >= 60:
        raise ValueError("birth_utc_offset超出有效UTC偏移范围。")
    return format_utc_offset(
        timedelta(hours=h, minutes=m, seconds=s) * (1 if sign == "+" else -1)
    )


def numerology_seed_time(
    date_text: str, clock: str, zone: str, birth_utc_offset: str | None
) -> str:
    """Feed a verified instant to the shared seed while keeping its named zone."""
    if birth_utc_offset is None:
        return clock
    wall = datetime.fromisoformat(f"{date_text}T{clock}")
    selected = resolve_civil_clock(
        wall, zone, birth_utc_offset, offset_field="birth_utc_offset"
    )
    return selected.isoformat().partition("T")[2]


def resolve_numerology_longitude(
    longitude: float | str | None, use_true_solar_time: bool
) -> tuple[float | None, str | None]:
    """Validate explicit longitude without supplying a birthplace."""
    if type(use_true_solar_time) is not bool:
        raise ValueError("use_true_solar_time须为布尔值。")
    parsed_longitude = parse_geo_coordinate(longitude, axis="longitude")
    if parsed_longitude is None and use_true_solar_time:
        raise ValueError(
            "河洛与参评的真太阳时需要明确出生地经度longitude，不能套用上海经度。"
            "不使用太阳时请明确设use_true_solar_time=false。"
        )
    return parsed_longitude, "longitude" if parsed_longitude is not None else None


def birth_clock_input_record(birth_clock: ParsedBirthClock) -> dict[str, Any]:
    """Record text components separately from numerical clock defaults."""
    supplied_components = ["hour", "minute"]
    omitted_components: list[str]
    calculation_defaults: dict[str, int]
    if birth_clock.fractional_digits:
        supplied_components.extend(("second", "fractional_second"))
        omitted_components = []
        calculation_defaults = {}
        detail = f"已提供时、分、秒及{birth_clock.fractional_digits}位小数秒；这些位数不认证记录的实际精度。"
    elif birth_clock.has_explicit_seconds:
        supplied_components.append("second")
        omitted_components = ["fractional_second"]
        calculation_defaults = {"microsecond": 0}
        detail = "已提供时、分、秒，未提供小数秒；微秒=0仅为计算参考值。"
    else:
        omitted_components = ["second", "fractional_second"]
        calculation_defaults = {"second": 0, "microsecond": 0}
        detail = "仅提供时、分；秒=0和微秒=0仅为计算参考值。"
    return {
        "policy_id": CLOCK_INPUT_POLICY_ID,
        "supplied_text": birth_clock.supplied_text,
        "normalized_clock": birth_clock.normalized_clock,
        "supplied_components": supplied_components,
        "omitted_components": omitted_components,
        "fractional_digits": birth_clock.fractional_digits,
        "calculation_defaults": calculation_defaults,
        "uncertainty_interval": None,
        "observed_precision_certified": False,
    }


def numerology_birth_clock(
    seed: MetaphysicsSeed,
    longitude: float | None,
    source: str | None,
    *,
    birth_utc_offset: str | None = None,
    input_clock: ParsedBirthClock | None = None,
) -> dict[str, Any]:
    offset_seconds = (seed.input_datetime.utcoffset() or timedelta(0)).total_seconds()
    clock: dict[str, Any] = {
        "policy_id": CLOCK_POLICY_ID,
        "mode": "apparent_solar" if seed.applied_true_solar else "civil",
        "timezone_policy_id": TIMEZONE_POLICY_ID,
        "timezone_spec": seed.timezone,
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "civil_utc_offset_seconds": (
            int(offset_seconds) if offset_seconds.is_integer() else offset_seconds
        ),
        "civil_daylight_saving_seconds": int(
            (seed.input_datetime.dst() or timedelta(0)).total_seconds()
        ),
        "civil_datetime": seed.input_isoformat(),
        "birth_instant_utc": utc_calendar(seed.input_datetime).isoformat(),
        "calculation_wall_clock": seed.clock.isoformat(sep=" "),
        "longitude": longitude,
        "longitude_source": source,
        "longitude_used": seed.applied_true_solar,
        "total_correction_minutes": seed.total_correction_minutes,
    }
    if input_clock is not None:
        if seed.input_datetime.time() != time.fromisoformat(
            input_clock.normalized_clock
        ):
            raise ValueError("所给出生钟时与实际计算参考钟面不一致。")
        clock["input_representation"] = birth_clock_input_record(input_clock)
    if birth_utc_offset is not None:
        civil = seed.input_datetime
        clock.update(
            birth_utc_offset_policy_id=BIRTH_OFFSET_POLICY_ID,
            requested_utc_offset=birth_utc_offset,
            civil_utc_offset=format_utc_offset(civil.utcoffset() or timedelta(0)),
            civil_fold=civil.fold,
            civil_time_ambiguous=(
                civil.replace(fold=0).utcoffset() != civil.replace(fold=1).utcoffset()
            ),
        )
    return clock


def attach_birth_clock(evidence: dict, clock: dict) -> None:
    evidence["birth_clock"] = clock


@lru_cache(maxsize=1)
def _pillar_source() -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(PILLAR_SOURCE_PATH.read_bytes())
        expected_groups = ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"]
        if (
            data["ruleset_id"] != PILLAR_RULESET_ID
            or data["month_branch_order"] != "寅卯辰巳午未申酉戌亥子丑"
            or data["hour_branch_order"] != ZHI
            or [r["basis_stems"] for r in data["month_heads"]] != expected_groups
            or [r["basis_stems"] for r in data["hour_heads"]] != expected_groups
        ):
            raise ValueError("卷七起月起时原句与所选表不一致。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_pillar_link_source_data") from exc
    return data


def pillar_link_evidence(pillars: dict[str, str]) -> dict[str, Any]:
    if not isinstance(pillars, dict) or any(
        not isinstance(pillars.get(k), str) or pillars[k] not in CYCLE
        for k in ("year", "month", "day", "hour")
    ):
        raise ValueError("干支衔接核对需要四个有效六十甲子。")
    source = _pillar_source()
    rows = []
    for target, basis in (("month", "year"), ("hour", "day")):
        basis_stem = pillars[basis][0]
        head = next(
            r for r in source[target + "_heads"] if basis_stem in r["basis_stems"]
        )
        branch = pillars[target][1]
        step = source[target + "_branch_order"].index(branch)
        expected = GAN[(GAN.index(head["head"][0]) + step) % 10] + branch
        rows.append(
            {
                "target": target,
                "basis": basis,
                "basis_pillar": pillars[basis],
                "basis_stem": basis_stem,
                "source_stem_group": head["basis_stems"],
                "head_pillar": head["head"],
                "branch_step": step,
                "actual_pillar": pillars[target],
                "expected_pillar": expected,
                "matches": pillars[target] == expected,
            }
        )
    return {
        "ruleset_id": PILLAR_RULESET_ID,
        "version": source["version"],
        "source_title": source["source_title"],
        "review_status": source["review_status"],
        "authorship_status": source["authorship_status"],
        "pillars": dict(pillars),
        "links": rows,
        "all_links_match": all(r["matches"] for r in rows),
    }


def require_pillar_links(pillars: dict[str, str]) -> dict[str, Any]:
    evidence = pillar_link_evidence(pillars)
    for row in evidence["links"]:
        if not row["matches"]:
            label = "月柱与年干" if row["target"] == "month" else "时柱与日干"
            raise ValueError(
                f"{label}衔接不一致：所给{row['actual_pillar']}，按卷七附法应为{row['expected_pillar']}。"
            )
    return evidence


def verified_computed_pillars(pillars: dict[str, str]) -> dict[str, Any]:
    try:
        return require_pillar_links(pillars)
    except ValueError as exc:
        raise NumerologySourceError("runtime_pillar_link_conflict") from exc


def attach_pillar_links(evidence: dict[str, Any], links: dict[str, Any]) -> None:
    evidence["pillar_links"] = links
