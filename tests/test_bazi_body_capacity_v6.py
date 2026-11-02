"""Complete chapters and old failures remain visible when a hypothesis fails."""

import gzip
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_body_capacity_v6"
REPORT = ROOT / "docs/validation/bazi-body-capacity-first-v6.json.gz"


def frozen(path):
    assert (
        sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(path.read_text())


def report():
    assert (
        sha256(REPORT.read_bytes()).hexdigest()
        == REPORT.with_suffix(".gz.sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(REPORT.read_bytes()))


def test_all_three_complete_units_and_unknown_labels_were_frozen_before_comparison():
    protocol = frozen(FIXTURE / "protocol.json")
    reference = frozen(FIXTURE / "reference.json")
    assert (
        reference["protocol_sha256"]
        == sha256((FIXTURE / "protocol.json").read_bytes()).hexdigest()
    )
    assert reference["chapter_case_counts"] == {"燥湿": 4, "隐显": 2, "众寡": 3}
    assert len(reference["cases"]) == 9
    assert sum(c["expected_strength"] is None for c in reference["cases"]) == 6
    assert all(c["new_nonoverlap_input"] for c in reference["cases"])
    assert (
        sha256((FIXTURE / "candidate-v5.py.txt").read_bytes()).hexdigest()
        == protocol["operators"]["hidden_seal_v5_sha256"]
    )
    assert (FIXTURE / "candidate-v5.py.txt").read_bytes() == (
        ROOT / "tests/fixtures/bazi_root_force_experiment_v5/candidate.py.txt"
    ).read_bytes()


def test_failed_fresh_gain_gate_and_every_old_group_remain_failed_or_preserved():
    result = report()
    assert result["fresh_summary"]["matches"] == {
        "production_v6": 0,
        "capacity_v3": 0,
        "hidden_seal_v5": 0,
    }
    assert result["fresh_summary"]["unknown_body"] == 6
    assert result["adoption_gates"]["new_nonoverlap_v5_specific_gain"] is False
    assert (
        result["adoption_gates"][
            "frozen_production_receipts_reproduce_all_previous_records"
        ]
        is True
    )
    assert result["adopted"] is False and result["source_labels_changed"] is False
    assert len(result["groups"]) == 22
    assert all(
        r["matches"]["production_v6"] is None
        for r in result["groups"]["three_complete_units"]
        if r["expected_strength"] is None
    )


def test_frozen_numerical_kernel_reproduces_the_entire_first_result(tmp_path):
    output = tmp_path / "replay.json.gz"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_body_capacity_v6.py"),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 1, process.stderr  # Failed adoption gate, not a crash.
    replay = json.loads(gzip.decompress(output.read_bytes()))
    before = report()
    before.pop("recorded_at_utc")
    replay.pop("recorded_at_utc")
    assert replay == before


def test_added_semantics_preserve_all_preceding_78_cards_and_old_pending_counts():
    review = frozen(FIXTURE / "knowledge-review.json")
    previous = json.loads((FIXTURE / "knowledge-before.json").read_text())
    # This immutable review binds the 82-card edition before a later,
    # separately reviewed correction of fourteen existing topic cards.
    after_path = (
        ROOT
        / "tests/fixtures/bazi_topic_knowledge_v2/before/src/fatebridge/data/knowledge/bazi.json"
    )
    assert (
        sha256(after_path.read_bytes()).hexdigest() == review["current_bundle_sha256"]
    )
    current = json.loads(after_path.read_text())
    assert (
        sha256((FIXTURE / "knowledge-before.json").read_bytes()).hexdigest()
        == review["previous_bundle_sha256"]
    )
    for cat, values in previous["categories"].items():
        for key, value in values.items():
            assert current["categories"][cat][key] == value
    assert sum(map(len, previous["categories"].values())) == 78
    assert (
        sum(map(len, current["categories"].values())) == review["current_total"] == 82
    )
    assert review["source_attribution_pending_original_entries"] == 50
    assert review["new_independent_cases"] == 0
    assert review["production_strength_policy_changed"] is False


@pytest.mark.parametrize(
    "key", ["燥湿与生发条件", "物理藏根与功能根", "隐显与制化", "众寡与日主符合"]
)
def test_public_semantic_cards_publish_named_source_and_unadjudicated_force(key):
    result = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key=key
    )
    assert "error" not in result
    curation = result["provenance"]["entry_curation"]
    assert (
        curation["validation_status"] == "text_semantics_not_model_force_adjudication"
    )
    source = curation["source_refs"][0]
    assert (
        source["source_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert source["source_pdf_pages"] and source["edition"] in result["snapshot_text"]
    assert source["source_url"] in result["citation"]


def test_source_body_and_whole_chart_balance_are_not_relabelled_to_match_weak_model():
    reference = frozen(FIXTURE / "reference.json")
    row = next(c for c in reference["cases"] if c["id"] == "DTCW1947-ZQ-03")
    assert row["expected_strength"] == "强"
    assert "成平" in row["source_anchor"]
    card = calculate_knowledge_read(
        domain="bazi", category="classical_force_semantics", key="众寡与日主符合"
    )
    assert "全局成平不等于日主必为中和" in card["rendered_text"]


def test_additional_exposed_replay_includes_the_other_study_without_fresh_credit(
    tmp_path,
):
    output = tmp_path / "expanded.json.gz"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_bazi_body_capacity_v6.py"),
            "--additional-exposed-reference",
            "tests/fixtures/bazi_body_seal_v5_followup_v1/reference.json",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert process.returncode == 1, process.stderr
    expanded = json.loads(gzip.decompress(output.read_bytes()))
    assert len(expanded["groups"]) == 23
    assert sum(len(rows) for rows in expanded["groups"].values()) == 304
    assert expanded["fresh_summary"] == report()["fresh_summary"]
    assert expanded["additional_exposed_replay"]["new_independent_cases"] == 0
    row = next(
        r
        for r in expanded["groups"]["additional_exposed_followup"]
        if r["id"] == "DTCW1947-FJ06"
    )
    assert row["expected_strength"] is None
    assert all(value is None for value in row["matches"].values())
