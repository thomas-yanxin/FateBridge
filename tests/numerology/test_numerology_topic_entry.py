"""Explicit numerology methods must work inside their declared topic surface."""

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import Client

from fatebridge.application.examples import evidence_views
from fatebridge.application.scenarios import definitions, scenario_keys
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts import evaluate_agent as evaluator
from tests.support.transports import AS_OF, SPECS, business, call_cli
from tests.support.transports import rest as shared_rest

rest = shared_rest


@pytest.mark.parametrize("scope", ["topic", "complete"])
def test_method_entry_adds_exactly_the_two_named_calculators(scope, monkeypatch):
    current = scenario_keys(CATALOG, "onda-xingpan", scope=scope)
    before = copy.deepcopy(definitions())
    row = next(r for r in before["scenarios"] if r["id"] == "onda-xingpan")
    row["engine_tools"] = [
        key for key in row["engine_tools"] if key not in {"heluo", "canping"}
    ]
    with monkeypatch.context() as m:
        m.setattr("fatebridge.application.scenarios.definitions", lambda: before)
        old = scenario_keys(CATALOG, "onda-xingpan", scope=scope)
    assert current - old == {"heluo", "canping"} and old <= current
    if scope == "topic":
        assert not ({"qimen", "jinkou", "astro_election", "gua_lookup"} & current)


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
def test_actual_topic_mcp_and_rest_cli_return_the_same_method_facts(
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
        async with Client(
            create_mcp_app(scenarios="onda-xingpan", tool_scope="topic")
        ) as client:
            names = {t.name for t in await client.list_tools()}
            assert {"heluo", "canping"} <= names and not (
                {"qimen", "jinkou", "astro_election"} & names
            )
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


@pytest.mark.parametrize(
    "cases,expected",
    [
        ([dict(scenario="onda-xingpan", tool_scope="topic")], "topic"),
        (
            [
                dict(scenario="onda-xingpan", tool_scope="topic"),
                dict(scenario="onda-zhanbu", tool_scope="topic"),
            ],
            "topic",
        ),
        ([dict(scenario="onda-xingpan")], "complete"),
        (
            [dict(scenario="onda-xingpan", tool_scope="topic"), dict(scenario="")],
            "complete",
        ),
    ],
)
def test_reference_scope_matches_homogeneous_batches_and_labels_mixed_union(
    cases, expected
):
    assert evaluator.reference_tool_scope(cases) == expected


@pytest.mark.parametrize(
    "cases", [[dict(tool_scope="bad")], [dict(tool_scope="topic", scenario="")]]
)
def test_invalid_topic_preparation_does_not_silently_widen_to_all_tools(cases):
    with pytest.raises(ValueError):
        evaluator.reference_tool_scope(cases)


def test_reference_capture_uses_the_requested_topic_before_any_model(
    tmp_path, monkeypatch
):
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
        scenario="onda-xingpan",
        tool_scope="topic",
        prompt="原提示",
        allowed_tools=["heluo"],
        manual_review=["隐藏标准"],
        reference_request=dict(tool="heluo", arguments={"date": "2000-02-01"}),
    )
    refs = asyncio.run(
        evaluator.prepare_references([case], tmp_path, tmp_path / "source")
    )
    assert seen["env"]["FATEBRIDGE_MCP_TOOL_SCOPE"] == "topic"
    assert refs[0]["reference_profile"] == dict(
        scenarios="onda-xingpan", tool_scope="topic"
    )
    worksheet = json.loads((tmp_path / "review-worksheet.json").read_bytes())
    assert (
        worksheet["model_invocations"] == 0
        and worksheet["cases"][0]["semantic_status"] == "pending"
    )
    assert "隐藏标准" not in (tmp_path / "model-prompts/one.txt").read_text()


def test_nine_diagnostics_keep_all_input_requirements_outside_the_prompt():
    import hashlib

    root = Path(__file__).parents[1] / "fixtures"
    dataset = root / "agent_behavior/numerology_semantic_cases_v1.json"
    d = json.loads(dataset.read_bytes())
    p = json.loads((root / "numerology_semantics_v1/protocol.json").read_bytes())
    assert len(d["cases"]) == p["case_count"] == 9
    assert (
        sum(len(c["manual_review"]) for c in d["cases"]) == p["criterion_count"] == 45
    )
    assert len({c["id"] for c in d["cases"]}) == 9
    assert p["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert (
        p["model_invocations_at_freeze"] == 0 and p["semantic_acceptance"] == "not_run"
    )
    for c in d["cases"]:
        assert c["tool_scope"] == "topic" and c["scenario"] == "onda-xingpan"
        assert all(text not in evaluator.model_prompt(c) for text in c["manual_review"])
        assert c["argument_paths"] == {
            c["reference_request"]["tool"]: {"use_true_solar_time": False}
        }


def test_hidden_rubric_paths_are_excluded_from_model_workspace(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("工程和咨询规则\n")
    (source / "skills/onda-xingpan").mkdir(parents=True)
    (source / "skills/onda-xingpan/SKILL.md").write_text("公开技能")
    (source / "src").mkdir()
    (source / "src/runtime.py").write_text("pass\n")
    (source / "docs/validation").mkdir(parents=True)
    (source / "docs/validation/hidden.md").write_text("隐藏判据")
    (source / "docs/public.md").write_text("公开接口")
    (source / "tests/fixtures/agent_behavior").mkdir(parents=True)
    (
        source / "tests/fixtures/agent_behavior/numerology_semantic_cases_v1.json"
    ).write_text("隐藏案例")
    work = tmp_path / "work"
    work.mkdir()
    evaluator.prepare_workspace(work, source)
    assert (work / "docs/public.md").exists() and not (
        work / "docs/validation"
    ).exists()
    assert not (work / "tests").exists()
