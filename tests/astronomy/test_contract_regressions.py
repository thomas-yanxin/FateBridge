"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import hashlib
import json
import math
import platform
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from fractions import Fraction as F

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import aa1996_solar, almanac, de440_solar, ephemeris_paths
from fatebridge.core import lunar_phase_events as subject
from fatebridge.core import solar_model_policy, solar_term_runtime
from fatebridge.core.aa1996_solar import MODEL_ID
from fatebridge.core.astro import moshier_motion
from fatebridge.core.astro.native_motion import context_motion
from fatebridge.core.astro.solar_decimal import stable_interpolation_cell
from fatebridge.core.fengshui.calendar import (
    boundary_model_policy,
    boundary_uncertainty_reason,
    solar_term_resolution,
)
from fatebridge.core.fengshui.historical_solar import historical_solar_resolution
from fatebridge.core.fengshui.snapshot import _calendar_cautions
from fatebridge.fetch_aa1996 import build, source_profile
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import (
    EphemerisSourceError,
    calculation_guard,
    handle_calculation_error,
)
from fatebridge.utils.timezones import (
    parse_timezone_name,
    timezone_rules_metadata,
    validate_local_clock,
)
from fatebridge.validation.fengshui_solar_terms import compare_resolution
from scripts.astronomy import build_ephemeris_manifest as builder
from tests.astronomy.test_moshier_motion_frames import analytical
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    inputs,
    native,
    rest,
    surface_calls,
)


def test_named_model_keeps_five_second_candidate_guard():
    moment = datetime(2026, 2, 4, tzinfo=timezone.utc)
    record = dict(
        moment=moment.isoformat(), ephemeris_model=MODEL_ID, approximate=False
    )
    policy = boundary_model_policy(record)
    assert policy["operational_guard_seconds"] == 5.0
    assert (
        policy["uncertainty_reason"]
        == "aa1996_solar_model_guard_not_accuracy_certification"
    )
    for offset in [-5, 0, 5]:
        assert (
            boundary_uncertainty_reason(moment + timedelta(seconds=offset), record)
            == policy["uncertainty_reason"]
        )
    assert (
        boundary_uncertainty_reason(moment + timedelta(seconds=5.001), record) is None
    )
    assert boundary_model_policy({**record, "approximate": True}) is None


def test_readout_names_actual_aa1996_model():
    lines = _calendar_cautions({"resolution": {"ephemeris_model": MODEL_ID}})
    assert any("AA1996" in line for line in lines)
    assert not any("完整范围尚未通过" in line for line in lines)


def test_named_provider_requires_both_root_and_actual_civil_gate():
    from fatebridge.core.astro.time_scales import ephemeris_time

    moment = datetime(2026, 2, 4, tzinfo=timezone.utc)
    tt = ephemeris_time(moment).jd_tt
    row = dict(year=2026, term_index=2, term="立春", jd_tt=tt)
    record = dict(
        moment=moment.isoformat(),
        provider="moshier_aa1996",
        approximate=False,
        ephemeris_model=MODEL_ID,
        time_basis={"root_time_scale": "TT"},
        solar_model_details={"selected_crossing_jd_tt": tt},
    )
    assert compare_resolution(row, record)["within_tolerance"]
    assert not compare_resolution(row, {**record, "solar_model_details": {}})[
        "within_tolerance"
    ]
    assert not compare_resolution(
        row,
        {**record, "solar_model_details": {"selected_crossing_jd_tt": tt + 2 / 86400}},
    )["within_tolerance"]
    assert not compare_resolution(
        row, {**record, "moment": (moment + timedelta(seconds=2)).isoformat()}
    )["within_tolerance"]


@pytest.mark.parametrize("year", [1783, 1800, 2000, 2200, 2205])
def test_unused_internal_profile_never_loads_aa1996(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("unused AA1996 source")
    )
    assert historical_solar_resolution(year, "立春", "UTC") is None


def test_historical_aa1996_strict_jpl_conflict_precedes_source_loading(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de441.eph")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("conflicting source loaded")
    )
    with pytest.raises(ValueError, match="AA1996.*conflicts"):
        historical_solar_resolution(1784, "立春", "UTC")


def test_mode_change_during_historical_aa1996_root_is_a_source_failure(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    context = ("frozen-clock", ("aa1996", aa1996_solar.MODEL_ID, ("frozen-source",)))
    monkeypatch.setattr(
        solar_term_runtime, "solar_term_cache_context", lambda *a, **k: context
    )

    def changed(*args, **kwargs):
        assert kwargs["aa1996"] is True and kwargs["expected_aa1996_key"] == (
            "frozen-source",
        )
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        return datetime(1784, 2, 4, tzinfo=timezone.utc), {
            "solar_model_details": {"qualified_solar_term_years": [1784, 2204]}
        }

    monkeypatch.setattr(almanac, "_solar_term_utc_via_analytic", changed)
    with pytest.raises(EphemerisSourceError) as caught:
        historical_solar_resolution(1784, "立春", "UTC")
    assert caught.value.reason == "solar_configuration_changed"


def test_older_build_does_not_silently_acquire_the_extended_working_span(
    tmp_path, monkeypatch
):
    profile, digest = source_profile()
    manifest = dict(
        model_id=profile["model_id"],
        version="1.0.0",
        abi_version=1,
        source_profile_sha256=digest,
        calculation_source_sha256=profile["calculation_source_sha256"],
        system=platform.system(),
        machine=platform.machine(),
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        aa1996_solar.ctypes, "CDLL", lambda *a, **k: pytest.fail("older build loaded")
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"


def test_missing_model_is_structured_failure_before_native_fallback(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.delenv(aa1996_solar.MANIFEST_ENV, raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(
        almanac,
        "_solar_term_utc_via_swe",
        lambda *a, **k: pytest.fail("native fallback"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        almanac.get_solar_terms_for_year(2026, "UTC")
    result = caught.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"][0]["code"] == "solar_aa1996_unavailable"


def test_text_receipt_does_not_resolve_unused_aa1996_library(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("unused library")
    )
    assert solar_model_policy.solar_model_environment_receipt(resolve_source=False) == {
        "mode": "aa1996",
        "source_resolution": "not_observed_in_business_output",
        "scope": "Configuration only; no independent solar source was resolved for this receipt. Actual consumed models are reported separately in provenance.",
    }


def test_strict_jpl_conflict_precedes_aa1996_loading(monkeypatch):
    from fatebridge.core.solar_term_runtime import solar_term_cache_context

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "de440.eph")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("conflicting model loaded")
    )
    with pytest.raises(ValueError, match="AA1996.*conflicts"):
        solar_term_cache_context(almanac.swe, year=2026)


@pytest.mark.parametrize("year", [1799, 2201])
def test_aa1996_input_years_do_not_expand_silently(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    monkeypatch.setattr(
        aa1996_solar, "cache_key", lambda: pytest.fail("out-of-policy model loaded")
    )
    with pytest.raises(ValueError, match="1800..2200"):
        solar_model_policy.solar_model_cache_key(year=year)


@pytest.mark.parametrize(
    "value", [True, "2451545", float("nan"), float("inf"), 10**1000]
)
def test_invalid_epoch_never_reaches_native_code(value, monkeypatch):
    monkeypatch.setattr(
        aa1996_solar, "_selected", lambda: pytest.fail("invalid input reached C")
    )
    with pytest.raises(ValueError, match="finite numeric"):
        aa1996_solar.solar_longitudes_tt([value])


@pytest.mark.parametrize(
    "fault",
    [
        {"abi_version": True},
        {"model_id": "moshier"},
        {"source_profile_sha256": "0" * 64},
    ],
)
def test_incorrect_model_claims_are_rejected_before_loading(
    fault, monkeypatch, tmp_path
):
    profile, digest = source_profile()
    import platform

    manifest = dict(
        model_id=profile["model_id"],
        version=profile["version"],
        abi_version=1,
        source_profile_sha256=digest,
        calculation_source_sha256=profile["calculation_source_sha256"],
        system=platform.system(),
        machine=platform.machine(),
        **{},
    )
    manifest.update(fault)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        aa1996_solar.ctypes,
        "CDLL",
        lambda *a, **k: pytest.fail("incorrect model loaded"),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"


def test_duplicate_manifest_field_is_not_last_value_wins(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        '{"model_id":"moshier","model_id":"fatebridge_moshier_aa1996_solar_v1"}'
    )
    with pytest.raises(EphemerisSourceError) as caught:
        aa1996_solar._Source(path, aa1996_solar._signature(path))
    assert caught.value.reason == "solar_aa1996_invalid"


def test_build_rejects_unpinned_bytes_and_keeps_failure_directory(
    tmp_path, monkeypatch
):
    import fatebridge.fetch_aa1996 as builder

    monkeypatch.setattr(builder.platform, "system", lambda: "Darwin")
    bad = tmp_path / "incorrect-source.tar.gz"
    bad.write_bytes(b"not the pinned source")
    destination = tmp_path / "attempt"
    monkeypatch.setattr(
        builder.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("unexpected download"),
    )
    with pytest.raises(ValueError, match="pinned source bytes"):
        build(destination, swiss_archive=bad, aa56_archive=bad, compiler="not-used")
    assert destination.is_dir() and not (destination / "manifest.json").exists()


def test_default_fengshui_model_keeps_the_existing_five_second_guard(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    resolution = solar_term_resolution(2026, "立春", "UTC")
    policy = boundary_model_policy(resolution)
    assert policy is not None
    assert policy["operational_guard_seconds"] == 5.0
    assert policy["scope"] == "candidate_preservation_not_numerical_accuracy_acceptance"
    instant = datetime.fromisoformat(resolution["moment"])
    assert (
        boundary_uncertainty_reason(instant + timedelta(seconds=4), resolution)
        is not None
    )
    assert (
        boundary_uncertainty_reason(instant + timedelta(seconds=6), resolution) is None
    )


def test_default_fengshui_source_is_an_orbit_record_crossing(monkeypatch):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    resolution = solar_term_resolution(2026, "立春", "UTC")
    assert resolution["ephemeris_model"] == de440_solar.MODEL_ID
    assert resolution["ephemeris_model_scope"] == "named_ephemeris_solar_crossing"
    assert resolution["solar_model_details"]["reference_event_table_used"] is False


def test_default_shared_fengshui_source_matches_all_protocols(
    monkeypatch, surface_calls
):
    monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["fengshui_assess"]
    payload = inputs(spec)
    options = dict(include_snapshot_text=False, response_char_limit=0)
    http, mcp, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False, rest_as_of=AS_OF
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error and code == 0
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        assert (
            de440_solar.MODEL_ID
            in output["run_metadata"]["provenance"]["ephemeris_model"]
        )


def test_one_bad_blob_preserves_the_existing_manifest(tmp_path, monkeypatch):
    payloads = {"a.se1": b"SW-a-reference", "b.se1": b"SW-b-reference"}
    rows = [
        {
            "type": "blob",
            "path": "ephe/" + name,
            "size": len(data),
            "sha": hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest(),
        }
        for name, data in payloads.items()
    ]

    def download(url):
        if "/git/trees/" in url:
            return json.dumps({"truncated": False, "tree": rows}).encode()
        return payloads["a.se1"] if url.endswith("a.se1") else b"SW-corrupt"

    monkeypatch.setattr(builder, "download", download)
    output = tmp_path / "catalog.json"
    output.write_bytes(b"existing edition")
    with pytest.raises(ValueError, match="No manifest written"):
        builder.build("a" * 40, tmp_path / "cache", output)
    assert output.read_bytes() == b"existing edition"
    assert (tmp_path / "cache/a.se1").read_bytes() == payloads["a.se1"]
    assert not (tmp_path / "cache/b.se1").exists()


def test_mutable_branch_name_is_not_an_edition_identifier(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "download", lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError, match="full upstream commit"):
        builder.build("master", tmp_path / "cache", tmp_path / "catalog.json")


@pytest.mark.parametrize(
    "separator,search_path,expected",
    [
        (":", "first;second:third", ["first", "second", "third"]),
        (";", r"C:\ephe;D:\other", [r"C:\ephe", r"D:\other"]),
        (":", ";first::first", [".", "first", "first"]),
        (";", ";first;;first", [".", "first", "first"]),
        (":", "first::", ["first", "/"]),
        (";", "first;;", ["first", "\\"]),
        (":", "a;" * 21 + "last", ["a"] * 19 + ["a;a;last"]),
        (":", None, []),
        (";", "", []),
    ],
)
def test_search_order_and_platform_separators(
    separator, search_path, expected, monkeypatch
):
    monkeypatch.setattr(ephemeris_paths.os, "pathsep", separator)
    monkeypatch.setattr(ephemeris_paths.os, "sep", "\\" if separator == ";" else "/")
    assert [
        str(directory)
        for directory in ephemeris_paths.ephemeris_search_directories(search_path)
    ] == expected


@pytest.mark.parametrize("reason", sorted(EphemerisSourceError.MESSAGES))
def test_typed_source_failure_is_not_rewritten_as_missing_dependency(reason):
    @calculation_guard("source check")
    def reject():
        raise EphemerisSourceError(reason)

    result = reject()
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503
    assert result["retryable"] is False
    assert result["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
    assert result["error"] == EphemerisSourceError.MESSAGES[reason]


def test_arbitrary_raw_details_cannot_be_used_as_safe_source_messages():
    private = "/private/server/ephemeris/data"
    with pytest.raises(ValueError) as caught:
        EphemerisSourceError(private)
    assert private not in str(caught.value)


@pytest.mark.parametrize(
    "error,code,status",
    [
        (ImportError("swisseph unavailable"), "dependency_missing", 503),
        (ValueError("missing ephemeris dependency"), "dependency_missing", 503),
        (ValueError("Invalid calendar date"), "validation_error", 400),
    ],
)
def test_other_error_classifications_are_preserved(error, code, status):
    result = handle_calculation_error(error, "legacy check")
    assert result["error_code"] == code
    assert result["status_code"] == status


@pytest.mark.parametrize(
    "label",
    ["GMT", "GMT0", "GMT+0", "GMT-0", "gmt", "gMt+00:00", "GMT-00:00:00"],
)
def test_gmt_zero_retains_its_declared_label_and_known_instant(label):
    # Official tzdata2026e etcetera/backward and independent C observations
    # agree on offset0/GMT/DST0 for the four exact legacy IANA names. The
    # parser also accepts case-insensitive and numeric spellings of GMT.
    zone = parse_timezone_name(label)
    for year in (1800, 1900, 2000, 2038, 2399):
        local = datetime(year, 9, 1, 12, tzinfo=zone)
        validate_local_clock(local)
        assert local.tzname() == "GMT"
        assert local.utcoffset() == timedelta(0)
        assert local.dst() is None
        assert local.astimezone(timezone.utc) == local
    assert timezone_rules_metadata(label) == {
        "provider": "datetime.timezone",
        "database": "explicit_fixed_offset",
    }


@pytest.mark.parametrize("label", ["UTC", "Z", "+00:00", "-00:00", "0", "UTC+0"])
def test_other_known_zero_spellings_keep_their_utc_label(label):
    assert parse_timezone_name(label).tzname(None) == "UTC"


def test_nonzero_gmt_offset_keeps_its_numeric_convention():
    zone = parse_timezone_name("GMT+8")
    assert zone.tzname(None) == "UTC+08:00"
    assert datetime(1900, 1, 1, 12, tzinfo=zone).astimezone(timezone.utc) == datetime(
        1900, 1, 1, 4, tzinfo=timezone.utc
    )


@pytest.mark.parametrize("start,end", [(0, 30), (30, 60), (-30, 0)])
def test_exact_boundary_event_included_only_at_window_start(monkeypatch, start, end):
    monkeypatch.setattr(subject, "_phase", lambda t: (12 * t) % 360)
    result = subject.phase_events_tt(start, end)
    assert [r["phase_kind"] for r in result["events"]] == list(subject.KINDS)
    assert [F(r["julian_day_tt_exact"]) for r in result["events"]] == [
        F(start) + F(15, 2) * i for i in range(4)
    ]
    assert result["timescale"] == "TT"
    assert not result["utc_or_local_civil_calendar_assigned"]
    assert not result["source_profile_reconstruction"]
    assert not result["physical_accuracy_claimed_from_numerical_resolution"]


def test_wrap_crossing_and_subday_windows_do_not_skip_new_moon(monkeypatch):
    monkeypatch.setattr(subject, "_phase", lambda t: (350 + 12 * t) % 360)
    result = subject.phase_events_tt(0, 1)
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["phase_kind"] == "new_moon"
    assert abs(F(event["julian_day_tt_exact"]) - F(5, 6)) <= F(1, 172800000)
    assert not subject.phase_events_tt(0.1, 0.2)["events"]


@pytest.mark.parametrize(
    "window", [(0, 0), (1, 0), (0, 3661), (math.nan, 1), (0, math.inf)]
)
def test_invalid_or_unbounded_windows_rejected(window):
    with pytest.raises(ValueError):
        subject.phase_events_tt(*window)


@pytest.mark.parametrize("window", [(False, 1), (0, True), ("0", 1)])
def test_no_implicit_time_conversion_or_boolean_jd(window):
    with pytest.raises(TypeError):
        subject.phase_events_tt(*window)


@pytest.mark.parametrize(
    "fn", [lambda t: 0, lambda t: (350 - t) % 360, lambda t: 40 * t]
)
def test_daily_nonprogress_or_large_advance_is_not_silently_unwrapped(monkeypatch, fn):
    monkeypatch.setattr(subject, "_phase", fn)
    with pytest.raises(ValueError):
        subject.phase_events_tt(0, 1)


def test_actual_ephemeris_model_is_checked_for_both_luminaries(monkeypatch):
    calls = []

    def fake(op, t, body, flag):
        calls.append(body)
        return (10, 0, 0, 13 if body == subject.swe.MOON else 1), (
            subject.swe.FLG_SWIEPH
            if body == subject.swe.MOON
            else subject.swe.FLG_MOSEPH
        )

    monkeypatch.setattr(subject, "ephemeris_call", fake)
    with pytest.raises(ValueError, match="Moshier"):
        subject._phase(2451545)
    assert calls == [subject.swe.SUN, subject.swe.MOON]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_ephemeris_nonfinite_longitude_rejected(monkeypatch, bad):
    monkeypatch.setattr(
        subject, "ephemeris_call", lambda *a: ((bad, 0, 0, 1), subject.swe.FLG_MOSEPH)
    )
    with pytest.raises(ValueError, match="有限"):
        subject._phase(2451545)


def test_nonpositive_relative_speed_is_not_used_for_search(monkeypatch):
    monkeypatch.setattr(
        subject, "ephemeris_call", lambda *a: ((10, 0, 0, 1), subject.swe.FLG_MOSEPH)
    )
    with pytest.raises(ValueError, match="递增"):
        subject._phase(2451545)


def test_native_moshier_all_quarters_close_the_geometric_target():
    result = subject.phase_events_tt(2451545, 2451580)
    assert len(result["events"]) in (4, 5)
    assert set(r["phase_kind"] for r in result["events"]) == set(subject.KINDS)
    for row in result["events"]:
        at = float(F(row["julian_day_tt_exact"]))
        difference = (
            subject._phase(at) - row["target_elongation_degrees"] + 180
        ) % 360 - 180
        # Numerical root/rounding check; independent reference accuracy tested separately.
        assert abs(difference) < 1e-6


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_complete_moshier_frame_receipt_roundtrips_actual_interfaces(
    analytical, monkeypatch, capsys, zodiacal
):
    spec = next(spec for spec in CATALOG if spec.key == "otherbu")
    payload = dict(
        planet="Saturn",
        sign="Aries",
        house=0,
        date="2000-01-01",
        time="12:00",
        zone="UTC",
        gps_lat=51.5,
        gps_lon=0,
        zodiacal=zodiacal,
    )
    fields = ["chart.chart.objects", "chart.params.chart_profile.longitude_motion"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2000-01-02T12:00:00Z",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", options["as_of"]),
        ],
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(invoke())
    assert not native.is_error, native
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    results = [
        {k: v for k, v in result.items() if k != "run_metadata"}
        for result in (response.json(), native.structured_content, cli)
    ]
    assert results[0] == results[1] == results[2]
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        chart = result["chart"]
        policy = chart["params"]["chart_profile"]["longitude_motion"]
        objects = {row["id"]: row for row in chart["chart"]["objects"]}
        frame = "lahiri" if zodiacal else "tropical"
        for body in moshier_motion.TARGETS:
            actual = objects[body]["motion"]
            receipt = policy["complete_position_derivatives"][body + ":" + frame]
            assert actual["source_model"] == "moshier"
            assert actual["reference_frame"] == receipt["reference_frame"]
            assert actual["method_id"] == receipt["method_id"]
            assert receipt["status"] == actual["correction_status"] == "applied"
            assert actual["longitude_speed"] == (
                actual["native_longitude_speed"]
                + actual.get("rotation_correction", 0)
                + actual["position_derivative_correction"]
            )
            if zodiacal:
                assert "rotation_correction" not in actual


def test_missing_derivative_receipt_does_not_invent_an_algorithm_version():
    motion = context_motion(
        "Moon",
        {"Moon": 13.0},
        {"Moon": "moshier"},
        "tropical_ecliptic_of_date",
        {
            "longitude_speed_native": 12.9,
            "longitude_speed_position_derivative_correction": 0.1,
        },
    )
    assert motion["method_id"] == "complete_position_derivative_method_unavailable"
    assert motion["correction_status"] == "applied"


@pytest.mark.parametrize("impact,cell", [("0.5099999999", 50), ("0.5100000001", 51)])
def test_stable_cross_product_cell_resolves_the_ill_conditioned_dot_margin(
    impact, cell
):
    radius = D("0.00465")
    ratio = D("0.8")
    result = stable_interpolation_cell(D(impact), radius, ratio)
    assert result["cell"] == cell
    assert result["status"] == "interior_sampled_cell"
    old_margin = 64 * D.from_float(2.0**-52) / (radius * radius * D(impact))
    assert old_margin > abs(D(impact) - D("0.51"))
    assert D.from_float(result["arithmetic_margin_fraction"]) < abs(
        D(impact) - D("0.51")
    )


@pytest.mark.parametrize("impact", ["0", "0.51", "0.5100000000001", "1"])
def test_a_knot_or_unresolved_margin_does_not_authorize_a_fit(impact):
    result = stable_interpolation_cell(D(impact), D("0.00465"), D("0.8"))
    assert result["cell"] is None and result["status"] == "boundary_ambiguous"


def test_invalid_geometry_cannot_become_a_source_cell():
    with pytest.raises(EphemerisSourceError):
        stable_interpolation_cell(D("-0.1"), D("0.00465"), D("0.8"))
