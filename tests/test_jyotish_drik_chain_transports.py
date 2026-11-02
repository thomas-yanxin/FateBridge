"""The verified internal Drik path preserves existing actual public results."""

import pytest

from fatebridge.core.jyotish_balas import verify_drik_evidence
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_same_run_D1_and_all_Drik_branches_survive_three_surfaces(
    monkeypatch, capsys, key
):
    payload = {**astro_payload(), "divisions": []}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    body = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        ["india.charts.D1", "india.strengths.drik_bala", "india.topic_evidence"],
    )
    india = body["india"]
    drik = india["strengths"]["drik_bala"]
    verify_drik_evidence(drik, india["charts"]["D1"])
    assert drik["source_witness"]["complete_single_original_accepted"] is False
    assert drik["nature_context"]["mercury_options"] == ["benefic", "malefic"]
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor.get("rule_id") == "jyotish.drik_bala_conditional.v2":
                context = factor["calculation_context"]
                assert context["scenario_count"] == len(drik["scenarios"])
                if context["value_status"] == "conditional_results":
                    assert factor["fact"] is None


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_internal_Drik_fault_is_not_bad_birth_input_on_three_surfaces(
    monkeypatch, capsys, tmp_path, key
):
    import asyncio
    import json

    from fastapi.testclient import TestClient
    from fastmcp import Client

    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.core import jyotish
    from fatebridge.mcp_server import create_mcp_app
    from tests.test_jyotish_transports import SPECS

    original = jyotish.other_balas

    def altered(raw):
        result = original(raw)
        result["drik_bala"]["matrix"]["Sun"]["Sun"] = False
        return result

    monkeypatch.setattr(jyotish, "other_balas", altered)
    payload = astro_payload()
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    spec = SPECS[key]
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(spec.rest_path, json=payload)

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(spec.tool_name, payload, raise_on_error=False)

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run([spec.tool_name, "--subject-file", str(request)])
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 503 and native.is_error and code == 1
    for body in [rest.json(), json.loads(native.content[0].text), cli]:
        assert body["error_code"] == "jyotish_calculation_inconsistent"
        assert body["retryable"] is False
        assert body["issues"] == [
            {"path": "runtime.jyotish.drik_bala", "code": "drik_chain_inconsistent"}
        ]
        assert "india" not in body and str(tmp_path) not in json.dumps(body)


def test_real_child_transports_safe_integrity_reason_and_is_reaped(monkeypatch):
    import sys
    from pathlib import Path

    from fatebridge.core.astro import native_execution as execution
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.jyotish import build_india
    from fatebridge.utils.errors import JyotishCalculationError

    root = Path(__file__).resolve().parents[1]
    bootstrap = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0,{str(root/'src')!r})",
            "from fatebridge.core import jyotish",
            "from fatebridge.core.astro import _native_worker",
            "original=jyotish.other_balas",
            "def altered(raw):",
            "    result=original(raw)",
            "    result['drik_bala']['matrix']['Sun']['Sun']=False",
            "    return result",
            "jyotish.other_balas=altered",
            "_native_worker.main()",
        ]
    )
    original = execution.subprocess.Popen
    children = []

    def started(args, *a, **kw):
        # Test-only fresh child bootstrap; real whitelist/protocol/cleanup stay active.
        process = original([sys.executable, "-I", "-c", bootstrap], *a, **kw)
        children.append(process)
        return process

    monkeypatch.setattr(execution.subprocess, "Popen", started)
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
        preserve_instant=True,
    )
    with pytest.raises(JyotishCalculationError) as error:
        build_india(birth, divisions=[])
    assert error.value.reason == "drik_chain_inconsistent"
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed
