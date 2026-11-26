"""Fengshui tool declarations, per-tool schemas (<6 KB), and compact views (<4 KB)."""

from __future__ import annotations

from functools import partial

from pydantic import BaseModel

from fatebridge.application.bindings import bind_request, service_ref
from fatebridge.application.domain_validators import detect_fengshui_approximate
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy


def _load_fengshui_model(model_name: str) -> type[BaseModel]:
    from fatebridge.core.fengshui import models

    return getattr(models, model_name)


def _compact_rulesets(result: ServiceResult) -> list[ServiceResult]:
    fields = {"ruleset_id", "version", "method", "source_ids"}
    return [
        {key: value for key, value in ruleset.items() if key in fields}
        for ruleset in result["rulesets"]
    ]


def _compact_sources(result: ServiceResult) -> ServiceResult:
    return {
        source_id: {"title": source["title"]}
        for source_id, source in result.get("source_catalog", {}).items()
        if "title" in source
    }


def _compact_directions(result: ServiceResult) -> ServiceResult:
    layer = result["layers"]["directions"]
    compact_layer = {
        key: value
        for key, value in layer.items()
        if key not in {"ruleset", "directions"}
    }
    compact_layer["directions"] = {
        d: {
            "trigram": info["trigram"],
            "palace_number": info["palace_number"],
            "element": info["element"],
        }
        for d, info in layer["directions"].items()
    }
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {"directions": compact_layer},
    }


def _compact_bazhai_chart(chart: ServiceResult) -> ServiceResult:
    return {
        **{
            key: value
            for key, value in chart.items()
            if key not in {"bearing_support", "sectors", "sitting_bearing"}
        },
        "sectors": {
            direction: f"{palace['star']['name']}({palace['star']['polarity'][0]})"
            for direction, palace in chart["sectors"].items()
        },
    }


def _compact_personal_chart(person: ServiceResult) -> ServiceResult:
    return {
        "status": person["status"],
        "subject_id": person["subject_id"],
        "effective_year": person["time_context"].get("effective_year"),
        "candidates": [_compact_bazhai_chart(chart) for chart in person["candidates"]],
        **(
            {"missing_inputs": person["missing_inputs"]}
            if person["missing_inputs"]
            else {}
        ),
    }


def _compact_minggua(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {"minggua": _compact_personal_chart(result["layers"]["minggua"])},
    }


def _compact_bazhai(result: ServiceResult) -> ServiceResult:
    layer = result["layers"]["bazhai"]
    house = layer["house"]
    compact_layer = {
        key: value
        for key, value in layer.items()
        if key not in {"ruleset", "yangzhai_sanyao", "missing_inputs"}
    }
    compact_layer.update(
        house=_compact_bazhai_chart(house) if house is not None else None,
        occupants=[_compact_personal_chart(person) for person in layer["occupants"]],
        placement_findings=[
            {
                "target": f"{f['subject_id']}.{f['object_id']}.{f['aspect']}",
                "direction": f["direction"],
                "star": f["star"]["name"],
                "ok": f["matches_convention"],
            }
            for f in layer["placement_findings"]
        ],
    )
    if layer.get("missing_inputs"):
        compact_layer["missing_inputs"] = layer["missing_inputs"]
    if "yangzhai_sanyao" in layer:
        sy = layer["yangzhai_sanyao"]
        compact_layer["yangzhai_sanyao"] = {
            "coherence": sy["east_west_coherence"],
            "complete": sy["complete_sanyao"],
            "relations": {
                k: f"{v['younian_star']['name']}/{v['element_label']}"
                for k, v in sy["relations"].items()
            },
        }
    if "house_candidates" in layer:
        compact_layer["house_candidates"] = [
            _compact_bazhai_chart(chart) for chart in layer["house_candidates"]
        ]
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {"bazhai": compact_layer},
    }


def _compact_jinsuo(result: ServiceResult) -> ServiceResult:
    layer = result["layers"]["jinsuo"]
    compact_layer = {
        "status": layer["status"],
        "preferences": {
            d: info["preferred_classification"]
            for d, info in layer["preferences"].items()
        },
        "feature_findings": layer["feature_findings"],
        "missing_inputs": layer["missing_inputs"],
    }
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {"jinsuo": compact_layer},
    }


def _compact_zibai(layer_name: str, result: ServiceResult) -> ServiceResult:
    layer = result["layers"][layer_name]
    compact_layer = {
        key: value
        for key, value in layer.items()
        if key not in {"ruleset", "time_context", "daily_stars", "hourly_stars"}
    }
    if "palaces" in compact_layer:
        star_num_key = (
            "annual_star_number"
            if layer_name == "annual_stars"
            else "monthly_star_number"
        )
        star_key = "annual_star" if layer_name == "annual_stars" else "monthly_star"
        compact_layer["palaces"] = {
            d: {star_num_key: p[star_num_key], star_key: p[star_key]}
            for d, p in compact_layer["palaces"].items()
        }
    if "daily_stars" in layer:
        ds = layer["daily_stars"]
        compact_layer["daily_stars"] = {
            "day_ganzhi": ds["day_ganzhi"],
            "center_star_number": ds["center_star_number"],
            "segment": ds["segment"],
        }
    if "hourly_stars" in layer:
        hs = layer["hourly_stars"]
        compact_layer["hourly_stars"] = {
            "hour_branch": hs["hour_branch"],
            "center_star_number": hs["center_star_number"],
            "dun_half": hs["dun_half"],
        }
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {layer_name: compact_layer},
    }


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
    }
    chart_fields = {
        "candidate_id",
        "period_number",
        "facing",
        "sitting",
        "chart_mode",
        "mode_reason",
        "facing_subband",
        "adjacent_mountain",
        "kongwang",
    }
    palace_fields = {
        "period_star_number",
        "mountain_star_number",
        "facing_star_number",
        "palace_number",
    }

    def chart_view(chart: ServiceResult) -> ServiceResult:
        out: ServiceResult = {
            "candidate_id": chart["candidate_id"],
            "period_number": chart["period_number"],
            "facing": chart["facing"]["name"],
            "sitting": chart["sitting"]["name"],
            "chart_mode": chart["chart_mode"],
            "facing_subband": chart.get("facing_subband"),
            "adjacent_mountain": chart.get("adjacent_mountain"),
            "kongwang": chart.get("kongwang"),
            "palaces": {
                d: {
                    "p": p["period_star_number"],
                    "m": p["mountain_star_number"],
                    "f": p["facing_star_number"],
                }
                for d, p in chart["palaces"].items()
            },
        }
        if "structure" in chart:
            st = chart["structure"]
            cp = st["classical_patterns"]
            out["structure"] = {
                "distribution": st["distribution"]["traditional_label"],
                "eval_distribution": st["eval_period_distribution"][
                    "traditional_label"
                ],
                "lingxing_ruqiu": st["lingxing_ruqiu"]["lingxing_ruqiu"],
                "eval_lingxing_ruqiu": st["eval_lingxing_ruqiu"]["lingxing_ruqiu"],
                "parental_triples": cp["parental_triples"]["all_nine_match"],
                "lianzhu_triples": cp["lianzhu_triples"]["all_nine_match"],
                "qixing_dajie": cp["qixing_dajie"]["matched"],
            }
        return out

    chart = layer["chart"]
    natal: ServiceResult = {
        "status": layer["status"],
        "subject_id": layer["subject_id"],
        "orientation_context": layer["orientation_context"],
        "missing_inputs": layer["missing_inputs"],
        "period_context": (
            {k: v for k, v in period.items() if k in period_fields}
            if period is not None
            else None
        ),
        "chart": chart_view(chart) if chart is not None else None,
        "candidates": (
            [{"candidate_id": c["candidate_id"]} for c in layer["candidates"]]
            if chart is not None
            else [chart_view(c) for c in layer["candidates"]]
        ),
    }
    if "city_gate_analysis" in layer:
        cg = layer["city_gate_analysis"]
        natal["city_gate_analysis"] = {
            "status": cg["status"],
            "reference_period_number": cg["reference_period_context"]["number"],
            "candidates": [
                {
                    "facing": c["facing"]["name"],
                    "gates": [
                        {
                            "direction": g["direction"],
                            "gate_type": g["gate_type"],
                            "mountain": g["mountain"]["name"],
                            "star_at_gate": g["star_at_gate"],
                            "usable": g["usable"],
                        }
                        for g in c["gates"]
                    ],
                }
                for c in cg["candidates"]
            ],
        }
    if "interpretation" in layer:
        natal["interpretation"] = {
            "status": layer["interpretation"]["status"],
            "current_period_context": layer["interpretation"]["current_period_context"],
            "missing_inputs": layer["interpretation"]["missing_inputs"],
        }
    return {
        **result,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
        "layers": {"xuankong_natal": natal},
    }


def _compact_assessment(result: ServiceResult) -> ServiceResult:
    layout = result.get("layout_analysis")
    compact_layers = {}
    for name, layer in result["layers"].items():
        if name == "bazhai":
            compact_layers[name] = _compact_bazhai(
                {"layers": {"bazhai": layer}, "rulesets": []}
            )["layers"]["bazhai"]
        elif name == "jinsuo":
            compact_layers[name] = _compact_jinsuo(
                {"layers": {"jinsuo": layer}, "rulesets": []}
            )["layers"]["jinsuo"]
        elif name in {"annual_stars", "monthly_stars"}:
            compact_layers[name] = _compact_zibai(
                name, {"layers": {name: layer}, "rulesets": []}
            )["layers"][name]
        elif name == "xuankong_natal":
            compact_layers[name] = _compact_xuankong(
                {"layers": {"xuankong_natal": layer}, "rulesets": []}
            )["layers"]["xuankong_natal"]
        else:
            compact_layers[name] = {k: v for k, v in layer.items() if k != "ruleset"}
    out: ServiceResult = {
        **result,
        "layers": compact_layers,
        "rulesets": _compact_rulesets(result),
        "source_catalog": _compact_sources(result),
    }
    if layout is not None:
        out["layout_analysis"] = {
            "status": layout["status"],
            "calculation_scope": layout["calculation_scope"],
            "placement_findings": [
                {
                    k: (v["name"] if k == "star" and isinstance(v, dict) else v)
                    for k, v in f.items()
                    if k
                    in {
                        "method",
                        "subject_id",
                        "object_id",
                        "direction",
                        "star",
                        "matches_convention",
                        "annual_star_number",
                        "monthly_star_number",
                    }
                }
                for f in layout["placement_findings"]
            ],
            **(
                {"environment_adjustments": layout["environment_adjustments"]}
                if layout["environment_adjustments"]
                else {}
            ),
            **(
                {"missing_inputs": layout["missing_inputs"]}
                if layout["missing_inputs"]
                else {}
            ),
        }
    out.pop("conflicts", None)
    return out


COMPACT_VIEWS = {
    "fengshui_directions": _compact_directions,
    "fengshui_minggua": _compact_minggua,
    "fengshui_bazhai": _compact_bazhai,
    "fengshui_jinsuo": _compact_jinsuo,
    "fengshui_annual_stars": partial(_compact_zibai, "annual_stars"),
    "fengshui_monthly_stars": partial(_compact_zibai, "monthly_stars"),
    "fengshui_xuankong_house_chart": _compact_xuankong,
    "fengshui_assess": _compact_assessment,
}


def _build_fengshui_specs() -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for public_name, label, service, req_model, out_model, summary in (
        (
            "directions",
            "风水方位",
            "calculate_directions",
            "DirectionsRequest",
            "DirectionsOutput",
            "后天八卦方位、空亡兼向细分；可选 WMM2025/IGRF-14(1900-2030) 地磁换算候选。",
        ),
        (
            "minggua",
            "风水命卦",
            "calculate_minggua",
            "MingguaRequest",
            "MingguaOutput",
            "住户命卦及个人八方关系；布局分析请用 fengshui_assess 的 analyze_layout。",
        ),
        (
            "bazhai",
            "八宅风水",
            "calculate_bazhai",
            "BazhaiRequest",
            "BazhaiOutput",
            "八宅坐山宅盘、逐人命盘、游年星宫生克与阳宅三要（门主灶）。",
        ),
        (
            "jinsuo",
            "金锁玉关",
            "calculate_jinsuo",
            "JinsuoRequest",
            "JinsuoOutput",
            "金锁玉关八宫与二十四山砂水偏好及逐项特征判定。",
        ),
        (
            "annual_stars",
            "流年飞星",
            "calculate_annual_stars",
            "AnnualRequest",
            "AnnualStarsOutput",
            "立春换年的年度九宫紫白飞星及岁煞（太岁/岁破/三煞/五黄/二黑）。",
        ),
        (
            "monthly_stars",
            "流月飞星",
            "calculate_monthly_stars",
            "MonthlyRequest",
            "MonthlyStarsOutput",
            "十二节换月九宫紫白飞星，并支持日紫白、时紫白计算。",
        ),
        (
            "xuankong_house_chart",
            "玄空宅盘",
            "calculate_xuankong_natal",
            "XuankongRequest",
            "XuankongOutput",
            "中州派玄空运山向宅盘、空亡兼向、连珠三般卦、七星打劫、令星入囚与正副城门。",
        ),
        (
            "assess",
            "风水布局评估",
            "calculate_fengshui_assessment",
            "AssessRequest",
            "AssessOutput",
            "家居风水多层合参主入口（八宅/金锁/玄空/年/月/日/时紫白四层叠盘）。",
        ),
    ):
        tool_name = f"fengshui_{public_name}"
        specs.append(
            ToolSpec(
                name=tool_name,
                bind=bind_request(service_ref("fatebridge.services.fengshui", service)),
                request_model_loader=partial(_load_fengshui_model, req_model),
                output_model_loader=partial(_load_fengshui_model, out_model),
                summary=summary,
                operation_label_zh=label,
                family="fengshui",
                rest_path="/api/fengshui/" + public_name.replace("_", "-"),
                cli_request_file=True,
                reproducibility=ReproducibilityPolicy(),
                approximate_record=detect_fengshui_approximate,
                compact_view=COMPACT_VIEWS[tool_name],
            )
        )
    return specs


SPECS: list[ToolSpec] = _build_fengshui_specs()
