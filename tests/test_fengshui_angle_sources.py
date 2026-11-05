"""Ambiguous angular units cannot certify or silently recalibrate selection."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.fengshui import xuankong
from fatebridge.validation.fengshui_angle_sources import (
    audit_angle_source_reference,
    load_angle_source_reference,
    normalize_source_quantities,
)

FOLDER = Path(__file__).parent / "data/fengshui_angle_sources_v1"


def test_frozen_source_preserves_author_context_and_different_local_units():
    raw = (FOLDER / "reference.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "9257220a2e0a9b96a1e4a086273cca7f815802bc135a97655409093f4855de0e"
    )
    reference = load_angle_source_reference(FOLDER)
    geometry = reference["wang_geometry"]
    assert geometry["grid_width_degrees"] == 3
    assert geometry["local_colloquial_label"]["grid_width_fen"] == 3
    assert not geometry["local_colloquial_label"][
        "global_fen_unit_conversion_established"
    ]
    assert reference["categorical_predicate"]["pdf_page"] == 755
    assert "章仲山" in reference["categorical_predicate"]["section_context"]
    assert not reference["quarantined_lead"]["admitted_for_expected_values"]


def test_unknown_unit_or_origin_cannot_be_filled_from_the_engine_threshold():
    reference = load_angle_source_reference(FOLDER)
    old, edited = [
        normalize_source_quantities(c) for c in reference["unresolved_thresholds"]
    ]
    assert old["source_quantities"] == ["3", "4"]
    assert old["missing_normalization_facts"] == [
        "degrees_per_unit",
        "origin_offset_degrees",
    ]
    assert edited["source_quantities"] == ["3"]
    assert edited["missing_normalization_facts"] == ["origin_offset_degrees"]
    assert old["offsets_from_center_degrees_exact"] is None
    assert edited["offsets_from_center_degrees_exact"] is None


def test_same_numeral_can_mean_different_offsets_under_explicit_synthetic_facts():
    claim = {
        "id": "synthetic_not_a_book_claim",
        "quantities": ["3"],
        "unit_label": "test_unit",
        "degrees_per_unit": "1",
        "origin_offset_degrees": "0",
    }
    direct = normalize_source_quantities(claim)
    scaled = normalize_source_quantities({**claim, "degrees_per_unit": "3/2"})
    shifted = normalize_source_quantities({**claim, "origin_offset_degrees": "3/2"})
    assert direct["offsets_from_center_degrees_exact"] == ["3"]
    assert scaled["offsets_from_center_degrees_exact"] == ["9/2"]
    assert shifted["offsets_from_center_degrees_exact"] == ["9/2"]
    assert all(
        not c["complete_selection_condition_verified"]
        for c in (direct, scaled, shifted)
    )


@pytest.mark.parametrize(
    "change",
    [
        {"quantities": [True]},
        {"quantities": [3.0]},
        {"quantities": ["-1"]},
        {"degrees_per_unit": "0"},
        {"degrees_per_unit": True},
        {"origin_offset_degrees": "-1"},
    ],
)
def test_invalid_quantities_never_gain_angular_evidence(change):
    claim = deepcopy(load_angle_source_reference(FOLDER)["unresolved_thresholds"][1])
    claim.update(change)
    with pytest.raises(ValueError):
        normalize_source_quantities(claim)


def test_all_relative_regions_keep_the_declared_composition_scope():
    result = audit_angle_source_reference(load_angle_source_reference(FOLDER))
    assert result["relative_probes"] == 144
    assert result["declared_composition_agreement"]
    assert result["disagreements"] == []
    assert result["unresolved_threshold_claim_count"] == 2
    central = [p for p in result["probes"] if abs(p["signed_offset_degrees"]) == 4]
    wings = [p for p in result["probes"] if abs(p["signed_offset_degrees"]) in (5, 7)]
    assert len(central) == 48
    assert {p["expected_mode_under_composition"] for p in central} == {"lower"}
    assert sum(p["expected_mode_under_composition"] == "lower" for p in wings) == 32
    assert (
        sum(p["expected_mode_under_composition"] == "replacement" for p in wings) == 64
    )
    for key in (
        "universal_fen_to_degree_conversion_established",
        "source_angle_applicability_verified",
        "boundary_equality_policy_verified",
        "absolute_compass_orientation_verified",
        "whole_book_conformity_established",
        "independent_human_expert_review_complete",
        "real_world_prediction_established",
    ):
        assert result[key] is False


def test_wrong_threshold_is_retained_as_a_failure(monkeypatch):
    original = xuankong.natal_rules
    rules = deepcopy(original())
    rules["central_half_width_degrees"] = 3
    monkeypatch.setattr(xuankong, "natal_rules", lambda: rules)
    result = audit_angle_source_reference(load_angle_source_reference(FOLDER))
    assert not result["declared_composition_agreement"]
    assert result["disagreements"][0] == {
        "scope": "central_half_width",
        "source_expected_exact": "9/2",
        "actual_exact": "3",
    }


def test_dropping_a_branch_cannot_improve_composition_agreement(monkeypatch):
    original = xuankong._selectors

    def discard_replacement(angle, uncertainty):
        return [s for s in original(angle, uncertainty) if s[1] != "replacement"]

    monkeypatch.setattr(xuankong, "_selectors", discard_replacement)
    result = audit_angle_source_reference(load_angle_source_reference(FOLDER))
    assert not result["declared_composition_agreement"]
    assert len(result["disagreements"]) == 64
    assert all(d["actual"] == [] for d in result["disagreements"])


def test_changed_source_bytes_are_rejected(tmp_path):
    for name in ("reference.json", "hashes.json"):
        (tmp_path / name).write_bytes((FOLDER / name).read_bytes())
    data = json.loads((tmp_path / "reference.json").read_text())
    data["wang_geometry"]["central_width_degrees"] = 6
    (tmp_path / "reference.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="transcription changed"):
        load_angle_source_reference(tmp_path)


def test_non_object_source_is_rejected_even_with_a_matching_manifest(tmp_path):
    raw = b"[]\n"
    (tmp_path / "reference.json").write_bytes(raw)
    (tmp_path / "hashes.json").write_text(
        json.dumps({"reference.json": hashlib.sha256(raw).hexdigest()})
    )
    with pytest.raises(ValueError, match="must be an object"):
        load_angle_source_reference(tmp_path)
