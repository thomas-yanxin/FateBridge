"""Complete replacement source evidence must retain all three literal conflicts."""

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation import fengshui_replacement_diagrams as audit

FOLDER = Path(__file__).parents[1] / "data/fengshui_replacement_diagrams_v1"


@pytest.fixture(scope="module")
def frozen():
    return audit.load_replacement_diagram_reference(FOLDER)


def test_all_216_replacement_diagrams_keep_three_literal_differences(frozen):
    result = audit.audit_replacement_diagrams(frozen)
    assert (result["printed_charts_checked"], result["printed_charts_matched"]) == (
        216,
        214,
    )
    assert (result["printed_numerals_checked"], result["printed_numerals_matched"]) == (
        5832,
        5829,
    )
    assert [
        (
            r["pdf_page"],
            r["direction"],
            r["role"],
            r["printed"],
            r["engine"],
            r["glyph_id"],
        )
        for r in result["differences"]
    ] == [
        (515, "S", "mountain", 9, 6, 111),
        (582, "S", "mountain", 7, 1, 1920),
        (582, "S", "facing", 1, 7, 1921),
    ]
    assert [
        (r["pdf_page"], r["role"]) for r in result["source_permutation_failures"]
    ] == [
        (515, "mountain"),
        (582, "mountain"),
        (582, "facing"),
    ]
    assert result["source_center_label_differences"] == []
    assert result["engine_permutation_failures"] == []
    assert result["engine_representation_failures"] == []
    assert result["all_216_diagrams_transcribed"] is True
    for key in (
        "literal_diagram_numeric_acceptance_passed",
        "complete_diagram_acceptance_passed",
        "source_corrected_to_match_engine",
        "source_exception_allowlist_used",
        "independent_human_expert_review_complete",
        "star_name_labels_and_prose_verified",
        "source_angle_applicability_verified",
        "whole_book_conformity_established",
        "calendar_selection_verified",
        "empirical_predictive_validity_established",
        "authority_certified",
    ):
        assert result[key] is False


def test_source_freeze_precedes_comparison_and_retains_review_errors(frozen):
    raw = (FOLDER / "reference.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == audit.REFERENCE_SHA256
    ref = frozen["reference"]
    assert ref["source_reference_frozen_before_first_engine_comparison"] is True
    assert ref["engine_outputs_used_to_transcribe"] is False
    assert ref["flight_math_used_to_fill_digits"] is False
    assert ref["independent_human_expert_review"] is False
    initial = json.loads(
        (FOLDER / "manual-source-sheets-before-pixel-recheck.json").read_text()
    )
    corrected = json.loads((FOLDER / "manual-source-sheets.json").read_text())
    initial_values = [
        c for s in initial["sheets"] for r in s["rows"] for c in r.replace(" ", "")
    ]
    corrected_values = [
        c for s in corrected["sheets"] for r in s["rows"] for c in r.replace(" ", "")
    ]
    assert len(initial_values) == len(corrected_values) == 1215
    assert sum(a != b for a, b in zip(initial_values, corrected_values)) == 15
    assert "申听禅" in ref["author_attribution"]


@pytest.mark.parametrize(
    "mutation",
    [
        "remove",
        "duplicate",
        "wrong_sitting",
        "page",
        "palace",
        "role",
        "unknown",
        "bool",
    ],
)
def test_all_literal_source_slots_and_identities_are_required(frozen, mutation):
    data = deepcopy(frozen)
    rows = data["reference"]["rows"]
    if mutation == "remove":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "wrong_sitting":
        rows[0]["sitting_mountain"] = "亥"
    elif mutation == "page":
        rows[0]["pdf_page"] = 512
    elif mutation == "palace":
        rows[0]["palaces"].pop("SE")
    elif mutation == "role":
        rows[0]["palaces"]["SE"].pop("mountain")
    else:
        rows[0]["palaces"]["SE"]["mountain"] = None if mutation == "unknown" else True
    with pytest.raises(
        ValueError, match="216 distinct|identity|nine printed|27 explicit"
    ):
        audit.audit_replacement_diagrams(data)


def test_copying_all_printed_errors_cannot_clear_acceptance(frozen, monkeypatch):
    real = audit._chart
    by_key = {
        (r["period"], r["facing_mountain"]): r for r in frozen["reference"]["rows"]
    }

    def copy_print(period, selector):
        chart = real(period, selector)
        row = by_key[(period, chart["facing"]["name"])]
        for d in audit.DIRECTIONS:
            for role in audit.ROLES:
                value = row["palaces"][d][role]
                chart["palaces"][d][role + "_star_number"] = value
                chart[role + "_chart"][d] = value
        return chart

    monkeypatch.setattr(audit, "_chart", copy_print)
    result = audit.audit_replacement_diagrams(frozen)
    assert result["printed_numerals_matched"] == 5832
    assert result["literal_diagram_numeric_acceptance_passed"] is True
    assert len(result["engine_permutation_failures"]) == 3
    assert len(result["source_permutation_failures"]) == 3
    assert result["complete_diagram_acceptance_passed"] is False


def test_new_permutation_error_outside_disputes_is_not_allowlisted(frozen, monkeypatch):
    real = audit._chart

    def swap(period, selector):
        chart = real(period, selector)
        if period == 1 and chart["facing"]["name"] == "午":
            a, b = chart["mountain_chart"]["E"], chart["mountain_chart"]["W"]
            for direction, value in (("E", b), ("W", a)):
                chart["mountain_chart"][direction] = value
                chart["palaces"][direction]["mountain_star_number"] = value
        return chart

    monkeypatch.setattr(audit, "_chart", swap)
    result = audit.audit_replacement_diagrams(frozen)
    assert len(result["differences"]) == 5
    assert result["engine_permutation_failures"] == []
    assert result["complete_diagram_acceptance_passed"] is False


def test_declared_mode_is_not_a_fabricated_source_angle(frozen, monkeypatch):
    real = audit._chart
    calls = []

    def observed(period, selector):
        calls.append((period, selector))
        return real(period, selector)

    monkeypatch.setattr(audit, "_chart", observed)
    audit.audit_replacement_diagrams(frozen)
    assert {(p, s[0]) for p, s in calls} == {
        (p, i) for p in range(1, 10) for i in range(24)
    }
    assert all(s[1] == "replacement" for _, s in calls)
    assert all("no angle applicability" in s[2] for _, s in calls)


@pytest.mark.parametrize(
    "name", ["reference.json", "native-images/子-午-5.jpeg", "ocr-native.json"]
)
def test_changed_original_or_proposal_is_rejected(tmp_path, name):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    with (folder / name).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(
        ValueError, match="pre-engine freeze|capture or review record changed"
    ):
        audit.load_replacement_diagram_reference(folder)


def test_rehashing_cannot_omit_a_disagreeing_source_image(tmp_path):
    folder = tmp_path / "source"
    shutil.copytree(FOLDER, folder)
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest.pop("native-images/坤-艮-9.jpeg")
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest changed"):
        audit.load_replacement_diagram_reference(folder)


def test_claimed_totals_and_awards_cannot_change_actual_coverage(frozen):
    data = deepcopy(frozen)
    data["reference"].update(numerals=99999, whole_book_conformity_established=True)
    unchanged = deepcopy(data)
    result = audit.audit_replacement_diagrams(data)
    assert data == unchanged
    assert result["printed_numerals_checked"] == 5832
    assert result["whole_book_conformity_established"] is False
