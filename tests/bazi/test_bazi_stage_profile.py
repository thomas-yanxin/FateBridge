"""Explicit stage convention stays separate from physical roots and force."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.classical_roots import classify_classical_root
from fatebridge.core.classical_stages import life_stage_profile, twelve_life_stage
from fatebridge.core.output_stage_profile import LifeStageProfile
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ANCHORS = json.loads(
    (
        Path(__file__).parents[1]
        / "data/bazi_stage_profile_v1/source-anchors-first.json"
    ).read_text()
)
PAYLOAD = {
    "name": "虚构阶段口径传输验证",
    "birth_year": 1993,
    "birth_month": 12,
    "birth_day": 12,
    "birth_hour": 12,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}
KEYS = ["analyze_destiny", "bazi_birth"] + [
    "bazi_" + topic
    for topic in [
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ]
]


def at(value, path):
    for part in path.split("."):
        value = value[part]
    return value


def test_ten_primary_starts_and_complete_published_lookup_match_existing_table():
    profile = life_stage_profile()
    LifeStageProfile.model_validate(profile)
    for anchor in ANCHORS["anchors"]:
        stem = anchor["stem"]
        start = profile["growth_starts"][stem]
        assert start == {
            "growth_branch": anchor["growth_branch"],
            "direction": anchor["direction"],
        }
        assert twelve_life_stage(stem, anchor["growth_branch"]) == "长生"
        for branch in profile["branch_cycle"]:
            distance = (
                (
                    profile["branch_cycle"].index(branch)
                    - profile["branch_cycle"].index(start["growth_branch"])
                )
                * start["direction"]
                % 12
            )
            assert twelve_life_stage(stem, branch) == profile["stage_cycle"][distance]
    assert profile["independent_expert_review"] == "not_completed"
    assert profile["calculation_effect"] == "none_existing_values_only"


def test_complete_profile_rejects_digest_contradiction_and_partial_does_not_invent_context():
    value = life_stage_profile()
    value["growth_starts"]["戊"]["growth_branch"] = "申"
    with pytest.raises(ValidationError, match="散列"):
        LifeStageProfile.model_validate(value)
    partial = {"growth_starts": {"戊": {"growth_branch": "寅"}}}
    assert (
        LifeStageProfile.model_validate(partial).model_dump(exclude_none=True)
        == partial
    )
    assert partial == {"growth_starts": {"戊": {"growth_branch": "寅"}}}


def test_future_annotations_are_preserved_without_changing_the_lookup_hash():
    value = life_stage_profile()
    value["growth_starts"]["甲"]["future_fact"] = {"note": "额外注释"}
    original = copy.deepcopy(value)
    validated = LifeStageProfile.model_validate(value)
    assert validated.lookup_sha256 == original["lookup_sha256"]
    assert validated.model_dump(exclude_none=True)["growth_starts"]["甲"][
        "future_fact"
    ] == {"note": "额外注释"}
    assert value == original
    value["growth_starts"]["甲"]["direction"] = -value["growth_starts"]["甲"][
        "direction"
    ]
    with pytest.raises(ValidationError, match="散列"):
        LifeStageProfile.model_validate(value)


@pytest.mark.parametrize(
    "stem,branch,phase,hidden",
    [("戊", "申", "病", ["戊"]), ("癸", "申", "死", ["壬"]), ("乙", "午", "长生", [])],
)
def test_phase_neither_creates_nor_deletes_actual_hidden_roots(
    stem, branch, phase, hidden
):
    root = classify_classical_root(stem, branch)
    assert root["life_stage"] == phase
    assert root["matching_hidden_stems"] == hidden
    assert root["effect_status"] == "root_effect_not_adjudicated"


@pytest.mark.parametrize("key", KEYS)
def test_profile_view_preserves_whole_root_receipts_on_public_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    fields = suggested_fields(spec, view="stage_profile")
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    payload = {
        k: v
        for k, v in PAYLOAD.items()
        if key != "analyze_destiny" or not k.startswith("analysis_")
    }
    protocol = asyncio.run(native(spec, payload, **flags))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    assert not protocol.is_error and code == 0
    result = protocol.structured_content
    assert business(result) == business(local)
    if spec.rest_path:
        response = rest.post(spec.rest_path, json=payload, params=flags)
        assert response.status_code == 200, response.text
        assert business(response.json()) == business(result)
    spec.output_model.model_validate(result)
    root = at(result, fields[0].removesuffix(".life_stage_profile"))
    assert root["life_stage_profile"] == life_stage_profile()
    assert len(root["roots"]) == 4
    assert root["global_strength_status"] == "not_adjudicated"
    before = copy.deepcopy(result)
    spec.output_model.model_validate(result)
    assert result == before
