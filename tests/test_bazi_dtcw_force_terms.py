"""Named-source semantic cards do not turn a relative judgment into a score."""

from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
KEY_PAGES = {
    "身杀两停": [118],
    "旺者冲衰与衰者冲旺": [78, 79, 89, 90],
    "盖头与干支位置": [106, 107, 108, 109],
}


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
