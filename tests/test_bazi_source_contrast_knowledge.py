"""Queryable source distinctions preserve every existing response and old gate."""

import asyncio
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

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
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-contrast-knowledge-v1"
FIXTURE = ROOT / "tests/fixtures/bazi_source_contrast_knowledge_v1"
BUNDLE = ROOT / "src/fatebridge/data/knowledge/bazi-source-contrasts.json"
KEY = "只换一字与干支联动"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_every_existing88_complete_service_response_is_unchanged():
    before = read(STUDY / "all88-services-before-first.json")
    assert len(before) == 88
    for name, expected in before.items():
        category, key = name.split("/", 1)
        assert_read_matches_before_repair(
            category,
            key,
            calculate_knowledge_read(domain="bazi", category=category, key=key),
        )
    protocol = read(FIXTURE / "protocol.json")
    for name in [
        "src/fatebridge/data/knowledge/bazi.json",
        "src/fatebridge/data/knowledge/bazi-foundations.json",
        "src/fatebridge/data/knowledge/index.json",
        "tests/fixtures/bazi_knowledge_curation_v1/ledger.json",
    ]:
        edition = ROOT / name
        if name == "src/fatebridge/data/knowledge/bazi.json":
            edition = (
                ROOT / "docs/validation/bazi-source-contrast-knowledge-v1/before" / name
            )
        elif name == "src/fatebridge/data/knowledge/index.json":
            edition = (
                ROOT / "docs/validation/bazi-source-contrast-knowledge-v1/before" / name
            )
        assert digest(edition) == protocol["before_files_sha256"][name]


def test_all15_source_comparisons_and14_unknown_alternatives_are_bound():
    binding = read(FIXTURE / "source-bindings.json")
    protocol = read(FIXTURE / "protocol.json")
    assert (
        digest(FIXTURE / "protocol.json")
        == (FIXTURE / "protocol.sha256").read_text().strip()
    )
    assert (
        digest(FIXTURE / "source-bindings.json") == protocol["source_bindings_sha256"]
    )
    actual = calculate_knowledge_read(domain="bazi", key=KEY)
    curation = actual["provenance"]["entry_curation"]
    linked = curation["source_contrast_binding"]
    assert linked["all15_printed_pairs"] == binding["all15_printed_pair_results"]
    assert (
        linked["all14_unprinted_relational_cases"]
        == binding["all14_unprinted_relational_cases"]
    )
    assert len(linked["all15_printed_pairs"]) == 15
    assert len(linked["all14_unprinted_relational_cases"]) == 14
    assert all(
        not any(r["literal_pillars"].values())
        for r in linked["all14_unprinted_relational_cases"]
    )
    assert (
        linked["all_original_questions_retained"]
        == binding["all_original_questions_retained"]
    )
    assert len(linked["all_original_questions_retained"]["original22"]) == 22
    assert len(linked["all_original_questions_retained"]["input4"]) == 4
    assert linked["source_questions_closed"] == 0
    assert not linked["force_comparison_allowed"] and not linked["causal_acceptance"]


def test_all_three_rendered_examples_match_source_pillars_and_keep_cautions():
    actual = calculate_knowledge_read(domain="bazi", key=KEY)
    rows = {
        r["after_case_id"]: r
        for r in read(FIXTURE / "source-bindings.json")["all15_printed_pair_results"]
    }
    for index, identity in [(3, "MAIN-C363"), (4, "MAIN-C202"), (5, "MAIN-C394")]:
        source = rows[identity]
        for side in ["before_case", "after_case"]:
            text = "、".join(
                source[side]["literal_pillars"][k]
                for k in ["year", "month", "day", "hour"]
            )
            assert text in actual["tips"][index]
    assert "不能把这个比较说成只单独改变辛金" in actual["tips"][4]
    assert "年干和月支仍都改变" in actual["tips"][5]
    curation = actual["provenance"]["entry_curation"]
    assert sorted(
        sum(
            [
                curation[k]
                for k in [
                    "source_tip_indices",
                    "implementation_tip_indices",
                    "editorial_tip_indices",
                ]
            ],
            [],
        )
    ) == list(range(8))
    assert curation["source_refs"][0]["author"] == "任鐵樵增注（任氏曰）"
    assert curation["source_refs"][1]["author"] == "李雨田增補"
    assert curation["independent_expert_review"] == "not_completed"
    assert curation["reality_prediction_efficacy"] == "not_tested"
    for ref in curation["implementation_refs"]:
        assert digest(ROOT / ref["source_path"]) == ref["source_sha256"]
    assert "非逐字引文" in actual["citation"]


def test_builder_is_reproducible_and_readonly():
    before = BUNDLE.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_bazi_source_contrast_knowledge.py"),
            "--check",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert BUNDLE.read_bytes() == before


def test_registry_declares_supplements_without_changing_old_provenance():
    registry = calculate_knowledge_registry(domain="bazi")
    domain = registry["domains"][0]
    new = next(c for c in domain["categories"] if c["name"] == "source_contrasts")
    assert new["count"] == 1 and new["keys"] == [KEY]
    supplements = domain["provenance"]["supplements"]
    assert [s["source_file"] for s in supplements] == [
        "data/knowledge/bazi-foundations.json",
        "data/knowledge/bazi-source-contrasts.json",
        "data/knowledge/bazi-frontmatter.json",
    ]
    assert supplements[1]["sha256"] == digest(BUNDLE)
    actual = calculate_knowledge_read(domain="bazi", key=KEY)
    assert actual["provenance"]["supplements"] == [supplements[1]]
    assert calculate_knowledge_read(domain="bazi", key="四柱")["provenance"][
        "supplements"
    ] == [supplements[0]]
    assert (
        "supplements"
        not in calculate_knowledge_read(domain="bazi", key="正官")["provenance"]
    )


@pytest.mark.parametrize(
    "mode",
    [
        "base_category",
        "foundation_category",
        "base_key",
        "foundation_key",
        "duplicate_id",
        "invalid_version",
    ],
)
def test_second_supplement_cannot_shadow_any_existing_entry(
    mode, tmp_path, monkeypatch
):
    value = copy.deepcopy(read(BUNDLE))
    entry = value["categories"]["source_contrasts"][KEY]
    if mode == "base_category":
        value["categories"] = {"ten_gods": {KEY: entry}}
    elif mode == "foundation_category":
        value["categories"] = {"basics": {KEY: entry}}
    elif mode == "base_key":
        value["categories"] = {"source_contrasts": {"正官": entry}}
    elif mode == "foundation_key":
        value["categories"] = {"source_contrasts": {"四柱": entry}}
    elif mode == "duplicate_id":
        value["id"] = read(
            ROOT / "src/fatebridge/data/knowledge/bazi-foundations.json"
        )["id"]
    else:
        value["version"] = True
    path = tmp_path / "second.json"
    path.write_text(json.dumps(value, ensure_ascii=False))
    original = knowledge_store._data_path
    knowledge_store.load_knowledge_bundles.cache_clear()
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(
                knowledge_store,
                "_data_path",
                lambda n: path if n == "bazi-source-contrasts.json" else original(n),
            )
            with pytest.raises(ValueError):
                knowledge_store.load_knowledge_bundles()
    finally:
        knowledge_store.load_knowledge_bundles.cache_clear()


def test_new_entry_nested_evidence_cannot_mutate_cached_values():
    first = calculate_knowledge_read(domain="bazi", key=KEY)
    first["provenance"]["entry_curation"]["source_contrast_binding"][
        "all15_printed_pairs"
    ][0]["after_case"]["literal_pillars"]["day"] = "甲子"
    again = calculate_knowledge_read(domain="bazi", key=KEY)
    assert (
        again["provenance"]["entry_curation"]["source_contrast_binding"][
            "all15_printed_pairs"
        ]
        == read(FIXTURE / "source-bindings.json")["all15_printed_pair_results"]
    )


@pytest.mark.parametrize("category", [None, "source_contrasts"])
@pytest.mark.parametrize("include_snapshot", [False, True])
def test_complete_card_is_identical_on_rest_mcp_and_cli(
    category, include_snapshot, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "key": KEY}
    if category:
        payload["category"] = category
    options = {"include_snapshot_text": include_snapshot, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--include-snapshot-text",
            str(include_snapshot).lower(),
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert (
        len(
            http.json()["provenance"]["entry_curation"]["source_contrast_binding"][
                "all15_printed_pairs"
            ]
        )
        == 15
    )


def test_strict_source_projection_matches_on_three_transports(rest, tmp_path, capsys):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "key": KEY}
    fields = [
        "title",
        "tips",
        "citation",
        "provenance.supplements",
        "provenance.entry_curation.source_refs",
        "provenance.entry_curation.source_contrast_binding",
    ]
    options = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
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
