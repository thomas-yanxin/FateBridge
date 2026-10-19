"""Solar-clock corrections retain physical direction and timezone consistency."""

from datetime import datetime

import fatebridge.services.bazi as bazi
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    calculate_solar_time_adjustment,
)


def test_longitude_only_strategy_sign_matches_physics() -> None:
    """At Shanghai's +08 meridian (120°E), 130°E sits 10° east; true solar
    time must run AHEAD of the wall clock. The longitude-only strategy
    used to flip this, pushing eastern longitudes backward."""
    moment = datetime(2024, 6, 21, 14, 30)
    tz = "Asia/Shanghai"

    east = calculate_solar_time_adjustment(
        moment, tz, 130.0, strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    west = calculate_solar_time_adjustment(
        moment, tz, 100.0, strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    same_east = calculate_solar_time_adjustment(
        moment, tz, 130.0, strategy=SOLAR_TIME_STRATEGY_APPARENT
    )

    # 4 minutes per degree: 10° * 4 = 40 min.
    assert east["total_correction_minutes"] == 40.0
    assert west["total_correction_minutes"] == -80.0
    # Both strategies must agree in sign (apparent adds the equation-of-time
    # term, so magnitudes differ by a few minutes but direction must match).
    assert (east["total_correction_minutes"] > 0) == (
        same_east["total_correction_minutes"] > 0
    )


def test_longitude_only_true_solar_matches_explicit_timezone():
    """A western longitude without a timezone must not use Asia/Shanghai's meridian."""
    implicit = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "未提供",
        birth_longitude=-74.0,
        use_true_solar_time=True,
    )
    explicit = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "未提供",
        birth_longitude=-74.0,
        birth_timezone="America/New_York",
        use_true_solar_time=True,
    )
    pi = bazi.calculate_bazi_birth(implicit)["bazi_birth"]["four_pillars"]
    pe = bazi.calculate_bazi_birth(explicit)["bazi_birth"]["four_pillars"]
    assert pi["day"] == pe["day"]
    assert pi["hour"] == pe["hour"]


def test_china_longitude_keeps_expected_day_pillar():
    p = create_person_info(
        1990,
        5,
        20,
        10,
        "t",
        "男",
        "北京",
        birth_longitude=116.4,
        use_true_solar_time=True,
    )
    day = bazi.calculate_bazi_birth(p)["bazi_birth"]["four_pillars"]["day"]
    assert day == {"stem": "乙", "branch": "酉"}
