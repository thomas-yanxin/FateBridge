"""A valid nominal direction must retain unknown boundary samples explicitly."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import runtime, solar_arc
from fatebridge.core.astro.day_meridian import sampled_day_meridian_spans
from fatebridge.services.astrology import calculate_germany_chart_analysis

BIRTH = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
PAYLOAD = dict(
    name="虚构：太阳弧生时区间边界回归",
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=0.0,
    birth_latitude=0.0,
    birth_time_uncertainty_minutes=1,
)
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
@pytest.mark.parametrize(
    "key_years,missing_offsets", [(0, [30, 60]), (150, [-60, -30])]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_nominal_and_all_samples_survive_both_model_range_edges(
    key_years, missing_offsets, zodiacal
):
    target = BIRTH + timedelta(days=key_years * 365.25)
    result = calculate_germany_chart_analysis(
        **PAYLOAD, analysis_datetime=target, zodiacal=zodiacal
    )
    assert "error" not in result
    natal = result["midpoint_analysis"]
    direction = natal["solar_arc_analysis"]
    assert natal["status"] == direction["status"] == "computed"
    assert direction["profile"]["key_years"] == key_years
    assert natal["time_sensitivity"]["sample_count"] == 5
    sensitivity = direction["birth_time_sensitivity"]
    assert sensitivity["status"] == "partial"
    assert sensitivity["sample_count"] == 5
    assert sensitivity["computed_sample_count"] == 3
    assert sensitivity["unavailable_sample_count"] == 2
    assert [r["offset_seconds"] for r in sensitivity["samples"]] == [
        -60,
        -30,
        0,
        30,
        60,
    ]
    missing = [r for r in sensitivity["samples"] if r["status"] == "unavailable"]
    assert [r["offset_seconds"] for r in missing] == missing_offsets
    for row in missing:
        assert row["supported_key_years"] == [0.0, 150.0]
        assert row.get("source_condition_met") is None
        assert "source_direct_orb_degrees" not in row
        assert "solar_arc_degrees" not in row
        assert row["reason_code"] == (
            "target_before_birth_time_sample"
            if key_years == 0
            else "target_after_supported_key_range_for_sample"
        )
    calculated = [r for r in sensitivity["samples"] if r["status"] == "computed"]
    for row in calculated:
        independent_elapsed = (
            target - datetime.fromisoformat(row["effective_utc"])
        ).total_seconds() / (86400 * 365.25)
        assert 0 <= independent_elapsed <= 150
        assert row["source_condition_met"] in (True, False)
    pattern = sensitivity["source_pattern"]
    assert pattern["sampled_status"] == "underdetermined"
    assert pattern["present_sample_count"] + pattern["absent_sample_count"] == 3
    assert pattern["unavailable_sample_count"] == 2
    assert pattern["orb_range_scope"] == "computed_samples_only"
    assert pattern["minimum_sampled_direct_orb_degrees"] == min(
        r["source_direct_orb_degrees"] for r in calculated
    )
    assert pattern["maximum_sampled_direct_orb_degrees"] == max(
        r["source_direct_orb_degrees"] for r in calculated
    )
    day = direction["daily_meridian"]
    assert day["status"] == "computed"
    ds = day["birth_time_sensitivity"]
    assert ds["status"] == "partial" and ds["sample_count"] == 5
    assert ds["computed_sample_count"] == 3 and ds["unavailable_sample_count"] == 2
    assert [
        r["offset_seconds"] for r in ds["samples"] if r["status"] == "unavailable"
    ] == missing_offsets
    assert all(
        "upper_meridian_longitude" not in row
        for row in ds["samples"]
        if row["status"] == "unavailable"
    )
    assert (
        sensitivity["continuous_interval_proven"]
        is ds["continuous_interval_proven"]
        is False
    )
    assert (
        sensitivity["sample_frequency_is_probability"]
        is ds["sample_frequency_is_probability"]
        is False
    )


@HAS_SWE
def test_supported_interval_keeps_the_existing_complete_output_shape():
    result = calculate_germany_chart_analysis(
        **PAYLOAD, analysis_datetime=BIRTH + timedelta(days=50 * 365.25)
    )
    sensitivity = result["midpoint_analysis"]["solar_arc_analysis"][
        "birth_time_sensitivity"
    ]
    assert sensitivity["status"] == "sampled" and sensitivity["sample_count"] == 5
    assert "unavailable_sample_count" not in sensitivity
    assert all("status" not in row for row in sensitivity["samples"])
    assert sensitivity["source_pattern"]["sampled_status"] in {
        "present_at_every_sample",
        "absent_at_every_sample",
        "varies_across_samples",
    }


@HAS_SWE
def test_other_sample_calculation_failures_are_not_disguised_as_range_limits(
    monkeypatch,
):
    original = solar_arc.solar_arc_state

    def broken_sample(birth_utc, *args, **kwargs):
        if birth_utc < BIRTH:
            raise ValueError("synthetic unexpected Sun calculation failure")
        return original(birth_utc, *args, **kwargs)

    monkeypatch.setattr(solar_arc, "solar_arc_state", broken_sample)
    result = calculate_germany_chart_analysis(**PAYLOAD, analysis_datetime=BIRTH)
    assert "error" in result
    assert "synthetic unexpected Sun calculation failure" in result["error"]
    assert "midpoint_analysis" not in result


def test_day_meridian_spans_do_not_bridge_an_unavailable_gap():
    # Pure aggregation retains the gap regression. The actual chart builder now
    # rejects an unavailable nominal sample as incoherent with a valid nominal arc.
    spans = sampled_day_meridian_spans(
        {"upper_meridian_longitude": 0.0, "lower_meridian_longitude": 180.0},
        [
            {
                "offset_seconds": -60,
                "status": "computed",
                "upper_meridian_longitude": 359.0,
                "lower_meridian_longitude": 179.0,
            },
            {
                "offset_seconds": 0,
                "status": "unavailable",
                "reason_code": "fictional gap",
            },
            {
                "offset_seconds": 60,
                "status": "computed",
                "upper_meridian_longitude": 1.0,
                "lower_meridian_longitude": 181.0,
            },
        ],
    )
    for span in spans.values():
        assert span == {
            "minimum_offset_from_nominal_degrees": -1.0,
            "maximum_offset_from_nominal_degrees": 1.0,
            "maximum_adjacent_sample_jump_degrees": 0.0,
        }
