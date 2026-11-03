"""Point-intent repair must retain old gates and refuse impossible UTC labels."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac, analytic_solar, spk_solar
from fatebridge.core.astro.time_scales import datetime_from_tt

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-scalar-solar-point-repair-v1"


def sealed(path):
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    raw = (
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )
    return json.loads(raw)


def test_all_original_point_inputs_unknowns_and_failed_legacy_gate_survive():
    current = sealed(STUDY / "consumer-candidate-first.json.gz")
    old = sealed(
        ROOT / "docs/validation/bazi-scalar-solar-consumer-v1/baseline-first.json.gz"
    )
    oracle = sealed(ROOT / "tests/fixtures/bazi_tt_utc_exact_v1/oracle.json.gz")
    for result in (old, current):
        assert result["row_count"] == len(result["rows"]) == 6391
        assert [
            {k: actual[k] for k in expected}
            for actual, expected in zip(result["rows"], oracle["rows"], strict=True)
        ] == oracle["rows"]
        assert result["counts"]["unknown_retained"] == 2218
        assert result["old_legacy_gate_superseded"] is False
    assert len(old["failed_ids"]) == 41
    assert old["consumer_failure_ids_equal_legacy_conflicts"]
    assert not old["consumer_point_semantics_gate_passed"]
    assert current["counts"]["normal_matches"] == 3930
    assert current["counts"]["unrepresentable_rejected"] == 243
    assert not current["failed_ids"]
    assert not current["unknown_outcome_differences_vs_saved_point"]
    assert current["consumer_point_semantics_gate_passed"]


def test_old_global_scalar_entry_still_reproduces_all41_original_conflicts():
    ledger = sealed(ROOT / "docs/validation/bazi-tt-scalar-conflicts-retained-v1.json")
    assert len(ledger["rows"]) == 41
    for row in ledger["rows"]:
        try:
            value = datetime_from_tt(row["jd_tt"])
        except Exception as error:
            assert type(error).__name__ == row["error_type"]
        else:
            assert value.isoformat() == row["actual_datetime_utc"]


@pytest.mark.parametrize("spk", [False, True])
def test_entire_known_oracle_through_each_scalar_model_caller(spk, monkeypatch):
    oracle = sealed(ROOT / "tests/fixtures/bazi_tt_utc_exact_v1/oracle.json.gz")
    provider = spk_solar if spk else analytic_solar
    seen = 0
    for row in oracle["rows"]:
        if row["status"] == "pre_atomic_policy_unadjudicated":
            continue
        jd = row["jd_tt"]

        def solver(*args, **kwargs):
            return {
                "jd_tt": jd,
                "bracket_tt": [jd, jd],
                "bracket_seconds": 0,
                "model": {"model_id": "synthetic_point_control"},
            }

        monkeypatch.setattr(provider, "longitude_crossing_tt", solver)
        if row["status"] == "normal":
            civil, receipt = almanac._solar_term_utc_via_analytic(2000, 0, {}, spk=spk)
            assert civil.isoformat() == row["expected_datetime_utc"], row["id"]
            details = receipt["solar_model_details"]
            assert details["selected_crossing_jd_tt"] == jd
            assert (
                details["numerical_epoch_representation"]
                == "explicit_ieee_float_tt_point"
            )
        else:
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                almanac._solar_term_utc_via_analytic(2000, 0, {}, spk=spk)
        seen += 1
    assert seen == 4173


def test_explicit_root_conversion_error_cannot_publish_a_linear_year(
    monkeypatch, tmp_path
):
    oracle = sealed(ROOT / "tests/fixtures/bazi_tt_utc_exact_v1/oracle.json.gz")
    bad = next(r for r in oracle["rows"] if r["status"] == "unrepresentable_utc_label")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))

    def native(year, target, anchor, provenance):
        provenance.update(ephemeris_model="moshier")
        return anchor

    def root(*args, **kwargs):
        return {
            "jd_tt": bad["jd_tt"],
            "bracket_tt": [bad["jd_tt"]] * 2,
            "bracket_seconds": 0,
            "model": {"model_id": "synthetic_unrepresentable"},
        }

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", native)
    monkeypatch.setattr(analytic_solar, "longitude_crossing_tt", root)
    with pytest.raises(ValueError, match="UTC leap second not representable"):
        almanac._calculate_solar_terms_for_year(2000, "UTC")


def test_real_grid_roots_and_default_delivery_are_preserved_with_declared_clock_deltas():
    result = sealed(STUDY / "actual-grid-assessment-first.json")
    assert result["counts"]["delivered_TT_points"] == 432
    assert result["counts"]["before_point_mismatches"] == 96
    assert result["counts"]["after_point_mismatches"] == 0
    assert result["counts"]["full_unchanged_auto"] == 144
    assert result["counts"]["full_unchanged_native"] == 144
    assert (
        result["counts"]["native_rows_without_delivered_TT_reference_retained"] == 144
    )
    assert not result["unexpected_delta_ids"]
    assert not result["physical_clock_accuracy_certified"]
