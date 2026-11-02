"""Actual date-table sources, complete finite coverage, and unresolved clock policy."""

import asyncio
import hashlib
import json
import shutil
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
import scripts.audit_ziwei as overall
import scripts.audit_ziwei_calendar_sources as audit
from fatebridge.application.examples import evidence_views
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.output_chinese import ZiweiDateConversionProvenance
from fatebridge.core.ziwei_date_sources import date_conversion_provenance
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_receipt import assert_same_run_receipt

# Match the existing calendar-audit file's precise legacy-API filters; other
# warnings still surface. This does not suppress conversion errors or defects.
pytestmark = [
    pytest.mark.filterwarnings("ignore:fromSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:toSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:use is_leap_month:DeprecationWarning"),
]


def test_full_1900_printed_cohort_and_source_roles_are_retained():
    r = audit.audit_calendar_sources()
    assert not r["differences"]
    assert r["distinct_printed_civil_dates"] == 365
    assert r["calendar_receipts_checked"] == 1460
    assert r["clock_reference_joins_checked"] == 4380
    assert r["adapter_correction_code_path_cases"] == 6
    assert r["adapter_correction_receipts_checked"] == 24
    assert not r["adapter_correction_probes_are_independent_calendar_truth"]
    assert all(
        v["dates_checked"] == 365 and v["pmo_prefix_cases"] == 30 for v in r["reports"]
    )
    assert r["new_publishing_institutions_in_this_round"] == 0
    assert r["distinct_publishers_in_reused_material"] == 2
    assert r["independent_human_reviewers"] == r["independent_model_reviewers"] == 0
    assert not r["moon_instants_or_classical_clock_rule_validated"]
    assert not r["mixed_clock_age_boundary_resolved"]
    assert r["live_model_blind_evaluation"] == "not_run"


def test_misattributed_hko_1900_source_is_detected(monkeypatch):
    original = audit.calculate_ziwei_birth

    def wrong(*args, **kwargs):
        result = original(*args, **kwargs)
        result["ziwei_birth"]["calendar_basis"][
            "reference_source"
        ] = "https://www.hko.gov.hk/tc/gts/time/conversion.htm"
        return result

    monkeypatch.setattr(audit, "calculate_ziwei_birth", wrong)
    assert len(audit.audit_calendar_sources()["differences"]) == 1460


def test_published_pdf_and_frozen_daily_values_are_required(tmp_path):
    shutil.copytree(
        audit.FIXTURES / "calendar_1900_sources_v1",
        tmp_path / "calendar_1900_sources_v1",
    )
    p = tmp_path / "calendar_1900_sources_v1/tam/sources/tam-1900.pdf"
    p.write_bytes(b"changed")
    with pytest.raises(ValueError, match="printed calendar source checksum"):
        audit.frozen_calendar_rows(tmp_path)


def test_hko_audit_uses_current_support_and_a_printed_preceding_month():
    r = overall.audit_calendar()
    assert not r["mismatches"]
    assert r["day_and_year_cells"] == r["full_date_cells"] == 73049
    assert r["outside_engine_support"] == 0
    assert r["actual_engine_supported_range"] == {
        "start": "1900-01-01",
        "end": "2100-12-31",
    }
    assert r["frozen_manifest_declared_engine_range"] == {
        "start": "1900-01-31",
        "end": "2100-02-08",
    }
    assert r["source_prefix_cells_recovered_from_preceding_tam_table"] == 19
    assert not r["recovered_month_labels_are_explicitly_printed_in_each_hko_cell"]
    assert r["preceding_printed_anchor"] == dict(
        solar="1900-12-31", year=1900, month=11, day=10, is_leap_month=False
    )


def test_newly_audited_2100_year_end_error_cannot_hide_outside_old_range(monkeypatch):
    original = overall._lunar_date_from_solar

    def wrong(solar):
        lunar = original(solar)
        if solar == date(2100, 12, 31):
            return SimpleNamespace(
                year=lunar.year,
                month=lunar.month,
                day=2,
                isLeapMonth=lunar.isLeapMonth,
            )
        return lunar

    monkeypatch.setattr(overall, "_lunar_date_from_solar", wrong)
    r = overall.audit_calendar()
    assert len(r["mismatches"]) == 1 and r["mismatches"][0]["solar"] == "2100-12-31"


def test_smaller_runtime_support_cannot_shrink_the_fixed_source_cohort(monkeypatch):
    monkeypatch.setattr(overall, "LUNAR_SUPPORTED_SOLAR_END", date(2100, 2, 8))
    r = overall.audit_calendar()
    assert r["day_and_year_cells"] == r["full_date_cells"] == 73049
    assert r["outside_engine_support"] == 326
    assert len(r["mismatches"]) == 326
    assert r["status"] == "failed"


@pytest.mark.parametrize(
    "year,month,day,provider,reference",
    [
        (1900, 1, 1, "pmo_1900_january_prefix_v1", "tam_1900"),
        (1900, 1, 30, "pmo_1900_january_prefix_v1", "tam_1900"),
        (1900, 1, 31, "fatebridge_lunardate_adapter_v1", "tam_1900"),
        (1900, 9, 24, "fatebridge_lunardate_adapter_v1", "tam_1900"),
        (1984, 2, 2, "fatebridge_lunardate_adapter_v1", "hko_1901_2100"),
        (2100, 2, 8, "fatebridge_lunardate_adapter_v1", "hko_1901_2100"),
        (2100, 2, 9, "hko_2100_month_starts_v1", "hko_1901_2100"),
        (2100, 12, 31, "hko_2100_month_starts_v1", "hko_1901_2100"),
    ],
)
def test_provider_and_printed_witness_are_separate_at_both_supplement_seams(
    year, month, day, provider, reference
):
    result = calculate_ziwei_birth(
        create_person_info(
            birth_year=year,
            birth_month=month,
            birth_day=day,
            birth_hour=12,
            birth_timezone="+08:00",
            use_true_solar_time=False,
            gender="未知",
        )
    )
    assert "error" not in result, result
    p = result["ziwei_birth"]["calendar_basis"]["date_conversion_provenance"]
    assert all(
        v["implementation_provider"] == provider
        and v["printed_date_reference"] == reference
        for v in p["lookups"].values()
    )
    assert not p["implementation_data_is_independent_validation"]
    if provider == "fatebridge_lunardate_adapter_v1":
        assert p["implementation_sources"][provider]["upstream"] == "lunardate"
    else:
        assert p["implementation_sources"][provider]["method_id"] == provider


def test_foreign_reference_outside_printed_range_is_not_labelled_hko():
    r = calculate_ziwei_birth(
        create_person_info(
            birth_year=1900,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=5,
            birth_timezone="+14:00",
            use_true_solar_time=False,
            gender="未知",
        )
    )
    b = r["ziwei_birth"]["calendar_basis"]
    assert b["reference_datetime_utc_plus_08"] == "1899-12-31 18:05:00"
    assert b["reference_lunar_date"] is None and b["reference_source"] is None
    row = b["date_conversion_provenance"]["lookups"]["reference_utc_plus_08"]
    assert row == dict(
        solar_date="1899-12-31",
        status="unavailable",
        implementation_provider=None,
        printed_date_reference=None,
        applied_year_info_correction=None,
    )


@pytest.mark.parametrize(
    "month,day,placement_provider,reference",
    [
        (1, 30, "fatebridge_lunardate_adapter_v1", "tam_1900"),
        (12, 31, "fatebridge_lunardate_adapter_v1", "hko_1901_2100"),
    ],
)
def test_solar_shift_may_change_provider_or_reference_without_relabelling_civil(
    month, day, placement_provider, reference
):
    r = calculate_ziwei_birth(
        create_person_info(
            birth_year=1900,
            birth_month=month,
            birth_day=day,
            birth_hour=23,
            birth_minute=55,
            birth_timezone="+08:00",
            birth_longitude=150,
            use_true_solar_time=True,
            gender="未知",
        )
    )
    b = r["ziwei_birth"]["calendar_basis"]
    p = b["date_conversion_provenance"]
    assert b["date_shift_days"] == 1
    assert p["lookups"]["placement"]["implementation_provider"] == placement_provider
    assert p["lookups"]["placement"]["printed_date_reference"] == reference
    assert p["lookups"]["civil"]["printed_date_reference"] == "tam_1900"
    assert p["lookups"]["reference_utc_plus_08"]["printed_date_reference"] == "tam_1900"
    if month == 1:
        assert (
            p["lookups"]["civil"]["implementation_provider"]
            == "pmo_1900_january_prefix_v1"
        )
    assert r["analysis_context"]["lunar_date_reference"] == reference


def test_provenance_mutation_does_not_modify_the_cached_catalogue():
    args = ({"placement": "1900-01-31"}, {"placement": {"year": 1900}})
    a = date_conversion_provenance(*args)
    a["printed_date_references"]["tam_1900"]["date_scope"].clear()
    b = date_conversion_provenance(*args)
    assert b["printed_date_references"]["tam_1900"]["date_scope"] == [
        "1900-01-01",
        "1900-12-31",
    ]


@pytest.mark.parametrize(
    "field",
    [
        "implementation_data_is_independent_validation",
        "historical_clock_policy_verified",
    ],
)
def test_public_model_rejects_false_certification(field):
    with pytest.raises(ValidationError):
        ZiweiDateConversionProvenance.model_validate({field: True})


@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_horoscope"])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("year", [1900, 1933])
def test_source_view_and_actual_provider_match_rest_native_mcp_cli(
    tool, profile, year, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == tool)
    inputs = dict(
        birth_year=year,
        birth_month=1 if year == 1900 else 6,
        birth_day=1,
        birth_hour=12,
        birth_timezone="+08:00",
        use_true_solar_time=False,
        gender="男",
        rule_profile=profile,
        sihua_source="naj_ming_v1",
    )
    if tool == "ziwei_horoscope":
        inputs.update(
            target_year=1900 if year == 1900 else 1934,
            target_month=1 if year == 1900 else 6,
            target_day=31 if year == 1900 else 1,
            target_hour=12,
        )
    fields = evidence_views(spec)["calendar_sources"]["fields"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(tool, {**inputs, **opts})
            assert not result.is_error
            p = result.structured_content
            assert len(json.dumps(p, ensure_ascii=False, separators=(",", ":"))) <= 8192
            if "result_delivery" not in p:
                return p
            ref = p["result_delivery"]
            uri = ref["first_page_uri"]
            raw = ""
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                raw += page["text"]
                uri = page["next_uri"]
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            full = json.loads(raw)
            assert_same_run_receipt(
                p["run_metadata"],
                full["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
            return full

    native = asyncio.run(call())
    args = [tool]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    b = bodies[0][tool]["calendar_basis"]
    birth = b if tool == "ziwei_birth" else b["birth"]
    assert birth["date_conversion_provenance"]["lookups"]["placement"][
        "implementation_provider"
    ] == (
        "pmo_1900_january_prefix_v1"
        if year == 1900
        else "fatebridge_lunardate_adapter_v1"
    )
    assert birth["date_conversion_provenance"]["lookups"]["placement"][
        "printed_date_reference"
    ] == ("tam_1900" if year == 1900 else "hko_1901_2100")
    assert birth["date_conversion_provenance"]["lookups"]["placement"][
        "applied_year_info_correction"
    ] == (None if year == 1900 else "1933:0x16a95")


@pytest.mark.parametrize(
    "solar,expected_year,expected_override",
    [
        ("1933-06-01", 1933, "1933:0x16a95"),
        ("1934-01-01", 1933, "1933:0x16a95"),
        ("1954-06-01", 1954, "1954:0xa5b0"),
        ("1955-01-01", 1954, "1954:0xa5b0"),
        ("1978-06-01", 1978, "1978:0xb6a0"),
        ("1979-01-01", 1978, "1978:0xb6a0"),
    ],
)
def test_adapter_records_the_actual_lunar_year_override_across_civil_years(
    solar, expected_year, expected_override
):
    moment = date.fromisoformat(solar)
    result = calculate_ziwei_birth(
        create_person_info(
            birth_year=moment.year,
            birth_month=moment.month,
            birth_day=moment.day,
            birth_hour=12,
            birth_timezone="+08:00",
            use_true_solar_time=False,
            gender="未知",
        )
    )
    chart = result["ziwei_birth"]
    assert chart["lunar_date"]["year"] == expected_year
    provenance = chart["calendar_basis"]["date_conversion_provenance"]
    assert all(
        row["implementation_provider"] == "fatebridge_lunardate_adapter_v1"
        and row["applied_year_info_correction"] == expected_override
        for row in provenance["lookups"].values()
    )


def test_same_run_claim_rejects_hko_as_the_actual_prefix_implementation():
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    p = execute_tool(
        spec,
        spec.request_model.model_validate(
            dict(
                birth_year=1900,
                birth_month=1,
                birth_day=1,
                birth_hour=12,
                birth_timezone="+08:00",
                use_true_solar_time=False,
                gender="未知",
            )
        ),
    )
    m = p["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="ziwei_birth.calendar_basis.date_conversion_provenance.lookups.placement.implementation_provider",
            value=value,
            run_id=m["run_id"],
            business_output_sha256=m["business_output_sha256"],
        )

    assert (
        verify_calculation_claims(p, [claim("pmo_1900_january_prefix_v1")])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(p, [claim("hko_1901_2100")])["status"] == "rejected"
    )


def test_source_attribution_does_not_claim_to_fix_mixed_age_clock():
    person = create_person_info(
        birth_year=1984,
        birth_month=2,
        birth_day=1,
        birth_hour=23,
        birth_minute=55,
        birth_timezone="Asia/Shanghai",
        birth_longitude=150,
        use_true_solar_time=True,
        gender="男",
    )
    r = calculate_ziwei_horoscope(
        person,
        nominal_age_basis="legacy_mixed_clock",
        target_year=1984,
        target_month=2,
        target_day=1,
        target_hour=23,
        target_minute=59,
    )
    assert r["status_code"] == 400 and "此边界暂不支持" in r["error"]
