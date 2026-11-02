"""Keep source variants and nonblinded corrections separate from computation."""

import copy
import hashlib
import json
import runpy
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.validation import guolao_witnesses as audit

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-witness-variants-v1"


def test_source_artifacts_initial_reading_and_correction_are_preserved():
    data, _, _ = audit._read()
    reference_raw = (FIXTURE / "reference.json").read_bytes()
    assert hashlib.sha256(reference_raw).hexdigest() == data["fixture_reference_sha256"]
    reference = json.loads(reference_raw)
    assert reference["single_collator"]
    assert not reference["independent_second_collator"]
    assert reference["prior_formula_and_siku_values_known"]
    assert reference["prior_witness_results_known_while_reading_later_witnesses"]
    for artifact in reference["artifacts"]:
        raw = (FIXTURE / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    for witness in data["witnesses"]:
        initial_final = json.loads(
            (FIXTURE / (witness["witness_id"] + "-final-observations.json")).read_text()
        )
        for frozen, row in zip(
            initial_final["observations"], witness["observations"], strict=True
        ):
            assert all(frozen[key] == row[key] for key in frozen)
            for name in ["complete_page_image", "inspection_crop"]:
                assert (FIXTURE / row[name]).is_file()
    journal = json.loads((FIXTURE / "reading-corrections.json").read_text())
    assert (
        journal["initial_sha256"]
        == hashlib.sha256((FIXTURE / journal["initial_path"]).read_bytes()).hexdigest()
    )
    assert len(journal["corrections"]) == 1
    correction = journal["corrections"][0]
    assert correction["limit_index"] == 155
    assert correction["initial_value"] == "-0.10255075"
    assert correction["corrected_value"] == "-0.10225075"
    # Reinspection moves away from the adjacency expectation, not toward a fit.
    assert correction["corrected_value"] != "-0.10255075"
    assert not correction["reviewer_independent_of_initial_collator"]


def test_all_six_targets_and_four_witness_readings_remain_unadjudicated():
    result = audit.audit_gujin45_witness_variants()
    assert result["additional_readings"] == 18
    assert result["declared_target_cells"] == 6
    assert [(c["field"], c["limit_index"]) for c in result["cells"]] == list(
        audit.TARGETS
    )
    assert [c["limit_index"] for c in result["cells_with_observed_variants"]] == [
        90,
        154,
        12,
    ]
    expected = [
        ("7.2807", "7.3607"),
        ("12.6392", "12.6292"),
        ("13.6333", "13.6333"),
        ("0.10225075", "0.10255075"),
        ("-0.10225075", "-0.10225075"),
        ("-0.10817275", "-0.10817275"),
    ]
    for cell, (baseline, additional) in zip(result["cells"], expected, strict=True):
        assert [r["value"] for r in cell["readings"]] == [baseline] + [additional] * 3
        assert cell["adjudicated_value"] is None
        assert cell["computational_override"] is None
        for row in cell["readings"][1:]:
            assert Fraction(row["difference_from_siku_exact"]) == Fraction(
                additional
            ) - Fraction(baseline)
    assert not result["independent_textual_ancestry_established"]
    assert not result["same_printing_blocks_established"]
    assert not result["can_supply_complete_computational_profile"]
    assert not result["existing_computational_profiles_modified"]
    assert not result["majority_or_formula_fit_used_for_adjudication"]
    assert not result["predictive_validity_demonstrated"]
    assert result["new_real_world_prediction_subjects"] == 0


def _mutated_data(tmp_path, monkeypatch):
    data = json.loads(audit.DATA.read_text())
    for name in data["baseline_files_sha256"]:
        (tmp_path / Path(name).name).write_bytes(
            (audit.DATA.parent / Path(name).name).read_bytes()
        )
    monkeypatch.setattr(audit, "DATA", tmp_path / "variants.json")
    return copy.deepcopy(data)


@pytest.mark.parametrize(
    "flag",
    [
        "independent_second_collator",
        "full_additional_table_transcription",
        "textual_ancestry_adjudicated",
        "computational_overrides_authorized",
    ],
)
def test_metadata_cannot_upgrade_six_cells_into_full_source_acceptance(
    tmp_path, monkeypatch, flag
):
    data = _mutated_data(tmp_path, monkeypatch)
    data[flag] = True
    audit.DATA.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="不是独立双人校勘"):
        audit.audit_gujin45_witness_variants()


@pytest.mark.parametrize("operation", ["missing", "duplicate", "reorder"])
def test_missing_or_reordered_targets_are_rejected_without_filling(
    tmp_path, monkeypatch, operation
):
    data = _mutated_data(tmp_path, monkeypatch)
    rows = data["witnesses"][0]["observations"]
    if operation == "missing":
        rows.pop()
    elif operation == "duplicate":
        rows[1] = rows[0]
    else:
        rows.reverse()
    audit.DATA.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="缺值不得省略或补齐"):
        audit.audit_gujin45_witness_variants()


@pytest.mark.parametrize("value", [None, 7.3607, "7.36070", "7.3807_inferred"])
def test_unknown_or_inferred_cells_cannot_masquerade_as_literal_values(
    tmp_path, monkeypatch, value
):
    data = _mutated_data(tmp_path, monkeypatch)
    data["witnesses"][0]["observations"][0]["value"] = value
    audit.DATA.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="原读数"):
        audit.audit_gujin45_witness_variants()


def test_changed_siku_baseline_is_rejected_instead_of_silently_rebased(
    tmp_path, monkeypatch
):
    data = _mutated_data(tmp_path, monkeypatch)
    file = tmp_path / "gujin45-day-rate-v1.json"
    baseline = json.loads(file.read_text())
    baseline["rows"][90]["day_rate_days"] = "7.3607"
    file.write_text(json.dumps(baseline))
    audit.DATA.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="指纹改变"):
        audit.audit_gujin45_witness_variants()


def test_targeted_cli_prints_the_complete_unadjudicated_matrix(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit_guolao_witnesses.py", "--targeted-audit"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_witnesses.py"), run_name="__main__"
        )
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out) == audit.audit_gujin45_witness_variants()


def test_cli_requires_explicit_targeted_scope(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit_guolao_witnesses.py"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_witnesses.py"), run_name="__main__"
        )
    assert exit_info.value.code == 2
    assert not capsys.readouterr().out
