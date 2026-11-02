"""Reject corrupted time-layer declarations before output projection."""

from copy import deepcopy

import pytest

from fatebridge.application.execution import OutputContractError, validate_output
from fatebridge.core.local_techniques.suzhan import build_suzhan_result
from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.services.tool_catalog import CATALOG

SPEC = next(s for s in CATALOG if s.key == "suzhan")


@pytest.fixture(scope="module")
def untimed():
    request = SuZhanRequest(
        date="2024-08-04", zone="+08:00", calendar_profile="hinoo_t1299_host27"
    )
    return request, build_suzhan_result(**request.model_dump())


@pytest.mark.parametrize(
    "fault",
    [
        "chart",
        "astronomy",
        "missing_chart",
        "missing_astronomy",
        "imputed",
        "mode",
        "calendar_clock",
        "layer",
        "clock_request",
        "missing_calendar",
        "missing_rulesets",
    ],
)
def test_rejects_invalid_date_only_layer_before_projection(untimed, fault):
    request, original = untimed
    result = deepcopy(original)
    if fault in {"chart", "astronomy"}:
        result[fault] = {"fabricated": True}
    elif fault.startswith("missing_"):
        del result[fault.removeprefix("missing_").replace("calendar", "sukuyo")]
    elif fault == "imputed":
        result["params"]["birthTimeImputed"] = True
    elif fault == "mode":
        result["params"]["calculationMode"] = "chart"
    elif fault == "calendar_clock":
        result["sukuyo"]["calendar"]["birth_time_known"] = True
    elif fault == "layer":
        result["validation"]["calculation_layers"]["astronomy"] = "computed"
    elif fault == "clock_request":
        request = request.model_copy(update={"time": "09:00:00"})
    with pytest.raises(OutputContractError):
        validate_output(SPEC, result, request=request)


def test_correct_unknown_layers_validate_and_known_clock_still_requires_chart(untimed):
    request, result = untimed
    validate_output(SPEC, result, request=request)
    request = request.model_copy(update={"time": "09:00:00"})
    known = build_suzhan_result(**request.model_dump())
    validate_output(SPEC, known, request=request)
    known["chart"] = None
    with pytest.raises(OutputContractError):
        validate_output(SPEC, known, request=request)


@pytest.fixture(scope="module")
def timed(untimed):
    request, _ = untimed
    request = request.model_copy(update={"time": "09:00:00"})
    return request, build_suzhan_result(**request.model_dump())


@pytest.mark.parametrize(
    "fault",
    [
        "calendar_false",
        "all_unknown_declarations",
        "date_only_mode",
        "unknown_method",
        "birthTimeKnown",
        "chartComputed",
        "imputed",
        "astronomyComputed",
        "layer_chart",
        "layer_calendar",
        "layer_astronomy",
    ],
)
def test_known_clock_rejects_unknown_or_contradictory_declarations(
    timed, untimed, fault
):
    request, original = timed
    result = deepcopy(original)
    if fault == "calendar_false":
        result["sukuyo"]["calendar"]["birth_time_known"] = False
    elif fault == "all_unknown_declarations":
        result["params"] = deepcopy(untimed[1]["params"])
        result["validation"] = deepcopy(untimed[1]["validation"])
    elif fault == "date_only_mode":
        result["params"]["calculationMode"] = "calendar_date_only"
    elif fault == "unknown_method":
        result["params"]["su28Method"] = "not_computed_birth_time_unknown"
    elif fault in {"birthTimeKnown", "chartComputed", "astronomyComputed"}:
        result["params"][fault] = False
    elif fault == "imputed":
        result["params"]["birthTimeImputed"] = True
    else:
        layers = {
            "calendar": result["sukuyo"]["calendar"]["status"],
            "chart": "computed",
            "astronomy": "computed",
        }
        layers[fault.removeprefix("layer_")] = "not_computed_birth_time_unknown"
        result["validation"]["calculation_layers"] = layers
    with pytest.raises(OutputContractError):
        validate_output(SPEC, result, request=request)


def test_unknown_clock_boolean_flags_are_not_integer_placeholders(untimed):
    request, original = untimed
    result = deepcopy(original)
    result["params"]["birthTimeImputed"] = 0
    with pytest.raises(OutputContractError):
        validate_output(SPEC, result, request=request)
