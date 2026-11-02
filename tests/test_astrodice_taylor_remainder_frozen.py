"""Reject promotion and weakened constraints using one already-seen proof."""

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_astrodice_taylor_remainder import verify

ROOT = (
    Path(__file__).parent.parent
    / "docs/validation/astrodice-derivative-remainder-run-2026-10-28"
)
PLAN = json.loads((ROOT / "design-before-development.json").read_text())
DATA = json.loads((ROOT / "D1-producer-segment-repair-first.json").read_text())
ENTRY = PLAN["development"][0]


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("promote", "promoted"),
        ("drop_model", "model was omitted"),
        ("shrink_window", "whole fixed interval was narrowed"),
        ("zero_remainder", "factorial/remainder"),
        ("drop_window", "window or full degree was dropped"),
    ],
)
def test_saved_development_proof_rejects_weakened_or_promoted_claims(mutation, reason):
    altered = copy.deepcopy(DATA)
    if mutation == "promote":
        altered["physical_TT_time_model_certified"] = True
    elif mutation == "drop_model":
        altered["models"].pop()
    elif mutation == "shrink_window":
        altered["receiver_support"] = altered["center_receiver"]
    elif mutation == "zero_remainder":
        altered["models"][0]["all_window_remainders"][0][
            "derivative_remainder_arcsec_per_source_day"
        ] = ["0", "0"]
    else:
        altered["models"][0]["all_window_remainders"].pop()
    with pytest.raises(ValueError, match=reason):
        verify(PLAN, ENTRY, altered)
