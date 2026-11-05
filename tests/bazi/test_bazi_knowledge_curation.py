"""Editorial/source scope is explicit; it is not a new force-accuracy score."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.services.knowledge import (
    calculate_knowledge_read,
)
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
LEDGER = json.loads((ROOT / "tests/data/bazi/knowledge-reviewed-keys.json").read_text())
CASES = [
    (category, key) for category, keys in LEDGER["curated_keys"].items() for key in keys
]


@pytest.mark.parametrize("key", LEDGER["curated_keys"]["ten_gods"])
def test_ten_god_cards_replace_unqualified_outcomes_with_conditions_and_sources(key):
    result = calculate_knowledge_read(domain="bazi", category="ten_gods", key=key)
    assert "error" not in result
    text = result["rendered_text"]
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
    assert (ROOT / implementation["source_path"]).is_file()

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
    curation = result["provenance"]["entry_curation"]
    assert (
        result["provenance"]["review_status"]
        == "selected_month_command_semantics_not_formation_acceptance"
    )
    assert curation["validation_status"].endswith("not_complete_formation")
    assert curation["source_refs"][0]["source_pdf_pages"][:5] == [26, 27, 28, 29, 30]
    assert (ROOT / curation["implementation_refs"][0]["source_path"]).is_file()


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
