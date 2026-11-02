"""A source correction reaches public knowledge without rewriting old editions."""

import asyncio
import hashlib
import json
from pathlib import Path

from fatebridge.services.knowledge import calculate_knowledge_read
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_current_collation_v1"
HISTORICAL_AFTER = ROOT / "tests/fixtures/bazi_mediated_capacity_v1/before"
TARGET = ("classical_force_semantics", "物理藏根与功能根")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return read(path)


def test_only_one_named_card_changes_and_all_81_other_cards_remain_exact():
    protocol = frozen("knowledge-supplement-protocol.json")
    review = frozen("knowledge-review.json")
    bundle = Path("src/fatebridge/data/knowledge/bazi.json")
    old_path = FIXTURE / "before" / bundle
    assert digest(old_path) == protocol["before_sha256"][str(bundle)]
    assert digest(old_path) == review["previous_bundle_sha256"]
    # The frozen one-card review binds its exact82-card after-edition.
    # The later three-card addition separately guards all82oldobjects.
    assert digest(HISTORICAL_AFTER / bundle) == review["current_bundle_sha256"]
    before, current = read(old_path), read(HISTORICAL_AFTER / bundle)
    assert {k: v for k, v in before.items() if k != "categories"} == {
        k: v for k, v in current.items() if k != "categories"
    }
    assert set(before["categories"]) == set(current["categories"])
    changes, preserved = [], 0
    for category, entries in before["categories"].items():
        assert set(entries) == set(current["categories"][category])
        for key, value in entries.items():
            if value != current["categories"][category][key]:
                changes.append((category, key))
            else:
                preserved += 1
    assert changes == [TARGET]
    assert preserved == review["other_entries_preserved"] == 81
    old = before["categories"][TARGET[0]][TARGET[1]]
    new = current["categories"][TARGET[0]][TARGET[1]]
    assert new["tips"][:4] == old["tips"]
    assert len(new["tips"]) == 7
    assert new["curation"]["entry_revision"] == old["curation"]["entry_revision"] + 1
    assert new["curation"]["source_refs"][:-1] == old["curation"]["source_refs"]
    assert (
        digest(
            ROOT
            / "tests/fixtures/bazi_topic_knowledge_v2/before/src/fatebridge/data/knowledge/index.json"
        )
        == protocol["index_sha256"]
    )


def test_pending_counts_and_original_topic_review_keep_their_original_meaning():
    review = frozen("knowledge-review.json")
    ledger_path = Path("tests/fixtures/bazi_knowledge_curation_v1/ledger.json")
    before, current = (
        read(FIXTURE / "before" / ledger_path),
        read(HISTORICAL_AFTER / ledger_path),
    )
    for key in before:
        if key not in {"current_bundle_sha256", "scope"}:
            assert before[key] == current[key], key
    assert current["current_total"] == 82
    assert current["source_attribution_pending_original_entries"] == 40
    assert current["current_bundle_sha256"] == review["current_bundle_sha256"]
    assert current["independent_expert_acceptance"].startswith("not_completed")
    historical = read(ROOT / "tests/fixtures/bazi_topic_knowledge_v2/review.json")
    assert historical["current_bundle_sha256"] == review["previous_bundle_sha256"]
    assert not review["adoption_gates_changed"]
    assert not review["production_strength_policy_changed"]


def test_same_source_root_contrast_is_queryable_and_snapshot_keeps_final_judgment():
    result = calculate_knowledge_read(domain="bazi", category=TARGET[0], key=TARGET[1])
    assert "error" not in result
    assert "最终以癸水仍得通根判戊癸合而不化" in result["rendered_text"]
    assert "后造才明言合而必化" in result["snapshot_text"]
    curation = result["provenance"]["entry_curation"]
    assert curation["entry_revision"] == 2
    source = curation["source_refs"][-1]
    assert source["source_pdf_pages"] == [209, 210]
    assert source["source_sha256"] == (
        "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["edition"] in result["snapshot_text"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    indices = sum(
        (
            curation[k]
            for k in (
                "classical_condition_tip_indexes",
                "implementation_tip_indexes",
                "editorial_tip_indexes",
            )
        ),
        [],
    )
    assert sorted(indices) == list(range(7))


def test_current_root_card_is_identical_on_rest_native_mcp_and_cli(
    rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": TARGET[0], "key": TARGET[1]}
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
    assert http.json()["provenance"]["entry_curation"]["entry_revision"] == 2
