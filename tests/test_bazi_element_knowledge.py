"""Selected primary-text taxonomies are not personality or clinical measures."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_element_knowledge_v1"
BUNDLE = Path("src/fatebridge/data/knowledge/bazi.json")
LEDGER = Path("tests/fixtures/bazi_knowledge_curation_v1/ledger.json")
HISTORICAL_AFTER = ROOT / "tests/fixtures/bazi_body_vocabulary_knowledge_v2/before"
KEYS = ["木", "火", "土", "金", "水"]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return read(path)


def test_every_other_object_and_all_keys_are_preserved_against_the_sealed_edition():
    protocol, review = frozen("protocol.json"), frozen("review.json")
    assert review["protocol_sha256"] == digest(FIXTURE / "protocol.json")
    assert review["before_bundle_sha256"] == digest(FIXTURE / "before" / BUNDLE)
    # Preserve the exact after-edition of this five-element review. The later
    # body-vocabulary revision has its own current84-object preservation gate.
    assert review["current_bundle_sha256"] == digest(HISTORICAL_AFTER / BUNDLE)
    before, current = read(FIXTURE / "before" / BUNDLE), read(HISTORICAL_AFTER / BUNDLE)
    assert {k: v for k, v in before.items() if k != "categories"} == {
        k: v for k, v in current.items() if k != "categories"
    }
    assert set(before["categories"]) == set(current["categories"])
    changed, kept = [], 0
    for category, entries in before["categories"].items():
        assert set(entries) == set(current["categories"][category])
        for key, entry in entries.items():
            if entry == current["categories"][category][key]:
                kept += 1
            else:
                changed.append((category, key))
    assert changed == [("elements", key) for key in KEYS]
    assert protocol["targets"] == {"elements": KEYS}
    assert kept == review["all_other_entries_exactly_preserved"] == 80
    assert sum(map(len, current["categories"].values())) == 85
    for name in protocol["before_sha256"]:
        assert digest(FIXTURE / "before" / name) == protocol["before_sha256"][name]
    assert not review["numeric_policy_changed"]
    assert not review["source_labels_changed"]
    assert not review["adoption_gates_changed"]
    assert not review["independent_scan_or_expert_acceptance"]
    assert review["new_chart_cases"] == review["new_model_executions"] == 0
    assert review["real_world_efficacy"] == "not_tested"
    assert not review["full_goal_complete"] and review["overall_score"] is None


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
    old = read(FIXTURE / "before" / BUNDLE)["categories"]["elements"][key]
    industries = next(t for t in old["tips"] if t.startswith("**行业：**"))[7:].split(
        "、"
    )
    assert all(industry in result["tips"][4] for industry in industries)
    assert "现代编辑类比" in result["tips"][4]
    assert old["tips"][1] not in result["rendered_text"]
    assert old["tips"][2] not in result["rendered_text"]
    assert "not_medical_personality_or_efficacy" in curation["validation_status"]
    assert "external_review_pending" in curation["review_status"]


def test_inventory_credits_only_five_declared_textual_collations_and_no_expert_acceptance():
    before, current = read(FIXTURE / "before" / LEDGER), read(HISTORICAL_AFTER / LEDGER)
    assert current["curated_keys"]["elements"] == KEYS
    for category, keys in before["curated_keys"].items():
        assert current["curated_keys"][category] == keys
    assert current["current_bundle_sha256"] == digest(HISTORICAL_AFTER / BUNDLE)
    assert current["original_entries"] == before["original_entries"] == 72
    assert current["current_total"] == before["current_total"] == 85
    assert (
        current["unmodified_original_entries"]
        == before["unmodified_original_entries"] - 5
        == 25
    )
    assert (
        current["revised_original_entries"]
        == before["revised_original_entries"] + 5
        == 47
    )
    assert (
        current["source_attribution_pending_original_entries"]
        == before["source_attribution_pending_original_entries"] - 5
        == 35
    )
    assert (
        current["curated_total"]
        == sum(map(len, current["curated_keys"].values()))
        == 60
    )
    assert (
        current["independent_expert_acceptance"]
        == before["independent_expert_acceptance"]
    )
    assert current["independent_expert_acceptance"].startswith("not_completed_for_any")
