"""Keep source voices, every condition and complete public delivery distinct."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.core import knowledge_store
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
)
from tests.support.transports import AS_OF, SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_frontmatter_knowledge_v1"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi-frontmatter.json"
KEYS = ("旺衰与强弱的编者分层", "得时得势得地的判读对象", "五行取用表的适用范围")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_source_bytes_and_five_leaf_images_remain_bound():
    source = read(FIXTURE / "source-binding.json")
    assert sha(ROOT / source["source_djvu_path"]) == source["source_djvu_sha256"]
    assert len(source["source_images_sha256"]) == 5
    for path, expected in source["source_images_sha256"].items():
        assert sha(ROOT / path) == expected


@pytest.mark.parametrize("key", KEYS)
def test_every_statement_keeps_its_author_and_role_without_classifier_credit(key):
    value = calculate_knowledge_read(domain="bazi", key=key)
    c = value["provenance"]["entry_curation"]
    assert c["source_refs"][0]["author"] == "李雨田增补（初学捷径；雨田按）"
    assert (
        c["source_refs"][0]["source_kind"]
        == "additional_digital_witness_single_reader_not_independent_edition"
    )
    assert "source_pdf_pages" not in c["source_refs"][0]
    assert sorted(
        sum(
            [
                c[k]
                for k in [
                    "source_tip_indices",
                    "implementation_tip_indices",
                    "editorial_tip_indices",
                ]
            ],
            [],
        )
    ) == list(range(len(value["tips"])))
    assert c["independent_expert_review"] == "not_completed"
    assert c["reality_prediction_efficacy"] == "not_tested"
    assert not c["numerical_strength_rules_adopted"]
    assert not c["original26_disagreement_gate_closed"]
    assert "非逐字引文" in value["citation"]
    if "separate_Ren_passage" in c:
        other = c["separate_Ren_passage"]
        assert other["source_claim_id"] == "CENSUS-R539"
        assert other["source_pdf_pages"] == [177, 178]
        assert other["no_cross_author_table_merging"]
    for ref in c.get("implementation_refs", []):
        assert (ROOT / ref["source_path"]).is_file()


def test_complete30_row_rendering_preserves_all_candidates_and_global_exclusions():
    actual = calculate_knowledge_read(domain="bazi", key=KEYS[2])
    source = read(FIXTURE / "source-binding.json")["all30_rows"]
    rendered = []
    for element, index in zip("木火土金水", range(2, 7), strict=True):
        head, text = actual["tips"][index].split("：", 1)
        assert head == element
        rendered.extend(text.removesuffix("。").split("；"))
    assert rendered == [row["normalized_source_text"] for row in source]
    binding = actual["provenance"]["entry_curation"]["source_table_binding"]
    assert binding["rows"] == source and len(source) == 30
    assert binding["excluded_contexts"] == ["从", "化", "变格"]
    assert binding["exclusion_tip_index"] == 1
    assert all(
        term in actual["tips"][1] for term in ["正常", "从", "化", "变格", "全部30行"]
    )
    assert not binding["numeric_thresholds_defined"]
    assert not binding["individual_outcome_rules_adopted"]
    assert all(
        row["literal_pillars"] is None
        and row["expected_daymaster_strength"] is None
        and not row["implemented_or_evaluated"]
        for row in source
    )


def test_ambiguous_editorial_vocabulary_is_not_recast_as_a_four_class_oracle():
    words = calculate_knowledge_read(domain="bazi", key=KEYS[0])["tips"]
    assert "不完全一致之处继续保留" in words[2]
    assert "不要拘泥" in words[2]
    assert "常理" in words[3] and "变法" in words[3]
    assert "没有新增四态分类器" in words[5]


@pytest.mark.parametrize(
    "attack",
    [
        "base_category",
        "foundation_category",
        "contrast_category",
        "base_key",
        "foundation_key",
        "contrast_key",
        "duplicate_id",
    ],
)
def test_third_supplement_cannot_shadow_any_existing_layer(
    attack, tmp_path, monkeypatch
):
    value = read(BUNDLE)
    entry = value["categories"]["source_vocabulary"][KEYS[0]]
    categories = {
        "base_category": "ten_gods",
        "foundation_category": "basics",
        "contrast_category": "source_contrasts",
    }
    keys = {
        "base_key": "正官",
        "foundation_key": "四柱",
        "contrast_key": "只换一字与干支联动",
    }
    if attack in categories:
        value["categories"] = {categories[attack]: {KEYS[0]: entry}}
    elif attack in keys:
        value["categories"] = {"source_vocabulary": {keys[attack]: entry}}
    else:
        value["id"] = read(
            ROOT / "src/fatebridge/data/knowledge/bazi-source-contrasts.json"
        )["id"]
    path = tmp_path / "third.json"
    path.write_text(json.dumps(value))
    original = knowledge_store._data_path
    knowledge_store.load_knowledge_bundles.cache_clear()
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(
                knowledge_store,
                "_data_path",
                lambda n: path if n == "bazi-frontmatter.json" else original(n),
            )
            with pytest.raises(ValueError):
                knowledge_store.load_knowledge_bundles()
    finally:
        knowledge_store.load_knowledge_bundles.cache_clear()


def test_cached_source_rows_cannot_be_mutated_by_a_caller():
    first = calculate_knowledge_read(domain="bazi", key=KEYS[2])
    first["provenance"]["entry_curation"]["source_table_binding"]["rows"].clear()
    assert (
        len(
            calculate_knowledge_read(domain="bazi", key=KEYS[2])["provenance"][
                "entry_curation"
            ]["source_table_binding"]["rows"]
        )
        == 30
    )


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("category", [None, "source_vocabulary"])
def test_full_card_is_identical_on_rest_native_mcp_and_cli(
    key, category, surface_calls
):
    spec = SPECS["knowledge_read"]
    payload = dict(domain="bazi", key=key)
    if category:
        payload["category"] = category
    options = dict(include_snapshot_text=False, response_char_limit=0)
    http, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )


@pytest.mark.parametrize("key", KEYS)
def test_source_projection_is_identical_and_keeps_requested_evidence(
    key, surface_calls
):
    spec = SPECS["knowledge_read"]
    payload = dict(domain="bazi", key=key)
    fields = [
        "title",
        "tips",
        "citation",
        "provenance.supplements",
        "provenance.entry_curation.source_refs",
        "provenance.entry_curation.source_binding",
    ]
    if key == KEYS[2]:
        fields.append("provenance.entry_curation.source_table_binding")
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert "snapshot_text" not in http.json() and "rendered_text" not in http.json()


def test_complete_table_can_be_read_from_the_same_budgeted_mcp_run(rest):
    spec = SPECS["knowledge_read"]
    payload = dict(domain="bazi", key=KEYS[2])
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=dict(include_snapshot_text=False, response_char_limit=0),
    )
    assert http.status_code == 200

    async def check():
        async with Client(mcp.app) as client:
            answer = await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": AS_OF,
                    "fields": None,
                    "include_snapshot_text": False,
                    "response_char_limit": 4096,
                },
                raise_on_error=False,
            )
            assert not answer.is_error
            inline = answer.structured_content
            assert len(answer.content[0].text) <= 4096
            ref = inline["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            text, uri, pages = "", ref["first_page_uri"], 0
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                text += page["text"]
                uri = page["next_uri"]
                pages += 1
            assert pages > 1
            assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
            full = json.loads(text)
            assert (
                full["run_metadata"]["run_id"]
                == inline["run_metadata"]["run_id"]
                == manifest["run_metadata"]["run_id"]
            )
            assert business(full) == business(http.json())
            assert (
                full["provenance"]["entry_curation"]["source_table_binding"]["rows"]
                == read(FIXTURE / "source-binding.json")["all30_rows"]
            )

    asyncio.run(check())
