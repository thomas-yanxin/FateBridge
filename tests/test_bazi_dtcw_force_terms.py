"""Named-source semantic cards do not turn a relative judgment into a score."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_knowledge_curation_v1"
KEY_PAGES = {
    "身杀两停": [118],
    "旺者冲衰与衰者冲旺": [78, 79, 89, 90],
    "盖头与干支位置": [106, 107, 108, 109],
}


def test_preexisting_75_cards_and_other_index_domains_are_preserved_byte_semantically():
    review = json.loads((FIXTURE / "dtcw-terms-review-v1.json").read_text())
    before = FIXTURE / "bundle-before-dtcw-terms.json"
    assert (
        hashlib.sha256(before.read_bytes()).hexdigest()
        == review["previous_bundle_sha256"]
    )
    previous = json.loads(before.read_text())
    # Compare the old preservation claim to the exact edition it described.
    current_path = (
        ROOT
        / "tests/fixtures/bazi_topic_knowledge_v2/before/src/fatebridge/data/knowledge/bazi.json"
    )
    current = json.loads(current_path.read_text())
    retained = 0
    for category, entries in previous["categories"].items():
        for key, value in entries.items():
            assert current["categories"][category][key] == value
            retained += 1
    assert retained == review["preexisting_entries_unchanged"] == 75
    # The old signed review still identifies its exact 78-card version.
    # A later additive edition has a separate signed review and current hash.
    extension = ROOT / "tests/fixtures/bazi_body_capacity_v6"
    current_review = json.loads((extension / "knowledge-review.json").read_text())
    assert (
        hashlib.sha256((extension / "knowledge-before.json").read_bytes()).hexdigest()
        == review["current_bundle_sha256"]
    )
    assert current_review["previous_bundle_sha256"] == review["current_bundle_sha256"]
    assert (
        hashlib.sha256(current_path.read_bytes()).hexdigest()
        == current_review["current_bundle_sha256"]
    )
    old_index = json.loads((FIXTURE / "index-before-dtcw-terms.json").read_text())
    new_index = json.loads(
        (ROOT / "src/fatebridge/data/knowledge/index.json").read_text()
    )
    for domain in new_index["domains"]:
        if domain["domain"] == "bazi":
            category = next(
                c
                for c in domain["categories"]
                if c["name"] == "classical_force_semantics"
            )
            category["count"] = 3
            category["keys_sample"] = sorted(
                previous["categories"]["classical_force_semantics"]
            )
    assert old_index == new_index
    assert review["original_entries"] == 72
    assert review["source_attribution_pending_original_entries"] == 50
    assert review["new_independent_cases"] == 0


@pytest.mark.parametrize("key,pages", KEY_PAGES.items())
def test_public_card_retains_checked_edition_pages_and_no_force_acceptance(key, pages):
    result = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key=key
    )
    curation = result["provenance"]["entry_curation"]
    source = curation["source_refs"][0]
    assert (
        source["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["source_pdf_pages"] == pages
    assert source["edition"] in result["snapshot_text"]
    assert source["source_url"] in result["citation"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    assert "not new independent observations" in curation["known_overlap"]
    assert "非逐字引文" in result["citation"]


def test_relative_balance_and_counterfactual_position_changes_remain_distinct():
    balance = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="身杀两停"
    )
    position = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="盖头与干支位置"
    )
    assert (
        "不能直接" in balance["rendered_text"]
        and "全局中和" in balance["rendered_text"]
    )
    assert "年、月两柱位置也不同" in position["rendered_text"]
    assert "不能把它误当只改一个日支" in position["rendered_text"]
