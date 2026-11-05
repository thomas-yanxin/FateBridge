"""All five original years and their integrity failures remain in acceptance."""

import hashlib
import json
import shutil
from copy import deepcopy

import pytest

import scripts.sukuyo.check_suzhan_lunar_phase as checker

INDEX = json.loads(checker.INDEX.read_bytes())
NEW_ROWS = [
    row
    for source in INDEX["annual_responses"]
    if source["format"] == "annual_tool_extracted_json"
    for row in json.loads((checker.INDEX.parent / source["fixture"]).read_bytes())[
        "phasedata"
    ]
]


@pytest.mark.parametrize("row", NEW_ROWS)
def test_every_newly_obtained_phase_against_unchanged_original_tolerance(row):
    checked = checker.compare_row(row)
    assert checked["absolute_wrapped_elongation_residual_degrees"] <= 0.01


def test_full_original_five_year_gate_checks_all_248_rows():
    result = checker.compare_frozen_years()
    assert result["required_years"] == [1700, 1900, 2000, 2026, 2100]
    assert result["obtained_years"] == result["required_years"]
    assert result["missing_years"] == []
    assert result["uniform_tolerance_degrees"] == 0.01
    assert result["all_available_rows_checked"] == 248
    assert result["full_frozen_five_year_gate_met"]
    assert result["all_extracted_source_bytes_and_complete_annual_rows_checked"]
    assert {s["year"]: s["all_rows_checked"] for s in result["annual_sources"]} == {
        1700: 49,
        1900: 50,
        2000: 49,
        2026: 50,
        2100: 50,
    }
    assert not result["strict_holdout"]
    assert result["real_astrological_samples"] == 0
    assert not result["ancient_day_boundary_or_rule_priority_established"]


@pytest.fixture
def copied_archive(tmp_path):
    folder = tmp_path / "archive"
    shutil.copytree(checker.INDEX.parent, folder)
    shutil.copyfile(checker.FIXTURE, tmp_path / checker.FIXTURE.name)
    return folder / "index.json"


def write_index(path, data):
    path.write_text(json.dumps(data))


def test_removing_one_year_does_not_turn_the_other_years_into_full_acceptance(
    copied_archive,
):
    index = json.loads(copied_archive.read_bytes())
    index["annual_responses"] = [
        r for r in index["annual_responses"] if r["year"] != 1700
    ]
    write_index(copied_archive, index)
    report = checker.compare_frozen_years(copied_archive)
    assert report["missing_years"] == [1700]
    assert report["all_available_rows_checked"] == 199
    assert report["available_rows_within_tolerance"]
    assert not report["full_frozen_five_year_gate_met"]


def test_empty_source_index_does_not_pass_vacuously(copied_archive):
    index = json.loads(copied_archive.read_bytes())
    index["annual_responses"] = []
    write_index(copied_archive, index)
    result = checker.compare_frozen_years(copied_archive)
    assert result["all_available_rows_checked"] == 0
    assert not result["available_rows_within_tolerance"]
    assert not result["full_frozen_five_year_gate_met"]


def test_duplicate_annual_source_is_not_an_additional_year(copied_archive):
    index = json.loads(copied_archive.read_bytes())
    index["annual_responses"].append(deepcopy(index["annual_responses"][0]))
    write_index(copied_archive, index)
    with pytest.raises(ValueError, match="duplicated"):
        checker.compare_frozen_years(copied_archive)


@pytest.mark.parametrize("mutation", ["required_years", "tolerance"])
def test_legacy_fixture_cannot_change_the_original_acceptance_standard(
    monkeypatch, tmp_path, mutation
):
    data = json.loads(checker.FIXTURE.read_bytes())
    if mutation == "required_years":
        data["comparison_protocol"]["source_years"] = [2026]
    else:
        data["comparison_protocol"][
            "uniform_absolute_wrapped_elongation_residual_tolerance_degrees"
        ] = 100
    target = tmp_path / "changed-standard.json"
    target.write_text(json.dumps(data))
    monkeypatch.setattr(checker, "FIXTURE", target)
    with pytest.raises(ValueError, match="original frozen standard"):
        checker.compare_available()


@pytest.mark.parametrize("mutation", ["required_years", "tolerance", "declared_digest"])
def test_complete_index_cannot_change_the_original_acceptance_standard(
    copied_archive, mutation
):
    index = json.loads(copied_archive.read_bytes())
    if mutation == "required_years":
        index["comparison_protocol"]["source_years"] = [2026]
    elif mutation == "tolerance":
        index["comparison_protocol"][
            "uniform_absolute_wrapped_elongation_residual_tolerance_degrees"
        ] = 100
    else:
        index["original_protocol_bytes_sha256"] = "0" * 64
    write_index(copied_archive, index)
    with pytest.raises(ValueError, match="protocol"):
        checker.compare_frozen_years(copied_archive)


def test_actual_extracted_source_change_cannot_keep_old_identity(copied_archive):
    index = json.loads(copied_archive.read_bytes())
    path = copied_archive.parent / index["annual_responses"][0]["fixture"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source bytes changed"):
        checker.compare_frozen_years(copied_archive)


@pytest.mark.parametrize(
    "mutation", ["wrong_year", "missing_row", "duplicated_row", "wrong_phase_order"]
)
def test_structurally_incomplete_annual_table_is_rejected_even_after_rehash(
    copied_archive, mutation
):
    index = json.loads(copied_archive.read_bytes())
    record = index["annual_responses"][0]
    path = copied_archive.parent / record["fixture"]
    data = json.loads(path.read_bytes())
    if mutation == "wrong_year":
        data["phasedata"][0]["year"] = 1900
    elif mutation == "missing_row":
        data["phasedata"].pop()
        data["numphases"] -= 1
    elif mutation == "duplicated_row":
        data["phasedata"][1] = deepcopy(data["phasedata"][0])
    else:
        data["phasedata"][1]["phase"] = "First Quarter"
    raw = (json.dumps(data) + "\n").encode()
    path.write_bytes(raw)
    record["extracted_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
    write_index(copied_archive, index)
    with pytest.raises(ValueError, match="USNO annual"):
        checker.compare_frozen_years(copied_archive)
