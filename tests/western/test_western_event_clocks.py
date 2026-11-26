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
from fatebridge.core.contracts.output_western import WesternEventClockConversion
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.utils.errors import EphemerisSourceError

FIXTURES = Path(__file__).parents[1] / "fixtures"
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


def test_pre_edit_reference_and_reused_jpl_operands_have_not_changed() -> None:
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
def test_lmt_hand_arithmetic_and_same_native_epoch(row) -> None:
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
def test_lat_inverse_against_reused_external_jpl_ra_and_gast(row) -> None:
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


def test_modern_lmt_is_ut1_not_a_utc_label() -> None:
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


def test_civil_default_is_explicit_legacy_policy_and_sky_stays_identical() -> None:
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
def test_solar_requests_reject_every_explicit_civil_zone(
    model, prefix: str, basis: str
) -> None:
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
def test_direct_call_cannot_bypass_clock_contract(kw) -> None:
    with pytest.raises(ValueError):
        event(**kw)


def test_civil_dst_gap_does_not_make_a_solar_label_nonexistent() -> None:
    with pytest.raises(ValueError, match="nonexistent"):
        event("2024-03-31T02:30:00", timezone_name="Europe/Paris")
    _, receipt = event("2024-03-31T02:30:00", clock_basis="local_mean_solar")
    assert receipt["effective_civil_timezone"] is None
    assert receipt["chart_timezone"] == "UTC"


@pytest.mark.parametrize("fault", ["model", "edition", "hash"])
def test_clock_and_chart_cannot_silently_mix_observed_sun_sources(fault: str) -> None:
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
def test_chart_axis_mismatch_fails_before_returning_a_receipt(
    monkeypatch: pytest.MonkeyPatch, axis: str
) -> None:
    real = clock.build_subject
    field = {"julian_day": "ut1", "julian_day_tt": "tt"}[axis]

    def shifted(**kw):
        subject = real(**kw)
        instant = getattr(subject, field)
        shifted_instant = replace(instant, days=instant.days + Fraction(1, 86400))
        return replace(subject, **{field: shifted_instant})

    monkeypatch.setattr(clock, "build_subject", shifted)
    with pytest.raises(EphemerisSourceError, match="physical time axes"):
        event(clock_basis="local_mean_solar")


def test_changed_tt_mapping_after_lat_inversion_is_not_hidden_by_matching_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
def test_solar_planetary_weekday_uses_local_opening_sunrise_date(
    monkeypatch: pytest.MonkeyPatch, basis: str
) -> None:
    from fatebridge.core.astro import classical
    from fatebridge.core.astro.geometry import _julian_day

    # Hand-selected UT1 arcs isolate the date/weekday policy. These are not
    # measured sunrise times or an independent horizon-geometry validation.
    rise = _julian_day(datetime(1999, 12, 31, 20, tzinfo=timezone.utc))
    setting = rise + 0.5

    from tests.support.solar_events import fixed_crossings

    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((rise, rise + 1), (setting - 1, setting)),
    )
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


def test_civil_planetary_weekday_requires_a_defined_opening_sunrise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.astro import classical
    from fatebridge.core.astro.iers_ut1 import use_ut1_source
    from fatebridge.core.astro.lilly_radicality_inputs import collect_radicality_hour
    from tests.support.solar_events import fixed_crossings

    # Fixed UT1 points from the Davis observer after the station reopened.
    # Its opening sunrise still falls in the earlier -00 TZif interval.
    query = 2440253.520833784
    rise, setting = 2440253.3893537987, 2440254.1933527226
    longitude, latitude = 77.96666666666667, -68.58333333333333
    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((rise,), (setting,)),
    )
    with use_ut1_source("iers_c04"):
        assert (
            classical._planetary_hours(query, longitude, latitude, "Antarctica/Davis")
            is None
        )
        utc = classical._planetary_hours(query, longitude, latitude, "UTC")
        subject = SimpleNamespace(
            julian_day=query, lng=longitude, lat=latitude, tz_str="Antarctica/Davis"
        )
        davis_inputs = collect_radicality_hour(subject)
        subject.tz_str = "UTC"
        utc_inputs = collect_radicality_hour(subject)

        with monkeypatch.context() as missing:
            missing.setattr(
                classical, "solar_crossings_in_window", fixed_crossings([], [])
            )
            no_arc = collect_radicality_hour(subject)

        def unavailable_conversion(*args):
            raise ValueError("ordinary unavailable quantity")

        with monkeypatch.context() as ordinary:
            ordinary.setattr(classical, "utc_calendar_from_tt", unavailable_conversion)
            assert classical._planetary_hours(query, longitude, latitude, "UTC") is None
            no_label = collect_radicality_hour(subject)

    for unavailable in (no_arc, no_label):
        assert unavailable["status"] == "unavailable" and unavailable["hour"] is None
        assert (
            unavailable["unavailable_reason"] == "sunrise_sunset_interval_unavailable"
        )
    assert davis_inputs["status"] == "unavailable" and davis_inputs["hour"] is None
    assert davis_inputs["actual_solar_backend_verified"] is False
    assert davis_inputs["source_method_acceptance"] is False
    assert (
        davis_inputs["unavailable_reason"] == "opening_sunrise_civil_weekday_undefined"
    )
    assert utc_inputs["hour"] == utc and utc_inputs["unavailable_reason"] is None

    assert utc is not None
    assert utc["day_ruler"] == "Venus"
    assert utc["hour_ruler"] == "Mercury"


@pytest.mark.parametrize(
    ("offset", "hour_ruler", "is_day"),
    [(0.02, "Saturn", True), (0.52, "Mercury", False)],
)
def test_solar_planetary_weekday_keeps_c04_opening_ut1(
    monkeypatch: pytest.MonkeyPatch, offset: float, hour_ruler: str, is_day: bool
) -> None:
    from fatebridge.core.astro import classical
    from fatebridge.core.astro.iers_ut1 import use_ut1_source
    from tests.support.solar_events import fixed_crossings

    rise = float.fromhex("0x1.2b42c60440000p+21")
    longitude = -90.7470703135
    # The supplied UT1 plus longitude/360 is about 0.24 μs before local
    # midnight. Nearest-even rounds to Saturday, while the UTC datetime
    # round trip moves the sample to Friday on the solar display grid.
    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((rise, rise + 1), (rise - 0.5, rise + 0.5)),
    )
    with use_ut1_source("iers_c04"):
        result = classical._planetary_hours(
            rise + offset,
            longitude,
            40.0,
            "UTC",
            weekday_clock_basis="local_mean_solar",
        )

    assert result["weekday_opening_sunrise_label"] == "2000-01-01T00:00:00"
    assert result["day_ruler"] == "Saturn"
    assert result["hour_ruler"] == hour_ruler
    assert result["is_day"] is is_day
    assert result["hour_number"] == 1
