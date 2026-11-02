"""Frozen raw-data/consumer evidence cannot be reduced to a selected subset."""

import ast
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

from fatebridge.core import solar_model_policy

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_de440_default_v1"


def sealed(path):
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def test_orbit_extraction_and_reference_inputs_remain_the_predeclared_sources():
    protocol = sealed(FIXTURE / "protocol.json")
    for name, expected in protocol["frozen_references"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    for name, expected in protocol["before_sha256"].items():
        assert (
            hashlib.sha256((FIXTURE / "before" / name).read_bytes()).hexdigest()
            == expected
        )
    epochs = sealed(FIXTURE / "generic-epochs.json")
    assert len(epochs["rows"]) == 1024
    manifest = json.loads(
        (ROOT / "src/fatebridge/data/astronomy/de440-solar-v1.json").read_text()
    )
    raw = gzip.decompress(
        (ROOT / "src/fatebridge/data/astronomy/de440-solar-v1.bin.gz").read_bytes()
    )
    assert len(raw) == manifest["uncompressed_bytes"] == 17751664
    assert hashlib.sha256(raw).hexdigest() == manifest["uncompressed_sha256"]
    assert sum(s["record_count"] for s in manifest["segments"]) == 55474
    assert manifest["coefficients_resampled_rounded_fitted_or_degree_reduced"] is False
    assert manifest["reference_event_table_used"] is False
    assert manifest["derived_product_producer"]["institution"] == "FateBridge project"


def test_failed_first_source_guard_is_retained_and_full_retry_uses_the_whole_cohort():
    first = sealed(ROOT / "docs/validation/bazi-de440-component-first-v1.json.gz")
    assert first["accepted_unchanged_source"] is False
    assert set(first["source_drift"]) == {"src/fatebridge/utils/errors.py"}
    assert (
        hashlib.sha256(
            (FIXTURE / "audit-component-first.py.txt").read_bytes()
        ).hexdigest()
        == first["runner_sha256"]
    )
    accepted = sealed(ROOT / "docs/validation/bazi-de440-component-accepted-v1.json.gz")
    assert accepted["accepted_unchanged_source"] and not accepted["source_drift"]
    for key, count in [
        ("geometry", 166422),
        ("geocentric_tdb", 1024),
        ("generic_existing512", 512),
        ("full9624_roots", 9624),
        ("original4872_roots", 4872),
    ]:
        assert len(first[key]) == len(accepted[key]) == count
    assert accepted["all_original_record_bytes_equal"]
    for key in [
        "geometry_failures",
        "geocentric_tdb_failures",
        "generic_failures",
        "full9624_failures",
        "original4872_failures",
    ]:
        assert accepted[key] == 0
    assert (
        accepted["adopted"] is False
    )  # The historical component report is not a release.
    assert not accepted["full_goal_complete"] and accepted["overall_score"] is None


def test_actual_default_consumers_keep_all_original_probes_and_unknown_endpoints():
    probes = sealed(ROOT / "tests/fixtures/bazi_boundary_decisions_v1/probes.json")
    for environment in ["empty", "swiss"]:
        result = sealed(
            ROOT / f"docs/validation/bazi-de440-public-{environment}-first-v1.json.gz"
        )
        assert result["root_count"] == 9624
        assert result["original4872_root_count"] == 4872
        assert (
            result["original4872_root_failures"]
            == result["original_one_second_gate_failures"]
            == 0
        )
        assert result["probe_count"] == len(result["comparisons"]) == 9744
        assert [r["probe_id"] for r in result["comparisons"]] == [
            r["id"] for r in probes["rows"]
        ]
        assert not result["wrong_probe_ids"]
        for counts in result["counts"].values():
            assert (
                counts["matched"] + counts["mismatched"] + counts["unknown_endpoint"]
                == 9744
            )
            assert counts["mismatched"] == 0
        assert result["counts"]["bazi_year"]["unknown_endpoint"] == 5
        assert result["counts"]["liuri_next_term"]["unknown_endpoint"] == 3
        for row in result["root_comparisons"]:
            assert row["actual_term"]["resolution_provider"] == "jpl_de440"
            assert row["actual_term"]["ephemeris_model"] == "fatebridge_de440_solar_v1"
        assert (
            not result["full_calendar_acceptance"] and result["overall_score"] is None
        )


def test_original_audited_mathematics_and_default_policy_remain_replayable(monkeypatch):
    manifest = sealed(FIXTURE / "audited-vs-final-numerical-dependencies.json")
    before = FIXTURE / "audited-source-before-late-metadata"
    for name in [
        "src/fatebridge/core/analytic_solar.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/historical_utc.py",
        "src/fatebridge/core/ephemeris_runtime.py",
        "src/fatebridge/core/calendar.py",
        "src/fatebridge/core/timing.py",
        "src/fatebridge/core/almanac.py",
        "src/fatebridge/data/astronomy/de440-solar-v1.json",
        "src/fatebridge/data/astronomy/de440-solar-v1.bin.gz",
        "src/fatebridge/data/astronomy/geocentric-tdb-v1.json",
        "src/fatebridge/data/astronomy/analytic-solar-v1.json",
    ]:
        source = before if name.endswith(".py") else ROOT
        assert (
            hashlib.sha256((source / name).read_bytes()).hexdigest()
            == manifest[name]["audited_sha256"]
        )
    path = Path("src/fatebridge/core/de440_solar.py")
    metadata_edition = ROOT / "docs/validation/liuyao-v29/adoption-capture" / path
    assert (
        hashlib.sha256(metadata_edition.read_bytes()).hexdigest()
        == manifest[str(path)]["current_sha256"]
    )
    old, current = ast.parse((before / path).read_text()), ast.parse(
        metadata_edition.read_text()
    )
    definitions = lambda tree: {
        n.name: ast.dump(n)
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }
    assert definitions(old) == definitions(current)
    # After the audited run, only unused-source/strict-JPL policy handling and
    # metadata wording changed. The actual no-JPL default key remains equal.
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    spec = importlib.util.spec_from_file_location(
        "fatebridge.core._audited_de440_policy",
        before / "src/fatebridge/core/solar_model_policy.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.solar_model_cache_key() == solar_model_policy.solar_model_cache_key()
