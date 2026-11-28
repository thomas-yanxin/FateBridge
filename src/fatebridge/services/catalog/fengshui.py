"""Fengshui tool declarations, per-tool schemas (<6 KB), and default_omit views."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from fatebridge.application.bindings import bind_request, service_ref
from fatebridge.application.tool_spec import BatchInputPolicy, ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy

if TYPE_CHECKING:
    from pydantic import BaseModel


def detect_fengshui_approximate(record: ServiceResult) -> bool:
    """Identify a degraded Feng Shui solar-term computation record."""
    return (
        record.get("approximate") is True
        and isinstance(record.get("provider"), str)
        and isinstance(record.get("moment"), str)
        and "precision_scope" in record
    )


def _load_fengshui_model(model_name: str) -> type[BaseModel]:
    from fatebridge.core.fengshui import models

    model: type[BaseModel] = getattr(models, model_name)
    return model


_XUANKONG_NATAL_OMIT: tuple[str, ...] = (
    "layers.xuankong_natal.period_context.timing",
    "layers.xuankong_natal.chart.flight_details",
    "layers.xuankong_natal.chart.structure.classical_patterns",
    "layers.xuankong_natal.chart.structure.combination_of_ten",
    "layers.xuankong_natal.candidates.*.flight_details",
    "layers.xuankong_natal.candidates.*.structure.classical_patterns",
    "layers.xuankong_natal.candidates.*.structure.combination_of_ten",
    "layers.xuankong_natal.interpretation.candidates.*.palaces",
)


def _build_fengshui_specs() -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for public_name, label, service, req_model, out_model, summary, default_omit in (
        (
            "directions",
            "风水方位",
            "calculate_directions",
            "DirectionsRequest",
            "DirectionsOutput",
            "后天八卦方位、空亡兼向细分；可选 WMM2025/IGRF-14(1900-2030) 地磁换算候选。",
            (),
        ),
        (
            "minggua",
            "风水命卦",
            "calculate_minggua",
            "MingguaRequest",
            "MingguaOutput",
            "住户命卦及个人八方关系；布局分析请用 fengshui_assess 的 analyze_layout。",
            ("layers.minggua.time_context.timing",),
        ),
        (
            "bazhai",
            "八宅风水",
            "calculate_bazhai",
            "BazhaiRequest",
            "BazhaiOutput",
            "八宅坐山宅盘、逐人命盘、游年星宫生克与阳宅三要（门主灶）。",
            (
                "conflicts",
                "layers.bazhai.house.sitting_bearing",
                "layers.bazhai.occupants.*.time_context.timing",
                "layers.bazhai.occupants.*.candidates.*.sectors",
            ),
        ),
        (
            "jinsuo",
            "金锁玉关",
            "calculate_jinsuo",
            "JinsuoRequest",
            "JinsuoOutput",
            "金锁玉关八宫与二十四山砂水偏好及逐项特征判定。",
            ("layers.jinsuo.twenty_four_mountains",),
        ),
        (
            "annual_stars",
            "流年飞星",
            "calculate_annual_stars",
            "AnnualRequest",
            "AnnualStarsOutput",
            "立春换年的年度九宫紫白飞星及岁煞（太岁/岁破/三煞/五黄/二黑）。",
            (
                "layers.annual_stars.time_context.timing",
                "layers.annual_stars.flight_path",
            ),
        ),
        (
            "monthly_stars",
            "流月飞星",
            "calculate_monthly_stars",
            "MonthlyRequest",
            "MonthlyStarsOutput",
            "十二节换月九宫紫白飞星，并支持日紫白、时紫白计算。",
            (
                "layers.monthly_stars.time_context.timing",
                "layers.monthly_stars.flight_path",
                "layers.monthly_stars.daily_stars.palaces",
                "layers.monthly_stars.hourly_stars.palaces",
            ),
        ),
        (
            "xuankong_house_chart",
            "玄空宅盘",
            "calculate_xuankong_natal",
            "XuankongRequest",
            "XuankongOutput",
            "中州派玄空运山向宅盘、空亡兼向、连珠三般卦、七星打劫、令星入囚与正副城门。",
            _XUANKONG_NATAL_OMIT,
        ),
        (
            "assess",
            "风水布局评估",
            "calculate_fengshui_assessment",
            "AssessRequest",
            "AssessOutput",
            "家居风水多层合参主入口（八宅/金锁/玄空/年/月/日/时紫白四层叠盘）。",
            (
                "conflicts",
                "layers.bazhai.house.sitting_bearing",
                "layers.bazhai.house.sectors",
                "layers.bazhai.house_candidates.*.sectors",
                "layers.bazhai.occupants.*.time_context.timing",
                "layers.bazhai.occupants.*.candidates.*.sectors",
                "layers.bazhai.placement_findings",
                "layers.jinsuo.twenty_four_mountains",
                "layers.jinsuo.feature_findings",
                "layers.annual_stars.time_context.timing",
                "layers.annual_stars.palaces",
                "layers.annual_stars.flight_path",
                "layers.monthly_stars.time_context.timing",
                "layers.monthly_stars.palaces",
                "layers.monthly_stars.flight_path",
                "layers.monthly_stars.daily_stars.palaces",
                "layers.monthly_stars.hourly_stars.palaces",
                *_XUANKONG_NATAL_OMIT,
                "layout_analysis.adjustment_options",
                "layout_analysis.element_relationships",
            ),
        ),
    ):
        tool_name = f"fengshui_{public_name}"
        if public_name == "minggua":
            batch_policy = BatchInputPolicy(subject_mode="exclusive_birth_record")
        elif public_name in {"bazhai", "assess"}:
            batch_policy = BatchInputPolicy(
                subject_mode="subject_list", list_field="occupants"
            )
        else:
            batch_policy = BatchInputPolicy()
        required_output_fields = (
            ("status", "coverage")
            if public_name == "assess"
            else ("status", "layers", "coverage")
        )
        specs.append(
            ToolSpec(
                name=tool_name,
                bind=bind_request(service_ref("fatebridge.services.fengshui", service)),
                request_model_loader=partial(_load_fengshui_model, req_model),
                output_model_loader=partial(_load_fengshui_model, out_model),
                required_output_fields=required_output_fields,
                summary=summary,
                operation_label_zh=label,
                family="fengshui",
                rest_path="/api/fengshui/" + public_name.replace("_", "-"),
                cli_request_file=True,
                default_omit=default_omit,
                reproducibility=ReproducibilityPolicy(),
                approximate_record=detect_fengshui_approximate,
                batch_policy=batch_policy,
            )
        )
    return specs


SPECS: list[ToolSpec] = _build_fengshui_specs()
