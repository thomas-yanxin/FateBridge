"""Source Shoushi lower-reckoning winter solar position, in equatorial du.

Yuan Shi 54 supplies the recipe and fixed measured equatorial mansion table.
Gujin lvli kao 43 independently works elapsed year 318 through the same
remainder (310.1467) and 箕 5.0392. This is neither a modern solar longitude nor
a full redating of all mansion widths. The changed remainder period and the
fixed reference table circle are disclosed separately rather than normalized.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from fatebridge.core.guolao_classical import MANSIONS, SHOUSHI_EQUATORIAL_1281
from fatebridge.core.guolao_historical import shoushi_winter_cycle

SOURCE_URL = "https://commons.wikimedia.org/w/index.php?title=File:NLC892-312002017339-363669_二十四史_第166冊.pdf&oldid=1270279566"
LOCATOR = "元史卷54·步日躔·推冬至赤道日度、赤道宿度；NLC166 PDF第55页"
ZHOUYING_DU = Fraction("315.1075")


def shoushi_winter_sun(elapsed_years: int) -> dict[str, Any]:
    """Explicit nonnegative source 距算; never infer a civil year or date.

    Whole centuries shorten 岁实 (in the shared 中积 recipe) and lengthen the
    remainder 周天 by 1/10000 du. 周应 is an angle here, despite the source
    assigning the same numerical representation to 中积's 日 and 度.
    The final mansion reduction uses the named *fixed* equatorial table.
    """
    cycle = shoushi_winter_cycle(elapsed_years)
    table = SHOUSHI_EQUATORIAL_1281
    centuries = elapsed_years // 100
    period = table.circle_du + Fraction(centuries, 10000)
    # 源算命日曰度 is a numerical convention, not a physical units conversion.
    total = cycle.zhongji_days + ZHOUYING_DU
    revolutions = total // period
    remainder = total - revolutions * period
    origin = sum(table.widths_du[: MANSIONS.index("虚")], Fraction()) + 6
    angle = (origin + remainder) % table.circle_du
    mansion, degree = table.locate(angle)
    return {
        "method": "shoushi_lower_reckoning_fixed_equatorial_reference_v1",
        "source_url": SOURCE_URL,
        "locator": LOCATOR,
        "mansion_table_id": table.source_id,
        "coordinate_frame": table.coordinate_frame,
        "coordinate_unit": "historical_du_not_modern_degrees",
        "elapsed_years": elapsed_years,
        "whole_centuries": centuries,
        "effective_year_days_exact": str(cycle.effective_year_days),
        "zhongji_days_exact": str(cycle.zhongji_days),
        "zhongji_numerically_reused_as_du": True,
        "zhouying_du_exact": str(ZHOUYING_DU),
        "accumulated_du_exact": str(total),
        "remainder_period_du_exact": str(period),
        "complete_revolutions": revolutions,
        "remainder_from_xu6_du_exact": str(remainder),
        "mansion_reference_circle_du_exact": str(table.circle_du),
        "mansion_widths_redated": False,
        "period_minus_reference_circle_du_exact": str(period - table.circle_du),
        "origin_mansion": "虚",
        "origin_degree_du_exact": "6",
        "angle_from_jiao_du_exact": str(angle),
        "mansion": mansion,
        "degree_in_mansion_du_exact": str(degree),
        "winter_sexagenary_day": cycle.winter_sexagenary_day,
        "winter_fraction_of_day_exact": str(cycle.winter_fraction_of_day),
        "modern_right_ascension": None,
        "modern_longitude": None,
        "modern_calendar_date_assigned": False,
        "modern_epoch_calibrated": False,
        "life_degree_accepted": False,
        "used_in_native_birth_chart": False,
        "limitations": [
            "仅复算非负距算的原历下算，不代替实际太阳位置或负距算上考",
            "回显变动周天与固定赤道宿表，不把固定宿宽冒充逐年重测或重算宿宽",
            "黄赤道率另有具名四列复算；完整六列表、逐年宿度、古今历元或命度映射未完成",
        ],
    }
