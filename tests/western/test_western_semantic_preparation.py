"""Preregistered Western diagnostics must stay pending and hidden from examinees."""

import json
from pathlib import Path

import pytest

from fatebridge.services.tool_catalog import CATALOG
from scripts.evaluate_agent import (
    grade_case,
    model_prompt,
    prepare_workspace,
    source_files,
)

DATASET = (
    Path(__file__).parents[1] / "fixtures/agent_behavior/western_semantic_cases_v1.json"
)
DATA = json.loads(DATASET.read_text())
SPECS = {s.tool_name: s for s in CATALOG}


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda c: c["id"])
def test_reference_requests_are_live_contracts_but_empty_model_runs_never_pass(case):
    req = case["reference_request"]
    SPECS[req["tool"]].request_model.model_validate(req["arguments"])
    assert not grade_case(case, [], "", 0)["mechanical_checks_passed"]
    assert case["capture_payloads"] is True
    assert all(text not in model_prompt(case) for text in case["manual_review"])


def test_development_cases_cannot_be_relabelled_as_blind_or_real_world_evidence():
    assert DATA["cohort_role"] == "known_development_regressions"
    assert DATA["independent_held_out_cases"] == 0
    assert DATA["semantic_acceptance"] == "not_run"
    assert DATA["real_world_outcome_observations"] == 0
    assert len({c["id"] for c in DATA["cases"]}) == len(DATA["cases"])


def test_model_workspace_keeps_runtime_guidance_but_excludes_new_hidden_criteria(
    tmp_path,
):
    source = tmp_path / "source"
    for name, text in {
        "AGENTS.md": "runtime rules",
        "skills/onda-xingpan/SKILL.md": "runtime skill",
        "src/fatebridge/example.py": "runtime code",
        "docs/western-astrology.md": "runtime guide",
        "docs/western-semantics-evaluation.md": "HIDDEN_REVIEW_CRITERIA",
        "docs/validation/evaluation.json": "HIDDEN_PAST_GRADES",
        "tests/fixtures/agent_behavior/western_semantic_cases_v1.json": "hidden dataset",
    }.items():
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    assert (workspace / "docs/western-astrology.md").read_text() == "runtime guide"
    assert not (workspace / "docs/western-semantics-evaluation.md").exists()
    assert not (workspace / "docs/validation").exists()
    assert not (workspace / "tests").exists()
    assert (
        source / "tests/fixtures/agent_behavior/western_semantic_cases_v1.json"
        in source_files(source, profile="runtime")
    )
