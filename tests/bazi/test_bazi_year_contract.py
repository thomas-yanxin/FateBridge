"""Published year limits must match the already-existing service limits."""

import asyncio

import pytest
from pydantic import ValidationError

from fatebridge.utils.birth_input import PersonInfo
from tests.evaluation.test_agentic_nested_outputs import SPECS, call_cli, native
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

TOPICS = [
    "birth",
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
]


rest = _shared_rest


@pytest.mark.parametrize("topic", TOPICS)
def test_all_ten_year_schemas_match_internal_person_limits(topic):
    spec = SPECS["bazi_" + topic]
    internal = PersonInfo.model_json_schema()["properties"]["birth_year"]
    public = spec.request_model.model_json_schema()["properties"]["birth_year"]
    assert (public["minimum"], public["maximum"]) == (1900, 2100)
    assert (public["minimum"], public["maximum"]) == (
        internal["minimum"],
        internal["maximum"],
    )
    for year, month, day in [(1900, 1, 1), (2100, 12, 31)]:
        # Retain the existing full boundary years, not only their safer dates.
        obj = spec.request_model.model_validate(
            {
                "birth_year": year,
                "birth_month": month,
                "birth_day": day,
                "birth_hour": 12,
            }
        )
        assert obj.birth_year == year


@pytest.mark.parametrize("year,month,day", [(1900, 1, 1), (2100, 12, 31)])
def test_boundary_years_retain_bazi_and_explicit_lunar_sources(year, month, day, rest):
    args = {
        "birth_year": year,
        "birth_month": month,
        "birth_day": day,
        "birth_hour": 12,
        "gender": "男",
        "use_true_solar_time": False,
        "analysis_year": year,
        "analysis_month": month,
        "analysis_day": day,
    }
    response = rest.post(SPECS["bazi_birth"].rest_path, json=args)
    assert response.status_code == 200
    bazi = response.json()["bazi_birth"]
    assert bazi["four_pillars"]
    calendar = bazi["calendar_context"]
    assert calendar["solar_datetime"] == f"{year:04d}-{month:02d}-{day:02d} 12:00:00"
    if year == 1900:
        assert calendar["lunar_calendar_support"]["supported"] is True
        assert calendar["lunar_calendar"]["year"] == 1899
        assert calendar["lunar_calendar"]["month"] == 12
        assert calendar["lunar_calendar"]["day"] == 1
        assert (
            calendar["lunar_calendar"]["conversion_source"]["method_id"]
            == "pmo_1900_january_prefix_v1"
        )
    else:
        assert calendar["lunar_calendar_support"]["supported"] is True
        assert calendar["lunar_calendar"]["year"] == 2100
        assert calendar["lunar_calendar"]["month"] == 12
        assert calendar["lunar_calendar"]["day"] == 1
        assert (
            calendar["lunar_calendar"]["conversion_source"]["method_id"]
            == "hko_2100_month_starts_v1"
        )
    # Finite source tables at both ends preserve the full birth-year contract.
    assert calendar["lunar_calendar_support"]["supported_range"] == {
        "start": "1900-01-01",
        "end": "2100-12-31",
    }


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("year", [1899, 2101])
def test_invalid_year_is_rejected_before_computation_on_three_surfaces(
    topic, year, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    args = {
        "birth_year": year,
        "birth_month": 6,
        "birth_day": 1,
        "birth_hour": 12,
        "gender": "男",
        "use_true_solar_time": False,
    }
    with pytest.raises(ValidationError) as error:
        spec.request_model.model_validate(args)
    assert error.value.errors()[0]["loc"] == ("birth_year",)
    response = rest.post(spec.rest_path, json=args)
    assert response.status_code == 422
    envelope = response.json()
    assert envelope["error_code"] == "validation_error"
    assert envelope["retryable"] is False
    assert envelope["issues"] == [
        {
            "path": "birth_year",
            "code": "greater_than_equal" if year < 1900 else "less_than_equal",
            "constraints": {"ge": 1900} if year < 1900 else {"le": 2100},
        }
    ]
    protocol = asyncio.run(native(spec, args))
    assert protocol.is_error
    assert "birth_year" in str(protocol.content)
    code, result = call_cli(spec, args, tmp_path, capsys)
    assert code != 0
    assert result["issues"] == envelope["issues"]
