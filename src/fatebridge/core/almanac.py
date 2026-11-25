"""
Calendrical helpers for solar terms, lunar context, and BaZi boundaries.

This module keeps the expensive year-level calculations cached so service-layer
code can enrich responses without recomputing 24 solar terms on every call.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from fractions import Fraction
from functools import lru_cache
from typing import Any, TypedDict

try:
    from lunardate import LunarDate
    from lunardate import __version__ as LUNARDATE_VERSION
except ImportError:  # pragma: no cover - optional import failure path
    LunarDate = None
    LUNARDATE_VERSION = ""

from fatebridge.core import (
    aa1996_solar,
    analytic_solar,
    de440_solar,
    de441_solar,
    jpl_ephemeris,
    native_solar_source,
    solar_model_policy,
    solar_term_clock,
    spk_solar,
    vsop2013_solar,
)
from fatebridge.core.astro import time_scales
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import (
    UTCDefinitionEvidence,
    utc_definition_evidence,
)
from fatebridge.core.divination import derive_meihua_hexagram
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
    native_ephemeris_errors,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.core.execution_context import current_datetime
from fatebridge.core.lunar_1900_prefix import START as LUNAR_PREFIX_START
from fatebridge.core.lunar_1900_prefix import convert as _prefix_lunar_date
from fatebridge.core.lunar_1900_prefix import source_for as _prefix_lunar_source
from fatebridge.core.lunar_supplement import END as LUNAR_SUPPLEMENT_END
from fatebridge.core.lunar_supplement import convert as _supplement_lunar_date
from fatebridge.core.lunar_supplement import source_for as _later_lunar_source
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.utils.civil_time import (
    CivilPoint,
    NominalClockLabel,
    UTCCalendar,
    ZonedCalendar,
    gregorian_ordinal,
    utc_calendar,
)
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import is_unspecified_local_time, parse_timezone_name

logger = logging.getLogger(__name__)

# Solar ecliptic longitude (tropical) at which each term occurs.
# Mapping follows SOLAR_TERM_NAMES order starting at 小寒 = 285°.
SOLAR_TERM_LONGITUDES = tuple((285 + 15 * i) % 360 for i in range(24))


DEFAULT_TIMEZONE = "Asia/Shanghai"

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
    else:
        pass
    prefix = _prefix_lunar_date(solar_date)
    if prefix is not None:
        return _LunarDateValue(*prefix)
    else:
        pass
    supplement = _supplement_lunar_date(solar_date)
    if supplement is not None:
        return _LunarDateValue(*supplement)
    else:
        pass
    # note (lunardate): The 0.2 API needs camelCase; 0.3 deprecates those names.
    uses_legacy_lunar_api = LUNARDATE_VERSION.startswith("0.2.")
    year, month, day = solar_date.year, solar_date.month, solar_date.day
    if uses_legacy_lunar_api:
        lunar = LunarDate.fromSolarDate(year, month, day)
        round_trip_solar_date = lunar.toSolarDate()
        is_leap_month = lunar.isLeapMonth
    else:
        lunar = LunarDate.from_solar_date(year, month, day)
        round_trip_solar_date = lunar.to_solar_date()
        is_leap_month = lunar.is_leap_month
    if round_trip_solar_date != solar_date:
        raise ValueError("农历转换无法反向验证")
    else:
        pass
    corrected_year_encoding = LUNAR_YEAR_INFO_CORRECTIONS.get(lunar.year)
    if corrected_year_encoding is None:
        return _LunarDateValue(lunar.year, lunar.month, lunar.day, is_leap_month)
    else:
        pass

    lunar_new_year = LunarDate(lunar.year, 1, 1)
    solar_new_year = (
        lunar_new_year.toSolarDate()
        if uses_legacy_lunar_api
        else lunar_new_year.to_solar_date()
    )
    remaining = (solar_date - solar_new_year).days
    leap_month = corrected_year_encoding & 0xF
    for month in range(1, 13):
        for is_leap in (False, True) if month == leap_month else (False,):
            bit = 16 if is_leap else 16 - month
            length = 29 + ((corrected_year_encoding >> bit) & 1)
            if remaining < length:
                return _LunarDateValue(lunar.year, month, remaining + 1, is_leap)
            else:
                pass
            remaining -= length
    raise ValueError("农历日期超出当年月份表")


DAY_GANZHI_JDN_OFFSET = 49


class SolarTermProvenance(TypedDict, total=False):
    ephemeris_model: str
    ephemeris_retflags: tuple[int, ...]
    ephemeris_library_version: str | None
    resolved_jd_tt: float
    solar_model_details: dict[str, Any]
    resolution_provider: str
    resolved_tt_instant: TTInstant
    resolved_civil_point: CivilPoint


_STATIC_SOLAR_MODEL_KEYS = frozenset(
    {
        "coefficient_product_producer",
        "source_url",
        "source_format_url",
        "segment_coverage_tdb_jd",
        "apparent_direction_model",
        "source_identity_scope",
        "tdb_model_author_comparison_years",
        "time_argument",
        "position_frame",
        "coefficient_storage",
    }
)


def _compact_solar_model_details(details: dict[str, Any]) -> dict[str, Any]:
    return {
        k: deepcopy(v) for k, v in details.items() if k not in _STATIC_SOLAR_MODEL_KEYS
    }


@dataclass(frozen=True)
class SolarTerm:
    name: str
    calendar: ZonedCalendar
    # Retflags/library details remain internal; public records expose provider/model.
    resolution_provider: str = "unknown"
    ephemeris_model: str = "unknown"
    ephemeris_retflags: tuple[int, ...] = ()
    ephemeris_library_version: str | None = None
    solar_model_details: dict[str, Any] | None = field(default=None, hash=False)
    tt_instant: TTInstant | None = None
    civil_point: CivilPoint | None = None
    utc_definition: UTCDefinitionEvidence | None = field(
        default=None, compare=False, hash=False
    )
    source_grid_year: int | None = None

    def __post_init__(self) -> None:
        point = self.civil_point
        if point is None:
            return
        else:
            pass
        display_day = self.calendar.utc.julian_day_exact()
        if point.day >= display_day:
            return
        else:
            pass
        # Zone transitions, folds and local dates change on the clock grid.
        # The lower neighbor owns the exact point before a forward rounding.
        lower, _ = point.nominal_calendar_bracket()
        earlier = ZonedCalendar(lower, self.calendar.zone)
        exact = earlier.rule_sample()
        rounded = self.calendar.rule_sample()
        exact_unspecified = is_unspecified_local_time(exact)
        rounded_unspecified = is_unspecified_local_time(rounded)
        if exact_unspecified != rounded_unspecified or (
            not exact_unspecified
            and (earlier.local_ordinal, exact.utcoffset(), exact.fold)
            != (self.calendar.local_ordinal, rounded.utcoffset(), rounded.fold)
        ):
            object.__setattr__(self, "calendar", earlier)
            object.__setattr__(self, "civil_point", CivilPoint(point.day, display_day))
        else:
            pass

    @property
    def point(self) -> CivilPoint:
        """Retain the selected point; calendar-only fixtures keep label precision."""
        if self.civil_point is not None:
            return self.civil_point
        else:
            pass
        return CivilPoint(self.calendar.utc.julian_day_exact())

    @property
    def moment(self) -> datetime:
        """A datetime adapter for consumers whose civil range is representable."""
        return self.calendar.require_datetime()

    @property
    def utc_key(self) -> tuple[int, int]:
        """Legacy display-grid key; numerical boundary decisions use point.day."""
        return self.calendar.utc.ordinal, self.calendar.utc.microseconds_of_day

    @property
    def date_key(self) -> str:
        moment = self.calendar.as_datetime()
        if moment is not None:
            return moment.strftime("%Y%m%d")
        else:
            pass
        year, month, day = self.calendar.local_parts[:3]
        label = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
        return f"{label}{month:02d}{day:02d}"

    @property
    def day_ganzhi(self) -> str:
        return get_day_ganzhi(*self.calendar.local_parts[:3])

    @property
    def has_defined_local_clock(self) -> bool:
        return not is_unspecified_local_time(self.calendar.rule_sample())

    def local_day_delta_label(self, local_ordinal: int) -> str:
        if not self.has_defined_local_clock:
            return f"{self.name}的当地节气日序未定义"
        else:
            pass
        return f"{self.name}后第{local_ordinal - self.calendar.local_ordinal}天"

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "resolution_provider": self.resolution_provider,
            "ephemeris_model": self.ephemeris_model,
            "timezone": self.calendar.timezone_label,
        }
        # Display uses the already rounded and capped UTC calendar. The
        # retained rational point controls numerical boundary decisions.
        if self.has_defined_local_clock:
            result.update(
                datetime=self.calendar.isoformat(sep=" ", include_offset=False),
                date_key=self.date_key,
                day_ganzhi=self.day_ganzhi,
                datetime_with_offset=self.calendar.isoformat(),
                utc_offset_seconds=self.calendar.offset.total_seconds(),
                fold=self.calendar.fold,
            )
        else:
            result["datetime_utc"] = self.calendar.utc.isoformat()
        if self.solar_model_details is not None:
            result["solar_model_details"] = _compact_solar_model_details(
                self.solar_model_details
            )
        else:
            pass
        if self.civil_point is not None:
            result["civil_point"] = self.civil_point.to_record()
            result["comparison_policy"] = "retained_nominal_civil_point_v1"
        else:
            pass
        if self.utc_definition is not None:
            result["utc_definition"] = deepcopy(self.utc_definition)
        else:
            pass
        return result


def is_calculated_solar_term(term: SolarTerm) -> bool:
    if term.resolution_provider == "jpl_de441":

        details = term.solar_model_details or {}
        return (
            term.ephemeris_model == de441_solar.MODEL_ID
            and all(details.get(k) == v for k, v in de441_solar.model_details().items())
            and not term.ephemeris_retflags
        )
    elif term.resolution_provider == "swisseph":
        return True
    elif term.resolution_provider in {"moshier_aa1996", "vsop2013"}:

        selected = (
            vsop2013_solar.MODEL_ID
            if term.resolution_provider == "vsop2013"
            else aa1996_solar.MODEL_ID
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
    elif term.resolution_provider == "jpl_de440":

        return (
            term.ephemeris_model
            in {de440_solar.MODEL_ID, de440_solar.EXTENDED_MODEL_ID}
            and term.solar_model_details is not None
            and term.solar_model_details.get("model_id") == term.ephemeris_model
            and bool(term.solar_model_details.get("coefficient_sha256"))
            and bool(term.solar_model_details.get("source_kernel_sha256"))
            and not term.ephemeris_retflags
        )
    elif term.resolution_provider == "jpl_spk":

        return (
            term.ephemeris_model == spk_solar.MODEL_ID
            and term.solar_model_details is not None
            and term.solar_model_details.get("model_id") == spk_solar.MODEL_ID
            and bool(term.solar_model_details.get("kernel_sha256"))
        )
    else:
        return (
            term.resolution_provider == "fatebridge_analytic"
            and term.ephemeris_model == analytic_solar.MODEL_ID
            and term.solar_model_details is not None
            and term.solar_model_details.get("model_id") == analytic_solar.MODEL_ID
        )


def require_calculated_solar_term(term: SolarTerm) -> None:
    """Reject coarse or unknown solar-term boundaries.

    Checking the actual consumed term avoids certifying a separate cache or
    a different year. Provider availability alone is not an accuracy verdict.
    """
    if not is_calculated_solar_term(term):
        raise EphemerisSourceError("solar_term_source_unverified")
    else:
        pass


def localize_datetime(moment: datetime, timezone_name: str | None) -> datetime:
    tzinfo = parse_timezone_name(timezone_name or DEFAULT_TIMEZONE)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=tzinfo)
    else:
        pass
    return ZonedCalendar(utc_calendar(moment), tzinfo).require_datetime()


def _nominal_day_span(
    start: datetime | ZonedCalendar | CivilPoint,
    end: datetime | ZonedCalendar | CivilPoint,
) -> Fraction:
    """Subtract the selected civil coordinates before scalar display rounding."""
    points: list[Fraction] = []
    for moment in (start, end):
        if isinstance(moment, CivilPoint):
            points.append(moment.day)
        else:
            calendar = (
                moment.utc
                if isinstance(moment, ZonedCalendar)
                else utc_calendar(moment)
            )
            points.append(calendar.julian_day_exact())
    return points[1] - points[0]


def elapsed_seconds_between(
    start: datetime | ZonedCalendar | CivilPoint,
    end: datetime | ZonedCalendar | CivilPoint,
) -> float:
    """Nominal UTC-label seconds, including auxiliary Gregorian labels."""
    return float(_nominal_day_span(start, end) * 86400)


def elapsed_days_between(
    start: datetime | ZonedCalendar | CivilPoint,
    end: datetime | ZonedCalendar | CivilPoint,
) -> float:
    """Nominal UTC-label days between aware instants, accounting for DST.

    Python subtracts wall clocks when two datetimes share the same tzinfo.
    Normalize both labels to UTC before subtracting, with 86400 nominal
    seconds per day. Python datetime omits leap seconds: this engineering
    calendar policy does not compute uniform TAI/TT elapsed SI seconds.
    """
    return float(_nominal_day_span(start, end))


def current_local_datetime(timezone_name: str | None = None) -> datetime:
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
) -> str:
    """Gregorian civil-day cycle; 2000-01-07 is 甲子, without hour rollover."""
    index = (_julian_day_number(year, month, day) + DAY_GANZHI_JDN_OFFSET) % 60
    return f"{GAN[index % 10]}{ZHI[index % 12]}"


def _solar_term_utc_via_swe(
    year: int,
    target_longitude: float,
    anchor_utc: UTCCalendar,
    provenance: SolarTermProvenance | None = None,
) -> UTCCalendar | None:
    """Resolve a TT solar-longitude crossing, then label its civil instant.
    ``target_longitude`` near ``anchor_utc``.

    The anchor is used to disambiguate which yearly crossing to return
    (so 冬至 for civil year 2024 is Dec 2024 rather than Dec 2023). Search
    up to 30 days from the calendar-month anchor toward the target longitude.
    Files for an unused prefix before that bracket are not required.

    Optional native data select the source; they are not a prerequisite for
    the bundled DE441 Sun. Strict Swiss/JPL selection cannot use that fallback.
    Return None if no crossing is found; the caller rejects that result.
    """

    require_swiss = solar_model_policy.solar_model_policy() == "swiss"
    strict_jpl = jpl_ephemeris.configured_jpl_file() is not None
    if swe is None and (require_swiss or strict_jpl):
        return None
    else:
        pass
    models: set[str] = set()
    retflags: set[int] = set()
    refining = False
    refinement_context: dict[str, Any] | None = None

    def sun_longitude(jd: float) -> float:
        # Planetary dynamics use TT. A UTC wall-clock JD is not UT1, and an
        # UT1 root cannot be labelled UTC with revjul().
        native_result = None
        if swe is not None:
            try:
                native_result = ephemeris_call("calc", jd, swe.SUN, swe.FLG_SWIEPH)
            except swe.Error as error:
                # Outside the native analytical interval, a missing .se1 file
                # raises instead of returning MOSEPH. Recover only that public
                # missing-file error, never a corrupt file or strict source.
                message = str(error)
                if (
                    require_swiss
                    or strict_jpl
                    or not message.startswith("swisseph.calc: SwissEph file '")
                    or ".se1' not found in PATH " not in message
                ):
                    raise
                else:
                    pass
        else:
            pass
        if native_result is None:
            model = "unavailable"
        else:
            result, flags = native_result
            model = ephemeris_model_from_retflag(flags)
            if model not in {"swieph", "moshier", "jpl"} or not math.isfinite(
                result[0]
            ):
                raise RuntimeError(
                    "Solar position has no valid ephemeris model or longitude"
                )
            else:
                pass
        if model in {"unavailable", "moshier"}:
            if require_swiss:
                raise EphemerisSourceError("solar_swiss_files_required")
            else:
                pass

            longitude = de441_solar.solar_longitude(jd)
            model = de441_solar.MODEL_ID
        else:
            longitude = float(result[0] % 360.0)
        if refining:
            models.add(model)
            if native_result is not None and model in {"swieph", "jpl"}:
                retflags.add(flags)
            else:
                pass
            if len(models) != 1:
                raise RuntimeError("Solar crossing mixed different ephemeris models")
            else:
                pass
        else:
            pass
        if (
            refinement_context is not None
            and native_solar_source.native_solar_file_context(swe) != refinement_context
        ):
            raise EphemerisSourceError("solar_configuration_changed")
        else:
            pass
        return longitude

    # Find a daily bracket in the target direction from the monthly anchor.
    def wrapped_diff(jd: float) -> float:
        return math.remainder(sun_longitude(jd) - target_longitude, 360.0)

    try:
        anchor_jd = time_scales.utc_clock(anchor_utc).jd_tt
        if anchor_jd is None:
            anchor_jd = time_scales.ephemeris_time(anchor_utc).jd_tt
        else:
            pass
        if anchor_jd is None:
            raise solar_term_clock.SolarTermClockError("solar_root_clock_unavailable")
        else:
            pass
        previous_jd = anchor_jd
        previous_diff = wrapped_diff(previous_jd)
        step = -1.0 if previous_diff >= 0.0 else 1.0
        crossing: tuple[float, float] | None = None
        for offset in range(1, 31):
            jd = anchor_jd + offset * step
            current_diff = wrapped_diff(jd)
            if step < 0.0:
                low, high = jd, previous_jd
                left, right = current_diff, previous_diff
            else:
                low, high = previous_jd, jd
                left, right = previous_diff, current_diff
            # An exact root on the backward limit still needs its earlier
            # side, as did an exact first sample in the original full scan.
            if step < 0.0 and current_diff == 0.0:
                crossing = (jd - 1.0, jd)
                break
            else:
                pass
            # Both directions must produce the same forward crossing bracket,
            # excluding a sign change across the opposite-side angular wrap.
            if left < 0.0 <= right and right - left < 90.0:
                crossing = (low, high)
                break
            else:
                pass
            previous_jd, previous_diff = jd, current_diff

        if crossing is None:
            return None
        else:
            pass

        low, high = crossing
        # Coarse samples may use another model near a file boundary.
        # Only the consumed root bracket and refinement may
        # establish the returned model/flags. Recheck both ends before pinning.
        refining = True
        left, right = wrapped_diff(low), wrapped_diff(high)
        if not left < 0 <= right or right - left >= 90:
            raise RuntimeError("Selected source does not bracket the solar crossing")
        else:
            pass
        # A coarse search can retain an earlier .se1 file through its
        # overlap with the nominal file. Pin one same-epoch source before
        # refinement, then recheck the bracket under that source. The public
        # Ren interval and its adjacent guard years fit the built-in preflight.
        # Use the actual TT bracket for the same policy as its reobserver.
        if models == {"swieph"} and native_solar_source.swiss_solar_context_required(
            (low + high) / 2.0
        ):
            primed, refinement_context = native_solar_source.prime_swiss_solar_context(
                (low + high) / 2.0,
                native=swe,
                invoke=ephemeris_call,
                capture_context=provenance is not None,
            )
            if primed[1] != swe.FLG_SWIEPH:
                raise RuntimeError("Solar crossing source changed during refinement")
            else:
                pass
            if refinement_context is None and provenance is not None:
                raise EphemerisSourceError("solar_native_context_unavailable")
            else:
                pass
            left, right = wrapped_diff(low), wrapped_diff(high)
            if not left < 0 <= right or right - left >= 90:
                raise RuntimeError(
                    "Refinement source no longer brackets the solar crossing"
                )
            else:
                pass
        else:
            pass
        for _ in range(48):  # 2^-48 days is well below any needed precision
            mid = (low + high) / 2.0
            if mid in (low, high):
                break
            else:
                pass
            if wrapped_diff(mid) < 0.0:
                low = mid
            else:
                high = mid
        # The adjacent lower float is still before the numerical crossing.
        # A rounded midpoint can choose it and publish a pre-crossing boundary.
        resolved_jd = high
        point = TTInstant.from_float(resolved_jd)
        civil_point = solar_term_clock.native_solar_root_point(point)
        moment = civil_point.as_calendar()
        if provenance is not None:
            provenance.update(
                {
                    "ephemeris_model": next(iter(models)),
                    "ephemeris_retflags": tuple(sorted(retflags)),
                    "ephemeris_library_version": str(
                        getattr(swe, "version", "unknown")
                    ),
                    "resolved_jd_tt": resolved_jd,
                    "resolved_tt_instant": point,
                    "resolved_civil_point": civil_point,
                    "solar_model_details": {
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
                        "civil_time_method": "utc_calendar_from_tt",
                        **solar_term_clock.native_solar_root_time_policy(moment),
                        "accuracy_certified": False,
                        "numerical_resolution_is_physical_accuracy": False,
                    },
                }
            )
            if refinement_context is not None:
                provenance["solar_model_details"][
                    "native_source_context"
                ] = refinement_context
            else:
                pass

            if models == {de441_solar.MODEL_ID}:
                # These are composed positions, not a stock native Sun. Keep
                # the model identity separate from native category flags.
                provenance.update(
                    {
                        "resolution_provider": de441_solar.PROVIDER,
                        "ephemeris_library_version": None,
                        "ephemeris_retflags": (),
                    }
                )
                provenance["solar_model_details"].update(de441_solar.model_details())
                provenance["solar_model_details"].pop("ephemeris_retflags")
                provenance["solar_model_details"].pop("ephemeris_library_version")
            else:
                pass
        else:
            pass
        return moment
    except EphemerisSourceError:
        # A selected strict source must not silently become a linear year.
        raise
    except native_ephemeris_errors(
        swe
    ) as error:  # pragma: no cover - defensive swe error surface
        logger.warning(f"Swiss solar-term resolution failed ({type(error).__name__})")
        return None


def _solar_term_search_anchor_utc(year: int, term_index: int) -> UTCCalendar:
    """Choose a calendar month for the ±30-day native root search only."""
    return UTCCalendar(gregorian_ordinal(year, term_index // 2 + 1, 15), 0)


def _solar_term_utc_via_analytic(
    year: int,
    term_index: int,
    *,
    spk: bool = False,
    expected_spk_key: tuple[Any, ...] | None = None,
    de440: bool = False,
    de440_profile: str | None = None,
    vsop2013: bool = False,
    expected_vsop2013_key: tuple[Any, ...] | None = None,
    aa1996: bool = False,
    expected_aa1996_key: tuple[Any, ...] | None = None,
) -> tuple[UTCCalendar, SolarTermProvenance]:

    month = term_index // 2 + 1
    low_day, high_day = (1, 12) if term_index % 2 == 0 else (12, 28)
    low = gregorian_ordinal(year, month, low_day) + 1721424.5
    high = gregorian_ordinal(year, month, high_day) + 1721424.5
    if sum((spk, de440, aa1996, vsop2013)) > 1:
        raise ValueError("A solar crossing requires one selected orbit source")
    else:
        pass
    if vsop2013:

        result = vsop2013_solar.longitude_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_vsop2013_key,
        )
    elif aa1996:

        result = aa1996_solar.longitude_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_aa1996_key,
        )
    elif de440:

        if de440_profile in {None, de440_solar.MODEL_ID}:
            result = de440_solar.longitude_crossing_tt_parts(
                float(SOLAR_TERM_LONGITUDES[term_index]), low, high
            )
        else:
            result = de440_solar.longitude_crossing_tt_parts(
                float(SOLAR_TERM_LONGITUDES[term_index]),
                low,
                high,
                profile_id=de440_profile,
            )
    elif spk:

        result = spk_solar.longitude_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]),
            low,
            high,
            expected_source_key=expected_spk_key,
        )
    else:
        result = analytic_solar.longitude_crossing_tt(
            float(SOLAR_TERM_LONGITUDES[term_index]), low, high
        )
    selected_parts = result.get("tt_parts")
    if selected_parts is not None:
        point = TTInstant.from_parts(*selected_parts)
    else:
        # A numerical root is an IEEE point, not a rounded UTC-label encoding.
        point = TTInstant.from_float(result["jd_tt"])
    civil_point = time_scales.utc_point_from_tt(point)
    civil = civil_point.as_calendar()
    clock_policy = solar_term_clock.native_solar_root_time_policy(civil)
    details = {
        **result["model"],
        "root_bracket_tt": (
            [sum(parts) for parts in result["tt_bracket_parts"]]
            if selected_parts is not None
            else result["bracket_tt"]
        ),
        "root_bracket_seconds": result["bracket_seconds"],
        "root_time_scale": "TT",
        "native_choice_probe_model": None,
        "native_choice_probe_retflags": [],
        "selected_crossing_jd_tt": result["jd_tt"],
        "native_choice_probe_jd_tt": None,
        "native_choice_probe_datetime_utc": None,
        "selected_minus_native_seconds_tt": None,
        "numerical_resolution_is_physical_accuracy": False,
        "civil_time_method": clock_policy["civil_time_policy"],
        "historical_ut1_convention": clock_policy["historical_ut1_convention"],
        "future_leap_seconds_assumed_unchanged": clock_policy[
            "future_leap_seconds_assumed_unchanged"
        ],
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
        "resolved_tt_instant": point,
        "resolved_civil_point": civil_point,
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
) -> tuple[SolarTerm, ...]:
    """Cache a year only within the same selected data-file environment."""
    if not 1 <= year <= 9999:
        raise ValueError("Solar year grids require a civil year from1 through9999")
    else:
        pass
    return _solar_terms_for_context_year(year, timezone_name, year)


def get_solar_term(
    year: int, name: str, timezone_name: str = DEFAULT_TIMEZONE
) -> SolarTerm:
    """Resolve a named term with the same source policy as the annual grid."""
    if not 1 <= year <= 9999:
        raise ValueError("Solar term queries require a civil year from 1 through 9999")
    else:
        pass
    (term,) = _solar_terms_for_context_year(
        year, timezone_name, year, term_index=SOLAR_TERM_NAMES.index(name)
    )
    return term


def _solar_terms_for_context_year(
    year: int,
    timezone_name: str,
    context_year: int,
    *,
    term_index: int | None = None,
) -> tuple[SolarTerm, ...]:
    # An in-range input needs neighbouring boundaries even at the two ends
    # of the software range. Select their model from that input's year, while
    # solving the actual adjacent year. This private allowance never extends
    # the standalone year-grid API or shares its out-of-range native cache.
    if year != context_year:

        low, high = solar_model_policy.solar_context_input_years(context_year)
        if not low <= context_year <= high or abs(year - context_year) != 1:
            raise ValueError("Adjacent solar boundaries require an in-range context")
        else:
            pass
    else:
        pass
    for _ in range(2):
        context = solar_term_cache_context(swe, year=context_year)
        try:
            terms = _get_solar_terms_for_year_cached(
                year, timezone_name, context, context_year, term_index=term_index
            )
        except _SolarTermEnvironmentChanged:
            _get_solar_terms_for_year_cached.cache_clear()
            continue
        if solar_term_cache_context(swe, year=context_year) == context:
            return tuple(
                replace(term, solar_model_details=deepcopy(term.solar_model_details))
                for term in terms
            )
        else:
            pass
        # A concurrent installer changed the files while the year was
        # computed. Discard it rather than reuse a potentially mixed year.
        _get_solar_terms_for_year_cached.cache_clear()
    raise RuntimeError("星历数据在节气求解期间持续变化，请待安装完成后重试")


@lru_cache(maxsize=128)
def _get_solar_terms_for_year_cached(
    year: int,
    timezone_name: str,
    _context: tuple[Any, ...],
    context_year: int,
    *,
    term_index: int | None = None,
) -> tuple[SolarTerm, ...]:
    # Lock the numerical work, not cache hits: restoring the Swiss path on
    # every hit would unnecessarily flush native ephemeris caches.
    with preserve_ephemeris_path():
        if solar_term_cache_context(swe, year=context_year) != _context:
            raise _SolarTermEnvironmentChanged()
        else:
            pass
        terms = _calculate_solar_terms_for_year(
            year, timezone_name, context_year=context_year, term_index=term_index
        )
        if solar_term_cache_context(swe, year=context_year) != _context:
            raise _SolarTermEnvironmentChanged()
        else:
            pass
        if any(not is_calculated_solar_term(t) for t in terms):
            raise EphemerisSourceError("solar_term_source_unverified")
        else:
            pass
        return terms


def _calculate_solar_terms_for_year(
    year: int,
    timezone_name: str,
    *,
    context_year: int | None = None,
    term_index: int | None = None,
) -> tuple[SolarTerm, ...]:
    tzinfo = parse_timezone_name(timezone_name or DEFAULT_TIMEZONE)
    terms: list[SolarTerm] = []
    model_year = year if context_year is None else context_year
    context = solar_term_cache_context(swe, year=model_year)

    indices = range(len(SOLAR_TERM_NAMES)) if term_index is None else (term_index,)
    for index in indices:
        term_name = SOLAR_TERM_NAMES[index]
        target_longitude = SOLAR_TERM_LONGITUDES[index]
        # A calendar anchor identifies the intended year/month; only a solved
        # longitude crossing may become a returned solar term.
        anchor_utc = _solar_term_search_anchor_utc(year, index)

        utc_moment: UTCCalendar | None = None
        provenance: SolarTermProvenance = {}

        # Select every crossing from the same captured source as its cache key.
        # Re-reading the environment here can observe A -> B -> A and cache a
        # mixed-source year even though the before/after contexts both say A.
        selected_mode = context[-1][0]
        explicit_vsop2013 = selected_mode == "vsop2013"
        explicit_spk = selected_mode == "spk"
        explicit_aa1996 = selected_mode == "aa1996"
        packaged_de440 = context[-1][1] in {
            de440_solar.MODEL_ID,
            de440_solar.EXTENDED_MODEL_ID,
        }
        if selected_mode == "analytic":
            utc_moment, provenance = _solar_term_utc_via_analytic(year, index)
            provider = "fatebridge_analytic"
        elif explicit_vsop2013:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, vsop2013=True, expected_vsop2013_key=context[-1][2]
            )
            provider = "vsop2013"
        elif explicit_aa1996:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, aa1996=True, expected_aa1996_key=context[-1][2]
            )
            provider = "moshier_aa1996"
        elif packaged_de440:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year,
                index,
                de440=True,
                de440_profile=solar_model_policy.de440_profile_for_year(model_year),
            )
            provider = "jpl_de440"
        elif explicit_spk:
            utc_moment, provenance = _solar_term_utc_via_analytic(
                year, index, spk=True, expected_spk_key=context[-1][2]
            )
            provider = "jpl_spk"
        else:
            utc_moment = _solar_term_utc_via_swe(
                year, float(target_longitude), anchor_utc, provenance
            )
            provider = "swisseph"
        if selected_mode == "swiss" and (
            utc_moment is None or provenance.get("ephemeris_model") != "swieph"
        ):
            raise EphemerisSourceError("solar_swiss_files_required")
        else:
            pass
        provider = provenance.get("resolution_provider", provider)
        if model_year != year and provenance.get("solar_model_details") is not None:

            provenance["solar_model_details"].update(
                adjacent_boundary_context_year=model_year,
                solar_model_input_years=list(
                    solar_model_policy.solar_context_input_years(model_year)
                ),
            )
        else:
            pass
        # Observe changes after each term as well as the whole year. Otherwise
        # a selector A -> B -> A between terms can leave a mixed cached year.
        # This does not certify native files were read atomically within a call.
        if solar_term_cache_context(swe, year=model_year) != context:
            raise _SolarTermEnvironmentChanged()
        else:
            pass

        if utc_moment is None:
            raise EphemerisSourceError("solar_native_unavailable")
        else:
            pass

        terms.append(
            SolarTerm(
                name=term_name,
                calendar=ZonedCalendar(utc_moment, tzinfo),
                source_grid_year=year,
                resolution_provider=provider,
                ephemeris_model=provenance.get("ephemeris_model", "unknown"),
                ephemeris_retflags=provenance.get("ephemeris_retflags", ()),
                ephemeris_library_version=provenance.get("ephemeris_library_version"),
                solar_model_details=provenance.get("solar_model_details"),
                tt_instant=provenance.get("resolved_tt_instant"),
                civil_point=provenance["resolved_civil_point"],
                utc_definition=(
                    utc_definition_evidence()
                    if provenance.get("resolved_tt_instant") is not None
                    else None
                ),
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


def _solar_term_source_year(year: int, context_year: int) -> int:
    """Preserve a neighbor's own profile unless it needs the boundary allowance."""

    low, high = solar_model_policy.solar_context_input_years(context_year)
    return (
        context_year
        if low <= context_year <= high and not low <= year <= high
        else year
    )


def get_solar_term_environment_key(*, year: int | None = None) -> tuple[Any, ...]:
    """Bind derived BaZi caches to the same environment as solar-term roots.

    This stat-based identity detects ordinary installations/provider changes;
    it is not a continuous byte-immutability or accuracy certificate.
    """
    if year is None:
        return solar_term_cache_context(swe)
    else:
        pass
    # Month boundaries read adjacent years too. Their selected source must
    # stay in the derived-cache identity even when the input year is outside.
    contexts = []
    for candidate in range(year - 1, year + 2):
        source_year = _solar_term_source_year(candidate, year)
        context = solar_term_cache_context(swe, year=source_year)
        if context not in contexts:
            contexts.append(context)
        else:
            pass
    if len(contexts) == 1:
        return contexts[0]
    else:
        pass
    return ("solar_adjacent_profile_contexts", tuple(contexts))


def get_jieqi_year_grid(
    year: int, timezone_name: str = DEFAULT_TIMEZONE
) -> list[dict[str, Any]]:
    return [item.as_dict() for item in get_solar_terms_for_year(year, timezone_name)]


def _term_window(moment: datetime, timezone_name: str) -> list[SolarTerm]:
    """Three complete annual cycles for consumers evaluating seasonal windows."""
    local_year = localize_datetime(moment, timezone_name).year
    window = [
        term
        for year in (local_year - 1, local_year, local_year + 1)
        for term in _solar_terms_for_context_year(
            year, timezone_name, _solar_term_source_year(year, local_year)
        )
    ]
    return sorted(window, key=lambda item: item.point.day)


def _adjacent_term_window(moment: datetime, timezone_name: str) -> list[SolarTerm]:
    """Bracket a local instant and Jie month without unrelated annual cycles."""
    local_moment = localize_datetime(moment, timezone_name)
    year = local_moment.year
    window = list(get_solar_terms_for_year(year, timezone_name))
    by_name = {term.name: term for term in window}
    key = utc_calendar(local_moment).julian_day_exact()
    # The current year already brackets ordinary dates. Only the December /
    # January endpoints can need adjacent-year boundaries; never solve two
    # unrelated full grids, especially at the civil-year representation ends.
    if key < by_name["小寒"].point.day:
        neighbor, indices = year - 1, (22, 23)
    elif key >= by_name["大雪"].point.day:
        neighbor, indices = year + 1, (0, 1)
    else:
        return window
    for index in indices:
        window.extend(
            _solar_terms_for_context_year(
                neighbor,
                timezone_name,
                _solar_term_source_year(neighbor, year),
                term_index=index,
            )
        )
    return sorted(window, key=lambda item: item.point.day)


def get_adjacent_solar_terms(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> tuple[SolarTerm, SolarTerm]:
    local_moment = localize_datetime(moment, timezone_name)
    key = utc_calendar(local_moment).julian_day_exact()
    previous = None
    upcoming = None

    for term in _adjacent_term_window(local_moment, timezone_name):
        if term.point.day <= key:
            previous = term
            continue
        else:
            pass
        upcoming = term
        break

    if previous is None or upcoming is None:
        raise ValueError("Unable to resolve neighbouring solar terms.")
    else:
        pass

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
        if utc_calendar(local_moment).julian_day_exact() >= li_chun.point.day
        else local_moment.year - 1
    )


def get_bazi_month_context(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> dict[str, object]:
    current_boundary, next_boundary, month_branch, month_index = (
        get_bazi_month_boundaries(moment, timezone_name)
    )
    local_moment = localize_datetime(moment, timezone_name)

    return {
        "branch": month_branch,
        "month_index": month_index,
        "comparison_datetime": local_moment.isoformat(),
        "elapsed_basis": "utc_instant_seconds",
        "elapsed_seconds_since_start": elapsed_seconds_between(
            current_boundary.point, local_moment
        ),
        "elapsed_seconds_until_next": elapsed_seconds_between(
            local_moment, next_boundary.point
        ),
        "start_term": current_boundary.as_dict(),
        "next_term": next_boundary.as_dict(),
        "days_since_start": round(
            elapsed_days_between(current_boundary.point, local_moment), 4
        ),
        "days_until_next": round(
            elapsed_days_between(local_moment, next_boundary.point), 4
        ),
    }


def get_bazi_month_boundaries(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> tuple[SolarTerm, SolarTerm, str, int]:
    current_boundary, next_boundary = get_jie_boundaries(moment, timezone_name)
    require_calculated_solar_term(current_boundary)
    require_calculated_solar_term(next_boundary)
    month_branch = BAZI_MONTH_START_TERMS[current_boundary.name]
    month_index = BAZI_MONTH_SEQUENCE.index(month_branch)
    return current_boundary, next_boundary, month_branch, month_index


def get_jie_boundaries(
    moment: datetime, timezone_name: str = DEFAULT_TIMEZONE
) -> tuple[SolarTerm, SolarTerm]:
    """Bracket the instant with the two sectional solar terms."""
    local_moment = localize_datetime(moment, timezone_name)
    key = utc_calendar(local_moment).julian_day_exact()
    current_boundary = None
    for term in _adjacent_term_window(local_moment, timezone_name):
        if term.name not in BAZI_MONTH_START_TERMS:
            continue
        else:
            pass
        if term.point.day <= key:
            current_boundary = term
        elif current_boundary is not None:
            return current_boundary, term
        else:
            break
    raise ValueError("Unable to resolve BaZi month boundary.")


def _format_lunar_year(year: int) -> str:
    digits = "零一二三四五六七八九"
    return "".join(digits[int(char)] for char in str(year))


def _lunar_supplement_source(solar_date: date) -> dict[str, str] | None:
    return _prefix_lunar_source(solar_date) or _later_lunar_source(solar_date)


def _lunar_supported_range_payload() -> dict[str, str]:
    return {
        "start": LUNAR_SUPPORTED_SOLAR_START.isoformat(),
        "end": LUNAR_SUPPORTED_SOLAR_END.isoformat(),
    }


def lunar_supported_range_message() -> str:
    return (
        f"离线农历换算仅支持公历 {LUNAR_SUPPORTED_SOLAR_START.isoformat()} "
        f"至 {LUNAR_SUPPORTED_SOLAR_END.isoformat()}。"
    )


def _safe_lunar_date_from_solar(solar_date: date) -> _LunarDateValue | None:
    if LunarDate is None:
        return None
    else:
        pass

    if (
        solar_date < LUNAR_SUPPORTED_SOLAR_START
        or solar_date > LUNAR_SUPPORTED_SOLAR_END
    ):
        return None
    else:
        pass

    try:
        lunar = _lunar_date_from_solar(solar_date)
    except ValueError:
        return None

    return lunar


def get_lunar_context(
    moment: datetime | NominalClockLabel,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    pillars: dict[str, tuple[str, str]] | None = None,
    civil_datetime: datetime | None = None,
) -> dict[str, object] | None:
    if isinstance(moment, datetime):
        label = NominalClockLabel.from_local_datetime(
            localize_datetime(moment, timezone_name)
        )
        civil_input = civil_datetime if civil_datetime is not None else moment
    else:
        label = moment
        if civil_datetime is None:
            raise ValueError("名义钟表标签须另附真实民用时刻，不能反推交节瞬间")
        else:
            pass
        civil_input = civil_datetime
    # Check the source domain before materializing a bounded Gregorian date.
    if not (
        LUNAR_SUPPORTED_SOLAR_START.toordinal()
        <= label.ordinal
        <= LUNAR_SUPPORTED_SOLAR_END.toordinal()
    ):
        return None
    else:
        pass
    solar_date = date.fromordinal(label.ordinal)
    lunar = _safe_lunar_date_from_solar(solar_date)
    if lunar is None:
        return None
    else:
        pass

    seasonal_moment = localize_datetime(civil_input, timezone_name)
    previous_term, next_term = get_adjacent_solar_terms(seasonal_moment, timezone_name)
    context: dict[str, object] = {
        "solar_datetime": label.isoformat(sep=" "),
        "timezone": timezone_name,
        "birth": label.isoformat(sep=" "),
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
        "jiedelta": previous_term.local_day_delta_label(seasonal_moment.toordinal()),
        "previous_jieqi": previous_term.as_dict(),
        "next_jieqi": next_term.as_dict(),
        "days_until_next_jieqi": round(
            elapsed_days_between(seasonal_moment, next_term.point), 4
        ),
    }

    conversion_source = _lunar_supplement_source(solar_date)
    if conversion_source is not None:
        context["conversion_source"] = conversion_source
    else:
        pass

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
            hour_branch=ZHI[((label.time_parts[0] + 1) // 2) % 12],
        )
    else:
        pass

    return context


def build_calendar_context(
    moment: datetime | NominalClockLabel,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    pillars: dict[str, tuple[str, str]] | None = None,
    civil_datetime: datetime | None = None,
    adjacent_terms: tuple[SolarTerm, SolarTerm] | None = None,
) -> dict[str, Any]:
    """Keep lunar/day clocks while resolving seasonal boundaries at the civil instant."""
    if isinstance(moment, datetime):
        label = NominalClockLabel.from_local_datetime(
            localize_datetime(moment, timezone_name)
        )
        civil_input = civil_datetime if civil_datetime is not None else moment
    else:
        label = moment
        if civil_datetime is None:
            raise ValueError("名义钟表标签须另附真实民用时刻，不能反推交节瞬间")
        else:
            pass
        civil_input = civil_datetime
    seasonal_moment = localize_datetime(civil_input, timezone_name)
    previous_term, next_term = (
        adjacent_terms
        if adjacent_terms is not None
        else get_adjacent_solar_terms(seasonal_moment, timezone_name)
    )
    require_calculated_solar_term(previous_term)
    require_calculated_solar_term(next_term)
    month_context = get_bazi_month_context(seasonal_moment, timezone_name)
    lunar_context = get_lunar_context(
        label,
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
    else:
        pass

    return {
        "timezone": timezone_name,
        # Use the same fractional civil clock consumed by term comparisons.
        # Truncation here makes opposite sides of a boundary print identically.
        "solar_datetime": label.isoformat(sep=" "),
        "current_solar_term": previous_term.as_dict(),
        "next_solar_term": next_term.as_dict(),
        "solar_term_delta": {
            "days_since_current": round(
                elapsed_days_between(previous_term.point, seasonal_moment), 4
            ),
            "days_until_next": round(
                elapsed_days_between(seasonal_moment, next_term.point), 4
            ),
            "description": previous_term.local_day_delta_label(
                seasonal_moment.toordinal()
            ),
        },
        "bazi_month_boundary": month_context,
        "lunar_calendar": lunar_context,
        "lunar_calendar_support": lunar_support,
    }
