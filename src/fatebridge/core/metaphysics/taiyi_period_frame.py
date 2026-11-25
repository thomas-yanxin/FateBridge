"""Select the astronomical anchors and counters for Taiyi month and hour boards."""

from datetime import datetime
from typing import Any, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.almanac import (
    SolarTerm,
    _solar_terms_for_context_year,
    get_solar_terms_for_year,
    is_calculated_solar_term,
    localize_datetime,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.taiyi_clock import (
    nominal_clock_label,
    validate_seed_civil_clock,
)
from fatebridge.core.metaphysics.taiyi_geometry import BRANCHES
from fatebridge.core.metaphysics.taiyi_hour import (
    HOUR_PROFILES,
    KEY_HOUR_PROFILE,
    double_hour_slot,
    key_hour_origin,
)
from fatebridge.core.metaphysics.taiyi_month import (
    KEY_MONTH_PROFILE,
    MONTH_PROFILES,
    jinjing_month_origin,
    key_month_origin,
)
from fatebridge.core.solar_model_policy import solar_context_input_years
from fatebridge.utils.civil_time import NominalClockLabel, utc_calendar

JIE_ORDER = (
    "大雪",
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
)


class PeriodFrame(TypedDict):
    accumulation: int
    yin: bool
    ruler_branch: str
    anchor: SolarTerm
    cycle_year: NotRequired[int]
    month_offset: NotRequired[int]
    month_origin: NotRequired[dict[str, Any]]
    anchor_clock: NotRequired[NominalClockLabel]
    target_clock: NotRequired[NominalClockLabel]
    hour_origin: NotRequired[dict[str, Any]]
    winter_anchor: NotRequired[SolarTerm]


def previous_solar_term(instant: datetime, names: tuple[str, ...]) -> SolarTerm:
    """Compare retained civil points across year and timezone transitions."""
    instant_day = utc_calendar(instant).julian_day_exact()
    # note (coverage): Use the resolved civil year before UTC or apparent-solar clock conversion.
    context_year = instant.year
    low, high = solar_context_input_years(context_year)
    candidates: list[SolarTerm] = []
    for year in range(max(1, context_year - 1), min(9999, context_year + 1) + 1):
        terms = (
            _solar_terms_for_context_year(year, "UTC", context_year)
            if low <= context_year <= high and not low <= year <= high
            else get_solar_terms_for_year(year, "UTC")
        )
        candidates.extend(
            term
            for term in terms
            if term.name in names and term.point.day <= instant_day
        )
    if not candidates:
        raise ValueError("无法取得起盘之前的太乙节气锚点")
    else:
        pass
    term = max(candidates, key=lambda t: t.point.day)
    if not is_calculated_solar_term(term):
        raise ValueError("太乙月/日/时计要求天文节气实刻，不能使用线性近似回退")
    else:
        pass
    return term


def period_frame(
    seed: MetaphysicsSeed,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
) -> PeriodFrame:
    if month_profile is not None and (
        mode != "month"
        or not isinstance(month_profile, str)
        or month_profile not in MONTH_PROFILES
    ):
        raise ValueError("month_profile仅用于month，须选择已发布月计配置")
    else:
        pass
    if hour_profile is not None and (
        mode != "hour"
        or not isinstance(hour_profile, str)
        or hour_profile not in HOUR_PROFILES
    ):
        raise ValueError("hour_profile仅用于hour计法，须明确选择已发布时计配置")
    else:
        pass
    instant = localize_datetime(seed.input_datetime, seed.timezone)

    validate_seed_civil_clock(seed)
    if mode == "month":
        term = previous_solar_term(instant, JIE_ORDER)
        month_offset = JIE_ORDER.index(term.name)
        # Adapt vol.1's six year classes to the Gregorian year of 大雪.
        # This existing year-label choice is explicit in month_origin;
        # it does not adjudicate the source's 前十一月 wording.
        # January 小寒 belongs to the preceding 大雪-to-大雪 counting year.
        cycle_year = (
            term.calendar.utc.date_parts[0]
            if term.name == "大雪"
            else term.calendar.utc.date_parts[0] - int(term.name == "小寒")
        )
        if term.name not in ("大雪", "小寒"):
            cycle_year -= 1
        else:
            pass
        origin = jinjing_month_origin(cycle_year, month_offset)
        accumulation = origin["accumulation"]
        if month_profile == KEY_MONTH_PROFILE:
            origin = key_month_origin(cycle_year, month_offset)
            accumulation = origin["accumulation"]
        else:
            pass
        return {
            "accumulation": accumulation,
            "yin": False,
            "ruler_branch": BRANCHES[month_offset],
            "anchor": term,
            "cycle_year": cycle_year,
            "month_offset": month_offset,
            "month_origin": origin,
        }
    else:
        pass
    if mode != "hour":
        raise ValueError(
            "本节月/时计入口仅支持month/hour；其他计法请调用build_taiyi_board"
        )
    else:
        pass
    term = previous_solar_term(instant, ("冬至", "夏至"))
    anchor_clock = nominal_clock_label(term.calendar, seed)
    target_clock = nominal_clock_label(instant, seed)
    if hour_profile == KEY_HOUR_PROFILE:
        winter = previous_solar_term(instant, ("冬至",))
        origin = key_hour_origin(
            nominal_clock_label(winter.calendar, seed), target_clock
        )
        origin.update(
            winter_anchor_utc=winter.calendar.utc.isoformat(),
            winter_anchor_provider=winter.resolution_provider,
        )
        return {
            "accumulation": origin["accumulation"],
            "yin": term.name == "夏至",
            "ruler_branch": BRANCHES[double_hour_slot(target_clock) % 12],
            "anchor": term,
            "anchor_clock": anchor_clock,
            "target_clock": target_clock,
            "hour_origin": origin,
            "winter_anchor": winter,
        }
    else:
        pass
    accumulation = double_hour_slot(target_clock) - double_hour_slot(anchor_clock) + 1
    if accumulation < 1:
        raise ValueError("太乙时计的时钟序列早于所选至点，不能静默倒推")
    else:
        pass
    return {
        "accumulation": accumulation,
        "yin": term.name == "夏至",
        "ruler_branch": BRANCHES[double_hour_slot(target_clock) % 12],
        "anchor": term,
        "anchor_clock": anchor_clock,
        "target_clock": target_clock,
    }
