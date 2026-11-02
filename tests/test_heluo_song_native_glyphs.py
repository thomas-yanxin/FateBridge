"""Literal source corrections from embedded pixels, not prediction accuracy."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_poems as hp
from fatebridge.core.heluo import yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.errors import NumerologySourceError
from tests.heluo_guan_shi_revision_reference import NEW_POEMS as R84_NEW_POEMS
from tests.heluo_shike_bi_revision_reference import assert_r92_source_addition

F = Path(__file__).parent / "fixtures/heluo_song_native_glyphs_v1"
REF = json.loads((F / "source-proposal-reference.json").read_bytes())
OLD = json.loads((F / "poems-before.json").read_bytes())
NEW = json.loads((F / "poems-proposed.json").read_bytes())
CHANGES = REF["word_changes"]
NOTES = [(int(k.split(":")[0]), int(k.split(":")[1])) for k in REF["reading_notes"]]


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def expected_poem(line, index):
    return next(
        e for e in NEW["entries"] if e["hexagram"] == "天水訟" and e["line"] == line
    )["poems"][index - 1]


@pytest.fixture(autouse=True)
def clear_poem_cache():
    hp._collation.cache_clear()
    yield
    hp._collation.cache_clear()


def test_source_and_proposal_precede_prototype_but_fixture_is_not_claimed_blind():
    freeze = json.loads((F / "fixture-freeze.json").read_bytes())
    assert freeze["fixture_assembly_after_prototype_code"] is True
    assert freeze["known_source_diagnostic_not_blind_or_independent"] is True
    for name, digest in freeze["files_sha256"].items():
        assert hashlib.sha256((F / name).read_bytes()).hexdigest() == digest
    source = F / "source-review/adjudication-before-edits.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == REF["adjudication_sha256"]
    assert (
        json.loads(source.read_bytes())["before_any_production_or_prototype_edits"]
        is True
    )
    assert REF["before_prototype_code_edits"] is True
    assert REF["before_root_production_edits"] is True
    assert REF["independent_review_completed"] is False
    assert len(CHANGES) == 4 and REF["changed_poem_locations"] == [
        [1, 1],
        [5, 3],
        [6, 1],
    ]


@pytest.mark.parametrize("change", CHANGES, ids=lambda c: c["id"])
def test_each_selected_source_glyph_uses_the_literal_proposal(change):
    poem = yao_text("天水訟", change["line"])["poem_sections"][change["index"] - 1]
    assert poem["text"] == expected_poem(change["line"], change["index"])["text"]
    assert change["after"] in poem["text"] and change["before"] not in poem["text"]
    assert (
        poem["printed_clauses"]
        == expected_poem(change["line"], change["index"])["printed_clauses"]
    )
    assert poem["applicability"] is None


def test_every_one_of_87_poems_and_old30_groups_keep_exact_scope():
    current = hp._collation()
    assert current["entries"][:30] == OLD["entries"][:30]
    assert current["entries"][:36] == NEW["entries"]
    assert current["entries"][36:42] == R84_NEW_POEMS["entries"][36:]
    assert_r92_source_addition()
    oldtexts = [p["text"] for e in OLD["entries"] for p in e["poems"]]
    newtexts = [p["text"] for e in current["entries"][:36] for p in e["poems"]]
    assert len(oldtexts) == len(newtexts) == 87
    assert sum(a == b for a, b in zip(oldtexts, newtexts, strict=True)) == 84
    assert (
        sum(
            sum(x != y for x, y in zip(a, b, strict=True))
            for a, b in zip(oldtexts, newtexts, strict=True)
        )
        == 4
    )
    summary = hp.collation_summary()
    assert (
        summary["collated_line_poem_groups"],
        summary["pending_line_poem_groups"],
        summary["total_individual_poems"],
    ) == (48, 336, None)
    third = yao_text("天水訟", 3)
    assert third["text_provenance"]["poem_heading_text"] == "訟卦三爻訣一首"
    assert len(third["poem_sections"]) == 3


@pytest.mark.parametrize("line,index", NOTES)
def test_all_five_notes_reach_the_actual_summary_without_independent_certification(
    line, index
):
    result = calculate_knowledge_read(domain="heluo", key=f"天水訟:{line}")
    poem = result["reference_details"]["record"]["poem_sections"][index - 1]
    expected = expected_poem(line, index)
    assert poem["reading_notes"] == expected["reading_notes"]
    assert (
        poem["review_status"]
        == "single_reader_embedded_pixel_recheck; independent_second_review_pending"
    )
    summary = "\n".join(result["lines"])
    assert all(n in summary for n in expected["reading_notes"])
    assert result["provenance"]["independent_whole_corpus_review_completed"] is False
    assert result["provenance"]["real_world_efficacy_validated"] is False
    assert (
        result["reference_details"]["record"]["poem_selection"]["selected_poem_indices"]
        == []
    )


def test_old_inherited_correct_words_are_not_rewritten_into_new_reading_history():
    for line in [1, 2, 4, 5, 6]:
        text = yao_text("天水訟", line)
        assert text["poem_selection"]["automatic_selection"] is False
        assert text["poem_selection"]["selected_poem_indices"] == []
        if line == 6:
            assert "不須歡" in text["text_provenance"]["inherited_shige"]
            assert "困來" in text["text_provenance"]["inherited_shige"]
            assert "不須懽" in text["shige"] and "困來" in text["shige"]


@pytest.mark.parametrize("change", CHANGES, ids=lambda c: c["id"])
def test_frozen_literal_reference_detects_rebound_producer_hash(
    change, monkeypatch, tmp_path
):
    bad = copy.deepcopy(hp._collation())
    poem = next(
        e
        for e in bad["entries"]
        if e["hexagram"] == "天水訟" and e["line"] == change["line"]
    )["poems"][change["index"] - 1]
    assert change["after"] in poem["text"]
    poem["text"] = poem["text"].replace(change["after"], change["before"])
    poem["printed_clauses"] = [
        c.replace(change["after"], change["before"]) for c in poem["printed_clauses"]
    ]
    path = tmp_path / "unreviewed-but-rebound.json"
    path.write_text(json.dumps(bad, ensure_ascii=False))
    monkeypatch.setattr(hp, "COLLATION_PATH", path)
    monkeypatch.setattr(hp, "CONTENT_SHA256", canonical(bad))
    hp._collation.cache_clear()
    # R89 adds a separately frozen full-text review binding. Rebinding the
    # earlier corpus hash can no longer make these four mutants readable.
    with pytest.raises(NumerologySourceError) as caught:
        yao_text("天水訟", change["line"])
    assert (
        caught.value.as_result()["issues"][0]["code"] == "invalid_heluo_poem_collation"
    )
    assert (
        canonical(bad)
        != REF["proposed_canonical_sha256"][
            "src/fatebridge/data/heluo/poem-collation-v1.json"
        ]
    )
    # The historical wrong output is now rejected before it can be explained.
