"""CI preserves coverage, skips passive docs and never cancels release commits."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text()
)


def test_cloud_jobs_do_not_restore_external_test_data():
    for job in WORKFLOW["jobs"].values():
        for step in job["steps"]:
            command = step.get("run", "")
            for dependency in (
                "restore_test_data.py",
                "fatebridge.fetch_ephe",
                "prepare_reference_kernel.py",
                "tests/fixtures/",
                "FATEBRIDGE_FIXTURE_TOKEN",
            ):
                assert dependency not in command, step["name"]
                assert dependency not in str(step.get("env", {})), step["name"]


def test_every_environment_keeps_the_full_suite_across_three_shards():
    jobs = WORKFLOW["jobs"]
    assert set(jobs) == {"changes", "locked", "quality", "test", "ci"}
    matrix = jobs["test"]["strategy"]["matrix"]
    assert matrix["shard"] == [0, 1, 2]
    assert {(e["python"], e["os"], e["resolution"]) for e in matrix["environment"]} == {
        (version, "ubuntu-24.04", "highest")
        for version in ("3.10", "3.11", "3.12", "3.13")
    } | {("3.10", "ubuntu-24.04", "lowest-direct"), ("3.12", "windows-2022", "locked")}
    assert jobs["test"]["strategy"]["fail-fast"] is False
    commands = "\n".join(s.get("run", "") for s in jobs["test"]["steps"])
    assert "scripts/run_ci_checks.py" in commands
    assert '--shard-index "$CI_SHARD" --shard-count 3' in commands
    assert "--selection-report ci-selection.json" in commands
    for name in ("locked", "quality", "test"):
        assert jobs[name]["needs"] == "changes"
        assert jobs[name]["if"] == "needs.changes.outputs.checks == 'true'"
    assert jobs["ci"]["if"] == "always()"
    assert set(jobs["ci"]["needs"]) == {"changes", "locked", "quality", "test"}


def test_pr_updates_cancel_but_main_and_master_commits_have_unique_groups():
    concurrency = WORKFLOW["concurrency"]
    assert (
        concurrency["cancel-in-progress"]
        == "${{ github.event_name == 'pull_request' }}"
    )
    assert "github.event.pull_request.number || github.run_id" in concurrency["group"]
    assert "github.workflow" in concurrency["group"]


def test_passive_docs_skip_heavy_jobs_but_keep_a_completed_summary():
    paths = next(
        s for s in WORKFLOW["jobs"]["changes"]["steps"] if s.get("id") == "paths"
    )
    assert paths["uses"].startswith("dorny/paths-filter@")
    assert paths["with"]["predicate-quantifier"] == "every"
    filters = yaml.safe_load(paths["with"]["filters"])
    assert filters["code"] == ["**", "!README*.md", "!docs/**/*.md"]
    assert filters["scenario"] == ["docs/scenario-routing.md"]
    assert (
        "steps.paths.outputs.scenario"
        in WORKFLOW["jobs"]["changes"]["outputs"]["checks"]
    )
    assert WORKFLOW["jobs"]["ci"]["name"] == "CI result"


@pytest.mark.parametrize(
    "failed_job,conclusion",
    [
        ("TEST_RESULT", "success"),
        ("CHANGES_RESULT", "failure"),
        ("LOCKED_RESULT", "failure"),
        ("QUALITY_RESULT", "failure"),
        ("TEST_RESULT", "failure"),
        ("TEST_RESULT", "cancelled"),
        ("TEST_RESULT", "skipped"),
    ],
)
def test_summary_gate_requires_every_selected_job_to_succeed(failed_job, conclusion):
    script = WORKFLOW["jobs"]["ci"]["steps"][0]["run"]
    results = {
        name: "success"
        for name in ("CHANGES_RESULT", "LOCKED_RESULT", "QUALITY_RESULT", "TEST_RESULT")
    }
    results.update(CHECKS_REQUIRED="true")
    results[failed_job] = conclusion
    result = subprocess.run(["bash", "-e", "-c", script], env={**os.environ, **results})
    assert (result.returncode == 0) is (conclusion == "success")


@pytest.mark.parametrize(
    "test_result",
    ["skipped", "failure"],
)
def test_docs_summary_accepts_only_the_explicit_skip_path(test_result):
    results = dict(
        CHANGES_RESULT="success",
        CHECKS_REQUIRED="false",
        LOCKED_RESULT="skipped",
        QUALITY_RESULT="skipped",
        TEST_RESULT=test_result,
    )
    script = WORKFLOW["jobs"]["ci"]["steps"][0]["run"]
    result = subprocess.run(["bash", "-e", "-c", script], env={**os.environ, **results})
    assert (result.returncode == 0) is (test_result == "skipped")


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing_report",
        "duplicate_node",
        "missing_node",
        "different_collection",
        "partial_rerun",
    ],
)
def test_live_gate_rejects_missing_or_overlapping_test_coverage(tmp_path, fault):
    reports = {}
    for environment in range(6):
        for index in range(3):
            reports[
                tmp_path
                / "ci-evidence"
                / f"env{environment}-part{index}-attempt1"
                / "ci-selection.json"
            ] = {
                "environment": f"env{environment}",
                "shard_index": index,
                "shard_count": 3,
                "collected": ["test_a", "test_b", "test_c"],
                "selected": [["test_a", "test_b", "test_c"][index]],
            }
    first = next(iter(reports))
    if fault == "missing_report":
        del reports[first]
    elif fault == "duplicate_node":
        reports[first]["selected"].append("test_b")
    elif fault == "missing_node":
        reports[first]["selected"] = []
    elif fault == "different_collection":
        reports[first]["collected"] = ["test_a"]
    elif fault == "partial_rerun":
        newer = (
            first.parent.with_name(first.parent.name.replace("attempt1", "attempt2"))
            / first.name
        )
        reports[newer] = {**reports[first], "selected": ["test_a"]}
        reports[first]["selected"] = []
    for path, report in reports.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")
    step = WORKFLOW["jobs"]["ci"]["steps"][-1]
    code = step["run"].split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True
    )
    assert (result.returncode == 0) is (fault in {None, "partial_rerun"}), result.stderr
