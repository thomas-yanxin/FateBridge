"""Public numeric/calendar types must agree before transport coercion."""

from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from importlib import import_module
from typing import Annotated

import pytest
from pydantic import TypeAdapter, ValidationError

# Literal inventory captured from all 45 Feng Shui input models. Each pair
# tests published input types, not the result of the implementation classifier.
FIELDS = [
    ("city_gate_inputs", "CityGateRequest", "reference_period_number"),
    ("context_inputs", "FloorSpace", "level"),
    ("context_inputs", "HouseholdMember", "generation"),
    ("geomagnetic_inputs", "GeomagneticReference", "latitude"),
    ("geomagnetic_inputs", "GeomagneticReference", "longitude"),
    ("geomagnetic_inputs", "GeomagneticReference", "height_km_wgs84"),
    ("geomagnetic_inputs", "GeomagneticReference", "model_date"),
    ("geomagnetic_inputs", "GeomagneticReference", "decimal_year"),
    ("layout_inputs", "FormObservation", "backing_distance_m"),
    ("models", "AnnualRequest", "effective_year"),
    ("models", "AnnualRequest", "query_at"),
    ("models", "AssessRequest", "effective_year"),
    ("models", "AssessRequest", "query_at"),
    ("models", "DirectionsRequest", "bearing_degrees"),
    ("models", "House", "facing_degrees"),
    ("models", "House", "bearing_uncertainty_degrees"),
    ("models", "HousePeriod", "period_number"),
    ("models", "HousePeriod", "effective_event_year"),
    ("models", "HousePeriod", "event_at"),
    ("models", "MingguaRequest", "birth_date"),
    ("models", "MingguaRequest", "effective_birth_year"),
    ("models", "MingguaRequest", "birth_at"),
    ("models", "MonthlyRequest", "query_at"),
    ("models", "MonthlyRequest", "effective_solar_year"),
    ("models", "MonthlyRequest", "solar_month_number"),
    ("models", "Occupant", "birth_date"),
    ("models", "Occupant", "effective_birth_year"),
    ("models", "Occupant", "birth_at"),
    ("models", "XuankongInterpretationRequest", "current_period_number"),
    ("workstation_inputs", "EvaluationPeriod", "number"),
]


def _adapter(module, model, field):
    cls = getattr(import_module("fatebridge.core.fengshui." + module), model)
    info = cls.model_fields[field]
    return TypeAdapter(Annotated[info.annotation, *info.metadata])


@pytest.mark.parametrize("module,model,field", FIELDS)
@pytest.mark.parametrize(
    "invalid", [True, False, "2026", float("nan"), float("inf"), float("-inf")]
)
def test_all_declared_facts_reject_coercible_nonfacts(module, model, field, invalid):
    with pytest.raises(ValidationError):
        _adapter(module, model, field).validate_python(invalid)


@pytest.mark.parametrize("number", [8, 8.0, Decimal("8.0"), Fraction(16, 2)])
def test_integral_json_numbers_keep_integer_semantics(number):
    assert (
        _adapter("models", "HousePeriod", "period_number").validate_python(number) == 8
    )
    assert (
        _adapter("models", "MonthlyRequest", "solar_month_number").validate_python(
            number
        )
        == 8
    )


@pytest.mark.parametrize(
    "number",
    [
        8.5,
        Decimal("8.000000000000000000000000000000001"),
        Fraction(8000000000000001, 1000000000000000),
    ],
)
def test_fractional_facts_are_never_rounded(number):
    with pytest.raises(ValidationError):
        _adapter("models", "HousePeriod", "period_number").validate_python(number)


@pytest.mark.parametrize("number", [22, 22.5, Decimal("22.5"), Fraction(45, 2)])
def test_valid_numeric_observations_remain_numbers(number):
    assert _adapter("models", "House", "facing_degrees").validate_python(
        number
    ) == float(number)


@pytest.mark.parametrize("value", [date(2000, 1, 1), "2000-01-01"])
def test_explicit_calendar_dates_are_preserved(value):
    assert _adapter("models", "MingguaRequest", "birth_date").validate_python(
        value
    ) == date(2000, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-01T12:00:00+08:00",
        "2026-06-01T04:00:00Z",
        datetime.fromisoformat("2026-06-01T12:00:00+08:00"),
    ],
)
def test_explicit_clocks_identify_same_instant(value):
    actual = _adapter("models", "AnnualRequest", "query_at").validate_python(value)
    assert actual == datetime.fromisoformat("2026-06-01T04:00:00+00:00")


@pytest.mark.parametrize(
    "model,field,value",
    [
        ("MingguaRequest", "birth_date", 946684800),
        ("MingguaRequest", "birth_date", datetime(2000, 1, 1)),
        ("MingguaRequest", "birth_date", "2000-01-01T00:00:00Z"),
        ("MingguaRequest", "birth_date", "2026-02-30"),
        ("AnnualRequest", "query_at", 2026),
        ("AnnualRequest", "query_at", "2026"),
        ("AnnualRequest", "query_at", "2026-06-01"),
        ("AnnualRequest", "query_at", date(2026, 6, 1)),
        ("AnnualRequest", "query_at", "2026-02-30T12:00:00Z"),
        ("AnnualRequest", "query_at", "2026-06-01T25:00:00Z"),
    ],
)
def test_calendar_input_never_invents_missing_date_or_clock(model, field, value):
    with pytest.raises(ValidationError):
        _adapter("models", model, field).validate_python(value)


def test_mcp_flattened_parameters_retain_same_field_preconditions():
    from fatebridge.core.fengshui.models import AnnualRequest
    from fatebridge.transports.mcp import model_parameters

    _, annotations = model_parameters(AnnualRequest)
    adapter = TypeAdapter(annotations["query_at"])
    for invalid in [2026, "2026", True, "2026-06-01"]:
        with pytest.raises(ValidationError):
            adapter.validate_python(invalid)
    assert adapter.validate_python("2026-06-01T12:00:00+08:00").year == 2026
