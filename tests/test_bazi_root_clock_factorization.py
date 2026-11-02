"""Paired interventions preserve introduced failures and non-additive effects."""

import gzip
import json
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from scripts.factor_bazi_saved_clock_roots import point, transition_counts

STUDY = (
    Path(__file__).resolve().parents[1]
    / "docs/validation/bazi-root-clock-factorization-v1"
)


def test_pairing_reports_both_directions_and_cancellations():
    masks = Counter({"10000": 2, "01000": 3, "00100": 5, "00010": 7})
    result = transition_counts(masks)
    assert result["original_to_legacy"] == {
        "outside_to_inside": 2,
        "inside_to_outside": 3,
    }
    assert result["legacy_to_exact_scalar"] == {
        "outside_to_inside": 3,
        "inside_to_outside": 5,
    }
    assert result["exact_scalar_to_split_skyfield"] == {
        "outside_to_inside": 5,
        "inside_to_outside": 7,
    }
    assert result["split_skyfield_to_actual"] == {
        "outside_to_inside": 7,
        "inside_to_outside": 0,
    }
    # Adding favorable transitions would give17, even though only2 oldrows failed.
    assert sum(r["outside_to_inside"] for r in result.values()) == 17


def test_tt_parts_never_add_at_large_float_jd():
    parts = [2451545.0, 1e-12]
    assert sum(parts) == parts[0]
    assert point(parts) - Fraction(parts[0]) == Fraction(parts[1])


def test_release_assumption_flag_uses_the_source_release_date():
    file = STUDY / "independent-atomic-roots-v2.json.gz"
    if not file.exists():
        file = STUDY / "independent-atomic-roots-first.json.gz"
    reference = json.loads(gzip.decompress(file.read_bytes()))
    for row in reference["rows"]:
        expected = (
            row["split_point_utc"] is not None
            and datetime.fromisoformat(row["split_point_utc"]).date()
            > datetime(2023, 10, 11).date()
        )
        assert row["later_than_source_release"] is expected, row


def test_every_atomic_point_is_preserved_and_pre_utc_is_unavailable():
    reference = json.loads(
        gzip.decompress((STUDY / "independent-atomic-roots-first.json.gz").read_bytes())
    )
    assert len(reference["rows"]) == 4872
    assert reference["atomic_points"] == 3408
    assert reference["unavailable_pre_UTC"] == 1464
    comparison = json.loads(
        (STUDY / "independent-atomic-comparison-first.json").read_text()
    )
    assert comparison["compared_point_counts"] == {
        "scalar_point_utc": 3408,
        "split_point_utc": 3408,
    }
    assert comparison["mismatches"] == []
    assert (
        comparison[
            "first_and_repaired_counterfactual_uncompressed_records_byte_identical"
        ]
        is True
    )
    assert comparison["old_frozen_labels_different_from_exact_scalar_point"] == 3386


def test_full_cohort_masks_retain_the_original_gate_and_unknowns():
    data = json.loads(
        gzip.decompress(
            (STUDY / "paired-factorization-dependency-closed.json.gz").read_bytes()
        )
    )
    counts = data["counts"]
    assert len(data["source_clock_dependencies_checked_before_and_after"]) == 7
    assert counts["all_rows"] == 116906
    assert counts["known_rows"] == 116124 and counts["unresolved_retained"] == 782
    assert counts["all_known_probes"] == 812868
    assert counts["safe_probes"] == 580620
    assert counts["original_outside_rows"] == 54818
    assert sum(data["masks"].values()) == counts["known_rows"]
    assert data["transition_counts"] == transition_counts(data["masks"])
    assert data["transition_counts"]["original_to_legacy"]["inside_to_outside"] == 8716
    assert (
        data["original_gate_superseded"] is data["original_strict_gate_passed"] is False
    )
