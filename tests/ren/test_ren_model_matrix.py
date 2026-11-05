"""Named-model comparison never rewrites old gates or drops difficult cases."""

import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ren_model_matrix", ROOT / "scripts/ren/audit_ren_model_matrix.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
ANALYTIC = {
    "provider": "fatebridge_analytic",
    "model": "fatebridge_analytic_solar_v1",
    "retflags": [],
}
EPOCH = datetime(2026, 3, 20, tzinfo=timezone.utc)
CASE = {
    "id": "source-label",
    "year": 2026,
    "term": "春分",
    "timescale": "UTC",
    "published_label": EPOCH.isoformat(),
}


def actual(delta=0.0):
    return {
        (2026, "春分"): {
            "actual": (EPOCH + timedelta(seconds=delta)).isoformat(),
            "provider": ANALYTIC["provider"],
            "ephemeris_model": ANALYTIC["model"],
            "ephemeris_retflags": [],
        }
    }


def compare(rows, convert=None):
    return AUDIT.compare_route(
        [deepcopy(CASE)],
        rows,
        "seasons",
        convert
        or (
            lambda _: SimpleNamespace(jd_tt=2451545.0, jd_ut1=2451545.0, method="test")
        ),
        lambda _: 2451545.0,
        datetime.fromisoformat,
        ANALYTIC,
    )


def test_named_model_numeric_result_does_not_repair_original_swiss_only_gate():
    rows = actual()
    before = deepcopy(rows)
    named = compare(rows)
    legacy = AUDIT.module("ren_matrix_test_old", "audit_ren_opale_seasons.py")
    old = legacy.comparison(
        [CASE], rows, "seasons", lambda _: SimpleNamespace(jd_tt=0, jd_ut1=0)
    )
    assert rows == before
    assert named["all_declared_numeric_and_identity_checks_passed"] is True
    assert old["compared_count"] == 0
    assert len(old["calculation_errors"]) == 1
    assert named["comparisons"][0]["actual_provider"] == "fatebridge_analytic"


@pytest.mark.parametrize(
    ("seconds", "fails"), [(1.0, 0), (-1.0, 0), (1.000001, 1), (-1.000001, 1)]
)
def test_original_one_second_gate_is_not_rounded_or_relaxed(seconds, fails):
    result = compare(actual(seconds))
    assert result["numeric_failure_count"] == fails
    assert result["expected_count"] == result["compared_count"] == 1


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf")])
def test_bad_clock_is_retained_as_error_not_a_numeric_pass(value):
    result = compare(actual(), lambda _: SimpleNamespace(jd_tt=value, jd_ut1=0))
    assert result["expected_count"] == 1
    assert result["compared_count"] == 0
    assert len(result["calculation_errors"]) == 1
    assert result["all_declared_numeric_and_identity_checks_passed"] is False


def test_unknown_model_cannot_pass_by_having_good_numeric_residual():
    rows = actual()
    rows[(2026, "春分")]["ephemeris_model"] = "unknown"
    result = compare(rows)
    assert result["numeric_failure_count"] == 0
    assert result["model_identity_failure_count"] == 1
    assert result["all_declared_numeric_and_identity_checks_passed"] is False


def test_missing_event_is_not_removed_from_denominator():
    result = compare({})
    assert result["expected_count"] == 1
    assert result["compared_count"] == 0
    assert len(result["calculation_errors"]) == 1


def test_original_source_protocol_and_all_profiles_are_frozen():
    value = AUDIT.protocol()
    assert len(value["profiles"]) == 3
    assert value["cohorts"]["pmo_minutes"]["count"] == 3024
    assert value["cohorts"]["pmo_ren_boundary_pairs"]["count"] == 4536
    assert value["cohorts"]["hko_lunar_table_replay"]["civil_dates"] == 73049


def test_changed_protocol_cannot_be_accepted_by_rewrapping_its_freeze(tmp_path):
    value = json.loads((AUDIT.CORPUS / "protocol.json").read_text())
    value["cohorts"]["pmo_minutes"]["max_absolute_difference_seconds"] = 31
    (tmp_path / "protocol.json").write_text(json.dumps(value))
    (tmp_path / "freeze.json").write_text(
        json.dumps({"protocol_sha256": AUDIT.sha(tmp_path / "protocol.json")})
    )
    with pytest.raises(ValueError, match="protocol changed"):
        AUDIT.protocol(tmp_path)
