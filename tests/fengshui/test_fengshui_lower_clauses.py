"""A complete fixed edition must retain its inconvenient prose/diagram conflicts."""

import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation import fengshui_lower_clauses as audit

FOLDER = Path(__file__).parents[1] / "data/fengshui_lower_clauses_v1"
WEB = Path(__file__).parents[1] / "data/fengshui_classical_v1/reference.json"


def sources():
    return audit.load_lower_clause_reference(FOLDER), json.loads(WEB.read_text())


def test_complete_edition_keeps_all_three_unresolved_conflicts():
    data, web = sources()
    result = audit.audit_lower_clauses(data, web)
    assert result["printed_prose_checked"] == 216
    assert result["printed_prose_matched"] == 213
    assert result["web_numeric_pairs_checked"] == 216
    assert result["web_numeric_pairs_matched"] == 216
    assert result["web_numeric_differences"] == []
    assert result["same_edition_diagrams_checked"] == 3
    assert result["diagram_numerals_checked"] == 81
    assert result["diagram_numeral_differences"] == []
    assert result["diagram_spot_checks_passed"] is True
    assert result["unresolved_source_conflict_count"] == 3
    conflicts = result["same_edition_prose_diagram_conflicts"]
    assert {(r["period"], r["facing_mountain"], r["pdf_page"]) for r in conflicts} == {
        (4, "酉", 302),
        (1, "卯", 307),
        (6, "乾", 324),
    }
    for key in (
        "complete_printed_clause_acceptance_passed",
        "silent_correction_or_edition_switch_authorized",
        "all_216_diagrams_collated",
        "whole_book_conformity_established",
        "independent_human_expert_review_complete",
        "calendar_selection_verified",
        "empirical_predictive_validity_established",
        "authority_certified",
    ):
        assert result[key] is False


def test_fixed_pre_engine_source_and_ocr_are_not_rewritten_for_a_pass():
    assert hashlib.sha256((FOLDER / "reference.json").read_bytes()).hexdigest() == (
        "85a10d759544d5b7729e6ffbec6427a1a5ee443b353184d0daa49e34f3b5ac88"
    )
    data, _ = sources()
    assert data["reference"]["fatebridge_imported"] is False
    assert data["reference"]["coverage"]["unparsed_clauses"] == []
    assert data["diagrams"]["no_engine_comparison_before_freeze"] is True
    assert data["edition_notes"]["cip_date"] == "2011.3（2016.2重印）"
    assert data["edition_notes"]["colophon_edition"] == "2011年6月第1版"
    assert data["edition_notes"]["colophon_printing"] == "2016年2月第3次印刷"
    assert data["edition_notes"]["historical_base_independently_authenticated"] is False
    ocr = json.loads((FOLDER / "ocr-checks.json").read_text())
    assert ocr["count"] == 216 and ocr["exact_native_prefix_matches"] == 215
    failed = [r for r in ocr["rows"] if not r["native_prefix_exactly_present"]]
    assert len(failed) == 1 and failed[0]["capture"]["file"] == "p368-亥-巳-9.png"
    assert failed[0]["lines"][0]["text"].startswith("九运挨星，一到山，儿到向")
    manual = json.loads((FOLDER / "ocr-manual-review.json").read_text())
    assert manual["manual_pixel_checks"][0]["visible_pixels"] == "八到向"
    assert manual["native_reference_edited_to_match_engine"] is False


@pytest.mark.parametrize("section", ["printed", "web"])
@pytest.mark.parametrize("mutation", ["remove", "duplicate"])
def test_cannot_silently_reduce_or_duplicate_the_216_pair_scope(section, mutation):
    data, web = sources()
    rows = data["reference"]["rows"] if section == "printed" else web["shen_cases"]
    if mutation == "remove":
        rows.pop()
    else:
        rows[-1] = deepcopy(rows[0])
    with pytest.raises(ValueError, match="216 distinct"):
        audit.audit_lower_clauses(data, web)


@pytest.mark.parametrize(
    "mutation", ["remove_chart", "remove_palace", "remove_numeral"]
)
def test_cannot_omit_conflicting_diagram_evidence(mutation):
    data, web = sources()
    diagrams = data["diagrams"]["cases"]
    if mutation == "remove_chart":
        diagrams.pop()
    elif mutation == "remove_palace":
        diagrams[0]["palaces"].pop("NE")
    else:
        diagrams[0]["palaces"]["NE"].pop("mountain")
    with pytest.raises(ValueError, match="All three|All nine|All 27"):
        audit.audit_lower_clauses(data, web)


def test_replacing_disagreeing_metadata_with_engine_values_cannot_pass():
    data, web = sources()
    row = next(
        r
        for r in data["reference"]["rows"]
        if (r["period"], r["facing_mountain"]) == (4, "酉")
    )
    row["mountain_flight"] = row["facing_flight"] = "forward"
    with pytest.raises(ValueError, match="uncorrected literal"):
        audit.audit_lower_clauses(data, web)


def test_corrupt_engine_grid_is_detected_without_rewriting_the_source(monkeypatch):
    data, web = sources()
    real = audit.xuankong_natal

    def altered(request):
        result = deepcopy(real(request))
        for palace in result["chart"]["palaces"].values():
            palace["mountain_star_number"] = palace["mountain_star_number"] % 9 + 1
        return result

    monkeypatch.setattr(audit, "xuankong_natal", altered)
    result = audit.audit_lower_clauses(data, web)
    assert len(result["diagram_numeral_differences"]) == 27
    assert result["diagram_spot_checks_passed"] is False
    assert result["complete_printed_clause_acceptance_passed"] is False
    assert result["unresolved_source_conflict_count"] == 3


def test_regressed_trace_cannot_hide_behind_the_existing_three_disputes(monkeypatch):
    data, web = sources()
    real = audit.xuankong_natal

    def altered(request):
        result = deepcopy(real(request))
        chart = result["chart"]
        if chart["period_number"] == 1 and chart["facing"]["name"] == "午":
            chart["trace"]["mountain"]["flight"] = "reverse"
        return result

    monkeypatch.setattr(audit, "xuankong_natal", altered)
    result = audit.audit_lower_clauses(data, web)
    assert result["printed_prose_matched"] == 212
    assert len(result["printed_prose_differences"]) == 4
    assert result["complete_printed_clause_acceptance_passed"] is False


def test_audit_is_read_only_and_ignores_self_awarded_coverage_flags():
    data, web = sources()
    data["reference"]["coverage"]["row_count"] = 99999
    data["reference"]["whole_book_conformity_established"] = True
    data["diagrams"]["all_216_diagrams_collated"] = True
    original = deepcopy((data, web))
    result = audit.audit_lower_clauses(data, web)
    assert (data, web) == original
    assert result["printed_prose_checked"] == 216
    assert result["all_216_diagrams_collated"] is False
    assert result["whole_book_conformity_established"] is False


@pytest.mark.parametrize(
    "name", ["reference.json", "captures/p302-卯-酉-4.png", "modern-page-324.png"]
)
def test_changed_source_bytes_are_rejected(tmp_path, name):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    with (folder / name).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="source capture changed|pre-engine freeze"):
        audit.load_lower_clause_reference(folder)


def test_rehashed_rewritten_prose_still_breaks_the_pre_engine_identity(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    reference = json.loads((folder / "reference.json").read_text())
    reference["rows"][0]["mountain_seed"] = 1
    (folder / "reference.json").write_text(json.dumps(reference))
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest["reference.json"] = hashlib.sha256(
        (folder / "reference.json").read_bytes()
    ).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pre-engine freeze"):
        audit.load_lower_clause_reference(folder)


def test_removed_capture_manifest_entry_cannot_shrink_the_source_scope(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest.pop("captures/p302-卯-酉-4.png")
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Incomplete"):
        audit.load_lower_clause_reference(folder)


def test_unaltered_global_source_gate_keeps_both_edition_scopes(tmp_path):
    target = tmp_path / "audit.json"
    process = subprocess.run(
        [
            sys.executable,
            "scripts/fengshui/audit_fengshui_sources.py",
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 1, process.stderr
    result = json.loads(target.read_text())
    assert result["counts"]["xuankong"] == {"checked": 216, "matched": 213}
    assert result["numeric_clause_acceptance_passed"] is False
    assert result["unresolved_disagreement_count"] == 0
    assert (
        result["unresolved_disagreement_count_scope"]
        == "web_versus_earlier_facsimile_spot_checks_only"
    )
    modern = result["same_edition_lower_clauses"]
    assert modern["unresolved_source_conflict_count"] == 3
    assert modern["complete_printed_clause_acceptance_passed"] is False
    assert result["all_scoped_source_checks_passed"] is False
