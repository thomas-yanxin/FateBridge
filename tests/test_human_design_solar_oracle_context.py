"""Missing native reference observations cannot become implicit exact passes."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.check_human_design_solar_speed_lattice import compare, compare_case

ROOT = Path(__file__).resolve().parents[1]


def example():
    c = {
        "label": "synthetic-unit-control",
        "backend": "moshier",
        "birth_jd_tt": 100.0,
        "birth_sun_longitude": 100.0,
        "lower_jd_tt": 10.0,
        "upper_jd_tt": 10.0001,
        "selected_jd_tt": 10.0,
        "selected_sun_longitude": 12.0,
        "exact_residual": ["0", "1"],
    }
    s = {
        "design_jd_tt": 10.0,
        "numerical_precision": {
            "birth_sun_longitude": 100.0,
            "selected": {"sun_longitude": 12.0, "residual_degrees": 0.0},
            "local_solar_lattice": {
                "samples": [
                    {"jd_tt": 10.0, "sun_longitude": 12.0},
                    {"jd_tt": 10.0001, "sun_longitude": 12.0001},
                ],
                "observed_decreasing_step_indices": [],
                "observed_sign_brackets": [],
            },
        },
    }
    return c, s


def test_first_real_missing_reference_keeps_failure_without_native_recalculation():
    from fatebridge.core.human_design_time import solve_design_epoch_tt

    c = json.loads(
        (ROOT / "tests/data/human_design/solar-missing-endpoint-case.json").read_text()
    )
    solver = solve_design_epoch_tt(c["birth_jd_tt"], backend=c["backend"])["solver"]
    result = compare_case(c, solver)
    assert result["status"] == "compared"
    assert result["strict_root_equal"] is False
    assert result["local_checks"]["birth_sun_exact"] is False
    assert result["missing_reference_jd_tt"] == [c["lower_jd_tt"], c["upper_jd_tt"]]
    assert "reference_exact_residual_preserved" in result["not_assessed_local_checks"]
    assert result["local_checks"]["reference_exact_residual_preserved"] is False
    assert (
        result["local_checks"]["current_exact_residual_matches_its_own_chart"] is True
    )


@pytest.mark.parametrize("missing", [10.0, 10.0001])
def test_missing_reference_observation_is_never_inferred_from_a_matching_selected_value(
    missing,
):
    c, s = example()
    s["numerical_precision"]["local_solar_lattice"]["samples"] = [
        r
        for r in s["numerical_precision"]["local_solar_lattice"]["samples"]
        if r["jd_tt"] != missing
    ]
    r = compare_case(c, s)
    assert r["strict_root_equal"] is True
    assert r["missing_reference_jd_tt"] == [missing]
    assert not all(r["local_checks"].values())
    assert r["not_assessed_local_checks"]
    aggregate = compare({"cases": [c]}, solve=lambda *a, **k: {"solver": s})
    assert aggregate["strict_selected_root_conformance"]["passed"] == 1
    assert aggregate["bounded_numeric_conformance_passed"] is False


def test_complete_matching_control_retains_every_old_local_check():
    c, s = example()
    r = compare_case(c, s)
    assert r["strict_root_equal"] is True
    assert all(r["local_checks"].values())
    assert r["not_assessed_local_checks"] == r["missing_reference_jd_tt"] == []
    report = compare({"cases": [c]}, solve=lambda *a, **k: {"solver": s})
    assert report["supplied_numeric_checks_passed"] is True
    assert report["bounded_numeric_conformance_passed"] is False
    assert report["reference_binding"]["frozen_content_bound"] is False


def test_report_retains_a_failed_calculation_then_continues_every_required_row():
    c, s = example()
    broken = {**c, "label": "unavailable-control", "birth_jd_tt": 99.0}
    reference = {"cases": [broken, c]}
    before = deepcopy(reference)

    def solve(tt, **kwargs):
        if tt == 99:
            raise RuntimeError("observed calculation failure")
        return {"solver": s}

    r = compare(reference, solve=solve)
    assert reference == before
    assert [row["label"] for row in r["cases"]] == [broken["label"], c["label"]]
    assert r["strict_selected_root_conformance"] == {
        "status": "failed",
        "total": 2,
        "passed": 1,
        "failed": 1,
    }
    assert r["unavailable_case_count"] == 1
    assert r["cases"][0]["error"] == {
        "type": "RuntimeError",
        "message": "observed calculation failure",
    }
    assert r["bounded_numeric_conformance_passed"] is False


def test_wrong_current_residual_cannot_hide_behind_equal_frozen_root():
    c, s = example()
    s["numerical_precision"]["selected"]["residual_degrees"] = 1.0
    r = compare({"cases": [c]}, solve=lambda *a, **k: {"solver": s})
    assert r["strict_selected_root_conformance"]["passed"] == 1
    assert r["actual_local_witness_checks_passed"] == 0
    assert not r["bounded_numeric_conformance_passed"]


def test_a_matching_fake_producer_and_deleted_real_failure_cannot_certify_a_subset():
    import sys
    from fractions import Fraction

    filename = (
        "human-design-solar-speed-lattice-linux.json"
        if sys.platform == "linux"
        else "human-design-solar-speed-lattice.json"
    )
    original = json.loads((ROOT / "tests/fixtures" / filename).read_text())
    subset = deepcopy(original)
    # Deliberate adversarial simulation, never a new physical reference:
    # remove a required row and make every remaining result echo its oracle.
    del subset["cases"][0]
    lookup = {(c["birth_jd_tt"], c["backend"]): c for c in subset["cases"]}

    def fake(tt, *, backend):
        c = lookup[(tt, backend)]
        selected = c["selected_jd_tt"]
        residual = (
            Fraction(c["birth_sun_longitude"]) - Fraction(c["selected_sun_longitude"])
        ) % 360 - 88
        samples = [
            {
                "jd_tt": t,
                "sun_longitude": (
                    c["selected_sun_longitude"]
                    if t == selected
                    else (c["selected_sun_longitude"] + 1) % 360
                ),
            }
            for t in sorted({c["lower_jd_tt"], c["upper_jd_tt"]})
        ]
        return {
            "solver": {
                "design_jd_tt": selected,
                "numerical_precision": {
                    "birth_sun_longitude": c["birth_sun_longitude"],
                    "selected": {
                        "sun_longitude": c["selected_sun_longitude"],
                        "residual_degrees": float(residual),
                    },
                    "local_solar_lattice": {
                        "samples": samples,
                        "observed_decreasing_step_indices": [],
                        "observed_sign_brackets": [],
                    },
                },
            }
        }

    report = compare(subset, solve=fake)
    assert len(report["cases"]) == 243
    assert report["strict_selected_root_conformance"]["passed"] == 243
    assert report["supplied_numeric_checks_passed"] is True
    assert report["reference_binding"]["frozen_content_bound"] is False
    assert report["bounded_numeric_conformance_passed"] is False


def test_content_binding_rejects_reordering_even_with_all244_rows():
    import sys

    filename = (
        "human-design-solar-speed-lattice-linux.json"
        if sys.platform == "linux"
        else "human-design-solar-speed-lattice.json"
    )
    original = json.loads((ROOT / "tests/fixtures" / filename).read_text())
    changed = deepcopy(original)
    changed["cases"].reverse()

    def unavailable(*a, **k):
        raise RuntimeError("No native calls in the identity check")

    original_report = compare(original, solve=unavailable)
    changed_report = compare(changed, solve=unavailable)
    assert original_report["reference_binding"]["frozen_content_bound"] is True
    assert changed_report["reference_binding"]["frozen_content_bound"] is False
    assert len(changed_report["cases"]) == 244
    assert changed_report["unavailable_case_count"] == 244


def test_strict_cli_rejects_numerically_matching_but_unbound_reference(
    tmp_path, monkeypatch
):
    import sys

    from scripts import check_human_design_solar_speed_lattice as checker

    c, s = example()
    report = compare({"cases": [c]}, solve=lambda *a, **k: {"solver": s})
    assert report["supplied_numeric_checks_passed"] is True
    target = tmp_path / "unbound.json"
    monkeypatch.setattr(checker, "compare", lambda: report)
    monkeypatch.setattr(
        sys, "argv", ["checker", "--output", str(target), "--require-exact"]
    )
    with pytest.raises(SystemExit) as stopped:
        checker.main()
    assert stopped.value.code == 1
    saved = json.loads(target.read_text())
    assert saved["strict_selected_root_conformance"]["status"] == "passed"
    assert saved["reference_binding"]["frozen_content_bound"] is False
