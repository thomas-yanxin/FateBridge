"""Keep rejected strength witnesses, whole-source failures and old cards visible."""

import asyncio
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_mediated_capacity_v1"
KEYS = ("暖局与用神", "日元强弱与性情措辞", "根位与有效接引")
DEVELOPMENT = (
    ROOT / "docs/validation/bazi-mediated-capacity-development-first-v1.json.gz"
)
PROSPECTIVE = (
    ROOT / "docs/validation/bazi-mediated-capacity-prospective-first-v1.json.gz"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return read(path)


def report(path):
    assert digest(path) == path.with_suffix(".gz.sha256").read_text().strip()
    return json.loads(gzip.decompress(path.read_bytes()))


def test_development_preserves_every_full_object_and_every_failed_constraint():
    protocol = frozen("protocol.json")
    result = report(DEVELOPMENT)
    old = json.loads(gzip.decompress((FIXTURE / "baseline314.json.gz").read_bytes()))
    assert result["protocol_sha256"] == digest(FIXTURE / "protocol.json")
    assert digest(FIXTURE / "candidate.py.txt") == protocol["candidate_sha256"]
    assert result["summary"]["records"] == len(result["rows"]) == 314
    assert result["summary"]["exact_labeled_records"] == 105
    assert result["summary"]["matching_records"]["production_v6"] == 79
    assert result["summary"]["matching_records"]["mediated_v1"] == 87
    assert len(result["summary"]["improvements"]) == 8
    assert not result["summary"]["regressions"]
    index = {(r["group"], r["id"]): r for r in result["rows"]}
    for group, data in old["groups"].items():
        for before in data["rows"]:
            current = index[group, before["id"]]
            assert current["assessment"] == before["assessment"]
            assert current["pillars"] == before["pillars"]
            assert current["expected_strength"] == before["expected_strength"]
    assert [
        (r["claim"]["id"], r["baseline_matches"], r["candidate_matches"])
        for r in result["negative_constraints"]
    ] == [("GH-07", True, True), ("DTCW1947-SJ05", False, False)]
    assert result["development_gate"] and not result["adopted"]
    for relative, item in protocol["numerical_dependencies"].items():
        assert digest(FIXTURE / item["archive"]) == item["sha256"]


def test_whole_new_unit_zero_gain_is_not_rewritten_as_adoption():
    result = report(PROSPECTIVE)
    reference, freeze = frozen("reference.json"), frozen("reference-freeze.json")
    assert result["reference_sha256"] == digest(FIXTURE / "reference.json")
    assert freeze["known_labels"] == result["summary"]["exact_labeled_records"] == 10
    assert freeze["unknown_labels"] == result["summary"]["unknown_records"] == 25
    assert len(result["rows"]) == len(reference["cases"]) == 35
    for before, row in zip(reference["cases"], result["rows"], strict=True):
        assert all(row[k] == v for k, v in before.items())
    assert result["summary"]["matching_records"] == {
        "production_v6": 9,
        "root_load_v2": 9,
        "capacity_v3": 8,
        "hidden_seal_v5": 8,
        "mediated_v1": 9,
    }
    assert (
        result["nonoverlap_records"] == 35
        and result["nonoverlap_labeled_records"] == 10
    )
    assert not result["nonoverlap_gains"]
    assert not result["gates"]["at_least_one_nonoverlap_gain_over_production"]
    assert not result["gates"]["new_cohort_complementarity_beyond_each_control"]
    assert not result["adopted"] and not result["production_default_changed"]
    assert not result["full_goal_complete"] and result["overall_score"] is None
    assert result["real_world_efficacy"] == "not_tested"
    unknown = {r["id"] for r in reference["cases"] if r["expected_strength"] is None}
    assert {
        "DTCW1947-XQ-03",
        "DTCW1947-XQ-08",
        "DTCW1947-XQ-09",
        "DTCW1947-XQ-31",
    } <= unknown
    error = next(r for r in result["rows"] if r["id"] == "DTCW1947-XQ-30")
    assert error["pillars"] == ["庚午", "乙酉", "庚午", "壬午"]
    assert error["expected_strength"] == "弱"
    assert set(error["grades"].values()) == {"强"}


def test_complete_v5_corpus_retains_every_old314_object_and_the_new_failure():
    result = report(ROOT / "docs/validation/bazi-source-corpus-first-v5.json.gz")
    old = report(ROOT / "docs/validation/bazi-source-corpus-first-v4.json.gz")
    assert len(result["groups"]) == 25
    assert result["record_count"] == 349
    assert result["input_index"]["distinct_four_pillar_inputs"] == 303
    assert len(result["all_distinct_disagreements"]) == 26
    assert len(result["original_nineteen"]) == 19
    assert all(r["matches"] is False for r in result["original_nineteen"])
    assert all(result["groups"][k] == v for k, v in old["groups"].items())
    assert result["production_strength_policy_changed"] is False
    assert not result["classical_acceptance_passed"]


@pytest.mark.parametrize(
    "script,first,expected_code",
    [
        ("audit_bazi_mediated_capacity.py", DEVELOPMENT, 0),
        ("audit_bazi_mediated_prospective.py", PROSPECTIVE, 1),
    ],
)
def test_fresh_process_replays_complete_first_result_and_refuses_overwrite(
    script, first, expected_code, tmp_path
):
    output = tmp_path / "complete.json.gz"
    command = [sys.executable, str(ROOT / "scripts" / script), "--output", str(output)]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == expected_code, run.stdout + run.stderr
    actual, original = report(output), report(first)
    assert {k: v for k, v in actual.items() if k != "recorded_at_utc"} == {
        k: v for k, v in original.items() if k != "recorded_at_utc"
    }
    previous = output.read_bytes()
    repeated = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert repeated.returncode == 2 and output.read_bytes() == previous


def test_corrupted_protocol_fails_before_any_candidate_can_run(tmp_path, monkeypatch):
    path = ROOT / "scripts/audit_bazi_mediated_capacity.py"
    spec = importlib.util.spec_from_file_location("_mediated_corruption", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("protocol.json", "protocol.sha256"):
        shutil.copy2(FIXTURE / name, tmp_path / name)
    (tmp_path / "protocol.json").write_text("{}")
    monkeypatch.setattr(module, "FIXTURE", tmp_path)
    with pytest.raises(ValueError, match="Frozen input changed"):
        module.audit()


def test_all82_previous_cards_are_identical_and_inventory_is_not_acceptance():
    review = frozen("knowledge-review.json")
    protocol = frozen("knowledge-extension-protocol.json")
    bundle = Path("src/fatebridge/data/knowledge/bazi.json")
    old_path = FIXTURE / "before" / bundle
    assert digest(old_path) == review["previous_bundle_sha256"]
    # Bind the exact85-card after-edition of this historical three-card review.
    # The later five-element review guards all80 other current objects separately.
    after = ROOT / "tests/fixtures/bazi_element_knowledge_v1/before"
    assert digest(after / bundle) == review["current_bundle_sha256"]
    before, current = read(old_path), read(after / bundle)
    assert sum(map(len, before["categories"].values())) == 82
    assert sum(map(len, current["categories"].values())) == 85
    assert all(
        current["categories"][c][k] == v
        for c, entries in before["categories"].items()
        for k, v in entries.items()
    )
    assert set(current["categories"]["classical_force_semantics"]) - set(
        before["categories"]["classical_force_semantics"]
    ) == set(KEYS)
    assert protocol["targets"] == list(KEYS)
    ledger_path = Path("tests/fixtures/bazi_knowledge_curation_v1/ledger.json")
    old, new = read(FIXTURE / "before" / ledger_path), read(after / ledger_path)
    for key in [
        "original_entries",
        "revised_original_entries",
        "remaining_legacy_entries",
        "source_attribution_pending_original_entries",
        "health_source_attribution_pending_entries",
        "topic_partial_attribution_pending_entries",
        "independent_expert_acceptance",
    ]:
        assert new[key] == old[key]
    assert new["source_attribution_pending_original_entries"] == 40
    assert new["current_total"] == 85 and new["curated_total"] == 55
    assert review["new_independent_cases_from_cards"] == 0
    assert not review["production_strength_policy_changed"]


@pytest.mark.parametrize("key", KEYS)
def test_new_source_conditions_survive_rest_native_mcp_and_cli(
    key, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    payload = {"domain": "bazi", "category": "classical_force_semantics", "key": key}
    options = {"include_snapshot_text": True, "response_char_limit": 0}
    http = rest.post(spec.rest_path, json=payload, params=options)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--include-snapshot-text", "true", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    value = http.json()
    curation = value["provenance"]["entry_curation"]
    assert (
        curation["source_refs"][0]["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert (
        curation["review_status"]
        == "single_developer_source_reading_external_review_pending"
    )
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    assert curation["source_refs"][0]["edition"] in value["snapshot_text"]
    if key == "日元强弱与性情措辞":
        assert len(value["tips"]) == 8
        assert curation["method_id"] == "dtcw1947_body_vocabulary_semantics_v3"
        assert curation["entry_revision"] == 3
        assert len(curation["source_relation_binding"]["rows"]) == 20
    else:
        assert len(value["tips"]) == 5
        assert curation["entry_revision"] == 1
    if key == "暖局与用神":
        assert "用神必在酉金" in value["snapshot_text"]
        assert "用神不在丙火而在辰土" in value["snapshot_text"]
