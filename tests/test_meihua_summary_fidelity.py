"""Published default evidence and summaries carry their own computed qualifiers."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.application.examples import suggested_fields
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.meihua_summary_reference import SUMMARY_SCOPE, VOLUME2_PREFIX, VOLUME3_PREFIX
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

FIXTURE = Path(__file__).parent / "fixtures/meihua_summary_fidelity_v1"
POLICY = json.loads((FIXTURE / "composition-policy.json").read_text())
ROWS = json.loads((FIXTURE / "before-rendering.json").read_text())["rows"]


def test_original_policy_and_before_rendering_references_are_preserved():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    supplement = json.loads((FIXTURE / "discovery-supplement.json").read_text())
    assert manifest["preimplementation"] and supplement["before_production_edit"]
    for name, sha in {**manifest["files"], **supplement["files"]}.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    assert POLICY["volume2_prefix"] == VOLUME2_PREFIX
    assert POLICY["volume3_prefix"] == VOLUME3_PREFIX
    assert POLICY["summary_scope"] == SUMMARY_SCOPE


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize("view", [None, "reading"])
def test_default_reading_view_contains_complete_qualification(tool, view):
    fields = suggested_fields(SPECS[tool], view=view)
    if tool == "meihua_analysis" and view is None:
        # The compact time card carries the exact combined qualification in
        # summary; the complete reading card still carries every source fact.
        assert fields.count("summary") == 1
        assert not any(
            field.startswith("interpretation.seasonal_qualification.")
            for field in fields
        )
        fields = suggested_fields(SPECS[tool], view="reading")
    assert fields.count("interpretation.seasonal_qualification") == 1


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
def test_critical_source_qualifiers_reach_each_own_summary(row):
    out = calculate_meihua_cast(**row["arguments"])
    assert "error" not in out
    interpretation = out["interpretation"]
    layers = [interpretation, *(interpretation.get("casting_readings") or [])]
    assert len(layers) == len(row["layers"])
    for index, (layer, before) in enumerate(zip(layers, row["layers"], strict=True)):
        q = layer["seasonal_qualification"]
        assert q["roles"][0]["trigram"] == before["body"]
        assert q["volume2_summary"] == before["volume2_summary"]
        assert q["volume3_qualification"]["summary"] == before["volume3_summary"]
        assert q["summary_scope"] == SUMMARY_SCOPE
        combined = (
            VOLUME2_PREFIX
            + before["volume2_summary"]
            + VOLUME3_PREFIX
            + before["volume3_summary"]
        )
        assert q["summary"] == combined
        assert combined in out["summary"]
        assert combined in interpretation["comprehensive_judgement"]
        assert combined in layer["traditional_judgement"]
        if index == 0:
            assert combined in interpretation["traditional_judgement"]
        assert q["net_verdict"] is q["event_time"] is q["success_probability"] is None
        assert q["volume3_qualification"]["net_verdict"] is None
    if row["id"].startswith("mixed-weak"):
        assert all(
            text in out["summary"] for text in ["受克之忧加重", "衰稍解", "不吉之占"]
        )
    if row["id"].startswith("candidate-attacker-wang"):
        candidate = next(c for c in layers[1:] if c["body"] == "乾")
        assert "不引用乘旺皆吉" in candidate["traditional_judgement"]
        assert (
            candidate["seasonal_qualification"]["volume3_qualification"][
                "auxiliary_checks"
            ][0]["favorable_clause_applies"]
            is False
        )
    if row["arguments"]["season_month_branch"] is None:
        assert all(
            r["strength"] is None
            for r in interpretation["seasonal_qualification"]["roles"]
        )


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize("view", [None, "reading"])
@pytest.mark.parametrize("topic", ["general", "wealth", "weather"])
def test_published_first_response_agrees_on_rest_mcp_cli(
    tool, view, topic, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = (
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            "season_month_branch": "午",
        }
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    payload["interpretation_topic"] = topic
    fields = suggested_fields(spec, view=view)
    compact = tool == "meihua_analysis" and view is None
    assert fields.count("interpretation.seasonal_qualification") == (
        0 if compact else 1
    )
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )
    result = response.json()
    full = (
        calculate_meihua_analysis(**payload)
        if tool == "meihua_analysis"
        else calculate_meihua_cast(**payload)
    )
    q = full["interpretation"]["seasonal_qualification"]
    if compact:
        assert "seasonal_qualification" not in result["interpretation"]
    else:
        assert result["interpretation"]["seasonal_qualification"] == q
    if topic == "weather":
        assert q is None
        for key in ["classical_text_reference", "action_hint", "risk_hint"]:
            if "interpretation." + key in fields:
                assert result["interpretation"][key] is None
        if compact:

            async def bounded_weather():
                async with Client(create_mcp_app()) as client:
                    bounded = await client.call_tool(
                        spec.tool_name,
                        {
                            **payload,
                            "as_of": AS_OF,
                            "fields": fields,
                            "strict_fields": True,
                            "include_snapshot_text": False,
                            "response_char_limit": 8192,
                        },
                    )
                    assert not bounded.is_error
                    return await verified_inline_business(
                        client, bounded.structured_content
                    )

            assert business(asyncio.run(bounded_weather())) == business(result)
    else:
        assert q["summary_scope"] == SUMMARY_SCOPE
        assert q["summary"] in result["summary"]
