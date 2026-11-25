"""Psychometrics tool declarations and domain binding helpers."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.bindings import lazy_service
from fatebridge.application.tool_spec import (
    BoundServiceCall,
    DetailLevel,
    OutputContractError,
    ServiceInput,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.method_contracts import MethodContract
from fatebridge.core.psychometrics.ipip_big_five import (
    METHOD_ID,
    SCALE_URL,
    SCORING_URL,
    IpipBigFiveOutput,
    IpipBigFiveRequest,
)

calculate_ipip_big_five = lazy_service(
    "fatebridge.services.psychometrics", "calculate_ipip_big_five"
)


def bind_ipip_big_five(request: BaseModel) -> BoundServiceCall:
    assert isinstance(request, IpipBigFiveRequest)
    arguments: dict[str, ServiceInput] = dict(request.service_inputs())
    return BoundServiceCall(calculate_ipip_big_five.resolved, (), arguments)


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
        if result.get("scale_raw_sum") is None or result.get("scale_mean") is None:
            raise OutputContractError("IPIP-50 score 输出缺少总量表原始分或均分")
        return
    raise OutputContractError(f"IPIP-50 输出 mode 非法：{mode}")


def _identity_detail_view(
    result: ServiceResult,
    _detail: DetailLevel,
    _requested: set[str],
) -> ServiceResult:
    return result


SPECS: list[ToolSpec] = [
    ToolSpec(
        key="ipip_big_five",
        bind=bind_ipip_big_five,
        request_model=IpipBigFiveRequest,
        output_model=IpipBigFiveOutput,
        required_output_fields=("mode", "scale_id", "provenance", "summary"),
        required_output_validator=_validate_ipip_output,
        summary=(
            "IPIP 50题大五人格因子标记量表（Goldberg 1992 公有领域）："
            "支持 action=list_items 列出50道题项与计分方向，"
            "或 action=score 对1-5分整数作答进行确定性正反向计分、8/10缺题阈值折算；"
            "仅输出客观计分事实与量表出处，不输出百分位、诊断或叙事建议。"
        ),
        operation_label_zh="IPIP大五人格量表",
        family="psychometrics",
        rest_path="/api/psychometrics/ipip-big-five",
        mcp_name="ipip_big_five",
        include_snapshot_text=False,
        uses_astronomy_runtime=False,
        detail_view=_identity_detail_view,
        methods=(
            MethodContract(
                method_id=METHOD_ID,
                output_paths=(
                    "mode",
                    "scale_id",
                    "domains",
                    "scale_raw_sum",
                    "scale_mean",
                    "items",
                    "provenance",
                ),
                quantity_kind="psychometric_scale_score",
                unit="likert_1_to_5",
                prerequisites=(
                    "action=list_items，或 action=score 且提供合法的 1..5 整数作答（responses 或 ratings）",
                ),
                dependencies=("validated_request",),
                comparison_requirements=(
                    "相同 Goldberg (1992) IPIP 50 题条目键、反向计分公式 (6 - score) 与 8/10 缺失阈值",
                ),
                limitations=(
                    "仅确定性算术计分与公有领域条目清单；不输出常模百分位、临床诊断或泛化叙事建议",
                    "仅作答 >= 8/10 题的因子计算折算均值；< 8 题标记为 insufficient_items 且 mean 为 null",
                ),
                implementation_refs=(
                    "src/fatebridge/core/psychometrics/ipip_big_five.py",
                    "src/fatebridge/services/psychometrics.py",
                ),
                source_refs=(SCALE_URL, SCORING_URL),
                selector_fields=("action", "domain", "include_item_breakdown"),
                error_sources=(),
                validation_status="deterministic_arithmetic_verified",
            ),
        ),
    )
]
