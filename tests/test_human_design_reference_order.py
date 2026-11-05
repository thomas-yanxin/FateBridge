"""Preregistered input failures and full, rehashed ordering witnesses."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.astro import runtime
from fatebridge.core.human_design import chart_at
from fatebridge.core.human_design_reference_order import civil_jd, reference_ordering
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-reference-order-plan.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_every_preregistered_request_decision(case, empty_files, monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    if case["expected_accepted"]:
        assert HumanDesignRequest(**case["input"])
    else:
        with pytest.raises(ValueError):
            HumanDesignRequest(**case["input"])


@pytest.mark.parametrize(
    "label",
    [
        "1990-04-06T09:33:00.0000001Z",
        "1990-04-06T09:33:00,0000001Z",
        "1990-04-06T09:33:00+00:00:00.0000001",
        "2016-12-31T23:59:60.0000001Z",
    ],
)
def test_precision_is_rejected_before_datetime_can_truncate(label):
    with pytest.raises(ValueError, match="最多6位"):
        cycles.reference_epoch(label)


def test_exact_gregorian_fraction_and_utc_rate_are_independent_of_binary64():
    assert civil_jd(datetime(2000, 1, 1, 12, tzinfo=timezone.utc)) == 2451545
    before = civil_jd(datetime(1960, 1, 1, tzinfo=timezone.utc))
    after = civil_jd(datetime(1960, 1, 1, microsecond=1, tzinfo=timezone.utc))
    assert after - before == Fraction(1, 86400 * 1_000_000)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        a, at = cycles.reference_epoch("1960-01-01T00:00:00Z")
        b, bt = cycles.reference_epoch("1960-01-01T00:00:00.000001Z")
    proof = reference_ordering(a, at, b, bt)
    values = [
        Fraction(
            int(proof[k]["exact_jd_tt"]["numerator"]),
            int(proof[k]["exact_jd_tt"]["denominator"]),
        )
        for k in ("birth", "reference")
    ]
    assert (values[1] - values[0]) * 86400 == Fraction(1, 1_000_000) * (
        1 + Fraction("0.001296") / 86400
    )


@pytest.mark.parametrize(
    "case",
    [c for c in PLAN["cases"] if not c["expected_accepted"]],
    ids=lambda c: c["id"],
)
def test_full_service_rejects_each_bad_input_without_request_model(case):
    result = calculate_human_design(**case["input"])
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 400
    assert result["retryable"] is False


def test_domain_rejects_before_cycle_search_even_with_same_binary64_tt(monkeypatch):
    chart = chart_at(datetime(1990, 4, 6, 9, 33, tzinfo=timezone.utc))
    label, tt = cycles.reference_epoch("1990-04-06T09:32:59.999999Z")
    assert tt == chart["time_scales"]["personality"]["jd_tt"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid reference reached the multi-decade search")

    monkeypatch.setattr(cycles, "derive_body_contacts", forbidden)
    with pytest.raises(ValueError, match="不能早于出生"):
        cycles.calculate_cycle_context(chart, label, require_swiss_files=False)


@pytest.fixture(scope="module", params=["normal_after_1us", "historical_cross_era"])
def full_run(request):
    params = (
        next(c["input"] for c in PLAN["cases"] if c["id"] == request.param)
        if request.param != "historical_cross_era"
        else {
            "birth_year": 1959,
            "birth_month": 12,
            "birth_day": 31,
            "birth_hour": 23,
            "birth_minute": 59,
            "birth_timezone": "UTC",
            "cycle_reference_datetime": "1960-01-01T00:00:00Z",
        }
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        return execute_tool(SPEC, HumanDesignRequest(**params))


def forbidden_native(*args, **kwargs):
    raise AssertionError("Reading verification called the native producer")


def test_complete_reading_and_order_summary_replay_without_native(
    full_run, monkeypatch
):
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden_native)
    for name in ("utc_to_jd", "deltat_ex", "set_ephe_path"):
        monkeypatch.setattr(runtime.swe, name, forbidden_native)
    report = verify_human_design_reading(full_run)
    assert report["status"] == "verified_fixed_template_reading", report
    order = full_run["cycle_context"]["reference_ordering"]
    assert order["relation"] == "after"
    assert full_run["cycle_summary"]["reference_ordering"]["relation"] == "after"
    if full_run["birth_utc"].startswith("1990"):
        assert order["birth"]["physical_jd_tt"] == order["reference"]["physical_jd_tt"]
    else:
        assert order["birth"]["source"]["native_observation"]["delta_t_flag"] == -1
    assert full_run["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize("bad", PLAN["negative_receipts"])
def test_fresh_hash_cannot_hide_malformed_ordering(full_run, monkeypatch, bad):
    value = deepcopy(full_run)
    proof = value["cycle_context"]["reference_ordering"]
    if bad == "changed_exact_TT_numerator":
        v = proof["reference"]["exact_jd_tt"]
        v["numerator"] = str(int(v["numerator"]) + 1)
    elif bad == "invented_equal_relation":
        proof["relation"] = "equal"
    elif bad == "changed_source_offset":
        source = proof["reference"]["source"]
        key = (
            "tai_minus_utc_seconds"
            if "tai_minus_utc_seconds" in source["entry"]
            else "offset_seconds"
        )
        source["entry"][key] += 1
    elif bad == "wrong_native_delta_T_flag":
        native = proof["birth"]["source"].get("native_observation")
        if native is None:
            proof["birth"]["source"]["native_observation"] = {"delta_t_flag": 2}
        else:
            native["delta_t_flag"] = 2
    elif bad == "missing_order_witness":
        del value["cycle_context"]["reference_ordering"]
    else:
        head = value["cycle_context"]["reference_utc"].replace("+00:00", "")
        value["clock_evidence"]["cycle_reference_datetime"] = head + (
            "1Z" if "." in head else ".0000001Z"
        )
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden_native)
    assert verify_human_design_reading(value)["status"] == "rejected"
