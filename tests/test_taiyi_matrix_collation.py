"""Source integrity and safeguards against turning column text into accuracy."""

import shutil

import pytest

from scripts.audit_taiyi_matrix_collation import (
    CORPUS,
    audit,
    literal_locations,
    source_data,
)


def test_source_index_does_not_resolve_six_differences_or_fill_blanks():
    report = audit()
    assert report["recorded_physical_columns"] == 32
    assert report["required_target_cells"] == 128
    assert report["adjudicated_ncl_cells"] == 0
    assert report["unadjudicated_ncl_cells"] == 128
    assert report["source_eye_fragments_indexed"] == 33
    differences = report["previously_reported_six_differences"]
    assert {r["siku_cell_id"] for r in differences} == {
        "酉-3",
        "子-4",
        "丑-7",
        "巳-2",
        "午-8",
        "坤-6",
    }
    for row in differences:
        assert row["literal_occurrences_in_ncl_half_column"]
        assert row["ncl_palace_assignment"] == "not_adjudicated"
        assert row["cell_conflict_resolved"] is False
        assert row["literal_occurrence_counts_as_geometry_match"] is False
    assert len(report["siku_blank_columns_retained"]) == 4
    assert len(report["siku_lacunae_retained"]) == 1
    assert all(not row["blank_filled"] for row in report["siku_blank_columns_retained"])
    assert all(not row["lacuna_filled"] for row in report["siku_lacunae_retained"])
    assert report["copied_text_counted_as_calculated_hits"] == 0
    assert report["new_geometric_matches_claimed"] == 0
    assert report["matrix_128_cells_accepted"] is False
    assert report["whole_classic_acceptance_passed"] is False
    assert report["transcription_attribution"]["transcriber"] == "Codex agent"
    assert not report["transcription_attribution"][
        "new_independent_human_review_claimed"
    ]


def test_repeated_text_in_parallel_strands_keeps_both_locations_without_palaces():
    data = source_data()
    column = next(c for c in data["columns"]["columns"] if c["id"] == "巳-second")
    found = literal_locations(column, "門具將發")
    assert len(found) == 2
    assert [r["strand_from_right"] for r in found] == [1, 2]
    assert all(r["group_from_top"] == 2 for r in found)
    assert all("taiyi_number" not in r for r in found)
    assert literal_locations(column, "天目內迫") == []


@pytest.mark.parametrize(
    "name",
    [
        "manifest.json",
        "physical-columns.json",
        "same-edition-names.json",
        "source-metadata.json",
        "ncl-page34.png",
        "ncl-page52.png",
        "ncl-page54.png",
        "metadata-correction.json",
        "correction-manifest.json",
    ],
)
def test_frozen_images_readings_and_correction_cannot_be_replaced(tmp_path, name):
    copied = tmp_path / "corpus"
    shutil.copytree(CORPUS, copied)
    (copied / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_data(copied)
