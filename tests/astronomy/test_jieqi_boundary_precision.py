"""两个远离交节瞬间的年、月柱回归，防止按整日切换。

本测试只检查指定生时仍在交节之前；不直接比较节气秒数，也不认证所选后端
的物理精度。后端由实际配置选择，不能把历史 swisseph 锚点描述成当前唯一来源。

两个锚点（北京时 +08:00，节气瞬时由 swisseph 反解）：

  1) 立春1972 = 1972-02-05 01:20（北京时）。
     生于 1972-02-04 23:00 仍在立春之前 → 年柱应为立春前的「辛亥」(1971)。
     粗粒度引擎把 23:00 滚到次日 02-05 再按「立春日」判年，误得「壬子」。

  2) 小暑1936 = 1936-07-07 15:58（北京时）。
     生于 1936-07-07 05:05 早于小暑约 11 小时 → 月柱应为小暑前的午月「甲午」。
     粗粒度引擎误置于未月「乙未」。

两个锚点有约2.3小时／11小时时间余量，不能用其通过结果推断秒级精度。
"""

from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.utils.birth_input import create_person_info


def _pillars(year, month, day, hour, minute):
    person = create_person_info(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        name="边界",
        gender="男",
        birth_place="北京",
        birth_timezone="Asia/Shanghai",
        # 用民用时排盘，使断言只考察「节气瞬时 vs 生时」这一边界，不掺入真太阳时位移。
        use_true_solar_time=False,
    )
    four = calculate_bazi_birth(person)["bazi_birth"]["four_pillars"]
    return {key: value["stem"] + value["branch"] for key, value in four.items()}


def test_year_pillar_uses_true_lichun_instant_not_civil_date():
    """1972-02-04 23:00：立春(02-05 01:20)之前，年柱必须是「辛亥」而非「壬子」。"""
    pillars = _pillars(1972, 2, 4, 23, 0)
    assert pillars["year"] == "辛亥"
    assert pillars["month"] == "辛丑"  # 立春前仍属丑月


def test_month_pillar_uses_true_xiaoshu_instant_not_civil_date():
    """1936-07-07 05:05：小暑(07-07 15:58)之前约 11 小时，月柱必须是午月「甲午」。"""
    pillars = _pillars(1936, 7, 7, 5, 5)
    assert pillars["month"] == "甲午"
