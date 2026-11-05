"""Selected primary-text taxonomies are not personality or clinical measures."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_element_knowledge_v1"
KEYS = ["木", "火", "土", "金", "水"]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return read(path)


def test_exact_revision_capture_preserves_complete_source_units_and_taxonomies():
    claims = frozen("source-claims.json")
    capture = FIXTURE / "sources/revision-capture.json"
    assert digest(capture) == claims["capture_sha256"]
    pages = {p["title"]: p for p in read(capture)["query"]["pages"]}
    texts = {}
    for source in claims["sources"]:
        revision = pages[source["title"]]["revisions"][0]
        assert revision["revid"] == source["revision_id"]
        assert revision["timestamp"] == source["revision_timestamp"]
        path = FIXTURE / source["text_path"]
        assert path.read_text() == revision["slots"]["main"]["content"]
        assert digest(path) == source["text_sha256"]
        texts[source["id"]] = path.read_text()
    assert len(claims["complete_liji_month_units"]) == 12
    assert all(unit in texts["liji"] for unit in claims["complete_liji_month_units"])
    assert "第二論五行及生成數" in texts["wuxingdayi"]
    assert "陰陽應象大論第五" in texts["suwen2"]
    assert "本輸第二" in texts["lingshu1"]
    for row in claims["rows"]:
        paragraph = row["suwen_full_correspondence_paragraph"]
        assert paragraph in texts["suwen2"]
        for field, marker in [
            ("suwen_body_as_printed", "在體為"),
            ("suwen_viscus_as_printed", "在藏為"),
            ("suwen_orifice_as_printed", "在竅為"),
        ]:
            assert marker + row[field] in paragraph
        assert (
            row["suwen_viscus_as_printed"] + "合" + row["lingshu_paired_fu_as_printed"]
            in texts["lingshu1"]
        )
    # Ritual "祭先" and medical "在藏" refer to different classification tasks.
    assert (
        sum(
            r["liji_ritual_viscus_as_printed"] != r["suwen_viscus_as_printed"]
            for r in claims["rows"]
        )
        == 4
    )
    earth = next(r for r in claims["rows"] if r["element"] == "土")
    assert (
        earth["liji_number_as_printed"] == earth["generation_number_as_printed"] == "五"
    )
    assert earth["completion_number_as_printed"] == "十"


@pytest.mark.parametrize("key", KEYS)
def test_published_card_attributes_each_field_and_exposes_sources_in_first_view(key):
    claims = frozen("source-claims.json")
    row = next(r for r in claims["rows"] if r["element"] == key)
    result = calculate_knowledge_read(domain="bazi", category="elements", key=key)
    curation = result["provenance"]["entry_curation"]
    assert len(result["tips"]) == 8
    indices = sum(
        [
            curation[name]
            for name in [
                "classical_condition_tip_indexes",
                "implementation_tip_indexes",
                "editorial_tip_indexes",
            ]
        ],
        [],
    )
    assert sorted(indices) == list(range(8))
    assert curation["editorial_tip_indexes"] == [4, 7]
    for source in curation["source_refs"]:
        # The default summary's citation must be useful without hidden provenance.
        assert source["source_url"] in result["citation"]
        assert source["author"] in result["citation"]
        assert source["edition"] in result["snapshot_text"]
    medical = "—".join(
        row["medical_display_simplified"][k] for k in ["viscus", "body", "orifice"]
    )
    assert medical in result["tips"][5]
    for source in claims["sources"]:
        actual = next(
            r
            for r in curation["source_refs"]
            if r.get("source_revision_id") == source["revision_id"]
        )
        assert actual["source_sha256"] == source["text_sha256"]
