"""Every explicit cast uses the same source method on all public transports."""

import pytest
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from fatebridge.core.public_output import same_public_value
from tests.support.transports import SPECS, business, rest, surface_calls

# These calls check transport parity. Source comparisons use the historical corpus
# in test_meihua_casting.py.
MODES = [
    {
        "method": "sound_groups",
        "first_count": 1,
        "second_count": 5,
        "hour_branch": "酉",
    },
    {"method": "text_tones", "tones": [1, 4, 3, 3, 1, 1], "text": "今日動靜如何"},
    {"method": "text_strokes", "strokes": [7, 10], "text": "西林"},
    {
        "method": "observed_trigrams",
        "upper_trigram": "离",
        "lower_trigram": "兑",
        "hour_branch": "辰",
    },
    {"method": "length_zhang_chi", "zhang": 12, "chi": 3, "cun": 9},
    {"method": "length_chi_cun", "chi": 12, "cun": 3, "fen": 9, "hour_branch": "酉"},
    {
        "method": "single_character_strokes",
        "script_style": "regular",
        "left_strokes": 3,
        "right_strokes": 7,
        "total_strokes": 10,
    },
    {"method": "text_count", "character_count": 11},
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


@pytest.mark.parametrize(
    "casting",
    [
        *MODES,
        {
            "method": "observed_categories",
            "subject_category": "elder_person",
            "subject_description": "虚构独行老人",
            "single_subject_confirmed": True,
            "direction": "southeast",
            "direction_role": "from",
            "hour_branch": "卯",
        },
        {
            "method": "lunar_time_added_count",
            "year_branch": "巳",
            "lunar_month": 12,
            "lunar_day": 29,
            "hour_branch": "子",
            "added_count": 1,
        },
    ],
    ids=lambda x: x["method"],
)
def test_published_first_view_survives_strict_projection(casting, surface_calls):
    spec = SPECS["meihua_cast"]
    fields = suggested_fields(spec, view="general")
    assert fields == suggested_fields(spec)
    assert {
        "meihua.base_hexagram.binary_code",
        "meihua.mutual_hexagram.binary_code",
        "meihua.changed_hexagram.binary_code",
        "meihua.seed.moving_line",
        "meihua.body_trigram.name",
        "meihua.use_trigram.name",
        "meihua.body_use_relation",
        "interpretation.classical_text_reference",
        "summary",
    } <= set(fields)
    payload = {"casting": casting, "question": "天气、婚姻（仅作为测试文字）"}
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    full_response, full_protocol, full_code, full_cli = surface_calls(
        spec,
        payload,
        params={"response_char_limit": 0},
        flags=["--response-char-limit", "0"],
    )
    assert (
        full_response.status_code == 200
        and full_code == 0
        and not full_protocol.is_error
    )
    full = full_response.json()
    assert (
        business(full)
        == business(full_cli)
        == business(full_protocol.structured_content)
    )
    assert "projection_warnings" not in local
    assert "seasonal_strength" not in local["meihua"]
    assert local["meihua"]["calendar_policy"]["context_status"] == "not_supplied"
    assert local["interpretation"]["interpretation_topic"] == "general"
    assert set(local["interpretation"]) == {
        "interpretation_topic",
        "classical_text_reference",
    }
    assert full["meihua"]["seasonal_strength"] is None
    assert full["meihua"]["calendar_policy"]["true_solar_time_applied"] is False
    assert full["interpretation"]["weather"] is None
    assert full["interpretation"]["topic_reading"] is None
    for field in fields:
        projected_value, full_value = local, full
        for part in field.split("."):
            projected_value, full_value = projected_value[part], full_value[part]
        assert projected_value is not None, field
        assert same_public_value(projected_value, full_value), field


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
