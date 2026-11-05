"""真太阳时默认值「对齐传统」回归锁。

传统约定：八字 / 紫微 / 数算(参评·河洛) / 式占(三式·六壬·奇门) 以真太阳时
（经度 + 均时差）定时辰 / 命宫 / 起局，故默认 ON；西方占星按出生地的钟表(时区)
时间起盘，故默认 OFF。

此前 FateBridge 的默认值恰好相反（西占 ON、其余 OFF）。本测试把「谁默认 ON、谁
默认 OFF」钉死在请求模型契约上——三端(REST/MCP/CLI)都从这些模型取默认值。

均时差为纯历法计算（不依赖星历），断言均为离散布尔/标量，跨平台确定，无需
golden 字节锁。
"""

from __future__ import annotations

import pytest

from fatebridge.core.requests.astrology import AstroChartRequest
from fatebridge.core.requests.bazi import BaziBirthRequest
from fatebridge.core.requests.birth import FateBridgeRequest
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest
from fatebridge.core.requests.divination import (
    CanpingRequest,
    HeluoRequest,
    SanShiUnitedRequest,
)
from fatebridge.core.requests.metaphysics import (
    LiuRengGodsRequest,
    QimenAnalysisRequest,
    ZiweiBirthRequest,
)

# 所有中式体系：缺省 use_true_solar_time 必须为 True。
_CHINESE_MODELS = [
    FateBridgeRequest,
    BaziBirthRequest,
    ZiweiBirthRequest,
    CanpingRequest,
    HeluoRequest,
    SanShiUnitedRequest,
    LiuRengGodsRequest,
    QimenAnalysisRequest,
]

_MIN_BIRTH = dict(birth_year=2000, birth_month=12, birth_day=10, birth_hour=9)


@pytest.mark.parametrize("model", _CHINESE_MODELS, ids=lambda m: m.__name__)
def test_chinese_models_default_true_solar_on(model: type) -> None:
    # Inspect the field default directly so the assertion does not depend on each
    # model's other required fields (date / analysis_* etc.).
    assert model.model_fields["use_true_solar_time"].default is True


def test_western_core_chart_defaults_true_solar_off() -> None:
    assert AstroChartRequest.model_fields["use_true_solar_time"].default is False
    # And end-to-end through construction (omitted flag stays off).
    req = AstroChartRequest(**_MIN_BIRTH, birth_place="上海")
    assert req.use_true_solar_time is False


def test_compatibility_both_persons_default_true_solar_on() -> None:
    req = TwoPersonCompatibilityRequest(
        person1_name="甲",
        person1_birth_year=1990,
        person1_birth_month=5,
        person1_birth_day=15,
        person1_birth_hour=10,
        person1_gender="男",
        person2_name="乙",
        person2_birth_year=1992,
        person2_birth_month=8,
        person2_birth_day=3,
        person2_birth_hour=14,
        person2_gender="女",
        relationship_type="marriage",
    )
    assert req.person1_use_true_solar_time is True
    assert req.person2_use_true_solar_time is True


def test_explicit_flags_override_default_both_directions() -> None:
    off = AstroChartRequest(**_MIN_BIRTH, birth_place="上海", use_true_solar_time=True)
    assert off.use_true_solar_time is True
    on = FateBridgeRequest(**_MIN_BIRTH, use_true_solar_time=False)
    assert on.use_true_solar_time is False
