"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.cli as cli
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.gauquelin import method_profile
from scripts.evaluate_agent import (
    _without_evaluation_private_sections,
    prepare_workspace,
)
from scripts.evaluation.audit_gauquelin_definitions import (
    BASELINE_POLICY,
    BASELINE_POLICY_SHA256,
    PROTOCOL,
    PROTOCOL_SHA256,
    read_baseline,
)
from tests.evaluation.test_gauquelin_request_guard import HOUSE_SPECS, payload


def test_reviewer_artifacts_stay_in_snapshot_but_outside_the_model_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("Runtime instructions")
    paths = {
        "skills/onda-shiye/SKILL.md": "Runtime consultation skill",
        "src/fatebridge/domain.py": "Executable backend",
        "docs/contracts/bazi_career.json": "Actual runtime contract",
        "docs/scenario-routing.md": "Runtime routing",
        "docs/numerology-audit.md": "Public calculation and source audit",
        "docs/validation/old-answer.txt": "HIDDEN_EXPECTED_ANSWER",
        "docs/validation/nested/grade.json": "HIDDEN_GRADE",
        "docs/reviews/review.md": "HIDDEN_REVIEW",
        "docs/agent-evaluation.md": "HIDDEN_EVALUATOR_CRITERIA",
        "docs/numerology-semantics-preparation.md": "HIDDEN_NUMEROLOGY_PRIOR_GRADES",
        "docs/bazi-semantics-evaluation.md": "HIDDEN_BAZI_CRITERIA",
        "docs/liuren-jinkou-audit.md": "HIDDEN_REN_FIRST_GRADES_AND_REVIEW",
        "tests/fixtures/agent_behavior/cases.json": "HIDDEN_DATASET",
    }
    for name, value in paths.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    for name, value in paths.items():
        assert (source / name).read_text() == value
        if value.startswith("HIDDEN_"):
            assert not (workspace / name).exists()
        else:
            assert (workspace / name).read_text() == value
    assert (
        workspace / ".agents/skills/onda-shiye/SKILL.md"
    ).read_text() == "Runtime consultation skill"


def test_explicit_grade_spans_are_removed_without_losing_public_source_or_limits(
    tmp_path,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("Runtime instructions")
    for name in ("src", "skills", "docs"):
        (source / name).mkdir()
    body = (
        "Verified public source facts.\n"
        "<!-- agent-evaluation-private:start -->\n"
        "HIDDEN_PREVIOUS_MODEL_GRADE\n"
        "<!-- agent-evaluation-private:end -->\n"
        "Whole-book alignment remains incomplete.\n"
    )
    path = source / "docs/public-audit.md"
    path.write_text(body)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    visible = (workspace / "docs/public-audit.md").read_text()
    assert "HIDDEN_PREVIOUS_MODEL_GRADE" not in visible
    assert "Verified public source facts." in visible
    assert "Whole-book alignment remains incomplete." in visible
    assert path.read_text() == body


@pytest.mark.parametrize(
    "text",
    [
        "<!-- agent-evaluation-private:start -->unfinished",
        "unopened<!-- agent-evaluation-private:end -->",
        "<!-- agent-evaluation-private:start --><!-- agent-evaluation-private:start -->nested<!-- agent-evaluation-private:end -->",
    ],
)
def test_unbalanced_private_markers_fail_closed_instead_of_leaking_or_guessing(text):
    with pytest.raises(ValueError, match="Unbalanced"):
        _without_evaluation_private_sections(text)


def test_all_live_house_system_tools_reject_g_on_three_transports(
    monkeypatch, capsys, tmp_path
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("unsupported36-sector request reached calculation")

    monkeypatch.setattr("fatebridge.transports.rest.execute_tool", forbidden)
    monkeypatch.setattr("fatebridge.transports.mcp.execute_tool", forbidden)
    monkeypatch.setattr(cli, "execute_tool", forbidden)
    rest = TestClient(api.app)
    results = []

    async def exercise():
        async with Client(create_mcp_app()) as client:
            for index, spec in enumerate(HOUSE_SPECS):
                values = ("G", "gauquelin_sectors", "Ｇ")
                value = values[index % len(values)]
                request = {**payload(spec), "house_system": value}
                response = rest.post(spec.rest_path, json=request)
                subject = tmp_path / f"{spec.key}.json"
                subject.write_text(
                    json.dumps(
                        {k: v for k, v in request.items() if k != "house_system"}
                    )
                )
                capsys.readouterr()
                code = cli.run(
                    [
                        spec.tool_name,
                        "--subject-file",
                        str(subject),
                        "--house-system",
                        value,
                    ]
                )
                local = json.loads(capsys.readouterr().out)
                protocol = await client.call_tool(
                    spec.tool_name, request, raise_on_error=False
                )
                native = json.loads(protocol.content[0].text)
                assert (
                    response.status_code == 422 and code == 1 and protocol.is_error
                ), spec.key
                bodies = [response.json(), local, native]
                for error in bodies:
                    assert error["error_code"] == "validation_error", (spec.key, error)
                    assert error["retryable"] is False
                    assert "run_metadata" not in error
                    assert error["issues"][0]["path"] == "house_system", error
                    assert (
                        error["issues"][0]["code"] == "unsupported_house_system"
                    ), error
                    assert (
                        "36" in error["error"] and "Gauquelin" in error["error"]
                    ), error
                results.append(spec.key)

    asyncio.run(exercise())
    assert results == [s.key for s in HOUSE_SPECS]


@pytest.mark.parametrize("method", range(6))
def test_each_method_reports_its_source_defined_observer_and_horizon(method):
    profile = method_profile(method)
    assert profile["requested_topocentric_flag"] is False
    assert profile["observer_origin"] == ("geocentric" if method < 2 else "topocentric")
    assert profile["atmosphere_inputs_used"] == (method in (3, 5))
    assert profile["disk_reference"] == (
        "position_point"
        if method < 2
        else "center" if method in (2, 3) else "upper_limb"
    )
    assert profile["historical_cfepp_method_identified"] is False


@pytest.mark.parametrize("method", [True, False, -1, 6, 2.0, "2", None])
def test_method_selection_does_not_coerce_invalid_definitions(method):
    with pytest.raises(ValueError):
        method_profile(method)


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("method", range(6))
@pytest.mark.parametrize("body_name", ["MOON", "MARS"])
def test_actual_native_observer_and_atmosphere_follow_the_reported_policy(
    method, body_name
):
    swe = runtime.swe
    body = getattr(swe, body_name)

    def position(*, height=0.0, topo=False, pressure=1013.25, temperature=0.0):
        # These are fictional controls in a test process, never a birth estimate.
        runtime.ephemeris_call("set_topo", 0.0, 45.0, height)
        return runtime.ephemeris_call(
            "gauquelin_sector",
            2451545.0,
            body,
            method,
            (0.0, 45.0, height),
            pressure,
            temperature,
            swe.FLG_MOSEPH | (swe.FLG_TOPOCTR if topo else 0),
        )

    base = position()
    with_flag = position(topo=True)
    raised = position(height=10000.0)
    reduced_pressure = position(pressure=800.0)
    warmer = position(temperature=30.0)
    profile = method_profile(method)
    if profile["observer_origin"] == "geocentric":
        assert base != with_flag
        assert base == raised
    else:
        assert base == with_flag
        assert base != raised
    if profile["atmosphere_inputs_used"]:
        assert base != reduced_pressure and base != warmer
    else:
        assert base == reduced_pressure == warmer


def test_diagnostic_protocol_and_baseline_remain_pinned():
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert (
        hashlib.sha256(BASELINE_POLICY.read_bytes()).hexdigest()
        == BASELINE_POLICY_SHA256
    )
    with pytest.raises(ValueError, match="baseline_hash_mismatch"):
        read_baseline(b'{"rows": []}')
