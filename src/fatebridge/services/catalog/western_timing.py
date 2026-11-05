"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import Any, List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_timing import (
    WesternTimingModuleRequest,
    WesternTimingRequest,
)

calculate_western_timing_analysis = lazy_service(
    "fatebridge.services.western_timing", "calculate_western_timing_analysis"
)


calculate_decennials = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_decennials"
)


calculate_firdaria = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_firdaria"
)


calculate_givenyear = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_givenyear"
)


calculate_lunarreturn = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_lunarreturn"
)


calculate_pd = lazy_service("fatebridge.services.western_timing_tools", "calculate_pd")


calculate_pdchart = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_pdchart"
)


calculate_profection = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_profection"
)


calculate_solararc = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_solararc"
)


calculate_solarreturn = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_solarreturn"
)


calculate_transit = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_transit"
)


calculate_zr = lazy_service("fatebridge.services.western_timing_tools", "calculate_zr")


def _western_module_spec(name: str, service: Any, label: str) -> ToolSpec:
    return ToolSpec(
        key=name,
        bind=raw_invoke(service),
        request_model=WesternTimingModuleRequest,
        summary=(
            f"{label}：西占行运的单项技法，读取本命盘+目标时刻只算这一种。"
            f"想一次拿到多项行运的整合结果，改用聚合工具 western_timing_analysis。"
            "（本族 11 个西占时运工具共用 WesternTimingModuleRequest，"
            "schema 中部分参数仅对特定技法生效，与本工具无关的可忽略。）"
        ),
        operation_label_zh=label,
        family="western_timing_tool",
        cpu_bound=True,
        rest_path=f"/api/astro/timing/{name}",
        mcp_name=name,
    )


SPECS: List[ToolSpec] = [
    ToolSpec(
        key="western_timing_analysis",
        bind=raw_invoke(calculate_western_timing_analysis),
        request_model=WesternTimingRequest,
        summary=(
            "西占预测时运的聚合分析：一次整合多种行运技法（返照/行运/太阳弧/小限/法达等）；"
            "只要单一技法请用对应的 solarreturn/transit/… 工具。"
        ),
        operation_label_zh="西占时运",
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astro/timing",
        mcp_name="western_timing_analysis",
    ),
    # --- Western timing modules -------------------------------------------
    _western_module_spec("solarreturn", calculate_solarreturn, "西占太阳返照"),
    _western_module_spec("lunarreturn", calculate_lunarreturn, "西占月亮返照"),
    _western_module_spec("transit", calculate_transit, "西占行运盘"),
    _western_module_spec("solararc", calculate_solararc, "西占太阳弧"),
    _western_module_spec("givenyear", calculate_givenyear, "西占指定年盘"),
    _western_module_spec("profection", calculate_profection, "西占年小限"),
    _western_module_spec("pd", calculate_pd, "西占主限"),
    _western_module_spec("pdchart", calculate_pdchart, "西占主限法盘"),
    _western_module_spec("zr", calculate_zr, "西占黄道释放"),
    _western_module_spec("firdaria", calculate_firdaria, "西占法达星限"),
    _western_module_spec("decennials", calculate_decennials, "西占十年星限"),
]
