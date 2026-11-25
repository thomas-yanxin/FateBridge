"""IPIP psychometric tool declaration using the shared transport contract."""

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
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

SPECS = [
    ToolSpec(
        key="ipip_big_five",
        bind=raw_invoke(calculate_ipip_big_five),
        request_model=IpipBigFiveRequest,
        output_model=IpipBigFiveOutput,
        required_output_fields=("mode", "scale_id", "provenance", "summary"),
        summary=(
            "IPIP 50题大五因子：list_items 列题目与计分键；score 按1–5整数正反向计分。"
            "各因子作答至少8/10题才给均值和折算和（项目缺题策略）；中文为项目释义。"
        ),
        operation_label_zh="IPIP大五因子",
        family="psychometrics",
        rest_path="/api/psychometrics/ipip-big-five",
        mcp_name="ipip_big_five",
        include_snapshot_text=False,
        methods=(
            MethodContract(
                method_id=METHOD_ID,
                output_paths=("mode", "scale_id", "domains", "items", "provenance"),
                quantity_kind="psychometric_domain_score",
                unit="likert_1_to_5",
                prerequisites=("list_items，或 score 提供至少一道1–5整数作答",),
                dependencies=("validated_request",),
                comparison_requirements=("相同IPIP样本题序、50题键和项目8/10缺题策略",),
                limitations=(
                    "8/10门槛为项目策略，IPIP原计分页未规定缺题处理",
                    "中文为项目词义释义，未完成独立翻译效度研究",
                    "未建立本产品常模或临床效度，不生成跨因子总分",
                ),
                implementation_refs=(
                    "src/fatebridge/core/psychometrics/ipip_big_five.py",
                    "src/fatebridge/services/psychometrics.py",
                ),
                source_refs=(SCALE_URL, SCORING_URL),
                selector_fields=("action", "domain", "include_item_breakdown"),
                validation_status="item_keys_and_arithmetic_verified",
            ),
        ),
    )
]
