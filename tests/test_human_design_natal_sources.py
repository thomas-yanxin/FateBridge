"""Runtime source changes, partial file contexts and supplied-metadata boundaries."""

import json
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import runtime
from fatebridge.core.human_design_natal_sources import NatalSourceTrace
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_natal_sources import verify_natal_sources
from scripts.check_human_design_natal_sources import (
    PLAN_PATH,
    isolated_source_change,
    regression_checks,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
PLAN = json.loads(PLAN_PATH.read_text())


def test_four_frozen_probes_and_prior_native_rejection_remain():
    check = regression_checks()
    assert check["original_accepted_count"] == 3
    assert check["original_native_rejected_count"] == 1
    assert len(check["cases"]) == 4
    assert check["status"] == "bounded_natal_source_checks_passed", check


@pytest.mark.parametrize("kind", [c["id"] for c in PLAN["cases"]])
@pytest.mark.native_engine_fault
def test_source_change_is_explicit_even_without_optional_cycles(tmp_path, kind):
    with isolated_source_change(kind, tmp_path) as state:
        result = calculate_human_design(**PLAN["birth_input"])
        assert state["mutation_performed"]
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"][0]["code"] in {
            "changed_during",
            "edition_changed",
            "physical_configuration_changed",
        }
        assert str(tmp_path) not in json.dumps(result)


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(SPEC, SPEC.request_model(**PLAN["birth_input"]))


@pytest.mark.parametrize(
    "kind",
    [
        "delete",
        "scope",
        "atomic",
        "accuracy",
        "native_auth",
        "config",
        "hash_checked",
        "total_count",
        "wrong_model",
        "wrong_body",
        "wrong_role",
        "wrong_tt",
        "missing_file",
        "unused_file",
        "fake_manifest",
        "fake_id",
        "wrong_slot",
        "wrong_prefix",
        "empty_contexts",
        "duplicate_context",
        "bad_count",
        "bool_tt",
        "analytical_file",
        "identity_status",
        "unresolved_omitted",
        "unresolved_required_slot",
        "unresolved_bool",
    ],
)
def test_rehashed_source_metadata_cannot_claim_more_than_observed(complete, kind):
    p = deepcopy(complete)
    s = p["ephemeris_source_evidence"]
    context = s["contexts"][0]
    if kind == "delete":
        del p["ephemeris_source_evidence"]
    elif kind == "scope":
        s["scope"] = "全部物理精度及原生执行均认证。"
    elif kind == "atomic":
        s["atomic_file_read_proven"] = True
    elif kind == "accuracy":
        s["accuracy_certified"] = True
    elif kind == "native_auth":
        s["native_execution_authenticated"] = True
    elif kind == "config":
        s["configuration_checked"] = False
    elif kind == "hash_checked":
        s["endpoint_file_hashes_checked"] = False
    elif kind == "total_count":
        s["observed_native_position_evaluations"] += 1
    elif kind == "wrong_model":
        context["native_return_flag_model"] = "moshier"
    elif kind == "wrong_body":
        context["body"] = "Chiron"
    elif kind == "wrong_role":
        context["role"] = "certified_read"
    elif kind == "wrong_tt":
        for row in s["contexts"]:
            row["minimum_jd_tt"] = row["maximum_jd_tt"] = 2451545.0
    elif kind == "missing_file":
        s["files"].pop()
    elif kind == "unused_file":
        r = deepcopy(s["files"][0])
        r["sha256"] = "0" * 64
        r["id"] = "se1:0:" + r["sha256"]
        s["files"].append(r)
        s["files"].sort(key=lambda x: x["id"])
    elif kind == "fake_manifest":
        s["files"][0]["matches_packaged_manifest"] = False
    elif kind == "fake_id":
        s["files"][0]["id"] = "unverified"
    elif kind == "wrong_slot":
        s["files"][0]["slot"] = 2
    elif kind == "wrong_prefix":
        s["files"][0]["id"] = s["files"][0]["id"].replace("se1:", "jpl:")
    elif kind == "empty_contexts":
        s["contexts"] = []
    elif kind == "duplicate_context":
        s["contexts"].append(deepcopy(context))
    elif kind == "bad_count":
        context["observed_evaluation_count"] = True
    elif kind == "bool_tt":
        context["minimum_jd_tt"] = True
    elif kind == "analytical_file":
        context["status"] = "analytical_mean_node"
    elif kind == "unresolved_omitted":
        del context["unresolved_slots"]
    elif kind == "unresolved_required_slot":
        context["unresolved_slots"] = [0]
    elif kind == "unresolved_bool":
        context["unresolved_slots"] = [True]
    else:
        s["has_unidentified_sources"] = True
    p["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in p.items() if k != "run_metadata"}
    )
    assert verify_natal_sources(p)["errors"], kind
    assert verify_human_design_reading(p)["status"] == "rejected", kind


def test_complete_source_context_check_never_reopens_native_ephemeris(
    complete, monkeypatch
):
    def forbidden(*a, **k):
        raise AssertionError("Supplied-source verification called native engine")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(runtime.swe, "get_current_file_data", forbidden)
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_nominal_native_source_count"] == 22
    assert (
        complete["ephemeris_source_evidence"]["native_execution_authenticated"] is False
    )
    assert str(ROOT) not in json.dumps(complete["ephemeris_source_evidence"])


@pytest.mark.parametrize(
    "files", [[], ["semo_18.se1"], ["sepl_18.se1"], ["semo_18.se1", "sepl_18.se1"]]
)
@pytest.mark.parametrize("mode", ["true", "mean"])
def test_builtin_partial_and_full_file_contexts_remain_valid(
    tmp_path, monkeypatch, files, mode
):
    for name in files:
        shutil.copy2(ROOT / "ephe" / name, tmp_path / name)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    p = execute_tool(
        SPEC,
        SPEC.request_model(
            **PLAN["birth_input"], node_mode=mode, birth_time_uncertainty_minutes=1
        ),
    )
    if files == ["sepl_18.se1"]:
        # A top-level SWIEPH flag cannot exclude an analytical Moon
        # dependency. The current physical-source contract fails closed.
        assert p["error_code"] == "ephemeris_source_inconsistent"
        assert p["status_code"] == 503 and p["retryable"] is False
        assert p["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "swiss_dependency_unavailable"}
        ]
        assert verify_human_design_reading(p)["status"] == "rejected"
        assert "ephemeris_source_evidence" not in p
        return
    check = verify_human_design_reading(p)
    assert check["status"] == "verified_fixed_template_reading", check
    contexts = p["ephemeris_source_evidence"]["contexts"]
    if mode == "mean":
        node_statuses = {
            c["status"]
            for c in contexts
            if c["body"] == "NorthNode" and c["role"] == "activation"
        }
        assert "analytical_mean_node" in node_statuses
        assert node_statuses & {
            "library_builtin",
            "file_contexts_observed",
        }  # explicit true-node counterfactual is also retained
    if len(files) == 1:
        assert p["ephemeris_source_evidence"]["status"] == "identity_incomplete"
        assert any(c["unresolved_slots"] for c in contexts)
    if not files:
        assert p["ephemeris_source_evidence"]["files"] == []
        assert {c["status"] for c in contexts} <= {
            "analytical_mean_node",
            "library_builtin",
        }


def test_missing_introspection_is_explicit_not_certified(monkeypatch):
    monkeypatch.setattr(runtime, "swe", SimpleNamespace())
    trace = NatalSourceTrace()
    trace.observe_native("Sun", 2451545.0, 258, "activation", False)
    p = trace.finish()
    assert (
        p["status"] == "identity_incomplete" and p["has_unidentified_sources"] is True
    )
    assert p["files"] == [] and p["native_execution_authenticated"] is False


@pytest.mark.parametrize("mode", ["true", "mean"])
def test_strict_jpl_header_contexts_keep_node_analytical_role(
    tmp_path, monkeypatch, mode
):
    kernel = ROOT / "tests/fixtures/human-design-de441-j2000.eph"
    shutil.copy2(kernel, tmp_path / kernel.name)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", kernel.name)
    p = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
            node_mode=mode,
        ),
    )
    checked = verify_human_design_reading(p)
    assert checked["status"] == "verified_fixed_template_reading", checked
    assert p["ephemeris_source_evidence"]["files"]
    assert all(
        f["id"].startswith("jpl:0:") and f["de_number"] == 441
        for f in p["ephemeris_source_evidence"]["files"]
    )


def test_strict_swiss_refuses_unidentified_context_instead_of_certifying_flags(
    monkeypatch,
):
    monkeypatch.setattr(runtime, "swe", SimpleNamespace())
    trace = NatalSourceTrace(require_swiss_files=True)
    from fatebridge.utils.errors import EphemerisSourceError

    with pytest.raises(EphemerisSourceError):
        trace.observe_native("Sun", 2451545.0, 258, "activation", False)
