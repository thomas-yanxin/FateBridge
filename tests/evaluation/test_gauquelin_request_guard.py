"""A known36-sector request cannot silently produce a twelve-house chart."""

import pytest
from pydantic import ValidationError

from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.house_systems import (
    UnsupportedGauquelinError,
    house_system_fields,
    normalize_house_system,
)
from tests.fixtures.surface_payloads import MCP_CASES, REST_POST_CASES

HOUSE_SPECS = [s for s in CATALOG if "house_system" in s.request_model.model_fields]
GAUQUELIN_NAMES = [
    "G",
    "g",
    " G ",
    "Gauquelin",
    "gauquelin_sectors",
    "Gauquelin-sector",
    "Gauquelin sectors",
    "GAUQUELIN",
    "Ｇ",
    "Gauquelin分区",
    "高奎林",
    "高奎林分区",
    "高奎林宫制",
    "\tGauquelin\nsectors\t",
]


def payload(spec):
    factory = REST_POST_CASES.get(spec.rest_path) or MCP_CASES[spec.tool_name][1]
    return factory()


@pytest.mark.parametrize("value", GAUQUELIN_NAMES)
def test_known_sector_names_are_rejected_by_both_shared_house_helpers(value):
    with pytest.raises(UnsupportedGauquelinError, match="36 clockwise sectors"):
        normalize_house_system(value)
    with pytest.raises(UnsupportedGauquelinError):
        house_system_fields(value, default="R")


@pytest.mark.parametrize("value", GAUQUELIN_NAMES)
def test_all_live_house_system_request_models_reject_the_known_sector_name(value):
    assert HOUSE_SPECS
    for spec in HOUSE_SPECS:
        with pytest.raises(ValidationError) as caught:
            spec.request_model.model_validate({**payload(spec), "house_system": value})
        issue = caught.value.errors(include_input=False)[0]
        assert issue["loc"] == ("house_system",), spec.key
        assert issue["type"] == "unsupported_house_system", spec.key
        assert issue["ctx"] == {"system": "Gauquelin", "sector_count": 36}


def test_gauquelin_cannot_be_supplied_as_a_default_house_system():
    for value in (None, "", "P"):
        with pytest.raises(UnsupportedGauquelinError):
            normalize_house_system(value, default="G")


def test_every_live_house_field_describes_the_36_sector_exclusion():
    for spec in HOUSE_SPECS:
        schema = spec.request_model.model_json_schema()
        description = schema["properties"]["house_system"]["description"]
        assert "Gauquelin" in description and "36" in description, spec.key


@pytest.mark.parametrize(
    "value",
    [
        "P",
        "R",
        "W",
        "D",
        "X",
        "I",
        "i",
        "placidus",
        "equal_mc",
        "whole_sign",
        *range(9),
    ],
)
def test_supported_inputs_are_kept_in_every_request_model(value):
    for spec in HOUSE_SPECS:
        model = spec.request_model.model_validate(
            {**payload(spec), "house_system": value}
        )
        assert model.house_system == value, spec.key


def test_unknown_extra_house_field_is_still_an_extra_field_on_other_models():
    from fatebridge.core.requests.base import _DeferredModel

    class Unrelated(_DeferredModel):
        name: str

    with pytest.raises(ValidationError) as caught:
        Unrelated.model_validate({"name": "fictional", "house_system": "G"})
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_integer_hsys_family_already_rejects_g_without_fallback():
    from fatebridge.core.requests.astrology import AstroChartRequest

    with pytest.raises(ValidationError) as caught:
        AstroChartRequest.model_validate(
            {
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 0,
                "birth_timezone": "UTC",
                "birth_longitude": 0,
                "birth_latitude": 0,
                "hsys": "G",
            }
        )
    assert caught.value.errors()[0]["loc"] == ("hsys",)
