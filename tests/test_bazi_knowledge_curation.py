"""Editorial/source scope is explicit; it is not a new force-accuracy score."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_knowledge_curation_v1"
LEDGER = json.loads((FIXTURE / "ledger.json").read_text())
LEGACY = json.loads((FIXTURE / "legacy-bundle.json").read_text())
CASES = [
    (category, key) for category, keys in LEDGER["curated_keys"].items() for key in keys
]


def test_bureau_fidelity_review_updates_only_review_metadata_and_preserves_history():
    review_path = FIXTURE / "bureau-fidelity-v5-review.json"
    assert (
        hashlib.sha256(review_path.read_bytes()).hexdigest()
        == review_path.with_suffix(".sha256").read_text().strip()
    )
    review = json.loads(review_path.read_text())
    before_path = FIXTURE / "bundle-before-bureau-fidelity-v5.json"
    before = json.loads(before_path.read_text())
    # The sealed v5 review describes75 cards. Its exact after-review bytes
    # are reconstructed and checked against that original sealed digest.
    after_path = (
        ROOT / "tests/fixtures/bazi_topic_knowledge_v2/historical-bureau-v5-after.json"
    )
    assert (
        hashlib.sha256(after_path.read_bytes()).hexdigest()
        == review["current_bundle_sha256"]
    )
    current = json.loads(after_path.read_text())
    assert (
        hashlib.sha256(before_path.read_bytes()).hexdigest()
        == review["previous_bundle_sha256"]
    )
    for category, entries in before["categories"].items():
        for key, entry in entries.items():
            new = current["categories"][category][key]
            if category == "structures":
                assert {k: v for k, v in entry.items() if k != "curation"} == {
                    k: v for k, v in new.items() if k != "curation"
                }
                assert (
                    new["curation"]["entry_revision"]
                    == entry["curation"]["entry_revision"] + 1
                )
                assert (
                    new["curation"]["implementation_ref_history"][-1]["previous_ref"]
                    == entry["curation"]["implementation_refs"][0]
                )
                assert (
                    new["curation"]["validation_status"]
                    == entry["curation"]["validation_status"]
                )
            else:
                assert entry == new
    assert not review["classical_acceptance_passed"] and not review["labels_changed"]


def test_frozen_legacy_keys_and_unreviewed_entries_are_not_silently_relabelled():
    before = (FIXTURE / "legacy-bundle.json").read_bytes()
    assert (
        hashlib.sha256(before).hexdigest()
        == (FIXTURE / "legacy-bundle.sha256").read_text().strip()
        == LEDGER["legacy_bundle_sha256"]
    )
    current = json.loads((ROOT / "src/fatebridge/data/knowledge/bazi.json").read_text())
    assert set(LEGACY["categories"]) <= set(current["categories"])
    retained = 0
    for category, entries in LEGACY["categories"].items():
        assert set(entries) <= set(current["categories"][category])
        for key, old in entries.items():
            new = current["categories"][category][key]
            if category == "ten_gods":
                assert new["tips"][0] == old["tips"][0]
            elif key not in LEDGER["curated_keys"].get(category, []):
                assert new == old
                retained += 1
    assert retained == LEDGER["unmodified_original_entries"] == 25
    assert LEDGER["original_entries"] == 72 and LEDGER["current_total"] == 85
    assert LEDGER["source_attribution_pending_original_entries"] == retained + 6 + 4
    assert LEDGER["independent_expert_acceptance"].startswith("not_completed")


def test_registry_and_index_publish_semantic_keys_without_claiming_all_reviewed():
    registry = calculate_knowledge_registry(domain="bazi")
    domain = next(d for d in registry["domains"] if d["domain"] == "bazi")
    card = next(
        c for c in domain["categories"] if c["name"] == "classical_force_semantics"
    )
    assert card["count"] == 14
    assert sorted(card["keys"]) == sorted(
        LEDGER["curated_keys"]["classical_force_semantics"] + ["藏干序位与人元司令"]
    )
    original = (
        ROOT
        / "tests/fixtures/bazi_birth_seconds_v1/before/src/fatebridge/data/knowledge/bazi.json"
    )
    assert (
        hashlib.sha256(original.read_bytes()).hexdigest()
        == LEDGER["current_bundle_sha256"]
    )
    assert LEDGER["remaining_legacy_entries"] == 25
    assert LEDGER["health_source_attribution_pending_entries"] == 6
    assert LEDGER["topic_partial_attribution_pending_entries"] == 4


@pytest.mark.parametrize("key", LEDGER["curated_keys"]["ten_gods"])
def test_ten_god_cards_replace_unqualified_outcomes_with_conditions_and_sources(key):
    result = calculate_knowledge_read(domain="bazi", category="ten_gods", key=key)
    assert "error" not in result
    assert result["lines"][0] == LEGACY["categories"]["ten_gods"][key]["tips"][0]
    text = result["rendered_text"]
    for old in LEGACY["categories"]["ten_gods"][key]["tips"][1:]:
        if len(old) > 3:
            assert old not in text
    assert "**健康：**" not in text
    curation = result["provenance"]["entry_curation"]
    assert result["provenance"]["source_domain"] == "fatebridge_curated_bazi"
    assert (
        curation["validation_status"]
        == "selected_source_conditions_not_full_classical_or_reality_acceptance"
    )
    assert curation["definition_basis"].startswith("首行是五行生克")
    reference = curation["source_refs"][0]
    assert (
        reference["source_sha256"]
        == "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
    )
    assert reference["source_pdf_pages"]
    assert reference["edition"] in result["snapshot_text"]
    assert reference["source_url"] in result["snapshot_text"]
    assert "非逐字引文" in result["citation"]


def test_force_term_cards_keep_known_counterexamples_and_inferred_variant_separate():
    heavy = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="身重印轻"
    )
    light = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="身轻印重"
    )
    both = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="身强印旺与印用食伤"
    )
    assert (
        "正式v2的中和" in heavy["rendered_text"]
        and "分歧仍保留" in heavy["rendered_text"]
    )
    assert (
        "正式v2输出强" in light["rendered_text"]
        and "分歧尚未解决" in light["rendered_text"]
    )
    assert (
        "扫描本印作乙亥" in both["rendered_text"]
        and "推导候选" in both["rendered_text"]
    )
    for result in (heavy, light, both):
        assert (
            result["provenance"]["entry_curation"]["validation_status"]
            == "text_semantics_not_model_force_adjudication"
        )
        assert (
            "not new independent observations"
            in result["provenance"]["entry_curation"]["known_overlap"]
        )


def test_unreviewed_card_keeps_an_explicit_unreviewed_status():
    result = calculate_knowledge_read(domain="bazi", category="shensha", key="桃花")
    assert result["provenance"]["review_status"] == "legacy_unreviewed"
    assert "旧资料待逐条核对" in result["citation"]
    assert "entry_curation" not in result["provenance"]


def test_nested_entry_sources_cannot_mutate_the_cached_knowledge_bundle():
    first = calculate_knowledge_read(domain="bazi", category="ten_gods", key="正印")
    first["provenance"]["entry_curation"]["source_refs"][0]["source_pdf_pages"].append(
        999
    )
    second = calculate_knowledge_read(domain="bazi", category="ten_gods", key="正印")
    assert (
        999
        not in second["provenance"]["entry_curation"]["source_refs"][0][
            "source_pdf_pages"
        ]
    )


@pytest.mark.parametrize("category,key", CASES)
def test_curated_cards_keep_identical_content_on_rest_native_mcp_and_cli(
    category, key, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": category, "key": key}
    opts = {"include_snapshot_text": False, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "false", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    provenance = http.json()["provenance"]
    curation = provenance["entry_curation"]
    if category == "health":
        assert curation["implementation_refs"]
        assert provenance["review_status"] == curation["review_status"]
    else:
        assert curation["source_refs"]


@pytest.mark.parametrize("key", LEDGER["curated_keys"]["health"])
def test_health_cards_separate_software_evidence_from_uncollated_correspondences(key):
    result = calculate_knowledge_read(domain="bazi", category="health", key=key)
    curation = result["provenance"]["entry_curation"]
    implementation = curation["implementation_refs"][0]
    assert (
        hashlib.sha256((ROOT / implementation["source_path"]).read_bytes()).hexdigest()
        == implementation["source_sha256"]
    )
    assert implementation["source_path"] in result["snapshot_text"]
    assert implementation["source_sha256"] in result["snapshot_text"]
    assert curation["review_status"] in result["snapshot_text"]
    if key in {"七杀攻身", "调候寒暖"}:
        assert (
            curation["review_status"]
            == "selected_classical_semantics_not_full_acceptance"
        )
        assert curation["source_refs"][0]["source_pdf_pages"] == (
            [28, 39, 77] if key == "七杀攻身" else [37, 38]
        )
    else:
        assert curation["source_refs"] == []
        assert curation["legacy_correspondence_status"] == "not_collated"
        assert (
            curation["review_status"]
            == "computational_scope_only_correspondence_source_pending"
        )
        assert "医籍" in result["citation"] and "待完成" in result["citation"]
        assert "原典：" not in result["snapshot_text"]


def test_climate_card_discloses_the_actual_grouping_and_unimplemented_classical_layer():
    result = calculate_knowledge_read(domain="bazi", category="health", key="调候寒暖")
    text = result["rendered_text"]
    assert "火土权重之和与水金权重之和" in text and "差值达到3" in text
    assert "未实现上述原典的月令调候裁定" in text
    assert (
        "并不表示身体已经受伤"
        in calculate_knowledge_read(domain="bazi", category="health", key="七杀攻身")[
            "rendered_text"
        ]
    )


@pytest.mark.parametrize("key", LEDGER["curated_keys"]["structures"])
def test_structure_cards_replace_automatic_formation_and_occupation_with_conditions(
    key,
):
    result = calculate_knowledge_read(domain="bazi", category="structures", key=key)
    text = result["rendered_text"]
    assert "候选" in text and "不认证成格" in text
    assert "monthly_structure.structure_god" in text
    for old in LEGACY["categories"]["structures"][key]["tips"]:
        if len(old) > 3:
            assert old not in text
    curation = result["provenance"]["entry_curation"]
    assert (
        result["provenance"]["review_status"]
        == "selected_month_command_semantics_not_formation_acceptance"
    )
    assert curation["validation_status"].endswith("not_complete_formation")
    assert curation["source_refs"][0]["source_pdf_pages"][:5] == [26, 27, 28, 29, 30]
    assert (
        curation["implementation_refs"][0]["source_sha256"]
        == hashlib.sha256(
            (ROOT / "src/fatebridge/core/classical.py").read_bytes()
        ).hexdigest()
    )
    assert "非逐字引文" in result["citation"]


def test_structure_cards_preserve_seal_output_exceptions_and_actual_blade_seat_meaning():
    wealth = calculate_knowledge_read(
        domain="bazi", category="structures", key="正财格"
    )
    seal = calculate_knowledge_read(domain="bazi", category="structures", key="正印格")
    blade = calculate_knowledge_read(
        domain="bazi", category="structures", key="羊刃驾杀格"
    )
    assert "食伤生财" in wealth["rendered_text"]
    assert "身印两旺用食伤泄气" in seal["rendered_text"]
    assert "不能把食伤一概列为印格忌神" in seal["rendered_text"]
    assert "月刃，不是日坐羊刃" in blade["rendered_text"]
    assert "五阳干" in blade["rendered_text"]
    assert LEDGER["content_revised_original_entries"] == 47
    assert LEDGER["source_attribution_pending_original_entries"] == 35
    assert (
        LEDGER["independent_expert_acceptance"]
        == "not_completed_for_any_of_the_72_original_entries"
    )
