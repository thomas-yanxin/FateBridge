"""Independent calendar mapping and actual stdio MCP/REST/CLI consistency."""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from tests.liuyao.test_liuyao_moving_si import BASE, CASES, check
from tests.support.transports import AS_OF, SPECS, business, call_cli

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = json.loads((BASE / "public-payloads.json").read_text())["rows"]
IDS = [
    "single_si-month-root",
    "single_si-day-root",
    "single_si-unproven-root",
    "single_si-si-void",
    "single_si-si-binding",
    "si_back_controlled-month-root",
    "si_and_wu-month-root",
    "si_and_earth-unproven-root",
]
SELECTED = [r for r in PUBLIC if r["id"] in IDS]
FIELDS = [
    "liuyao_evidence.conditional_analysis",
    "liuyao_evidence.calendar_conventions",
    "liuyao_evidence.rule_trace",
    "snapshot_text",
]
LEAF = "liuyao_evidence.conditional_analysis.growth_conditions.focus.moving_si.condition_match"


@pytest.fixture(scope="module")
def protocol_outputs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("moving-si-stdio")
    evidence = Path(os.environ.get("FATEBRIDGE_V40_EVIDENCE", str(folder)))
    evidence.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "SE_EPHE_PATH": str(folder),
        "FATEBRIDGE_SOLAR_TERM_MODEL": "auto",
        "FATEBRIDGE_MCP_FAMILIES": "",
    }
    env.pop("FATEBRIDGE_JPL_FILE", None)

    async def collect():
        transport = StdioTransport(
            command=sys.executable,
            args=["-X", "utf8", "-m", "fatebridge.mcp_server"],
            cwd=str(ROOT),
            env=env,
            log_file=evidence / "stdio.log",
        )
        observed = {}
        async with Client(transport) as client:
            for public in SELECTED:
                kinds = ["full", "projection"]
                if public["id"] in {"single_si-month-root", "single_si-unproven-root"}:
                    kinds.append("leaf")
                for kind in kinds:
                    flags = dict(as_of=AS_OF, response_char_limit=0)
                    if kind != "full":
                        flags.update(
                            fields=[LEAF] if kind == "leaf" else FIELDS,
                            strict_fields=True,
                        )
                    request = {**public["payload"], **flags}
                    result = await client.call_tool(
                        SPECS["sixyao"].tool_name, request, raise_on_error=False
                    )
                    raw = dict(
                        tool=SPECS["sixyao"].tool_name,
                        arguments=request,
                        is_error=result.is_error,
                        structured_content=result.structured_content,
                    )
                    (evidence / (public["id"] + "-" + kind + "-mcp.json")).write_text(
                        json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
                    )
                    assert not result.is_error, raw
                    observed[public["id"], kind] = result.structured_content
        return observed

    return asyncio.run(collect())


def test_public_dates_are_bound_to_independent_calendars():
    assert len(PUBLIC) == len(CASES) == 35 and len(SELECTED) == 8
    for name, digest in json.loads(
        (BASE / "public-mapping-freeze.json").read_text()
    ).items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    mapping = json.loads((BASE / "public-payloads.json").read_text())
    assert (
        mapping["day_anchor_sha256"]
        == hashlib.sha256(
            (BASE.parent / "liuyao_scan_v3/naoj-day-reference.json").read_bytes()
        ).hexdigest()
    )
    assert (
        mapping["reference_sha256"]
        == hashlib.sha256(
            (
                Path(__file__).parents[1] / "data/bazi_all_terms_v1/reference.json"
            ).read_bytes()
        ).hexdigest()
    )


@pytest.mark.parametrize("public", SELECTED, ids=lambda r: r["id"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_moving_si_facts_and_faithful_readout_on_three_protocols(
    public, project, protocol_outputs, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["sixyao"]
    options = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--as-of", AS_OF, "--response-char-limit", "0"]
    if project:
        options.update(fields=FIELDS, strict_fields=True)
        flags += ["--fields", *FIELDS, "--strict-fields", "true"]
    http = rest.post(spec.rest_path, json=public["payload"], params=options)
    code, cli = call_cli(spec, public["payload"], tmp_path, capsys, flags=flags)
    mcp = protocol_outputs[public["id"], "projection" if project else "full"]
    assert http.status_code == 200 and code == 0, http.text
    outputs = [http.json(), cli, mcp]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    case = next(c for c in CASES if c["id"] == public["id"])
    for result in outputs:
        spec.output_model.model_validate(result)
        conditional = result["liuyao_evidence"]["conditional_analysis"]
        check(conditional, case)
        assert (
            conditional["growth_conditions"]["focus"]["condition_match_scope"]
            == "day_branch_growth_only"
        )
        cal = result["liuyao_evidence"]["calendar_conventions"]
        assert (cal["month_branch"], cal["day_ganzhi"]) == (
            public["month"],
            public["day"],
        )
        context = conditional["growth_conditions"]["focus"]["moving_si"]
        lines = [
            line
            for line in result["snapshot_text"].splitlines()
            if line.startswith(f"第{case['focus_line']}爻")
            and "金遇第" in line
            and "实际动巳" in line
        ]
        assert len(lines) == 1
        if context["condition_match"] is True:
            assert (
                "遇长生资格" in lines[0]
                and "合并效力待审" in lines[0]
                and "许可仍保留" in lines[0]
            )
        elif context["condition_match"] is None:
            assert (
                "普通火克金方向与所列许可另列" in lines[0]
                and "合并效力未裁定" in lines[0]
            )
        else:
            assert "不认定本项已获长生" in lines[0] and "不据此认定金爻无气" in lines[0]
        trace = next(
            t
            for t in result["liuyao_evidence"]["rule_trace"]
            if t["rule_id"] == "metal_actual_moving_si_growth_qualification"
        )
        assert (
            context["source_path"] in trace["proof_paths"]
            and trace["source_sha256"] == context["source_sha256"]
        )
    if folder := os.environ.get("FATEBRIDGE_V40_EVIDENCE"):
        (Path(folder) / (public["id"] + f"-{project}-surfaces.json")).write_text(
            json.dumps(outputs, ensure_ascii=False, indent=2) + "\n"
        )


@pytest.mark.parametrize(
    "case_id,expected",
    [("single_si-month-root", True), ("single_si-unproven-root", None)],
)
def test_new_leaf_projection_preserves_true_and_unknown(
    case_id, expected, protocol_outputs
):
    result = protocol_outputs[case_id, "leaf"]
    assert result["liuyao_evidence"]["conditional_analysis"]["growth_conditions"][
        "focus"
    ]["moving_si"] == {"condition_match": expected}
    assert not result.get("projection_warnings")
