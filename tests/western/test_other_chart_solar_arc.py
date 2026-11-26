"""Independent Sun references, source rounding intervals and mixed-layer algebra."""

import json
import math
import random
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.astro.solar_arc import (
    biwheel_geometry,
    rotate_factors,
    solar_arc_state,
)
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroGermanyRequest,
    AstroGuolaoRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from tests.fixtures.surface_payloads import astro_payload

ROOT = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((ROOT / "uranian-solar-arc-horizons.json").read_text())
STATIC = json.loads((ROOT / "uranian-al319-static.json").read_text())
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["birth_utc"])
def test_actual_sun_and_true_arc_against_independent_horizons(case) -> None:
    birth = datetime.fromisoformat(case["birth_utc"])
    state = solar_arc_state(
        birth, ephemeris_time(birth).jd_tt, datetime.fromisoformat(case["analysis_utc"])
    )
    positions = {r["utc"]: r["apparent_ecliptic_longitude"] for r in REFERENCE["rows"]}
    first, last = positions[case["birth_utc"]], positions[case["progressed_utc"]]
    for actual, expected in [
        (state["natal_tropical_sun"], first),
        (state["progressed_tropical_sun"], last),
    ]:
        assert (
            abs((actual - expected + 180) % 360 - 180) * 3600
            <= REFERENCE["position_tolerance_arcseconds"]
        )
    expected = (last - first) % 360
    assert (
        abs(state["solar_arc_degrees"] - expected) * 3600
        <= REFERENCE["arc_tolerance_arcseconds"]
    )
    assert state["key_years"] == pytest.approx(case["key_years"], abs=4e-14)
    assert state["progressed_julian_day_tt"] - state[
        "birth_julian_day_tt"
    ] == pytest.approx(case["key_years"], abs=5e-10)
    assert abs(state["difference_from_one_degree_per_year"]) > 0.1


def test_publisher_static_twenty_two_pairs_have_compatible_rounding_intervals() -> None:
    # These are source-author printed numbers, not our birth-chart calculation.
    def minutes(parts):
        return parts[0] * 1800 + parts[1] * 60 + parts[2]

    low, high = Fraction(959, 2), Fraction(961, 2)  # printed 8deg00 +/- half minute
    differences = []
    for row in STATIC["rows"]:
        difference = (minutes(row["directed"]) - minutes(row["natal"])) % 21600
        differences.append(difference)
        # Difference of two independently rounded 1-minute values has width 2'.
        low = max(low, Fraction(difference - 1))
        high = min(high, Fraction(difference + 1))
    assert len(STATIC["rows"]) == 22
    assert low == 480 and high == Fraction(961, 2)
    assert set(differences) == {480, 481}
    # A constructed interval witness, explicitly not the unknown original raw
    # coordinates: demonstrate that one common arc can explain every row.
    arc_minutes = (low + high) / 2
    witness = {}
    for row, difference in zip(STATIC["rows"], differences):
        correction = Fraction(3, 8) if difference == 481 else 0
        witness[row["id"]] = float((Fraction(minutes(row["natal"])) + correction) / 60)
    rotated = rotate_factors(witness, float(arc_minutes / 60))
    for row in STATIC["rows"]:
        residual = (
            Fraction(rotated[row["id"]]) * 60 - minutes(row["directed"]) + 10800
        ) % 21600 - 10800
        assert abs(residual) <= Fraction(1, 2)
    # Treating every printed input as exact would contradict some published
    # outputs. The production engine must not add arbitrary rounding repairs.
    assert rotate_factors({"Sun": 214 + 23 / 60}, 8)["Sun"] == pytest.approx(
        222 + 23 / 60
    )


@pytest.mark.parametrize("period", [90, 45])
def test_all_biwheel_contacts_match_independent_trigonometric_equations(
    period: int,
) -> None:
    rng = random.Random(22971)
    natal = {str(i): rng.uniform(0, 360) for i in range(7)}
    arc = 13.421
    shifted = {k: v + arc for k, v in natal.items()}
    result = biwheel_geometry(natal, arc)["dials"][str(period)]

    def residual(value):
        phi = math.pi * value / period
        return abs(math.atan2(math.sin(phi), math.cos(phi))) * period / (2 * math.pi)

    two = {
        (a, b)
        for a in natal
        for b in natal
        if residual(2 * (shifted[a] - natal[b])) <= 1
    }
    assert {(r["id_a"], r["id_b"]) for r in result["two_factor_contacts"]} == two
    pairs = list(combinations(natal, 2))
    expected_three = set()
    for point in natal:
        for a, b in pairs:
            if residual(2 * shifted[point] - natal[a] - natal[b]) <= 1:
                expected_three.add((point, "solar_arc", a, b, "natal"))
            else:
                pass
            if residual(2 * natal[point] - shifted[a] - shifted[b]) <= 1:
                expected_three.add((point, "natal", a, b, "solar_arc"))
            else:
                pass
    assert {
        (r["point"], r["point_layer"], r["id_a"], r["id_b"], r["axis_layer"])
        for r in result["three_factor_contacts"]
    } == expected_three
    four = {
        (a, b, c, d)
        for a, b in pairs
        for c, d in pairs
        if residual(shifted[a] + shifted[b] - natal[c] - natal[d]) <= 1
    }
    assert {
        (r["id_a"], r["id_b"], r["id_c"], r["id_d"])
        for r in result["four_factor_contacts"]
    } == four
    for row in result["four_factor_contacts"]:
        expected = residual(
            shifted[row["id_a"]]
            + shifted[row["id_b"]]
            - natal[row["id_c"]]
            - natal[row["id_d"]]
        )
        assert row["orb"] == pytest.approx(expected, abs=2e-12)


def test_biwheel_inclusive_orb_and_zero_arc_identities_remain_explicit() -> None:
    for arc, expected in [
        (math.nextafter(1, -math.inf), True),
        (1.0, True),
        (math.nextafter(1, math.inf), False),
    ]:
        rows = biwheel_geometry({"A": 0, "B": 11}, arc)["dials"]["90"][
            "two_factor_contacts"
        ]
        assert any(r["id_a"] == "A" and r["id_b"] == "A" for r in rows) == expected
    for arc in (0, 360):
        result = biwheel_geometry({"A": 0, "B": 11, "C": 23}, arc)
        assert result["contact_counts"]["90"]["zero_arc_identities"] == 6
        assert result["contact_counts"]["45"]["zero_arc_identities"] == 6


@HAS_SWE
def test_source_directed_mc_reading_keeps_layer_identity_and_uncertainty_evidence() -> (
    None
):
    result = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        analysis_datetime=datetime(2000, 2, 1, tzinfo=timezone.utc),
        birth_time_uncertainty_minutes=5,
    )
    natal = result["midpoint_analysis"]
    directed = natal["solar_arc_analysis"]
    assert len(directed["interpretations"]) == 1
    reading = directed["interpretations"][0]
    assert reading["factor_layers"] == {
        "Mars": "natal",
        "Jupiter": "natal",
        "Zeus": "natal",
        "Midheaven": "solar_arc",
    }
    assert reading["claim_id"] != natal["interpretations"][0]["claim_id"]
    samples = directed["birth_time_sensitivity"]["samples"]
    natal_samples = {
        r["offset_seconds"]: r["factor_longitudes"]
        for r in natal["time_sensitivity"]["samples"]
    }
    matches = []
    for row in samples:
        values = natal_samples[row["offset_seconds"]]
        mc = (values["Midheaven"] + row["solar_arc_degrees"]) % 360
        theta = math.radians(values["Mars"] + values["Jupiter"] - values["Zeus"] - mc)
        actual_orb = abs(math.degrees(math.atan2(math.sin(theta), math.cos(theta))))
        assert row["source_direct_orb_degrees"] == pytest.approx(actual_orb, abs=2e-11)
        assert row["source_condition_met"] == (actual_orb <= 2)
        matches.append(actual_orb <= 2)
    pattern = directed["birth_time_sensitivity"]["source_pattern"]
    assert 0 < sum(matches) < len(matches)
    assert sum(matches) == pattern["present_sample_count"]
    assert reading["birth_time_sampled_status"] == "varies_across_samples"
    assert directed["profile"]["directed_factors_are_observations"] is False
    assert "real_world_efficacy" not in directed


@HAS_SWE
def test_solar_arc_uses_tropical_sun_even_in_a_natal_lahiri_display() -> None:
    payload = {
        **astro_payload(),
        "analysis_datetime": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    tropical = calculate_germany_chart_analysis(**payload, zodiacal=0)[
        "midpoint_analysis"
    ]
    sidereal = calculate_germany_chart_analysis(**payload, zodiacal=1)[
        "midpoint_analysis"
    ]
    t = tropical["solar_arc_analysis"]
    s = sidereal["solar_arc_analysis"]
    assert t["profile"]["solar_arc_degrees"] == s["profile"]["solar_arc_degrees"]
    for period in ("90", "45"):
        for name in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            assert [r["equation"] for r in t["dials"][period][name]] == [
                r["equation"] for r in s["dials"][period][name]
            ]


@pytest.mark.parametrize("instant", ["2000-02-01T00:00:00", "not-a-date"])
def test_public_target_instant_requires_an_explicit_offset(instant: str) -> None:
    with pytest.raises(ValidationError):
        AstroGermanyRequest.model_validate(
            {**astro_payload(), "analysis_datetime": instant}
        )


@pytest.mark.parametrize(
    "model,options",
    [
        (AstroGermanyRequest, {}),
        (AstroGuolaoRequest, {}),
        (AstroChartPolyRequest, {"chart_variant": "germany"}),
        (AstroChartPolyRequest, {"chart_variant": "guolao_chart"}),
    ],
)
def test_iso_targets_preserve_the_instant_or_identify_the_field(model, options) -> None:
    payload = {**astro_payload(), **options}
    exact = model.model_validate(
        {**payload, "analysis_datetime": "2000-02-01T08:00:00.123456000+08:00"}
    )
    assert exact.analysis_datetime.astimezone(timezone.utc) == datetime(
        2000, 2, 1, 0, 0, 0, 123456, tzinfo=timezone.utc
    )
    with pytest.raises(ValidationError) as caught:
        model.model_validate(
            {**payload, "analysis_datetime": "2000-02-01T08:00:00.123456001+08:00"}
        )
    assert caught.value.errors()[0]["loc"] == ("analysis_datetime",)


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        (-315619199.75, "1960-01-01T00:00:00.250000+00:00"),
        (-315619199750.125, "1960-01-01T00:00:00.249875+00:00"),
        (20000000000.25, "1970-08-20T11:33:20.000250+00:00"),
        ("253000000000000.123", "9987-04-02T17:46:40.000123+00:00"),
    ],
)
def test_numeric_targets_preserve_signed_epoch_microseconds(
    timestamp, expected: str
) -> None:
    for model, options in (
        (AstroGermanyRequest, {}),
        (AstroGuolaoRequest, {}),
        (AstroChartPolyRequest, {"chart_variant": "germany"}),
        (AstroChartPolyRequest, {"chart_variant": "guolao_chart"}),
    ):
        payload = {**astro_payload(), **options, "analysis_datetime": timestamp}
        for request in (
            model.model_validate(payload),
            model.model_validate_json(json.dumps(payload)),
        ):
            assert request.analysis_datetime == datetime.fromisoformat(expected)


def test_target_option_is_rejected_for_other_variants() -> None:
    for variant in ("chart", "chart13", "india_chart", "hellen_chart"):
        with pytest.raises(ValidationError):
            AstroChartPolyRequest.model_validate(
                {
                    **astro_payload(),
                    "chart_variant": variant,
                    "analysis_datetime": "2026-01-01T00:00:00Z",
                }
            )


@HAS_SWE
def test_invalid_time_domain_and_zero_arc_are_not_replaced_by_defaults() -> None:
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    jd = ephemeris_time(birth).jd_tt
    for target in (
        birth - timedelta(seconds=1),
        birth + timedelta(days=151 * 365.25),
        datetime(2001, 1, 1),
    ):
        with pytest.raises(ValueError):
            solar_arc_state(birth, jd, target)
    assert solar_arc_state(birth, jd, birth)["solar_arc_degrees"] == 0


@HAS_SWE
def test_zero_arc_source_reading_does_not_create_a_second_evidence_identity() -> None:
    result = calculate_germany_chart_analysis(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime(2000, 1, 1, 4, 30, tzinfo=timezone.utc),
    )
    layer = result["midpoint_analysis"]
    solar = layer["solar_arc_analysis"]
    assert solar["profile"]["solar_arc_degrees"] == 0
    assert (
        solar["interpretations"][0]["claim_id"]
        == layer["interpretations"][0]["claim_id"]
    )
    assert solar["contact_counts"]["90"]["zero_arc_identities"] == 253


@HAS_SWE
def test_symbolic_elapsed_key_uses_utc_even_when_supplied_datetimes_share_a_dst_zone() -> (
    None
):
    zone = ZoneInfo("America/New_York")
    start = datetime(2000, 3, 1, 12, tzinfo=zone)
    end = datetime(2000, 5, 1, 12, tzinfo=zone)
    result = solar_arc_state(start, ephemeris_time(start).jd_tt, end)
    assert result["elapsed_calendar_days"] == pytest.approx(61 - 1 / 24)
    assert result["elapsed_calendar_days"] != (end - start).total_seconds() / 86400


@HAS_SWE
@pytest.mark.parametrize(
    "public_variant,second,target,progressed_tt,key_years",
    [
        pytest.param(
            True,
            30,
            "2017-01-02T00:00:30.023479Z",
            "0x1.2c04d406869acp+21",
            "0x1.671a6a0003da5p-9",
            id="generic-advance-next-double",
        ),
        pytest.param(
            False,
            31,
            "2017-01-02T00:00:30.038898Z",
            "0x1.2c04d4068ca7fp+21",
            "0x1.67195dfffda04p-9",
            id="specialty-advance-previous-double",
        ),
        pytest.param(
            True,
            30,
            "2016-12-31T23:59:30.409595Z",
            "0x1.2c04d400ea311p+21",
            "0x1.345e4c4eae4c4p-47",
            id="same-display-actual-after-birth",
        ),
        pytest.param(
            False,
            31,
            "2016-12-31T23:59:31.409589Z",
            None,
            None,
            id="same-display-actual-before-birth",
        ),
    ],
)
def test_local_mean_solar_arc_key_uses_exact_utc_coordinate(
    public_variant: bool,
    second: int,
    target: str,
    progressed_tt: str | None,
    key_years: str | None,
) -> None:
    # R96 used Swiss 2.10.03 Delta T, USNO atomic offsets and independent
    # rational calendar subtraction and nearest-even binary64 encoding.
    birth = dict(
        birth_year=2016,
        birth_month=12,
        birth_day=31,
        birth_hour=23,
        birth_minute=59,
        birth_second=second,
        birth_longitude=0.0,
        birth_latitude=0.0,
        birth_clock_basis="local_mean_solar",
        analysis_datetime=datetime.fromisoformat(target),
    )
    result = (
        calculate_core_chart_analysis(chart_variant="germany", **birth)
        if public_variant
        else calculate_germany_chart_analysis(**birth)
    )
    if progressed_tt is None:
        assert result["status_code"] == 400
        assert result["retryable"] is False
        assert result["error"] == (
            "Solar arc supports target instants 0..150 Julian key years after birth"
        )
        return
    else:
        pass
    midpoint = result["midpoint_analysis"]
    assert midpoint["time_sensitivity"]["status"] == "not_assessed"
    arc = midpoint["solar_arc_analysis"]
    profile = arc["profile"]
    progressed_index = profile["sun_observation_indices"][1]
    observation = profile["sun_ephemeris_source"]["observations"][progressed_index]
    assert profile["progressed_julian_day_tt"].hex() == progressed_tt
    assert observation["julian_day_tt"].hex() == progressed_tt
    assert profile["key_years"].hex() == key_years
    assert arc["daily_meridian"]["input_coherence"]["status"] == "verified"
