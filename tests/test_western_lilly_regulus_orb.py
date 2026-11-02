"""Source-corrected Regulus range; retain the original erroneous annotation."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.lilly_fortune import evaluate_fortune
from scripts.audit_western_lilly_fortitudes import audit
from tests.test_western_lilly_fortitudes import inputs, result, row

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/western-lilly-regulus-orb-v2"
CORRECTION = json.loads((FIXTURE / "correction.json").read_text())
RAW = json.loads((FIXTURE / "cases.json").read_text())["cases"]
# The sealed list contains repeated zero offsets in its two directions.
# Count each identical input once, retaining every distinct counterexample.
CASES = list({(c["star"], c["gap_exact"]): c for c in RAW}.values())


def test_manual_source_correction_is_sealed_and_does_not_replace_original_answers():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert len(RAW) == 42 and len(CASES) == 39
    assert CORRECTION["stellar_orbs_degrees"] == {"Regulus": 6, "Spica": 5, "Algol": 5}
    assert CORRECTION["original_annotation_preserved"]
    assert not CORRECTION["book_weights_changed"]
    assert not CORRECTION["printed_totals_changed"]
    evidence = audit()
    assert evidence["original_annotation_row_table_matches"] is False
    assert evidence["row_table_matches"] is True
    assert evidence["planetary_applications_reproduced"] == 3
    assert evidence["planetary_applications_compared"] == 7
    assert not evidence["worked_example_reproduction_passed"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["star"] + ":" + c["gap_exact"])
def test_planet_and_declared_fortune_transfer_use_each_stars_own_range(case):
    states, data = inputs()
    star = case["star"]
    gap = Fraction(case["gap_exact"])
    data["star_longitudes"][star] = 0
    states["Mercury"]["longitude"] = gap
    code = {"Regulus": "F17", "Spica": "F18", "Algol": "D15"}[star]
    observed = row(result(states, data), "Mercury", code)
    assert observed["satisfied"] == case["expected"]
    assert observed["inputs"]["orb_degrees"] == CORRECTION["stellar_orbs_degrees"][star]
    assert observed["source_pages"] == CORRECTION["source_pages"][star]
    fortune = evaluate_fortune(
        gap + states["Sun"]["longitude"] - states["Moon"]["longitude"],
        states,
        data,
        house_assignment={
            "assigned_house": 1,
            "geometric_house": 1,
            "assignment_policy": "controlled synthetic house fact",
        },
        house_system="R",
        zodiac_type="Tropic",
    )
    code = {"Regulus": "P14", "Spica": "P15", "Algol": "N10"}[star]
    observed = next(r for r in fortune["rows"] if r["code"] == code)
    assert observed["satisfied"] == case["expected"]
    assert observed["inputs"]["orb_degrees"] == CORRECTION["stellar_orbs_degrees"][star]
    assert "declared convention" in observed["inputs"]["star_policy"]
    assert not fortune["full_original_text_acceptance"]
