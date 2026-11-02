"""New development questions cannot silently replace the original eight."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.audit_human_design_semantics import audit_review

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "tests/fixtures/agent_behavior/human_design_semantic_cases_v2.json"
DIGEST = "af298d2f53fcb7f1437d5ed520cb94d413caf31edc83d6b4471ba02d0dd95d8c"


def test_both_frozen_cohorts_keep_their_original_scope_and_bytes():
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == DIGEST
    d = json.loads(DATASET.read_text())
    assert (
        len(d["cases"]) == 5 and sum(len(c["manual_review"]) for c in d["cases"]) == 20
    )
    assert (
        d["independent_held_out_cases"] == 0 and d["original8_cases_replaced"] is False
    )
    old = ROOT / "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json"
    assert (
        hashlib.sha256(old.read_bytes()).hexdigest()
        == "0e413de085cb892fffa222c05219ec438b0e62f9ee1d769b293c7e0f931dad9b"
    )


def test_default_original_auditor_does_not_accept_the_new_cohort(tmp_path):
    (tmp_path / "case-dataset.json").write_bytes(DATASET.read_bytes())
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"dataset_sha256": DIGEST}))
    with pytest.raises(ValueError, match="cohort changed"):
        audit_review(tmp_path, review)


def test_new_cohort_selector_does_not_accept_original_eight_or_unknown_cohorts(
    tmp_path,
):
    old = ROOT / "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json"
    (tmp_path / "case-dataset.json").write_bytes(old.read_bytes())
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps({"dataset_sha256": hashlib.sha256(old.read_bytes()).hexdigest()})
    )
    with pytest.raises(ValueError, match="cohort changed"):
        audit_review(tmp_path, review, cohort="source-contract-v2")
    with pytest.raises(ValueError, match="Unknown preregistered"):
        audit_review(tmp_path, review, cohort="invented")


def test_new_case_bytes_survive_real_git_autocrlf_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.autocrlf", "true"], check=True
    )
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    relative = DATASET.relative_to(ROOT)
    target = repo / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(DATASET.read_bytes())
    subprocess.run(
        ["git", "-C", str(repo), "add", ".gitattributes", str(relative)],
        check=True,
        capture_output=True,
    )
    exported = tmp_path / "export"
    exported.mkdir()
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "checkout-index",
            "--all",
            "--prefix=" + str(exported) + "/",
        ],
        check=True,
        capture_output=True,
    )
    assert hashlib.sha256((exported / relative).read_bytes()).hexdigest() == DIGEST
