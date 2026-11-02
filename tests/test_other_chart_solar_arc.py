"""Independent Sun references, source rounding intervals and mixed-layer algebra."""

import hashlib
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
)
from fatebridge.services.astrology import calculate_germany_chart_analysis
from tests.fixtures.surface_payloads import astro_payload

ROOT = Path(__file__).parent / "fixtures"
REFERENCE = json.loads((ROOT / "uranian-solar-arc-horizons.json").read_text())
STATIC = json.loads((ROOT / "uranian-al319-static.json").read_text())
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["birth_utc"])
def test_actual_sun_and_true_arc_against_independent_horizons(case):
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


def test_publisher_static_twenty_two_pairs_have_compatible_rounding_intervals():
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
def test_all_biwheel_contacts_match_independent_trigonometric_equations(period):
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
            if residual(2 * natal[point] - shifted[a] - shifted[b]) <= 1:
                expected_three.add((point, "natal", a, b, "solar_arc"))
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


def test_biwheel_inclusive_orb_and_zero_arc_identities_remain_explicit():
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
def test_source_directed_mc_reading_keeps_layer_identity_and_uncertainty_evidence():
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
    assert directed["real_world_efficacy"] == "not_tested"


@HAS_SWE
def test_solar_arc_uses_tropical_sun_even_in_a_natal_lahiri_display():
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
def test_public_target_instant_requires_an_explicit_offset(instant):
    with pytest.raises(ValidationError):
        AstroGermanyRequest.model_validate(
            {**astro_payload(), "analysis_datetime": instant}
        )


def test_target_option_is_rejected_for_other_variants():
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
def test_invalid_time_domain_and_zero_arc_are_not_replaced_by_defaults():
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


def test_cached_independent_response_has_explicit_reverifiable_hash_meaning():
    assert (
        hashlib.sha256(REFERENCE["response"]["result"].encode()).hexdigest()
        == REFERENCE["response_sha256"]
    )
    if "source_fixture" in REFERENCE:
        source = Path(REFERENCE["source_fixture"])
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == REFERENCE["source_fixture_sha256"]
        )
        assert REFERENCE["original_http_json_bytes_preserved"] is False
        assert (
            REFERENCE["retrieved_at"] == json.loads(source.read_text())["retrieved_at"]
        )
    else:
        raw = REFERENCE["http_json_text"].encode("utf-8")
        assert (
            hashlib.sha256(raw).hexdigest()
            == REFERENCE["original_http_json_bytes_sha256"]
        )
        assert json.loads(raw) == REFERENCE["response"]
        assert REFERENCE["original_http_json_bytes_preserved"] is True


@HAS_SWE
def test_zero_arc_source_reading_does_not_create_a_second_evidence_identity():
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
def test_symbolic_elapsed_key_uses_utc_even_when_supplied_datetimes_share_a_dst_zone():
    zone = ZoneInfo("America/New_York")
    start = datetime(2000, 3, 1, 12, tzinfo=zone)
    end = datetime(2000, 5, 1, 12, tzinfo=zone)
    result = solar_arc_state(start, ephemeris_time(start).jd_tt, end)
    assert result["elapsed_calendar_days"] == pytest.approx(61 - 1 / 24)
    assert result["elapsed_calendar_days"] != (end - start).total_seconds() / 86400
