"""Unknown clocks expose calendar evidence without running a physical chart."""

import pytest
from pydantic import ValidationError

from fatebridge.core.local_techniques import suzhan
from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.services.divination import calculate_suzhan_analysis


@pytest.mark.parametrize("provided", [{}, {"time": None}])
def test_omitted_and_null_clock_do_not_call_any_astronomy_or_house_builder(
    monkeypatch, provided
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unknown clock reached physical sky or chart")

    for name in [
        "_build_local_chart_response",
        "_build_birth_info",
        "build_equatorial_mansions",
        "apply_equatorial_mansions",
    ]:
        monkeypatch.setattr(suzhan, name, forbidden)
    request = SuZhanRequest(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        natal_mansion="室",
        activity="travel",
        **provided,
    )
    result = suzhan.build_suzhan_result(**request.model_dump())
    assert result["input_normalized"]["time"] is None
    assert result["chart"] is None and result["astronomy"] is None
    assert result["params"]["birthTimeImputed"] is False
    assert result["params"]["coordinatesApplied"] is False
    assert result["validation"]["calculation_layers"] == {
        "calendar": "partial",
        "chart": "not_computed_birth_time_unknown",
        "astronomy": "not_computed_birth_time_unknown",
    }
    day = result["sukuyo"]
    assert day["calendar"]["birth_time_known"] is False
    assert day["day_mansion"] is None and day["personal_day"] is None
    assert [
        (r["day_mansion"], r["personal_day"]["relation"]["relation"])
        for r in day["candidate_mansion_days"]
    ] == [("星", "安"), ("张", "危")]
    assert "未知" in result["snapshot_text"]
    assert "已生成星图" not in result["summary"]
    assert "宫制：equal" not in result["snapshot_text"]


@pytest.mark.parametrize("clock", ["", " ", "\t"])
def test_blank_clock_is_invalid_rather_than_imputed_or_accepted_as_unknown(clock):
    with pytest.raises(ValueError, match="空字符串"):
        suzhan.build_suzhan_result(date="2024-08-04", time=clock)


@pytest.mark.parametrize("clock", ["not-time", "25:00:00", "12:00:60"])
def test_invalid_known_clock_is_not_downgraded_to_date_only(clock):
    result = calculate_suzhan_analysis(date="2024-08-04", time=clock, zone="+08:00")
    assert "error" in result


def test_request_schema_exposes_optional_clock_without_using_example_as_default():
    schema = SuZhanRequest.model_json_schema()
    assert "time" not in schema["required"]
    assert SuZhanRequest(date="2024-08-04").time is None
    assert SuZhanRequest(date="2024-08-04", time=None).time is None
    with pytest.raises(ValidationError):
        SuZhanRequest(date="2024-08-04", time=93000)


@pytest.mark.parametrize(
    "basis,date,zone",
    [
        ("chinese_hko_utc08", "2024-08-04", "Asia/Tokyo"),
        ("japanese_hutime_1002_1_utc09", "2017-06-24", "+08:00"),
        ("japanese_naoj_historical_utc09", "0806-09-20", "+08:00"),
        ("japanese_hutime_1002_1_utc09", "2031-01-22", "UTC"),
        ("japanese_naoj_historical_utc09", "0001-01-01", "+15:00"),
    ],
)
def test_public_date_only_retains_every_existing_calendar_and_day_branch(
    basis, date, zone
):
    expected_calendar = calendar_mansion(
        date, zone=zone, calendar_basis=basis, calendar_profile="hinoo_t1299_host27"
    )
    expected_day = day_evidence(
        expected_calendar, "室", "travel", ["personal_departure"]
    )
    result = calculate_suzhan_analysis(
        date=date,
        zone=zone,
        calendar_basis=basis,
        calendar_profile="hinoo_t1299_host27",
        natal_mansion="室",
        activity="travel",
        activity_details=["personal_departure"],
    )
    assert result["sukuyo"] == expected_day
    assert result["chart"] is None and result["astronomy"] is None
    if expected_calendar["out_of_range_calendar_dates"]:
        assert result["sukuyo"]["day_mansion"] is None
        assert not expected_calendar["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ]


def test_explicit_textual_half_does_not_establish_a_clock_or_physical_sky():
    result = calculate_suzhan_analysis(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert result["sukuyo"]["day_mansion"] == "星"
    assert result["sukuyo"]["calendar"]["birth_time_known"] is False
    assert result["chart"] is None and result["astronomy"] is None


def test_date_only_does_not_infer_a_natal_mansion_or_a_place():
    result = calculate_suzhan_analysis(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        activity="study",
        gps_lat=0,
        gps_lon=0,
    )
    assert result["sukuyo"]["personal_day"] is None
    assert all(
        r["personal_day"] is None for r in result["sukuyo"]["candidate_mansion_days"]
    )
    assert result["params"]["coordinatesApplied"] is False
    assert "birthLongitude" not in result["params"]
