"""Fengshui tool declarations and domain binding helpers."""

from __future__ import annotations

from functools import partial

from pydantic import BaseModel

from fatebridge.application.bindings import bind_request, service_ref
from fatebridge.application.domain_validators import detect_fengshui_approximate
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy


def _load_fengshui_request_model(model_name: str) -> type[BaseModel]:
    from fatebridge.core.fengshui import models

    return getattr(models, model_name)


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


COMPACT_VIEWS = {
    "fengshui_minggua": _compact_minggua,
    "fengshui_bazhai": _compact_bazhai,
    "fengshui_xuankong_house_chart": _compact_xuankong,
    "fengshui_assess": _compact_assessment,
}


def _build_fengshui_specs() -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for public_name, label, service, model, summary in (
        (
            "directions",
            "风水方位",
            "calculate_directions",
            "DirectionsRequest",
            "后天八卦方位与角区索引；可选 WMM2025 地磁换算候选，不自动套用宅盘。",
        ),
        (
            "minggua",
            "风水命卦",
            "calculate_minggua",
            "MingguaRequest",
            "住户命卦及个人八方关系；布局分析请用 fengshui_assess 的 analyze_layout。",
        ),
        (
            "bazhai",
            "八宅风水",
            "calculate_bazhai",
            "BazhaiRequest",
            "八宅坐山宅盘、逐人命盘与用途判定；不是完整阳宅三要门主灶结构法",
        ),
        (
            "jinsuo",
            "金锁玉关",
            "calculate_jinsuo",
            "JinsuoRequest",
            "金锁玉关八宫基础砂水偏好（已确认分类）",
        ),
        (
            "annual_stars",
            "流年飞星",
            "calculate_annual_stars",
            "AnnualRequest",
            "立春换年的年度九宫紫白飞星（非山向宅盘）",
        ),
        (
            "monthly_stars",
            "流月飞星",
            "calculate_monthly_stars",
            "MonthlyRequest",
            "十二节换月九宫紫白飞星；需 query_at 或已确认 solar 年月，不替代宅盘。",
        ),
        (
            "xuankong_house_chart",
            "玄空宅盘",
            "calculate_xuankong_natal",
            "XuankongRequest",
            "中州派玄空运山向宅盘、定运与兼向替星；支持显式 xuankong_conditioned_v1 解释。",
        ),
        (
            "assess",
            "风水布局评估",
            "calculate_fengshui_assessment",
            "AssessRequest",
            "工位、合租与家居风水布局主入口；布局设 analyze_layout=true，只传已确认事实。",
        ),
    ):
        tool_name = f"fengshui_{public_name}"
        specs.append(
            ToolSpec(
                name=tool_name,
                bind=bind_request(service_ref("fatebridge.services.fengshui", service)),
                request_model_loader=partial(_load_fengshui_request_model, model),
                summary=summary,
                operation_label_zh=label,
                family="fengshui",
                rest_path="/api/fengshui/" + public_name.replace("_", "-"),
                cli_request_file=True,
                reproducibility=ReproducibilityPolicy(),
                approximate_record=detect_fengshui_approximate,
                compact_view=COMPACT_VIEWS.get(tool_name),
            )
        )
    return specs


SPECS: list[ToolSpec] = _build_fengshui_specs()
