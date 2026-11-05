"""All source-planned leap seconds survive public calculation and reading."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro.time_scales import ephemeris_time, leap_table
from fatebridge.core.human_design_birth_clock import (
    resolve_birth_clock,
    verify_birth_clock,
)
from fatebridge.core.human_design_cycles import reference_epoch
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURES = Path(__file__).parents[1] / "fixtures"
PLAN = json.loads((FIXTURES / "human-design-leap-plan.json").read_text())
REFERENCE = json.loads((FIXTURES / "human-design-leap-sofa.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def birth_input(label):
    return dict(
        birth_year=int(label[:4]),
        birth_month=int(label[5:7]),
        birth_day=int(label[8:10]),
        birth_hour=int(label[11:13]),
        birth_minute=int(label[14:16]),
        birth_second=int(label[17:19]),
        birth_timezone="UTC",
    )


def test_frozen_sofa_plan_contains_every_known_step_and_no_removed_rows():
    assert (
        REFERENCE["plan_sha256"]
        == hashlib.sha256(
            (FIXTURES / "human-design-leap-plan.json").read_bytes()
        ).hexdigest()
    )
    assert len(REFERENCE["cases"]) == len(PLAN["utc_labels"]) == 81
    assert [r["utc_label"] for r in REFERENCE["cases"]] == PLAN["utc_labels"]
    assert all(r["statuses"] == [0, 0, 0] for r in REFERENCE["cases"])
    days = {label[:10] for label in PLAN["utc_labels"] if label[17:19] == "60"}
    entries = leap_table()["entries"]
    from datetime import timedelta

    expected = {
        (datetime.fromisoformat(b["effective_date"]) - timedelta(days=1))
        .date()
        .isoformat()
        for a, b in zip(entries, entries[1:])
        if b["tai_minus_utc_seconds"] - a["tai_minus_utc_seconds"] == 1
    }
    assert days == expected and len(days) == 27
    assert PLAN["tolerance_seconds"] == 0.0002


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda r: r["utc_label"])
def test_all_81_frozen_labels_agree_with_independent_two_part_sofa(case):
    request = HumanDesignRequest(**birth_input(case["utc_label"]))
    clock = resolve_birth_clock(**birth_input(case["utc_label"]))
    tt = clock.jd_tt if clock.leap_second else ephemeris_time(clock.utc_anchor).jd_tt
    oracle = Fraction(case["tt_jd1"]) + Fraction(case["tt_jd2"])
    assert abs(Fraction(tt) - oracle) * 86400 <= Fraction(1, 5000)
    assert request.birth_second == int(case["utc_label"][17:19])


@pytest.mark.parametrize("label", [x for x in PLAN["utc_labels"] if x[17:19] == "60"])
def test_all_27_public_leap_births_have_full_verified_explanations(label):
    run = execute_tool(SPEC, HumanDesignRequest(**birth_input(label)))
    proof = run["birth_clock_evidence"]
    assert run["birth_utc"] == label[:19] + ".000000+00:00"
    assert (
        proof["tai_minus_utc_after_leap_seconds"]
        - proof["tai_minus_utc_during_leap_seconds"]
        == 1
    )
    assert run["design_solver"]["civil_elapsed_days"] is None
    assert run["time_scales"]["personality"]["jd_tt"] == proof["jd_tt"]
    assert run["time_scales"]["personality"]["utc_is_leap_second"] is True
    assert run["interpretation"]["statements"][0]["id"] == "birth_clock"
    assert "插秒前" in run["interpretation"]["birth_clock_meaning"]
    checked = verify_human_design_reading(run)
    assert checked["status"] == "verified_fixed_template_reading", checked
    following = datetime.fromisoformat(proof["following_utc_midnight"])
    after_tt = ephemeris_time(following).jd_tt
    assert abs((after_tt - proof["jd_tt"]) * 86400 - 1) < 0.0002
    assert after_tt != proof["jd_tt"]
    assert run["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "label,zone",
    [
        ("2016-12-30T23:59:60", "UTC"),
        ("2017-12-31T23:59:60", "UTC"),
        ("1961-07-31T23:59:60", "UTC"),
        ("2030-12-31T23:59:60", "UTC"),
        ("2016-12-31T22:59:60", "UTC"),
        ("2016-12-31T23:59:60", "Asia/Shanghai"),
        ("2017-01-01T07:59:60", "UTC"),
        ("2024-03-10T02:30:60", "America/New_York"),
        ("2024-11-03T01:30:60", "America/New_York"),
    ],
)
def test_unknown_unpublished_wrong_local_minute_and_dst_are_rejected(label, zone):
    with pytest.raises(ValueError):
        HumanDesignRequest(**{**birth_input(label), "birth_timezone": zone})


@pytest.mark.parametrize(
    "label",
    [
        "2016-12-31T23:59:60Z",
        "2017-01-01T07:59:60+08:00",
        "2016-12-31T18:59:60-05:00",
        "2016-12-31T23:59:60.000000+00:00",
    ],
)
def test_cycle_reference_accepts_the_same_confirmed_leap_instant(label):
    canonical, tt = reference_epoch(label)
    clock = resolve_birth_clock(**birth_input("2016-12-31T23:59:60"))
    assert canonical == clock.utc_label and tt == clock.jd_tt
    HumanDesignRequest(
        **birth_input("2016-12-31T23:59:60"), cycle_reference_datetime=label
    )
    with pytest.raises(ValueError, match="不能早于"):
        HumanDesignRequest(
            **birth_input("2016-12-31T23:59:60"),
            cycle_reference_datetime="2016-12-31T23:59:59Z",
        )


def test_fractional_cycle_reference_is_continuous_and_replays_its_own_label():
    label, tt = reference_epoch("2017-01-01T07:59:60.500000+08:00")
    _, start = reference_epoch("2016-12-31T23:59:60Z")
    assert label == "2016-12-31T23:59:60.500000+00:00"
    assert abs((tt - start) * 86400 - 0.5) < 0.0002
    assert reference_epoch(label) == (label, tt)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "input",
        "offset",
        "table",
        "source",
        "authenticated",
        "utc",
        "local",
        "tt",
        "flag",
        "method",
        "text",
    ],
)
def test_rehashed_inconsistent_leap_proofs_and_explanations_are_rejected(mutation):
    run = execute_tool(SPEC, HumanDesignRequest(**birth_input("2016-12-31T23:59:60")))
    forged = deepcopy(run)
    proof = forged["birth_clock_evidence"]
    if mutation == "missing":
        del forged["birth_clock_evidence"]
    elif mutation == "input":
        proof["input"]["birth_day"] = 30
    elif mutation == "offset":
        proof["tai_minus_utc_during_leap_seconds"] = 37
    elif mutation == "table":
        proof["source_table_sha256"] = "0" * 64
    elif mutation == "source":
        proof["source_url"] = "https://example.invalid/unverified"
    elif mutation == "authenticated":
        proof["birth_record_authenticated"] = True
    elif mutation == "utc":
        forged["birth_utc"] = "2017-01-01T00:00:00+00:00"
    elif mutation == "local":
        forged["calculation_policy"]["birth_local"] = "2017-01-01T00:00:00+00:00"
    elif mutation == "tt":
        forged["time_scales"]["personality"]["jd_tt"] += 1 / 86400
    elif mutation == "flag":
        forged["time_scales"]["personality"]["utc_is_leap_second"] = False
    elif mutation == "method":
        forged["time_scales"]["personality"]["method"] = "ordinary_datetime"
    else:
        forged["interpretation"]["birth_clock_meaning"] = "出生记录与天文精度均已认证。"
    if mutation != "text":
        with pytest.raises((ValueError, KeyError)):
            verify_birth_clock(forged)
    forged["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in forged.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(forged)["status"] == "rejected"


@pytest.mark.parametrize("empty_files", [False, True])
def test_leap_birth_uncertainty_and_cycles_keep_selected_tt(
    monkeypatch, tmp_path, empty_files
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    run = execute_tool(
        SPEC,
        HumanDesignRequest(
            **birth_input("2016-12-31T23:59:60"),
            birth_time_uncertainty_minutes=1,
            cycle_reference_datetime="2016-12-31T23:59:60Z",
        ),
    )
    tt = run["birth_clock_evidence"]["jd_tt"]
    assert (
        run["cycle_context"]["birth_jd_tt"]
        == run["cycle_context"]["reference_jd_tt"]
        == tt
    )
    assert run["time_sensitivity"]["status"] != "not_assessed"
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check
    assert run["cycle_summary"]["sixth_line"]["current_phase"] is None
