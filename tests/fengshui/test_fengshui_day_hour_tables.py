"""Printed source positions constrain both the arithmetic and its coverage."""

import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.fengshui.xuankong import _fly
from fatebridge.validation import fengshui_day_hour as audit

FOLDER = Path(__file__).parents[1] / "data/fengshui_day_hour_tables_v1"


def reference():
    return audit.load_day_hour_reference(FOLDER)


def test_complete_printed_tables_and_source_scope():
    result = audit.audit_day_hour_reference(reference())
    assert result["daily_confirmed_table_cycle_cases"] == 1080
    assert result["hour_confirmed_day_group_cases"] == 72
    assert result["palace_relations_checked"] == 10368
    assert result["differences"] == []
    assert result["table_arithmetic_and_shared_flight_conform"] is True
    countermodels = result["countermodels"]
    assert countermodels["ignore_inverted_tail_mismatching_charts"] == 32
    assert countermodels["always_forward_daily_mismatching_charts"] == 540
    assert countermodels["always_forward_hourly_mismatching_charts"] == 36
    assert (
        countermodels["flip_spatial_flight_in_inverted_tail_mismatching_charts"] == 36
    )
    for key in (
        "calendar_table_selection_verified",
        "day_hour_boundary_policy_verified",
        "new_public_daily_or_hourly_tool",
        "whole_book_conformity_established",
        "independent_human_expert_review",
        "real_world_prediction_established",
        "included_in_complete_calendar_acceptance",
    ):
        assert result[key] is False


def test_transcription_was_fixed_before_arithmetic_probe():
    assert hashlib.sha256((FOLDER / "reference.json").read_bytes()).hexdigest() == (
        "968fa587634e1f53a657142622b4b4dada3c10d65e0d1043caa4028fe3f01a32"
    )
    assert reference()["source"]["full_pdf_sha256"] == (
        "b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847"
    )


def test_literal_inverted_branch_controls_the_third_cycle_only():
    table = next(t for t in reference()["daily_tables"] if t["id"] == "middle_yang")
    cell = next(t for t in table["inverted_cells"] if t["ganzhi"] == "戊午")
    assert (cell["row"], cell["column"]) == (5, 8)
    # Printed middle-yang third column: 戊午 is underneath 丁巳, not its
    # ordinary row-6/column-0 position. The extremal nine repeats first.
    assert table["palace_rows"][8][cell["column"]] == "中"
    assert table["star_columns"][2][8] == 9
    assert table["star_columns"][2][0] == 1
    result = audit.audit_day_hour_reference(reference())
    case = next(
        row
        for row in result["countermodels"]["examples"]
        if row["table"] == "middle_yang" and row["ganzhi"] == "戊午"
    )
    assert case["cycle"] == 2
    assert case["printed_center"] == 9
    assert case["ignoring_inverted_tail_center"] == 1


def test_hour_table_keeps_inverse_spatial_flight_and_literal_group_names():
    hour = reference()["hour_table"]
    assert hour["title"] == "三元时紫白顺逆合局表"
    assert hour["intro_page"] == 856
    assert hour["groups"][0]["printed_day_branches"] == "子午卯酉"
    assert hour["groups"][0]["printed_label"] == "四孟"
    assert hour["groups"][1]["printed_day_branches"] == "丑未辰戌"
    assert hour["groups"][1]["printed_label"] == "四仲"
    # First row is 子/酉 for the first group. The inverse header puts eight
    # at 乾 while nine is in the center; annual/monthly forward flight differs.
    assert hour["groups"][0]["hour_rows"][0] == "子酉"
    assert hour["palace_rows"][0][:2] == "中乾"
    assert hour["star_columns"]["yin"][:2] == [9, 8]
    assert _fly(9, False)["NW"] == 8
    assert _fly(9, True)["NW"] == 1


def test_pure_collation_never_mutates_literal_capture():
    data = reference()
    original = deepcopy(data)
    audit.audit_day_hour_reference(data)
    assert data == original


@pytest.mark.parametrize("file", ["reference.json", "page-849.png", "page-857.png"])
def test_changed_source_bytes_are_rejected(tmp_path, file):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    with (folder / file).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="source capture changed"):
        audit.load_day_hour_reference(folder)


def test_incomplete_capture_manifest_cannot_reduce_scope(tmp_path):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    hashes = json.loads((folder / "hashes.json").read_text())
    hashes.pop("page-856.png")
    (folder / "hashes.json").write_text(json.dumps(hashes))
    with pytest.raises(ValueError, match="Incomplete"):
        audit.load_day_hour_reference(folder)


def test_hashes_do_not_make_a_nonobject_reference_valid(tmp_path):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    (folder / "reference.json").write_text("[]\n")
    hashes = json.loads((folder / "hashes.json").read_text())
    hashes["reference.json"] = hashlib.sha256(
        (folder / "reference.json").read_bytes()
    ).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(hashes))
    with pytest.raises(ValueError, match="JSON object"):
        audit.load_day_hour_reference(folder)


@pytest.mark.parametrize("change", ["table", "cycle", "day", "tail", "star", "row"])
def test_no_missing_or_invalid_cells_are_treated_as_passing(change):
    data = reference()
    if change == "table":
        data["daily_tables"].pop()
    elif change == "cycle":
        data["daily_tables"][0]["star_columns"].pop()
    elif change == "day":
        data["normal_ganzhi_rows"][0].pop()
    elif change == "tail":
        data["daily_tables"][2]["inverted_cells"].pop()
    elif change == "star":
        data["daily_tables"][0]["star_columns"][0][0] = True
    else:
        data["daily_tables"][2]["inverted_cells"][0]["row"] = 4
    with pytest.raises(ValueError):
        audit.audit_day_hour_reference(data)


def test_wrong_but_well_formed_palace_row_is_a_disagreement():
    data = reference()
    row = list(data["daily_tables"][0]["palace_rows"][0])
    row[1], row[2] = row[2], row[1]
    data["daily_tables"][0]["palace_rows"][0] = "".join(row)
    result = audit.audit_day_hour_reference(data)
    assert result["differences"]
    assert result["table_arithmetic_and_shared_flight_conform"] is False


def test_prose_endpoint_cannot_be_ignored():
    data = reference()
    data["daily_tables"][2]["last_ordinary_star"] = 8
    result = audit.audit_day_hour_reference(data)
    assert any(row.get("kind") == "prose_end_mismatch" for row in result["differences"])
    assert result["table_arithmetic_and_shared_flight_conform"] is False


def test_prose_join_does_not_disappear_when_the_matrix_matches():
    data = reference()
    data["daily_tables"][2]["following_anchor_star"] = 9
    result = audit.audit_day_hour_reference(data)
    assert any(
        row.get("kind") == "prose_join_mismatch" for row in result["differences"]
    )
    assert result["table_arithmetic_and_shared_flight_conform"] is False


def test_bad_flight_implementation_is_detected(monkeypatch):
    original = audit._fly
    monkeypatch.setattr(audit, "_fly", lambda center, yang=True: original(center, True))
    result = audit.audit_day_hour_reference(reference())
    assert len(result["differences"]) == 576
    assert result["table_arithmetic_and_shared_flight_conform"] is False
    assert result["calendar_table_selection_verified"] is False


def test_reference_cannot_award_itself_full_algorithm_coverage():
    data = reference()
    data["not_implemented_or_certified"] = {}
    data["whole_book_conformity_established"] = True
    result = audit.audit_day_hour_reference(data)
    assert result["table_arithmetic_and_shared_flight_conform"] is True
    assert result["whole_book_conformity_established"] is False
    assert result["calendar_table_selection_verified"] is False
    assert result["real_world_prediction_established"] is False


def test_full_source_audit_retains_its_original_nonzero_gate(tmp_path):
    output = tmp_path / "audit.json"
    root = Path(__file__).parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/fengshui/audit_fengshui_sources.py",
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1, completed.stderr
    result = json.loads(output.read_text())
    assert result["counts"]["xuankong"] == {"checked": 216, "matched": 213}
    assert len(result["disagreements"]) == 3
    assert result["all_scoped_source_checks_passed"] is False
    assert result["day_hour_table_research"]["differences"] == []
    assert (
        result["day_hour_table_research"]["included_in_complete_calendar_acceptance"]
        is False
    )
    calendar = result["day_hour_calendar_selection_research"]
    assert calendar["independent_calendar_comparison_passed"] is True
    assert calendar["retained_full_windows"]["sufficient_for_unique_selection"] is False
    assert calendar["calendar_table_selection_verified"] is False
