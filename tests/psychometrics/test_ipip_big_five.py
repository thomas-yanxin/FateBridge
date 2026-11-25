"""Tests for the deterministic 50-item IPIP Big-Five psychometric scale engine."""

from __future__ import annotations

import asyncio
import json
import re
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.api as api_module
import fatebridge.mcp_server as mcp_module
from fatebridge.cli import run as cli_run
from fatebridge.core.psychometrics.ipip_big_five import (
    DOMAIN_ORDER,
    IPIP_BIG_FIVE_ITEMS,
    ITEMS_BY_DOMAIN,
    ITEMS_BY_ID,
    METHOD_ID,
    SCALE_ID,
    SCALE_URL,
    SCORING_URL,
    IpipBigFiveRequest,
    score_ipip_big_five,
)
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import AS_OF, business, surface_calls  # noqa: F401

EXPECTED_KEYING_BY_DOMAIN = {
    "extraversion": {
        1: 1,
        6: -1,
        11: 1,
        16: -1,
        21: 1,
        26: -1,
        31: 1,
        36: -1,
        41: 1,
        46: -1,
    },
    "agreeableness": {
        2: -1,
        7: 1,
        12: -1,
        17: 1,
        22: -1,
        27: 1,
        32: -1,
        37: 1,
        42: 1,
        47: 1,
    },
    "conscientiousness": {
        3: 1,
        8: -1,
        13: 1,
        18: -1,
        23: 1,
        28: -1,
        33: 1,
        38: -1,
        43: 1,
        48: 1,
    },
    "emotional_stability": {
        4: -1,
        9: 1,
        14: -1,
        19: 1,
        24: -1,
        29: -1,
        34: -1,
        39: -1,
        44: -1,
        49: -1,
    },
    "intellect": {
        5: 1,
        10: -1,
        15: 1,
        20: -1,
        25: 1,
        30: -1,
        35: 1,
        40: 1,
        45: 1,
        50: 1,
    },
}


def _client(monkeypatch) -> TestClient:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api_module.app)


def test_ipip_50_items_and_keys_match_goldberg_standard():
    assert len(IPIP_BIG_FIVE_ITEMS) == 50
    assert [item.item_id for item in IPIP_BIG_FIVE_ITEMS] == list(range(1, 51))
    assert sum(1 for item in IPIP_BIG_FIVE_ITEMS if item.keying == 1) == 26
    assert sum(1 for item in IPIP_BIG_FIVE_ITEMS if item.keying == -1) == 24

    for factor_idx, domain in enumerate(DOMAIN_ORDER, start=1):
        domain_items = ITEMS_BY_DOMAIN[domain]
        assert len(domain_items) == 10
        assert {
            item.item_id: item.keying for item in domain_items
        } == EXPECTED_KEYING_BY_DOMAIN[domain]
        assert all(item.factor == factor_idx for item in domain_items)
        assert all(item.text.strip() and item.gloss_zh.strip() for item in domain_items)


def test_forward_and_reverse_scoring_exact_arithmetic():
    max_answers = {
        item.item_id: (5 if item.keying == 1 else 1) for item in IPIP_BIG_FIVE_ITEMS
    }
    max_result = score_ipip_big_five(max_answers, include_item_breakdown=True)
    assert max_result["status"] == "complete"
    assert max_result["answered_count"] == 50
    assert max_result["missing_count"] == 0
    for domain in DOMAIN_ORDER:
        d = max_result["domains"][domain]
        assert d["status"] == "complete"
        assert d["raw_sum"] == 50
        assert d["prorated_sum"] == 50.0
        assert d["mean"] == 5.0
        assert d["missing_item_ids"] == []
    assert len(max_result["item_breakdown"]) == 50
    assert all(row["scored_value"] == 5 for row in max_result["item_breakdown"])

    min_answers = {
        item.item_id: (1 if item.keying == 1 else 5) for item in IPIP_BIG_FIVE_ITEMS
    }
    min_result = score_ipip_big_five(min_answers)
    for domain in DOMAIN_ORDER:
        assert min_result["domains"][domain]["raw_sum"] == 10
        assert min_result["domains"][domain]["mean"] == 1.0

    # All raw=5 tests exact positive/negative key counts per domain: 10 + 4*pos_count.
    all_five = score_ipip_big_five(
        {i: 5 for i in range(1, 51)}, include_item_breakdown=True
    )
    assert all_five["domains"]["extraversion"]["raw_sum"] == 30
    assert all_five["domains"]["extraversion"]["mean"] == 3.0
    assert all_five["domains"]["agreeableness"]["raw_sum"] == 34
    assert all_five["domains"]["agreeableness"]["mean"] == 3.4
    assert all_five["domains"]["conscientiousness"]["raw_sum"] == 34
    assert all_five["domains"]["conscientiousness"]["mean"] == 3.4
    assert all_five["domains"]["emotional_stability"]["raw_sum"] == 18
    assert all_five["domains"]["emotional_stability"]["mean"] == 1.8
    assert all_five["domains"]["intellect"]["raw_sum"] == 38
    assert all_five["domains"]["intellect"]["mean"] == 3.8
    # Spot check reverse scoring (6 - raw) on item 4 (-1) and forward on item 5 (+1).
    item4 = next(r for r in all_five["item_breakdown"] if r["item_id"] == 4)
    item5 = next(r for r in all_five["item_breakdown"] if r["item_id"] == 5)
    assert (item4["raw_score"], item4["keying"], item4["scored_value"]) == (5, -1, 1)
    assert (item5["raw_score"], item5["keying"], item5["scored_value"]) == (5, 1, 5)


def test_missing_item_proration_and_insufficient_threshold():
    # Extraversion: 8/10 answered (missing 41, 46) -> prorated.
    # Agreeableness: 9/10 answered (missing 47) -> prorated.
    # Conscientiousness: 7/10 answered (missing 38, 43, 48) -> insufficient_items (mean None).
    # Emotional stability: 10/10 answered -> complete.
    # Intellect: 0/10 answered -> insufficient_items.
    answers: dict[int, int] = {}
    for item in ITEMS_BY_DOMAIN["extraversion"][:8]:
        answers[item.item_id] = 4 if item.keying == 1 else 2  # each scored 4
    for item in ITEMS_BY_DOMAIN["agreeableness"][:9]:
        answers[item.item_id] = 5 if item.keying == 1 else 1  # each scored 5
    for item in ITEMS_BY_DOMAIN["conscientiousness"][:7]:
        answers[item.item_id] = 3  # each scored 3
    for item in ITEMS_BY_DOMAIN["emotional_stability"]:
        answers[item.item_id] = 2 if item.keying == 1 else 4  # each scored 2

    res = score_ipip_big_five(answers, include_item_breakdown=True)
    assert res["status"] == "partial"
    assert res["answered_count"] == 34
    assert res["missing_count"] == 16

    ext = res["domains"]["extraversion"]
    assert ext["status"] == "prorated"
    assert ext["answered_count"] == 8
    assert ext["missing_count"] == 2
    assert ext["missing_item_ids"] == [41, 46]
    assert ext["raw_sum"] == 32
    assert ext["prorated_sum"] == 40.0
    assert ext["mean"] == 4.0

    agr = res["domains"]["agreeableness"]
    assert agr["status"] == "prorated"
    assert agr["answered_count"] == 9
    assert agr["missing_count"] == 1
    assert agr["missing_item_ids"] == [47]
    assert agr["raw_sum"] == 45
    assert agr["prorated_sum"] == 50.0
    assert agr["mean"] == 5.0

    con = res["domains"]["conscientiousness"]
    assert con["status"] == "insufficient_items"
    assert con["answered_count"] == 7
    assert con["missing_count"] == 3
    assert con["missing_item_ids"] == [38, 43, 48]
    assert con["raw_sum"] == 21
    assert con["prorated_sum"] is None
    assert con["mean"] is None

    es = res["domains"]["emotional_stability"]
    assert es["status"] == "complete"
    assert es["mean"] == 2.0
    assert es["prorated_sum"] == 20.0

    intel = res["domains"]["intellect"]
    assert intel["status"] == "insufficient_items"
    assert intel["answered_count"] == 0
    assert intel["missing_count"] == 10
    assert intel["raw_sum"] == 0
    assert intel["prorated_sum"] is None
    assert intel["mean"] is None

    missing_rows = [r for r in res["item_breakdown"] if r["status"] == "missing"]
    assert len(missing_rows) == 16
    assert all(
        r["raw_score"] is None and r["scored_value"] is None for r in missing_rows
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"action": "score"},
        {"responses": {}},
        {"responses": {"1": None}},
        {"responses": {"1": 0}},
        {"responses": {"1": 6}},
        {"responses": {"1": True}},
        {"responses": {"1": 3.5}},
        {"responses": {"1": "4"}},
        {"responses": {"0": 3}},
        {"responses": {"51": 3}},
        {"responses": {"01": 3}},
        {"responses": {"abc": 3}},
        {"ratings": []},
        {"ratings": [3] * 51},
        {"ratings": [0]},
        {"ratings": [6]},
        {"ratings": [True]},
        {"ratings": [None]},
        {"responses": {"1": 3}, "ratings": [3]},
        {"responses": {"1": 3}, "domain": "extraversion"},
        {"action": "list_items", "responses": {"1": 3}},
        {"action": "list_items", "ratings": [3]},
    ],
)
def test_invalid_inputs_are_rejected(payload):
    with pytest.raises(ValidationError):
        IpipBigFiveRequest.model_validate(payload)


def test_direct_scoring_rejects_invalid_scores_and_keys():
    for bad in ({1: 0}, {1: 6}, {1: True}, {1: 3.0}, {0: 3}, {51: 3}):
        with pytest.raises(ValueError):
            score_ipip_big_five(bad)


def test_output_stays_within_psychometric_engine_boundary():
    res = score_ipip_big_five({i: 3 for i in range(1, 51)}, include_item_breakdown=True)
    serialized = json.dumps(res, ensure_ascii=False).lower()
    for forbidden in (
        "percentile",
        "diagnosis",
        "disorder",
        "therapy",
        "advice",
        "百分位",
        "诊断",
        "建议",
    ):
        assert forbidden not in serialized
    assert not re.search(r"[0-9a-f]{64}", serialized)
    assert res["provenance"]["scale_id"] == SCALE_ID
    assert res["provenance"]["method_id"] == METHOD_ID
    assert res["provenance"]["scale_url"] == SCALE_URL
    assert res["provenance"]["scoring_url"] == SCORING_URL
    assert set(ITEMS_BY_ID) == set(range(1, 51))


@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
def test_every_named_item_direction_independently(rating):
    """The official sample key must control every response, including reverse items."""
    for domain, scoring_key in EXPECTED_KEYING_BY_DOMAIN.items():
        for item_id, direction in scoring_key.items():
            result = score_ipip_big_five({item_id: rating}, include_item_breakdown=True)
            expected = (
                rating if direction == 1 else {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}[rating]
            )
            assert result["domains"][domain]["raw_sum"] == expected
            answered = [
                row for row in result["item_breakdown"] if row["status"] == "answered"
            ]
            assert len(answered) == 1
            assert answered[0]["scored_value"] == expected


@pytest.mark.parametrize("count", [7, 8, 9, 10])
@pytest.mark.parametrize("domain", EXPECTED_KEYING_BY_DOMAIN)
def test_each_domain_missing_threshold_with_fraction_reference(domain, count):
    scoring_key = EXPECTED_KEYING_BY_DOMAIN[domain]
    selected = list(scoring_key)[:count]
    answers = {item_id: index % 5 + 1 for index, item_id in enumerate(selected)}
    expected_sum = sum(
        answers[item_id] if scoring_key[item_id] == 1 else 6 - answers[item_id]
        for item_id in selected
    )
    result = score_ipip_big_five(answers)
    dimension = result["domains"][domain]
    assert dimension["raw_sum"] == expected_sum
    assert dimension["missing_item_ids"] == list(scoring_key)[count:]
    if count == 7:
        assert dimension["status"] == "insufficient_items"
        assert dimension["mean"] is None and dimension["prorated_sum"] is None
    else:
        assert dimension["status"] == ("complete" if count == 10 else "prorated")
        assert dimension["mean"] == round(float(Fraction(expected_sum, count)), 4)
        assert dimension["prorated_sum"] == round(
            float(Fraction(10 * expected_sum, count)), 4
        )
    assert "scale_raw_sum" not in result and "scale_mean" not in result


@pytest.mark.parametrize(
    "payload,fields",
    [
        ({"action": "list_items"}, None),
        ({"ratings": [3] * 50}, None),
        ({"responses": {"1": 4, "6": None}}, None),
        ({"ratings": [5, None, 4]}, None),
        (
            {"action": "list_items", "domain": "intellect"},
            ["mode", "items", "provenance"],
        ),
        (
            {"ratings": [5] * 50},
            ["mode", "domains.extraversion.mean", "provenance.missing_policy_source"],
        ),
    ],
)
def test_real_three_surfaces(payload, fields, surface_calls):
    spec = next(spec for spec in CATALOG if spec.key == "ipip_big_five")
    projection = {"as_of": AS_OF, "response_char_limit": 0}
    if fields is not None:
        projection.update(fields=fields, strict_fields=True)
    http, protocol, code, local = surface_calls(spec, payload, projection=projection)
    assert http.status_code == 200, http.text
    assert not protocol.is_error, protocol.content
    assert code == 0, local
    bodies = [http.json(), protocol.structured_content, local]
    for body in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        assert "scale_raw_sum" not in body and "scale_mean" not in body
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    if fields is None:
        if payload.get("action") == "list_items":
            assert bodies[0]["item_count"] == 50
        else:
            assert len(bodies[0]["domains"]) == 5
    else:
        assert "summary" not in business(bodies[0])


def test_discovery_and_rejection(monkeypatch, capsys, surface_calls):
    client = _client(monkeypatch)
    manifest = client.get("/api/tools", params={"family": "psychometrics"})
    assert manifest.status_code == 200
    assert [row["tool"] for row in manifest.json()["tools"]] == ["ipip_big_five"]
    assert cli_run(["list", "--family", "psychometrics"]) == 0
    assert "ipip_big_five" in capsys.readouterr().out
    assert cli_run(["describe", "ipip_big_five"]) == 0
    assert json.loads(capsys.readouterr().out)["family"] == "psychometrics"

    async def discover_native():
        async with Client(mcp_module.create_mcp_app("psychometrics")) as native_client:
            tools = await native_client.list_tools()
            assert [tool.name for tool in tools] == ["ipip_big_five"]
            resource = await native_client.read_resource(
                "fatebridge://families/psychometrics"
            )
            assert [row["tool"] for row in json.loads(resource[0].text)["tools"]] == [
                "ipip_big_five"
            ]

    asyncio.run(discover_native())
    spec = next(spec for spec in CATALOG if spec.key == "ipip_big_five")
    for payload, projection in [
        ({"ratings": [True]}, {"as_of": AS_OF}),
        (
            {"ratings": [3]},
            {"as_of": AS_OF, "fields": ["scale_mean"], "strict_fields": True},
        ),
    ]:
        http, protocol, code, local = surface_calls(
            spec, payload, projection=projection
        )
        assert http.status_code == 422, http.text
        assert protocol.is_error
        assert code != 0
