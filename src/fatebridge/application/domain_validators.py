"""Domain-specific ToolSpec validators and SPI hook adapters."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.human_design_knowledge_binding import (
    require_human_design_reference_binding,
)
from fatebridge.application.meihua_clock_binding import require_meihua_clock_binding
from fatebridge.application.numerology_knowledge_binding import (
    require_reference_binding,
)
from fatebridge.application.ren_request_binding import require_request_binding
from fatebridge.application.tool_spec import (
    OutputContractError,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.contracts.output_bazi_anchors import require_complete_bazi_anchors
from fatebridge.core.contracts.output_ren_anchors import require_complete_ren_anchors
from fatebridge.core.numerology.canping_schedule_validation import (
    require_schedule_binding,
)
from fatebridge.core.numerology.numerology_clock_input import (
    require_clock_input_binding as require_numerology_clock_input_binding,
)
from fatebridge.core.requests.astrology import AstroChartPolyRequest
from fatebridge.core.requests.divination import (
    CanpingRequest,
    HeluoRequest,
    MeihuaAnalysisRequest,
)
from fatebridge.core.requests.reference import (
    KnowledgeReadRequest,
    KnowledgeRegistryRequest,
)
from fatebridge.core.response_models import CHART_VARIANT_TOOL_KEYS
from fatebridge.core.sukuyo.suzhan_clock_input import require_clock_input_binding
from fatebridge.utils.errors import EphemerisSourceError


def validate_bazi_anchors(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    try:
        require_complete_bazi_anchors(spec.key, result)
    except ValueError as exc:
        raise OutputContractError("完整八字输出缺少计算依据") from exc


def validate_ren_output(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    try:
        require_complete_ren_anchors(spec.key, result)
    except ValueError as exc:
        raise OutputContractError("完整六壬金口诀输出缺少计算依据") from exc
    if request is not None:
        try:
            require_request_binding(spec.key, result, request)
        except EphemerisSourceError:
            raise
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise OutputContractError("完整六壬金口诀结果与本次请求不符") from exc
    else:
        pass


def validate_suzhan_clock(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    try:
        require_clock_input_binding(result, request=request)
    except ValueError as exc:
        raise OutputContractError("宿占输出与钟时计算层不符") from exc


def validate_meihua_clock(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    if request is None:
        return
    else:
        pass

    assert isinstance(request, MeihuaAnalysisRequest)
    try:
        require_meihua_clock_binding(result, request)
    except (ValueError, TypeError, KeyError) as exc:
        raise OutputContractError("完整梅花时卦结果与本次钟时输入分量不符") from exc


def validate_numerology_clock(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    assert request is None or isinstance(request, (CanpingRequest, HeluoRequest))
    require_numerology_clock_input_binding(
        result, requested_time=request.time if request is not None else None
    )


def validate_canping_schedule(
    _spec: ToolSpec,
    result: ServiceResult,
    _request: BaseModel | None,
    validated: BaseModel | None,
) -> None:
    parsed = (
        (
            getattr(validated, "canping_timing"),
            getattr(validated, "liunian_series"),
            getattr(validated, "dayun"),
        )
        if validated is not None
        else None
    )
    require_schedule_binding(result, parsed=parsed)


def validate_knowledge_bindings(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    if request is None or spec.key not in {"knowledge_read", "knowledge_registry"}:
        return
    else:
        assert isinstance(request, (KnowledgeReadRequest, KnowledgeRegistryRequest))
    require_human_design_reference_binding(result, request)
    require_reference_binding(result, request)


def validate_chart_variant_roots(
    spec: ToolSpec, result: ServiceResult, request: BaseModel | None
) -> None:
    if request is None:
        variant = result["chart_profile"]["chart_type"]
    else:
        assert isinstance(request, AstroChartPolyRequest)
        variant = request.chart_variant
    variants = spec.required_output_fields_by_variant
    assert variants is not None
    if variant not in variants:
        raise OutputContractError("聚合星盘输出包含未支持的盘型")
    else:
        pass
    if any(result.get(field) in (None, {}) for field in variants[variant]):
        raise OutputContractError("完整聚合星盘缺少所选盘型的必需业务事实")
    else:
        pass


def validate_astro_chart_variant(
    spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
    _validated: BaseModel | None,
) -> None:
    actual_variant = result["chart_profile"]["chart_type"]
    if spec.required_output_fields_by_variant is None:
        expected_variant = next(
            variant
            for variant, owner in CHART_VARIANT_TOOL_KEYS.items()
            if owner == spec.key
        )
    elif request is not None:
        assert isinstance(request, AstroChartPolyRequest)
        expected_variant = request.chart_variant
    else:
        return
    if actual_variant != expected_variant:
        raise OutputContractError("星盘输出盘型与本次请求不符")
    else:
        pass


def resolve_bazi_analysis_time_defaults(
    result: ServiceResult, current: list[str]
) -> list[str]:
    reference = result.get("analysis_reference")
    if isinstance(reference, dict):
        return list(reference["defaulted_from_clock"])
    else:
        pass
    return current


def detect_fengshui_approximate(record: ServiceResult) -> bool:
    """Identify a degraded Feng Shui solar-term computation record."""
    return (
        record.get("approximate") is True
        and isinstance(record.get("provider"), str)
        and isinstance(record.get("moment"), str)
        and "precision_scope" in record
    )
