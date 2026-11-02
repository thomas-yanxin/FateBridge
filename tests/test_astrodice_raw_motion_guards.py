"""Preserve every original condition and refuse false source/precision claims."""

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_astrodice_raw_motion import verify

RUN = Path("docs/validation/astrodice-raw-motion-run-2026-10-28")


@pytest.mark.parametrize(
    "mutation",
    [
        "case",
        "body",
        "raw_acceleration",
        "observer_acceleration",
        "clock",
        "source",
        "agreement",
        "old_gate",
    ],
)
def test_independent_replay_rejects_changed_evidence(tmp_path, mutation):
    candidate = json.loads((RUN / "development-candidate-first.json").read_text())
    candidate = copy.deepcopy(candidate)
    row = candidate["rows"][0]
    fixed = row["motion"]["lunar_light_time"]["fixed_frame_source_derivative"]
    if mutation == "case":
        candidate["rows"].pop()
    elif mutation == "body":
        row["raw_states"].pop("Venus")
    elif mutation == "raw_acceleration":
        row["raw_states"]["Earth"][0][6] += 0.00001
    elif mutation == "observer_acceleration":
        fixed["acceleration_estimates_au_per_day2"][0][0] += 0.00001
    elif mutation == "clock":
        row["raw_states"]["Mercury"][1]["tt_tdb_conversion_applied"] = True
    elif mutation == "source":
        row["source"]["files"][0]["sha256"] = "changed"
    elif mutation == "agreement":
        fixed["observer_derivative_disagreement_arcsec_per_day"] = 0.0
    elif mutation == "old_gate":
        candidate["old_gates"]["overall"] = 0
    else:
        raise AssertionError(mutation)
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(candidate))
    with pytest.raises(ValueError):
        verify(RUN, path, RUN / "development-baseline-first.json")
