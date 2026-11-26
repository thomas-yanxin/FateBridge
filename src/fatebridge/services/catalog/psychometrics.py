"""Psychometrics tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import (
    OutputContractError,
    ServiceResult,
    ToolSpec,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

calculate_ipip_big_five = service_ref(
    "fatebridge.services.psychometrics", "calculate_ipip_big_five"
)


def _validate_ipip_output(
    _spec: ToolSpec,
    result: ServiceResult,
    _request: BaseModel | None,
) -> None:
    mode = result.get("mode")
    if mode == "list_items":
        items = result.get("items")
        if not isinstance(items, list) or not items:
            raise OutputContractError("IPIP-50 list_items 输出缺少题项列表")
        return
    if mode == "score":
        domains = result.get("domains")
        if not isinstance(domains, dict) or len(domains) != 5:
            raise OutputContractError("IPIP-50 score 输出缺少完整五因子结果")
        return
    raise OutputContractError(f"IPIP-50 输出 mode 非法：{mode}")


def _compact_ipip_big_five(result: ServiceResult) -> ServiceResult:
    return {key: value for key, value in result.items() if key != "provenance"}


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="ipip_big_five",
        bind=bind_kwargs(calculate_ipip_big_five),
        request_model_loader=request_model_ref(
            "fatebridge.core.psychometrics.ipip_big_five", "IpipBigFiveRequest"
        ),
        required_output_fields=("mode", "scale_id", "provenance", "summary"),
        required_output_validator=_validate_ipip_output,
        summary="IPIP 50题大五人格量表（Goldberg 1992）：列题项或按1–5分确定性正反向计分，不含常模或诊断。",
        operation_label_zh="IPIP大五人格量表",
        family="psychometrics",
        rest_path="/api/psychometrics/ipip-big-five",
        uses_astronomy_runtime=False,
        compact_view=_compact_ipip_big_five,
    )
]
