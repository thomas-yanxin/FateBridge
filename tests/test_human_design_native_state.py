"""Frozen dirty-parent controls cross the real private execution boundary."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_execution import verify_native_context

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-native-state-plan.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize(
    "year", [p["birth_year"] for p in PLAN["mandatory_birth_inputs"]]
)
@pytest.mark.parametrize("empty", [False, True])
def test_every_original_dirty_parent_case_keeps_complete_output_and_parent_state(
    tmp_path, year, empty
):
    directory = tmp_path if empty else ROOT / "ephe"
    r = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "tests/human_design_native_state_driver.py"),
            str(year),
            str(directory),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    result = json.loads(r.stdout)
    assert (
        result["complete_business_output_identical"]
        and result["parent_setting_preserved"]
        and result["full_readings_verified"]
    )


def test_manual_tidal_acceleration_is_also_private(tmp_path):
    r = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "tests/human_design_native_state_driver.py"),
            "1900",
            str(ROOT / "ephe"),
            "tidal_acceleration",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_parent_native_monkeypatch_cannot_cross_production_dispatch(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Parent native state leaked into private calculation")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    p = calculate_human_design(**PLAN["mandatory_birth_inputs"][0])
    assert "activations" in p, p
    assert p["native_execution_context"]["mechanism"] == "fresh_exec_process"


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
@pytest.mark.parametrize("present", [False, True])
def test_auxiliary_candidate_change_after_real_worker_ready_is_rejected(
    tmp_path, monkeypatch, filename, present
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    path = tmp_path / filename
    if present:
        path.write_text("# Initial empty synthetic auxiliary table\n")
    original = native_execution._receive
    seen = []

    def receive(*args):
        result = original(*args)
        if result.get("kind") == "ready":
            path.write_text("# Changed after worker source snapshot\n")
            seen.append(True)
        return result

    monkeypatch.setattr(native_execution, "_receive", receive)
    result = calculate_human_design(**PLAN["mandatory_birth_inputs"][1])
    assert seen == [True]
    assert result["error_code"] == "ephemeris_source_inconsistent", result
    assert result["retryable"] is False
    assert result["issues"][0]["code"] == "auxiliary_changed_during"
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize("filename", ["swe_deltat.txt", "sedeltat.txt"])
@pytest.mark.parametrize("year", [1900, 1960])
def test_current_auxiliary_file_is_used_instead_of_stale_parent_table(
    tmp_path, filename, year
):
    stale = tmp_path / "stale"
    stale.mkdir()
    (stale / "swe_deltat.txt").write_text(
        "\n".join(f"{y} 400" for y in range(1790, 2011)) + "\n"
    )
    results = []
    for name, value in [("empty", None), ("current", 1000)]:
        directory = tmp_path / name
        directory.mkdir()
        if value is not None:
            (directory / filename).write_text(
                "\n".join(f"{y} {value}" for y in range(1790, 2011)) + "\n"
            )
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROOT / "tests/human_design_native_state_driver.py"),
                str(year),
                str(directory),
                "stale_auxiliary",
                str(stale),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        results.append(json.loads(done.stdout))
    assert results[0]["auxiliary_files_present"] == []
    assert results[1]["auxiliary_files_present"] == [
        {
            "search_index": 0,
            "filename": filename,
            "bytes": (tmp_path / "current" / filename).stat().st_size,
            "sha256": hashlib.sha256(
                (tmp_path / "current" / filename).read_bytes()
            ).hexdigest(),
        }
    ]
    # Retain 1900 as the historical-model control; add the applicable 1960 UT1 case.
    if year == 1900:
        assert results[1]["nominal_jd_tt"] == results[0]["nominal_jd_tt"]
    else:
        assert (
            abs(results[1]["nominal_jd_ut1"] - results[0]["nominal_jd_ut1"]) * 86400
            > 900
        )


@pytest.fixture(scope="module")
def complete():
    return execute_tool(SPEC, SPEC.request_model(**PLAN["mandatory_birth_inputs"][-1]))


@pytest.mark.parametrize(
    "kind",
    [
        "delete",
        "local_forgery",
        "lifetime",
        "scope",
        "count",
        "bool_count",
        "fake_file",
        "extra",
        "policy",
        "cache_count",
        "policy_scope",
    ],
)
def test_rehashed_context_cannot_invent_boundaries_or_auxiliary_identity(
    complete, kind
):
    p = deepcopy(complete)
    c = p["native_execution_context"]
    if kind == "delete":
        del p["native_execution_context"]
    elif kind == "local_forgery":
        c["mechanism"] = "local_engine_context"
    elif kind == "lifetime":
        c["lifetime"] = "unbounded_shared_pool"
    elif kind == "scope":
        c["scope"] = "原生运行、所有天文精度及现实预测均已认证。"
    elif kind == "count":
        c["auxiliary_candidates_checked"] = 2
    elif kind == "bool_count":
        c["auxiliary_candidates_checked"] = True
    elif kind == "fake_file":
        c["auxiliary_files_present"] = [
            {
                "search_index": 0,
                "filename": "arbitrary.secret",
                "bytes": 1,
                "sha256": "0" * 64,
            }
        ]
    elif kind == "extra":
        c["native_execution_authenticated"] = True
    elif kind == "policy":
        c["compressed_file_endpoint_policy"]["input_instant_shifted"] = True
    elif kind == "cache_count":
        c["compressed_file_endpoint_policy"]["native_cache_resets_so_far"] = False
    else:
        c["compressed_file_endpoint_policy"][
            "scope"
        ] = "Full positional accuracy proved."
    p["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in p.items() if k != "run_metadata"}
    )
    assert verify_native_context(p)["errors"]
    assert verify_human_design_reading(p)["status"] == "rejected"
