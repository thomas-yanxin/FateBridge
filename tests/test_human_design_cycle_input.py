"""Frozen request time-order cases must retain correct decisions and caller state."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.utils.errors import EphemerisSourceError, validation_error_result

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-cycle-input-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())


def test_all_original_contamination_cases_and_bad_inputs_remain_frozen():
    before = ROOT / "docs/validation/human-design-cycle-input-before.json"
    assert (
        hashlib.sha256(before.read_bytes()).hexdigest()
        == "f676dbe6bd5adba9c36588a0febd9c571465388923757f564b7243507554d7b2"
    )
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "a790ca39da2576edeffbbbb19646160b8f2ff1937b2015f31eeb2a852bcd42cd"
    )
    report = json.loads(before.read_text())
    assert len(report["cases"]) == 12
    assert report["wrong_dirty_acceptance_count"] == 2
    assert report["parent_setting_changes"] == 5
    for row in report["cases"]:
        expected = next(c for c in PLAN["cases"] if c["id"] == row["id"])
        assert row["input"] == expected["input"]
        assert row["clean"]["accepted"] == expected["expected_accepted"]


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("kind", PLAN["perturbations"])
@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_actual_model_keeps_each_frozen_decision_and_parent_setting(
    tmp_path, monkeypatch, empty, kind, case
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty else ROOT / "ephe"))
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "tests/human_design_cycle_input_driver.py"),
            json.dumps(case["input"]),
            kind,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    result = json.loads(done.stdout)
    assert (
        result["clean"]["accepted"]
        == result["dirty"]["accepted"]
        == case["expected_accepted"]
    )
    assert result["parent_setting_preserved"]


def test_request_validation_never_calls_parent_native_code(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Request clock conversion leaked to parent native code")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    for method in ("utc_to_jd", "deltat_ex", "set_ephe_path"):
        monkeypatch.setattr(runtime.swe, method, forbidden)
    request = HumanDesignRequest(**PLAN["cases"][0]["input"])
    assert request.birth_year == 1959


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
def test_actual_preflight_auxiliary_change_is_an_enumerated_runtime_source_error(
    tmp_path, monkeypatch, filename
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    original = native_execution._receive
    seen = []

    def receive(*args):
        result = original(*args)
        if result.get("kind") == "ready":
            (tmp_path / filename).write_text(
                "# Changed after request clock worker snapshot\n"
            )
            seen.append(True)
        return result

    monkeypatch.setattr(native_execution, "_receive", receive)
    with pytest.raises(ValueError) as caught:
        HumanDesignRequest(**PLAN["cases"][0]["input"])
    result = validation_error_result(caught.value)
    assert seen == [True]
    assert result == EphemerisSourceError("auxiliary_changed_during").as_result()
    assert str(tmp_path) not in json.dumps(result)


def test_source_error_cannot_be_forged_by_an_untrusted_context_dictionary():
    class Errors:
        def errors(self):
            return [
                {
                    "type": "value_error",
                    "loc": [],
                    "ctx": {
                        "error": {
                            "reason": "auxiliary_changed_during",
                            "error_code": "ephemeris_source_inconsistent",
                        }
                    },
                }
            ]

    assert validation_error_result(Errors())["error_code"] == "validation_error"
