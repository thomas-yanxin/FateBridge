"""Frozen source contexts keep three kinds of motion and missing valence apart."""

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.meihua.test_meihua_external import at_path

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_motion_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
TIME = dict(
    analysis_year=2026,
    analysis_month=10,
    analysis_day=22,
    analysis_hour=12,
    analysis_timezone="Asia/Shanghai",
)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_inner_observer_and_outer_contexts(case):
    out = calculate_meihua_cast(**case["input"])
    assert "error" not in out, out
    layer = out["interpretation"]["motion_context"]
    roles = layer["inner_roles"]
    assert [r["role"] for r in roles] == [
        "body",
        "use",
        "body_mutual",
        "use_mutual",
        "changed_use",
    ]
    assert [r["motion"] for r in roles] == [
        "static",
        "active",
        "static",
        "static",
        "active",
    ]
    assert [r["trigram"] for r in roles] == [case["body"], *case["stage_trigrams"]]
    for row in roles:
        assert at_path(out, row["fact_path"])["name"] == row["trigram"]
    observer = layer["observer"]
    assert observer["activity"] == case["activity"]
    assert observer["relative_wording"] == case["relative_wording"]
    if case["activity"] is None:
        assert observer["declaration"] is None
    else:
        assert at_path(out, observer["declaration"]["fact_path"]) == case["activity"]
    assert len(layer["external_motion"]) == int(case["external_record_present"])
    for row in layer["external_motion"]:
        assert row["motion"] == case["motion"]
        assert row["declaration_status"] == (
            "not_collected" if case["motion"] is None else "caller_reported_unverified"
        )
        observation = at_path(out, row["reported_fact_path"])
        assert observation == case["input"]["external_observations"][0]
        assert at_path(out, row["qualification_fact_path"])["body"] == case["body"]
        assert row["omen_valence"] is None
        assert [r["full_clause_applies"] for r in row["moving_clauses"]] == (
            [False, False] if case["motion"] == "stationary" else [None, None]
        )
        assert (row["stationary_source_wording"] is not None) == (
            case["motion"] == "stationary"
        )
    assert layer["event_time"] is layer["duration"] is layer["combined_outcome"] is None
    assert layer["casting_trigger_adjudicated"] is False
    assert layer["independent_verified_observations"] == 0


def test_frozen_bytes_and_variant_are_preserved():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert m["implementation_not_present"] and m["request_fields_not_present"]
    assert m["production_generated_expected_values"] is False
    for name, digest in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    from fatebridge.core.meihua_motion import motion_ruleset

    p = motion_ruleset()
    assert p["source"]["transcription_variants"][0]["selected"] == "吉凶之未見也"
    p["source"]["transcription_variants"].clear()
    assert len(motion_ruleset()["source"]["transcription_variants"]) == 3


@pytest.mark.parametrize("value", [True, 0, "", "坐", "driving", {}, []])
def test_unknown_observer_activity_rejected(value):
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {"casting": CASES[0]["input"]["casting"], "observer_activity": value}
        )


@pytest.mark.parametrize("value", [True, 0, "", "water", "static", {}, []])
def test_unknown_external_motion_rejected(value):
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {
                "casting": CASES[0]["input"]["casting"],
                "external_observations": [
                    {"manifestation": "soil", "label": "虚构", "motion": value}
                ],
            }
        )


def test_scenario_raw_relation_and_question_never_supply_omen_valence():
    for scenario in [None, "favorable_matter", "unfavorable_matter"]:
        out = calculate_meihua_cast(
            casting=CASES[0]["input"]["casting"],
            matter_scenario=scenario,
            observer_activity="walking",
            question="我在坐着看担水的人，快成功吗？",
            external_observations=[
                {
                    "manifestation": "actual_water",
                    "label": "虚构担水",
                    "motion": "moving",
                }
            ],
        )
        layer = out["interpretation"]["motion_context"]
        assert layer["observer"]["activity"] == "walking"
        row = layer["external_motion"][0]
        assert row["omen_valence"] is None
        assert all(
            r["full_clause_applies"] is None and r["omen_condition_met"] is None
            for r in row["moving_clauses"]
        )
        assert layer["combined_outcome"] is None


def test_omitted_activity_and_movement_are_not_read_from_words_or_material():
    out = calculate_meihua_cast(
        casting=CASES[0]["input"]["casting"],
        question="我行路时看见流动的水和搬土的人",
        external_observations=[
            {"manifestation": "actual_water", "label": "流动的水"},
            {"manifestation": "soil", "label": "搬土"},
        ],
    )
    layer = out["interpretation"]["motion_context"]
    assert layer["observer"]["activity"] is None
    assert [r["motion"] for r in layer["external_motion"]] == [None, None]
    assert all(
        "motion" not in r
        for r in out["interpretation"]["external_omens"]["reported_observations"]
    )


def test_count_candidates_keep_own_roles_and_qualified_pair_paths():
    out = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        observer_activity="seated",
        external_observations=[
            {
                "manifestation": "fired_pottery",
                "label": "虚构被搬动的瓦器",
                "motion": "moving",
            }
        ],
    )
    rows = out["interpretation"]["casting_readings"]
    assert [r["body"] for r in rows] == ["离", "乾"]
    for i, candidate in enumerate(rows):
        layer = candidate["motion_context"]
        assert layer["inner_roles"][0]["trigram"] == candidate["body"]
        for role in layer["inner_roles"]:
            assert at_path(out, role["fact_path"])["name"] == role["trigram"]
        row = layer["external_motion"][0]
        assert (
            row["qualification_fact_path"]
            == f"interpretation.casting_readings.{i}.external_omens.observations.0"
        )
        q = at_path(out, row["qualification_fact_path"])
        assert q["body"] == candidate["body"]
        assert row["omen_valence"] is None
    assert (
        at_path(
            out,
            rows[1]["motion_context"]["external_motion"][0]["qualification_fact_path"],
        )["qualification"]
        == "no_substantive_generation"
    )


def test_weather_excludes_motion_context_and_rejects_observer_activity():
    casting = CASES[0]["input"]["casting"]
    out = calculate_meihua_cast(casting=casting, interpretation_topic="weather")
    assert out["interpretation"]["motion_context"] is None
    bad = calculate_meihua_cast(
        casting=casting, interpretation_topic="weather", observer_activity="standing"
    )
    assert bad["error_code"] == "validation_error"


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_motion_agrees_on_rest_mcp_cli(tool, rest, tmp_path, capsys):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = (
        {"casting": CASES[0]["input"]["casting"]}
        if tool == "meihua_cast"
        else dict(TIME)
    )
    payload.update(
        observer_activity="standing",
        external_observations=[
            {"manifestation": "soil", "label": "虚构抬土", "motion": "moving"}
        ],
    )
    fields = suggested_fields(spec, view="motion")
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )
