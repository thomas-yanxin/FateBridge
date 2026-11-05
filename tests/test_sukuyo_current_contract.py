"""The date-based compatibility contract has no ignored coordinate inputs."""

import inspect

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.compatibility import SukuyoCompatibilityRequest
from fatebridge.services.divination import calculate_sukuyo_compatibility
from fatebridge.services.tool_catalog import CATALOG

REMOVED_COORDINATES = tuple(
    f"person{person}_{name}"
    for person in (1, 2)
    for name in ("lat", "lon", "gps_lat", "gps_lon")
)


def test_current_request_service_and_catalog_publish_only_effective_inputs():
    service = inspect.signature(calculate_sukuyo_compatibility).parameters
    spec = next(s for s in CATALOG if s.key == "sukuyo_compatibility")
    schema = spec.request_model.model_json_schema()
    assert set(REMOVED_COORDINATES).isdisjoint(service)
    assert set(REMOVED_COORDINATES).isdisjoint(schema["properties"])
    assert {"calendar_profile", "calendar_basis", "leap_month_policy"} <= schema[
        "properties"
    ].keys()


@pytest.mark.parametrize("field", REMOVED_COORDINATES)
def test_ignored_coordinates_cannot_silently_enter_the_current_request(field):
    with pytest.raises(ValidationError):
        SukuyoCompatibilityRequest.model_validate(
            {"person1_date": "1990-06-15", "person2_date": "1991-07-16", field: 0}
        )
