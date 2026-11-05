"""All original node epochs, raw independent replay and non-erasing acceptance."""

import ast
import math
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.human_design import check_human_design_calendar_nodes as checker
from scripts.human_design import gen_human_design_calendar_nodes as generator

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tests/data/human_design/calendar_nodes"
E = BASE / "evidence"
NATIVE_SHA256 = "98b10ed9b3c4e5eb4fc7e799c756df31516a990e07c017ccffa3bc2aedb4eb54"
COMPARISON_SHA256 = "7afa30baed78e6e6afb62841629d0cc13fa798b7ef766b3b9d4c506ce7338d9e"


@pytest.fixture(scope="module")
def materials():
    plan, reference, legacy = checker.reference()
    production = checker.capture()
    return plan, reference, legacy, production, checker.compare(production)


def test_independent_reference_keeps_all_original_epochs_controls_and_dependencies(
    materials,
):
    plan, reference, _, _, _ = materials
    assert (
        plan["epoch_count"]
        == reference["epoch_count"]
        == len(reference["rows"])
        == 2400
    )
    assert reference["original122_controls_exact"] is True
    assert len(reference["control_rows"]) == 122
    assert reference["package_files_before"] == reference["package_files_after"]
    assert len(reference["package_files_before"]) == 925
    assert (
        reference["kernel_sha256"]
        == "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
    )
    tree = ast.parse(
        (ROOT / "scripts/human_design/gen_human_design_calendar_nodes.py").read_text()
    )
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imports += [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]
    assert not any(
        n.startswith(("fatebridge", "swisseph", "tests", "scripts")) for n in imports
    )
    assert plan["tolerance_arcseconds"] == 1.0


def matvec(matrix, vector):
    return [
        math.fsum(a * b for a, b in zip(row, vector, strict=True)) for row in matrix
    ]


def reconstructed_node(row, prefix):
    matrix = row["icrf_to_mean_ecliptic_of_date_matrix"]
    r = matvec(matrix, row[prefix + "geocentric_position_icrf_km"])
    v = matvec(matrix, row[prefix + "geocentric_velocity_icrf_km_per_day"])
    hx = r[1] * v[2] - r[2] * v[1]
    hy = r[2] * v[0] - r[0] * v[2]
    return math.degrees(math.atan2(hx, -hy) + row["nutation_longitude_radians"]) % 360


def test_all2522_geometric_and_light_time_node_facts_replay_from_raw_states(materials):
    _, reference, _, _, _ = materials
    maximum = 0.0
    for row in reference["rows"] + reference["control_rows"]:
        assert row["jd_tdb"] - row["retarded_jd_tdb"] > 0
        for prefix, key in (
            ("", "geometric_node_longitude"),
            ("retarded_", "node_longitude"),
        ):
            error = (
                abs(math.remainder(reconstructed_node(row, prefix) - row[key], 360))
                * 3600
            )
            maximum = max(maximum, error)
            assert error <= 1e-7
    assert maximum <= 1e-7


def test_full4800_comparison_replays_without_native_and_keeps_all_original_failures(
    materials,
):
    _, _, _, production, expected = materials
    with (
        patch(
            "fatebridge.core.astro.runtime.ephemeris_call",
            side_effect=AssertionError("native replay"),
        ),
        patch(
            "fatebridge.core.astro.native_execution.calculate",
            side_effect=AssertionError("native dispatch"),
        ),
    ):
        actual = checker.compare(production)
    assert actual == expected
    swiss, moshier = [actual["backends"][k] for k in ("selected", "moshier_diagnostic")]
    for row in (swiss, moshier):
        assert row["node_observation_count"] == 2400 and row["not_assessed"] == 0
        assert row["actual_backend_or_batch_rejection_count"] == 0
        assert row["all_fresh_physical_values_equal_original"] is True
    assert (
        swiss["position_failure_count"] == 0
        and swiss["node_projection_accepted_count"] == 2400
    )
    assert swiss["maximum_position_error_arcseconds"] == pytest.approx(
        0.11319074629909665, abs=1e-12
    )
    assert swiss["original_physical_failure_count"] == 1
    assert swiss["accepted_with_original_physical_rows_count"] == 2399
    assert (
        moshier["position_failure_count"] == 2248
        and moshier["node_projection_accepted_count"] == 148
    )
    assert moshier["maximum_position_error_arcseconds"] == pytest.approx(
        62.51129812824274, abs=1e-12
    )
    assert moshier["different_level_counts"] == {
        "gate": 2,
        "line": 8,
        "color": 80,
        "tone": 500,
        "base": 2210,
        "tone_orientation": 188,
    }
    assert moshier["original_physical_failure_count"] == 2265
    assert moshier["accepted_with_original_physical_rows_count"] == 65
    assert actual["status"] == "failed"
    assert (
        actual["complete_continuous_calendar_certified"]
        is actual["official_human_design_node_convention_certified"]
        is actual["new_independent_mean_node_evidence"]
        is actual["real_world_prediction_validated"]
        is False
    )


def test_one_arcsecond_pass_does_not_certify_exact_subdivision(materials):
    rows = materials[-1]["backends"]["moshier_diagnostic"]["rows"]
    near = [
        r
        for r in rows
        if r["position_within_original1arcsecond"]
        and any(r["different_levels_using_current_mapping"].values())
    ]
    assert len(near) == 4
    assert all(not r["node_projection_accepted"] for r in near)
    assert all(r["error_arcseconds"] <= 1 for r in near)
    assert all(
        "base" in r["different_levels_using_current_mapping"]["NorthNode"] for r in near
    )


@pytest.mark.parametrize(
    "fault",
    [
        "model",
        "flags",
        "missing_position",
        "missing_prefix",
        "opposition",
        "nonfinite",
        "incomplete_batch",
    ],
)
def test_same_longitude_cannot_hide_wrong_source_or_incomplete_batch(materials, fault):
    _, reference, legacy, production, _ = materials
    actual = deepcopy(production["backends"]["selected"]["rows"][0])
    if fault == "model":
        actual["positions"]["NorthNode"]["native_return_flag_model"] = "moshier"
    if fault == "flags":
        for values in (actual["positions"], actual["observed_prefix"]):
            values["NorthNode"]["return_flags"] = 260
    if fault == "missing_position":
        actual["positions"].pop("Pluto")
    if fault == "missing_prefix":
        actual["observed_prefix"].pop("Moon")
    if fault == "opposition":
        actual["positions"]["SouthNode"]["derivation_source_longitude"] += 0.01
    if fault == "nonfinite":
        actual["positions"]["NorthNode"]["longitude"] = float("nan")
    if fault == "incomplete_batch":
        actual["complete_batch_returned"] = False
    physical = [
        {**r, "original_index": j}
        for j, r in enumerate(legacy["backends"]["selected"]["rows"][:10])
    ]
    result = checker.compare_row(actual, reference["rows"][0], physical, "swieph")
    assert (
        result["evaluation_status"] == "not_assessed"
        and result["node_projection_accepted"] is False
    )
    assert result["accepted_with_original_physical_rows"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing_file",
        "detached_file",
        "count",
        "wrong_role",
        "invented_accuracy",
        "context_removed",
        "unknown_body",
        "nonfinite_range",
        "nonfinite_context",
        "boolean_edition",
        "duplicate_context",
    ],
)
def test_source_context_flags_cannot_replace_complete_observations(materials, fault):
    value = deepcopy(materials[3])
    source = value["source_evidence"]
    if fault == "missing_file":
        source["files"].pop()
    if fault == "detached_file":
        source["files"][0]["sha256"] = "0" * 64
    if fault == "count":
        source["contexts"][0]["observed_evaluation_count"] -= 1
    if fault == "wrong_role":
        source["contexts"][0]["role"] = "solar_root"
    if fault == "invented_accuracy":
        source["accuracy_certified"] = True
    if fault == "context_removed":
        source["contexts"].pop()
    if fault == "unknown_body":
        source["contexts"][0]["body"] = "NotANode"
    if fault == "nonfinite_range":
        source["files"][0]["start_julian_day_tt"] = float("nan")
    if fault == "nonfinite_context":
        source["contexts"][0]["maximum_jd_tt"] = float("inf")
    if fault == "boolean_edition":
        source["files"][0]["de_number"] = True
    if fault == "duplicate_context":
        original = source["contexts"][0]
        duplicate = deepcopy(original)
        duplicate["observed_evaluation_count"] = 1
        original["observed_evaluation_count"] -= 1
        source["contexts"].append(duplicate)
    assert checker.source_contexts_accepted(value) is False


@pytest.mark.parametrize(
    "fault", ["missing", "reordered", "duplicate", "retimed", "backend"]
)
def test_fixed_cohort_cannot_be_narrowed_or_rebound(materials, fault, monkeypatch):
    plan, reference, legacy, production, _ = materials
    monkeypatch.setattr(checker, "reference", lambda: (plan, reference, legacy))
    value = deepcopy(production)
    rows = value["backends"]["selected"]["rows"]
    if fault == "missing":
        rows.pop()
    if fault == "reordered":
        rows[0], rows[1] = rows[1], rows[0]
    if fault == "duplicate":
        rows[1] = deepcopy(rows[0])
    if fault == "retimed":
        rows[0]["jd_tt"] += 0.01
    if fault == "backend":
        value["backends"].pop("moshier_diagnostic")
    with pytest.raises(ValueError):
        checker.compare(value)


def test_reader_rejects_non_object_json(tmp_path):
    path = tmp_path / "not-an-object.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        generator.read(path)
