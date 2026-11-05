"""All original calendar rows survive unavailable data and false backends."""

import json
from pathlib import Path

import pytest

from scripts.human_design import check_human_design_calendar_span as audit

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cohort(monkeypatch):
    pairs = [
        {
            "label": str(i),
            **{
                side: {
                    "jd_tt": float(2 * i + offset),
                    "positions": {
                        body: {"longitude": 1.0} for body in ("Sun", "Uranus")
                    },
                }
                for side, offset in (("personality", 0), ("design", 1))
            },
        }
        for i in range(2)
    ]
    monkeypatch.setattr(
        audit, "reference", lambda root: ({"scope": "synthetic"}, {"pairs": pairs})
    )

    def positions(epoch, node_mode, backend):
        return {
            body: {
                "longitude": 1.0,
                "return_flags": 258 if backend == "swieph" else 260,
                "ephemeris_model": backend,
            }
            for body in ("Sun", "Uranus")
        }

    def root(epoch, backend):
        return {
            "solver": {"design_jd_tt": epoch + 1},
            "ephemeris_source_evidence": {
                "contexts": [
                    {
                        "body": "Sun",
                        "role": "solar_root",
                        "observed_evaluation_count": 3,
                        "native_return_flag_model": backend,
                    }
                ],
            },
        }

    monkeypatch.setattr(audit, "positions_at_tt", positions)
    monkeypatch.setattr(audit, "_root_result", root)
    return pairs, positions, root


def test_batch_and_root_exceptions_retain_all_rows_and_continue(cohort, monkeypatch):
    pairs, positions, root = cohort
    calls = []

    def sometimes_positions(epoch, mode, backend):
        calls.append((backend, epoch))
        if epoch == 1.0:
            raise RuntimeError("unavailable native batch")
        return positions(epoch, mode, backend)

    def sometimes_root(epoch, backend):
        if epoch == 0.0:
            raise OSError("unavailable root dependency")
        return root(epoch, backend)

    monkeypatch.setattr(audit, "positions_at_tt", sometimes_positions)
    monkeypatch.setattr(audit, "_root_result", sometimes_root)
    result = audit.checks()
    assert result["status"] == "failed"
    for name, report in result["backends"].items():
        assert report["position_count"] == 8
        assert report["positions_matched"] == 6
        assert report["position_not_assessed_count"] == 2
        assert report["position_failure_count"] == 2
        assert report["root_count"] == 2
        assert report["roots_matched"] == 1
        assert report["root_not_assessed_count"] == 1
        assert [r["label"] for r in report["root_rows"]] == ["0", "1"]
        assert [r["body"] for r in report["position_failures"]] == ["Sun", "Uranus"]
        for row in report["position_failures"]:
            assert row["evaluation_status"] == "not_assessed_calculation_error"
            assert row["error_arcseconds"] is None
            assert row["computed_longitude"] is None
            assert row["different_levels_using_current_mapping"] is None
            assert row["within_tolerance"] is row["accepted"] is False
        assert report["root_failures"][0]["error_seconds"] is None
    assert len(calls) == 8 and calls[-1] == ("moshier", 3.0)
    assert len(json.dumps(result, allow_nan=False)) > 0


@pytest.mark.parametrize(
    "change", ["missing_body", "nan", "inf", "negative", "string", "boolean"]
)
def test_one_malformed_position_does_not_delete_other_positions(
    cohort, monkeypatch, change
):
    _, positions, _ = cohort

    def malformed(epoch, mode, backend):
        result = positions(epoch, mode, backend)
        if epoch == 1.0:
            if change == "missing_body":
                result.pop("Uranus")
            else:
                result["Uranus"]["longitude"] = {
                    "nan": float("nan"),
                    "inf": float("inf"),
                    "negative": -1.0,
                    "string": "1.0",
                    "boolean": True,
                }[change]
        return result

    monkeypatch.setattr(audit, "positions_at_tt", malformed)
    result = audit.checks()
    for report in result["backends"].values():
        assert report["position_count"] == 8 and report["positions_matched"] == 7
        assert report["position_not_assessed_count"] == 1
        assert report["position_failures"][0]["body"] == "Uranus"
        assert report["position_failures"][0]["error_arcseconds"] is None
    assert result["status"] == "failed"
    json.dumps(result, allow_nan=False)


def test_all_unavailable_has_null_maxima_and_keeps_both_full_cohorts(
    cohort, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("all unavailable")

    monkeypatch.setattr(audit, "positions_at_tt", fail)
    monkeypatch.setattr(audit, "_root_result", fail)
    result = audit.checks()
    for report in result["backends"].values():
        assert report["position_count"] == report["position_not_assessed_count"] == 8
        assert report["root_count"] == report["root_not_assessed_count"] == 2
        assert report["positions_matched"] == report["roots_matched"] == 0
        assert report["maximum_position_error_arcseconds"] is None
        assert report["maximum_position_error_row"] is None
        assert report["maximum_root_error_seconds"] is None
        assert len(report["position_failures"]) == 8
        assert len(report["root_failures"]) == 2
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("change", ["fallback", "flags", "model", "missing_flags"])
def test_exact_numeric_match_cannot_hide_wrong_position_backend(
    cohort, monkeypatch, change
):
    _, positions, _ = cohort

    def altered(epoch, mode, backend):
        result = positions(epoch, mode, backend)
        if backend == "swieph":
            for value in result.values():
                if change == "fallback":
                    value.update(ephemeris_model="moshier", return_flags=260)
                elif change == "flags":
                    value["return_flags"] = 260
                elif change == "model":
                    value["ephemeris_model"] = "jpl"
                else:
                    value.pop("return_flags")
        return result

    monkeypatch.setattr(audit, "positions_at_tt", altered)
    result = audit.checks()
    selected = result["backends"]["selected"]
    assert (
        selected["positions_matched"] == 8 and selected["position_failure_count"] == 0
    )
    assert selected["position_accepted_count"] == 0
    assert selected["position_backend_unaccepted_count"] == 8
    assert selected["status"] == "failed"
    assert len(selected["position_backend_failures"]) == 8
    assert all(r["error_arcseconds"] == 0 for r in selected["position_rows"])
    assert result["status"] == "failed"


@pytest.mark.parametrize(
    "change", ["fallback", "missing", "wrong_body", "wrong_role", "zero_count"]
)
def test_exact_root_match_requires_actual_solar_backend_observations(
    cohort, monkeypatch, change
):
    _, _, root = cohort

    def altered(epoch, backend):
        result = root(epoch, backend)
        contexts = result["ephemeris_source_evidence"]["contexts"]
        if change == "missing":
            contexts.clear()
        else:
            contexts[0].update(
                {
                    "fallback": {"native_return_flag_model": "jpl"},
                    "wrong_body": {"body": "Uranus"},
                    "wrong_role": {"role": "activation"},
                    "zero_count": {"observed_evaluation_count": 0},
                }[change]
            )
        return result

    monkeypatch.setattr(audit, "_root_result", altered)
    report = audit.checks()["backends"]["selected"]
    assert report["roots_matched"] == 2 and not report["root_failures"]
    assert report["root_accepted_count"] == 0
    assert report["root_backend_unaccepted_count"] == 2
    assert report["status"] == "failed"
    assert len(report["root_backend_failures"]) == 2


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "2.0", True, 1e308])
def test_invalid_root_retains_later_cases_and_serializes_finitely(
    cohort, monkeypatch, value
):
    _, _, root = cohort

    def altered(epoch, backend):
        result = root(epoch, backend)
        if epoch == 0.0:
            result["solver"]["design_jd_tt"] = value
        return result

    monkeypatch.setattr(audit, "_root_result", altered)
    result = audit.checks()
    for report in result["backends"].values():
        assert report["root_count"] == 2 and report["root_not_assessed_count"] == 1
        assert report["roots_matched"] == 1
        assert report["root_failures"][0]["error_seconds"] is None
    json.dumps(result, allow_nan=False)


def test_finite_synthetic_success_is_still_not_full_calendar_acceptance(cohort):
    result = audit.checks()
    assert result["status"] == "additional_bounded_match"
    assert result["complete_calendar_acceptance"] is False
    assert result["subdivision_critical_accuracy_certified"] is False
    assert result["authority_certified"] is False


def test_empty_real_observer_does_not_infer_solar_backend(monkeypatch):
    # A solver replacement returning only its numerical result makes no
    # observed native call. The actual guard must report that absence.
    monkeypatch.setattr(
        audit,
        "solve_design_epoch_tt",
        lambda epoch, backend: {"solver": {"design_jd_tt": epoch + 1}},
    )
    pair = {"label": "0", "personality": {"jd_tt": 0.0}, "design": {"jd_tt": 1.0}}
    row = audit._root_row(pair, "swieph")
    assert row["within_tolerance"] is True
    assert row["source_evidence"]["contexts"] == []
    assert row["backend_status"] == "not_assessed_missing_solar_observations"
    assert row["backend_accepted"] is row["accepted"] is False
