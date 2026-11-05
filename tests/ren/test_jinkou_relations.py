"""Primary pair variants, missing birth scope and whole-board fidelity."""

import importlib.util
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.jinkou_relations import structural_relations
from fatebridge.core.output_chinese import JinkouRelations
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from tests.ren.test_ren_classical_depth import AUDIT as CLASSICAL
from tests.ren.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_relations", ROOT / "scripts/ren/audit_jinkou_relations.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_complete_source_rule_matrices_keep_true_and_false_relations():
    report = AUDIT.audit()
    assert report["totals"] == {"si_jue": 720, "si_bai_seats": 180, "calendar": 1296}
    assert report["selected_rule_checks_passed"]
    assert not report["classical_acceptance_passed"] and not report["goal_complete"]
    assert len(report["incomplete_requirements"]) == 5
    diagnostic = report["source_reconstruction_diagnostics"]
    assert diagnostic["case_count"] == 64 and diagnostic["missing_source_day"] == 2
    assert diagnostic["default_matched"] == 46
    assert diagnostic["either_override_matched"] == 49
    assert diagnostic["alternate_only_ids"] == ["P34", "P41", "P44"]


@pytest.mark.parametrize("god,general,phase", [("午", "亥", "火"), ("巳", "子", "水")])
def test_scan_corrects_swapped_transcription_phases_without_changing_pairs(
    god, general, phase
):
    rows = AUDIT.literal_rows(dict(人元="甲", 贵神=god, 将神=general, 地分="辰"))
    result = structural_relations(
        rows, year_branch="午", day_branch="申", hour_branch="酉"
    )
    primary = result["si_jue"]["checks"][0]
    assert primary["element"] == phase and primary["matched"]
    assert primary["classification"] == "正绝"
    variant = next(
        row
        for row in result["transcription_variants"]
        if set(row["branches"]) == {god, general}
    )
    assert variant["scan_element"] == phase != variant["transcription_element"]
    assert primary["original_pdf_page"] == variant["original_pdf_page"] == 109


def test_generic_twelve_stage_extinction_is_not_substituted_for_the_named_pairs():
    # A wood phase with 申 is not sufficient: this chapter names 卯申, not 寅申.
    rows = AUDIT.literal_rows(dict(人元="甲", 贵神="寅", 将神="申", 地分="辰"))
    result = structural_relations(
        rows, year_branch="子", day_branch="子", hour_branch="子"
    )
    assert result["si_jue"]["checks"][0]["matched"] is False
    missing = result["si_jue"]["unavailable"][0]
    assert missing["classification"] == "大绝" and missing["matched"] is None
    assert missing["status"] == "missing_birth_branch"


def test_existing_book_rows_and_use_are_preserved_with_new_relations():
    board = CLASSICAL.observe_jinkou(
        dict(day="丙申", hour="丑", ground="巳", general="子")
    )
    assert (
        board["overview"]["use_position"] == board["use_evidence"]["polarity_position"]
    )
    assert board["use_evidence"]["comprehensive_position"] is None
    assert board["relations"]["calendar"]["day_branch"] == "申"
    assert board["relations"]["si_jue"]["unavailable"][0]["matched"] is None
    assert board["ruleset"]["version"] == "1.16.0"
    assert board["ruleset"]["classical_acceptance_passed"] is False


def test_snapshot_and_selected_shensha_export_use_only_actual_matched_relations():
    result = calculate_jinkou_analysis(
        **PAYLOAD, di_fen="酉", selected_sections=["四位神煞"]
    )
    assert "error" not in result
    relations = result["jinkou"]["relations"]
    for group in ("si_jue", "si_bai", "calendar"):
        for row in relations[group]["checks"]:
            if row["matched"]:
                assert row["basis"] in result["snapshot_text"]
                assert row["basis"] in result["snapshot_export"]["export_text"]
    assert "大绝未计算" in result["snapshot_export"]["export_text"]
    invalid = deepcopy(relations)
    invalid["si_jue"]["checks"][0]["matched"] = "false"
    with pytest.raises(ValidationError):
        JinkouRelations.model_validate(invalid)


def test_primary_source_manifest_rejects_changed_phase_labels(tmp_path):
    target = tmp_path / "relations"
    shutil.copytree(AUDIT.CORPUS, target)
    path = target / "reference.json"
    path.write_text(path.read_text().replace('"element": "火"', '"element": "水"', 1))
    with pytest.raises(ValueError, match="Frozen relation reference changed"):
        AUDIT.reference(target)
