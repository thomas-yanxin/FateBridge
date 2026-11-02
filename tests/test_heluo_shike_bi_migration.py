"""Frozen reference edges must reject altered facts and repeated migrations."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import yao_text
from tests.heluo_ben22_revision_reference import rebind_r96_metadata, rebind_r96_record
from tests.heluo_current_source_reference import advance_current_record
from tests.heluo_shike_bi_revision_reference import (
    CURRENT_COMMENTARIES,
    CURRENT_HEADERS,
    CURRENT_POEMS,
    R91,
    REVISION,
    F,
    assert_r92_source_addition,
    rebind_r92_business22,
    rebind_r92_counts,
    rebind_r92_metadata,
    rebind_r92_record,
    rebind_r92_render_row,
)

ROOT = Path(__file__).parents[1]
BEFORE = json.loads(
    gzip.decompress((R91 / "before-records384-delivery-receipt.json.gz").read_bytes())
)
TARGETS = sorted(REVISION["record_extensions"])


def test_reference_precedes_old_test_edits_and_does_not_create_accuracy_credit():
    freeze = json.loads((F / "reference-freeze.json").read_bytes())
    assert freeze["before_existing_test_or_auditor_edits"] is True
    for name, digest in freeze["files"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    assert REVISION["new_model_evaluations"] == REVISION["new_independent_readers"] == 0
    assert REVISION["authority_certified"] is False
    assert REVISION["other372record_bodies_and_all384verdicts_exact"] is True
    assert REVISION["all22mathematical_results_exact"] is True
    assert_r92_source_addition()


def test_every384_record_follows_the_declared_edge_without_new_verdicts():
    assert len(BEFORE) == 384 and len(TARGETS) == 12
    for key, old in BEFORE.items():
        gua, pos = key.rsplit(":", 1)
        expected = rebind_r92_record(rebind_r92_metadata(old), key)
        from tests.heluo_bo23_revision_reference import rebind_r101_record

        expected = rebind_r101_record(
            rebind_r96_record(rebind_r96_metadata(expected), key), key
        )
        expected = advance_current_record(expected, key)
        assert yao_text(gua, int(pos)) == expected
        assert expected["verdict"] == old["verdict"]


@pytest.mark.parametrize("key", TARGETS)
@pytest.mark.parametrize("kind", ["detail", "verdict", "repeated"])
def test_record_edge_cannot_rewrite_an_unbound_body_or_reapply(key, kind):
    before = rebind_r92_metadata(BEFORE[key])
    if kind == "detail":
        before["detail"] += "伪造"
    elif kind == "verdict":
        before["verdict"] = "伪造"
    else:
        before = rebind_r92_record(before, key)
    with pytest.raises(AssertionError):
        rebind_r92_record(before, key)


@pytest.mark.parametrize("parent", ["text_provenance", "provenance"])
def test_source_metadata_rejects_forged_or_repeated_values(parent):
    for key, (before, after) in REVISION[parent + "_pairs"].items():
        with pytest.raises(AssertionError):
            rebind_r92_metadata({key: "伪造"}, parent)
        assert rebind_r92_metadata({key: before}, parent) == {key: after}
        with pytest.raises(AssertionError):
            rebind_r92_metadata({key: after}, parent)


def test_each_source_object_and_count_edge_is_guarded_by_exact_old_value():
    for owner, pairs in REVISION["source_record_pairs"].items():
        for field, (old, new) in pairs.items():
            assert rebind_r92_metadata(
                {"key": owner, field: old}, "source_records"
            ) == {"key": owner, field: new}
            with pytest.raises(AssertionError):
                rebind_r92_metadata({"key": owner, field: "伪造"}, "source_records")
    for key, (old, new) in REVISION["coverage_field_pairs"].items():
        assert rebind_r92_counts({"coverage": {key: old}}) == {"coverage": {key: new}}
        for bad in [new, float(old), "伪造"]:
            with pytest.raises(AssertionError):
                rebind_r92_counts({"coverage": {key: bad}})


def test_metadata_like_keys_inside_literal_or_numeric_bodies_stay_literal():
    for field in ["detail", "reading_notes", "chart", "number"]:
        value = {
            field: {
                "provenance": {"source_catalogue_version": 8},
                "coverage": {"header_collated": 120},
            }
        }
        assert rebind_r92_metadata(value) == value
        assert rebind_r92_counts(value) == value


def test_metadata_never_substitutes_numbers_words_or_partial_body_lines():
    old, new = REVISION["exact_metadata_footer_pairs"][0]
    for name in ["detail", "reading_notes", "verdict", "number"]:
        value = {name: [old, 120, "14.0.0"]}
        assert rebind_r92_metadata(value) == value
        assert rebind_r92_counts({name: 120}) == {name: 120}
    assert rebind_r92_metadata({"snapshot_text": "prefix " + old}) == {
        "snapshot_text": "prefix " + old
    }
    assert rebind_r92_metadata({"snapshot_text": old}) == {"snapshot_text": new}


@pytest.mark.parametrize("key", TARGETS)
def test_render_edges_keep_geometry_and_reject_edited_or_repeated_rows(key):
    edge = REVISION["render_oracle_extensions"][key]
    assert rebind_r92_render_row(edge["before"]) == edge["after"]
    bad = copy.deepcopy(edge["before"])
    bad["lines"][0] = 1 - bad["lines"][0]
    with pytest.raises(AssertionError):
        rebind_r92_render_row(bad)
    with pytest.raises(AssertionError):
        rebind_r92_render_row(edge["after"])


@pytest.mark.parametrize("index", [0, 21])
@pytest.mark.parametrize("kind", ["number", "snapshot", "repeated"])
def test_full_business_edge_rejects_unreviewed_facts_and_snapshot_edits(index, kind):
    old = json.loads(
        (
            ROOT / f"tests/fixtures/heluo_reading_delivery_v1/before22/{index:02d}.json"
        ).read_bytes()
    )
    if kind == "number":
        old["chart"]["tian"] += 1
    elif kind == "snapshot":
        old["snapshot_text"] += "伪造"
    else:
        old = rebind_r92_business22(old, index)
    with pytest.raises(AssertionError):
        rebind_r92_business22(old, index)


def test_old_source_conflicts_and_calendar_gate_have_not_been_edited():
    assert (
        yao_text("天水訟", 3)["text_provenance"]["poem_heading_text"]
        == "訟卦三爻訣一首"
    )
    assert len(yao_text("天水訟", 3)["poem_sections"]) == 3
    assert "poem_review_supplement" in yao_text("天水訟", 1)
    assert (
        hashlib.sha256(
            (ROOT / "tests/fixtures/ren_calendar_guard_v1/reference.json").read_bytes()
        ).hexdigest()
        == "0ddfd96563464ac2f8a02961cb89c84c5f65891796cce5528fcf99acbf504aed"
    )
