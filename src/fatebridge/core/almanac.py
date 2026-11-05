"""
Calendrical helpers for solar terms, lunar context, and BaZi boundaries.

This module keeps the expensive year-level calculations cached so service-layer
code can enrich responses without recomputing 24 solar terms on every call.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    from lunardate import LunarDate
except ImportError:  # pragma: no cover - exercised only in misconfigured envs
    LunarDate = None

from ..utils.civil_clock import utc_instant
from ..utils.civil_time import utc_ordering_key
from ..utils.errors import EphemerisSourceError
from ..utils.timezones import parse_timezone_name
from .divination import derive_meihua_hexagram
from .ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
    preserve_ephemeris_path,
    swe,
)
from .execution_context import current_datetime
from .lunar_1900_prefix import START as LUNAR_PREFIX_START
from .lunar_1900_prefix import convert as _prefix_lunar_date
from .lunar_1900_prefix import source_for as _prefix_lunar_source
from .lunar_supplement import END as LUNAR_SUPPLEMENT_END
from .lunar_supplement import convert as _supplement_lunar_date
from .lunar_supplement import source_for as _later_lunar_source
from .solar_term_runtime import solar_term_cache_context

logger = logging.getLogger(__name__)

# Solar ecliptic longitude (tropical) at which each term occurs.
# Mapping follows SOLAR_TERM_NAMES order starting at 小寒 = 285°.
SOLAR_TERM_LONGITUDES = tuple((285 + 15 * i) % 360 for i in range(24))


DEFAULT_TIMEZONE = "Asia/Shanghai"
DAY_GANZHI_STRATEGY_STANDARD = "standard"
DAY_GANZHI_STRATEGY_REFERENCE_OFFSET = "reference_offset"

SOLAR_TERM_NAMES = [
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
]

NATIVE_SOLAR_ROOT_MODEL_ID = "native_swiss_tt_solar_bisection_v2"

GAN = tuple("甲乙丙丁戊己庚辛壬癸")
ZHI = tuple("子丑寅卯辰巳午未申酉戌亥")

BAZI_MONTH_START_TERMS = {
    "立春": "寅",
    "惊蛰": "卯",
    "清明": "辰",
    "立夏": "巳",
    "芒种": "午",
    "小暑": "未",
    "立秋": "申",
    "白露": "酉",
    "寒露": "戌",
    "立冬": "亥",
    "大雪": "子",
    "小寒": "丑",
}

BAZI_MONTH_SEQUENCE = [
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
    "子",
    "丑",
]

LUNAR_MONTH_NAMES = {
    1: "正月",
    2: "二月",
    3: "三月",
    4: "四月",
    5: "五月",
    6: "六月",
    7: "七月",
    8: "八月",
    9: "九月",
    10: "十月",
    11: "冬月",
    12: "腊月",
}

LUNAR_DAY_NAMES = {
    1: "初一",
    2: "初二",
    3: "初三",
    4: "初四",
    5: "初五",
    6: "初六",
    7: "初七",
    8: "初八",
    9: "初九",
    10: "初十",
    11: "十一",
    12: "十二",
    13: "十三",
    14: "十四",
    15: "十五",
    16: "十六",
    17: "十七",
    18: "十八",
    19: "十九",
    20: "二十",
    21: "廿一",
    22: "廿二",
    23: "廿三",
    24: "廿四",
    25: "廿五",
    26: "廿六",
    27: "廿七",
    28: "廿八",
    29: "廿九",
    30: "三十",
}

LUNAR_SUPPORTED_SOLAR_START = LUNAR_PREFIX_START
LUNAR_SUPPORTED_SOLAR_END = LUNAR_SUPPLEMENT_END

# Month-length corrections independently checked against sxtwl 2.0.7 and
# Hong Kong Observatory annual calendars. Each preserves the year's total
# length, so new-year anchors and other years in lunardate remain unchanged.
# Encoding: low nibble = leap month; bits 15..4 = months 1..12 (30 vs 29
# days); bit 16 = leap-month length. Do not mutate lunardate's global tables.
LUNAR_YEAR_INFO_CORRECTIONS = {1933: 0x16A95, 1954: 0xA5B0, 1978: 0xB6A0}


@dataclass(frozen=True)
class _LunarDateValue:
    year: int
    month: int
    day: int
    isLeapMonth: bool


@lru_cache(maxsize=2048)
def _lunar_date_from_solar(solar_date: date) -> _LunarDateValue:
    """Return corrected calendar data without changing a third-party singleton."""
    if LunarDate is None:
        raise ValueError("离线农历换算不可用")
    prefix = _prefix_lunar_date(solar_date)
    if prefix is not None:
        return _LunarDateValue(*prefix)
    supplement = _supplement_lunar_date(solar_date)
    if supplement is not None:
        return _LunarDateValue(*supplement)
    lunar = LunarDate.fromSolarDate(solar_date.year, solar_date.month, solar_date.day)
    if lunar.toSolarDate() != solar_date:
        raise ValueError("农历转换无法反向验证")
    info = LUNAR_YEAR_INFO_CORRECTIONS.get(lunar.year)
    if info is None:
        return _LunarDateValue(lunar.year, lunar.month, lunar.day, lunar.isLeapMonth)

    new_year = LunarDate(lunar.year, 1, 1).toSolarDate()
    remaining = (solar_date - new_year).days
    leap_month = info & 0xF
    for month in range(1, 13):
        for is_leap in (False, True) if month == leap_month else (False,):
            bit = 16 if is_leap else 16 - month
            length = 29 + ((info >> bit) & 1)
            if remaining < length:
                return _LunarDateValue(lunar.year, month, remaining + 1, is_leap)
            remaining -= length
    raise ValueError("农历日期超出当年月份表")


DAY_GANZHI_JDN_OFFSETS = {
    DAY_GANZHI_STRATEGY_STANDARD: 49,
    DAY_GANZHI_STRATEGY_REFERENCE_OFFSET: 38,
}


@dataclass(frozen=True)
class SolarTerm:
    name: str
    moment: datetime
    date_key: str
    day_ganzhi: str
    # Retflags/library details remain internal; public records expose provider/model.
    resolution_provider: str = "unknown"
    ephemeris_model: str = "unknown"
    ephemeris_retflags: Tuple[int, ...] = ()
    ephemeris_library_version: Optional[str] = None
    solar_model_details: Optional[Dict[str, Any]] = field(default=None, hash=False)

    def as_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "name": self.name,
            # Keep the actual boundary used by comparisons. Rounding an event
            # down/up to an integral second can change which term an input at
            # that displayed second belongs to. Fractions are numerical solver
            # resolution, not an independent physical-accuracy certificate.
            "datetime": self.moment.replace(tzinfo=None).isoformat(sep=" "),
            "date_key": self.date_key,
            "day_ganzhi": self.day_ganzhi,
            "resolution_provider": self.resolution_provider,
            "ephemeris_model": self.ephemeris_model,
        }
        offset = self.moment.utcoffset()
        if offset is not None:
            # A wall label alone cannot distinguish the two occurrences of a
            # repeated hour. Keep the legacy label, and preserve the actual
            # supplied civil instant without consulting the host timezone.
            result.update(
                datetime_with_offset=self.moment.isoformat(),
                utc_offset_seconds=offset.total_seconds(),
                fold=self.moment.fold,
                timezone=getattr(self.moment.tzinfo, "key", None)
                or getattr(self.moment.tzinfo, "zone", None)
                or self.moment.tzname(),
            )
        if self.solar_model_details is not None:
            result["solar_model_details"] = deepcopy(self.solar_model_details)
        return result


def is_calculated_solar_term(term: SolarTerm) -> bool:
    if term.resolution_provider == "fatebridge_moshier":
        from .moshier_solar import MODEL_ID, model_details

        details = term.solar_model_details or {}
        return (
            term.ephemeris_model == MODEL_ID
            and all(details.get(k) == v for k, v in model_details().items())
            and not term.ephemeris_retflags
        )
    if term.resolution_provider == "swisseph":
        return True
    if term.resolution_provider in {"moshier_aa1996", "vsop2013"}:
        from .aa1996_solar import MODEL_ID as AA1996_MODEL_ID
        from .vsop2013_solar import MODEL_ID as VSOP2013_MODEL_ID

        selected = (
            VSOP2013_MODEL_ID
            if term.resolution_provider == "vsop2013"
            else AA1996_MODEL_ID
        )

        details = term.solar_model_details or {}
        return (
            term.ephemeris_model == selected
            and details.get("model_id") == selected
            and all(
                isinstance(details.get(key), str) and len(details[key]) == 64
                for key in (
                    "binary_sha256",
                    "source_profile_sha256",
                    "calculation_source_sha256",
                    "build_manifest_sha256",
                )
            )
            and not term.ephemeris_retflags
        )
    if term.resolution_provider == "jpl_de440":
        from .de440_solar import EXTENDED_MODEL_ID
        from .de440_solar import MODEL_ID as DE440_MODEL_ID

        return (
            term.ephemeris_model in {DE440_MODEL_ID, EXTENDED_MODEL_ID}
            and term.solar_model_details is not None
            and term.solar_model_details.get("model_id") == term.ephemeris_model
            and bool(term.solar_model_details.get("coefficient_sha256"))
            and bool(term.solar_model_details.get("source_kernel_sha256"))
            and not term.ephemeris_retflags
        )
    if term.resolution_provider == "jpl_spk":
        from .spk_solar import MODEL_ID as SPK_MODEL_ID

        return (
            term.ephemeris_model == SPK_MODEL_ID
            and term.solar_model_details is not None
            and term.solar_model_details.get("model_id") == SPK_MODEL_ID
            and bool(term.solar_model_details.get("kernel_sha256"))
        )
    from .analytic_solar import MODEL_ID

    return (
        term.resolution_provider == "fatebridge_analytic"
        and term.ephemeris_model == MODEL_ID
        and term.solar_model_details is not None
        and term.solar_model_details.get("model_id") == MODEL_ID
    )


def require_calculated_solar_term(term: SolarTerm) -> None:
    """Reject coarse or unknown solar-term boundaries.

    Checking the actual consumed term avoids certifying a separate cache or
    a different year. Provider availability alone is not an accuracy verdict.
    """
    if not is_calculated_solar_term(term):
        raise RuntimeError(
            f"交气计算需要 swisseph 或具名解析太阳模型；{term.name}的来源为"
            f" {term.resolution_provider}，不能使用线性或未知节气边界。"
        )


def localize_datetime(moment: datetime, timezone_name: Optional[str]) -> datetime:
    tzinfo = parse_timezone_name(timezone_name or DEFAULT_TIMEZONE)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=tzinfo)
    if moment.tzinfo == tzinfo:
        # Equal fixed-offset objects need not be identical. astimezone would
        # otherwise visit an unrepresentable UTC year even for no conversion.
        return moment.replace(tzinfo=tzinfo)
    return moment.astimezone(tzinfo)


def elapsed_days_between(start: datetime, end: datetime) -> float:
    """Nominal UTC-label days between aware instants, accounting for DST.

    Python subtracts wall clocks when two datetimes share the same tzinfo.
    Normalize both labels to UTC before subtracting, with 86400 nominal
    seconds per day. Python datetime omits leap seconds: this engineering
    calendar policy does not compute uniform TAI/TT elapsed SI seconds.
    """
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Elapsed solar-term durations require aware datetimes.")
    return (
        end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    ).total_seconds() / 86400


def current_local_datetime(timezone_name: Optional[str] = None) -> datetime:
    """当前时刻的"本地墙钟"，以朴素(无 tzinfo) datetime 返回。

    裸 ``datetime.now()`` 读的是*服务器*时区，因此一台部署在 UTC 的主机会
    为"未显式给定年/月/日"的调用方解析出错误的日历日期——最明显的是临近
    元旦 / 立春边界时 :func:`calculate_liunian` 默认的流年年份会差一年。
    这里把默认时刻锚定到一个固定的民用时区（缺省 ``Asia/Shanghai``），
    使"当前"无论进程跑在哪个时区都确定一致。

    返回朴素 datetime 是刻意为之：下游一律把它拆成 ``.year/.month/.day``
    或据此构造新的朴素 datetime，保持与既有"朴素本地时间"契约一致，绝不与
    别处的 aware datetime 混用而触发 TypeError。
    """
    tzinfo = parse_timezone_name(timezone_name or DEFAULT_TIMEZONE)
    return current_datetime(
        tzinfo, timezone_name or DEFAULT_TIMEZONE, now_provider=datetime.now
    ).replace(tzinfo=None)


def _julian_day_number(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def get_day_ganzhi(
    year: int,
    month: int,
    day: int,
    *,
    strategy: str = DAY_GANZHI_STRATEGY_STANDARD,
) -> str:
    if strategy not in DAY_GANZHI_JDN_OFFSETS:
        raise ValueError(f"Unsupported day ganzhi strategy: {strategy}")

    index = (
        _julian_day_number(year, month, day) + DAY_GANZHI_JDN_OFFSETS[strategy]
    ) % 60
    return f"{GAN[index % 10]}{ZHI[index % 12]}"


def _solar_term_utc_via_swe(
    year: int,
    target_longitude: float,
    anchor_utc: datetime,
    provenance: Optional[Dict[str, Any]] = None,
) -> Optional[datetime]:
    """Resolve a TT solar-longitude crossing, then label its civil instant.
    ``target_longitude`` near ``anchor_utc``.

    The anchor is used to disambiguate which yearly crossing to return
    (so 冬至 for civil year 2024 is Dec 2024 rather than Dec 2023). We
    scan a ±30-day window around the calendar-month anchor; the
    Sun moves ~1°/day so a crossing is guaranteed in that window.

    Return None if swisseph is unavailable or no crossing is found. The caller
    must reject the unavailable crossing.
    """
    if swe is None:
        return None

    from .astro.time_scales import ephemeris_time
    from .native_solar_source import (
        native_solar_file_context,
        prime_swiss_solar_context,
    )
    from .solar_term_clock import (
        native_solar_root_datetime,
        native_solar_root_time_policy,
    )

    models: set[str] = set()
    retflags: set[int] = set()
    refinement_context: Optional[Dict[str, Any]] = None

    def sun_longitude(jd: float) -> float:
        # Planetary dynamics use TT. A UTC wall-clock JD is not UT1, and an
        # UT1 root cannot be labelled UTC with revjul().
        result, flags = ephemeris_call("calc", jd, swe.SUN, swe.FLG_SWIEPH)
        model = ephemeris_model_from_retflag(flags)
        if model not in {"swieph", "moshier", "jpl"} or not math.isfinite(result[0]):
            raise RuntimeError(
                "Solar position has no valid ephemeris model or longitude"
            )
        if model == "moshier":
            from .moshier_solar import MODEL_ID, solar_longitude

            longitude = solar_longitude(jd)
            model = MODEL_ID
        else:
            longitude = float(result[0] % 360.0)
        models.add(model)
        retflags.add(flags)
        if len(models) != 1:
            raise RuntimeError("Solar crossing mixed different ephemeris models")
        if (
            refinement_context is not None
            and native_solar_file_context(swe) != refinement_context
        ):
            raise EphemerisSourceError("solar_configuration_changed")
        return longitude

    # Coarse scan at ~daily resolution to find a sign change of
    # wrapped(longitude - target). Bisect within the bracket.
    def wrapped_diff(jd: float) -> float:
        return math.remainder(sun_longitude(jd) - target_longitude, 360.0)

    try:
        anchor_jd = ephemeris_time(anchor_utc).jd_tt
        if anchor_jd is None:
            return None
        jd_start = anchor_jd - 30.0
        jd_end = anchor_jd + 30.0
        previous_jd = jd_start
        previous_diff = wrapped_diff(previous_jd)
        step = 1.0  # one day
        if previous_diff == 0.0:
            # Retain a crossing exactly at the scan's first sample. Sun
            # longitude increases through it; the previous day brackets it.
            previous_jd -= step
            previous_diff = wrapped_diff(previous_jd)
        jd = previous_jd + step
        crossing: Optional[Tuple[float, float]] = None
        while jd <= jd_end:
            current_diff = wrapped_diff(jd)
            # A valid crossing goes from negative to non-negative while both
            # samples are near target (exclude the opposite-side wrap).
            if (
                previous_diff < 0.0
                and current_diff >= 0.0
                and current_diff - previous_diff < 90.0
            ):
                crossing = (previous_jd, jd)
                break
            previous_jd, previous_diff = jd, current_diff
            jd += step

        if crossing is None:
            return None

        low, high = crossing
        # A +/-30-day search can retain an earlier .se1 file through its
        # overlap with the nominal file. Pin one same-epoch source before
        # refinement, then recheck the bracket under that source. The public
        # Ren interval and its adjacent guard years fit the built-in preflight.
        if models == {"swieph"} and 1799 <= year <= 2201:
            primed, refinement_context = prime_swiss_solar_context(
                (low + high) / 2.0,
                native=swe,
                invoke=ephemeris_call,
                capture_context=provenance is not None,
            )
            if primed[1] != swe.FLG_SWIEPH:
                raise RuntimeError("Solar crossing source changed during refinement")
            if refinement_context is None and provenance is not None:
                raise EphemerisSourceError("solar_native_context_unavailable")
            left, right = wrapped_diff(low), wrapped_diff(high)
            if not left < 0 <= right or right - left >= 90:
                raise RuntimeError(
                    "Refinement source no longer brackets the solar crossing"
                )
        for _ in range(48):  # 2^-48 days is well below any needed precision
            mid = (low + high) / 2.0
            if mid in (low, high):
                break
            if wrapped_diff(mid) < 0.0:
                low = mid
            else:
                high = mid
        # The adjacent lower float is still before the numerical crossing.
        # A rounded midpoint can choose it and publish a pre-crossing boundary.
        resolved_jd = high
        moment = native_solar_root_datetime(resolved_jd)
        if provenance is not None:
            provenance.update(
                ephemeris_model=next(iter(models)),
                ephemeris_retflags=tuple(sorted(retflags)),
                ephemeris_library_version=str(getattr(swe, "version", "unknown")),
                resolved_jd_tt=resolved_jd,
                resolved_datetime_utc=moment.astimezone(timezone.utc).isoformat(),
                solar_model_details={
                    "model_id": NATIVE_SOLAR_ROOT_MODEL_ID,
                    "ephemeris_model": next(iter(models)),
                    "ephemeris_retflags": list(sorted(retflags)),
                    "ephemeris_library_version": str(
                        getattr(swe, "version", "unknown")
                    ),
                    "selected_crossing_jd_tt": resolved_jd,
                    "root_bracket_tt": [low, high],
                    "root_bracket_seconds": (high - low) * 86400,
                    "root_time_scale": "TT",
                    "root_selection_policy": "first_post_crossing_tt_float",
                    "numerical_epoch_representation": "explicit_ieee_float_tt_point",
                    "scalar_jd_scope": "exact_value_of_selected_ieee_float",
                    "civil_time_method": "datetime_from_tt_point",
                    **native_solar_root_time_policy(moment),
                    "accuracy_certified": False,
                    "numerical_resolution_is_physical_accuracy": False,
                },
            )
            if refinement_context is not None:
                provenance["solar_model_details"][
                    "native_source_context"
                ] = refinement_context
            from .moshier_solar import MODEL_ID, PROVIDER, model_details

            if models == {MODEL_ID}:
                # These are composed positions, not a stock native Sun. Keep
                # the model identity separate from native category flags.
                provenance.update(
                    resolution_provider=PROVIDER,
                    ephemeris_retflags=(),
                )
                provenance["solar_model_details"].update(model_details())
                provenance["solar_model_details"].pop("ephemeris_retflags")
        return moment
    except EphemerisSourceError:
        # A selected strict source must not silently become a linear year.
        raise
    except Exception as error:  # pragma: no cover - defensive swe error surface
        logger.warning(
            "swisseph solar-term resolution failed at year=%s target=%s: %s",
            year,
            target_longitude,
            error,
        )
        return None


def _solar_term_search_anchor_utc(year: int, term_index: int) -> datetime:
    """Choose a calendar month for the ±30-day native root search only."""
    return datetime(year, term_index // 2 + 1, 15, tzinfo=timezone.utc)


def _solar_term_utc_via_analytic(
    year: int,
    term_index: int,
    native_provenance: Dict[str, Any],
    *,
    spk: bool = False,
    expected_spk_key: Optional[Tuple[Any, ...]] = None,
    de440: bool = False,
    de440_profile: Optional[str] = None,
    vsop2013: bool = False,
    expected_vsop2013_key: Optional[Tuple[Any, ...]] = None,
    aa1996: bool = False,
    expected_aa1996_key: Optional[Tuple[Any, ...]] = None,
) -> Tuple[datetime, Dict[str, Any]]:
    from .analytic_solar import longitude_crossing_tt
    from .astro.time_scales import datetime_from_tt_point, ephemeris_time
    from .astro.tt_epoch import TTInstant

    month = term_index // 2 + 1
    low_day, high_day = (1, 12) if term_index % 2 == 0 else (12, 28)
    low = date(year, month, low_day).toordinal() + 1721424.5
    high = date(year, month, high_day).toordinal() + 1721424.5
    if sum((spk, de440, aa1996, vsop2013)) > 1:
        raise ValueError("A solar crossing requires one selected orbit source")
    if vsop2013:
        from .vsop2013_solar import longitude_crossing_tt as vsop2013_crossing_tt

        result = vsop2013_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_vsop2013_key,
        )
    elif aa1996:
        from .aa1996_solar import longitude_crossing_tt as aa1996_crossing_tt

        result = aa1996_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_aa1996_key,
        )
    elif de440:
        from .de440_solar import MODEL_ID as DE440_MODEL_ID
        from .de440_solar import longitude_crossing_tt_parts as de440_crossing_tt

        if de440_profile in {None, DE440_MODEL_ID}:
            result = de440_crossing_tt(
                float(SOLAR_TERM_LONGITUDES[term_index]), low, high
            )
        else:
            result = de440_crossing_tt(
                float(SOLAR_TERM_LONGITUDES[term_index]),
                low,
                high,
                profile_id=de440_profile,
            )
    elif spk:
        from .spk_solar import longitude_crossing_tt as spk_crossing_tt

        result = spk_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_spk_key,
        )
    else:
        result = longitude_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]), low, high
        )
    selected_parts = result.get("tt_parts")
    if selected_parts is not None:
        civil = datetime_from_tt_point(TTInstant.from_parts(*selected_parts))
    else:
        # A numerical root is an IEEE point, not a rounded UTC-label encoding.
        civil = datetime_from_tt_point(TTInstant.from_float(result["jd_tt"]))
    clock = ephemeris_time(civil)
    details = {
        **result["model"],
        "root_bracket_tt": (
            [sum(parts) for parts in result["tt_bracket_parts"]]
            if selected_parts is not None
            else result["bracket_tt"]
        ),
        "root_bracket_seconds": result["bracket_seconds"],
        "root_time_scale": "TT",
        "native_choice_probe_model": native_provenance.get("ephemeris_model"),
        "native_choice_probe_retflags": list(
            native_provenance.get("ephemeris_retflags", ())
        ),
        "selected_crossing_jd_tt": result["jd_tt"],
        "native_choice_probe_jd_tt": native_provenance.get("resolved_jd_tt"),
        "native_choice_probe_datetime_utc": native_provenance.get(
            "resolved_datetime_utc"
        ),
        **(
            {
                "native_choice_probe_source_context": native_provenance[
                    "solar_model_details"
                ]["native_source_context"]
            }
            if native_provenance.get("solar_model_details", {}).get(
                "native_source_context"
            )
            is not None
            else {}
        ),
        "selected_minus_native_seconds_tt": (
            (
                math.fsum(
                    [
                        selected_parts[0] - native_provenance["resolved_jd_tt"],
                        selected_parts[1],
                    ]
                )
                if selected_parts is not None
                else result["jd_tt"] - native_provenance["resolved_jd_tt"]
            )
            * 86400
            if type(native_provenance.get("resolved_jd_tt")) in (int, float)
            and math.isfinite(native_provenance["resolved_jd_tt"])
            else None
        ),
        "numerical_resolution_is_physical_accuracy": False,
        "civil_time_method": clock.method,
        "historical_ut1_convention": clock.method == "pre_1972_swiss_UT1_delta_t",
        "future_leap_seconds_assumed_unchanged": clock.future_leap_seconds_assumed_unchanged,
    }
    if selected_parts is not None:
        details.update(
            selected_crossing_tt_parts=list(selected_parts),
            root_bracket_tt_parts=[list(parts) for parts in result["tt_bracket_parts"]],
            numerical_epoch_representation="explicit_two_part_tt",
            scalar_jd_scope="rounded_display_of_selected_tt_parts",
        )
    else:
        details.update(
            numerical_epoch_representation="explicit_ieee_float_tt_point",
            scalar_jd_scope="exact_value_of_selected_ieee_float",
        )
    return civil, {
        "ephemeris_model": str(result["model"]["model_id"]),
        "ephemeris_retflags": (),
        "ephemeris_library_version": (
            "fatebridge.vsop2013_solar/" + str(result["model"]["version"])
            if vsop2013
            else (
                "fatebridge.aa1996_solar/" + str(result["model"]["version"])
                if aa1996
                else (
                    "fatebridge.de440_solar/1.1.0"
                    if de440
                    else (
                        "fatebridge.spk_solar/1.0.0"
                        if spk
                        else "fatebridge.analytic_solar/1.0.0"
                    )
                )
            )
        ),
        "solar_model_details": details,
    }


class _SolarTermEnvironmentChanged(RuntimeError):
    pass


def get_solar_terms_for_year(
    year: int, timezone_name: str = DEFAULT_TIMEZONE
) -> Tuple[SolarTerm, ...]:
    """Cache a year only within the same selected data-file environment."""
    return _solar_terms_for_context_year(year, timezone_name, year)


def _solar_terms_for_context_year(
    year: int, timezone_name: str, context_year: int
) -> Tuple[SolarTerm, ...]:
    # An in-range input needs neighbouring boundaries even at the two ends
    # of the software range. Select their model from that input's year, while
    # solving the actual adjacent year. This private allowance never extends
    # the standalone year-grid API or shares its out-of-range native cache.
    if year != context_year:
        from .solar_model_policy import solar_context_input_years

        low, high = solar_context_input_years(context_year)
        if not low <= context_year <= high or abs(year - context_year) != 1:
            raise ValueError("Adjacent solar boundaries require an in-range context")
    for _ in range(2):
        context = solar_term_cache_context(swe, year=context_year)
        try:
            terms = _get_solar_terms_for_year_cached(
                year, timezone_name, context, context_year
            )
        except _SolarTermEnvironmentChanged:
            _get_solar_terms_for_year_cached.cache_clear()
            continue
        if solar_term_cache_context(swe, year=context_year) == context:
            return terms
        # A concurrent installer changed the files while the year was
        # computed. Discard it rather than reuse a potentially mixed year.
        _get_solar_terms_for_year_cached.cache_clear()
    raise RuntimeError("星历数据在节气求解期间持续变化，请待安装完成后重试")


@lru_cache(maxsize=128)
def _get_solar_terms_for_year_cached(
    year: int, timezone_name: str, _context: Tuple[Any, ...], context_year: int
) -> Tuple[SolarTerm, ...]:
    # Lock the numerical work, not cache hits: restoring the Swiss path on
    # every hit would unnecessarily flush native ephemeris caches.
    with preserve_ephemeris_path():
        if solar_term_cache_context(swe, year=context_year) != _context:
            raise _SolarTermEnvironmentChanged()
        terms = _calculate_solar_terms_for_year(
            year, timezone_name, context_year=context_year
        )
        if solar_term_cache_context(swe, year=context_year) != _context:
            raise _SolarTermEnvironmentChanged()
        if any(not is_calculated_solar_term(t) for t in terms):
            raise EphemerisSourceError("solar_term_source_unverified")
        return terms


def _calculate_solar_terms_for_year(
    year: int, timezone_name: str, *, context_year: Optional[int] = None
) -> Tuple[SolarTerm, ...]:
    tzinfo = parse_timezone_name(timezone_name or DEFAULT_TIMEZONE)
    terms: List[SolarTerm] = []
    model_year = year if context_year is None else context_year
    context = solar_term_cache_context(swe, year=model_year)

    using_swe = swe is not None
    for index, (term_name, target_longitude) in enumerate(
        zip(SOLAR_TERM_NAMES, SOLAR_TERM_LONGITUDES)
    ):
        # A calendar anchor identifies the intended year/month; only a solved
        # longitude crossing may become a returned solar term.
        anchor_utc = _solar_term_search_anchor_utc(year, index)

        utc_moment: Optional[datetime] = None
        provenance: Dict[str, Any] = {}
        from .de440_solar import EXTENDED_MODEL_ID
        from .de440_solar import MODEL_ID as DE440_MODEL_ID
        from .solar_model_policy import (
            VALIDATED_SOFTWARE_YEARS,
            de440_profile_for_year,
        )

        # Select every crossing from the same captured source as its cache key.
        # Re-reading the environment here can observe A -> B -> A and cache a
        # mixed-source year even though the before/after contexts both say A.
        selected_mode = context[-1][0]
        explicit_vsop2013 = selected_mode == "vsop2013"
        explicit_spk = selected_mode == "spk"
        explicit_aa1996 = selected_mode == "aa1996"
        packaged_de440 = context[-1][1] in {DE440_MODEL_ID, EXTENDED_MODEL_ID}
        if explicit_vsop2013:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, {}, vsop2013=True, expected_vsop2013_key=context[-1][2]
            )
        elif explicit_aa1996:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, {}, aa1996=True, expected_aa1996_key=context[-1][2]
            )
        elif packaged_de440:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year,
                index,
                {},
                de440=True,
                de440_profile=de440_profile_for_year(model_year),
            )
        elif explicit_spk:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, {}, spk=True, expected_spk_key=context[-1][2]
            )
        elif using_swe:
            utc_moment = _solar_term_utc_via_swe(
                year, float(target_longitude), anchor_utc, provenance
            )
        if selected_mode == "swiss" and (
            utc_moment is None or provenance.get("ephemeris_model") != "swieph"
        ):
            raise EphemerisSourceError("solar_swiss_files_required")
        provider = (
            "vsop2013"
            if explicit_vsop2013
            else (
                "moshier_aa1996"
                if explicit_aa1996
                else (
                    "jpl_de440"
                    if packaged_de440
                    else ("jpl_spk" if explicit_spk else "swisseph")
                )
            )
        )
        provider = provenance.get("resolution_provider", provider)
        if (
            utc_moment is not None
            and not explicit_spk
            and not packaged_de440
            and not explicit_aa1996
            and not explicit_vsop2013
        ):
            if selected_mode == "analytic":
                if (
                    not VALIDATED_SOFTWARE_YEARS[0]
                    <= model_year
                    <= VALIDATED_SOFTWARE_YEARS[1]
                ):
                    raise ValueError(
                        "Explicit analytic solar mode currently covers1800..2200"
                    )
                utc_moment, provenance = _solar_term_utc_via_analytic(
                    year, index, provenance
                )
                provider = "fatebridge_analytic"
        if model_year != year and provenance.get("solar_model_details") is not None:
            from .solar_model_policy import solar_context_input_years

            provenance["solar_model_details"].update(
                adjacent_boundary_context_year=model_year,
                solar_model_input_years=list(solar_context_input_years(model_year)),
            )
        # Observe changes after each term as well as the whole year. Otherwise
        # a selector A -> B -> A between terms can leave a mixed cached year.
        # This does not certify native files were read atomically within a call.
        if solar_term_cache_context(swe, year=model_year) != context:
            raise _SolarTermEnvironmentChanged()

        if utc_moment is None:
            raise EphemerisSourceError("solar_native_unavailable")

        local_moment = utc_moment.astimezone(tzinfo)
        terms.append(
            SolarTerm(
                name=term_name,
                moment=local_moment,
                date_key=local_moment.strftime("%Y%m%d"),
                day_ganzhi=get_day_ganzhi(
                    local_moment.year, local_moment.month, local_moment.day
                ),
                resolution_provider=provider,
                ephemeris_model=provenance.get("ephemeris_model", "unknown"),
                ephemeris_retflags=provenance.get("ephemeris_retflags", ()),
                ephemeris_library_version=provenance.get("ephemeris_library_version"),
                solar_model_details=provenance.get("solar_model_details"),
            )
        )

    return tuple(terms)


# Preserve the existing cache-maintenance API for callers and tests. The
# actual cache is keyed by the private data-environment token as well.
for _cache_attribute in ("cache_clear", "cache_info", "cache_parameters"):
    setattr(
        get_solar_terms_for_year,
        _cache_attribute,
        getattr(_get_solar_terms_for_year_cached, _cache_attribute),
    )


def get_solar_term_environment_key(*, year: Optional[int] = None) -> Tuple[Any, ...]:
    """Bind derived BaZi caches to the same environment as solar-term roots.

    This stat-based identity detects ordinary installations/provider changes;
    it is not a continuous byte-immutability or accuracy certificate.
    """
    if year is None:
        return solar_term_cache_context(swe)
    from .solar_model_policy import solar_context_input_years

    low, high = solar_context_input_years(year)
    # Month boundaries read adjacent years too. Their selected source must
    # stay in the derived-cache identity even when the input year is outside.
    contexts = []
    for candidate in range(year - 1, year + 2):
        source_year = (
            year if low <= year <= high and not low <= candidate <= high else candidate
        )
        context = solar_term_cache_context(swe, year=source_year)
        if context not in contexts:
            contexts.append(context)
    if len(contexts) == 1:
        return contexts[0]
    return ("solar_adjacent_profile_contexts", tuple(contexts))


def get_jieqi_year_grid(
    year: int, timezone_name: str = DEFAULT_TIMEZONE
) -> List[Dict[str, Any]]:
    return [item.as_dict() for item in get_solar_terms_for_year(year, timezone_name)]


def _term_window(moment: datetime, timezone_name: str) -> List[SolarTerm]:
    local_moment = localize_datetime(moment, timezone_name)
    from .solar_model_policy import solar_context_input_years

    low, high = solar_context_input_years(local_moment.year)
    window: List[SolarTerm] = []
    for year in (local_moment.year - 1, local_moment.year, local_moment.year + 1):
        if low <= local_moment.year <= high and not low <= year <= high:
            window.extend(
                _solar_terms_for_context_year(year, timezone_name, local_moment.year)
            )
        else:
            window.extend(get_solar_terms_for_year(year, timezone_name))
    return sorted(window, key=lambda item: utc_instant(item.moment))


def get_adjacent_solar_terms(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> Tuple[SolarTerm, SolarTerm]:
    local_moment = localize_datetime(moment, timezone_name)
    previous = None
    upcoming = None

    for term in _term_window(local_moment, timezone_name):
        if utc_instant(term.moment) <= utc_instant(local_moment):
            previous = term
            continue
        upcoming = term
        break

    if previous is None or upcoming is None:
        raise ValueError("Unable to resolve neighbouring solar terms.")

    return previous, upcoming


def get_bazi_year(moment: datetime, timezone_name: str = DEFAULT_TIMEZONE) -> int:
    local_moment = localize_datetime(moment, timezone_name)
    current_year_terms = {
        term.name: term
        for term in get_solar_terms_for_year(local_moment.year, timezone_name)
    }
    li_chun = current_year_terms["立春"]
    require_calculated_solar_term(li_chun)
    return (
        local_moment.year
        if utc_ordering_key(local_moment) >= utc_ordering_key(li_chun.moment)
        else local_moment.year - 1
    )


def get_bazi_month_context(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> Dict[str, object]:
    current_boundary, next_boundary, month_branch, month_index = (
        get_bazi_month_boundaries(moment, timezone_name)
    )
    local_moment = localize_datetime(moment, timezone_name)

    return {
        "branch": month_branch,
        "month_index": month_index,
        "comparison_datetime": local_moment.isoformat(),
        "elapsed_basis": "utc_instant_seconds",
        "elapsed_seconds_since_start": (
            utc_instant(local_moment) - utc_instant(current_boundary.moment)
        ).total_seconds(),
        "elapsed_seconds_until_next": (
            utc_instant(next_boundary.moment) - utc_instant(local_moment)
        ).total_seconds(),
        "start_term": current_boundary.as_dict(),
        "next_term": next_boundary.as_dict(),
        "days_since_start": round(
            elapsed_days_between(current_boundary.moment, local_moment), 4
        ),
        "days_until_next": round(
            elapsed_days_between(local_moment, next_boundary.moment), 4
        ),
    }


def get_bazi_month_boundaries(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> Tuple[SolarTerm, SolarTerm, str, int]:
    local_moment = localize_datetime(moment, timezone_name)
    candidates = [
        term
        for term in _term_window(local_moment, timezone_name)
        if term.name in BAZI_MONTH_START_TERMS
    ]

    current_boundary = None
    next_boundary = None
    for term in candidates:
        if utc_instant(term.moment) <= utc_instant(local_moment):
            current_boundary = term
            continue
        next_boundary = term
        break

    if current_boundary is None or next_boundary is None:
        raise ValueError("Unable to resolve BaZi month boundary.")

    require_calculated_solar_term(current_boundary)
    require_calculated_solar_term(next_boundary)
    month_branch = BAZI_MONTH_START_TERMS[current_boundary.name]
    month_index = BAZI_MONTH_SEQUENCE.index(month_branch)
    return current_boundary, next_boundary, month_branch, month_index


def _format_lunar_year(year: int) -> str:
    digits = "零一二三四五六七八九"
    return "".join(digits[int(char)] for char in str(year))


def _lunar_supplement_source(solar_date: date) -> Optional[Dict[str, str]]:
    return _prefix_lunar_source(solar_date) or _later_lunar_source(solar_date)


def _lunar_supported_range_payload() -> Dict[str, str]:
    return {
        "start": LUNAR_SUPPORTED_SOLAR_START.isoformat(),
        "end": LUNAR_SUPPORTED_SOLAR_END.isoformat(),
    }


def lunar_supported_range_message() -> str:
    return (
        f"离线农历换算仅支持公历 {LUNAR_SUPPORTED_SOLAR_START.isoformat()} "
        f"至 {LUNAR_SUPPORTED_SOLAR_END.isoformat()}。"
    )


def _safe_lunar_date_from_solar(
    moment: datetime, timezone_name: str
) -> Optional[_LunarDateValue]:
    if LunarDate is None:
        return None

    local_moment = localize_datetime(moment, timezone_name)
    solar_date = local_moment.date()
    if (
        solar_date < LUNAR_SUPPORTED_SOLAR_START
        or solar_date > LUNAR_SUPPORTED_SOLAR_END
    ):
        return None

    try:
        lunar = _lunar_date_from_solar(solar_date)
    except ValueError:
        return None

    return lunar


def get_lunar_context(
    moment: datetime,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    pillars: Optional[Dict[str, Tuple[str, str]]] = None,
    civil_datetime: Optional[datetime] = None,
) -> Optional[Dict[str, object]]:
    local_moment = localize_datetime(moment, timezone_name)
    lunar = _safe_lunar_date_from_solar(local_moment, timezone_name)
    if lunar is None:
        return None

    seasonal_moment = localize_datetime(civil_datetime or moment, timezone_name)
    previous_term, next_term = get_adjacent_solar_terms(seasonal_moment, timezone_name)
    days_since_term = (seasonal_moment.date() - previous_term.moment.date()).days

    context: Dict[str, object] = {
        "solar_datetime": local_moment.replace(tzinfo=None).isoformat(sep=" "),
        "timezone": timezone_name,
        "birth": local_moment.replace(tzinfo=None).isoformat(sep=" "),
        "year": lunar.year,
        "month": lunar.month,
        "day": lunar.day,
        "is_leap_month": bool(lunar.isLeapMonth),
        "year_cn": _format_lunar_year(lunar.year),
        "month_cn": f"{'闰' if lunar.isLeapMonth else ''}{LUNAR_MONTH_NAMES[lunar.month]}",
        "day_cn": LUNAR_DAY_NAMES[lunar.day],
        "display": (
            f"{'闰' if lunar.isLeapMonth else ''}{LUNAR_MONTH_NAMES[lunar.month]}"
            f"{LUNAR_DAY_NAMES[lunar.day]}"
        ),
        "jieqi": previous_term.name,
        "jiedelta": f"{previous_term.name}后第{days_since_term}天",
        "previous_jieqi": previous_term.as_dict(),
        "next_jieqi": next_term.as_dict(),
        "days_until_next_jieqi": round(
            elapsed_days_between(seasonal_moment, next_term.moment), 4
        ),
    }

    conversion_source = _lunar_supplement_source(local_moment.date())
    if conversion_source is not None:
        context["conversion_source"] = conversion_source

    if pillars:
        context["year_jieqi_ganzhi"] = f"{pillars['year'][0]}{pillars['year'][1]}"
        context["month_ganzhi"] = f"{pillars['month'][0]}{pillars['month'][1]}"
        context["day_ganzhi"] = f"{pillars['day'][0]}{pillars['day'][1]}"
        context["time_ganzhi"] = f"{pillars['hour'][0]}{pillars['hour'][1]}"
        context["meihua"] = derive_meihua_hexagram(
            # 梅花年月日時取数采用同一农历年、月、日；八字年柱仍以立春分界。
            year_branch=ZHI[(lunar.year - 4) % 12],
            lunar_month=lunar.month,
            lunar_day=lunar.day,
            hour_branch=ZHI[((local_moment.hour + 1) // 2) % 12],
        )

    return context


def build_calendar_context(
    moment: datetime,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    pillars: Optional[Dict[str, Tuple[str, str]]] = None,
    civil_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Keep lunar/day clocks while resolving seasonal boundaries at the civil instant."""
    local_moment = localize_datetime(moment, timezone_name)
    seasonal_moment = localize_datetime(civil_datetime or moment, timezone_name)
    previous_term, next_term = get_adjacent_solar_terms(seasonal_moment, timezone_name)
    require_calculated_solar_term(previous_term)
    require_calculated_solar_term(next_term)
    month_context = get_bazi_month_context(seasonal_moment, timezone_name)
    lunar_context = get_lunar_context(
        local_moment,
        timezone_name=timezone_name,
        pillars=pillars,
        civil_datetime=seasonal_moment,
    )
    lunar_support = {
        "supported": lunar_context is not None,
        "supported_range": _lunar_supported_range_payload(),
    }
    if lunar_context is None:
        lunar_support["reason"] = lunar_supported_range_message()

    return {
        "timezone": timezone_name,
        # Use the same fractional civil clock consumed by term comparisons.
        # Truncation here makes opposite sides of a boundary print identically.
        "solar_datetime": local_moment.replace(tzinfo=None).isoformat(sep=" "),
        "current_solar_term": previous_term.as_dict(),
        "next_solar_term": next_term.as_dict(),
        "solar_term_delta": {
            "days_since_current": round(
                elapsed_days_between(previous_term.moment, seasonal_moment), 4
            ),
            "days_until_next": round(
                elapsed_days_between(seasonal_moment, next_term.moment), 4
            ),
            "description": f"{previous_term.name}后第{(seasonal_moment.date() - previous_term.moment.date()).days}天",
        },
        "bazi_month_boundary": month_context,
        "lunar_calendar": lunar_context,
        "lunar_calendar_support": lunar_support,
    }
