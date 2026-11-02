"""Keep source voices, every condition and complete public delivery distinct."""

import asyncio
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.core import knowledge_store
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.knowledge_refactor_reference import (
    assert_read_matches_before_repair,
    baseline,
)
from tests.knowledge_refactor_reference import digest as refactor_digest
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-frontmatter-knowledge-v1"
FIXTURE = ROOT / "tests/fixtures/bazi_frontmatter_knowledge_v1"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi-frontmatter.json"
KEYS = ("旺衰与强弱的编者分层", "得时得势得地的判读对象", "五行取用表的适用范围")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all89_existing_full_service_outputs_and_raw_bundles_are_exact():
    before = read(STUDY / "all89-service-responses-before-first.json")
    assert len(before) == 89
    for name, expected in before.items():
        category, key = name.split("/", 1)
        assert_read_matches_before_repair(
            category,
            key,
            calculate_knowledge_read(domain="bazi", category=category, key=key),
        )
    protocol = read(FIXTURE / "protocol.json")
    for name in [
        "bazi.json",
        "bazi-foundations.json",
        "bazi-source-contrasts.json",
        "index.json",
    ]:
        path = "src/fatebridge/data/knowledge/" + name
        edition = ROOT / path
        if name == "bazi.json":
            edition = (
                ROOT
                / "docs/validation/bazi-body-vocabulary-knowledge-v3/current-workspace"
                / path
            )
        elif name == "index.json":
            edition = (
                ROOT / "docs/validation/bazi-source-contrast-knowledge-v1/before" / path
            )
        assert sha(edition) == protocol["prechange_hashes"][path]
    assert (
        refactor_digest(
            {
                k: v
                for k, v in knowledge_store.load_knowledge_bundles().items()
                if k != "bazi"
            }
        )
        == baseline()["other_domain_bundles_sha256"]
    )


def test_registry_adds_only_one_category_and_one_declared_supplement():
    before = read(STUDY / "registry-before-first.json")["domains"][0]
    after = calculate_knowledge_registry(domain="bazi")["domains"][0]
    assert (
        refactor_digest(calculate_knowledge_registry(domain="bazi"))
        == baseline()["registry_sha256"]
    )
    # The later source-bound hidden-rank card adds one explicit member.
    category = next(
        c for c in before["categories"] if c["name"] == "classical_force_semantics"
    )
    assert "藏干序位与人元司令" not in category["keys"]
    category["keys"] = sorted([*category["keys"], "藏干序位与人元司令"])
    category["count"] += 1
    assert after["categories"][:-1] == before["categories"]
    assert after["categories"][-1] == dict(
        name="source_vocabulary", count=3, keys=sorted(KEYS), supports=["read"]
    )
    assert (
        after["provenance"]["supplements"][:-1] == before["provenance"]["supplements"]
    )
    supplement = after["provenance"]["supplements"][-1]
    assert supplement["source_file"] == "data/knowledge/bazi-frontmatter.json"
    assert supplement["sha256"] == sha(BUNDLE)
    for key in KEYS:
        assert calculate_knowledge_read(domain="bazi", key=key)["provenance"][
            "supplements"
        ] == [supplement]


def test_all_source_bytes_and_five_leaf_images_remain_bound():
    source = read(FIXTURE / "source-binding.json")
    protocol = read(FIXTURE / "protocol.json")
    assert (
        sha(FIXTURE / "protocol.json")
        == "3cd171eef27321afb8af3702efe02ac32b65d003239fdc24b9cfcc5538d13268"
    )
    assert sha(FIXTURE / "source-binding.json") == protocol["source_binding_sha256"]
    for path_key, hash_key in [
        ("source_djvu_path", "source_djvu_sha256"),
        ("source_supplement_path", "source_supplement_sha256"),
        ("gap_review_path", "gap_review_sha256"),
    ]:
        assert sha(ROOT / source[path_key]) == source[hash_key]
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
        assert sha(STUDY / "before" / ref["source_path"]) == ref["source_sha256"]


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


def test_builder_is_reproducible_readonly_and_preserves_existing_generators():
    before = BUNDLE.read_bytes()
    for script in [
        "build_bazi_frontmatter_knowledge.py",
        "build_bazi_source_contrast_knowledge.py",
        "build_bazi_four_state_knowledge.py",
    ]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert BUNDLE.read_bytes() == before


@pytest.mark.parametrize(
    "attack", ["curation-plan.json", "cross-reference-binding.json"]
)
def test_rebound_editorial_plan_or_cross_reference_is_rejected(attack, tmp_path):
    fixture = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture)
    path = fixture / attack
    value = read(path)
    if attack == "curation-plan.json":
        value["cards"][0]["tips"][0] = "Unreviewed replacement"
    else:
        value["binding"]["source_pdf_pages"] = [999]
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    path.with_suffix(".sha256").write_text(sha(path) + "\n")
    namespace = runpy.run_path(
        str(ROOT / "scripts/build_bazi_frontmatter_knowledge.py")
    )
    build = namespace["expected_bundle"]
    build.__globals__["FIXTURE"] = fixture
    with pytest.raises(ValueError, match="Reviewed.*changed"):
        build()


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
    key, category, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = dict(domain="bazi", key=key)
    if category:
        payload["category"] = category
    options = dict(include_snapshot_text=False, response_char_limit=0)
    http = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
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


@pytest.mark.parametrize("key", KEYS)
def test_source_projection_is_identical_and_keeps_requested_evidence(
    key, rest, tmp_path, capsys
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
    http = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
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
