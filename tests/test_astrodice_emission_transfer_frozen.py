"""Seen development rows with independent source replay and tamper refusal."""

import copy
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_emission_transfer import check_row

FIXTURE = Path(__file__).parent / "fixtures/astrodice-emission-transfer-v1/cases.json"
NATIVE = Path(__file__).parent / "fixtures/astrodice-native-reference-v1"
SHA = "7b50ae67995e42512ab65e234a89209da63a8cc9ac5074bb7edd737839ed9684"


@pytest.fixture(scope="module")
def frozen():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == SHA
    data = json.loads(FIXTURE.read_text())
    for name, digest in data["native_source_sha256"].items():
        assert hashlib.sha256((NATIVE / name).read_bytes()).hexdigest() == digest
    assert not data["original_results_regraded"]
    return data


@pytest.mark.parametrize("index", (0, 1))
def test_seen_row_all_eight_models_independent_replay(frozen, index):
    row = frozen["rows"][index]
    check_row(
        NATIVE,
        row["case"],
        row["observation"],
        row["pair"],
        row["saved"],
        frozen["design"],
        frozen["checking"],
    )


@pytest.mark.parametrize("mutation", ("pair", "model", "printing", "promotion"))
def test_tampering_does_not_become_conditional_acceptance(frozen, mutation):
    row = copy.deepcopy(frozen["rows"][0])
    saved = row["saved"]
    if mutation == "pair":
        saved["receiver_hex"] = float(0).hex()
    elif mutation == "model":
        saved["models"].pop()
    elif mutation == "printing":
        low, high = map(Q, saved["original_printing_interval_arcsec"][0])
        # Attempt to shrink full printed LSB to half, with a passing midpoint.
        saved["original_printing_interval_arcsec"][0] = [
            str((3 * low + high) / 4),
            str((low + 3 * high) / 4),
        ]
    else:
        saved["physical_service_model_equivalence_certified"] = True
    with pytest.raises(ValueError):
        check_row(
            NATIVE,
            row["case"],
            row["observation"],
            row["pair"],
            saved,
            frozen["design"],
            frozen["checking"],
        )
