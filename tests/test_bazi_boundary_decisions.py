"""Reference coverage and retained verifier failures cannot become fake gains."""

import ast
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_boundary_decisions_v1"


def sealed(path):
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


def test_all_reference_roots_and_minute_pairs_are_retained_without_selection():
    protocol = sealed(FIXTURE / "protocol.json")
    probes = sealed(FIXTURE / "probes.json")
    reference = sealed(ROOT / protocol["reference_path"])
    assert len(reference["rows"]) == probes["root_count"] == 4872
    assert len(probes["rows"]) == probes["probe_count"] == 9744
    for root, first, second in zip(
        reference["rows"], probes["rows"][::2], probes["rows"][1::2], strict=True
    ):
        assert first["year"] == second["year"] == root["year"]
        assert first["name"] == second["name"] == root["name"]
        assert (
            first["reference_root_tt"] == second["reference_root_tt"] == root["jd_tt"]
        )
        a, b = datetime.fromisoformat(first["civil_utc"]), datetime.fromisoformat(
            second["civil_utc"]
        )
        assert a.second == b.second == a.microsecond == b.microsecond == 0
        assert b - a == timedelta(minutes=1)
    for name, digest in protocol["source_fingerprints"].items():
        assert (
            hashlib.sha256((FIXTURE / "before" / name).read_bytes()).hexdigest()
            == digest
        )


def test_verifier_repair_changes_only_the_two_misidentified_12jie_fields():
    first = sealed(ROOT / "docs/validation/bazi-boundary-decisions-first-v1.json.gz")
    corrected = sealed(
        ROOT / "docs/validation/bazi-boundary-windows-adjudicated-first-v1.json.gz"
    )
    assert (
        hashlib.sha256((FIXTURE / "audit-first.py.txt").read_bytes()).hexdigest()
        == first["runner_sha256"]
        == corrected["first_runner_sha256"]
    )
    for old, new in zip(first["arms"], corrected["arms"], strict=True):
        assert old["arm"] == new["arm"]
        assert (
            old["original_one_second_root_gate_failures"]
            == new["original_one_second_root_gate_failures"]
        )
        assert (
            old["maximum_root_difference_seconds"]
            == new["maximum_root_difference_seconds"]
        )
        assert len(new["comparisons"]) == len(old["comparisons"]) == 9744
        for a, b in zip(old["comparisons"], new["comparisons"], strict=True):
            assert a["probe_id"] == b["probe_id"]
            assert a["matches"] == b["original_matches"]
            for key in a["matches"]:
                if key not in {"liuri_last_term", "liuri_next_term"}:
                    assert a["matches"][key] == b["matches"][key]
    assert not corrected["production_values_recomputed_or_changed"]
    assert not corrected["reference_or_old_gate_changed"]
    assert not corrected["full_calendar_acceptance"]


def test_native_failures_and_four_new_default_month_errors_stay_visible():
    result = sealed(
        ROOT / "docs/validation/bazi-boundary-windows-adjudicated-first-v1.json.gz"
    )
    swiss, native, analytic = result["arms"]
    assert swiss["counts"]["last_term"]["mismatched"] == 1
    assert native["original_one_second_root_gate_failures"] == 501
    assert native["counts"]["bazi_year"]["mismatched"] == 2
    assert native["counts"]["month_branch"]["mismatched"] == 18
    assert analytic["original_one_second_root_gate_failures"] == 0
    assert analytic["counts"]["month_branch"]["mismatched"] == 4
    assert len(analytic["mismatched_probe_ids"]) == 5


def test_spk_development_and_generic_sources_are_frozen_without_independence_credit():
    development = sealed(
        ROOT / "docs/validation/bazi-spk-sun-development-first-v1.json.gz"
    )
    generic = sealed(ROOT / "docs/validation/bazi-spk-sun-generic-first-v1.json")
    epochs = sealed(FIXTURE / "generic-epochs.json")
    refs = sealed(FIXTURE / "generic-reference.json")
    assert development["root_count"] == 4872 and development["probe_count"] == 9744
    assert (
        development["original_one_second_gate_failures"]
        == development["minute_probe_failures"]
        == 0
    )
    assert not development["adopted"]
    assert len(generic["rows"]) == len(refs["rows"]) == len(epochs["rows"]) == 512
    assert [r["jd_tt"] for r in generic["rows"]] == [r["jd_tt"] for r in epochs["rows"]]
    assert generic["gate_failures"] == generic["new_independent_observations"] == 0
    assert not generic["adopted"]


def test_actual_integrated_spk_consumes_all_original_probes_and_reports_its_own_source():
    result = sealed(
        ROOT / "docs/validation/bazi-spk-public-boundaries-accepted-v1.json.gz"
    )
    assert result["root_count"] == len(result["root_comparisons"]) == 4872
    assert result["probe_count"] == len(result["comparisons"]) == 9744
    assert result["original_one_second_gate_failures"] == 0
    assert result["wrong_probe_ids"] == []
    for term in result["root_comparisons"]:
        actual = term["actual_term"]
        assert actual["resolution_provider"] == "jpl_spk"
        assert actual["ephemeris_model"] == "fatebridge_jpl_spk_solar_v1"
        assert (
            actual["solar_model_details"]["kernel_sha256"]
            == "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
        )
        assert actual["solar_model_details"]["accuracy_certified"] is False
    assert not result["full_calendar_acceptance"]
    assert result["overall_score"] is None


def test_later_source_identity_guards_preserve_the_audited_physics_and_root_math():
    path = Path("src/fatebridge/core/spk_solar.py")
    before = ast.parse((FIXTURE / "before-aba-guard" / path).read_text())
    after = ast.parse((ROOT / path).read_text())

    def method(tree, name):
        cls = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "_KernelSun"
        )
        return next(
            n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name
        )

    for name in ["longitude", "segment"]:
        assert ast.dump(method(before, name)) == ast.dump(method(after, name))

    def numerical_tail(tree):
        fn = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "longitude_crossing_tt"
        )
        lock = next(n for n in fn.body if isinstance(n, ast.With))
        start = next(
            i
            for i, n in enumerate(lock.body)
            if isinstance(n, ast.FunctionDef) and n.name == "residual"
        )
        return [ast.dump(n) for n in lock.body[start:]]

    assert numerical_tail(before) == numerical_tail(after)
