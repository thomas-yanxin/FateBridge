"""Conflicting occurrences and score explanations retain all actual evidence."""

import re

import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.analysis.marriage import MarriageAnalysis


@pytest.mark.parametrize("is_male", [True, False])
@pytest.mark.parametrize(
    "order", [("year", "month", "day", "hour"), ("hour", "day", "month", "year")]
)
def test_spouse_stars_at_both_ends_do_not_select_timing_by_iteration_order(
    is_male, order
):
    # Both visible spouse-star conventions hit the year and hour positions.
    # The existing rules attach opposite ordinal cues to those positions;
    # there is no declared priority that lets one silently replace the other.
    p = {
        "year": ("戊" if is_male else "庚", "辰"),
        "month": ("丙", "午"),
        "day": ("甲", "子"),
        "hour": ("己" if is_male else "辛", "巳"),
    }
    result = MarriageAnalysis._predict_marriage_timing(
        {key: p[key] for key in order}, "甲", "子", is_male
    )
    assert result["marriage_tendency"] == "早晚信号并存，未裁定"
    assert any("早婚倾向" in note for note in result["tendency_notes"])
    assert any("晚婚倾向" in note for note in result["tendency_notes"])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("count", [1, 2, 3])
def test_favorable_conflict_explanation_reconciles_with_actual_deduction(
    reverse, count
):
    selected = ["木", "火", "土"][:count]
    first = {"structure_profile": {"useful_elements": selected}}
    second = {"structure_profile": {"avoid_elements": selected}}
    if reverse:
        first, second = second, first
    result = AdvancedCompatibility._analyze_favorable_synergy(first, second)
    deltas = [
        int(re.search(r"\((-?\d+)\)$", row).group(1)) for row in result["score_basis"]
    ]
    assert result["score"] == 60 + sum(deltas) == 60 - 8 * count


@pytest.mark.parametrize("count", [1, 2, 3, 4])
@pytest.mark.parametrize(
    "dimension,base,cap",
    [("favorable_synergy", 60, 8), ("ten_gods_relationship", 65, 10)],
)
def test_shared_ten_god_bonus_is_included_in_the_public_score_explanation(
    count, dimension, base, cap
):
    selected = ["正印", "偏印", "食神", "伤官"][:count]
    person = {
        "day_master": {"stem": "甲"},
        "structure_profile": {"useful_ten_gods": selected},
    }
    result = (
        AdvancedCompatibility._analyze_favorable_synergy(person, person)
        if dimension == "favorable_synergy"
        else AdvancedCompatibility._analyze_ten_gods_relationship(
            person, person, RelationshipType.GENERAL
        )
    )
    deltas = [
        int(re.search(r"\(([+-]?\d+)\)$", row).group(1))
        for row in result["score_basis"]
    ]
    assert result["score"] == base + sum(deltas) == base + min(cap, count * 3)


def test_conflicting_marriage_cues_match_rest_mcp_and_cli(monkeypatch):
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from tests.test_agentic_replay import business, cli, native

    # Fabricated regression input: 戊辰 / 戊午 / 甲午 / 戊辰.
    # Birth facts and timing overrides are explicit in all three calls.
    inputs = {
        "name": "虚构婚期相反信号回归",
        "birth_year": 1988,
        "birth_month": 6,
        "birth_day": 8,
        "birth_hour": 8,
        "birth_minute": 0,
        "birth_second": 0,
        "gender": "男",
        "birth_timezone": "+08:00",
        "use_true_solar_time": False,
        "dayun_pillar": "甲子",
        "liunian_pillar": "丙午",
    }
    controls = {"as_of": "2026-11-03T10:00:00+08:00", "response_char_limit": 0}
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        "/api/cn/bazi/marriage", json=inputs, params=controls
    )
    protocol = native("bazi_marriage", inputs, controls)
    code, local = cli("bazi_marriage", inputs, controls)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    expected = business(response.json())
    assert expected == business(protocol.structured_content) == business(local)
    assert expected["marriage_analysis"]["marriage_timing"]["marriage_tendency"] == (
        "早晚信号并存，未裁定"
    )
