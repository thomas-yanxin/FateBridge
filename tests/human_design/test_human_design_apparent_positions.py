"""Same-run position binding, explicit legacy scope and rehashed forgery checks."""

import copy
import json
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_apparent_positions import (
    METHOD,
    geometry,
    observed_coordinates,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_apparent_positions import checked_context

SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("failed_body", ["NorthNode", "Mercury"])
def test_failed_reference_retains_observed_prefix_without_inventing_positions(
    monkeypatch,
    failed_body,
):
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design_mechanics import BODY_IDS

    original = runtime.ephemeris_call
    body_id = (
        runtime.swe.TRUE_NODE if failed_body == "NorthNode" else BODY_IDS[failed_body]
    )

    def native(operation, *args, **kwargs):
        if (
            operation == "calc"
            and args[1] == body_id
            and args[2] & runtime.swe.FLG_MOSEPH
        ):
            raise RuntimeError("controlled reference failure")
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    value = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
        ),
    )
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check
    c = value["apparent_position_context"]
    assert c["observed_physical_position_count"] == sum(
        len(b["bodies"]) * b["observed_count"] for b in c["batches"]
    )
    if failed_body == "Mercury":
        assert c["partial_physical_batch_count"] > 0
        partial = next(b for b in c["batches"] if len(b["bodies"]) < 10)
        assert [r["body"] for r in partial["bodies"]] == ["Sun", "Moon"]
        partial["bodies"].pop()
        assert verify_human_design_reading(value)["status"] == "rejected"
    else:
        assert c["partial_physical_batch_count"] == 0


def test_nonfinite_supplementary_coordinates_are_unavailable_not_defaults():
    coords = observed_coordinates((12.0, float("nan"), float("inf"), 1.0, 0, 0))
    assert coords == [12.0, "nan", "inf", 1.0]
    rows = geometry(
        [
            {"body": "Sun", "native_coordinates": [0.0, 0.0, 1.0, 1.0]},
            {"body": "Moon", "native_coordinates": coords},
        ]
    )
    assert rows == [
        {
            "body": "Moon",
            "status": "supplementary_coordinates_unavailable",
            "physical_accuracy_certified": False,
        }
    ]


@pytest.fixture(scope="module")
def complete():
    # Disclosed development probe near the previously discovered failure;
    # this civil time is not claimed identical to the frozen TT reference.
    value = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=2236,
            birth_month=3,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
        ),
    )
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check
    return value


def test_bound_geometry_uses_all_physical_coordinates_without_a_native_replay(complete):
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier recalculated an ephemeris"),
    ):
        check = verify_human_design_reading(complete)
    context = complete["apparent_position_context"]
    assert (
        check["apparent_position_context_status"]
        == "verified_supplied_native_batch_geometry"
    )
    assert check["checked_apparent_position_batch_count"] == len(context["batches"])
    assert checked_context(complete) == context
    assert all(
        len(b["bodies"]) == 10 and len(b["solar_projection"]) == 9
        for b in context["batches"]
    )
    assert all(
        not b["physical_occultation_certified"]
        for batch in context["batches"]
        for b in batch["solar_projection"]
    )
    assert context["original_human_design_software_convention_certified"] is False
    assert context["native_execution_authenticated"] is False
    assert context["observed_physical_position_count"] == 10 * sum(
        b["observed_count"] for b in context["batches"]
    )
    assert len(complete["interpretation"]["statements"]) == 10
    assert (
        "透明太阳质量分布延拓"
        in complete["interpretation"]["apparent_position_context"]["text"]
    )


def test_sorted_json_keeps_array_batch_identity_and_reading(complete):
    check = verify_human_design_reading(
        json.loads(json.dumps(complete, sort_keys=True))
    )
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.mark.parametrize(
    "fault",
    [
        "remove_all",
        "unknown_contract",
        "remove_report",
        "remove_reading",
        "remove_ruleset",
        "remove_trace",
        "wrong_raw_latitude",
        "wrong_distance",
        "wrong_geometry",
        "wrong_nominal_side",
        "wrong_native_longitude",
        "wrong_native_speed",
        "unobserved_flag_convention",
        "incomplete_batches",
        "inflated_observation_count",
        "wrong_radius",
        "invented_visibility",
        "invented_original_convention",
        "wrong_prose",
        "rebased_basis",
    ],
)
def test_rehashed_current_or_unknown_result_cannot_forge_geometry_or_scope(
    complete, fault
):
    value = copy.deepcopy(complete)
    c = value["apparent_position_context"]
    nominal = next(
        b for b in c["batches"] if b["id"] == c["nominal_side_batch_ids"]["design"]
    )
    if fault in {"remove_all", "unknown_contract", "remove_report"}:
        value.pop("apparent_position_context")
    if fault in {"remove_all", "unknown_contract", "remove_reading"}:
        value["interpretation"].pop("apparent_position_context")
        value["interpretation"]["basis"].remove("apparent_position_context")
    if fault in {"remove_all", "unknown_contract", "remove_ruleset"}:
        value["rulesets"] = [r for r in value["rulesets"] if r["id"] != METHOD]
    if fault in {"remove_all", "unknown_contract", "remove_trace"}:
        value["rule_trace"] = [r for r in value["rule_trace"] if r["rule_id"] != METHOD]
    if fault == "unknown_contract":
        value["run_metadata"]["contract_sha256"] = "0" * 64
    elif fault == "wrong_raw_latitude":
        nominal["bodies"][1]["native_coordinates"][1] += 1
    elif fault == "wrong_distance":
        nominal["bodies"][0]["native_coordinates"][2] *= 2
    elif fault == "wrong_geometry":
        nominal["solar_projection"][0]["projection_margin_radians"] += 0.0001
    elif fault == "wrong_nominal_side":
        c["nominal_side_batch_ids"]["design"] = c["nominal_side_batch_ids"][
            "personality"
        ]
    elif fault == "wrong_native_longitude":
        nominal["bodies"][1]["native_coordinates"][0] += 0.0001
    elif fault == "wrong_native_speed":
        nominal["bodies"][1]["native_coordinates"][3] += 0.0001
    elif fault == "unobserved_flag_convention":
        nominal["bodies"][1]["return_flags"] |= 512
    elif fault == "incomplete_batches":
        c["batches"].pop()
    elif fault == "inflated_observation_count":
        nominal["observed_count"] += 1
    elif fault == "wrong_radius":
        c["nominal_solar_radius_m"] += 1
    elif fault == "invented_visibility":
        c["visibility_certified"] = True
    elif fault == "invented_original_convention":
        c["original_human_design_software_convention_certified"] = True
    elif fault == "wrong_prose":
        value["interpretation"]["apparent_position_context"]["text"] += "原典现已满分。"
    elif fault == "rebased_basis":
        value["interpretation"]["apparent_position_context"]["basis"][0][
            "path"
        ] = "profile"
    check = verify_human_design_reading(value)
    assert check["status"] == "rejected", (fault, check)
    assert check["apparent_position_context_status"] == "not_verified"


def test_original_legacy_receipts_keep_scope_instead_of_new_certification():
    from tests.human_design.test_human_design_publisher import RUNS

    for row in RUNS:
        check = verify_human_design_reading(row["run"])
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            check["apparent_position_context_status"]
            == "not_in_declared_legacy_contract"
        )


def test_an_old_schema_label_cannot_hide_present_new_markers(complete):
    value = copy.deepcopy(complete)
    value["run_metadata"][
        "contract_sha256"
    ] = "168d79463454686ee3e8afb731ea2ee8d29ae906f0d9ca88c5cf364ea7daba30"
    value["apparent_position_context"]["batches"].pop()
    assert verify_human_design_reading(value)["status"] == "rejected"
