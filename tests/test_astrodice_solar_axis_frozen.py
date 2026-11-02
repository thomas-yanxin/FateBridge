"""Replay the immutable analytic holdout without promoting it to sky data."""

import hashlib
import json
from pathlib import Path

from scripts.verify_astrodice_solar_axis import verify

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-solar-axis-run-2026-10-28"


def test_all_heldout_profiles_have_independent_containment():
    actual = verify(RUN, RUN / "heldout-first.json")
    for name in [
        "heldout-independent-first.json",
        "heldout-independent-isolated-313-first.json",
    ]:
        assert actual == json.loads((RUN / name).read_text())
    assert actual["samples"] == 16
    assert actual["new_astronomical_observations"] == 0


def test_original_heldout_sources_and_pre_opening_copies_remain_sealed():
    hashes = json.loads((RUN / "analytic-freeze-before-holdout.json").read_text())
    for name, digest in hashes.items():
        copy = RUN / "analytic-frozen-before-holdout" / name
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == digest


def test_original_plan_and_error_lines_remain_fixed():
    raw = (RUN / "plan-before-analysis.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "07c7990ebec093e7c98f26a412c6949b3c56818575134d28cee56e7cec284bcc"
    )
    plan = json.loads(raw)
    assert set(plan["development_exponents"]).isdisjoint(plan["heldout_exponents"])
    assert plan["old_position_line_arcsec"] == "0.02"
    assert plan["old_rate_reference_line_arcsec_per_day"] == "0.002"
    assert plan["production_acceptance_exit_code"] == 2
    assert plan["retained_overall_numeric_gate_exit_code"] == 1
    assert plan["original_results_regraded"] is False
