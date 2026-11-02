"""Full exposed root cohort and causal evidence cannot become an easier gate."""

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-solar-model-layers-v1"


def sealed(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(path.read_bytes()))


def test_full_factorial_and_raw_context_replay_preserve_all_original_roots():
    first = sealed("full-factorial-first.json.gz")
    closed = sealed("full-factorial-context-closed.json.gz")
    dependency_closed = sealed("full-factorial-dependency-closed.json.gz")
    assert dependency_closed["rows"] == closed["rows"]
    assert dependency_closed["dependency_files_unchanged"] == 1055
    source = json.loads(
        gzip.decompress(
            (
                ROOT
                / "docs/validation/bazi-root-clock-factorization-v1/independent-roots-first.json.gz"
            ).read_bytes()
        )
    )
    assert (
        first["row_count"]
        == closed["row_count"]
        == closed["default_reconstruction_exact"]
        == 4872
    )
    assert closed["variants_per_row"] == 16
    assert [(r["year"], r["name"], r["tt_parts"]) for r in closed["rows"]] == [
        (r["year"], r["name"], r["tt_parts"]) for r in source["rows"]
    ]
    for a, b in zip(first["rows"], closed["rows"]):
        assert a == {k: v for k, v in b.items() if k != "trace_contexts"}
        assert len(b["trace_contexts"]) == 2
        assert len(b["variants_degrees"]) == 16
        assert b["variants_degrees"]["0000"] == b["direct_production_longitude"]
    assert not closed["original_gates_superseded"]
    assert not closed["physical_accuracy_certified"]
    assert closed["new_independent_blind_credit"] == 0
    assert closed["new_model_executions"] == 0


def test_all_native_erfa_checks_keep_every_case_and_fixed_tolerances():
    data = sealed("native-erfa-comparison-guarded.json.gz")
    assert data["guarded_dependency_files"] == 943
    assert data["rows"] == sealed("native-erfa-comparison-second.json.gz")["rows"]
    rows = sealed("full-factorial-context-closed.json.gz")["rows"]
    assert [(r["year"], r["name"]) for r in data["rows"]] == [
        (r["year"], r["name"]) for r in rows
    ]
    assert data["row_count"] == 4872
    assert data["ab_failures"] == data["dtdb_failures"] == 0
    assert not data["original_gates_superseded"]
    assert not data["physical_accuracy_certified"]
    protocol = json.loads((STUDY / "erfa-comparison-protocol.json").read_text())
    assert protocol["vector_component_tolerance"] == 1e-15
    assert protocol["geocentric_dtdb_seconds_tolerance"] == 1e-12
