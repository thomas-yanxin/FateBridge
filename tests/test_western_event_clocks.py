"""Independent operands and hand arithmetic for explicit Western event clocks."""

import copy
import csv
import hashlib
import io
import json
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from fatebridge.core import western_event_clock as clock
from fatebridge.core.output_western import WesternEventClockConversion
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.utils.errors import EphemerisSourceError

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_FILE = FIXTURES / "western-event-clocks-reference.json"
REFERENCE = json.loads(REFERENCE_FILE.read_text())
SEALED_SHA = "1af9b8f064b1fe975a69cfbbb8b48cb7336814c0f4104b732e2e478db9d112c9"


def event(wall="2000-01-01T01:00:00", longitude=15.0, **kw):
    return clock.build_event_subject(
        name="synthetic event clock control",
        local_datetime=datetime.fromisoformat(wall),
        longitude=longitude,
        latitude=40,
        **kw,
    )


def test_pre_edit_reference_and_reused_jpl_operands_have_not_changed():
    assert hashlib.sha256(REFERENCE_FILE.read_bytes()).hexdigest() == SEALED_SHA
    old = FIXTURES / "guolao-apparent-clock-v1"
    manifest = json.loads((old / "reference.json").read_text())
    for asset in manifest["assets"]:
        raw = (old / asset["path"]).read_bytes()
        assert len(raw) == asset["bytes"]
        assert hashlib.sha256(raw).hexdigest() == asset["sha256"]

    def rows(name):
        text = json.loads((old / name).read_text())["result"]
        return list(csv.reader(io.StringIO(text.split("$$SOE\n")[1].split("$$EOE")[0])))

    for i, row in enumerate(REFERENCE["apparent_inverse_controls"]):
        ra = Fraction(rows("geocentric_sun.json")[i][3].strip())
        gast = Fraction(rows("greenwich_sidereal.json")[i][3].strip())
        lon = (1 + Fraction(i, 60) - 12 - gast) * 15 + ra
        assert str(lon) == row["longitude_exact"]
        assert float(lon) == row["longitude"]


@pytest.mark.parametrize("row", REFERENCE["historical_lmt_controls"])
def test_lmt_hand_arithmetic_and_same_native_epoch(row):
    subject, receipt = event(
        row["wall"], row["longitude"], clock_basis="local_mean_solar"
    )
    assert (
        abs(
            (
                datetime.fromisoformat(receipt["converted_utc"])
                - datetime.fromisoformat(row["utc"])
            ).total_seconds()
        )
        <= REFERENCE["lmt_utc_tolerance_seconds"]
    )
    direct = build_native_subject(
        name=subject.name,
        local_datetime=datetime.fromisoformat(row["utc"]),
        longitude=row["longitude"],
        latitude=40,
        timezone_name="UTC",
        house_system="R",
    )
    assert subject.points == direct.points
    assert subject.julian_day == direct.julian_day
    assert subject.julian_day_tt == direct.julian_day_tt
    WesternEventClockConversion.model_validate(receipt)
    assert receipt["solar_conversion"]["solar_model_call_count"] == 0
    assert (
        receipt["clock_chart_source_comparison"]["status"]
        == "no_solar_position_dependency"
    )
    assert not receipt["source_clock_identification_performed"]
    assert not receipt["input_clock_accuracy_certified"]


@pytest.mark.parametrize("row", REFERENCE["apparent_inverse_controls"])
def test_lat_inverse_against_reused_external_jpl_ra_and_gast(row):
    subject, receipt = event(
        row["wall"], row["longitude"], clock_basis="local_apparent_solar"
    )
    assert (
        abs(
            (
                datetime.fromisoformat(receipt["converted_utc"])
                - datetime.fromisoformat(row["utc"])
            ).total_seconds()
        )
        < REFERENCE["apparent_utc_tolerance_seconds"]
    )
    assert receipt["julian_day_ut1"] == subject.julian_day
    assert receipt["julian_day_tt"] == subject.julian_day_tt
    solar = receipt["solar_conversion"]
    assert abs(solar["ut1_roundtrip_error_seconds"]) <= 0.0002
    assert abs(solar["input_clock_roundtrip_error_seconds"]) <= 0.0002
    assert solar["solar_reference"] == "geocentric_apparent_sun"
    assert not solar["clock_accuracy_certified"] and not solar["measured_eop_applied"]
    comparison = receipt["clock_chart_source_comparison"]
    assert comparison["status"] == "compatible_observed_sun_contexts"
    assert set(comparison["chart_sun_source"]["by_factor"]) == {"Sun"}
    WesternEventClockConversion.model_validate(receipt)


def test_modern_lmt_is_ut1_not_a_utc_label():
    # Analytic 01:00 LMT at 15E is midnight UT1, JD2451544.5.
    subject, receipt = event(clock_basis="local_mean_solar")
    assert abs(subject.julian_day - 2451544.5) * 86400 <= 0.0002
    seconds = (
        datetime(2000, 1, 1, tzinfo=timezone.utc)
        - datetime.fromisoformat(receipt["converted_utc"])
    ).total_seconds()
    # Same epoch as the frozen DUT1 operand, not a new sky observation.
    assert (
        abs(seconds - float(REFERENCE["apparent_inverse_controls"][0]["dut1_seconds"]))
        < 0.001
    )


def test_civil_default_is_explicit_legacy_policy_and_sky_stays_identical():
    a, ra = event()
    b, rb = event(timezone_name="+08:00")
    assert a.points == b.points and a.julian_day_tt == b.julian_day_tt
    assert ra["effective_civil_timezone"] == rb["effective_civil_timezone"] == "+08:00"
    assert ra["timezone_selection_source"] == "legacy_api_default"
    assert rb["timezone_selection_source"] == "caller_supplied"
    assert ra["solar_conversion"] is None


@pytest.mark.parametrize(
    "model,prefix",
    [(AstroHoraryRequest, "question"), (AstroElectionRequest, "candidate")],
)
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_solar_requests_reject_every_explicit_civil_zone(model, prefix, basis):
    base = {
        f"{prefix}_year": 2000,
        f"{prefix}_month": 1,
        f"{prefix}_day": 1,
        f"{prefix}_hour": 1,
        f"{prefix}_clock_basis": basis,
        "longitude": 15,
        "latitude": 40,
    }
    assert model.model_validate(base).timezone_name is None
    for zone in ("UTC", "+00:00", "+08:00", "Europe/London", ""):
        with pytest.raises(ValidationError, match="omit timezone_name"):
            model.model_validate({**base, "timezone_name": zone})


@pytest.mark.parametrize(
    "kw",
    [
        {"clock_basis": "auto"},
        {"clock_basis": "local_mean_solar", "timezone_name": "UTC"},
        {"clock_basis": "local_apparent_solar", "timezone_name": "+08:00"},
    ],
)
def test_direct_call_cannot_bypass_clock_contract(kw):
    with pytest.raises(ValueError):
        event(**kw)


def test_civil_dst_gap_does_not_make_a_solar_label_nonexistent():
    with pytest.raises(ValueError, match="nonexistent"):
        event("2024-03-31T02:30:00", timezone_name="Europe/Paris")
    _, receipt = event("2024-03-31T02:30:00", clock_basis="local_mean_solar")
    assert receipt["effective_civil_timezone"] is None
    assert receipt["chart_timezone"] == "UTC"


@pytest.mark.parametrize("fault", ["model", "edition", "hash"])
def test_clock_and_chart_cannot_silently_mix_observed_sun_sources(fault):
    row = {"model": "swieph", "status": "se1_contexts_identified", "file_ids": ["test"]}
    source = {
        "by_factor": {"equatorial_Sun": row},
        "files": [
            {
                "id": "test",
                "slot": 0,
                "filename": "synthetic.se1",
                "de_number": 431,
                "sha256": "a",
            }
        ],
        "has_unidentified_sources": False,
    }
    native = copy.deepcopy(source)
    native["by_factor"] = {"Sun": copy.deepcopy(row)}
    solar = {
        "solar_source_comparison": {
            "physical_ephemeris_sources": [source],
            "has_unidentified_sources": False,
        }
    }
    if fault == "model":
        native["by_factor"]["Sun"]["model"] = "jpl"
    elif fault == "edition":
        native["files"][0]["de_number"] = 440
    else:
        native["files"][0]["sha256"] = "b"
    with pytest.raises(EphemerisSourceError, match="inconsistent"):
        clock._compare_sun_sources(
            solar,
            SimpleNamespace(calculation_basis={"physical_ephemeris_source": native}),
        )


@pytest.mark.parametrize("axis", ["julian_day", "julian_day_tt"])
def test_chart_axis_mismatch_fails_before_returning_a_receipt(monkeypatch, axis):
    real = clock.build_subject

    def shifted(**kw):
        s = real(**kw)
        return replace(s, **{axis: getattr(s, axis) + 1 / 86400})

    monkeypatch.setattr(clock, "build_subject", shifted)
    with pytest.raises(EphemerisSourceError, match="physical time axes"):
        event(clock_basis="local_mean_solar")


def test_changed_tt_mapping_after_lat_inversion_is_not_hidden_by_matching_sources(
    monkeypatch,
):
    real = clock.resolve_solar_epoch

    def shifted(*args, **kw):
        at, receipt = real(*args, **kw)
        receipt["solar_source_comparison"]["observations"][-1]["julian_day_tt"] += (
            1 / 86400
        )
        return at, receipt

    monkeypatch.setattr(clock, "resolve_solar_epoch", shifted)
    with pytest.raises(EphemerisSourceError, match="physical time axes"):
        event(clock_basis="local_apparent_solar")


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_solar_planetary_weekday_uses_local_opening_sunrise_date(monkeypatch, basis):
    from fatebridge.core.astro import classical
    from fatebridge.core.astro.geometry import _julian_day

    # Hand-selected UT1 arcs isolate the date/weekday policy. These are not
    # measured sunrise times or an independent horizon-geometry validation.
    rise = _julian_day(datetime(1999, 12, 31, 20, tzinfo=timezone.utc))
    setting = rise + 0.5

    def bracket(at, longitude, latitude, *, rising):
        return (rise, rise + 1) if rising else (setting - 1, setting)

    monkeypatch.setattr(classical, "_bracket_sun_event", bracket)
    civil = classical._planetary_hours(rise + 0.1, 150, 40, "UTC")
    solar = classical._planetary_hours(
        rise + 0.1, 150, 40, "UTC", weekday_clock_basis=basis
    )
    assert civil["day_ruler"] == "Venus"  # Friday on the UTC carrier.
    assert solar["day_ruler"] == "Saturn"  # Saturday locally.
    assert solar["weekday_opening_sunrise_label"].startswith("2000-01-01T")
    assert solar["weekday_clock_basis"] == basis
    for key in (
        "hour_number",
        "is_day",
        "arc_start_jd_ut1",
        "arc_end_jd_ut1",
        "planetary_day_start_utc",
    ):
        assert civil[key] == solar[key]
