"""An explicit method selection must not silently compute a different method."""

import pytest
from pydantic import ValidationError

from tests.support.transports import SPECS
from tests.support.transports import inputs as representative_inputs
from tests.support.transports import rest, surface_calls

METHODS = [
    ("astro_triplicity_rulers", "division", "halfs", ["thirds", "halves"]),
    ("astro_distributions", "time_key", "invalid", ["Ptolemy", "Naibod"]),
    (
        "astro_balbillus",
        "start_planet",
        "Neptune",
        ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
    ),
    ("astro_balbillus", "mode", "nearset", ["nearest", "forward"]),
    ("astro_keypoints", "release_mode", "spirit", ["soul", "body"]),
    (
        "astro_yearsystem129",
        "start_planet",
        "Pluto",
        ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
    ),
    (
        "astro_planetaryarc",
        "arc_source",
        "Neptune",
        [
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Ascendant",
            "Medium_Coeli",
        ],
    ),
    ("pd", "pd_time_key", "invalid", ["Ptolemy", "Naibod", "Cardan"]),
    ("astro_mundane", "ingress_term", "立春", ["春分", "夏至", "秋分", "冬至"]),
]


@pytest.mark.parametrize("tool,field,invalid,valid", METHODS)
def test_supported_methods_survive_and_unsupported_methods_fail_at_the_request_boundary(
    tool, field, invalid, valid
):
    spec = SPECS[tool]
    base = representative_inputs(spec)
    for value in valid:
        model = spec.request_model.model_validate({**base, field: value})
        assert getattr(model, field) == value
    with pytest.raises(ValidationError) as failure:
        spec.request_model.model_validate({**base, field: invalid})
    assert all(error["loc"][0] == field for error in failure.value.errors())


@pytest.mark.parametrize("tool,field,invalid,_valid", METHODS)
def test_unknown_methods_are_rejected_by_rest_mcp_and_cli(
    tool, field, invalid, _valid, surface_calls
):
    spec = SPECS[tool]
    inputs = {**representative_inputs(spec), field: invalid}
    http, protocol, code, cli = surface_calls(spec, inputs)
    assert http.status_code == 422, http.text
    assert code != 0 and "error" in cli
    assert protocol.is_error
