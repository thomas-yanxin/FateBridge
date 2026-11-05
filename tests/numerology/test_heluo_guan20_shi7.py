"""Literal-source regressions; no predictions or independent-reader credit."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_poems as hp
from fatebridge.core import heluo_texts as ht
from fatebridge.core.heluo import yao_text
from fatebridge.services.knowledge import calculate_knowledge_read
from tests.support.heluo_source_facts import PENDING_COUNT

W = Path(__file__).parents[1] / "fixtures" / "heluo_guan20_shi7_v1"
LITERAL = json.loads(
    (W / "reviewed-literal-readings-before-candidate.json").read_bytes()
)
PROPOSAL = json.loads((W / "source-proposal-reference.json").read_bytes())


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


@pytest.fixture(autouse=True)
def clear_sources():
    for fn in (hp._collation, ht._collation, ht._commentary_collation):
        fn.cache_clear()
    yield
    for fn in (hp._collation, ht._collation, ht._commentary_collation):
        fn.cache_clear()


def test_frozen_readings_precede_consumer_and_preserve_withdrawals():
    freeze = json.loads(
        (W / "reviewed-literal-freeze-before-candidate.json").read_bytes()
    )
    assert freeze["before_any_R84_producer_or_consumer_edits"] is True
    assert freeze["not_blind_or_independent_review"] is True
    for name, digest in freeze["files_sha256"].items():
        assert hashlib.sha256((W / name).read_bytes()).hexdigest() == digest
    second = json.loads((W / "postcomparison-review-second.json").read_bytes())
    assert second["withdrawals"][0]["first"] == "顧"
    assert second["withdrawals"][0]["selected"] == "賴"
    assert len(second["uncertainties_not_resolved"]) == 3
    assert second["goal_complete"] is False


@pytest.mark.parametrize(
    "entry", LITERAL["commentary"], ids=lambda e: f"guan-{e['line']}"
)
def test_complete_header_and_all_parented_sections(entry):
    actual = yao_text(entry["hexagram"], entry["line"])
    assert actual["yaoci"] == entry["yaoci"]
    assert actual["detail"] == "".join(s["text"] for s in entry["sections"])
    assert [s["text"] for s in actual["commentary_sections"]] == [
        s["text"] for s in entry["sections"]
    ]
    assert [s["section_id"] for s in actual["commentary_sections"]] == [
        "opening",
        "xie",
        "buxie",
        "annual",
    ]
    assert [s["condition_label"] for s in actual["commentary_sections"]] == [
        None,
        "叶者",
        "不叶者",
        "歲運逢之",
    ]
    assert all(s["applicability"] is None for s in actual["commentary_sections"])
    assert actual["commentary_branch_selection"]["selected_section_ids"] == []
    assert actual["text_provenance"]["commentary_pdf_pages"] == entry["pdf_pages"]
    assert (
        actual["text_provenance"]["commentary_reading_notes"] == entry["reading_notes"]
    )


@pytest.mark.parametrize("entry", LITERAL["poems"], ids=lambda e: f"shi-{e['line']}")
def test_every_poem_and_actual_printed_clause_boundary(entry):
    actual = yao_text(entry["hexagram"], entry["line"])
    assert actual["shige"] == "\n".join(p["text"] for p in entry["poems"])
    assert len(actual["poem_sections"]) == entry["printed_heading_count"]
    assert actual["text_provenance"]["poem_pdf_pages"] == entry["pdf_pages"]
    assert actual["text_provenance"]["poem_heading_text"] == entry["heading_text"]
    for expected, produced in zip(entry["poems"], actual["poem_sections"], strict=True):
        assert produced["text"] == expected["text"]
        assert produced["printed_clauses"] == expected["printed_clauses"]
        assert produced["pdf_pages"] == expected["pdf_pages"]
        assert produced["reading_notes"] == expected["reading_notes"]
        assert produced["review_status"] == expected["review_status"]
        assert produced["applicability"] is None
    assert actual["poem_selection"]["selected_poem_indices"] == []
    assert actual["poem_selection"]["automatic_selection"] is False


@pytest.mark.parametrize(
    "gua,line,layer",
    [("風地觀", 4, "commentary"), ("地水師", 2, "poems"), ("地水師", 5, "poems")],
)
def test_unresolved_choice_is_visible_in_actual_summary_and_notes(gua, line, layer):
    text = yao_text(gua, line)
    snapshot = ht.text_status_snapshot(text)
    assert "字形未决" in snapshot
    out = calculate_knowledge_read(domain="heluo", key=f"{gua}:{line}")
    summary = "\n".join(out["lines"])
    notes = (
        text["text_provenance"]["commentary_reading_notes"]
        if layer == "commentary"
        else [n for p in text["poem_sections"] for n in p["reading_notes"]]
    )
    assert all(n in summary for n in notes)
    assert out["reference_details"]["personal_applicability_assessed"] is False
    assert out["provenance"]["independent_whole_corpus_review_completed"] is False


@pytest.mark.parametrize(
    "kind,word,replacement",
    [
        ("headers", "闚觀", "蘭觀"),
        ("poems", "未能", "朱能"),
        ("poems", "青蠅", "青氈"),
        ("poems", "眼前人人不信", "眼前人不信"),
    ],
)
def test_frozen_reference_still_detects_synchronized_data_and_producer_rebinding(
    kind, word, replacement, monkeypatch, tmp_path
):
    module, path_attr, digest_attr = (
        (ht, "COLLATION_PATH", "HEADER_CONTENT_SHA256")
        if kind == "headers"
        else (hp, "COLLATION_PATH", "CONTENT_SHA256")
    )
    source = json.loads(Path(getattr(module, path_attr)).read_bytes())
    mutated = copy.deepcopy(source)
    gua, line, index = {
        "闚觀": ("風地觀", 2, None),
        "未能": ("地水師", 2, 1),
        "青蠅": ("地水師", 3, 3),
        "眼前人人不信": ("地水師", 4, 2),
    }[word]
    entry = next(
        e for e in mutated["entries"] if (e["hexagram"], e["line"]) == (gua, line)
    )
    if kind == "headers":
        assert entry["yaoci"].count(word) == 1
        entry["yaoci"] = entry["yaoci"].replace(word, replacement)
    else:
        poem = entry["poems"][index - 1]
        assert poem["text"].count(word) == 1
        poem["text"] = poem["text"].replace(word, replacement)
        poem["printed_clauses"] = [
            c.replace(word, replacement) for c in poem["printed_clauses"]
        ]
    target = tmp_path / "synchronized-rebinding.json"
    target.write_text(json.dumps(mutated, ensure_ascii=False))
    monkeypatch.setattr(module, path_attr, target)
    monkeypatch.setattr(module, digest_attr, canonical(mutated))
    module._collation.cache_clear()
    actual = module._collation()
    key = "src/fatebridge/data/heluo/" + (
        "yaoci-collation-v1.json" if kind == "headers" else "poem-collation-v1.json"
    )
    assert actual["_content_sha256"] != PROPOSAL["proposed_canonical_sha256"][key]
    expected = json.loads((W / "proposed" / key).read_bytes())
    assert actual["entries"] != expected["entries"]
