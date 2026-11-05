"""One current options contract accepts nulls and validates all supplied facts."""

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.output_facts import canonical_json

FIELDS = [
    "external_observations",
    "matter_scenario",
    "observer_activity",
    "observation_context",
    "response_context",
    "reputation_context",
]
VALID = [
    (
        "external_observations",
        [{"manifestation": "actual_water", "label": "declared test input"}],
    ),
    ("matter_scenario", "favorable_matter"),
    ("observer_activity", "seated"),
    ("observation_context", {"label": "declared test input", "quiet_room": True}),
    (
        "response_context",
        {
            "label": "declared test input",
            "same_casting_episode_confirmed": True,
            "weather": ["clear"],
        },
    ),
    (
        "reputation_context",
        {"label": "declared test input", "currently_in_office": False},
    ),
]


def result(kind, **kwargs):
    if kind == "cast":
        return calculate_meihua_cast(
            casting={"method": "existing", "hexagram_code": "111101", "moving_line": 1},
            **kwargs,
        )
    return calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=26,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["cast", "time"])
@pytest.mark.parametrize("topic", ["general", "reputation"])
def test_omitted_and_null_optional_facts_have_identical_current_business(kind, topic):
    omitted = result(kind, interpretation_topic=topic)
    explicit_null = result(kind, interpretation_topic=topic, **dict.fromkeys(FIELDS))
    assert "error" not in omitted and "error" not in explicit_null
    assert canonical_json(omitted) == canonical_json(explicit_null)


@pytest.mark.parametrize("kind", ["cast", "time"])
@pytest.mark.parametrize("field,value", VALID)
def test_supplied_facts_survive_the_current_options_boundary(kind, field, value):
    topic = "reputation" if field == "reputation_context" else "general"
    output = result(kind, interpretation_topic=topic, **{field: value})
    assert "error" not in output
    facts = output["input_normalized" if kind == "cast" else "analysis_context"]
    if field == "external_observations":
        rows = output["interpretation"]["external_omens"]["observations"]
        assert len(rows) == len(value)
        for row, provided in zip(rows, value, strict=True):
            actual = output
            for part in row["reported_fact_path"].split("."):
                actual = actual[int(part)] if isinstance(actual, list) else actual[part]
            assert actual == provided
    elif isinstance(value, dict):
        assert all(facts[field][key] == item for key, item in value.items())
    else:
        assert facts[field] == value


@pytest.mark.parametrize("field", FIELDS)
def test_invalid_supplied_optional_facts_are_rejected(field):
    with pytest.raises(ValidationError):
        MeihuaInterpretationOptions.model_validate(
            {
                "interpretation_topic": (
                    "reputation" if field == "reputation_context" else "general"
                ),
                field: "invalid",
            }
        )
