"""Confirmed false source antecedents must remain distinct from missing facts."""

import itertools
import json

import pytest
from pydantic import ValidationError

from fatebridge.core.meihua.topics import build_weather_interpretation
from fatebridge.core.requests.meihua import MeihuaWeatherContext
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import SPECS, business, rest, surface_calls

PRIOR_RULES = {
    "long_rain_gen_stops",
    "long_rain_qian_clears",
    "long_clear_kun_rain",
    "many_gen_long_rain_clear",
}


def test_confirmed_neither_is_accepted_but_never_supplied_by_default() -> None:
    assert MeihuaWeatherContext().prior_condition is None
    assert MeihuaWeatherContext(prior_condition=None).prior_condition is None
    assert (
        MeihuaWeatherContext(prior_condition="neither_prolonged").prior_condition
        == "neither_prolonged"
    )


@pytest.mark.parametrize("value", ["", "unknown", "dry", "mixed", False, 0])
def test_no_undeclared_alias_or_rainfall_proxy_becomes_confirmed_neither(
    value: bool | int | str,
) -> None:
    with pytest.raises(ValidationError):
        MeihuaWeatherContext(prior_condition=value)


@pytest.mark.parametrize("threshold", [None, 2])
def test_all384_casts_confirmed_neither_only_disables_four_prior_clauses(
    threshold: int | None,
) -> None:
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
            before_weather = unknown["weather"]
            after_weather = neither["weather"]
            assert after_weather["context"]["season"] is None
            assert after_weather["single_forecast"] is None
            assert set(after_weather["matched_rule_ids"]).isdisjoint(PRIOR_RULES)
            assert set(after_weather["pending_rule_ids"]).isdisjoint(PRIOR_RULES)
            assert [
                r for r in after_weather["matched_rule_ids"] if r not in PRIOR_RULES
            ] == [r for r in before_weather["matched_rule_ids"] if r not in PRIOR_RULES]
            assert [
                r for r in after_weather["pending_rule_ids"] if r not in PRIOR_RULES
            ] == [r for r in before_weather["pending_rule_ids"] if r not in PRIOR_RULES]


@pytest.mark.parametrize("tool", ["meihua_time_cast", "meihua_cast"])
def test_confirmed_neither_and_pending_other_conditions_agree_on_all_surfaces(
    tool: str, surface_calls
) -> None:
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
    fields = ["interpretation.weather", "summary"]
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params=[
            ("detail", "audit"),
            *(("fields", f) for f in fields),
        ],
        options={"detail": "audit", "fields": fields},
        flags=[
            "--detail",
            "audit",
            "--fields",
            *fields,
            "--weather-context",
            json.dumps(payload["weather_context"]),
        ],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        assert weather["context"]["prior_condition"] == "neither_prolonged"
        assert weather["context"]["season"] is None
        assert weather["context"]["many_min_count"] is None
        assert "rule_trace" not in weather
        assert set(weather["matched_rule_ids"]).isdisjoint(PRIOR_RULES)
        assert set(weather["pending_rule_ids"]).isdisjoint(PRIOR_RULES)
        assert weather["single_forecast"] is None
        assert "research_validation" not in weather
