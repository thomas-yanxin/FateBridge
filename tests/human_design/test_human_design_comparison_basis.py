"""Selected-to-candidate ordering is independent of chronological ordering."""

import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design import chart_at_tt
from fatebridge.core.human_design_root_interpretations import (
    FAMILY_SCOPE,
    SCOPE,
    root_interpretations,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_solar_root import verify_solar_root_context

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-comparison-basis-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Pure comparison verification invoked native calculation")


def family(run):
    return run["design_solver"]["numerical_precision"]["local_root_family"]


def assert_basis(run):
    selected = run["design_solver"]["design_jd_tt"]
    for index, row in enumerate(family(run)["candidates"]):
        basis = row["comparison_basis"]
        interpretation = row["interpretation_from_selected"]
        assert basis == interpretation["comparison_basis"]
        assert basis["order"] == "selected_then_candidate"
        assert basis["personality_path"] == "activations.personality"
        assert basis["before"] == {
            "candidate_index": 0,
            "role": "selected",
            "jd_tt": selected,
            "design_path": "activations.design",
        }
        assert basis["after"] == {
            "candidate_index": 1,
            "role": "candidate",
            "jd_tt": row["jd_tt"],
            "design_path": (
                "design_solver.numerical_precision.local_root_family."
                f"candidates[{index}].native_positions"
            ),
        }
        assert basis["candidate_time_relation"] == (
            "earlier"
            if row["jd_tt"] < selected
            else "later" if row["jd_tt"] > selected else "same"
        )
        assert interpretation["scope"] == FAMILY_SCOPE
        assert (
            "before为所选主盘、after为当前数值候选盘，不按时刻重排"
            in interpretation["scope"]
        )
        assert "before/after分别指较早/较晚TT" not in interpretation["scope"]
        assert "设计由同索引evaluations重建" not in interpretation["scope"]


@pytest.mark.parametrize("mode", ["true", "mean"])
@pytest.mark.parametrize("backend", ["swieph", "moshier"])
def test_actual_public_output_and_original_endpoint_scope(
    mode, backend, monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "SE_EPHE_PATH", str(ROOT / "ephe" if backend == "swieph" else tmp_path)
    )
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(
        SPEC,
        SPEC.request_model(
            **{
                **{
                    "birth_year": 2390,
                    "birth_month": 1,
                    "birth_day": 1,
                    "birth_hour": 11,
                    "birth_minute": 58,
                    "birth_second": 1,
                    "birth_timezone": "UTC",
                    "node_mode": "true",
                },
                "node_mode": mode,
            }
        ),
    )
    if family(run):
        assert_basis(run)
    else:
        assert backend == "swieph"
    endpoints = run["design_solver"]["numerical_precision"][
        "design_body_endpoint_assessment"
    ]["endpoint_interpretations"]
    assert endpoints["scope"] == SCOPE
    assert "comparison_basis" not in endpoints
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert (
            verify_human_design_reading(run)["status"]
            == "verified_fixed_template_reading"
        )


@pytest.mark.parametrize("mode", ["true", "mean"])
def test_actual_platform_control_has_earlier_same_later_candidates(mode, monkeypatch):
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    # Platform-specific actual observations; the original public five above
    # are deliberately not relabeled as covering an earlier candidate.
    run = chart_at_tt(
        2385984.0 if sys.platform == "linux" else 2593990.0, mode, backend="moshier"
    )
    assert_basis(run)
    assert {
        r["comparison_basis"]["candidate_time_relation"]
        for r in family(run)["candidates"]
    } == {"earlier", "same", "later"}
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_solar_root_context(run)["errors"] == []


@pytest.fixture(scope="module")
def actual_public():
    with pytest.MonkeyPatch.context() as p:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            p.setenv("SE_EPHE_PATH", directory)
            p.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            return execute_tool(
                SPEC,
                SPEC.request_model(
                    **{
                        "birth_year": 2390,
                        "birth_month": 1,
                        "birth_day": 1,
                        "birth_hour": 11,
                        "birth_minute": 58,
                        "birth_second": 1,
                        "birth_timezone": "UTC",
                        "node_mode": "true",
                    }
                ),
            )


@pytest.mark.parametrize("target", ["outer", "interpretation"])
@pytest.mark.parametrize("kind", PLAN["negative_cases"])
def test_rehashed_detached_comparison_is_rejected_without_native(
    actual_public, kind, target
):
    run = deepcopy(actual_public)
    original_digest = digest({k: v for k, v in run.items() if k != "run_metadata"})
    row = family(run)["candidates"][1]
    interpretation = row["interpretation_from_selected"]
    value = row if target == "outer" else interpretation
    basis = value["comparison_basis"]
    if kind == "swap_epoch":
        basis["before"]["jd_tt"], basis["after"]["jd_tt"] = (
            basis["after"]["jd_tt"],
            basis["before"]["jd_tt"],
        )
    elif kind == "swap_role":
        basis["before"]["role"], basis["after"]["role"] = "candidate", "selected"
    elif kind == "false_chronology":
        basis["order"] = "earlier_then_later"
    elif kind == "missing_basis":
        del value["comparison_basis"]
    elif kind == "boolean_epoch":
        basis["before"]["jd_tt"] = True
    elif kind == "wrong_indices":
        basis["before"]["candidate_index"] = 1
    elif kind == "fake_source":
        basis["after"][
            "design_path"
        ] = "design_solver.numerical_precision.design_body_endpoint_assessment.evaluations[1]"
    else:
        if target == "interpretation":
            interpretation["scope"] = SCOPE
        else:
            basis["candidate_time_relation"] = (
                "later" if basis["candidate_time_relation"] == "earlier" else "earlier"
            )
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    assert run["run_metadata"]["business_output_sha256"] != original_digest
    with (
        patch.object(runtime, "ephemeris_call", forbidden),
        patch.object(native_execution, "calculate", forbidden),
    ):
        assert verify_human_design_reading(run)["status"] == "rejected"


@pytest.mark.parametrize(
    "epochs,index",
    [
        ((True, 1.0), 0),
        ((1.0, math.inf), 0),
        ((1.0, math.nan), 0),
        ((1.0,), 0),
        ([1.0, 2.0], 0),
        ((1.0, 2.0), True),
        ((1.0, 2.0), -1),
        (None, 0),
        ((1.0, 2.0), None),
    ],
)
def test_invalid_explicit_comparison_context_never_becomes_a_reading(epochs, index):
    with pytest.raises(ValueError):
        root_interpretations(
            [], [[], []], comparison_epochs=epochs, family_candidate_index=index
        )


@pytest.mark.parametrize("count", [0, 1, 3])
def test_selected_comparison_requires_exactly_two_charts(count):
    with pytest.raises(ValueError, match="requires two charts"):
        root_interpretations(
            [],
            [[] for _ in range(count)],
            comparison_epochs=(1.0, 2.0),
            family_candidate_index=0,
        )
