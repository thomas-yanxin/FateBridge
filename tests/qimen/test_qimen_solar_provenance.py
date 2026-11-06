"""Frozen JPL solar clocks and exact provenance through the public tools."""

import asyncio
import importlib.util
import json
import shutil
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.solar_time_provenance import solar_time_receipt
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen_solar import (
    audit_solar_clocks,
    expected_solar_label,
    label_classification,
    read_solar_reference,
    verify_qimen_solar_time_quotes,
)
from tests.qimen.test_qimen_depth import seed

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_solar_jpl_v1"
CASES = read_solar_reference(BUNDLE)


def payload(case, solar=True):
    d = datetime.fromisoformat(case["instant_utc"])
    return dict(
        analysis_year=d.year,
        analysis_month=d.month,
        analysis_day=d.day,
        analysis_hour=d.hour,
        analysis_minute=d.minute,
        analysis_timezone="UTC",
        analysis_longitude=0.0,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["instant_utc"])
@pytest.mark.parametrize("aggregate", [False, True])
def test_solar_labels_and_provenance_match_jpl_without_claiming_every_boundary(
    case, aggregate
):
    args = payload(case)
    if aggregate:
        instant = datetime.fromisoformat(case["instant_utc"])
        result = calculate_sanshiunited_analysis(
            date=instant.date().isoformat(),
            time=instant.strftime("%H:%M:%S+00:00"),
            zone="UTC",
            gps_lat=0.0,
            gps_lon=0.0,
            use_true_solar_time=True,
            qimen_options={"ju_method": "chaibu"},
        )
    else:
        result = calculate_qimen_analysis(**args)
    assert "error" not in result, result
    q = result["qimen"]
    e = q["calendar_policy"]["solar_time_adjustment"]
    assert e["status"] == "captured_at_seed_calculation"
    assert e["civil_input_instant_utc"] == case["instant_utc"]
    assert e["equation_of_time_time_scale"] == "UTC_as_UT1"
    assert e["equation_of_time_method"] == "swiss_time_equ_utc_instant_v1"
    assert (
        not e["physical_input_instant_shifted"]
        and not e["subsecond_accuracy_certified"]
    )
    actual = datetime.fromisoformat(e["apparent_solar_label"])
    expected = expected_solar_label(case)
    assert abs((actual - expected).total_seconds()) <= 5
    assert (
        abs(e["equation_of_time_minutes"] - case["equation_of_time_minutes"]) * 60 <= 5
    )
    assert "UTC近似UT1" in result["snapshot_text"]
    assert "距离不是误差界" in result["snapshot_text"]
    low, high = [
        label_classification(expected + timedelta(seconds=s * 5)) for s in (-1, 1)
    ]
    if low == high:
        assert q["time_ganzhi"][-1] == low["hour_branch"]
        effective = date.fromisoformat(low["effective_day"])
        # Derived from the retained HKO 2026-01-20 Jiawu day anchor, not a
        # second independently published daily Ganzhi observation.
        i = (30 + (effective - date(2026, 1, 20)).days) % 60
        assert (
            q["day_ganzhi"]
            == "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        )
    else:
        assert case["instant_utc"] == "2026-02-15T23:14:00+00:00"
        assert e["boundary_distances_seconds"]["day_boundary_23"] < 5
        assert not e["boundary_distances_seconds"]["certainty_inferred_from_distance"]
    if aggregate:
        assert result["subresults"]["qimen"]["pan"] == q


def test_source_audit_retains_the_near_boundary_case_as_uncertified():
    r = audit_solar_clocks(BUNDLE)
    assert r["reference_instants"] == 12 and not r["implementation_disagreements"]
    assert r["boundary_cases_not_certified_at_reference_tolerance"] == [
        "2026-02-15T23:14:00+00:00"
    ]
    assert (
        not r["all_boundary_labels_certified"] and r["empirical_prediction_cases"] == 0
    )


def test_numeric_reference_failure_is_not_hidden_by_the_partial_boundary_status(
    monkeypatch,
):
    spec = importlib.util.spec_from_file_location(
        "qimen_solar_failure_audit",
        Path(__file__).parents[2] / "scripts/qimen/audit_qimen.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.audit_solar_clocks

    def failed_reference(folder):
        report = original(folder)
        report["implementation_disagreements"].append(
            {"kind": "synthetic_injected_reference_failure"}
        )
        return report

    monkeypatch.setattr(module, "audit_solar_clocks", failed_reference)
    report = module.audit()
    assert report["calendar"]["status"] == "failed"
    assert any(r["category"] == "solar_clock_reference" for r in report["failures"])


@pytest.mark.parametrize(
    "mutation",
    ["drop_near_boundary", "alter_expected", "raw_response", "relax_tolerance"],
)
def test_reference_integrity_does_not_allow_dropping_the_difficult_row(
    tmp_path, mutation
):
    dest = tmp_path / "source"
    shutil.copytree(BUNDLE, dest)
    ref = json.loads((dest / "reference.json").read_text())
    if mutation == "drop_near_boundary":
        ref["cases"] = [
            r for r in ref["cases"] if r["instant_utc"] != "2026-02-15T23:14:00+00:00"
        ]
    elif mutation == "alter_expected":
        ref["cases"][0]["apparent_solar_hours"] += 0.1
    elif mutation == "relax_tolerance":
        ref["tolerance_seconds"] = 60
    else:
        (dest / ref["response_file"]).write_bytes(b"changed")
    (dest / "reference.json").write_text(json.dumps(ref))
    with pytest.raises(ValueError):
        read_solar_reference(dest)


def test_direct_clock_and_supplied_seed_do_not_invent_astronomical_provenance():
    direct = calculate_qimen_analysis(**payload(CASES[0], solar=False))["qimen"][
        "calendar_policy"
    ]["solar_time_adjustment"]
    assert direct["status"] == "not_applied" and not direct["applied"]
    synthetic = seed()
    from dataclasses import replace

    q = build_qimen_with_options(
        replace(synthetic, applied_true_solar=True), {"ju_method": "chaibu"}
    )
    missing = q["calendar_policy"]["solar_time_adjustment"]
    assert missing["status"] == "missing_seed_adjustment_provenance"
    assert "equation_of_time_method" not in missing


@pytest.mark.parametrize("part", ["total", "label", "naive_instant"])
def test_correction_receipt_rejects_inconsistent_components_or_clock_labels(part):
    case = CASES[0]
    result = calculate_qimen_analysis(**payload(case))
    e = result["qimen"]["calendar_policy"]["solar_time_adjustment"]
    adjustment = {
        k: e[k]
        for k in [
            "standard_meridian",
            "longitude_correction_minutes",
            "equation_of_time_minutes",
            "daylight_saving_minutes",
            "total_correction_minutes",
        ]
    }
    actual = datetime.fromisoformat(e["apparent_solar_label"])
    instant = datetime.fromisoformat(case["instant_utc"])
    if part == "total":
        adjustment["total_correction_minutes"] += 1
    elif part == "label":
        actual += timedelta(seconds=1)
    else:
        instant = instant.replace(tzinfo=None)
    with pytest.raises(ValueError):
        solar_time_receipt(
            civil_instant=instant,
            corrected_label=actual,
            timezone_name="UTC",
            longitude=0.0,
            adjustment=adjustment,
        )


def test_whole_receipt_quote_cannot_omit_scale_boundaries_or_rebind_runs():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    result = execute_tool(spec, spec.request_model.model_validate(payload(CASES[1])))
    e = result["qimen"]["calendar_policy"]["solar_time_adjustment"]
    claim = CalculationClaim(
        path="qimen.calendar_policy.solar_time_adjustment",
        value=deepcopy(e),
        run_id=result["run_metadata"]["run_id"],
    )
    assert (
        verify_qimen_solar_time_quotes(result, [claim])["status"]
        == "verified_structured_solar_time_quotes"
    )
    for key in [
        "equation_of_time_time_scale",
        "subsecond_accuracy_certified",
        "boundary_distances_seconds",
    ]:
        value = deepcopy(e)
        value.pop(key)
        assert (
            verify_qimen_solar_time_quotes(
                result, [claim.model_copy(update={"value": value})]
            )["status"]
            == "rejected"
        )
    assert (
        verify_qimen_solar_time_quotes(
            result, [claim.model_copy(update={"run_id": "different-run"})]
        )["status"]
        == "rejected"
    )
    assert (
        verify_qimen_solar_time_quotes(
            result,
            [
                claim.model_copy(
                    update={
                        "path": claim.path + ".total_correction_minutes",
                        "value": e["total_correction_minutes"],
                    }
                )
            ],
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "date,time,zone,offset,longitude",
    [
        ("1990-05-15", "10:30:00", "Asia/Shanghai", "+09:00", 121.0),
        ("2026-11-01", "01:30:00", "America/New_York", "-04:00", -74.006),
        ("2026-11-01", "01:30:00", "America/New_York", "-05:00", -74.006),
        ("2024-12-06", "14:52:00", "Pacific/Kiritimati", "+14:00", -157.4),
    ],
)
def test_local_dst_fold_and_date_line_keep_the_actual_receipt(
    date, time, zone, offset, longitude
):
    local = datetime.fromisoformat(date + "T" + time + offset)
    from datetime import timezone

    instant = local.astimezone(timezone.utc).isoformat()
    case = next(r for r in CASES if r["instant_utc"] == instant)
    q = calculate_qimen_analysis(
        analysis_year=local.year,
        analysis_month=local.month,
        analysis_day=local.day,
        analysis_hour=local.hour,
        analysis_minute=local.minute,
        analysis_timezone=zone,
        analysis_utc_offset=offset,
        analysis_longitude=longitude,
        use_true_solar_time=True,
        qimen_options={"ju_method": "chaibu"},
    )["qimen"]
    other = calculate_sanshiunited_analysis(
        date=date,
        time=time + offset,
        zone=zone,
        gps_lat=0.0,
        gps_lon=longitude,
        use_true_solar_time=True,
        qimen_options={"ju_method": "chaibu"},
    )["qimen"]
    e = q["calendar_policy"]["solar_time_adjustment"]
    assert e == other["calendar_policy"]["solar_time_adjustment"]
    assert e["civil_input_instant_utc"] == instant
    assert (
        abs(
            (
                datetime.fromisoformat(e["apparent_solar_label"])
                - expected_solar_label(case, longitude)
            ).total_seconds()
        )
        <= 5
    )
    assert e["daylight_saving_minutes"] == (60 if offset in {"+09:00", "-04:00"} else 0)


@pytest.mark.parametrize("aggregate", [False, True])
@pytest.mark.parametrize("minute", [14, 15])
def test_solar_receipt_and_boundary_limits_cross_rest_mcp_cli(
    monkeypatch, capsys, aggregate, minute
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["qimen", "snapshot_text", "snapshot_export"]
    if aggregate:
        tool, path = "sanshiunited", "/api/divination/sanshiunited"
        args = dict(
            date="2026-02-15",
            time=f"23:{minute}:00",
            zone="UTC",
            gps_lat=0.0,
            gps_lon=0.0,
            use_true_solar_time=True,
            qimen_options={"ju_method": "chaibu"},
        )
        clock = [
            "--date",
            args["date"],
            "--time",
            args["time"],
            "--zone",
            "UTC",
            "--gps-lat",
            "0",
            "--gps-lon",
            "0",
        ]
    else:
        tool, path = "qimen", "/api/cn/qimen"
        args = payload(
            next(
                r
                for r in CASES
                if r["instant_utc"] == f"2026-02-15T23:{minute}:00+00:00"
            )
        )
        clock = [
            "--analysis-year",
            "2026",
            "--analysis-month",
            "2",
            "--analysis-day",
            "15",
            "--analysis-hour",
            "23",
            "--analysis-minute",
            str(minute),
            "--analysis-timezone",
            "UTC",
            "--analysis-longitude",
            "0",
        ]
    controls = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        path,
        json=args,
        params=[
            ("as_of", controls["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                tool, {**args, **controls}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run(
        [
            tool,
            *clock,
            "--use-true-solar-time",
            "--qimen-options",
            json.dumps(args["qimen_options"]),
            "--as-of",
            controls["as_of"],
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not native.is_error and code == 0
    bodies = [
        {k: b[k] for k in fields} for b in [rest.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert "UTC近似UT1" in bodies[0]["snapshot_text"]
