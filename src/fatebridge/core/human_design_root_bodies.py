"""Evaluate and replay actual design activations at final numeric root epochs.

The two TT endpoints are not a physical uncertainty interval. Equal endpoint
results do not certify continuous stability or an authentic native execution.
"""

from copy import deepcopy
from typing import Any

from fatebridge.core.human_design_mechanics import (
    VALID_PROFILES,
    bodygraph,
    longitude_activation,
    positions_at_tt,
)
from fatebridge.core.human_design_native_positions import (
    DIRECT_BODIES,
    SCALARS,
    decode_native_positions,
    pack_native_positions,
)
from fatebridge.core.human_design_root_interpretations import root_interpretations
from fatebridge.core.human_design_variables import variables_from_activations
from fatebridge.utils.json_values import same_value as _same_value

METHOD = "human_design_actual_design_root_endpoint_bodies_v1"
ROLE = "root_bracket_activation"
LEVELS = ("gate", "line", "color", "tone", "base")
SCOPE = "固定当前人格激活，分别推导最终数值根实际1或2个二进制TT端点的13项设计激活、结构和Variable；所选设计位置复用原始主盘，另一端点实际计算。不把两端当作物理误差界，不认证连续区间稳定、出生钟、原生执行或现实预测；候选整盘各自推导，不能拼接。主盘仍按原太阳弧最小残差规则选择。"


def _structure(
    personality: list[dict[str, Any]], design: list[dict[str, Any]]
) -> dict[str, Any]:
    graph = bodygraph((a["gate"] for a in personality), (a["gate"] for a in design))
    suns = [
        next(a for a in rows if a["body"] == "Sun") for rows in (personality, design)
    ]
    profile = f"{suns[0]['line']}/{suns[1]['line']}"
    return {
        **{
            k: graph[k]
            for k in (
                "type",
                "subtype",
                "authority",
                "strategy",
                "definition",
                "channels",
            )
        },
        "center_statuses": {k: v["status"] for k, v in graph["centers"].items()},
        "profile": profile,
        "profile_in_declared_pairs": profile in VALID_PROFILES,
        "cross_gates": [
            next(a["gate"] for a in rows if a["body"] == body)
            for rows in (personality, design)
            for body in ("Sun", "Earth")
        ],
        "variable_code": variables_from_activations(
            {"personality": personality, "design": design}
        )["code"],
    }


def derive_root_body_assessment(
    solver: dict[str, Any],
    personality: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    node_mode: str,
    evaluations: list[dict[str, Any]],
    *,
    require_swiss_files: bool,
    physical_backend_policy: str = "auto",
) -> dict[str, Any]:
    """Pure replay; the caller owns original coordinates and root witnesses."""
    root = solver["numerical_precision"]
    expected_times = sorted({root[key]["jd_tt"] for key in ("lower", "upper")})
    chosen = solver["design_jd_tt"]
    if (
        not isinstance(evaluations, list)
        or len(evaluations) != len(expected_times)
        or chosen not in expected_times
    ):
        raise ValueError("Missing or invented root endpoint evaluation")
    decoded = []
    for epoch, tt in zip(evaluations, expected_times):
        expected_role = "activation" if tt == chosen else ROLE
        if (
            set(epoch) != {"jd_tt", "native_positions", "source_role"}
            or type(epoch["jd_tt"]) is not float
            or epoch["jd_tt"] != tt
            or epoch["source_role"] != expected_role
        ):
            raise ValueError("Root endpoint detached from its native scalar witness")
        rows = decode_native_positions(
            epoch["native_positions"],
            node_mode,
            require_swiss_files=require_swiss_files,
            physical_backend_policy=physical_backend_policy,
        )
        if tt == chosen and not _same_value(rows, selected):
            raise ValueError(
                "Selected root endpoint differs from original design activations"
            )
        decoded.append(rows)
    first, last = decoded[0], decoded[-1]
    changes = [
        {
            "body": a["body"],
            "levels": [k for k in LEVELS if a[k] != b[k]],
            "lower": {k: a[k] for k in LEVELS},
            "upper": {k: b[k] for k in LEVELS},
        }
        for a, b in zip(first, last)
        if any(a[k] != b[k] for k in LEVELS)
    ]
    structures = [_structure(personality, rows) for rows in decoded]
    changed_fields = [
        k for k in structures[0] if not _same_value(structures[0][k], structures[-1][k])
    ]
    solar_differences = []
    for key, rows in (("lower", first), ("upper", last)):
        function = longitude_activation(root[key]["sun_longitude"])
        actual = rows[0]
        levels = [k for k in LEVELS if function[k] != actual[k]]
        if levels:
            solar_differences.append(
                {
                    "endpoint": key,
                    "levels": levels,
                    "root_function": {k: function[k] for k in LEVELS},
                    "actual_activation": {k: actual[k] for k in LEVELS},
                }
            )
    return {
        "method_id": METHOD,
        "node_mode": node_mode,
        "direct_body_order": list(DIRECT_BODIES),
        "native_scalar_order": list(SCALARS),
        "evaluations": evaluations,
        "evaluated_tt_count": len(evaluations),
        "selected_evaluation_index": expected_times.index(chosen),
        "endpoint_structures": structures,
        "endpoint_interpretations": root_interpretations(personality, decoded),
        "observed_activation_changes": changes,
        "observed_changed_levels": [
            k for k in LEVELS if any(k in r["levels"] for r in changes)
        ],
        "observed_structure_changed_fields": changed_fields,
        "solar_function_activation_subdivision_differences": solar_differences,
        "continuous_interval_stability_certified": False,
        "physical_time_accuracy_certified": False,
        "native_execution_authenticated": False,
        "scope": SCOPE,
    }


def assess_design_root_bodies(
    solver: dict[str, Any],
    personality: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    node_mode: str,
    *,
    require_swiss_files: bool,
    backend: str,
) -> dict[str, Any]:
    root = solver["numerical_precision"]
    chosen = solver["design_jd_tt"]
    evaluations = []
    for tt in sorted({root[key]["jd_tt"] for key in ("lower", "upper")}):
        if tt == chosen:
            native = pack_native_positions(selected)
        else:
            raw = positions_at_tt(
                tt,
                node_mode,
                require_swiss_files=require_swiss_files,
                backend=backend,
                source_role=ROLE,
            )
            native = pack_native_positions([{"body": b, **r} for b, r in raw.items()])
        evaluations.append(
            {
                "jd_tt": tt,
                "native_positions": native,
                "source_role": "activation" if tt == chosen else ROLE,
            }
        )
    return derive_root_body_assessment(
        solver,
        personality,
        selected,
        node_mode,
        evaluations,
        require_swiss_files=require_swiss_files,
    )


def root_body_summary(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        **{
            k: deepcopy(assessment[k])
            for k in (
                "method_id",
                "evaluated_tt_count",
                "selected_evaluation_index",
                "observed_activation_changes",
                "observed_structure_changed_fields",
                "solar_function_activation_subdivision_differences",
                "continuous_interval_stability_certified",
                "physical_time_accuracy_certified",
                "native_execution_authenticated",
                "scope",
            )
        },
        "candidates": [
            {
                k: row[k]
                for k in ("type", "subtype", "authority", "profile", "variable_code")
            }
            for row in assessment["endpoint_structures"]
        ],
        "evaluated_jd_tt": [r["jd_tt"] for r in assessment["evaluations"]],
        "interpretation_summary": deepcopy(
            assessment["endpoint_interpretations"]["summary"]
        ),
    }
