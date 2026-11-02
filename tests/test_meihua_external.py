"""Declared external manifestations use source-qualified pairs, not raw signs."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/meihua_external_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]


def at_path(out, path):
    value = out
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_manual_source_pairs_preserve_raw_relation_and_distinct_qualification(case):
    plain = calculate_meihua_cast(casting=case["casting"])
    assert plain["meihua"]["body_trigram"]["name"] == case["body"]
    out = calculate_meihua_cast(
        casting=case["casting"], external_observations=[case["observation"]]
    )
    assert "error" not in out, out
    layer = out["interpretation"]["external_omens"]
    row = layer["observations"][0]
    assert layer["declaration_status"] == "caller_reported_unverified"
    assert row["body"] == case["body"]
    assert row["external_element"] == case["external_element"]
    assert row["raw_relation_to_body"] == case["raw_relation"]
    assert row["qualification"] == case["qualification"]
    if case["rule_index"] is not None:
        source = json.loads((FIXTURE / "source-reading.json").read_text())[
            "selected_rules"
        ][case["rule_index"]]
        assert row["quote"] == source["quote"]
        expected_pages = (
            [108, 109]
            if case["observation"]["manifestation"] == "red_purple_color"
            else [source["pdf_index"]]
        )
        assert row["quote_original_pdf_indices"] == expected_pages
    else:
        assert row["quote"] is row["rule_id"] is None
    assert at_path(out, row["body_fact_path"])["name"] == case["body"]
    assert at_path(out, row["reported_fact_path"]) == case["observation"]
    assert row["physical_causation_verified"] is False
    assert row["numeric_effect_strength"] is row["real_outcome"] is None
    assert layer["event_time"] is layer["combined_outcome"] is None
    assert layer["independent_verified_observations"] == 0
    assert [r["relation"] for r in out["meihua"]["stage_relations"]] == [
        r["relation"] for r in plain["meihua"]["stage_relations"]
    ]


def test_frozen_source_and_manual_cases_are_unchanged():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert (
        m["production_generated_expected_values"] is False
        and m["implementation_not_present"] is True
    )
    for name, digest in m["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("kind", ["furnace_flame", "actual_water", "fired_pottery"])
def test_counting_candidates_keep_their_own_original_body_and_source_pair(basis, kind):
    casting = {
        "method": "sound_groups",
        "first_count": 11,
        "second_count": 1,
        "hour_branch": "子",
        "line_sum_basis": basis,
    }
    out = calculate_meihua_cast(
        casting=casting,
        external_observations=[{"manifestation": kind, "label": "虚构工程双候选"}],
    )
    readings = out["interpretation"]["casting_readings"]
    assert len(readings) == 2
    expected = {
        "furnace_flame": {
            "离": ("体用比和", "not_addressed_in_selected_pairs"),
            "乾": ("用克体", "substantive_control"),
        },
        "actual_water": {
            "离": ("用克体", "substantive_control"),
            "乾": ("体生用", "not_addressed_in_selected_pairs"),
        },
        "fired_pottery": {
            "离": ("体生用", "not_addressed_in_selected_pairs"),
            "乾": ("用生体", "no_substantive_generation"),
        },
    }
    for i, candidate in enumerate(readings):
        row = candidate["external_omens"]["observations"][0]
        assert row["body"] == candidate["body"]
        assert (row["raw_relation_to_body"], row["qualification"]) == expected[kind][
            candidate["body"]
        ]
        assert row["body_fact_path"] == f"meihua.counting_variants.{i}.body_trigram"
        assert at_path(out, row["body_fact_path"])["name"] == row["body"]
        assert at_path(out, row["reported_fact_path"]) == {
            "manifestation": kind,
            "label": "虚构工程双候选",
        }


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [{"manifestation": "unknown", "label": "观察"}],
        [{"manifestation": "furnace_flame", "label": "   "}],
        [{"manifestation": "soil"}],
    ],
)
def test_absent_or_unknown_manifestations_are_not_invented(bad):
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {"casting": CASES[0]["casting"], "external_observations": bad}
        )


def test_weather_never_uses_external_body_relations():
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {
                "casting": CASES[0]["casting"],
                "interpretation_topic": "weather",
                "external_observations": [CASES[0]["observation"]],
            }
        )
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="weather"
    )
    assert out["interpretation"]["external_omens"] is None


@pytest.mark.parametrize(
    "topic", ["general", "planning", "reputation", "wealth", "transaction"]
)
def test_selected_external_layer_is_available_without_changing_topic(topic):
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic=topic,
        external_observations=[CASES[0]["observation"]],
    )
    assert out["interpretation"]["interpretation_topic"] == topic
    assert (
        out["interpretation"]["external_omens"]["observations"][0]["qualification"]
        == "substantive_control"
    )
    assert "外应" in out["summary"]


def test_no_observation_keeps_the_previous_summary_and_does_not_assert_absence():
    plain = calculate_meihua_cast(casting=CASES[0]["casting"])
    explicit_none = calculate_meihua_cast(
        casting=CASES[0]["casting"], external_observations=None
    )
    assert plain == explicit_none
    assert plain["interpretation"]["external_omens"] is None
    assert (
        plain["interpretation"]["evidence_scope"]["external_omens"] == "not_collected"
    )


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_external_card_agrees_on_three_public_surfaces(tool, rest, tmp_path, capsys):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = (
        {"casting": CASES[0]["casting"]}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 22,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    payload["external_observations"] = [CASES[0]["observation"]]
    fields = suggested_fields(spec, view="external")
    assert "interpretation.external_omens" in fields
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
        ],
    )
    result = asyncio.run(
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
            "--response-char-limit",
            "0",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert response.status_code == 200 and code == 0 and not result.is_error
    assert (
        business(response.json())
        == business(result.structured_content)
        == business(cli)
    )


def test_time_card_does_not_request_alternatives_that_time_casts_do_not_have():
    from fatebridge.application.examples import suggested_fields

    assert "interpretation.casting_readings" not in suggested_fields(
        SPECS["meihua_analysis"], view="external"
    )
    assert "interpretation.casting_readings" in suggested_fields(
        SPECS["meihua_cast"], view="external"
    )


def test_returned_records_and_rules_cannot_mutate_input_or_cached_source():
    from fatebridge.core.meihua_external import external_manifestation_ruleset

    observation = dict(CASES[0]["observation"])
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], external_observations=[observation]
    )
    out["interpretation"]["external_omens"]["reported_observations"][0][
        "label"
    ] = "changed"
    assert observation == CASES[0]["observation"]
    rules = external_manifestation_ruleset()
    rules["rules"][0]["qualification"] = "changed"
    assert (
        external_manifestation_ruleset()["rules"][0]["qualification"]
        == "substantive_control"
    )
