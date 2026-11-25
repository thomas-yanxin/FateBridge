"""Fengshui tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.domain_validators import detect_fengshui_approximate
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    AssessRequest,
    BazhaiRequest,
    DirectionsRequest,
    JinsuoRequest,
    MingguaRequest,
    MonthlyRequest,
    XuankongRequest,
)
from fatebridge.core.fengshui.output import FengshuiOutput


def _compact_rulesets(result: ServiceResult) -> list[ServiceResult]:
    fields = {"ruleset_id", "version", "method", "source_ids"}
    return [
        {key: value for key, value in ruleset.items() if key in fields}
        for ruleset in result["rulesets"]
    ]


def _compact_bazhai_chart(chart: ServiceResult) -> ServiceResult:
    return {
        **{
            key: value
            for key, value in chart.items()
            if key not in {"trace", "bearing_support", "sectors"}
        },
        "sectors": {
            direction: {"star": palace["star"]}
            for direction, palace in chart["sectors"].items()
        },
    }


def _compact_personal_chart(person: ServiceResult) -> ServiceResult:
    time_fields = {
        "effective_year",
        "year_boundary",
        "timezone_name",
        "input_basis",
        "birth_date",
        "effective_year_status",
        "candidate_effective_years",
    }
    return {
        **{key: value for key, value in person.items() if key != "ruleset"},
        "time_context": {
            key: value
            for key, value in person["time_context"].items()
            if key in time_fields
        },
        "candidates": [_compact_bazhai_chart(chart) for chart in person["candidates"]],
    }


def _compact_bazhai(result: ServiceResult) -> ServiceResult:
    layer = result["layers"]["bazhai"]
    house = layer["house"]
    finding_fields = {
        "subject_id",
        "subject_kind",
        "gender_convention",
        "house_candidate_id",
        "object_id",
        "purpose",
        "aspect",
        "facing_role",
        "direction",
        "star",
        "expected_polarity",
        "matches_convention",
        "candidate_only",
    }
    compact_layer = {key: value for key, value in layer.items() if key != "ruleset"}
    compact_layer.update(
        house=_compact_bazhai_chart(house) if house is not None else None,
        occupants=[_compact_personal_chart(person) for person in layer["occupants"]],
        placement_findings=[
            {key: value for key, value in finding.items() if key in finding_fields}
            for finding in layer["placement_findings"]
        ],
    )
    if "house_candidates" in layer:
        compact_layer["house_candidates"] = [
            _compact_bazhai_chart(chart) for chart in layer["house_candidates"]
        ]
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "layers": {"bazhai": compact_layer},
    }


def _compact_minggua(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "layers": {"minggua": _compact_personal_chart(result["layers"]["minggua"])},
    }


def _compact_candidate_ids(candidates: list[ServiceResult]) -> list[ServiceResult]:
    return [{"candidate_id": candidate["candidate_id"]} for candidate in candidates]


def _compact_xuankong(result: ServiceResult) -> ServiceResult:
    layer = result["layers"]["xuankong_natal"]
    period = layer["period_context"]
    period_fields = {
        "basis",
        "number",
        "input_basis",
        "effective_event_year",
        "resolution_status",
        "candidate_effective_event_years",
        "candidate_period_numbers",
        "confirmation_reason",
    }
    chart_fields = {
        "candidate_id",
        "period_number",
        "facing",
        "sitting",
        "chart_mode",
        "mode_reason",
    }
    palace_fields = {
        "period_star_number",
        "mountain_star_number",
        "facing_star_number",
        "palace_number",
    }
    natal_fields = {
        "status",
        "subject_id",
        "orientation_context",
        "missing_inputs",
        "interpretation_scope",
    }

    def chart_view(chart: ServiceResult) -> ServiceResult:
        return {
            **{key: value for key, value in chart.items() if key in chart_fields},
            "palaces": {
                direction: {
                    key: value for key, value in palace.items() if key in palace_fields
                }
                for direction, palace in chart["palaces"].items()
            },
        }

    chart = layer["chart"]
    natal = {key: value for key, value in layer.items() if key in natal_fields}
    natal["period_context"] = (
        {key: value for key, value in period.items() if key in period_fields}
        if period is not None
        else None
    )
    natal["chart"] = chart_view(chart) if chart is not None else None
    natal["candidates"] = (
        _compact_candidate_ids(layer["candidates"])
        if chart is not None
        else [chart_view(candidate) for candidate in layer["candidates"]]
    )
    if "city_gate_analysis" in layer:
        city_gate = layer["city_gate_analysis"]
        gate_fields = {
            "direction",
            "star_at_gate",
            "combined_condition_match",
            "reference_star_reaches_gate_by_reverse_flight",
        }
        natal["city_gate_analysis"] = {
            "status": city_gate["status"],
            "calculation_status": city_gate["calculation_status"],
            "reference_period_context": {
                "number": city_gate["reference_period_context"]["number"],
            },
            "missing_inputs": city_gate["missing_inputs"],
            "candidates": [
                {
                    "facing": {"name": candidate["facing"]["name"]},
                    "candidate_only": candidate["candidate_only"],
                    "gates": [
                        {
                            **{
                                key: value
                                for key, value in gate.items()
                                if key in gate_fields
                            },
                            "mountain": {"name": gate["mountain"]["name"]},
                            "form_assessment": {
                                "status": gate["form_assessment"]["status"]
                            },
                        }
                        for gate in candidate["gates"]
                    ],
                }
                for candidate in city_gate["candidates"]
            ],
        }
    if "interpretation" in layer:
        interpretation_fields = {
            "status",
            "ruleset_id",
            "rule_coverage_status",
            "missing_inputs",
            "overall_auspiciousness",
        }
        natal["interpretation"] = {
            key: value
            for key, value in layer["interpretation"].items()
            if key in interpretation_fields
        }
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": {
            source_id: {
                key: value
                for key, value in source.items()
                if key in {"title", "author", "url"}
            }
            for source_id, source in result["source_catalog"].items()
        },
        "layers": {"xuankong_natal": natal},
    }


def _compact_assessment(result: ServiceResult) -> ServiceResult:
    layout = result.get("layout_analysis")
    if layout is None:
        return result
    coverage = result["coverage"]
    progress = layout["analysis_progress"]
    compact_layers: dict[str, ServiceResult] = {}
    for name, layer in result["layers"].items():
        trimmed = {key: value for key, value in layer.items() if key != "ruleset"}
        if name == "xuankong_natal" and trimmed.get("chart") is not None:
            trimmed["candidates"] = _compact_candidate_ids(
                trimmed.get("candidates", [])
            )
        compact_layers[name] = trimmed
    return {
        **result,
        "layers": compact_layers,
        "coverage": {
            key: value
            for key, value in coverage.items()
            if value
            and key
            not in {
                "analysis_progress",
                "layout_status",
                "layout_missing_inputs",
                "requested_analysis_status",
            }
        },
        "layout_analysis": {
            **{key: value for key, value in layout.items() if value},
            "analysis_progress": {
                key: value
                for key, value in progress.items()
                if key
                in {
                    "interpretation_status",
                    "rule_coverage_status",
                    "action_readiness",
                    "pending_confirmations",
                }
                or (
                    key == "follow_up"
                    and (value["conclusion_candidates"] or value["execution_only"])
                )
            },
            "placement_findings": [
                {
                    key: value
                    for key, value in finding.items()
                    if value is not None
                    and key
                    not in {
                        "you_nian_trace",
                        "palace_star_relationship",
                        "time_context",
                        "matches_convention_scope",
                        "application_scope",
                    }
                }
                for finding in layout["placement_findings"]
            ],
        },
        "rulesets": _compact_rulesets(result),
    }


SPECS: list[ToolSpec] = []
_COMPACT_VIEWS = {
    "minggua": _compact_minggua,
    "bazhai": _compact_bazhai,
    "xuankong_natal": _compact_xuankong,
    "assess": _compact_assessment,
}

for _name, _public_name, _service, _model, _summary in (
    (
        "directions",
        "directions",
        "calculate_directions",
        DirectionsRequest,
        "后天八卦固定方位、宫数与角区索引；可显式提供geomagnetic_reference计算WMM2025地磁与真北/磁北换算候选，保留原始方位，不自动应用宅盘。",
    ),
    (
        "minggua",
        "minggua",
        "calculate_minggua",
        MingguaRequest,
        "住户命卦及个人八方关系（独立于宅卦）：支持公历 birth_date，非立春当日不需要出生小时；布局问题优先 fengshui_assess 的 analyze_layout。",
    ),
    (
        "bazhai",
        "bazhai",
        "calculate_bazhai",
        BazhaiRequest,
        "八宅坐山宅盘、逐人命盘与用途判定；不是完整阳宅三要门主灶结构法",
    ),
    (
        "jinsuo",
        "jinsuo",
        "calculate_jinsuo",
        JinsuoRequest,
        "金锁玉关八宫基础砂水偏好（已确认分类）",
    ),
    (
        "annual_stars",
        "annual_stars",
        "calculate_annual_stars",
        AnnualRequest,
        "立春换年的年度九宫紫白飞星（非山向宅盘）",
    ),
    (
        "monthly_stars",
        "monthly_stars",
        "calculate_monthly_stars",
        MonthlyRequest,
        "十二节交节时刻换月的九宫月紫白；可传含时区query_at或已确认的effective_solar_year/solar_month_number，不以公历月/农历月补值，不替代年盘或宅盘，不生成布局处方。",
    ),
    (
        "xuankong_natal",
        "xuankong_house_chart",
        "calculate_xuankong_natal",
        XuankongRequest,
        "中州派玄空运山向宅盘、历史定运、兼向替星与边界候选（独立于年星）；interpretation 显式启用 xuankong_conditioned_v1 有限解释，current_period_number/period_evidence 成对，外局分宫独立确认山形/水形，不复用金锁或室内靠背。",
    ),
    (
        "assess",
        "assess",
        "assess",
        AssessRequest,
        "工位、合租和家居风水布局主入口；布局设 analyze_layout=true。"
        "有尺寸的工位可用workstation_layout计算几何、屏幕遮挡及有限网格候选，按需读workstation_layout_analysis；算法覆盖读research_coverage。"
        "只传确认事实，照片保留候选；位置、朝向、使用人与行动许可分开。"
        "解释已有依据与条件，不等待动作 ready；保留 rulesets/rule_trace 与来源。"
        "具体分支按当前参数说明、结果层与规则来源读取，不把个人八字喜忌当环境规则。",
    ),
):
    SPECS.append(
        ToolSpec(
            key=f"fengshui_{_name}",
            bind=raw_invoke(lazy_service("fatebridge.services.fengshui", _service)),
            request_model=_model,
            summary=_summary,
            operation_label_zh=_summary,
            family="fengshui",
            rest_path="/api/fengshui/" + _public_name.replace("_", "-"),
            mcp_name=f"fengshui_{_public_name}",
            output_model=FengshuiOutput,
            cli_request_file=True,
            approximate_record=detect_fengshui_approximate,
            compact_view=_COMPACT_VIEWS.get(_name),
        )
    )
