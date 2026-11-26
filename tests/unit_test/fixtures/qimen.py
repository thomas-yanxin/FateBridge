"""Qimen clock and fixed-geometry test inputs."""

from datetime import datetime
from typing import Any, TypedDict

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics import qimen as engine
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.utils.civil_time import NominalClockLabel


class FixedBoardCase(TypedDict):
    dun: str
    ju: int
    hour: str


def seed(
    hour: str = "甲子",
    day: str = "甲子",
    month: str = "丙寅",
    moment: datetime = datetime(2026, 1, 1, 12),
) -> MetaphysicsSeed:
    civil = localize_datetime(moment, "Asia/Shanghai")
    return MetaphysicsSeed(
        input_datetime=civil,
        clock=NominalClockLabel.from_local_datetime(civil),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0.0,
        pillars={
            pillar_name: (ganzhi[0], ganzhi[1])
            for pillar_name, ganzhi in {
                "year": "乙巳",
                "month": month,
                "day": day,
                "hour": hour,
            }.items()
        },
        calendar_context={"current_solar_term": {"name": "冬至"}},
        input_offset_visible=False,
    )


def fixed_board(
    monkeypatch: pytest.MonkeyPatch,
    case: FixedBoardCase,
    day: str = "甲子",
    month: str = "丙寅",
    **options: str,
) -> dict[str, Any]:
    monkeypatch.setattr(
        engine,
        "_qimen_resolve_zhirun_meta",
        lambda **kwargs: {
            "current_term": "冬至" if case["dun"] == "阳遁" else "夏至",
            "dun_type": case["dun"],
            "yuan": "上元",
            "ju_number": case["ju"],
        },
    )
    return engine.build_qimen_board(seed(case["hour"], day, month), **options)


def calculate_january_board(day: int, hour: int) -> dict[str, Any]:
    return calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=day,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
