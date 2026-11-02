"""Complete printed star coverage cannot be replaced by a passing exception list."""

import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation import fengshui_lower_diagrams as audit

FOLDER = Path(__file__).parent / "fixtures/fengshui_lower_diagrams_v1"


def source():
    return audit.load_lower_diagram_reference(FOLDER)


def test_all_5832_printed_numerals_keep_the_one_difference():
    result = audit.audit_lower_diagrams(source())
    assert (result["printed_charts_checked"], result["printed_charts_matched"]) == (
        216,
        215,
    )
    assert (result["printed_numerals_checked"], result["printed_numerals_matched"]) == (
        5832,
        5831,
    )
    assert result["differences"] == [
        dict(
            period=7,
            sitting_mountain="申",
            facing_mountain="寅",
            pdf_page=353,
            direction="E",
            role="mountain",
            printed=5,
            engine=2,
            glyph_id=2358,
        )
    ]
    assert result["engine_permutation_failures"] == []
    assert result["source_center_label_differences"] == []
    assert result["source_permutation_failures"] == [
        dict(
            period=7,
            facing_mountain="寅",
            role="mountain",
            values=[3, 8, 1, 5, 4, 6, 7, 9, 5],
        )
    ]
    assert result["all_216_diagrams_transcribed"] is True
    for key in (
        "literal_diagram_numeric_acceptance_passed",
        "complete_diagram_acceptance_passed",
        "source_corrected_to_match_engine",
        "source_exception_allowlist_used",
        "independent_human_expert_review_complete",
        "whole_book_conformity_established",
        "calendar_selection_verified",
        "empirical_predictive_validity_established",
        "authority_certified",
    ):
        assert result[key] is False


def test_source_was_frozen_before_comparison_and_keeps_old_print_five():
    assert (
        hashlib.sha256((FOLDER / "reference.json").read_bytes()).hexdigest()
        == "44488715143b6e6aebcfe8ae638397ced12ed07dfee392cce81440a43c8de483"
    )
    data = source()
    assert data["reference"]["source_only_before_v24_engine_comparison"] is True
    assert data["reference"]["unresolved_numerals"] == 0
    notes = data["anomaly_pixel_review"]
    assert notes["printed_value"] == notes["historical_source"]["printed_value"] == 5
    assert notes["historical_source"]["exact_imprint_authenticated"] is False
    assert notes["historical_spot_selected_after_first_engine_comparison"] is True
    assert notes["source_numeral_changed_to_fit_engine"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "remove_chart",
        "duplicate_chart",
        "remove_palace",
        "remove_role",
        "unknown",
        "boolean",
    ],
)
def test_every_chart_palace_and_explicit_numeral_is_required(mutation):
    data = source()
    rows = data["reference"]["rows"]
    if mutation == "remove_chart":
        rows.pop()
    elif mutation == "duplicate_chart":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "remove_palace":
        rows[0]["palaces"].pop("E")
    elif mutation == "remove_role":
        rows[0]["palaces"]["E"].pop("mountain")
    elif mutation == "unknown":
        rows[0]["palaces"]["E"]["mountain"] = None
    else:
        rows[0]["palaces"]["E"]["mountain"] = True
    with pytest.raises(ValueError, match="216 distinct|All nine|All 27"):
        audit.audit_lower_diagrams(data)


def test_corrupting_the_engine_to_match_the_print_cannot_clear_the_gate(monkeypatch):
    real = audit.xuankong_natal

    def altered(request):
        result = deepcopy(real(request))
        chart = result["chart"]
        if chart["period_number"] == 7 and chart["facing"]["name"] == "寅":
            chart["palaces"]["E"]["mountain_star_number"] = 5
        return result

    monkeypatch.setattr(audit, "xuankong_natal", altered)
    result = audit.audit_lower_diagrams(source())
    assert result["printed_numerals_matched"] == 5832
    assert result["literal_diagram_numeric_acceptance_passed"] is True
    assert len(result["engine_permutation_failures"]) == 1
    assert len(result["source_permutation_failures"]) == 1
    assert result["complete_diagram_acceptance_passed"] is False


def test_regression_outside_the_known_dispute_is_not_allowlisted(monkeypatch):
    real = audit.xuankong_natal

    def altered(request):
        result = deepcopy(real(request))
        chart = result["chart"]
        if chart["period_number"] == 1 and chart["facing"]["name"] == "午":
            chart["palaces"]["SE"]["mountain_star_number"] = 1
        return result

    monkeypatch.setattr(audit, "xuankong_natal", altered)
    result = audit.audit_lower_diagrams(source())
    assert result["printed_charts_matched"] == 214
    assert result["printed_numerals_matched"] == 5830
    assert len(result["differences"]) == 2
    assert result["complete_diagram_acceptance_passed"] is False


def test_audit_is_read_only_and_derives_coverage_from_the_complete_data():
    data = source()
    data["reference"]["numeral_count"] = 99999
    data["reference"]["whole_book_conformity_established"] = True
    original = deepcopy(data)
    result = audit.audit_lower_diagrams(data)
    assert data == original
    assert result["printed_numerals_checked"] == 5832
    assert result["whole_book_conformity_established"] is False


@pytest.mark.parametrize(
    "name", ["reference.json", "native-images/申-寅-7.png", "historical-page-57.png"]
)
def test_changed_source_capture_is_rejected(tmp_path, name):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    with (folder / name).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="pre-engine freeze|source capture changed"):
        audit.load_lower_diagram_reference(folder)


def test_rehashing_a_source_correction_cannot_replace_the_frozen_five(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    data = json.loads((folder / "reference.json").read_text())
    row = next(
        r for r in data["rows"] if r["period"] == 7 and r["facing_mountain"] == "寅"
    )
    row["palaces"]["E"]["mountain"] = 2
    (folder / "reference.json").write_text(json.dumps(data))
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest["reference.json"] = hashlib.sha256(
        (folder / "reference.json").read_bytes()
    ).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pre-engine freeze"):
        audit.load_lower_diagram_reference(folder)


def test_capture_manifest_cannot_omit_the_disagreeing_diagram(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest.pop("native-images/申-寅-7.png")
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Incomplete"):
        audit.load_lower_diagram_reference(folder)


def test_source_command_retains_both_complete_prose_and_diagram_failures(tmp_path):
    output = tmp_path / "source-audit.json"
    process = subprocess.run(
        [sys.executable, "scripts/audit_fengshui_sources.py", "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 1, process.stderr
    result = json.loads(output.read_text())
    assert result["same_edition_lower_clauses"]["unresolved_source_conflict_count"] == 3
    full = result["complete_lower_diagrams"]
    assert full["printed_numerals_checked"] == 5832
    assert full["printed_numerals_matched"] == 5831
    assert full["complete_diagram_acceptance_passed"] is False
    assert result["all_scoped_source_checks_passed"] is False
