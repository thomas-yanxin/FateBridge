"""Retain every new clock condition and every older failed numerical gate."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.audit_astrodice_clock_budget import audit
from scripts.compare_astrodice_clock_horizons import compare

FIXTURE = Path(__file__).parent / "fixtures/astrodice-clock-budget-v1"


def test_frozen_clock_evidence_and_every_authoritative_input_keep_their_hashes():
    manifest = FIXTURE / "manifest.json"
    assert (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        == "0a02a44ef3fd274945a7adec69b7b80b50ed329a6655662549fe8c301eb909a7"
    )
    for name, expected in json.loads(manifest.read_text())["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    for name in [
        "astrodice_clock_interval.py",
        "diagnose_astrodice_clock_budget.py",
        "capture_astrodice_clock_frame.py",
        "compare_astrodice_clock_horizons.py",
    ]:
        assert (FIXTURE / (name + ".txt")).read_bytes() == (
            Path(__file__).resolve().parents[1] / "scripts" / name
        ).read_bytes()
    # The original auditor is pinned by the manifest above. The maintained
    # auditor now imports that protocol's frozen reference; the replay tests
    # below still require every original result and point check unchanged.


@pytest.mark.parametrize("group,count", [("development", 3), ("holdout", 28)])
def test_source_enclosures_replay_in_a_separate_process_before_point_checks(
    group, count, tmp_path
):
    output = tmp_path / "replay.json"
    command = [
        sys.executable,
        "-m",
        "scripts.diagnose_astrodice_clock_budget",
        "--run",
        str(FIXTURE),
        "--fixture",
        str(FIXTURE / "source-records"),
        "--group",
        group,
        "--frames",
        str(FIXTURE / "frames-first"),
        "--output",
        str(output),
    ]
    r = subprocess.run(
        command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    actual = json.loads(output.read_text())
    assert actual == json.loads((FIXTURE / (group + "-first.json")).read_text())
    assert (
        len(actual["rows"]) == count and actual["candidate_accuracy_acceptances"] == 0
    )
    independent = tmp_path / "independent.json"
    assert (
        audit(
            FIXTURE,
            FIXTURE / "source-records",
            output,
            FIXTURE / "frames-first",
            independent,
        )
        == 0
    )
    assert json.loads(independent.read_text())["point_evaluations"] == count * 10


def test_exact_model_separations_leave_the_unqualified_venus_reference_visible(
    tmp_path,
):
    result = compare(
        FIXTURE,
        FIXTURE.parent / "astrodice-grid5-reference-v2",
        tmp_path / "separation.json",
    )
    assert result == json.loads(
        (FIXTURE / "source-clock-Horizons-separation-first.json").read_text()
    )
    for row in result["rows"][:2]:
        for h in row["hypotheses"].values():
            assert h["position"]["strict_separation_certificate"]
        fb = row["hypotheses"]["full_geocentric_FB_analytic_envelope_conditional_model"]
        assert fb["ICRF_RA_rate"]["strict_separation_beyond_fixed_rate_line"]
    venus = result["rows"][2]["hypotheses"][
        "full_geocentric_FB_analytic_envelope_conditional_model"
    ]
    assert venus["ICRF_RA_rate"]["status"] == "original_rate_reference_unqualified"
    assert (
        not result["original_Horizons_results_regraded"]
        and not result["full_goal_complete"]
    )


@pytest.mark.parametrize(
    "mutation", ["position_box", "clock_envelope", "offset_only_rate_claim"]
)
def test_false_enclosures_or_strengthened_claims_cannot_pass_the_independent_checker(
    mutation, tmp_path
):
    run = tmp_path / "data"
    shutil.copytree(FIXTURE, run)
    path = run / "development-first.json"
    d = json.loads(path.read_text())
    row = d["rows"][0]
    if mutation == "position_box":
        box = row["center_direction_icrf_intervals"][0]
        box["lower_numerator"] = box["upper_numerator"] = "0"
    elif mutation == "clock_envelope":
        row["clock_model_envelope"]["maximum_offset_seconds"] = "1/100000000"
    else:
        row["hypotheses"]["source_documented_offset_no_rate_bound"][
            "display_rate_change_upper_arcsec_per_TT_day"
        ] = {}
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        audit(
            run,
            run / "source-records",
            path,
            run / "frames-first",
            tmp_path / "must-not-pass.json",
        )
