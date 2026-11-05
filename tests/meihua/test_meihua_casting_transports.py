"""Every explicit cast uses the same source method on all public transports."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from tests.support.transports import SPECS, business, rest, surface_calls

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/meihua_casting_v1/cases.json").read_text()
)["cases"]
MODES = list({c["input"]["method"]: c["input"] for c in CASES}.values()) + [
    {"method": "object_count", "count": 6, "hour_branch": "卯"},
    {"method": "object_count", "count": 9, "hour_branch": "酉"},
    {
        "method": "object_count",
        "count": 9,
        "hour_branch": "酉",
        "line_sum_basis": "trigram_numbers",
    },
    {"method": "existing", "hexagram_code": "101110", "moving_line": 1},
]


@pytest.mark.parametrize("casting", MODES, ids=lambda x: x["method"])
def test_explicit_methods_agree_on_rest_mcp_cli(casting, surface_calls):
    spec = SPECS["meihua_cast"]
    payload = {"casting": casting, "question": "虚构原法验收"}
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["meihua"]["seed"]["casting_method"] == casting["method"]
        assert output["run_metadata"]["determinism"]["uses_current_time"] is False
        assert (
            "meihua_explicit_casts_v1@1.5.0"
            in output["run_metadata"]["provenance"]["ruleset"]
        )
        assert output["meihua"]["seasonal_strength"] is None


def test_published_first_view_survives_strict_projection(surface_calls):
    spec = SPECS["meihua_cast"]
    fields = suggested_fields(spec)
    payload = {"casting": MODES[0]}
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )


def test_missing_clock_is_not_filled_for_a_method_that_needs_it(surface_calls):
    spec = SPECS["meihua_cast"]
    payload = {
        "casting": {
            "method": "observed_trigrams",
            "upper_trigram": "乾",
            "lower_trigram": "巽",
        }
    }
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and protocol.is_error
