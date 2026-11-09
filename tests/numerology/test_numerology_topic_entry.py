"""Explicit numerology methods must work through the published family surface."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import Client

from fatebridge.application.examples import evidence_views
from fatebridge.mcp_server import create_mcp_app
from scripts import evaluate_agent as evaluator
from tests.support.transports import AS_OF, SPECS, business, call_cli
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.mark.parametrize(
    "tool,payload,view",
    [
        (
            "heluo",
            dict(
                date="2000-02-01",
                time="03:33:00",
                zone="+08:00",
                gender="男",
                use_true_solar_time=False,
            ),
            "selected_texts",
        ),
        (
            "canping",
            dict(
                date="2000-02-07",
                time="21:33:00",
                zone="+08:00",
                gender="男",
                method="gu",
                use_true_solar_time=False,
            ),
            "text_selection",
        ),
    ],
)
def test_actual_mcp_and_rest_cli_return_the_same_method_facts(
    tool, payload, view, rest, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty"))
    spec = SPECS[tool]
    fields = evidence_views(spec)[view]["fields"]
    assert {"input_normalized", "numerology_evidence.birth_clock"} <= set(fields)
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0"), ("as_of", AS_OF)],
    )
    code, local = call_cli(
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

    async def run():
        async with Client(create_mcp_app(families="divination")) as client:
            names = {t.name for t in await client.list_tools()}
            assert {"heluo", "canping"} <= names
            return await client.call_tool(
                tool,
                {
                    **payload,
                    "as_of": AS_OF,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    result = asyncio.run(run())
    assert response.status_code == 200 and code == 0 and not result.is_error
    outputs = [response.json(), local, result.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert output["input_normalized"]["date"] == payload["date"]
        clock = output["numerology_evidence"]["birth_clock"]
        assert clock["civil_datetime"] == "2000-" + (
            "02-01T03:33:00+08:00" if tool == "heluo" else "02-07T21:33:00+08:00"
        )
        assert clock["birth_instant_utc"] == (
            "2000-01-31T19:33:00+00:00"
            if tool == "heluo"
            else "2000-02-07T13:33:00+00:00"
        )
    if tool == "heluo":
        t = outputs[0]["numerology_evidence"]["selected_texts"][0]["text"]
        assert [s["section_id"] for s in t["commentary_sections"]] == [
            "opening",
            "xie",
            "annual",
        ]
        assert t["commentary_branch_selection"][
            "condition_labels_not_separately_printed"
        ] == ["不葉者"]
    else:
        v = outputs[0]["benming"]["verses"]
        assert (v["numShun"], v["numNi"]) == (2524, 2924)
        assert (
            v["statusShun"] == "source_reading_uncertain"
            and v["statusNi"] == "unavailable_in_local_corpus"
        )


def test_reference_capture_labels_full_catalog_before_any_model(tmp_path, monkeypatch):
    import fastmcp
    from fastmcp.client import transports

    seen = {}

    def transport(**kwargs):
        seen.update(kwargs)
        return object()

    class FakeClient:
        def __init__(self, transport):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def call_tool(self, name, arguments, raise_on_error=False):
            assert name == "heluo" and arguments["fields"] is None
            return SimpleNamespace(
                is_error=False,
                structured_content={"run_metadata": {"run_id": "reference-only"}},
                content=[],
            )

    monkeypatch.setattr(transports, "StdioTransport", transport)
    monkeypatch.setattr(fastmcp, "Client", FakeClient)
    case = dict(
        id="one",
        prompt="原提示",
        allowed_tools=["heluo"],
        manual_review=["隐藏标准"],
        reference_request=dict(tool="heluo", arguments={"date": "2000-02-01"}),
    )
    refs = asyncio.run(
        evaluator.prepare_references([case], tmp_path, tmp_path / "source")
    )
    assert seen["env"]["FATEBRIDGE_MCP_FAMILIES"] == ""
    assert refs[0]["reference_profile"] == dict(tool_selection="full_catalog")
    worksheet = json.loads((tmp_path / "review-worksheet.json").read_bytes())
    assert (
        worksheet["model_invocations"] == 0
        and worksheet["cases"][0]["semantic_status"] == "pending"
    )
    assert "隐藏标准" not in (tmp_path / "model-prompts/one.txt").read_text()


def test_hidden_rubric_paths_are_excluded_from_model_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("工程和咨询规则\n")
    (source / "src").mkdir()
    (source / "src/runtime.py").write_text("pass\n")
    (source / "docs/validation").mkdir(parents=True)
    (source / "docs/validation/hidden.md").write_text("隐藏判据")
    (source / "docs/public.md").write_text("公开接口")
    (source / "tests/fixtures/evaluation").mkdir(parents=True)
    (source / "tests/fixtures/evaluation/cases.json").write_text("隐藏案例")
    work = tmp_path / "work"
    work.mkdir()
    evaluator.prepare_workspace(work, source)
    assert (work / "docs/public.md").exists() and not (
        work / "docs/validation"
    ).exists()
    assert not (work / "tests").exists()
