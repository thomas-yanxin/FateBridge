"""Hand-built Unicode rows and collisions, never historical prediction scores."""

import hashlib

import pytest

from fatebridge.validation.gauquelin_linkage import (
    _link_index,
    _parse_corrections,
    _parse_ertel,
    audit_cfepp_linkage,
)


def row(erid, cfid="", *, name="Fictional", source="G:A01", gnr="17", cp=""):
    line = list(" " * 270)
    for start, width, value in (
        (0, 6, source),
        (7, 6, str(erid)),
        (13, 19, name),
        (144, 4, gnr),
        (149, 5, cp),
        (157, 6, str(cfid)),
    ):
        assert len(value) <= width
        line[start : start + width] = value.ljust(width)
    return "".join(line) + "\r\n"


def source(*rows):
    return "header\n" * 6 + "".join(rows) + " \n\n.close\n"


def test_unicode_uses_character_columns_and_preserves_source_line_bytes():
    original = row(1, 96, name="Épreuve-虚构", cp="12")
    parsed = _parse_ertel(source("\n", original))
    assert len(parsed) == 1
    assert parsed[0] == {
        "ertel_id": 1,
        "source_line": 8,
        "source_line_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "literal_cfepp_field": "96",
        "raw_cfepp_id": 96,
        "raw_gauquelin_source": "G:A01",
        "raw_gauquelin_number": 17,
        "raw_comite_para_id": "12",
        "comite_para_subset": "published_535",
        "comite_para_number": 12,
    }


def test_raw_collisions_and_out_of_range_ids_cannot_be_silently_overwritten():
    parsed = _parse_ertel(source(row(1, 96), row(2, 96), row(3, 1921), row(4)))
    index, summary = _link_index(parsed, {})
    assert [r["ertel_id"] for r in index[96]] == [1, 2]
    assert summary == {
        "linked_ertel_rows": 3,
        "unlinked_ertel_rows": 1,
        "distinct_referenced_cfepp_ids": 2,
        "collisions": [{"cfepp_id": 96, "ertel_ids": [1, 2]}],
        "out_of_range": [{"cfepp_id": 1921, "ertel_ids": [3]}],
    }
    revised, changed = _link_index(parsed, {2: 768, 3: 1021, 4: 1120})
    assert set(revised) == {96, 768, 1021, 1120}
    assert changed["collisions"] == changed["out_of_range"] == []
    # Applying a declared correction never rewrites the original evidence.
    assert parsed[1]["raw_cfepp_id"] == 96
    assert parsed[2]["raw_cfepp_id"] == 1921
    assert parsed[3]["raw_cfepp_id"] is None


def test_zero_missing_cross_id_is_unknown_not_a_new_person():
    parsed = _parse_ertel(source(row(1, "0", source="GMIND", gnr="", cp="0")))
    assert parsed[0]["raw_cfepp_id"] is None
    assert parsed[0]["literal_cfepp_field"] == "0"
    assert parsed[0]["raw_gauquelin_number"] is None
    assert parsed[0]["raw_comite_para_id"] == "0"
    assert parsed[0]["comite_para_subset"] is None
    assert _link_index(parsed, {})[1]["unlinked_ertel_rows"] == 1


def test_starred_para_pool_stays_distinct_from_same_number_in_published_sample():
    parsed = _parse_ertel(source(row(1, cp="26"), row(2, cp="* 26")))
    assert [r["raw_comite_para_id"] for r in parsed] == ["26", "* 26"]
    assert [r["comite_para_number"] for r in parsed] == [26, 26]
    assert [r["comite_para_subset"] for r in parsed] == [
        "published_535",
        "unpublished_lowers_76",
    ]


@pytest.mark.parametrize(
    "text,error",
    [
        (source(row(1), row(1)), "missing_or_duplicate_ertel_id"),
        (source(row(0)), "missing_or_duplicate_ertel_id"),
        (source(row(1, "???")), "invalid_source_cross_id"),
        (source("short\n"), "truncated_ertel_source_row"),
    ],
)
def test_malformed_rows_are_errors_not_dropped_from_the_cohort(text, error):
    with pytest.raises(ValueError, match=error):
        _parse_ertel(text)


def test_only_active_literal_corrections_are_read_without_running_php():
    text = """<?php
    const ERTEL_CFEPP = [
        // 3619 => 218, // a possible identity confusion, not an active correction
        2 => 790,
        255 => 1106,
    ];
    exit('this program must never execute');
    """
    assert _parse_corrections(text) == {2: 790, 255: 1106}


@pytest.mark.parametrize("entries", ["1 => 2,\n1 => 3,", "1 => 1121,", "0 => 2,"])
def test_invalid_corrections_cannot_overwrite_a_previous_entry(entries):
    with pytest.raises(ValueError, match="invalid_or_duplicate_linkage_correction"):
        _parse_corrections("const ERTEL_CFEPP = [\n" + entries + "\n];")


def test_public_audit_rejects_unpinned_sources_before_any_linkage():
    with pytest.raises(ValueError, match="pinned_ertel_source_hash_mismatch"):
        audit_cfepp_linkage(b"", source(row(1)).encode(), b"", b"")
