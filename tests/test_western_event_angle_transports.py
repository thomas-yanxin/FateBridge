"""Actual service calculations keep reference qualification on all adapters."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest


@pytest.mark.parametrize("key", ["astro_horary", "astro_election"])
@pytest.mark.parametrize("house", ["R", "E", "N"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_unresolved_physical_reference_is_not_a_confirmed_fact_on_any_adapter(
    key, house, zodiac, rest, tmp_path, capsys
):
    prefix = "question" if key == "astro_horary" else "candidate"
    root = "horary" if key == "astro_horary" else "election"
    payload = {
        f"{prefix}_year": 2000,
        f"{prefix}_month": 1,
        f"{prefix}_day": 1,
        f"{prefix}_hour": 12,
        "name": "Synthetic reference-geometry engineering fixture",
        "timezone_name": "UTC",
        "longitude": -10.458556062519506,
        "latitude": 66.56232328397007,
        "house_system": house,
        "zodiac_type": zodiac,
    }
    spec = SPECS[key]
    # Full JSON validates all nested facts, not a stubbed domain calculation.
    http = rest.post(spec.rest_path, json=payload, params={"response_char_limit": 0})
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, ["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for index, value in enumerate(values):
        spec.output_model.model_validate(value)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(value)
        facts = value[root]
        assert facts["ascendant"]["longitude"] is None
        assert facts["reference_geometry"]["ascendant_resolved"] is False
        assert (
            facts["calculation_basis"]["angle_definition"][
                "geometric_ascendant_resolved"
            ]
            is False
        )
        assert facts["backend_convention"]["ascendant"]["longitude"] is not None
        if root == "horary":
            assert facts["fortune"]["longitude"] is None
            assert facts["significators"]["querent"] is None
            assert facts["perfection"]["event_history"]["status"] == "computed"
            assert facts["rule_profile"]["full_original_text_acceptance"] is False
        else:
            assert facts["score"] is None and facts["score_bounds"] is not None
            assert facts["axes"]["midheaven_longitude"] is not None
            assert "非概率区间" in value["summary"]
        (tmp_path / f"{root}-{index}.json").write_text(json.dumps(value))
