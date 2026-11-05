"""Reported source categories resolve before arithmetic, never from a story."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaCastRequest
from fatebridge.services.meihua import calculate_meihua_cast
from tests.meihua.test_meihua_external import at_path
from tests.support.transports import SPECS, business, rest, surface_calls

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_observed_categories_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
ORIGINAL = [c for c in CASES if c["kind"] == "reused_original_arithmetic_example"]
GRID = [c for c in CASES if c["kind"] == "synthetic_parameter_context"]
PAIRS = sorted(
    {(c["input"]["subject_category"], c["input"]["direction"]) for c in GRID}
)


def assert_case(case):
    out = calculate_meihua_cast(casting=case["input"])
    assert "error" not in out, out
    cast = out["meihua"]
    for key in ["upper_number", "lower_number", "moving_line"]:
        assert cast["seed"][key] == case["expected"][key], (case["id"], key)
    for name in ["base", "changed", "mutual"]:
        assert (
            cast[name + "_hexagram"]["binary_code"] == case["expected"][name + "_code"]
        )
    for name in ["body", "use"]:
        assert cast[name + "_trigram"]["name"] == case["expected"][name]
    basis = cast["seed"]["observation_basis"]
    reference = json.loads((FIXTURE / "source-reading.json").read_text())
    assert (
        basis["subject"]["trigram"]
        == reference["subjects"][case["input"]["subject_category"]]["trigram"]
    )
    assert (
        basis["direction"]["trigram"]
        == reference["directions"][case["input"]["direction"]]["trigram"]
    )
    assert (
        basis["subject"]["quote"]
        == reference["subjects"][case["input"]["subject_category"]]["quote"]
    )
    assert basis["subject"]["category"] == case["input"]["subject_category"]
    assert basis["direction"]["value"] == case["input"]["direction"]
    assert basis["direction"]["role"] == case["input"]["direction_role"]
    assert (
        at_path(out, basis["subject"]["category_fact_path"])
        == case["input"]["subject_category"]
    )
    assert (
        at_path(out, basis["direction"]["value_fact_path"])
        == case["input"]["direction"]
    )
    assert (
        at_path(out, basis["direction"]["role_fact_path"])
        == case["input"]["direction_role"]
    )
    assert basis["declaration_status"] == "caller_reported_unverified"
    assert (
        basis["scene_verified"]
        is basis["compass_verified"]
        is basis["casting_trigger_adjudicated"]
        is False
    )
    assert basis["independent_verified_observations"] == 0
    assert cast["ruleset_id"] == "meihua_observed_categories_nlc1925_v1"
    assert out["interpretation"]["status"] == "conditional_on_reported_observation"
    assert out["input_normalized"]["casting"] == case["input"]
    return out


@pytest.mark.parametrize("case", ORIGINAL, ids=lambda c: c["id"])
def test_five_reused_original_arithmetic_examples(case):
    assert_case(case)


@pytest.mark.parametrize("category,direction", PAIRS)
def test_twelve_hours_for_each_source_category_and_direction(category, direction):
    rows = [
        c
        for c in GRID
        if c["input"]["subject_category"] == category
        and c["input"]["direction"] == direction
    ]
    assert len(rows) == 12
    for case in rows:
        assert_case(case)


def test_frozen_reference_bytes_and_real_observation_count():
    m = json.loads((FIXTURE / "manifest.json").read_text())
    assert m["implementation_not_present"] and m["request_method_not_present"]
    assert m["production_generated_expected_values"] is False
    assert m["new_independent_real_observations"] == 0
    assert len(ORIGINAL) == 5 and len(GRID) == 480
    assert (
        len({(c["expected"]["base_code"], c["expected"]["moving_line"]) for c in GRID})
        == 240
    )
    for name, digest in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


def test_from_toward_and_at_preserve_the_reported_side_without_inversion():
    for role in ["from", "toward", "at"]:
        case = deepcopy(ORIGINAL[1])
        case["input"]["direction_role"] = role
        out = assert_case(case)
        assert out["meihua"]["seed"]["lower_number"] == 3
        assert out["interpretation"]["motion_context"]["observer"]["activity"] is None
        assert out["interpretation"]["external_omens"] is None


def test_declared_fields_are_not_reclassified_by_question_or_description():
    inp = {
        **ORIGINAL[4]["input"],
        "subject_description": "虚构描述提到木、东、坤和数字八，不能替换明确字段",
    }
    a = calculate_meihua_cast(casting=inp, question="把这个换成巽会如何？")
    b = calculate_meihua_cast(casting=ORIGINAL[4]["input"])
    assert a["meihua"]["seed"]["upper_number"] == 3
    assert a["meihua"]["seed"]["lower_number"] == 2
    assert a["meihua"]["base_hexagram"] == b["meihua"]["base_hexagram"]
    assert a["meihua"]["changed_hexagram"] == b["meihua"]["changed_hexagram"]


@pytest.mark.parametrize(
    "replacement",
    [
        {"subject_category": "wood"},
        {"subject_category": "animal_sound"},
        {"subject_category": True},
        {"direction": "center"},
        {"direction": 180},
        {"direction_role": "heading_opposite"},
        {"subject_description": "  "},
        {"single_subject_confirmed": False},
        {"single_subject_confirmed": 1},
        {"upper_trigram": "巽"},
        {"lower_trigram": "坎"},
    ],
)
def test_unknown_or_mixed_facts_are_rejected(replacement):
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate(
            {"casting": {**ORIGINAL[0]["input"], **replacement}}
        )


@pytest.mark.parametrize(
    "missing",
    [
        "subject_category",
        "subject_description",
        "single_subject_confirmed",
        "direction",
        "direction_role",
        "hour_branch",
    ],
)
def test_necessary_source_facts_are_never_defaulted(missing):
    inp = dict(ORIGINAL[0]["input"])
    inp.pop(missing)
    with pytest.raises(ValidationError):
        MeihuaCastRequest.model_validate({"casting": inp})


def test_new_mapping_preserves_existing_selected_cast_and_interpretation_facts():
    source = json.loads((FIXTURE / "source-reading.json").read_text())
    for c in ORIGINAL:
        new = calculate_meihua_cast(casting=c["input"], season_month_branch="子")
        old = calculate_meihua_cast(
            casting={
                "method": "observed_trigrams",
                "upper_trigram": source["subjects"][c["input"]["subject_category"]][
                    "trigram"
                ],
                "lower_trigram": source["directions"][c["input"]["direction"]][
                    "trigram"
                ],
                "hour_branch": c["input"]["hour_branch"],
            },
            season_month_branch="子",
        )
        for key in [
            "base_hexagram",
            "changed_hexagram",
            "mutual_hexagram",
            "body_trigram",
            "use_trigram",
            "stage_relations",
            "seasonal_strength",
        ]:
            assert new["meihua"][key] == old["meihua"][key], key
        for key in [
            "internal_countercontrol",
            "seasonal_qualification",
            "stage_emphasis",
            "motion_context",
            "traditional_stage_readings",
        ]:
            assert new["interpretation"][key] == old["interpretation"][key], key


def test_weather_keeps_no_body_use_interpretation_after_source_lookup():
    out = calculate_meihua_cast(
        casting=ORIGINAL[4]["input"], interpretation_topic="weather"
    )
    assert "error" not in out
    assert out["meihua"]["seed"]["upper_number"] == 3
    assert out["interpretation"]["motion_context"] is None
    assert out["interpretation"]["stage_emphasis"] is None
    assert out["interpretation"]["evidence_scope"]["body_use_applied"] is False


def test_profile_copy_does_not_change_future_mappings():
    from fatebridge.core.meihua_observed import observed_category_profile

    p = observed_category_profile()
    reference = json.loads((FIXTURE / "source-reading.json").read_text())
    for key in ["subjects", "directions", "source"]:
        assert p[key] == reference[key]
    p["subjects"]["dry_wood"]["number"] = 5
    assert observed_category_profile()["subjects"]["dry_wood"]["number"] == 3


def test_new_category_method_agrees_on_rest_native_mcp_and_cli(surface_calls):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS["meihua_cast"]
    payload = {"casting": ORIGINAL[4]["input"]}
    fields = suggested_fields(spec, view="observation_source")
    response, mcp, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )
