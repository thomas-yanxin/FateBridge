"""Monthly Zi Bai numbers and neutral position readings, independent of natal plates."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, cast

from .directions import rule_data, wrap9
from .models import MonthlyRequest
from .monthly_integrity import validate_monthly_layer
from .monthly_time import solar_month_context


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            (Path(__file__).parents[2] / "data/fengshui/monthly-v1.json").read_text()
        ),
    )


def monthly_provenance() -> Dict[str, Any]:
    data = _bundle()
    return {
        **deepcopy(data["ruleset"]),
        "bundle_version": data["bundle_version"],
        "sources": [
            dict(source_id=k, **deepcopy(data["sources"][k]))
            for k in data["ruleset"]["source_ids"]
        ],
    }


def monthly_position_reading(layer: Dict[str, Any]) -> Dict[str, Any]:
    """Consume already calculated fields; no fresh clock or star computation."""
    statements: list[dict[str, Any]] = []
    if layer["status"] == "complete":
        time = layer["time_context"]
        statements.append(
            {
                "target_path": "layers.monthly_stars.time_context",
                "text": f"月紫白采用立春后有效年{time['effective_solar_year']}（{layer['year_branch']}年）、第{time['solar_month_number']}节月（{time['month_branch']}月），有效期{time['valid_from']}至{time['valid_until']}，起点含、终点不含；入中星为{layer['center_star_number']}。月份序号不等于公历月或农历月。",
            }
        )
        for direction, palace in layer["palaces"].items():
            statements.append(
                {
                    "target_path": f"layers.monthly_stars.palaces.{direction}",
                    "text": f"{direction}宫固定宫数{palace['palace_number']}，本节月飞临月星{palace['monthly_star_number']}（{palace['monthly_star']['name']}，{palace['monthly_star']['element']}）。",
                }
            )
    else:
        text = "尚不能确认唯一的有效年／节月组合，未给出唯一月盘；保留本次缺项或交节候选，不使用当前日期或公历月补值。"
        time = layer["time_context"]
        if time.get("provisional_interval") is not None:
            windows = "；".join(
                f"有效年{candidate['effective_solar_year']}第{candidate['solar_month_number']}节月（{candidate['month_branch']}月），{candidate['valid_from']}至{candidate['valid_until']}"
                for candidate in time["candidate_months"]
            )
            text += f"候选有效期：{windows}，各区间起点含、终点不含；暂取区间不表示月份已确认。"
        statements.append(
            {
                "target_path": "layers.monthly_stars.time_context",
                "text": text,
            }
        )
    context = [
        key
        for key in (
            "status",
            "time_context",
            "year_branch",
            "year_group",
            "center_star_number",
            "trace",
            "ruleset",
            "limitations",
            "missing_inputs",
        )
        if key in layer
    ]
    for statement in statements:
        target = statement["target_path"].removeprefix("layers.monthly_stars.")
        value: Any = layer
        for key in target.split("."):
            value = value[key]
        paths = [f"layers.monthly_stars.{key}" for key in context]
        basis = {path: deepcopy(layer[path.split(".")[-1]]) for path in paths}
        basis[statement["target_path"]] = deepcopy(value)
        statement.update(basis_paths=list(basis), basis=basis)
    return {
        "reading_id": "monthly_zibai_position_reading_v1",
        "version": "1.0.0",
        "statements": statements,
        "text": "\n".join(s["text"] for s in statements),
        "scope": "fixed_position_text_only_not_natal_reading_verification_or_reality_efficacy",
    }


def monthly_stars(req: MonthlyRequest) -> Dict[str, Any]:
    time = solar_month_context(
        req.effective_solar_year,
        req.solar_month_number,
        req.query_at,
        req.timezone_name,
    )
    year = time["effective_solar_year"]
    complete = year is not None and time["solar_month_number"] is not None
    result: Dict[str, Any] = {
        "status": "complete" if complete else "partial",
        "time_context": time,
        "palaces": {},
        "ruleset": monthly_provenance(),
        "missing_inputs": (
            [
                (
                    "monthly_stars.confirmed_solar_month_due_to_boundary_precision"
                    if time.get("month_status") == "requires_confirmation"
                    else "monthly_stars.query_at_or_confirmed_effective_solar_year_and_solar_month"
                )
            ]
            if not complete
            else []
        ),
        "interpretation_scope": "monthly_positions_only_no_house_verdict_or_annual_natal_overwrite",
        "limitations": [
            "节月独立于公历月与农历月，年支采用立春后的有效年。",
            "原整理本六月节候栏印作大暑、小暑；原样差异保留，时序独立采用小暑起月、大暑为中气。",
            "原书全本、年/月叠加断事、日时紫白、布局处方及现实预测尚未由本层验证。",
        ],
    }
    if complete:
        assert year is not None
        branch = tuple("子丑寅卯辰巳午未申酉戌亥")[(year - 4) % 12]
        group = next(g for g in _bundle()["year_groups"] if branch in g["branches"])
        month = time["solar_month_number"]
        center = wrap9(group["first_month_center"] - month + 1)
        stars = rule_data("annual_stars")
        directions = rule_data("directions")
        palaces = {}
        for index, direction in enumerate(rule_data("flight_path")):
            number = wrap9(center + index)
            # Share number/name/element identities, not the foundation table's
            # generic polarity labels or annual prescriptions.
            palaces[direction] = {
                **directions.get(
                    direction,
                    {
                        "direction": "C",
                        "label": "中",
                        "palace_number": 5,
                        "trigram": None,
                        "element": "土",
                    },
                ),
                "monthly_star_number": number,
                "monthly_star": {k: stars[str(number)][k] for k in ("name", "element")},
                "method": "monthly_stars",
                "rule_id": "monthly_zibai_jie_v1.reverse_month_forward_palace",
                "source_ids": ["MP1", "MP2"],
            }
        result.update(
            year_branch=branch,
            year_group=deepcopy(group),
            center_star_number=center,
            palaces=palaces,
            flight_path=rule_data("flight_path"),
            trace={
                "year_branch_epoch": "4_CE_JiaZi_modulo_12",
                "month_center_direction": "descending",
                "within_month_flight": "ascending",
                "year_boundary": "lichun",
                "month_boundary": "twelve_jie",
            },
        )
    validate_monthly_layer(result, req)
    result["position_reading"] = monthly_position_reading(result)
    return result
