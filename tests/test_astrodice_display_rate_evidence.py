"""Frozen holdout integrity; scientific failure and provenance stay separate."""

import json
from pathlib import Path

import pytest

from scripts import audit_astrodice_display_rate as grading
from scripts.astrodice_display_frame import load, sha
from scripts.historical_source_identity import HistoricalSources
from scripts.verify_astrodice_display_reference import verify

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-display-rate-run-2026-10-28"


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_first_references_remain_independently_reproducible(split):
    result = verify(RUN, RUN / f"{split}-reference-first.json")
    assert result == json.loads((RUN / f"{split}-independent-first.json").read_text())
    assert all(r["status"] == "strict_containment_passed" for r in result["rows"])


def test_original_candidate_and_numerical_reference_sources_remain_sealed():
    sources = HistoricalSources(ROOT)
    for manifest, key in [
        ("candidate-before-heldout-seal.json", "files"),
        ("maintenance-before-heldout.json", None),
    ]:
        values = json.loads((RUN / manifest).read_text())
        for name, digest in (values[key] if key else values).items():
            path = Path(name)
            if name == "src/fatebridge/data/astronomy/vsop2013-solar-v1.json":
                # The old all-repository context recorded this unused catalogue
                # edition. Its original bytes, not the current catalogue, are sealed.
                path = (
                    ROOT
                    / "tests/fixtures/vsop2013_projection_v1/evidence/runtime-before"
                    / name
                )
            assert sources.matches(path, digest)
    assert (RUN / "candidate-before-development-seal.json").read_bytes() == (
        RUN / "candidate-before-heldout-seal.json"
    ).read_bytes()


def test_all_original_position_leaves_and_inner_planet_rates_are_unchanged():
    plan = load(RUN)
    for backend in plan["backends"]:
        for index, case in enumerate(plan["development"]):
            old = json.loads(
                (
                    RUN / f"native-development-baseline-first/{backend}-{index}.json"
                ).read_text()
            )
            new = json.loads(
                (
                    RUN / f"native-development-candidate-first/{backend}-{index}.json"
                ).read_text()
            )
            assert len(old["rows"]) == len(new["rows"]) == len(case["bodies"])
            for before, after in zip(old["rows"], new["rows"]):
                assert before["body"] == after["body"]
                if before["body"] != "Moon":
                    assert before["state"] == after["state"]
                else:
                    allowed = {
                        "longitude_speed",
                        "longitude_speed_analytic_frame_correction",
                    }
                    assert {
                        k: v for k, v in before["state"].items() if k not in allowed
                    } == {k: v for k, v in after["state"].items() if k not in allowed}
                    assert (
                        after["metadata"]["lunar_tropical_frame"]["status"] == "applied"
                    )


def test_complete_fresh_population_and_component_coverage_are_retained():
    data = json.loads((RUN / "heldout-candidate-audit-first.json").read_text())
    assert len(data["rows"]) == 18 and all(r["qualified"] for r in data["rows"])
    assert data["old_gates"] == {"production": 2, "overall": 1}
    assert data["physical_TT_equivalence_certified"] is False
    assert data["original_Horizons_model_equivalence_certified"] is False
    assert data["rate_line_arcsec_per_day"] == "0.002"
    for path in (RUN / "native-heldout-candidate-first").glob("*.json"):
        d = json.loads(path.read_text())
        moon = next(r for r in d["rows"] if r["body"] == "Moon")
        assert moon["metadata"]["lunar_tropical_frame"]["status"] == "applied"
        assert "longitude_speed_analytic_frame_correction" in moon["state"]


@pytest.mark.parametrize("kind", ["population", "binary", "backend", "clock"])
def test_candidate_rebinding_cannot_be_blessed_by_a_good_reference(
    kind, tmp_path, monkeypatch
):
    # Full numerical reference replay has separate tests above; isolate these
    # candidate guards without repeatedly recomputing identical trig series.
    proof = RUN / "heldout-independent-first.json"
    monkeypatch.setattr(grading, "verify", lambda *args: json.loads(proof.read_text()))
    for path in (RUN / "native-heldout-candidate-first").glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    path = tmp_path / "jpl_record_window-0.json"
    data = json.loads(path.read_text())
    if kind == "population":
        path.unlink()
    else:
        if kind == "binary":
            data["native_binary_sha256"] = "0" * 64
        elif kind == "backend":
            data["rows"][0]["native_calls"][0]["returned_flags"] = 258
        else:
            data["rows"][0]["native_numeric_jd"] = 2451545.0
        path.write_text(json.dumps(data))
    messages = {
        "population": "population",
        "binary": "identity rebound",
        "backend": "backend differs",
        "clock": "Numeric time rebound",
    }
    seal = RUN / "candidate-before-heldout-seal.json"
    with pytest.raises(ValueError, match=messages[kind]):
        grading.audit(
            RUN, RUN / "heldout-reference-first.json", proof, tmp_path, seal, sha(seal)
        )


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_auxiliary_proof_keeps_standard_variant_and_all_source_interiors(split):
    proof = json.loads(
        (RUN / f"{split}-independent-decomposition-first.json").read_text()
    )
    assert proof["reference_sha256"] == sha(RUN / f"{split}-reference-first.json")
    assert all(
        r["status"] == "strict_containment_and_interiority_passed"
        for r in proof["rows"]
    )
    assert all(
        r["used_to_replace_primary_variant"] is False
        for r in proof["standard_variant_checks"]
    )
