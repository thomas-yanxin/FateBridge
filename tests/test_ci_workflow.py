"""Cloud checks stay self-contained and cannot hide failed or skipped jobs."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
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


def test_workflow_runs_the_self_contained_matrix_on_every_change():
    jobs = WORKFLOW["jobs"]
    assert set(jobs) == {"locked", "test", "floor", "windows", "ci"}
    assert jobs["test"]["strategy"]["matrix"]["python-version"] == [
        "3.10",
        "3.11",
        "3.12",
        "3.13",
    ]
    assert jobs["test"]["strategy"]["fail-fast"] is False
    for name in ("test", "floor", "windows"):
        assert "if" not in jobs[name]
        assert any(
            "scripts/run_ci_checks.py" in step.get("run", "")
            for step in jobs[name]["steps"]
        )
    for job in jobs.values():
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step.get("with", {}).get("fetch-depth", 1) == 1
    assert jobs["windows"]["runs-on"] == "windows-2022"
    assert WORKFLOW["concurrency"]["cancel-in-progress"] is True
    assert "github.workflow" in WORKFLOW["concurrency"]["group"]
    assert "github.ref" in WORKFLOW["concurrency"]["group"]
    assert jobs["ci"]["if"] == "always()"
    assert set(jobs["ci"]["needs"]) == {"locked", "test", "floor", "windows"}


@pytest.mark.parametrize(
    "failed_job", ["LOCKED_RESULT", "TEST_RESULT", "FLOOR_RESULT", "WINDOWS_RESULT"]
)
@pytest.mark.parametrize(
    "conclusion", ["success", "failure", "cancelled", "skipped", ""]
)
def test_summary_gate_requires_every_selected_job_to_succeed(failed_job, conclusion):
    script = WORKFLOW["jobs"]["ci"]["steps"][0]["run"]
    results = {
        name: "success"
        for name in ("LOCKED_RESULT", "TEST_RESULT", "FLOOR_RESULT", "WINDOWS_RESULT")
    }
    results[failed_job] = conclusion
    result = subprocess.run(["bash", "-e", "-c", script], env={**os.environ, **results})
    assert (result.returncode == 0) is (conclusion == "success")
