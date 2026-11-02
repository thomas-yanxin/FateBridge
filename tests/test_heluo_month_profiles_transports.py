"""The selected original passage governs the same results on all adapters."""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core import heluo_months as months
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest

rest = shared_rest
ROOT = Path(__file__).parent / "fixtures/heluo_month_profiles_v1"
CASES = json.loads((ROOT / "adapter-cases.json").read_bytes())["cases"]
DIFF = {
    r["gua"]: r
    for r in json.loads((ROOT / "first-comparison.json").read_bytes())["differences"]
}


@pytest.fixture(autouse=True)
def native_source(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["gua"])
@pytest.mark.parametrize("method", [None, "intro_preferred_v1", "volume_one_table_v1"])
def test_actual_profile_on_rest_mcp_cli(case, method, rest, tmp_path, capsys):
    spec = SPECS["heluo"]
    payload = {
        **case["payload"],
        **({"month_assignment_method": method} if method else {}),
    }
    fields = ["chart", "judge", "snapshot_text", "input_normalized"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
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
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    row = DIFF[case["gua"]]
    chosen = (
        row["front_month"] if method == "volume_one_table_v1" else row["intro_month"]
    )
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        assert out["chart"][case["phase"]]["name"] == case["gua"]
        affinity = out["judge"]["month_affinity"]
        phase = next(p for p in affinity["phases"] if p["phase"] == case["phase"])
        assert affinity["assignment_method"] == (method or "intro_preferred_v1")
        assert (
            out["input_normalized"]["month_assignment_method"]
            == affinity["assignment_method"]
        )
        assert phase["assigned_month_number"] == chosen
        assert phase["assigned_month_match"] is (chosen == case["birth_month"])
        assert phase["source_consensus_match"] is None
        assert phase["source_months_agree"] is False
        assert [w["month_number"] for w in phase["source_readings"]] == [
            row["intro_month"],
            row["front_month"],
        ]
        assert out["judge"]["deTime"] is any(
            p["assigned_month_match"] for p in affinity["phases"]
        )
        assert "两处月号不同" in out["snapshot_text"]
        assert affinity["assignment_method"] in out["snapshot_text"]
        assert affinity["complete_assessment"] is False


@pytest.mark.parametrize("bad", [None, "automatic_best", True])
def test_invalid_source_selection_rejected_on_every_adapter(
    bad, rest, tmp_path, capsys
):
    spec = SPECS["heluo"]
    payload = {**CASES[0]["payload"], "month_assignment_method": bad}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and mcp.is_error
    assert "month_assignment_method" in response.text
    assert "month_assignment_method" in json.dumps(cli)


@pytest.mark.parametrize("non_object", [False, True])
@pytest.mark.parametrize(
    "source_attr,cache",
    [("COLLATION_PATH", "_collation"), ("FRONT_TABLE_PATH", "_front_table")],
)
def test_tampered_source_is_a_source_error_before_summary_projection(
    source_attr, cache, monkeypatch, rest, tmp_path, capsys, non_object
):
    data = json.loads(getattr(months, source_attr).read_bytes())
    if non_object:
        data = []
    else:
        data["assigned_months"][0]["month"] = 3
    p = tmp_path / "bad-month.json"
    p.write_text(json.dumps(data, ensure_ascii=False))
    getattr(months, cache).cache_clear()
    try:
        monkeypatch.setattr(months, source_attr, p)
        spec = SPECS["heluo"]
        payload = CASES[0]["payload"]
        response = rest.post(
            spec.rest_path,
            json=payload,
            params={"fields": "judge.month_affinity", "strict_fields": "true"},
        )
        code, cli = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=["--fields", "judge.month_affinity", "--strict-fields", "true"],
        )
        mcp = asyncio.run(
            native(
                spec,
                {**payload, "fields": ["judge.month_affinity"], "strict_fields": True},
            )
        )
        assert response.status_code == 503 and code != 0 and mcp.is_error
        assert "invalid_month_source_data" in response.text
        assert "invalid_month_source_data" in json.dumps(cli)
    finally:
        getattr(months, cache).cache_clear()
