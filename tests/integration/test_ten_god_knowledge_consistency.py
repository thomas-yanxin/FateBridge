"""Bundled definitions agree with independent five-element/polarity relations."""

import asyncio
import json
from itertools import product

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.data import get_shishen, get_ten_god

# Independent oracle: the generating ring is wood -> fire -> earth -> metal ->
# water. Adjacent stem pairs share an element; their first stem is yang, second
# yin. The controlling ring advances two positions. No production relationship,
# element, polarity, or ten-god mapping table is reused here.
STEMS = "甲乙丙丁戊己庚辛壬癸"
RELATIONS = {
    0: ("比肩", "劫财", "与日主同五行"),
    1: ("食神", "伤官", "日主所生"),
    2: ("偏财", "正财", "日主所克"),
    3: ("七杀", "正官", "克日主"),
    4: ("偏印", "正印", "生日主"),
}


def independent_relation(day, other):
    day_index, other_index = STEMS.index(day), STEMS.index(other)
    relation = (other_index // 2 - day_index // 2) % 5
    same_polarity = day_index % 2 == other_index % 2
    same_god, different_god, direction = RELATIONS[relation]
    return (
        same_god if same_polarity else different_god,
        direction,
        "同阴阳" if same_polarity else "异阴阳",
    )


@pytest.mark.parametrize("day,other", list(product(STEMS, repeat=2)))
def test_all_stem_pairs_match_knowledge_definition_and_both_calculators(day, other):
    expected, direction, polarity = independent_relation(day, other)
    assert get_ten_god(day, other).value == expected
    assert get_shishen(day, other) == expected
    entry = calculate_knowledge_read(domain="bazi", category="ten_gods", key=expected)
    definition = entry["lines"][0]
    assert direction in definition
    assert polarity in definition
    assert ("异阴阳" if polarity == "同阴阳" else "同阴阳") not in definition


# 三命通会卷五's named 甲见庚/乙见辛七杀 example supplies a second,
# concrete anchor rather than relying solely on the cyclic oracle.
@pytest.mark.parametrize("day,other", [("甲", "庚"), ("乙", "辛")])
def test_classical_seven_killings_examples(day, other):
    assert independent_relation(day, other)[0] == "七杀"
    assert get_ten_god(day, other).value == "七杀"
    assert get_shishen(day, other) == "七杀"


@pytest.mark.parametrize(
    "day,other,expected,direction,polarity",
    [
        ("甲", "庚", "七杀", "克日主", "同阴阳"),
        ("甲", "癸", "正印", "生日主", "异阴阳"),
    ],
)
def test_corrected_definitions_reach_rest_mcp_and_cli(
    monkeypatch, capsys, day, other, expected, direction, polarity
):
    assert get_ten_god(day, other).value == expected
    inputs = {"domain": "bazi", "category": "ten_gods", "key": expected}
    controls = {"include_snapshot_text": False, "response_char_limit": 0}

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post("/api/knowledge/read", json=inputs, params=controls)
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("knowledge_read", {**inputs, **controls})

    protocol = asyncio.run(call())
    assert not protocol.is_error
    assert (
        run(
            [
                "knowledge_read",
                "--domain",
                "bazi",
                "--category",
                "ten_gods",
                "--key",
                expected,
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    payloads = [response.json(), protocol.structured_content, cli]
    definitions = []
    for payload in payloads:
        assert payload["key"] == expected
        definition = payload["lines"][0]
        assert direction in definition
        assert polarity in definition
        definitions.append(definition)
    assert len(set(definitions)) == 1
