"""Known restricted intents stop before calculation on every public surface."""

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

from fatebridge.application.description import resolve_spec
from fatebridge.application.execution import invoke_validated_service
from fatebridge.core.consultation_policy import restricted_intent_path
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import MCP_CASES
from tests.support.transports import call_calculation

SAFE_TIME = dict(
    analysis_year=2026, analysis_month=10, analysis_day=19, analysis_hour=12
)


@pytest.mark.parametrize(
    "question",
    [
        "我还能活多久",
        "爸爸还能陪我多久",
        "我的寿元是多少",
        "哪一年会去世",
        "虚构人物的死亡年份",
        "只给我生死关口的提示",
        "哪年会得癌症",
        "按八字判断我是什么病",
        "哪天手术最吉利",
        "预测我是否不孕",
        "什么时候自杀能成功",
        "How long will I live?",
        "When will my mother die?",
        "我的死\u200b亡时间",
        "预测我哪年有车祸",
        "best time for surgery",
        "我会不会死",
        "我能活多久",
        "下个月适不适合动手术",
        "Will I die soon?",
        "我家里将来哪年办白事，只要年份不用细说",
        "哪年给父亲办丧事",
        "父亲的葬礼会是什么时候",
    ],
)
def test_explicit_red_lines_rejected_without_echoing_input(question: str) -> None:
    with pytest.raises(ValidationError) as caught:
        MeihuaAnalysisRequest(**SAFE_TIME, question=question)
    assert caught.value.errors()[0]["type"] == "consultation_restricted"
    from fatebridge.utils.errors import validation_error_result

    error = validation_error_result(caught.value)
    assert error["error_code"] == "consultation_restricted"
    assert question not in json.dumps(error, ensure_ascii=False)


@pytest.mark.parametrize(
    "question",
    [
        "我想离开公司换工作",
        "紫微大限是什么",
        "奇门死门是什么意思",
        "这个项目何时提交比较合适",
        "传统寒暖标签是什么意思",
        "How should I leave my job?",
        "孩子几岁离开家去上学",
        "传统白事有哪些礼俗",
    ],
)
def test_neutral_terms_and_allowed_culture_are_not_life_death_predictions(
    question: str,
) -> None:
    assert MeihuaAnalysisRequest(**SAFE_TIME, question=question).question == question


def test_nested_intent_and_unicode_category_cannot_bypass() -> None:
    assert (
        restricted_intent_path({"options": {"question": "能活到多少岁"}})
        == "options.question"
    )
    assert (
        restricted_intent_path({"category": "ＤＥＡＴＨ", "question_year": 2026})
        == "category"
    )
    assert (
        restricted_intent_path({"domain": "bazi", "category": "health", "key": "五行"})
        is None
    )
    assert restricted_intent_path({"name": "死侍", "question": "工作方向"}) is None


def test_constructed_request_still_cannot_invoke_binding() -> None:
    """Single-boundary request validation rejects restricted intent before execute_spec."""
    with pytest.raises(ValidationError) as caught:
        MeihuaAnalysisRequest(**SAFE_TIME, question="算寿命")
    assert caught.value.errors()[0]["type"] == "consultation_restricted"


def test_removed_categories_are_absent_from_schemas_and_core_maps() -> None:
    from fatebridge.core.astro.astrology_election import (
        TOPIC_MASTER,
        build_election_payload,
    )
    from fatebridge.core.astro.astrology_horary import (
        HOUSE_BY_CATEGORY,
        build_horary_payload,
    )

    horary = AstroHoraryRequest.model_json_schema()["properties"]["category"]["enum"]
    election = AstroElectionRequest.model_json_schema()["properties"]["topic_id"][
        "enum"
    ]
    for category in ("death", "health", "pregnancy"):
        assert category not in horary and category not in HOUSE_BY_CATEGORY
        with pytest.raises(ValueError):
            build_horary_payload(None, category=category)
    assert "surgery" not in election and "surgery" not in TOPIC_MASTER
    with pytest.raises(ValueError):
        build_election_payload(None, topic_id="surgery")


def test_passive_death_lot_is_not_part_of_normal_natal_output() -> None:
    from fatebridge.core.classical_western import LOTS, build_lots_layer

    assert "death" not in LOTS
    points = {
        "asc": 30.0,
        "sun": 60.0,
        "moon": 90.0,
        "venus": 100.0,
        "saturn": 120.0,
        "jupiter": 150.0,
        "eighth": 240.0,
    }
    for is_day in (True, False):
        assert "death" not in build_lots_layer(points, is_day)


@pytest.mark.parametrize(
    "tool,inputs",
    [
        ("meihua_time_cast", {**SAFE_TIME, "question": "预测爸爸去世时间"}),
        ("meihua_time_cast", {**SAFE_TIME, "question": "家里将来哪年办白事"}),
        (
            "horary_chart",
            dict(
                question_year=2026,
                question_month=10,
                question_day=19,
                question_hour=12,
                longitude=116.4,
                latitude=39.9,
                category="death",
            ),
        ),
        (
            "evaluate_election_time",
            dict(
                candidate_year=2026,
                candidate_month=10,
                candidate_day=19,
                candidate_hour=12,
                longitude=116.4,
                latitude=39.9,
                topic_id="surgery",
            ),
        ),
    ],
)
def test_restrictions_match_rest_mcp_cli_and_never_reach_services(
    tool: str,
    inputs,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import fatebridge.api as api
    import fatebridge.application.execution as execution
    from fatebridge.mcp_server import create_mcp_app

    spec = resolve_spec(CATALOG, tool)
    assert spec is not None

    # The adapters must reject raw input before execution, independent of backend availability.
    def forbidden_execute(*args, **kwargs):
        pytest.fail("restricted request reached the shared executor")

    monkeypatch.setattr(api, "execute_with_receipt", forbidden_execute)
    monkeypatch.setattr("fatebridge.mcp_server.execute_with_receipt", forbidden_execute)
    monkeypatch.setattr(execution, "execute_with_receipt", forbidden_execute)
    response = TestClient(api.app).post(spec.rest_path, json=inputs)
    args = [tool]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    from fatebridge import cli

    code = cli.run(args)
    local = json.loads(capsys.readouterr().out)

    async def call():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(client, tool, inputs, raise_on_error=False)

    protocol = asyncio.run(call())
    # MCP validation normalizes the same safe issue before rendering an isError result.
    protocol_data = protocol.structured_content
    assert response.status_code == 422 and code == 1 and protocol.is_error
    for error in (response.json(), local, protocol_data):
        assert error["error_code"] == "consultation_restricted"
        assert error["retryable"] is False
        assert error["issues"][0]["code"] == "consultation_restricted"
        assert "run_metadata" not in error


def test_health_is_cultural_and_has_no_disease_or_treatment_recommendations() -> None:
    spec = resolve_spec(CATALOG, "bazi_health")
    assert spec is not None
    request = spec.request_model.model_validate(MCP_CASES["bazi_health"][1]())
    result = invoke_validated_service(spec, request)["health_analysis"]
    facts = result["topic_facts"]
    assert facts["element_distribution"]
    assert facts["seasonal_climate"]
    assert "disease_risks" not in result
    assert "regimen" not in result
    text = json.dumps(result, ensure_ascii=False)
    for claim in (
        "先天偏弱",
        "易受外伤",
        "整体健康风险较低",
        "宜滋阴",
        "宜温阳",
        "易劳损",
    ):
        assert claim not in text


def test_health_output_contract_rejects_reintroduced_clinical_claims() -> None:
    from jsonschema import Draft202012Validator

    from fatebridge.core.contracts.output_bazi import DimensionOutput

    schema = Draft202012Validator(DimensionOutput.model_json_schema())
    for invalid in (
        {"disease_risks": {"enabled": False, "risks": []}},
        {"disease_risks": {"enabled": True}},
        {"disease_risks": {"risks": ["疾病风险高"]}},
        {"regimen": {"advice": ["按喜用服药"]}},
    ):
        with pytest.raises(ValidationError):
            DimensionOutput.model_validate(invalid)
        assert not schema.is_valid(invalid)


def test_parent_child_rules_do_not_recommend_reproduction_or_predict_count() -> None:
    spec = resolve_spec(CATALOG, "bazi_children")
    assert spec is not None
    request = spec.request_model.model_validate(
        {**MCP_CASES["bazi_children"][1](), "gender": "女"}
    )
    result = invoke_validated_service(spec, request)["children_analysis"]
    facts = result["topic_facts"]
    assert facts["four_pillars"]["hour"]
    assert [star["ten_god"] for star in facts["natal_stars"]] == ["伤官"]
    assert "count_hint" not in result
    text = json.dumps(result, ensure_ascii=False)
    for claim in ("早育多育", "利于添丁", "一至二位", "主生育", "备孕育儿"):
        assert claim not in text
