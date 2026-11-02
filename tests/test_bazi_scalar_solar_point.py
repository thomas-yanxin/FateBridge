"""Point-intent repair must retain old gates and refuse impossible UTC labels."""

import ast
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import almanac, analytic_solar, spk_solar
from fatebridge.core.astro.time_scales import datetime_from_tt
from scripts.historical_source_identity import HistoricalSources

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


def test_all_untouched_functions_and_legacy_time_conversion_bytes_stay_exact():
    plan = sealed(STUDY / "protocol.json")
    for relative in (
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/tt_epoch.py",
    ):
        assert (
            hashlib.sha256((STUDY / "before" / relative).read_bytes()).hexdigest()
            == plan["before_sources"][relative]
        )
    old = ast.parse((STUDY / "before/src/fatebridge/core/almanac.py").read_text())
    new = ast.parse((ROOT / "src/fatebridge/core/almanac.py").read_text())

    def definitions(tree):
        return {
            n.name: ast.dump(n, include_attributes=False)
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            and n.name
            not in {"_solar_term_utc_via_analytic", "_solar_term_utc_via_swe"}
        }

    # The next sealed stage contains the scalar-point change before the
    # separately qualified native-point migration. Preserve this historical
    # unchanged-function proof; current native solver math is checked below.
    after_scalar_path = (
        ROOT
        / "docs/validation/bazi-native-solar-point-v1/before/src/fatebridge/core/almanac.py"
    )
    assert (
        hashlib.sha256(after_scalar_path.read_bytes()).hexdigest()
        == "55a66bcb6dd92d449799db154ce8d1e4192b2991ec504db036d016a7d218f8bd"
    )
    assert definitions(old) == definitions(ast.parse(after_scalar_path.read_text()))
    # The native point migration replaces this former unchanged-function
    # assertion with an exact solver-math guard, retaining the old source.
    native_study = ROOT / "docs/validation/bazi-native-solar-point-v1"
    native_before = ast.parse(
        (native_study / "before/src/fatebridge/core/almanac.py").read_text()
    )

    def native(tree):
        return next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_solar_term_utc_via_swe"
        )

    assert ast.dump(native(old), include_attributes=False) == ast.dump(
        native(native_before), include_attributes=False
    )

    originals = HistoricalSources(ROOT).originals
    # Physical-source guards were added after the earlier point audit.
    # Check both retained originals directly, without the retired process-wide
    # manifest. Their complete solver AST, guards and math must stay exact.
    for digest in (
        "48a5a2be827bc7cc99a67b25ece1cadbc1cc08b3afdf7ca15c500ffcaada77ee",
        "8b381e09b403b45c41c6cb7c4f33c27830cb0a238d21bf8f018c8bc3e8d182ca",
    ):
        original = originals[digest]
        assert "src/fatebridge/core/almanac.py" in original["paths"]
        assert hashlib.sha256(original["text"].encode()).hexdigest() == digest
        before_repair = ast.parse(original["text"])
        assert ast.dump(native(before_repair), include_attributes=False) == ast.dump(
            native(new), include_attributes=False
        )
