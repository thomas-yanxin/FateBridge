"""Collated ordinal rules and exact historical coordinates, not an epoch fit.

The Lu Wei edition's image 9 supplies hour counting, its solstice exceptions,
the reverse twelve-palace order and small-limit counting. The caller must name
its solar-palace and hour-clock conventions: the text alone does not establish
their mapping from a modern civil instant. Life *degree* is a separate problem.

The Shoushi table below belongs to Yuan Shi 54, not a silent emendation of the
different figures printed in the Lu Wei edition. Its origin is 角初 in the
source coordinate system; no modern RA/ecliptic epoch anchor is supplied here.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
PALACES = (
    "命",
    "财帛",
    "兄弟",
    "田宅",
    "男女",
    "奴仆",
    "夫妻",
    "疾厄",
    "迁移",
    "官禄",
    "福德",
    "相貌",
)
MANSIONS = tuple("角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")
STEMS = "甲乙丙丁戊己庚辛壬癸"
# Lu Wei edition, bundle vols. 1-2 image 33: 天乙=昼贵, 玉堂=夜贵.
# 戊庚 share 丑 by day and 未 by night: do not swap an external table wholesale.
DAY_NOBLES = dict(zip(STEMS, "未申酉亥丑子丑寅卯巳"))
NIGHT_NOBLES = dict(zip(STEMS, "丑子亥酉未申未午巳卯"))


def _branch_index(branch: str) -> int:
    if len(branch) != 1 or branch not in BRANCHES:
        raise ValueError("须提供单个有效地支")
    return BRANCHES.index(branch)


def counting_anchor(solar_longitude: float) -> str:
    """Explicit modern term-instant interpretation of the edition's exceptions.

    冬至後到大寒日止 and 夏至日起到小暑日止 are mapped here to [270,300)
    and [90,105) tropical degrees. The day-inclusive historical endpoint and
    local sunrise convention are unresolved; this policy is not a textual fact.
    """
    if not math.isfinite(solar_longitude):
        raise ValueError("太阳黄经须有限")
    longitude = Fraction(solar_longitude) % 360
    if 270 <= longitude < 300:
        return "辰"
    if 90 <= longitude < 105:
        return "寅"
    return "卯"


def life_branch(sun_palace: str, birth_hour: str, anchor: str) -> str:
    """生时加太阳宫，顺数遇指定辰即命宫; explicit inputs, no ASC."""
    sun, hour, stop = map(_branch_index, (sun_palace, birth_hour, anchor))
    return BRANCHES[(sun + stop - hour) % 12]


def palace_branches(life: str) -> dict[str, str]:
    start = _branch_index(life)
    return {
        name: BRANCHES[(start - offset) % 12] for offset, name in enumerate(PALACES)
    }


def small_limit_branch(life: str, birth_year: str, target_year: str) -> str:
    """生年支加命宫，逆数至太岁; year-boundary policy belongs to caller."""
    start, birth, target = map(_branch_index, (life, birth_year, target_year))
    return BRANCHES[(start - (target - birth)) % 12]


def month_limit_branch(annual_branch: str, birth_month: int, target_month: int) -> str:
    """小限宮中起生月, reverse through twelve explicitly supplied month numbers.

    NIJL Lu Wei image 9: annual 戌, birth month 5 gives 6 酉, 7 申, ...,
    1 寅, 2 丑, 3 子, 4 亥. No Gregorian/month/闰 or year rule is inferred.
    """
    start = _branch_index(annual_branch)
    for month in (birth_month, target_month):
        if type(month) is not int or not 1 <= month <= 12:
            raise ValueError(
                "月限须显式提供1至12的整数月序，不以公历月份或闰月自动代入"
            )
    return BRANCHES[(start - (target_month - birth_month)) % 12]


def year_god_branches(year_stem: str, year_branch: str) -> dict[str, str]:
    """Source tables only; caller must declare its year-boundary convention.

    天贵/玉贵 are retained API aliases for 天乙/玉堂. 岁驾 is the birth-year
    branch itself (bundle vols. 1-2 image 34); this does not make the person a ruler.
    """
    if year_stem not in DAY_NOBLES:
        raise ValueError("须提供单个有效年干")
    _branch_index(year_branch)
    return {
        "天贵": DAY_NOBLES[year_stem],
        "玉贵": NIGHT_NOBLES[year_stem],
        "岁驾": year_branch,
    }


# 邢云路《古今律厯考》卷58: distinguish the printed cycle from the
# author's criticism of its rounding. No longitude epoch is fitted here.
PURPLE_SOURCE_PERIOD_DAYS = Fraction("10227.1792")
PURPLE_SOURCE_OFFSET_DAYS = Fraction("1256.5224")
PURPLE_SOURCE_DAYS_PER_DU = Fraction(28)


def purple_cycle_reference(zhongji_days: Fraction) -> dict[str, Fraction]:
    """Exact 至后策 from caller-supplied source 中积, not UTC/TT/JD.

    A corrected-period phase is an explicitly separate arithmetic experiment:
    it retains the transcribed offset, whose modern epoch is not calibrated.
    Neither phase may be relabelled modern longitude or a Lu Wei birth mansion.
    """
    if not isinstance(zhongji_days, Fraction):
        raise TypeError("中积须以Fraction明确提供原典日数，不接收现代儒略日浮点值")
    corrected_period = SHOUSHI_1281.circle_du * PURPLE_SOURCE_DAYS_PER_DU
    elapsed = zhongji_days + PURPLE_SOURCE_OFFSET_DAYS
    return {
        "published_phase_days": elapsed % PURPLE_SOURCE_PERIOD_DAYS,
        "corrected_period_experiment_phase_days": elapsed % corrected_period,
        "published_period_days": PURPLE_SOURCE_PERIOD_DAYS,
        "corrected_period_days": corrected_period,
        "rounding_discrepancy_days": corrected_period - PURPLE_SOURCE_PERIOD_DAYS,
    }


@dataclass(frozen=True)
class HistoricalMansions:
    source_id: str
    circle_du: Fraction
    widths_du: tuple[Fraction, ...]
    coordinate_frame: str = "unspecified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "widths_du", tuple(self.widths_du))
        if self.coordinate_frame not in {
            "unspecified",
            "source_equatorial",
            "source_ecliptic",
        }:
            raise ValueError("历史宿表须明确为原历赤道、原历黄道或未指定坐标系")
        if not isinstance(self.circle_du, Fraction) or any(
            not isinstance(width, Fraction) for width in self.widths_du
        ):
            raise TypeError("历史周天与宿宽须均以Fraction提供，不能混入浮点或隐式单位")
        if self.circle_du <= 0:
            raise ValueError("历史周天须为正")
        if len(self.widths_du) != 28 or any(w <= 0 for w in self.widths_du):
            raise ValueError("历史宿表须包含28个正宿宽")
        if sum(self.widths_du) != self.circle_du:
            raise ValueError("历史宿度未闭合，不能分摊残差或强制归一化")

    def locate(self, angle_from_jiao_du: Fraction) -> tuple[str, Fraction]:
        """Exact half-open source intervals; no physical epoch conversion."""
        if not isinstance(angle_from_jiao_du, Fraction):
            raise TypeError("历史坐标须以Fraction明确表示古度，不能混入现代浮点度")
        starts = [sum(self.widths_du[:i], Fraction()) for i in range(28)]
        angle = angle_from_jiao_du % self.circle_du
        index = bisect_right(starts, angle) - 1
        return MANSIONS[index], angle - starts[index]


# 元史卷054·步日躔第三: 周天365度25分75秒, 百分/度, 百秒/分.
# 虚九〈分空太〉 = 9 + 0.75/100 du, not 9.75 du or 9 du.
# The explicit four-quadrant subtotals independently close at 365.2575 du.
SHOUSHI_1281 = HistoricalMansions(
    source_id="yuanshi_054_shoushi_1281",
    coordinate_frame="source_ecliptic",
    circle_du=Fraction("365.2575"),
    widths_du=tuple(
        map(
            Fraction,
            (
                "12.87",
                "9.56",
                "16.40",
                "5.48",
                "6.27",
                "17.95",
                "9.59",
                "23.47",
                "6.90",
                "11.12",
                "9.0075",
                "15.95",
                "18.32",
                "9.34",
                "17.87",
                "12.36",
                "15.81",
                "11.08",
                "16.50",
                "0.05",
                "10.28",
                "31.03",
                "2.11",
                "13",
                "6.31",
                "17.79",
                "20.09",
                "18.75",
            ),
        )
    ),
)

# Yuan Shi 54, NLC166 PDF page 55: a separate measured equatorial table.
# Same circle and mansion names do not make these ecliptic widths. 虚 is
# 8.9575 du here, versus 9.0075 in the source ecliptic table above.
SHOUSHI_EQUATORIAL_1281 = HistoricalMansions(
    source_id="yuanshi_054_nlc166_equatorial_mansions",
    coordinate_frame="source_equatorial",
    circle_du=Fraction("365.2575"),
    widths_du=tuple(
        map(
            Fraction,
            (
                "12.10",
                "9.20",
                "16.30",
                "5.60",
                "6.50",
                "19.10",
                "10.40",
                "25.20",
                "7.20",
                "11.35",
                "8.9575",
                "15.40",
                "17.10",
                "8.60",
                "16.60",
                "11.80",
                "15.60",
                "11.30",
                "17.40",
                "0.05",
                "11.10",
                "33.30",
                "2.20",
                "13.30",
                "6.30",
                "17.25",
                "18.75",
                "17.30",
            ),
        )
    ),
)
