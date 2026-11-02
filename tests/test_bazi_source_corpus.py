"""The complete current source regression corpus must retain negative evidence."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.bazi_source_corpus import (
    digest,
    input_consistency,
    input_index,
    load_registry,
    pillar_values,
    strength_annotation,
    validate_coverage,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_corpus_v1"
REPORT = ROOT / "docs/validation/bazi-source-corpus-first-v1.json.gz"


def report():
    assert digest(REPORT) == REPORT.with_suffix(".gz.sha256").read_text().strip()
    return json.loads(gzip.decompress(REPORT.read_bytes()))


def test_historical_registry_keeps_all_its_chapters_and_original_counterexamples():
    registry = load_registry(ROOT, FIXTURE / "registry.json", current_coverage=False)
    result = report()
    assert set(result["groups"]) == set(registry["groups"])
    assert len(registry["groups"]) == 21
    assert result["record_count"] == 269
    assert result["input_index"]["distinct_four_pillar_inputs"] == 224
    assert result["input_index"]["overlapping_input_records"] == 45
    assert len(result["original_nineteen"]) == 19
    assert all(c["matches"] is False for c in result["original_nineteen"])
    assert len(result["all_distinct_disagreements"]) == 21
    assert {
        (
            c["source_observations"][0]["id"],
            c["source_observations"][0]["actual_strength"],
        )
        for c in result["additional_distinct_disagreements"]
    } == {("DTCW1947-JC-02", "中和"), ("DTCW1947-JH-02", "强")}
    assert result["source_labels_changed"] is False
    assert result["overall_score"] is None
    assert result["new_independent_cases"] == 0


def test_historical_v6_registry_retains_its_full_scope_including_clock_exclusion():
    registry = load_registry(
        ROOT,
        ROOT / "tests/fixtures/bazi_source_corpus_v6/registry.json",
        current_coverage=False,
    )
    prior = load_registry(
        ROOT,
        ROOT / "tests/fixtures/bazi_source_corpus_v5/registry.json",
        current_coverage=False,
    )
    assert registry["groups"] == prior["groups"]
    assert registry["source_sha256"] == prior["source_sha256"]
    assert registry["auxiliary_sha256"] == prior["auxiliary_sha256"]
    assert set(registry["discovery_exclusions"]) - set(
        prior["discovery_exclusions"]
    ) == {"tests/fixtures/bazi_historical_clock_profiles_v1/reference.json"}
    previous = load_registry(ROOT, FIXTURE / "registry.json", current_coverage=False)
    assert len(registry["groups"]) == 25
    assert registry["groups"].items() >= previous["groups"].items()
    assert (
        "tests/fixtures/bazi_body_capacity_v6/reference.json"
        in registry["source_sha256"]
    )
    assert (
        "tests/fixtures/bazi_body_seal_v5_followup_v1/reference.json"
        in registry["source_sha256"]
    )
    assert (
        "tests/fixtures/bazi_root_load_capacity_v2/reference.json"
        in registry["source_sha256"]
    )
    assert (
        "tests/fixtures/bazi_mediated_capacity_v1/reference.json"
        in registry["source_sha256"]
    )
    with pytest.raises(ValueError, match="coverage changed"):
        load_registry(ROOT, FIXTURE / "registry.json")


def test_preserved_v7_keeps_all_old_sources_and_registers_every_new_unit_case():
    previous = load_registry(
        ROOT,
        ROOT / "tests/fixtures/bazi_source_corpus_v6/registry.json",
        current_coverage=False,
    )
    registry = load_registry(
        ROOT,
        ROOT / "tests/fixtures/bazi_source_corpus_v7/registry.json",
        current_coverage=False,
    )
    assert registry["groups"].items() >= previous["groups"].items()
    assert registry["source_sha256"].items() >= previous["source_sha256"].items()
    assert registry["auxiliary_sha256"].items() >= previous["auxiliary_sha256"].items()
    assert registry["discovery_exclusions"] == previous["discovery_exclusions"]
    new_path = "tests/fixtures/bazi_capacity_three_units_v1/reference.json"
    assert set(registry["groups"]) - set(previous["groups"]) == {
        "complete_caid_fenyu_enyuan_v1"
    }
    assert registry["groups"]["complete_caid_fenyu_enyuan_v1"] == new_path
    frozen = json.loads(
        (
            ROOT
            / "docs/validation/bazi-capacity-caid-fenyu-enyuan-v1/source-transcription.json"
        ).read_text()
    )
    current = json.loads((ROOT / new_path).read_text())
    assert current["cases"] == frozen["cases"]
    assert len(current["cases"]) == 12
    assert sum(c["expected_strength"] is None for c in current["cases"]) == 6
    with pytest.raises(ValueError, match="coverage changed"):
        load_registry(ROOT, ROOT / "tests/fixtures/bazi_source_corpus_v6/registry.json")


def test_unknown_and_unannotated_cases_are_distinct_and_neither_passes():
    assert strength_annotation({"expected_strength": None}) == (
        "explicitly_unknown_body_strength",
        None,
    )
    assert strength_annotation({"expected_path": "seal_output"}) == (
        "not_annotated_for_body_strength",
        None,
    )
    with pytest.raises(ValueError, match="do not recode"):
        strength_annotation({"expected_strength": "印重"})
    result = report()
    for group in result["groups"].values():
        assert all(
            r["matches"] is None
            for r in group["rows"]
            if r["expected_strength"] is None
        )


def test_literal_source_inconsistency_is_flagged_without_favorable_repair():
    values = ["丁卯", "丙寅", "辛亥", "庚寅"]
    original = deepcopy(values)
    flags = input_consistency(values)
    assert flags["sexagenary_pairs"] is True
    assert flags["month_stem_matches_recorded_year"] is False
    assert flags["expected_month_stem_under_modern_rule"] == "壬"
    assert flags["literal_source_changed"] is False
    assert flags["historical_birth_datetime_verified"] is False
    assert values == original
    row = next(
        r
        for r in report()["literal_input_consistency_flags"]
        if r["id"] == "DTCW1947-JC-04"
    )
    assert row["pillars"] == original


def test_internal_consistency_never_certifies_a_historical_birth_date():
    values = ["庚子", "戊寅", "丙寅", "癸巳"]
    flags = input_consistency(values)
    assert flags["all_three_modern_checks_match"] is True
    assert flags["historical_birth_datetime_verified"] is False
    assert (
        pillar_values({"pillars": dict(zip(("year", "month", "day", "hour"), values))})
        == values
    )
    with pytest.raises(ValueError, match="do not guess"):
        pillar_values({"pillars": ["甲", *values[1:]]})


def test_conflicting_source_labels_remain_separate_observations():
    rows = [
        {
            "pillars": ["甲子"] * 4,
            "group": group,
            "id": group,
            "label_status": "annotated_body_strength",
            "expected_strength": label,
        }
        for group, label in [("one", "强"), ("two", "弱")]
    ]
    index = input_index(rows)
    assert index["distinct_four_pillar_inputs"] == 1
    assert len(index["conflicting_body_annotations"]) == 1
    assert index["conflicting_body_annotations"][0]["observations"] == [
        {k: v for k, v in row.items() if k != "pillars"} for row in rows
    ]


def test_new_reference_cannot_silently_escape_coverage(tmp_path):
    reference = tmp_path / "tests/fixtures/bazi_new/reference.json"
    reference.parent.mkdir(parents=True)
    reference.write_text('{"cases": []}')
    registry = {
        "discovery_glob": "tests/fixtures/bazi*/reference.json",
        "groups": {},
        "discovery_exclusions": {},
    }
    with pytest.raises(ValueError, match="coverage changed"):
        validate_coverage(tmp_path, registry)


def test_strict_local_direction_ties_and_incomparables_are_not_counted_as_passes():
    result = report()
    directions = [
        c
        for c in result["local_and_negative_claims"]
        if c["kind"] == "local_clash_labels"
    ]
    assert sum(c["matches"] is True for c in directions) == 8
    assert sum(c["matches"] is False for c in directions) == 4
    assert sum(c["matches"] is None for c in directions) == 1
    assert result["classical_acceptance_passed"] is False


def test_selected_public_replay_does_not_mutate_other_studies():
    from scripts.audit_bazi_clash_current import GROUPS, audit

    before = dict(GROUPS)
    result = audit(
        {"retained_legacy_guard": "tests/fixtures/bazi-strength-reference.json"}
    )
    assert GROUPS == before
    assert list(result["groups"]) == ["retained_legacy_guard"]
    assert result["groups"]["retained_legacy_guard"]["matched"] == 21
    assert result["source_drift"] == []
