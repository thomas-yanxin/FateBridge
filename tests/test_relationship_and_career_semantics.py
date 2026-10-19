"""Relationship selection and rule-score meaning through the public transports."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError

import fatebridge.api as api
import fatebridge.services.compatibility as compatibility
from fatebridge.analysis.career import CareerAnalysis
from fatebridge.analysis.compatibility import RelationshipType
from fatebridge.application.examples import example_input
from fatebridge.cli import run
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.compatibility import assert_score_reference

SPECS = {
    spec.key: spec
    for spec in CATALOG
    if spec.key in {"two_person_compatibility", "bazi_career"}
}


def rest_client(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api.app)


async def mcp_call(tool, inputs):
    async with Client(create_mcp_app(families=SPECS[tool].family)) as client:
        return await client.call_tool(
            tool, {**inputs, "response_char_limit": 0}, raise_on_error=False
        )


def cli_call(tool, inputs, tmp_path, capsys):
    # Flat birth/pair tools expose ordinary flags, not --request-file.
    args = [tool]
    for key, value in inputs.items():
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        args.extend(["--" + key.replace("_", "-"), rendered])
    code = run(args)
    return code, json.loads(capsys.readouterr().out)


def test_relationship_schema_lists_exactly_the_supported_rules():
    schema = TwoPersonCompatibilityRequest.model_json_schema()
    field = schema["properties"]["relationship_type"]
    assert set(field["enum"]) == {kind.value for kind in RelationshipType}
    assert field["default"] == "general"
    inputs = example_input(SPECS["two_person_compatibility"])
    inputs.pop("relationship_type")
    assert TwoPersonCompatibilityRequest(**inputs).relationship_type == "general"


@pytest.mark.parametrize("invalid", ["business_partner", "Marriage", "", None, 7])
def test_invalid_relationship_fails_before_any_birth_calculation(monkeypatch, invalid):
    def unexpected_birth(*args, **kwargs):
        pytest.fail("invalid relationship must be rejected before birth computation")

    monkeypatch.setattr(
        compatibility, "build_birth_computation_context", unexpected_birth
    )
    result = compatibility.calculate_compatibility_analysis(None, None, invalid)
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 422 and not result["retryable"]
    assert result["issues"][0]["path"] == "relationship_type"
    assert result["issues"][0]["code"] == "literal_error"


@pytest.mark.parametrize("invalid", ["business_partner", "Marriage", "", None, 7])
def test_invalid_relationship_matches_all_transports(
    monkeypatch, tmp_path, capsys, invalid
):
    tool = "two_person_compatibility"
    inputs = {**example_input(SPECS[tool]), "relationship_type": invalid}
    with pytest.raises(ValidationError):
        TwoPersonCompatibilityRequest(**inputs)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(
            TwoPersonCompatibilityRequest.model_json_schema()
        ).validate(inputs)
    rest = rest_client(monkeypatch).post(SPECS[tool].rest_path, json=inputs)
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, tmp_path, capsys)
    assert rest.status_code == 422 and protocol.is_error and code == 1
    bodies = [rest.json(), protocol.structured_content, cli]
    for body in bodies:
        assert body["error_code"] == "validation_error"
        assert body["issues"][0]["path"] == "relationship_type"
        assert body["issues"][0]["code"] == "literal_error"
        assert not body["retryable"]
    assert bodies[0]["issues"] == bodies[1]["issues"] == bodies[2]["issues"]


@pytest.mark.parametrize(
    "kind",
    [None, "general", "marriage", "friendship", "business", "family"],
)
def test_revised_relationship_scores_match_across_transports(
    monkeypatch, tmp_path, capsys, kind
):
    # Existing public fictional example, never a real person's consultation.
    tool = "two_person_compatibility"
    inputs = example_input(SPECS[tool])
    if kind is None:
        inputs.pop("relationship_type")
    else:
        inputs["relationship_type"] = kind
    rest = rest_client(monkeypatch).post(SPECS[tool].rest_path, json=inputs)
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, tmp_path, capsys)
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    bodies = [rest.json(), protocol.structured_content, cli]
    for body in bodies:
        assert body["summary"]["relationship_type"] == (kind or "general")
        assert_score_reference(
            body["summary"], body["detailed_analysis"], kind or "general"
        )
        assert "不是关系成功概率" in body["summary"]["score_basis"]
    assert bodies[0]["summary"] == bodies[1]["summary"] == bodies[2]["summary"]


def test_food_god_controls_killer_changes_tendency_not_success_probability():
    pillars = {
        "year": ("庚", "申"),
        "month": ("丙", "寅"),
        "day": ("甲", "子"),
        "hour": ("庚", "午"),
    }
    result = CareerAnalysis._analyze_entrepreneurship(pillars, "甲")
    # Original weighted-rule result preserved; wording no longer claims success.
    assert result["score"] == 75 and result["tendency"] == "强烈创业倾向"
    assert any("食神制杀" in note for note in result["notes"])
    assert all("创业成功率高" not in note for note in result["notes"])
    assert result["score_kind"] == "traditional_rule_index"
    assert result["scope"] == "individual_natal_entrepreneurship_tendency"
    assert "不是成功率" in result["score_basis"]


def test_career_structure_score_does_not_measure_real_ability():
    pillars = {
        "year": ("庚", "午"),
        "month": ("辛", "巳"),
        "day": ("庚", "辰"),
        "hour": ("辛", "巳"),
    }
    result = CareerAnalysis._analyze_career_structure(pillars, "庚")
    assert result["score"] == 75 and result["level"] == "中等格局"
    assert result["scope"] == "individual_natal_career_structure"
    assert "不是事业成就或收入概率" in result["score_basis"]


def test_career_semantics_match_rest_mcp_cli(monkeypatch, tmp_path, capsys):
    tool = "bazi_career"
    inputs = {
        **example_input(SPECS[tool]),
        "dayun_pillar": "甲申",
        "liunian_pillar": "丙午",
    }
    rest = rest_client(monkeypatch).post(SPECS[tool].rest_path, json=inputs)
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, tmp_path, capsys)
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    career = [
        body["career_analysis"]
        for body in [rest.json(), protocol.structured_content, cli]
    ]
    assert career[0] == career[1] == career[2]
    assert career[0]["career_structure"]["score"] == 75
    assert career[0]["entrepreneurship"]["score"] == 73
    assert "不能据此决定辞职" in career[0]["interpretation_scope"]
    assert "创业成功率高" not in json.dumps(rest.json(), ensure_ascii=False)
    assert any("验证需求、现金流与执行能力" in s for s in career[0]["suggestions"])
