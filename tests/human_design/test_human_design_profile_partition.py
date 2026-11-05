"""Independent exact geometry, actual-role fidelity and complete-run replay."""

import ast
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import longitude_activation, opposite_activation
from fatebridge.core.human_design_profile_partition import (
    METHOD,
    classify_profile_solar_arc,
    context_reading,
    profile_partition_report,
    source_facts,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_all3072_engine_free_frozen_boundary_and_midpoint_cases():
    path = FIXTURES / "human-design-profile-partition-reference.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "93e736205e647e2bdd7700b9f6deb37284d11d7c35d7ceba2c88e5c85d18a714"
    )
    ref = json.loads(path.read_text())
    assert ref["case_count"] == len(ref["cases"]) == 3072
    assert (
        hashlib.sha256(
            (FIXTURES / "human-design-profile-partition-source-facts.json").read_bytes()
        ).hexdigest()
        == ref["source_facts_sha256"]
    )
    assert (
        hashlib.sha256(
            (
                ROOT / "src/fatebridge/data/human_design/rave-2001-reference.json"
            ).read_bytes()
        ).hexdigest()
        == ref["gate_reference_sha256"]
    )
    for row in ref["cases"]:
        actual = classify_profile_solar_arc(row["personality_longitude"])
        for key, value in row.items():
            if key not in {"id", "personality_longitude"}:
                expected = [str(v) for v in value] if key.endswith("_ratio") else value
                assert actual[key] == expected, (row["id"], key, actual[key], expected)
    assert any(r["personality_longitude"] < 0 for r in ref["cases"])


def chart(p, d):
    activations = {}
    for side, longitude in (("personality", p), ("design", d)):
        activations[side] = [
            {"body": "Sun", **longitude_activation(longitude)},
            {"body": "Earth", "derived_from": "Sun", **opposite_activation(longitude)},
        ]
    profile = (
        f"{activations['personality'][0]['line']}/{activations['design'][0]['line']}"
    )
    return {"activations": activations, "profile": profile}


def test_observed_role_is_preserved_when_native_design_differs_at_an_ideal_cut():
    p = 302.8125
    d = math.nextafter(214.8125, -math.inf)
    c = chart(p, d)
    assert c["profile"] == "1/3"
    report = profile_partition_report(c)
    assert report["actual_profile_category"] == "foundation"
    assert report["ideal_partition"]["ideal_profile"] == "1/4"
    assert report["ideal_partition"]["angular_category"] == "transition"
    assert report["actual_profile_matches_ideal_partition"] is False
    assert (
        report["comparison_status"]
        == "observed_role_differs_from_exact_solar_arc_partition"
    )
    assert int(report["actual_solar_arc_residual_degrees_ratio"][0]) != 0
    assert "保留实际日地线号" in context_reading(report)["text"]
    assert c["profile"] == "1/3"


def test_exact_rational_strings_survive_json_with_extreme_binary64_inputs():
    for longitude in (-math.ulp(0.0), math.ulp(0.0), 0.1):
        value = classify_profile_solar_arc(longitude)
        encoded = json.loads(json.dumps(value))
        assert encoded == value
        for key in (
            "line_offset_arcseconds_ratio",
            "ideal_design_longitude_degrees_ratio",
        ):
            assert all(type(v) is str for v in encoded[key])
            assert int(encoded[key][1]) > 0


def test_public_source_widths_and_wording_ambiguity_are_not_relabelled():
    ref = json.loads(
        (FIXTURES / "human-design-profile-partition-source-facts.json").read_text()
    )
    facts = source_facts()
    for key in (
        "line_arcseconds",
        "foundation_arcseconds",
        "transition_arcseconds",
        "solar_arc_degrees",
        "foundation_profiles",
        "transition_profiles",
    ):
        assert facts[key] == ref[key]
    assert facts["source_wording_ambiguity"]["resolved"] is False
    assert facts["source_wording_ambiguity"]["profile_foundation_term"] == "Resonances"
    assert (
        facts["foundation_arcseconds"] + facts["transition_arcseconds"]
        == facts["line_arcseconds"]
    )


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), True, "302.5"]
)
def test_non_numeric_or_nonfinite_partition_input_is_rejected(value):
    with pytest.raises(ValueError):
        classify_profile_solar_arc(value)


@pytest.fixture(scope="module")
def complete():
    value = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1981,
            birth_month=5,
            birth_day=6,
            birth_hour=16,
            birth_minute=22,
            birth_timezone="Europe/London",
        ),
    )
    result = verify_human_design_reading(value)
    assert result["status"] == "verified_fixed_template_reading", result
    return value


def rehash(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )


def test_complete_new_context_is_field_bound_without_native_recalculation(complete):
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Native replay forbidden"),
    ):
        result = verify_human_design_reading(complete)
    assert (
        result["profile_partition_context_status"]
        == "verified_nominal_role_and_exact_solar_arc_partition"
    )
    assert complete["profile_partition_context"] == profile_partition_report(complete)
    assert complete["interpretation"]["profile_partition_context"] == context_reading(
        complete["profile_partition_context"]
    )
    assert complete["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "profile",
        "category",
        "ideal",
        "width",
        "wording",
        "basis",
        "text",
        "all_regions",
    ],
)
def test_rehashed_partition_tampering_is_rejected(complete, mutation):
    value = copy.deepcopy(complete)
    c = value["profile_partition_context"]
    if mutation == "profile":
        c["actual_profile"] = "1/4"
    elif mutation == "category":
        c["actual_profile_category"] = (
            "transition"
            if c["actual_profile_category"] == "foundation"
            else "foundation"
        )
    elif mutation == "ideal":
        c["ideal_partition"]["ideal_profile"] = "1/1"
    elif mutation == "width":
        c["source_facts"]["transition_arcseconds"] = 451
    elif mutation == "wording":
        c["source_facts"]["source_wording_ambiguity"]["resolved"] = True
    elif mutation == "basis":
        c["basis"][0]["value"] = "1/1"
    elif mutation == "text":
        value["interpretation"]["profile_partition_context"][
            "text"
        ] += " 精度已获独立认证。"
    elif mutation == "all_regions":
        value.pop("profile_partition_context")
        value["interpretation"].pop("profile_partition_context")
        value["interpretation"]["basis"].remove("profile_partition_context")
        for key in ("rulesets", "rule_trace"):
            value[key] = [
                r
                for r in value[key]
                if all(r.get(k) != METHOD for k in ("id", "rule_id", "ruleset_id"))
            ]
    rehash(value)
    assert verify_human_design_reading(value)["status"] == "rejected"
