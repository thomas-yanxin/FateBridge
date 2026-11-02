"""Native source coverage and invalid-token regression, not classical acceptance."""

import json
import shutil

import pytest

from fatebridge.core.metaphysics.taiyi_source_alignment import count_source_assessment
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from scripts.audit_taiyi_native_columns import (
    CORPUS,
    MANIFEST_SHA,
    audit,
    source_readings,
)
from scripts.build_taiyi_source_alignment import source_data


def test_native_source_keeps_all_fields_and_all_disagreements():
    result = audit()
    assert result["required_rows"] == 144
    assert result["selected_semantic_observations"] == 864
    positions, counts, generals = (
        result["groups"][key] for key in ("positions", "counts", "printed_generals")
    )
    assert (positions["observations"], positions["matching"]) == (576, 573)
    assert [(r["id"], r["field"]) for r in positions["differences"]] == [
        ("yin-37", "shiji"),
        ("yin-43", "shiji"),
        ("yin-44", "shiji"),
    ]
    assert (counts["observations"], counts["matching"]) == (288, 277)
    assert len(counts["differences"]) == 11
    assert (generals["observations"], generals["matching"]) == (8, 8)
    assert len(result["unprinted_general_slots"]) == 568
    assert not result["general_values_inferred_from_counts"]
    assert not result["classical_acceptance_passed"]
    assert not result["glyph_adjudication_claimed"]
    assert not result["independent_human_expert_reviewed"]
    assert not result["blinded_reading"]
    assert result["new_dated_cases"] == 0


def test_initial_manual_errors_are_preserved_and_corrected_from_named_columns():
    result = source_readings()
    entries = result["corrections"]["entries"]
    assert [(r["id"], r["field"], r["initial"], r["selected"]) for r in entries] == [
        ("yang-57", "main_count", 12, 10),
        ("yang-60", "guest_count", 12, 13),
        ("yin-20", "guest_count", 16, 10),
        ("yin-70", "main_count", 32, 22),
    ]
    assert result["corrections"]["initial_reading_preserved"]
    assert not result["corrections"]["old_source_values_changed"]
    first = json.loads((CORPUS / "first-comparison.json").read_text())
    assert len(first["differences"]) == 4 and not first["corrections_applied"]


def test_every_returned_source_column_has_its_frozen_native_location():
    native = source_readings()
    catalog = {r["id"]: r for r in source_data()["rows"]}
    for row in native["rows"]:
        prior = catalog[row["id"]]
        assert prior["positions"] == row["positions"]
        assert prior["table_counts"] == row["table_counts"]
        result = count_source_assessment(cyclic_core(row["ju"], yin=row["yin"]))
        assert result["ruleset"]["facsimile_collation_manifest_sha256"] == MANIFEST_SHA
        assert result["facsimile_page"] == row["page"]
        assert result["facsimile_columns_from_right"] == row["columns_from_right"]
        assert all(
            p["source_layer"]
            in {"selected_facsimile", "primary_facsimile_semantic_collation"}
            for p in result["positions"]
        )
        assert all(
            p["source_layer"] == "primary_facsimile_semantic_collation"
            for p in result["counts"]
        )
        assert "字形" in result["scope"]
    # Caller-owned location arrays cannot corrupt the next run's source.
    result["facsimile_columns_from_right"].append(99)
    again = count_source_assessment(cyclic_core(72, yin=True))
    assert again["facsimile_columns_from_right"] == [7]


@pytest.mark.parametrize("field", ["wenchang_palace", "shiji", "jishen"])
@pytest.mark.parametrize("value", ["", "子丑"])
def test_empty_and_multiple_positions_are_unassessed(field, value):
    result = count_source_assessment({**cyclic_core(1), field: value})
    assert result["status"] == "not_assessed"
    assert result["positions"] == result["counts"] == result["facsimile_readings"] == []


@pytest.mark.parametrize(
    "field,positions",
    [
        ("wenchang_palace", "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"),
        ("shiji", "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"),
        ("jishen", "子丑寅卯辰巳午未申酉戌亥"),
    ],
)
def test_legitimate_single_positions_are_not_rejected_or_regenerated(field, positions):
    for position in positions:
        result = count_source_assessment({**cyclic_core(1), field: position})
        assert result["status"] == "assessed_selected_table_columns"
        assert (
            next(p for p in result["positions"] if p["field"] == field)["actual_value"]
            == position
        )


@pytest.mark.parametrize(
    "name",
    [
        "native-columns.tsv",
        "reading-corrections.json",
        "cadal-native-page121.png",
        "manifest.json",
    ],
)
def test_changed_oracle_or_source_image_is_rejected(tmp_path, name):
    corpus = tmp_path / "source"
    shutil.copytree(CORPUS, corpus)
    with (corpus / name).open("ab") as f:
        f.write(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        source_readings(corpus)
