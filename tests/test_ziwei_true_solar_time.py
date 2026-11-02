"""紫微斗数真太阳时口径回归：命盘校正须含均时差（APPARENT），与八字一致。

此前 ``_build_person_seed`` 用 LONGITUDE_ONLY（仅经度差、不含均时差），同一出生
时间在八字与紫微下的校正结果相差一个均时差量（最大约 ±16 分钟），跨体系合参时
会在时辰边界附近落入不同的 hour pillar。真太阳时的严格定义本就含均时差，故紫微
统一到 APPARENT。

均时差由共享天文算法按输入所代表的 UTC 时刻计算；本测试检查两条实际计算
路径的一致性，不把一致性或秒级显示当成天文精度认证。
"""

from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    normalize_birth_time,
)

# 12 月 10 日的均时差量级显著（约 +6 分钟），APPARENT 与 LONGITUDE_ONLY 两口径
# 的校正结果明显不同——正是促成紫微与八字统一口径的那条差异。
_PERSON = PersonInfo(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    gender="男",
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.47,
    use_true_solar_time=True,
)


def test_ziwei_natal_correction_includes_equation_of_time():
    apparent = normalize_birth_time(
        _PERSON, solar_time_strategy=SOLAR_TIME_STRATEGY_APPARENT
    )
    longitude_only = normalize_birth_time(
        _PERSON, solar_time_strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    # 守护断言：所选日期的均时差非零，两口径确实分叉，否则本测试无意义。
    assert apparent.corrected_datetime != longitude_only.corrected_datetime

    result = calculate_ziwei_birth(_PERSON)
    corrected = result["analysis_context"]["corrected_datetime"]

    # 紫微命盘校正后的时间须等于八字所用的 APPARENT 口径（经度差 + 均时差），
    # 不再是旧的 LONGITUDE_ONLY 值。
    assert corrected == apparent.corrected_datetime.strftime("%Y-%m-%d %H:%M:%S")
    assert corrected != longitude_only.corrected_datetime.strftime("%Y-%m-%d %H:%M:%S")
