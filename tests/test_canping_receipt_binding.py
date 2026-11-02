"""Same-result narrative, source roles and clock policies must agree."""

import gzip
import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_spec
from fatebridge.core.output_canping_schedule import CanpingScheduleBasis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError
from tests.canping_reading_fixture_compat import upgrade_prior_reading_presentation
from tests.numerology_clock_input_fixture_compat import upgrade_prior_clock_input

ROOT = Path(__file__).parent / "fixtures/canping_receipt_binding_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_bytes())
BASELINES = json.loads(
    gzip.decompress((ROOT / "baseline-results.json.gz").read_bytes())
)
BASELINES = [
    {
        **row,
        "output": upgrade_prior_clock_input(
            upgrade_prior_reading_presentation(row["output"]), row["input"]["time"]
        ),
    }
    for row in BASELINES
]
SPEC = next(s for s in CATALOG if s.key == "canping")
MUTATIONS = [
    "summary",
    "other_summary",
    "scope",
    "role",
    "future_policy",
    "books",
    "version",
    "review",
    "file_identity",
]


def label(row):
    return row["input"]["dayun_method"] + row["input"]["zone"]


def corrupt_basis(b, kind):
    b = deepcopy(b)
    if kind == "summary":
        b["summary"] = "本次已按原典完整核准，未来交运时刻无条件确定。"
    elif kind == "other_summary":
        b["summary"] = next(
            r["output"]["canping_timing"]["schedule_basis"]["summary"]
            for r in BASELINES
            if r["input"]["dayun_method"] != b["profile_id"]
        )
    elif kind == "scope":
        b["scope_statement"] = "本回执证明全书与现实预测全部满分。"
    elif kind == "role":
        c = next(c for c in b["clauses"] if c["id"] == "heluo_period_distinction")
        c["role"] = (
            "source_context"
            if c["role"] == "comparison_not_applied"
            else "comparison_not_applied"
        )
    elif kind == "future_policy":
        b["future_clock_policy"] = (
            "pinned_regional_rules; subject_to_future_legislation"
            if b["timezone_rules"]["database"] == "explicit_fixed_offset"
            else "explicit_fixed_offset_assumption; no_regional_future_rules"
        )
    elif kind == "books":
        b["sources"]["heluo_najda"], b["sources"]["sanming_nlc"] = (
            b["sources"]["sanming_nlc"],
            b["sources"]["heluo_najda"],
        )
    elif kind == "version":
        b["corpus_version"] = "99.0.0"
    elif kind == "review":
        b["review_status"] = "independently_certified_complete"
    elif kind == "file_identity":
        b["source_file_sha256"] = "0" * 64
    else:
        raise AssertionError(kind)
    return b


def corrupt_output(row, kind):
    out = deepcopy(row["output"])
    b = out["canping_timing"]["schedule_basis"]
    if kind in MUTATIONS:
        out["canping_timing"]["schedule_basis"] = corrupt_basis(b, kind)
    elif kind == "trace":
        next(
            r
            for r in out["numerology_evidence"]["rule_trace"]
            if r["rule_id"] == b["policy_id"]
        )["facts"]["summary"] = "本次未来规则已经无条件确定。"
    elif kind == "snapshot":
        out["snapshot_text"] = out["snapshot_text"].replace(
            b["summary"], "本次已经完成全书和现实认证。"
        )
    elif kind == "clock_context":
        b["timezone_rules"] = (
            {"database": "explicit_fixed_offset"}
            if b["timezone_rules"]["database"] != "explicit_fixed_offset"
            else {
                "database": "pytz",
                "future_policy": "extrapolate_pinned_rules_subject_to_legal_changes",
            }
        )
        b["future_clock_policy"] = (
            "explicit_fixed_offset_assumption; no_regional_future_rules"
            if b["timezone_rules"]["database"] == "explicit_fixed_offset"
            else "pinned_regional_rules; subject_to_future_legislation"
        )
    else:
        raise AssertionError(kind)
    return out


@pytest.mark.parametrize("row", BASELINES, ids=label)
def test_every_normal_receipt_and_each_single_field_projection_remains_valid(row):
    b = row["output"]["canping_timing"]["schedule_basis"]
    CanpingScheduleBasis.model_validate(b)
    for k, v in b.items():
        CanpingScheduleBasis.model_validate({k: v})
    for c in b["clauses"]:
        assert c["role"] == REFERENCE["expected_roles"][b["profile_id"]][c["id"]]
    assert (
        b["future_clock_policy"]
        == REFERENCE["clock_policy_by_database"][b["timezone_rules"]["database"]]
    )


@pytest.mark.parametrize("row", BASELINES, ids=label)
@pytest.mark.parametrize("kind", MUTATIONS)
def test_present_source_narrative_and_clock_contradictions_are_rejected(row, kind):
    b = corrupt_basis(row["output"]["canping_timing"]["schedule_basis"], kind)
    with pytest.raises(ValidationError):
        CanpingScheduleBasis.model_validate(b)


@pytest.mark.parametrize("row", BASELINES, ids=label)
@pytest.mark.parametrize("kind", ["summary", "scope", "role", "future_policy", "books"])
def test_corresponding_facts_still_bound_in_narrow_projections(row, kind):
    b = corrupt_basis(row["output"]["canping_timing"]["schedule_basis"], kind)
    keys = {
        "summary": ["profile_id", "summary"],
        "scope": ["scope_statement"],
        "role": ["profile_id", "clauses"],
        "future_policy": ["timezone_rules", "future_clock_policy"],
        "books": ["sources"],
    }[kind]
    with pytest.raises(ValidationError):
        CanpingScheduleBasis.model_validate({k: b[k] for k in keys})


@pytest.mark.parametrize("row", BASELINES, ids=label)
@pytest.mark.parametrize(
    "kind", ["summary", "role", "trace", "snapshot", "clock_context"]
)
def test_complete_same_result_guard_rejects_conflicts_before_projection(row, kind):
    bad = corrupt_output(row, kind)
    spec = replace(SPEC, bind=lambda _: (lambda: bad, (), {}))
    with pytest.raises(NumerologySourceError):
        execute_spec(spec, SPEC.request_model.model_validate(row["input"]))


def test_original_reference_and_semantic_criteria_are_not_rewritten():
    assert (
        hashlib.sha256((ROOT / REFERENCE["baseline_file"]).read_bytes()).hexdigest()
        == REFERENCE["baseline_sha256"]
    )

    assert (
        hashlib.sha256(
            (
                Path(__file__).parent
                / "fixtures/agent_behavior/canping_schedule_basis_semantic_cases_v1.json"
            ).read_bytes()
        ).hexdigest()
        == REFERENCE["unchanged_model_dataset_sha256"]
    )
    assert (
        REFERENCE["new_original_birth_examples"]
        == REFERENCE["new_calendar_observations"]
        == REFERENCE["new_reality_outcomes"]
        == 0
    )


def test_extensions_are_preserved_without_loosening_registered_source_facts():
    row = BASELINES[0]
    payload = deepcopy(row["output"])
    basis = payload["canping_timing"]["schedule_basis"]
    basis["vendor_note"] = {"revision": 1}
    basis["sources"]["heluo_najda"]["library_note"] = "extension"
    payload["future_root"] = {"enabled": True}
    before = deepcopy(payload)
    spec = replace(SPEC, bind=lambda _: (lambda: payload, (), {}))
    actual = execute_spec(spec, SPEC.request_model.model_validate(row["input"]))
    assert actual is payload and actual == before
