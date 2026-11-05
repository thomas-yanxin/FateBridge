"""Complete chapters and old failures remain visible when a hypothesis fails."""

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read


@pytest.mark.parametrize(
    "key", ["燥湿与生发条件", "物理藏根与功能根", "隐显与制化", "众寡与日主符合"]
)
def test_public_semantic_cards_publish_named_source_and_unadjudicated_force(key):
    result = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key=key
    )
    assert "error" not in result
    curation = result["provenance"]["entry_curation"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    source = curation["source_refs"][0]
    assert (
        source["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["source_pdf_pages"] and source["edition"] in result["snapshot_text"]
    assert source["source_url"] in result["citation"]
