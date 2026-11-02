"""Confirmed false source antecedents must remain distinct from missing facts."""

import asyncio
import itertools
import json

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua_weather import build_weather_interpretation
from fatebridge.core.requests.meihua import MeihuaWeatherContext
from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

PRIOR_RULES = {
    "long_rain_gen_stops",
    "long_rain_qian_clears",
    "long_clear_kun_rain",
    "many_gen_long_rain_clear",
}


def rows(output):
    return {r["rule_id"]: r for r in output["weather"]["rule_trace"]}


def test_confirmed_neither_is_accepted_but_never_supplied_by_default():
    assert MeihuaWeatherContext().prior_condition is None
    assert MeihuaWeatherContext(prior_condition=None).prior_condition is None
    assert (
        MeihuaWeatherContext(prior_condition="neither_prolonged").prior_condition
        == "neither_prolonged"
    )


@pytest.mark.parametrize("value", ["", "unknown", "dry", "mixed", False, 0])
def test_no_undeclared_alias_or_rainfall_proxy_becomes_confirmed_neither(value):
    with pytest.raises(ValidationError):
        MeihuaWeatherContext(prior_condition=value)


@pytest.mark.parametrize("threshold", [None, 2])
def test_all384_casts_confirmed_neither_only_disables_four_prior_clauses(threshold):
    for bits in itertools.product("01", repeat=6):
        for line in range(1, 7):
            cast = calculate_meihua_cast(
                casting={
                    "method": "existing",
                    "hexagram_code": "".join(bits),
                    "moving_line": line,
                }
            )["meihua"]
            unknown = build_weather_interpretation(cast, {"many_min_count": threshold})
            neither = build_weather_interpretation(
                cast,
                {"many_min_count": threshold, "prior_condition": "neither_prolonged"},
            )
            before, after = rows(unknown), rows(neither)
            assert len(after) == 40
            assert neither["weather"]["context"]["season"] is None
            assert neither["weather"]["single_forecast"] is None
            for rule_id in after:
                if rule_id not in PRIOR_RULES:
                    assert after[rule_id] == before[rule_id]
                    continue
                assert after[rule_id]["status"] == "not_met"
                prior = next(
                    c
                    for c in after[rule_id]["conditions"]
                    if c["condition"] == "prior_condition"
                )
                assert prior["actual"] == "neither_prolonged" and prior["met"] is False
                assert after[rule_id]["effective_status"] == "not_met"
                assert rule_id not in neither["weather"]["matched_rule_ids"]
                assert rule_id not in neither["weather"]["pending_rule_ids"]


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_confirmed_neither_and_pending_other_conditions_agree_on_all_surfaces(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = {
        "interpretation_topic": "weather",
        "weather_context": {"prior_condition": "neither_prolonged"},
    }
    if tool == "meihua_cast":
        payload["casting"] = {
            "method": "existing",
            "hexagram_code": "001010",
            "moving_line": 4,
        }
    else:
        payload.update(
            analysis_year=2026,
            analysis_month=2,
            analysis_day=19,
            analysis_hour=6,
            analysis_timezone="Asia/Hong_Kong",
        )
    fields = ["interpretation.weather", "interpretation.evidence_scope", "summary"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
            "--weather-context",
            json.dumps(payload["weather_context"]),
        ],
    )
    protocol = asyncio.run(
        native(spec, payload, fields=fields, strict_fields=True, response_char_limit=0)
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        assert weather["context"]["prior_condition"] == "neither_prolonged"
        assert weather["context"]["season"] is None
        assert weather["context"]["many_min_count"] is None
        assert all(
            r["status"] == "not_met"
            for r in weather["rule_trace"]
            if r["rule_id"] in PRIOR_RULES
        )
        assert weather["single_forecast"] is None
        study = weather["research_validation"]["current_profile_study"]
        assert study["primary"]["correct"] == 29
        assert study["primary"]["all_dates_always_dry_correct"] == 158
        assert study["primary"]["primary_full_cohort_gate_met"] is False
