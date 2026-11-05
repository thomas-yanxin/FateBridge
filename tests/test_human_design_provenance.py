"""Raw flags, computed models and fixed-template provenance must agree."""

from copy import deepcopy

import pytest

from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import runtime
from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design import positions_at_tt
from fatebridge.core.human_design_precision import compare_node_backends
from fatebridge.core.human_design_provenance import position_flag_model
from fatebridge.core.human_design_time import sun_at_tt
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_provenance import verify_selected_provenance
from tests.ephemeris_context import moshier_ephemeris

SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.fixture(scope="module")
def complete_run():
    with moshier_ephemeris():
        result = execute_tool(SPEC, SPEC.request_model(**example_input(SPEC)))
    assert verify_human_design_reading(result)["status"] == (
        "verified_fixed_template_reading"
    )
    return result


def reseal(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    return value


@pytest.mark.parametrize(
    "tamper",
    [
        "north_native_flag",
        "south_native_flag",
        "earth_speed",
        "south_speed",
        "require_swiss_files",
        "physical_scope",
        "factor_models",
    ],
)
def test_rehashed_provenance_contradictions_are_rejected(complete_run, tamper):
    value = deepcopy(complete_run)
    policy = value["calculation_policy"]
    if tamper == "require_swiss_files":
        policy["require_swiss_files"] = True
    elif tamper == "physical_scope":
        policy["ephemeris_model_scope"] = "all_factor_computation_models"
    elif tamper == "factor_models":
        policy["nonphysical_factor_models"]["personality"]["Earth"] = "jpl"
    else:
        body = {
            "north_native_flag": "NorthNode",
            "south_native_flag": "SouthNode",
            "earth_speed": "Earth",
            "south_speed": "SouthNode",
        }[tamper]
        row = next(a for a in value["activations"]["personality"] if a["body"] == body)
        if tamper.endswith("_flag"):
            row["native_return_flag_model"] = "swieph"
        else:
            row["longitude_speed"] += 0.25
    assert verify_human_design_reading(reseal(value))["status"] == "rejected"


# Swiss public flag bits change the coordinate/target or speed convention.
# The declared HD calculation requests none of these, even when a backend bit
# itself is valid. This is a protocol check, not a test of numerical astronomy.
INCOMPATIBLE_FLAGS = [
    8,
    16,
    32,
    64,
    128,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
    262144,
    524288,
    1048576,
]


@pytest.mark.parametrize("extra", INCOMPATIBLE_FLAGS)
def test_live_position_entry_rejects_undeclared_frame_or_target_flags(
    monkeypatch, extra
):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *args: ((10.0, 0, 1, 0.5, 0, 0), 2 | 256 | extra),
    )
    with pytest.raises(RuntimeError):
        positions_at_tt(2451545.0, "true")


@pytest.mark.parametrize("extra", INCOMPATIBLE_FLAGS)
def test_design_sun_rejects_undeclared_frame_or_target_flags(monkeypatch, extra):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *args: ((10.0, 0, 1, 0, 0, 0), 2 | extra),
    )
    with pytest.raises(RuntimeError):
        sun_at_tt(2451545.0)


@pytest.mark.parametrize("flags", [True, 2, 3 | 256, 6 | 256, 7 | 256])
def test_live_position_entry_requires_one_backend_and_a_computed_speed(
    monkeypatch, flags
):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *args: ((10.0, 0, 1, 0.0, 0, 0), flags),
    )
    with pytest.raises(RuntimeError):
        positions_at_tt(2451545.0, "true")


@pytest.mark.parametrize("model,flag", [("jpl", 1), ("swieph", 2), ("moshier", 4)])
def test_public_flag_contract_accepts_each_actual_backend_without_changing_frame(
    model, flag
):
    assert position_flag_model(flag | 256) == model
    assert position_flag_model(flag, require_speed=False) == model
    with pytest.raises(ValueError):
        position_flag_model(flag)


@pytest.mark.parametrize("bad", [None, True, False, 258.0, "258", -1, 0, 256])
def test_malformed_or_missing_native_flag_is_not_a_computation_model(bad):
    with pytest.raises(ValueError):
        position_flag_model(bad)


@pytest.mark.parametrize("node_mode", ["true", "mean"])
@pytest.mark.parametrize("empty_files", [False, True])
def test_real_complete_runs_keep_both_node_conventions_and_current_file_environment(
    node_mode, empty_files
):
    def check():
        value = execute_tool(
            SPEC, SPEC.request_model(**{**example_input(SPEC), "node_mode": node_mode})
        )
        verification = verify_human_design_reading(value)
        assert verification["status"] == "verified_fixed_template_reading", verification
        assert verification["checked_nominal_provenance_activation_count"] == 26
        assert value["calculation_policy"]["position_frame_scope"] == "physical_bodies"
        for rows in value["activations"].values():
            for row in rows:
                if row["body"] in {"NorthNode", "SouthNode"}:
                    assert row["native_return_flag_model"] == position_flag_model(
                        row["return_flags"]
                    )
                    if node_mode == "mean":
                        assert row["ephemeris_model"] == ANALYTICAL_MEAN_NODE_MODEL

    if empty_files:
        with moshier_ephemeris():
            check()
    else:
        check()


@pytest.mark.parametrize(
    "tamper,expected_code",
    [
        ("speed_nan", "invalid_longitude_speed"),
        ("speed_bool", "invalid_longitude_speed"),
        ("wrong_model", "activation_model_flag_mismatch"),
        ("missing_node_label", "native_flag_label_mismatch"),
        ("ambiguous_backend", "invalid_position_return_flags"),
        ("missing_speed_bit", "invalid_position_return_flags"),
        ("wrong_frame_bit", "invalid_position_return_flags"),
        ("swiss_policy_string", "incomplete_or_invalid_provenance_policy"),
        ("strict_jpl", "physical_backend_policy_mismatch"),
        ("wrong_physical_summary", "calculation_provenance_policy_mismatch"),
        ("wrong_physical_frame_scope", "calculation_provenance_policy_mismatch"),
        ("wrong_node_frame", "calculation_provenance_policy_mismatch"),
        ("wrong_node_mode", "activation_model_flag_mismatch"),
    ],
)
def test_provenance_field_checks_report_the_specific_contradiction(
    complete_run, tamper, expected_code
):
    value = deepcopy(complete_run)
    row = value["activations"]["personality"][0]
    node = next(
        r for r in value["activations"]["personality"] if r["body"] == "NorthNode"
    )
    policy = value["calculation_policy"]
    if tamper == "speed_nan":
        row["longitude_speed"] = float("nan")
    elif tamper == "speed_bool":
        row["longitude_speed"] = False
    elif tamper == "wrong_model":
        row["ephemeris_model"] = "jpl"
    elif tamper == "missing_node_label":
        node.pop("native_return_flag_model")
    elif tamper == "ambiguous_backend":
        row["return_flags"] = 256 | 2 | 4
    elif tamper == "missing_speed_bit":
        row["return_flags"] &= ~256
    elif tamper == "wrong_frame_bit":
        row["return_flags"] |= 32768
    elif tamper == "swiss_policy_string":
        policy["require_swiss_files"] = "false"
    elif tamper == "strict_jpl":
        policy["physical_backend_policy"] = "strict_jpl"
    elif tamper == "wrong_physical_summary":
        policy["ephemeris_model"] = "swieph"
    elif tamper == "wrong_physical_frame_scope":
        policy["position_frame_scope"] = "all_factors"
    elif tamper == "wrong_node_frame":
        policy["lunar_node_frame"] = "apparent_physical_body"
    else:
        policy["node_mode"] = "mean"
    errors = verify_selected_provenance(value)["errors"]
    assert expected_code in {e["code"] for e in errors}, errors


def test_position_bits_match_the_installed_official_library():
    assert (
        runtime.swe.FLG_JPLEPH,
        runtime.swe.FLG_SWIEPH,
        runtime.swe.FLG_MOSEPH,
        runtime.swe.FLG_SPEED,
    ) == (1, 2, 4, 256)


@pytest.mark.parametrize("flags", [4, 4 | 256 | 32768, 2 | 256, True])
def test_node_reference_with_wrong_frame_or_uncomputed_speed_is_unavailable(
    complete_run, monkeypatch, flags
):
    monkeypatch.setattr(
        runtime, "ephemeris_call", lambda *args: ((100.0, 0, 0, 0.0, 0, 0), flags)
    )
    report = compare_node_backends(complete_run, "true")
    assert report["status"] == "reference_unavailable"
    assert report["mechanical_comparison"] is None and report["rows"] == []
