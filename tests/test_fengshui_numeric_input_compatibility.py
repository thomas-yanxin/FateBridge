"""Within-range observations must remain valid; strings cannot impersonate them."""

from datetime import date, datetime
from importlib import import_module
from typing import Annotated

import pytest
from pydantic import TypeAdapter, ValidationError

CLOCK = "2026-06-01T12:00:00+08:00"
BIRTH_CLOCK = "2000-01-01T12:00:00+08:00"
CASES = [
    ("city_gate_inputs", "CityGateRequest", "reference_period_number", 9),
    ("context_inputs", "FloorSpace", "level", 1),
    ("context_inputs", "HouseholdMember", "generation", 1),
    ("geomagnetic_inputs", "GeomagneticReference", "latitude", 22.5),
    ("geomagnetic_inputs", "GeomagneticReference", "longitude", 121.0),
    ("geomagnetic_inputs", "GeomagneticReference", "height_km_wgs84", 0.0),
    ("geomagnetic_inputs", "GeomagneticReference", "model_date", "2026-06-01"),
    ("geomagnetic_inputs", "GeomagneticReference", "decimal_year", 2026.5),
    ("layout_inputs", "FormObservation", "backing_distance_m", 1.0),
    ("models", "AnnualRequest", "effective_year", 2026),
    ("models", "AnnualRequest", "query_at", CLOCK),
    ("models", "AssessRequest", "effective_year", 2026),
    ("models", "AssessRequest", "query_at", CLOCK),
    ("models", "DirectionsRequest", "bearing_degrees", 22.5),
    ("models", "House", "facing_degrees", 22.5),
    ("models", "House", "bearing_uncertainty_degrees", 1.0),
    ("models", "HousePeriod", "period_number", 8),
    ("models", "HousePeriod", "effective_event_year", 2026),
    ("models", "HousePeriod", "event_at", CLOCK),
    ("models", "MingguaRequest", "birth_date", "2000-01-01"),
    ("models", "MingguaRequest", "effective_birth_year", 2000),
    ("models", "MingguaRequest", "birth_at", BIRTH_CLOCK),
    ("models", "MonthlyRequest", "query_at", CLOCK),
    ("models", "MonthlyRequest", "effective_solar_year", 2026),
    ("models", "MonthlyRequest", "solar_month_number", 8),
    ("models", "Occupant", "birth_date", "2000-01-01"),
    ("models", "Occupant", "effective_birth_year", 2000),
    ("models", "Occupant", "birth_at", BIRTH_CLOCK),
    ("models", "XuankongInterpretationRequest", "current_period_number", 9),
    ("workstation_inputs", "EvaluationPeriod", "number", 9),
]


def _adapter(module, model, field):
    cls = getattr(import_module("fatebridge.core.fengshui." + module), model)
    info = cls.model_fields[field]
    return TypeAdapter(Annotated[info.annotation, *info.metadata])


@pytest.mark.parametrize("module,model,field,value", CASES)
def test_every_declared_numeric_or_calendar_field_accepts_within_range_fact(
    module, model, field, value
):
    expected = value
    if isinstance(value, str):
        expected = (
            datetime.fromisoformat(value) if "T" in value else date.fromisoformat(value)
        )
    assert _adapter(module, model, field).validate_python(value) == expected


@pytest.mark.parametrize(
    "module,model,field,value",
    [case for case in CASES if isinstance(case[3], (int, float))],
)
def test_numeric_strings_are_rejected_even_when_number_is_within_range(
    module, model, field, value
):
    adapter = _adapter(module, model, field)
    assert adapter.validate_python(value) == value
    with pytest.raises(ValidationError):
        adapter.validate_python(str(value))
