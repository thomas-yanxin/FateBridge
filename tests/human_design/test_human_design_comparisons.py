"""Keep all original accepted forgeries and verify complete node diagnostics."""

from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_precision as precision
from fatebridge.core.human_design_node_comparisons import reconstruct_node_reference
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_comparisons import (
    verify_node_comparison_reports,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(SPEC, SPEC.request_model(**INPUT))


MUTATIONS = [
    "node_difference",
    "node_selected_longitude",
    "node_reference_longitude",
    "node_reference_flag",
    "node_time",
    "node_backend_change_levels",
    "node_rows_removed",
    "node_backend_false_unavailable",
    "node_backend_independence_label",
    "convention_selected",
    "convention_alternative",
    "convention_activations_removed",
    "convention_provenance_time_corrected",
    "node_witness_missing",
    "convention_witness_missing",
    "node_witness_tt",
    "node_witness_flag",
    "node_witness_nan",
    "node_witness_bool",
    "node_witness_duplicate_side",
    "node_witness_extra",
    "convention_witness_tt",
    "convention_witness_flag",
    "convention_witness_longitude",
    "convention_provenance_flag",
    "backend_mechanics_activations",
    "backend_variable_code",
    "backend_source_url",
    "backend_published_bound",
    "backend_scope",
    "convention_scope",
    "text",
]


def alter(value, kind):
    node = value["node_backend_comparison"]
    conv = value["node_convention_comparison"]
    if kind == "node_difference":
        node["rows"][0]["difference_arcseconds"] = 9999.0
    elif kind == "node_selected_longitude":
        node["rows"][0]["selected_longitude"] = 123.0
    elif kind == "node_reference_longitude":
        node["rows"][0]["reference_longitude"] = 123.0
    elif kind == "node_reference_flag":
        node["rows"][0]["reference_return_flags"] = 2
    elif kind == "node_time":
        node["rows"][0]["jd_tt"] = 2451545.0
    elif kind == "node_backend_change_levels":
        node["changed_levels"] = ["gate", "line"]
    elif kind == "node_rows_removed":
        node["rows"] = []
    elif kind == "node_backend_false_unavailable":
        node["status"] = "reference_unavailable"
    elif kind == "node_backend_independence_label":
        node["status"] = "same_backend_not_independent"
    elif kind == "convention_selected":
        conv["selected"] = "mean"
    elif kind == "convention_alternative":
        conv["alternative"] = "true"
    elif kind == "convention_activations_removed":
        conv["changed_activations"] = []
    elif kind == "convention_provenance_time_corrected":
        conv["provenance"]["after"]["tt_epochs"]["personality"] = 2451545.0
    elif kind == "node_witness_missing":
        del node["reference_node_positions"]
    elif kind == "convention_witness_missing":
        del conv["reference_node_positions"]
    elif kind == "node_witness_tt":
        node["reference_node_positions"]["personality"]["jd_tt"] += 1 / 86400
    elif kind == "node_witness_flag":
        node["reference_node_positions"]["personality"]["return_flags"] = 258
    elif kind == "node_witness_nan":
        node["reference_node_positions"]["personality"]["longitude"] = float("nan")
    elif kind == "node_witness_bool":
        node["reference_node_positions"]["personality"]["longitude_speed"] = False
    elif kind == "node_witness_duplicate_side":
        node["reference_node_positions"]["design"] = deepcopy(
            node["reference_node_positions"]["personality"]
        )
    elif kind == "node_witness_extra":
        node["reference_node_positions"]["source_authenticated"] = True
    elif kind == "convention_witness_tt":
        conv["reference_node_positions"]["design"]["jd_tt"] += 1 / 86400
    elif kind == "convention_witness_flag":
        conv["reference_node_positions"]["design"]["return_flags"] = 2
    elif kind == "convention_witness_longitude":
        conv["reference_node_positions"]["design"]["longitude"] += 0.25
    elif kind == "convention_provenance_flag":
        conv["provenance"]["after"]["return_flags"]["design"]["NorthNode"] = 260
    elif kind == "backend_mechanics_activations":
        node["mechanical_comparison"]["changed_activations"] = []
    elif kind == "backend_variable_code":
        node["mechanical_comparison"]["variable_codes"]["after"] = "PP PP"
    elif kind == "backend_source_url":
        node["source_url"] = "https://example.invalid/unverified"
    elif kind == "backend_published_bound":
        node["published_difference"]["kind"] = "certified_error_bound"
    elif kind == "backend_scope":
        node["scope"] = "全部节点误差已认证。"
    elif kind == "convention_scope":
        conv["scope"] = "按照更符合自我感觉的一盘选择。"
    elif kind == "text":
        value["interpretation"][
            "node_comparison_meaning"
        ] = "所有交点计算均已独立认证。"
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", MUTATIONS)
def test_all_rehashed_false_diagnostic_reports_are_rejected(complete, kind):
    forged = deepcopy(complete)
    alter(forged, kind)
    if kind != "text":
        assert verify_node_comparison_reports(forged)["errors"], kind
    if kind == "node_witness_nan":
        with pytest.raises(ValueError):
            digest({k: v for k, v in forged.items() if k != "run_metadata"})
        return
    forged["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in forged.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(forged)["status"] == "rejected", kind


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_all_native_outcomes_reconstruct_without_ephemeris_calls(
    monkeypatch, tmp_path, empty, node_mode
):
    if empty:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    else:
        monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    run = execute_tool(SPEC, SPEC.request_model(**INPUT, node_mode=node_mode))

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic replay must not recalculate the sky")

    monkeypatch.setattr(precision.runtime, "ephemeris_call", forbidden)
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_node_report_count"] == 2
    assert run["interpretation"]["statements"][8]["id"] == "node_comparisons"
    assert run["interpretation"]["statements"][9]["id"] == "birth_interval"
    assert check["checked_statement_count"] == 10
    assert "不是另一后端的完整重排" in run["node_backend_comparison"]["scope"]


def test_counterfactual_reconstruction_keeps_every_non_node_and_does_not_mutate(
    complete,
):
    before = deepcopy(complete)
    proof = complete["node_convention_comparison"]["reference_node_positions"]
    ref = reconstruct_node_reference(complete, proof, "mean")
    assert complete == before
    for side in ("personality", "design"):
        a = [
            r
            for r in complete["activations"][side]
            if r["body"] not in {"NorthNode", "SouthNode"}
        ]
        b = [
            r
            for r in ref["activations"][side]
            if r["body"] not in {"NorthNode", "SouthNode"}
        ]
        assert a == b
    assert ref["time_scales"] == complete["time_scales"]


def test_unavailable_outcome_has_no_dangling_positive_reference(monkeypatch, complete):
    def unavailable(*args, **kwargs):
        raise RuntimeError("controlled reference unavailable")

    monkeypatch.setattr(precision.runtime, "ephemeris_call", unavailable)
    value = deepcopy(complete)
    value["node_backend_comparison"] = precision.compare_node_backends(value, "true")
    assert value["node_backend_comparison"]["status"] == "reference_unavailable"
    assert verify_node_comparison_reports(value)["errors"] == []
    assert value["node_backend_comparison"]["reference_node_positions"] is None
    value["node_backend_comparison"]["reference_node_positions"] = {}
    assert verify_node_comparison_reports(value)["errors"]


@pytest.mark.native_engine_fault
def test_actual_public_unavailable_report_and_reading_are_verified(monkeypatch):
    original = precision.runtime.ephemeris_call

    def native(operation, *args, **kwargs):
        if (
            operation == "calc"
            and args[1] == precision.runtime.swe.TRUE_NODE
            and args[2] & precision.runtime.swe.FLG_MOSEPH
        ):
            raise RuntimeError("controlled node reference failure")
        return original(operation, *args, **kwargs)

    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.setattr(precision.runtime, "ephemeris_call", native)
    run = execute_tool(SPEC, SPEC.request_model(**INPUT))
    assert run["node_backend_comparison"]["status"] == "reference_unavailable"
    assert "缺项不代表两者一致" in run["interpretation"]["node_comparison_meaning"]
    assert (
        verify_human_design_reading(run)["status"] == "verified_fixed_template_reading"
    )


@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_real_strict_jpl_reports_and_explanations_reconstruct(
    monkeypatch, tmp_path, node_mode
):
    kernel = ROOT / "tests/fixtures/human-design-de441-j2000.eph"
    target = tmp_path / kernel.name
    target.write_bytes(kernel.read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", target.name)
    run = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
            node_mode=node_mode,
        ),
    )
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_node_report_count"] == 2
    assert run["calculation_policy"]["physical_backend_policy"] == "strict_jpl"
    if node_mode == "true":
        assert (
            run["node_backend_comparison"]["reference_computation_performed"] is False
        )
        assert "未执行" in run["interpretation"]["node_comparison_meaning"]
    else:
        assert (
            run["node_backend_comparison"]["status"]
            == "analytic_mean_node_not_cross_validated"
        )
        assert "同一解析模型" in run["interpretation"]["node_comparison_meaning"]
