"""New table locations and preserved conflicts, not a calibrated life degree."""

import hashlib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures/guolao-life-degree-facsimile-v1"


@pytest.mark.parametrize("image", [76, 77, 78, 79, 86, 87])
def test_selected_primary_image_bytes_match_frozen_attributed_sources(image):
    reference = json.loads((FIXTURE / "reference.json").read_text())
    entry = next(e for e in reference["images"] if e["image"] == image)
    assert (
        hashlib.sha256((FIXTURE / entry["source_file"]).read_bytes()).hexdigest()
        == entry["sha256"]
    )
    assert "東北大学附属図書館所蔵" in reference["credit"]
    assert reference["edition_id"] == "tohoku_luwei_10020000001141"


def test_two_preserved_readings_do_not_become_a_universal_offset_or_modern_degree():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert (
        reference["comparison"]["example1"]["same_column_target_numeric_text"] == "六"
    )
    assert (
        reference["comparison"]["example1"]["introductory_target_numeric_text"] == "五"
    )
    assert (
        reference["comparison"]["example2"]["same_column_target_numeric_text"] == "五"
    )
    assert (
        reference["comparison"]["example2"]["introductory_target_numeric_text"] == "四"
    )
    assert not reference["scope"]["full_360_cells_collated"]
    assert not reference["scope"]["numbering_policy_adjudicated"]
    assert not reference["scope"]["modern_epoch_mapping_calibrated"]
    assert not reference["scope"]["life_degree_accepted"]
    assert not reference["scope"]["native_life_degree_changed"]
