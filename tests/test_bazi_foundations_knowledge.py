"""Additive source-backed concepts preserve the sealed base and public queries."""

import ast
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import knowledge_store
from fatebridge.services.knowledge import (
    calculate_knowledge_read,
    calculate_knowledge_registry,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_foundations_v1"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi-foundations.json"
KEYS = ("四柱", "年柱", "月柱")


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pinned_primary_source_and_quoted_spans_are_reproducible():
    review = load(FIXTURE / "curation-review.json")
    manifest = load(FIXTURE / "source-manifest.json")
    assert digest(BUNDLE) == review["bundle_sha256"]
    assert digest(FIXTURE / "source-manifest.json") == review["source_manifest_sha256"]
    for filename, expected in manifest["files"].items():
        assert digest(FIXTURE / "sources" / filename) == expected
    api = load(FIXTURE / "sources/sanming-vol02-api.json")
    revision = api["query"]["pages"][0]["revisions"][0]
    text = (FIXTURE / "sources/sanming-vol02.wiki").read_text()
    assert revision["revid"] == manifest["revision_id"] == 761691
    assert revision["slots"]["main"]["content"] == text
    for quote in review["source_excerpts"]:
        assert text[quote["start_codepoint"] : quote["end_codepoint"]] == quote["quote"]
        assert (
            hashlib.sha256(quote["quote"].encode()).hexdigest() == quote["quote_sha256"]
        )
    assert not review["old_criteria_changed"] and not review["old_scores_rewritten"]
    assert review["holdout_reruns"] == review["new_independent_chart_cases"] == 0


def test_legacy_files_and_all_85_entry_objects_remain_unchanged():
    review = load(FIXTURE / "curation-review.json")
    for filename, field in [
        (
            "tests/fixtures/bazi_body_vocabulary_knowledge_v2/before/"
            "src/fatebridge/data/knowledge/bazi.json",
            "base_bundle_sha256",
        ),
        (
            "docs/validation/bazi-source-contrast-knowledge-v1/before/src/fatebridge/data/knowledge/index.json",
            "base_index_sha256",
        ),
        ("tests/fixtures/bazi_knowledge_curation_v1/ledger.json", "base_ledger_sha256"),
    ]:
        assert digest(ROOT / filename) == review[field]
    # The original review still binds its exact archived85-entry edition.
    # Current body-vocabulary revisions have separate source and preservation
    # checks; the contrast supplement also preserves all88 preexisting responses.
    base = load(ROOT / "src/fatebridge/data/knowledge/bazi.json")
    merged = knowledge_store.load_knowledge_bundles()["bazi"]
    # The original85-entry edition above remains byte-pinned; the later,
    # separately sourced hidden-rank card is one explicit additional entry.
    assert sum(map(len, base["categories"].values())) == 86
    assert "藏干序位与人元司令" in base["categories"]["classical_force_semantics"]
    for category, entries in base["categories"].items():
        assert merged["categories"][category] == entries
    assert set(merged["categories"]) - set(base["categories"]) == {
        "basics",
        "source_contrasts",
        "source_vocabulary",
    }
    assert set(merged["categories"]["basics"]) == set(KEYS)
    # Old entry provenance does not acquire a different content/source claim.
    old = calculate_knowledge_read(domain="bazi", category="ten_gods", key="正官")
    assert "supplements" not in old["provenance"]


@pytest.mark.parametrize("key", KEYS)
def test_each_concept_separates_primary_program_and_editorial_attribution(key):
    result = calculate_knowledge_read(domain="bazi", key=key)
    assert result["category"] == "basics" and "error" not in result
    curation = result["provenance"]["entry_curation"]
    indices = sum(
        [
            curation[name]
            for name in (
                "source_tip_indices",
                "implementation_tip_indices",
                "editorial_tip_indices",
            )
        ],
        [],
    )
    assert sorted(indices) == list(range(len(result["tips"])))
    assert not curation["source_pending_tip_indices"]
    source = curation["source_refs"][0]
    assert source["revision_id"] == 761691
    assert source["source_sha256"] == digest(FIXTURE / "sources/sanming-vol02.wiki")
    assert source["source_url"] in result["citation"]
    assert source["source_locator"] in result["snapshot_text"]
    assert "PDF " not in result["snapshot_text"]
    assert "非逐字引文" in result["citation"]
    assert curation["independent_expert_review"] == "not_completed"
    assert curation["reality_prediction_efficacy"] == "not_tested"
    for reference in curation["implementation_refs"]:
        assert digest(ROOT / reference["source_path"]) == reference["source_sha256"]
        assert reference["source_sha256"] in result["snapshot_text"]


def test_recorded_program_excerpts_bind_archived_bytes_and_current_function_text():
    review = load(FIXTURE / "curation-review.json")
    path = FIXTURE / "implementation-extracts.json"
    assert digest(path) == review["implementation_extracts_sha256"]
    for row in load(path):
        text = (
            "\n".join(
                (ROOT / row["source_path"])
                .read_text()
                .splitlines()[row["line_start"] - 1 : row["line_end"]]
            )
            + "\n"
        )
        assert text == row["text"]
        assert hashlib.sha256(text.encode()).hexdigest() == row["text_sha256"]
        current = (ROOT / row["current_source_path"]).read_text()
        node = next(
            n
            for n in ast.walk(ast.parse(current))
            if isinstance(n, ast.FunctionDef) and n.name == row["function"]
        )
        actual = (
            "\n".join(current.splitlines()[node.lineno - 1 : node.end_lineno]) + "\n"
        )
        assert actual == row["text"]
    for reference in review["program_snapshots"]:
        assert digest(ROOT / reference["snapshot_path"]) == reference["snapshot_sha256"]
    tree = ast.parse((ROOT / "src/fatebridge/core/almanac.py").read_text())
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "BAZI_MONTH_START_TERMS"
            for t in n.targets
        )
    )
    assert ast.literal_eval(node.value) == review["month_start_terms_mapping"]


def test_registry_exposes_the_supplement_separately_from_the_historical_index():
    registry = calculate_knowledge_registry(domain="bazi")
    domain = registry["domains"][0]
    category = next(c for c in domain["categories"] if c["name"] == "basics")
    assert category["count"] == 3 and set(category["keys"]) == set(KEYS)
    supplement = domain["provenance"]["supplements"][0]
    assert supplement["sha256"] == digest(BUNDLE)
    assert (
        supplement["version"]
        == load(FIXTURE / "curation-review.json")["component_version"]
        == 2
    )
    assert (
        domain["provenance"]["coverage_scope"]
        == "original_index_plus_declared_supplements"
    )
    assert "basics" not in {
        c["name"] for c in domain["provenance"]["coverage"]["categories"]
    }


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("category", [None, "basics"])
def test_concepts_are_identical_on_rest_mcp_cli_with_bare_and_explicit_keys(
    key, category, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "key": key}
    if category is not None:
        payload["category"] = category
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
    assert http.json()["key"] == key
    assert (
        http.json()["provenance"]["entry_curation"]["source_refs"][0]["revision_id"]
        == 761691
    )


@pytest.mark.parametrize("key", KEYS)
def test_strict_projection_preserves_actual_source_and_supplement_on_three_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "key": key}
    fields = [
        "title",
        "lines",
        "citation",
        "provenance.supplements",
        "provenance.entry_curation.source_refs",
    ]
    opts = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
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
    value = business(http.json())
    assert value == business(protocol.structured_content) == business(cli)
    assert "rendered_text" not in value and "snapshot_text" not in value
    assert value["provenance"]["supplements"][0]["sha256"] == digest(BUNDLE)
    assert (
        value["provenance"]["entry_curation"]["source_refs"][0]["revision_id"] == 761691
    )


def test_unknown_terms_stay_errors_and_nested_sources_cannot_mutate_cached_entries():
    missing = calculate_knowledge_read(domain="bazi", key="未收录的基础术语")
    assert missing["error_code"] == "knowledge.bazi.unknown_key"
    first = calculate_knowledge_read(domain="bazi", key="四柱")
    first["provenance"]["entry_curation"]["source_refs"][0]["revision_id"] = 0
    assert (
        calculate_knowledge_read(domain="bazi", key="四柱")["provenance"][
            "entry_curation"
        ]["source_refs"][0]["revision_id"]
        == 761691
    )


@pytest.mark.parametrize("mode", ["replace_category", "shadow_key", "invalid_schema"])
def test_invalid_supplement_cannot_override_old_knowledge(mode, tmp_path, monkeypatch):
    replacement = load(BUNDLE)
    if mode == "replace_category":
        replacement["categories"] = {"ten_gods": {"正官": {"tips": ["wrong"]}}}
    elif mode == "shadow_key":
        replacement["categories"]["basics"]["正官"] = {"tips": ["wrong"]}
    else:
        replacement["schema_version"] = 99
    path = tmp_path / "supplement.json"
    path.write_text(json.dumps(replacement))
    original = knowledge_store._data_path
    knowledge_store.load_knowledge_bundles.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                knowledge_store,
                "_data_path",
                lambda name: (
                    path if name == "bazi-foundations.json" else original(name)
                ),
            )
            with pytest.raises(ValueError):
                knowledge_store.load_knowledge_bundles()
    finally:
        knowledge_store.load_knowledge_bundles.cache_clear()
