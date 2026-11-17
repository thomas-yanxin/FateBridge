"""Actual variant facts must survive discovery and complete output validation."""

import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.description import describe_spec
from fatebridge.application.execution import (
    OutputContractError,
    execute_tool,
    validate_output,
)
from fatebridge.application.projection import project_fields
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.requests.astrology import AstroChartPolyRequest
from fatebridge.services.astrology import SUPPORTED_CHART_VARIANTS
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.support.current_outputs import current_business
from tests.support.ephemeris_context import empty_ephemeris_path

SPECS = {spec.key: spec for spec in CATALOG}
VARIANTS = {
    "chart": "astro_chart",
    "chart13": "astro_chart13",
    "hellen_chart": "astro_hellen",
    "guolao_chart": "astro_guolao",
    "india_chart": "astro_india",
    "germany": "astro_germany",
}
AGGREGATE = SPECS["astro_chart"]


def aggregate_request(variant):
    owner = SPECS[VARIANTS[variant]]
    return AstroChartPolyRequest.model_validate(
        {**REST_POST_CASES[owner.rest_path](), "chart_variant": variant}
    )


def test_published_union_reuses_every_dedicated_owner_and_explains_full_roots():
    assert set(VARIANTS) == SUPPORTED_CHART_VARIANTS | {"germany"}
    description = describe_spec(AGGREGATE)
    schema = AGGREGATE.output_model.model_json_schema()
    for variant, key in VARIANTS.items():
        owner = SPECS[key]
        assert set(owner.output_model.model_fields) <= set(
            AGGREGATE.output_model.model_fields
        )
        assert description["full_result_required_fields_by_variant"][variant] == list(
            owner.required_output_fields
        )
        for field in owner.required_output_fields:
            assert (
                variant
                in schema["properties"][field][
                    "x-fatebridge-full-result-required-for-chart-variants"
                ]
            )
    for field, key in (("guolao", "astro_guolao"), ("hellenistic", "astro_hellen")):
        assert (
            AGGREGATE.output_model.model_fields[field].annotation
            == SPECS[key].output_model.model_fields[field].annotation
        )


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("operation", ["remove", "null", "empty_object"])
def test_actual_selected_roots_cannot_disappear_from_complete_output(
    current_business, variant, operation
):
    owner = SPECS[VARIANTS[variant]]
    request = aggregate_request(variant)
    for root in owner.required_output_fields:
        value = deepcopy(current_business(owner.key))
        if operation == "remove":
            del value[root]
        else:
            value[root] = None if operation == "null" else {}
        with pytest.raises(OutputContractError):
            validate_output(AGGREGATE, value, request=request)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("foreign_result", [False, True])
def test_both_entry_points_reject_the_wrong_actual_algorithm(
    current_business, variant, foreign_result
):
    owner = SPECS[VARIANTS[variant]]
    if foreign_result:
        other = "astro_guolao" if variant == "chart" else "astro_chart"
        value = deepcopy(current_business(other))
    else:
        value = deepcopy(current_business(owner.key))
        value["chart_profile"]["chart_type"] = (
            "chart13" if variant == "chart" else "chart"
        )
    request = aggregate_request(variant)
    for spec in (AGGREGATE, owner):
        with pytest.raises(OutputContractError):
            validate_output(spec, value, request=request)


@pytest.mark.parametrize("variant", ["guolao_chart", "hellen_chart"])
def test_existing_domain_numeric_types_are_enforced_on_the_aggregate(
    current_business, variant
):
    owner = SPECS[VARIANTS[variant]]
    value = deepcopy(current_business(owner.key))
    if variant == "guolao_chart":
        point = value["guolao"]["bodies"][0]
    else:
        point = value["hellenistic"]["lot_of_fortune"]
    point["longitude"] = "not-a-number"
    for spec in (AGGREGATE, owner):
        assert not Draft202012Validator(spec.output_model.model_json_schema()).is_valid(
            value
        )
        with pytest.raises(OutputContractError):
            validate_output(spec, value, request=aggregate_request(variant))


@pytest.mark.parametrize("variant", VARIANTS)
def test_actual_values_extensions_and_projected_siblings_remain_unchanged(
    current_business, variant
):
    owner = SPECS[VARIANTS[variant]]
    value = deepcopy(current_business(owner.key))
    value["future_extension"] = {"note": "neutral extension control"}
    before = json.dumps(value, sort_keys=True, allow_nan=False)
    validate_output(AGGREGATE, value, request=aggregate_request(variant))
    assert json.dumps(value, sort_keys=True, allow_nan=False) == before
    for field in ("chart_profile.chart_type", *owner.required_output_fields):
        projected = project_fields(value, [field], strict_fields=True)
        AGGREGATE.output_model.model_validate(projected)
        Draft202012Validator(AGGREGATE.output_model.model_json_schema()).validate(
            projected
        )
        expected = value
        actual = projected
        for part in field.split("."):
            expected, actual = expected[part], actual[part]
        assert json.dumps(actual, sort_keys=True) == json.dumps(
            expected, sort_keys=True
        )


def test_real_post_receipt_validation_retains_the_original_variant_request(monkeypatch):
    from fatebridge.services import run_metadata

    original = run_metadata.attach_run_metadata

    def corrupt_after_service(*args, **kwargs):
        result = original(*args, **kwargs)
        result["chart_profile"]["chart_type"] = "chart"
        return result

    monkeypatch.setattr(run_metadata, "attach_run_metadata", corrupt_after_service)
    with empty_ephemeris_path():
        result = execute_tool(
            AGGREGATE,
            aggregate_request("guolao_chart"),
            options=ExecutionOptions(
                as_of="2026-11-12T04:15:00Z",
                trace_id="variant-binding",
                parent_run_id="original-input",
            ),
        )
    assert result["error_code"] == "internal_error"
    assert result["trace_id"] == "variant-binding"
    assert result["parent_run_id"] == "original-input"
