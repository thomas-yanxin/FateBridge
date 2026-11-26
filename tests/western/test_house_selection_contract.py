"""Source-named house selection must survive spelling and never guess a system."""

import pytest
from pydantic import ValidationError

from fatebridge.core.astro.profiles import _coerce_house_system_code
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.house_systems import (
    InvalidHouseCodeError,
    InvalidHouseSystemError,
    house_system_fields,
    normalize_house_system,
    parse_house_code,
)
from tests.unit_test.fixtures.house_system import HOUSE_CODE_SPECS as CODE_SPECS
from tests.unit_test.fixtures.house_system import HOUSE_SYSTEM_SPECS as HOUSE_SPECS
from tests.unit_test.fixtures.house_system import house_system_payload as inputs


@pytest.mark.parametrize(
    "name,code",
    [
        ("Alcabitus", "B"),
        ("alcabitius", "B"),
        ("ALCHABITIUS", "B"),
        ("Whole Signs", "W"),
        ("WHOLE_SIGNS", "W"),
        ("whole-sign", "W"),
        ("Axial Rotation", "X"),
        ("axial_rotation", "X"),
        ("meridian", "X"),
        ("Equal Sign", "A"),
        ("E", "A"),
        ("e", "A"),
        ("equal-house", "A"),
        ("Equal MC", "D"),
        ("equal_mc", "D"),
        ("Sripati", "S"),
        ("Regiomontanus", "R"),
        ("Campanus", "C"),
        ("Porphyrius", "O"),
        ("Pullen SD", "L"),
        ("pullen_sr", "Q"),
        ("Carter poli-equatorial", "F"),
        ("Sunshine", "I"),
        ("Sunshine/alt.", "i"),
        ("I", "I"),
        ("i", "i"),
        ("equal_aries", "N"),
        ("整宫制", "W"),
        ("天顶为第10宫宫头的等宫制", "D"),
        ("\tWhole\n Signs ", "W"),
        ("Ｒ", "R"),
        ("Ｐ", "P"),
    ],
)
def test_declared_names_resolve_to_the_source_definition(name: str, code: str) -> None:
    assert normalize_house_system(name) == code


@pytest.mark.parametrize(
    "value",
    [
        "unknown-name",
        "Placiduss",
        "",
        "  ",
        "9",
        "-1",
        "++3",
        "3.7",
        "8.0",
        99,
        -1,
        True,
        False,
        3.7,
        8.0,
        float("nan"),
        float("inf"),
        [],
        {},
    ],
)
def test_explicit_invalid_selection_never_substitutes_another_chart(value) -> None:
    with pytest.raises(InvalidHouseSystemError):
        normalize_house_system(value)


@pytest.mark.parametrize("value", [True, False, 8.0, 3.7, 99, -1, "unknown", "", "  "])
def test_both_request_families_reject_invalid_values_before_dispatch(value) -> None:
    for field, specs, expected in (
        ("house_system", HOUSE_SPECS, "invalid_house_system"),
        ("hsys", CODE_SPECS, "invalid_house_code"),
    ):
        assert specs
        for spec in specs:
            with pytest.raises(ValidationError) as caught:
                spec.request_model.model_validate({**inputs(spec), field: value})
            issue = caught.value.errors(include_input=False)[0]
            assert issue["loc"] == (field,), spec.name
            assert issue["type"] == expected, (spec.name, issue)


def test_defaults_require_a_missing_override_and_validate_configuration() -> None:
    assert normalize_house_system(None) == "P"
    assert normalize_house_system(None, default="Regiomontanus") == "R"
    assert normalize_house_system(0, default="R") == "W"
    for value in (None, "P"):
        with pytest.raises(InvalidHouseSystemError):
            normalize_house_system(value, default="unknown")
    for spec in HOUSE_SPECS:
        with pytest.raises(ValidationError):
            spec.request_model.model_validate({**inputs(spec), "house_system": None})


@pytest.mark.parametrize(
    "code,letter", list(enumerate(["W", "B", "R", "P", "K", "V", "T", "S", "D"]))
)
def test_numeric_codes_have_one_unambiguous_meaning(code, letter) -> None:
    assert parse_house_code(code) == parse_house_code(str(code)) == code
    assert normalize_house_system(code) == letter
    assert _coerce_house_system_code(code) == code


def test_internal_numeric_coercion_does_not_truncate_or_accept_booleans() -> None:
    for value in (True, False, 3.7, 8.0, 99, "unknown"):
        assert _coerce_house_system_code(value) is None
        with pytest.raises(InvalidHouseCodeError):
            parse_house_code(value)
    assert _coerce_house_system_code(None) is None
    assert _coerce_house_system_code("Whole Signs") == 0
    assert _coerce_house_system_code("Alcabitus") == 1
    assert _coerce_house_system_code("Axial Rotation") is None  # not in the0..8 family


def test_previously_unlabelled_codes_have_named_metadata_and_distinct_sunshine_modes() -> (
    None
):
    for code, key in {
        "F": "carter_poli_equatorial",
        "I": "sunshine",
        "i": "sunshine_alternative",
        "L": "pullen_sd",
        "N": "equal_aries",
        "Q": "pullen_sr",
    }.items():
        info = house_system_fields(code)
        assert info["house_system"] == code
        assert normalize_house_system(key) == code
        assert info["house_system_label_zh"] != code


def test_every_representative_request_and_optional_missing_hsys_remains_valid() -> None:
    for spec in CATALOG:
        spec.request_model.model_validate(inputs(spec))
    from fatebridge.core.requests.astrology import AstroChartRequest

    spec = next(s for s in CATALOG if s.name == "astrology_chart")
    assert AstroChartRequest.model_validate({**inputs(spec), "hsys": None}).hsys is None


def test_numeric_request_schema_advertises_the_actual_range() -> None:
    for spec in CODE_SPECS:
        field = spec.request_model.model_json_schema()["properties"]["hsys"]
        shape = next(
            (v for v in field.get("anyOf", []) if v.get("type") == "integer"), field
        )
        assert shape["minimum"] == 0 and shape["maximum"] == 8, spec.name


def test_existing_strict_integer_domain_does_not_gain_string_coercion() -> None:
    spec = next(s for s in CODE_SPECS if s.name == "interpret_astrology_dice")
    with pytest.raises(ValidationError) as caught:
        spec.request_model.model_validate({**inputs(spec), "hsys": "3"})
    assert caught.value.errors()[0]["type"] == "int_type"
