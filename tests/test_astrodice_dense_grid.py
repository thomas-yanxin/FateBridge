"""Dense constraints retain the coarse evidence, noise model and fixed gates."""

import copy
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import audit_astrodice_local_reference as audit
from scripts.astrodice_interval_reference import quality, replay_interval, system

OLD = Path(__file__).parent / "fixtures/astrodice-local-interval-holdout-v1"


def linear_row():
    return {
        "id": "new",
        "role": "known_control",
        "body": "Venus",
        "date_tt": "2020-01-01T12:00:00",
        "jd_tt": 2458849.0,
        "samples": {
            str(t): {
                "printed_angles": [f"{(359.9996 + t / 1e6) % 360:.9f}", "1.000000000"],
                "returned_jd_tt_string": str(t),
            }
            for t in range(-1440, 1441, 5)
        },
    }


def dense_plan():
    plan = json.loads((OLD / "protocol.json").read_text())
    plan.update(
        local_interval_method_id="local_printed_angle_interval_lp_grid5_v2",
        local_grid_step_seconds=5,
        explicit_offsets_seconds={"Venus": list(range(-1440, 1441, 5))},
    )
    return plan


def test_all_old_constraints_are_retained_with_the_same_full_printing_interval():
    row = linear_row()
    a, b, baseline, scale = system(row, None, 810, 5, 0)
    dense_a, dense_b, dense_baseline, dense_scale = system(
        row, None, 810, 5, 0, step_seconds=5
    )
    assert baseline == dense_baseline and scale == dense_scale == F(36, 10**7)
    old = {(tuple(v), bound) for v, bound in zip(a, b)}
    new = {(tuple(v), bound) for v, bound in zip(dense_a, dense_b)}
    assert old < new and len(dense_a) == 2 * len(a)


def test_a_new_five_second_observation_is_actually_constrained():
    row = linear_row()
    before = system(row, None, 60, 3, 0)
    row["samples"]["5"]["printed_angles"][0] = "359.999900000"
    assert system(row, None, 60, 3, 0) == before
    dense = system(row, None, 60, 3, 0, step_seconds=5)
    assert any(bound < -1 for bound in dense[1])


@pytest.mark.parametrize("point", ["5", "10"])
def test_no_new_or_old_missing_node_is_ignored(point):
    row = linear_row()
    row["samples"][point] = None
    q = quality(row, [], step_seconds=5)
    assert q["status"] == "reference_unavailable"
    assert q["missing_offsets_seconds"] == [point]
    del row["samples"][point]
    with pytest.raises(ValueError, match="probe plan changed"):
        quality(row, [], step_seconds=5)


def test_a_certificate_cannot_silently_switch_between_coarse_and_dense_grids():
    with pytest.raises(ValueError, match="reference grid changed"):
        replay_interval(
            linear_row(), {"window_seconds": 60, "odd_order": 3}, step_seconds=5
        )


@pytest.mark.parametrize(
    "change", ["method", "step", "window", "order", "line", "nodes"]
)
def test_dense_policy_changes_are_rejected(change):
    p = dense_plan()
    if change == "method":
        p["local_interval_method_id"] = "other"
    if change == "step":
        p["local_grid_step_seconds"] = 10
    if change == "window":
        p["local_windows_seconds"] = p["local_windows_seconds"][1:]
    if change == "order":
        p["local_orders"] = [5]
    if change == "line":
        p["fixed_reference_convergence_arcsec_per_day"] = 0.0021
    if change == "nodes":
        p["explicit_offsets_seconds"]["Venus"].remove(5)
    with pytest.raises(ValueError):
        audit.reference_grid(p)


def test_old_policy_remains_identical_and_dense_policy_is_explicit():
    assert audit.reference_grid(json.loads((OLD / "protocol.json").read_text())) == (
        audit.METHOD,
        10,
    )
    assert audit.reference_grid(dense_plan()) == (
        "local_printed_angle_interval_lp_grid5_v2",
        5,
    )


def test_parent_conflict_cannot_be_overridden_by_a_passing_dense_model(
    tmp_path, monkeypatch
):
    row = linear_row()
    parent = copy.deepcopy(row)
    parent["id"] = "old"
    parent["samples"] = {k: v for k, v in parent["samples"].items() if int(k) % 10 == 0}
    parent_file = tmp_path / "parent.json"
    parent_file.write_text(json.dumps({"rows": [parent]}))
    plan = dense_plan()
    plan["densification_parent"] = {
        "reference_sha256": hashlib.sha256(parent_file.read_bytes()).hexdigest(),
        "case_map": {"new": "old"},
    }
    row["samples"]["10"]["printed_angles"][0] = "1.000000000"
    raw = {"rows": [row]}
    p, r = tmp_path / "protocol.json", tmp_path / "reference.json"
    p.write_text(json.dumps(plan))
    r.write_text(json.dumps(raw))
    passed = {
        "status": "qualified_under_declared_numerical_model",
        "selected_window_seconds": 810,
        "selected_order": 5,
        "selected": {"radius": 0},
    }
    monkeypatch.setattr(
        audit, "validate", lambda *args: {"status": "raw_identity_checked"}
    )
    monkeypatch.setattr(audit, "quality", lambda *args, **kwargs: copy.deepcopy(passed))
    certificates = {
        "method_id": plan["local_interval_method_id"],
        "reference_sha256": hashlib.sha256(r.read_bytes()).hexdigest(),
        "rows": [{"id": "new", "fits": [], "quality": passed}],
    }
    bundle = dict(protocol=p, reference=parent_file, material=tmp_path, seal=p)
    result = audit.replay(p, r, tmp_path, p, certificates, parent_bundle=bundle)
    q = result["rows"][0]
    assert result["exit_code"] == 2 and q["status"] == "reference_quality_unresolved"
    assert q["dense_model_quality"] == passed and q["selected"] is None
    assert q["parent_preservation"]["parent_observations_checked"] == 289
    assert q["parent_preservation"]["matching_parent_observations"] == 288
    assert q["parent_preservation"]["conflicts"][0]["offset_seconds"] == "10"
    with pytest.raises(ValueError, match="parent identity"):
        audit.replay(p, r, tmp_path, p, certificates)


def test_parent_paths_are_all_or_none():
    with pytest.raises(ValueError, match="All four"):
        audit.parent_from_args(SimpleNamespace(parent_reference=Path("parent.json")))
