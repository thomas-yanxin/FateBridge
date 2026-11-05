"""Known restricted intents stop before calculation on every public surface."""

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

from fatebridge.application.execution import execute_spec
from fatebridge.core.consultation_policy import restricted_intent_path
from fatebridge.core.requests.divination import MeihuaAnalysisRequest
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.services.tool_catalog import CATALOG

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
def test_explicit_red_lines_rejected_without_echoing_input(question):
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
def test_neutral_terms_and_allowed_culture_are_not_life_death_predictions(question):
    assert MeihuaAnalysisRequest(**SAFE_TIME, question=question).question == question


def test_nested_intent_and_unicode_category_cannot_bypass():
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


def test_constructed_request_still_cannot_invoke_binding():
    spec = next(spec for spec in CATALOG if spec.key == "meihua_analysis")

    def forbidden_bind(_):
        pytest.fail("restricted input reached binding/calculation")

    request = MeihuaAnalysisRequest.model_construct(**SAFE_TIME, question="算寿命")
    result = execute_spec(replace(spec, bind=forbidden_bind), request)
    assert result["error_code"] == "consultation_restricted"
    assert "meihua" not in result


def test_removed_categories_are_absent_from_schemas_and_core_maps():
    from fatebridge.core.astrology_election import TOPIC_MASTER, build_election_payload
    from fatebridge.core.astrology_horary import HOUSE_BY_CATEGORY, build_horary_payload

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


def test_passive_death_lot_is_not_part_of_normal_natal_output():
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
        ("meihua_analysis", {**SAFE_TIME, "question": "预测爸爸去世时间"}),
        ("meihua_analysis", {**SAFE_TIME, "question": "家里将来哪年办白事"}),
        (
            "astro_horary",
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
            "astro_election",
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
    tool, inputs, monkeypatch, capsys
):
    import fatebridge.api as api
    import fatebridge.cli as cli
    from fatebridge.mcp_server import create_mcp_app

    spec = next(spec for spec in CATALOG if spec.mcp_name == tool)

    # The adapters must reject raw input before execution, independent of backend availability.
    def forbidden_execute(*args, **kwargs):
        pytest.fail("restricted request reached the shared executor")

    monkeypatch.setattr("fatebridge.transports.rest.execute_tool", forbidden_execute)
    monkeypatch.setattr("fatebridge.transports.mcp.execute_tool", forbidden_execute)
    monkeypatch.setattr(cli, "execute_tool", forbidden_execute)
    response = TestClient(api.app).post(spec.rest_path, json=inputs)
    args = [tool]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    code = cli.run(args)
    local = json.loads(capsys.readouterr().out)

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(tool, inputs, raise_on_error=False)

    protocol = asyncio.run(call())
    # MCP validation normalizes the same safe issue before rendering an isError result.
    protocol_data = json.loads(protocol.content[0].text)
    assert response.status_code == 422 and code == 1 and protocol.is_error
    for error in (response.json(), local, protocol_data):
        assert error["error_code"] == "consultation_restricted"
        assert error["retryable"] is False
        assert error["issues"][0]["code"] == "consultation_restricted"
        assert "run_metadata" not in error


def test_health_is_cultural_and_has_no_disease_or_treatment_recommendations():
    from fatebridge.analysis.health import HealthAnalysis

    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": ("甲", "寅"),
    }
    result = HealthAnalysis.analyze_health(
        pillars, dayun_pillar=("庚", "子"), liunian_pillar=("丙", "午")
    )
    assert result["is_medical_assessment"] is False
    assert "disease_risks" not in result
    assert "regimen" not in result
    assert len(result["organ_analysis"]["findings"]) == 5
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


def test_health_output_contract_rejects_reintroduced_clinical_claims():
    from jsonschema import Draft202012Validator

    from fatebridge.core.output_bazi import HealthAnalysis

    schema = Draft202012Validator(HealthAnalysis.model_json_schema())
    for invalid in (
        {"disease_risks": {"enabled": False, "risks": []}},
        {"disease_risks": {"enabled": True}},
        {"disease_risks": {"risks": ["疾病风险高"]}},
        {"regimen": {"advice": ["按喜用服药"]}},
        {"is_medical_assessment": True},
    ):
        with pytest.raises(ValidationError):
            HealthAnalysis.model_validate(invalid)
        assert not schema.is_valid(invalid)


def test_parent_child_rules_do_not_recommend_reproduction_or_predict_count():
    from fatebridge.analysis.children import ChildrenAnalysis

    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": ("甲", "寅"),
    }
    result = ChildrenAnalysis.analyze_children(
        pillars, "女", ("丙", "寅"), ("丁", "卯")
    )
    assert "不预测数量或生育结果" in result["interpretation_scope"]
    assert "count_hint" not in result["affinity"]
    text = json.dumps(result, ensure_ascii=False)
    for claim in ("早育多育", "利于添丁", "一至二位", "主生育", "备孕育儿"):
        assert claim not in text
