"""BaZi calendar conversion, zi-hour policies, three origins, twelve stages, and month duty."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from fatebridge.core.almanac import (
    DEFAULT_TIMEZONE,
    get_bazi_month_context,
    get_bazi_year,
    get_day_ganzhi,
    get_solar_term_environment_key,
    localize_datetime,
)
from fatebridge.utils.civil_time import (
    NominalClockLabel,
    ZonedCalendar,
    gregorian_date_parts,
    gregorian_ordinal,
)
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_HIDDEN_STEMS,
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    STEM_COMBINATIONS,
    get_hour_branch,
    get_nayin,
    get_ten_god,
)

LATE_ZI_HOUR = 23  # 23:00-23:59 属晚子时 / 夜子时

ZiHourPolicy = Literal[
    "day_rollover_at_23",
    "night_zi_same_day_next_hour_stem",
    "night_zi_same_day_same_hour_stem",
]
ZI_HOUR_POLICIES: tuple[ZiHourPolicy, ...] = (
    "day_rollover_at_23",
    "night_zi_same_day_next_hour_stem",
    "night_zi_same_day_same_hour_stem",
)

ChangshengSchool = Literal[
    "fire_earth_same_palace",
    "water_earth_same_palace",
    "five_element_same_stage",
]
CHANGSHENG_SCHOOLS: tuple[ChangshengSchool, ...] = (
    "fire_earth_same_palace",
    "water_earth_same_palace",
    "five_element_same_stage",
)

DutyProfile = Literal["sanming", "yuanhai", "6tail", "ditian"]
DUTY_PROFILES: tuple[DutyProfile, ...] = ("sanming", "yuanhai", "6tail", "ditian")

TWELVE_STAGES: tuple[str, ...] = (
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
)

_CHANGSHENG_TABLES: dict[str, dict[str, tuple[str, int]]] = {
    "fire_earth_same_palace": {
        "甲": ("亥", +1),
        "丙": ("寅", +1),
        "戊": ("寅", +1),
        "庚": ("巳", +1),
        "壬": ("申", +1),
        "乙": ("午", -1),
        "丁": ("酉", -1),
        "己": ("酉", -1),
        "辛": ("子", -1),
        "癸": ("卯", -1),
    },
    "water_earth_same_palace": {
        "甲": ("亥", +1),
        "丙": ("寅", +1),
        "戊": ("申", +1),
        "庚": ("巳", +1),
        "壬": ("申", +1),
        "乙": ("午", -1),
        "丁": ("酉", -1),
        "己": ("卯", -1),
        "辛": ("子", -1),
        "癸": ("卯", -1),
    },
    "five_element_same_stage": {
        "甲": ("亥", +1),
        "乙": ("亥", +1),
        "丙": ("寅", +1),
        "丁": ("寅", +1),
        "戊": ("寅", +1),
        "己": ("寅", +1),
        "庚": ("巳", +1),
        "辛": ("巳", +1),
        "壬": ("申", +1),
        "癸": ("申", +1),
    },
}

CHANGSHENG_START = _CHANGSHENG_TABLES["fire_earth_same_palace"]
LU_SEATS = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
YANG_BLADE_SEATS = dict(zip("甲丙戊庚壬", "卯午午酉子"))
STAGE_PROFILE_ID = "ten_stem_yang_forward_yin_reverse_fire_earth_v1"

# 人元司令分野 (30-day nominal schedules per month branch)
MONTH_DUTY_SCHEDULES: dict[str, dict[str, tuple[tuple[str, int], ...]]] = {
    "sanming": {
        "寅": (("戊", 5), ("丙", 5), ("甲", 20)),
        "卯": (("甲", 7), ("乙", 23)),
        "辰": (("乙", 7), ("壬", 5), ("戊", 18)),
        "巳": (("戊", 7), ("庚", 5), ("丙", 18)),
        "午": (("丙", 7), ("丁", 23)),
        "未": (("丁", 7), ("甲", 5), ("己", 18)),
        "申": (("戊", 5), ("壬", 5), ("庚", 20)),
        "酉": (("庚", 7), ("辛", 23)),
        "戌": (("辛", 7), ("丙", 5), ("戊", 18)),
        "亥": (("戊", 5), ("甲", 5), ("壬", 20)),
        "子": (("壬", 7), ("癸", 23)),
        "丑": (("癸", 7), ("庚", 5), ("己", 18)),
    },
    "yuanhai": {
        "寅": (("戊", 7), ("丙", 7), ("甲", 16)),
        "卯": (("甲", 10), ("乙", 20)),
        "辰": (("乙", 9), ("癸", 3), ("戊", 18)),
        "巳": (("戊", 5), ("庚", 9), ("丙", 16)),
        "午": (("丙", 10), ("己", 9), ("丁", 11)),
        "未": (("丁", 9), ("乙", 3), ("己", 18)),
        "申": (("戊", 7), ("壬", 7), ("庚", 16)),
        "酉": (("庚", 10), ("辛", 20)),
        "戌": (("辛", 9), ("丁", 3), ("戊", 18)),
        "亥": (("戊", 7), ("甲", 5), ("壬", 18)),
        "子": (("壬", 10), ("癸", 20)),
        "丑": (("癸", 9), ("辛", 3), ("己", 18)),
    },
    "6tail": {
        "寅": (("戊", 7), ("丙", 7), ("甲", 16)),
        "卯": (("甲", 10), ("乙", 20)),
        "辰": (("乙", 9), ("癸", 3), ("戊", 18)),
        "巳": (("戊", 5), ("庚", 9), ("丙", 16)),
        "午": (("丙", 10), ("己", 9), ("丁", 11)),
        "未": (("丁", 9), ("乙", 3), ("己", 18)),
        "申": (("戊", 10), ("壬", 3), ("庚", 17)),
        "酉": (("庚", 10), ("辛", 20)),
        "戌": (("辛", 9), ("丁", 3), ("戊", 18)),
        "亥": (("戊", 7), ("甲", 5), ("壬", 18)),
        "子": (("壬", 10), ("癸", 20)),
        "丑": (("癸", 9), ("辛", 3), ("己", 18)),
    },
    "ditian": {
        "寅": (("戊", 7), ("丙", 5), ("甲", 18)),
        "卯": (("甲", 9), ("乙", 21)),
        "辰": (("乙", 9), ("癸", 3), ("戊", 18)),
        "巳": (("戊", 7), ("庚", 5), ("丙", 18)),
        "午": (("丙", 9), ("己", 3), ("丁", 18)),
        "未": (("丁", 7), ("乙", 5), ("己", 18)),
        "申": (("戊", 3), ("己", 7), ("壬", 3), ("庚", 17)),
        "酉": (("庚", 7), ("辛", 23)),
        "戌": (("辛", 7), ("丁", 5), ("戊", 18)),
        "亥": (("戊", 7), ("甲", 5), ("壬", 18)),
        "子": (("壬", 7), ("癸", 23)),
        "丑": (("癸", 7), ("辛", 5), ("己", 18)),
    },
}

_STEM_COMBINATION_PARTNER: dict[str, str] = {
    s: other for a, b, _ in STEM_COMBINATIONS for s, other in ((a, b), (b, a))
}

_MONTH_BRANCH_SEQUENCE = [
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

_PILLAR_LABELS = {
    "year": "年柱",
    "month": "月柱",
    "day": "日柱",
    "hour": "时柱",
    "taiyuan": "胎元",
    "minggong": "命宫",
    "shengong": "身宫",
    "taixi": "胎息",
}


def validate_zi_hour_policy(policy: str) -> ZiHourPolicy:
    if policy not in ZI_HOUR_POLICIES:
        raise ValueError(
            f"不支持的早晚子时规则: {policy!r}；可选 {', '.join(ZI_HOUR_POLICIES)}"
        )
    return policy  # type: ignore[return-value]


def resolve_bazi_effective_date(
    year: int,
    month: int,
    day: int,
    hour: int,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
) -> tuple[int, int, int]:
    """Resolve effective civil date for BaZi day pillar under selected zi-hour policy."""
    validate_zi_hour_policy(zi_hour_policy)
    if hour >= LATE_ZI_HOUR and zi_hour_policy == "day_rollover_at_23":
        return gregorian_date_parts(gregorian_ordinal(year, month, day) + 1)
    return year, month, day


def resolve_hour_stem_reference_date(
    year: int,
    month: int,
    day: int,
    hour: int,
    *,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
) -> tuple[int, int, int]:
    """Resolve which day stem anchors 五鼠遁 for hour stem under selected zi-hour policy."""
    validate_zi_hour_policy(zi_hour_policy)
    if hour >= LATE_ZI_HOUR and zi_hour_policy in {
        "day_rollover_at_23",
        "night_zi_same_day_next_hour_stem",
    }:
        return gregorian_date_parts(gregorian_ordinal(year, month, day) + 1)
    return year, month, day


class BaZiCalendar:
    """Resolve solar-boundary year/month pillars and policy-aware day/hour pillars."""

    BASE_YEAR = 1984

    @classmethod
    def calculate_year_pillar(cls, year: int) -> tuple[str, str]:
        year_offset = year - cls.BASE_YEAR
        return (
            HEAVENLY_STEMS[year_offset % len(HEAVENLY_STEMS)],
            EARTHLY_BRANCHES[year_offset % len(EARTHLY_BRANCHES)],
        )

    @classmethod
    def calculate_month_pillar_by_branch(
        cls, year: int, month_branch: str
    ) -> tuple[str, str]:
        month_index = _MONTH_BRANCH_SEQUENCE.index(month_branch)
        year_stem, _ = cls.calculate_year_pillar(year)
        year_stem_index = HEAVENLY_STEMS.index(year_stem)
        # 甲己年丙作首，乙庚年戊为头，丙辛年庚上起，丁壬年壬位流，戊癸年甲好求
        base_stem_index = ((year_stem_index % 5) * 2 + 2) % 10
        month_stem = HEAVENLY_STEMS[(base_stem_index + month_index) % 10]
        return month_stem, month_branch

    @classmethod
    def calculate_day_pillar(
        cls,
        year: int,
        month: int,
        day: int,
        *,
        hour: int | None = None,
        apply_late_zi_rollover: bool = True,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> tuple[str, str]:
        if hour is not None:
            effective_policy: ZiHourPolicy = (
                zi_hour_policy
                if apply_late_zi_rollover
                else "night_zi_same_day_same_hour_stem"
            )
            year, month, day = resolve_bazi_effective_date(
                year, month, day, hour, zi_hour_policy=effective_policy
            )
        day_ganzhi = get_day_ganzhi(year, month, day)
        return day_ganzhi[0], day_ganzhi[1]

    @classmethod
    def calculate_hour_pillar(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int,
        *,
        apply_late_zi_rollover: bool = True,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> tuple[str, str]:
        hour_branch = get_hour_branch(hour)
        effective_policy: ZiHourPolicy = (
            zi_hour_policy
            if apply_late_zi_rollover
            else "night_zi_same_day_same_hour_stem"
        )
        ref_year, ref_month, ref_day = resolve_hour_stem_reference_date(
            year, month, day, hour, zi_hour_policy=effective_policy
        )
        day_stem, _ = cls.calculate_day_pillar(ref_year, ref_month, ref_day)
        day_stem_index = HEAVENLY_STEMS.index(day_stem)
        # 甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途
        base_stem_index = (day_stem_index % 5) * 2
        hour_branch_index = EARTHLY_BRANCHES.index(hour_branch)
        hour_stem = HEAVENLY_STEMS[(base_stem_index + hour_branch_index) % 10]
        return hour_stem, hour_branch

    @classmethod
    @lru_cache(maxsize=2048)
    def _get_four_pillars_cached(
        cls,
        label: NominalClockLabel,
        civil_calendar: ZonedCalendar,
        timezone_name: str,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
        _solar_environment: tuple[Any, ...] = (),
    ) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]:
        year, month, day = label.date_parts
        hour = label.time_parts[0]
        civil_datetime = civil_calendar.require_datetime()
        bazi_year = get_bazi_year(civil_datetime, timezone_name)
        month_context = get_bazi_month_context(civil_datetime, timezone_name)
        month_branch = str(month_context["branch"])
        return (
            cls.calculate_year_pillar(bazi_year),
            cls.calculate_month_pillar_by_branch(bazi_year, month_branch),
            cls.calculate_day_pillar(
                year, month, day, hour=hour, zi_hour_policy=zi_hour_policy
            ),
            cls.calculate_hour_pillar(
                year, month, day, hour, zi_hour_policy=zi_hour_policy
            ),
        )

    @classmethod
    def get_four_pillars(
        cls,
        birth_datetime: datetime | NominalClockLabel,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        civil_datetime: datetime | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, tuple[str, str]]:
        validate_zi_hour_policy(zi_hour_policy)
        if isinstance(birth_datetime, datetime):
            label = NominalClockLabel.from_local_datetime(
                localize_datetime(birth_datetime, timezone_name)
            )
            civil_input = (
                civil_datetime if civil_datetime is not None else birth_datetime
            )
        else:
            label = birth_datetime
            if civil_datetime is None:
                raise ValueError("名义日时钟须另附真实民用时刻，不能反推年月交节")
            civil_input = civil_datetime
        civil = localize_datetime(civil_input, timezone_name)
        year_pillar, month_pillar, day_pillar, hour_pillar = (
            cls._get_four_pillars_cached(
                label,
                ZonedCalendar.from_datetime(civil),
                timezone_name,
                zi_hour_policy,
                get_solar_term_environment_key(year=civil.year),
            )
        )
        return {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "hour": hour_pillar,
        }


def twelve_life_stage(
    day_stem: str,
    branch: str,
    *,
    school: ChangshengSchool = "fire_earth_same_palace",
) -> str:
    """Lookup 十二长生 stage under the selected school convention."""
    table = _CHANGSHENG_TABLES.get(school)
    if table is None:
        raise ValueError(
            f"不支持的十二长生流派: {school!r}；可选 {', '.join(CHANGSHENG_SCHOOLS)}"
        )
    start_branch, direction = table[day_stem]
    steps = (
        (EARTHLY_BRANCHES.index(branch) - EARTHLY_BRANCHES.index(start_branch))
        * direction
    ) % 12
    return TWELVE_STAGES[steps]


def life_stages_for_pillars(
    pillars: dict[str, tuple[str, str]],
    *,
    school: ChangshengSchool = "fire_earth_same_palace",
) -> dict[str, str]:
    """Return day-master 十二长生 across year/month/day/hour branches."""
    day_stem = pillars["day"][0]
    return {
        pos: twelve_life_stage(day_stem, pillars[pos][1], school=school)
        for pos in ("year", "month", "day", "hour")
    }


def _cycle_stem(stem: str, steps: int) -> str:
    return HEAVENLY_STEMS[(HEAVENLY_STEMS.index(stem) + steps) % len(HEAVENLY_STEMS)]


def _palace_stem(year_stem: str, position: int) -> str:
    """五虎遁: 给定年干，取第 position 宫 (寅=1 … 丑=12) 的天干。"""
    year_gan_index = HEAVENLY_STEMS.index(year_stem)
    gan_index = (year_gan_index + 1) * 2 + position
    while gan_index > 10:
        gan_index -= 10
    return HEAVENLY_STEMS[gan_index - 1]


def _build_origin_payload(
    *, label_key: str, stem: str, branch: str, day_stem: str
) -> dict[str, Any]:
    return {
        "label": _PILLAR_LABELS[label_key],
        "stem": stem,
        "branch": branch,
        "pillar": f"{stem}{branch}",
        "nayin": get_nayin(stem, branch),
        "hidden_stems": BRANCH_HIDDEN_STEMS.get(branch, []),
        "ten_god": get_ten_god(day_stem, stem).value,
    }


def build_three_origins(
    pillars: dict[str, tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Compute 胎元, 命宫, 身宫."""
    year_stem = pillars["year"][0]
    month_stem, month_branch = pillars["month"]
    day_stem = pillars["day"][0]
    hour_branch = pillars["hour"][1]

    taiyuan = _build_origin_payload(
        label_key="taiyuan",
        stem=_cycle_stem(month_stem, 1),
        branch=EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(month_branch) + 3) % 12],
        day_stem=day_stem,
    )

    month_order = _MONTH_BRANCH_SEQUENCE.index(month_branch) + 1
    ming_hour_order = _MONTH_BRANCH_SEQUENCE.index(hour_branch) + 1
    ming_position = month_order + ming_hour_order
    ming_position = 26 - ming_position if ming_position >= 14 else 14 - ming_position
    ming_branch = _MONTH_BRANCH_SEQUENCE[ming_position - 1]
    ming_stem = _palace_stem(year_stem, ming_position)

    shen_hour_order = EARTHLY_BRANCHES.index(hour_branch) + 1
    shen_position = month_order + shen_hour_order
    if shen_position > 12:
        shen_position -= 12
    shen_branch = _MONTH_BRANCH_SEQUENCE[shen_position - 1]
    shen_stem = _palace_stem(year_stem, shen_position)

    return {
        "taiyuan": taiyuan,
        "minggong": _build_origin_payload(
            label_key="minggong", stem=ming_stem, branch=ming_branch, day_stem=day_stem
        ),
        "shengong": _build_origin_payload(
            label_key="shengong", stem=shen_stem, branch=shen_branch, day_stem=day_stem
        ),
    }


def build_taixi(pillars: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Compute 胎息 (day stem 五合 + day branch 六合)."""
    day_stem, day_branch = pillars["day"]
    return _build_origin_payload(
        label_key="taixi",
        stem=_STEM_COMBINATION_PARTNER[day_stem],
        branch=BRANCH_COMBINATIONS[day_branch],
        day_stem=day_stem,
    )


def resolve_month_duty(
    month_branch: str,
    elapsed_days_since_jie: float | None,
    *,
    day_stem: str | None = None,
    profile: DutyProfile = "sanming",
) -> dict[str, Any]:
    """Compute active 人元司令分野 stem from elapsed days since the Jie crossing."""
    schedules = MONTH_DUTY_SCHEDULES.get(profile)
    if schedules is None:
        raise ValueError(
            f"不支持的司令分野流派: {profile!r}；可选 {', '.join(DUTY_PROFILES)}"
        )
    entries = schedules[month_branch]
    schedule_rows = [
        {
            "stem": stem,
            "days": days,
            **({"ten_god": get_ten_god(day_stem, stem).value} if day_stem else {}),
        }
        for stem, days in entries
    ]
    if elapsed_days_since_jie is None:
        return {
            "status": "requires_birth_datetime",
            "rule_profile": profile,
            "month_branch": month_branch,
            "selected_stem": None,
            "ten_god": None,
            "schedule": schedule_rows,
        }

    elapsed = max(0.0, float(elapsed_days_since_jie))
    cursor = 0.0
    selected_stem = entries[-1][0]
    days_into_duty = 0.0
    remaining_days = 0.0
    for idx, (stem, duration) in enumerate(entries):
        end = cursor + duration
        if elapsed < end or idx == len(entries) - 1:
            selected_stem = stem
            days_into_duty = round(elapsed - cursor, 4)
            remaining_days = round(max(0.0, end - elapsed), 4)
            break
        cursor = end

    return {
        "status": "adjudicated",
        "rule_profile": profile,
        "month_branch": month_branch,
        "selected_stem": selected_stem,
        "ten_god": get_ten_god(day_stem, selected_stem).value if day_stem else None,
        "elapsed_days": round(elapsed, 4),
        "days_into_duty": days_into_duty,
        "remaining_days_in_duty": remaining_days,
        "schedule": schedule_rows,
    }
