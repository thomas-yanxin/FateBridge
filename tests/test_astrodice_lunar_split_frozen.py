"""Bind first independent receipts and require strict centre source support."""

import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.audit_astrodice_lunar_split import audit, cell_interior

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-lunar-split-run-2026-10-28"


def test_frozen_output_proofs_and_all_centre_interiors_are_retained():
    summary = audit(RUN)
    assert summary == json.loads((RUN / "posthoc-summary-first.json").read_text())
    assert summary["distinct_source_centres_including_control"] == 21
    assert len(summary["source_interiority_checks"]) == 84
    assert summary["all_selected_centres_strictly_inside_source_cells"]
    assert summary["results"]["development"]["rows"] == 20
    assert summary["results"]["heldout"]["rows"] == 4
    assert summary["results"]["heldout"]["model_points"] == 438
    assert [
        x["original_failed_template_count"]
        for x in summary["old_external_reference_failures"]
    ] == [4, 4]
    assert summary["old_gate_codes"] == [2, 1]
    assert summary["full_goal_complete"] is False


@pytest.mark.parametrize("offset", [Q(0), Q(4), Q(16)])
def test_a_source_knot_never_proves_a_unique_two_sided_derivative(offset):
    part, margin = cell_interior(Q(100) + offset, Q(100) + offset, Q(100), Q(132), 8)
    assert part == offset // 4
    assert margin == 0


def test_an_interval_straddling_a_source_knot_is_unqualified():
    _, margin = cell_interior(Q(104) - Q(1, 100), Q(104) + Q(1, 100), Q(100), Q(132), 8)
    assert margin < 0


def test_an_exact_interior_interval_has_a_positive_margin():
    part, margin = cell_interior(Q(105), Q(106), Q(100), Q(132), 8)
    assert part == 1 and margin == 1


def test_original_source_code_remains_sealed_with_its_pre_opening_copy():
    files = json.loads((RUN / "code-before-holdout.json").read_text())
    for name, h in files.items():
        assert (
            hashlib.sha256(
                (RUN / "source-before-holdout" / name).read_bytes()
            ).hexdigest()
            == h
        )
