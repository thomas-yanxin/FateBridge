"""Source relationships must agree, rather than merely sharing transport bytes."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path("src/fatebridge/data/knowledge/bazi.json")
CATEGORY = "classical_force_semantics"
KEY = "日元强弱与性情措辞"
NORMAL = {"旺極": "旺极", "衰極": "衰极", "煉": "炼", "剋": "克", "濟": "济"}


def read(path):
    return json.loads(path.read_text())


def card(path):
    return read(path)["categories"][CATEGORY][KEY]


def reference_rows():
    source = ROOT / "tests/data/bazi/four-state-relations.json"
    return read(source)["rows"]


def source_tuples():
    return {
        (row["element"], NORMAL.get(row["source_state"], row["source_state"])): (
            row["analogous_element"],
            row["preferred_element"],
            NORMAL.get(
                row["source_action_on_analogy"], row["source_action_on_analogy"]
            ),
        )
        for row in reference_rows()
    }


def rendered_tuples(tip):
    if "仅以木为例，依次说" in tip:
        text = tip.split("依次说", 1)[1].split("。", 1)[0]
        matches = [re.fullmatch("似(.)喜(.)(.)", part) for part in text.split("、")]
        assert all(matches) and len(matches) == 4
        return {
            ("木", state): match.groups()
            for state, match in zip(
                ["太旺", "旺极", "太衰", "衰极"], matches, strict=True
            )
        }
    text = tip.split("四态取用关系为：", 1)[1].split("。", 1)[0]
    found = {}
    for group in text.split("；"):
        element, rest = group.split("：", 1)
        for part in rest.split("，"):
            match = re.fullmatch("(太旺|旺极|太衰|衰极)似(.)宜(.)(.)", part)
            assert match, part
            state, analogy, preferred, action = match.groups()
            assert (element, state) not in found
            found[element, state] = (analogy, preferred, action)
    return found


def test_current_card_wood_relationships_match_frozen_source():
    actual = rendered_tuples(card(ROOT / BUNDLE)["tips"][7])
    assert {k: v for k, v in actual.items() if k[0] == "木"} == {
        k: v for k, v in source_tuples().items() if k[0] == "木"
    }


def test_all20_rendered_relations_and_structured_provenance_match_source():
    current = card(ROOT / BUNDLE)
    assert len(source_tuples()) == 20
    assert rendered_tuples(current["tips"][7]) == source_tuples()
    binding = current["curation"]["source_relation_binding"]
    assert binding["rows"] == reference_rows()
    assert binding["source_claim_id"] == "CENSUS-R539"
    assert binding["source_pdf_pages"] == [177, 178]
    assert binding["numeric_classifier_implemented"] is False
    assert binding["independent_annotation_review"] == "not_certified"
    assert all(row["numeric_threshold"] is None for row in binding["rows"])
    assert current["curation"]["entry_revision"] == 3


def test_reference_remains_bound_to_original_transcription_and_source_bytes():
    reference = read(ROOT / "tests/data/bazi/four-state-relations.json")
    census = read(ROOT / "tests/data/bazi/ditian-source-census.json")
    claim = next(
        c
        for c in census["resolved_source_claims"].values()
        if c["claim_id"] == reference["claim_id"]
    )
    assert claim["literal_table_or_relation_data"] == reference_rows()
    pdf = ROOT / "tests/data/bazi/primary/ditian-1947.pdf"
    assert (
        hashlib.sha256(pdf.read_bytes()).hexdigest() == reference["source_pdf_sha256"]
    )
