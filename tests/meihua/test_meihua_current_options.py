"""One current options contract accepts nulls and validates all supplied facts."""

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.output_facts import canonical_json
from tests.support.transports import AS_OF, SPECS, business

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
    else:
        pass
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
def test_omitted_and_null_optional_facts_have_identical_current_business(
    kind: str, topic: str
) -> None:
    omitted = result(kind, interpretation_topic=topic)
    explicit_null = result(kind, interpretation_topic=topic, **dict.fromkeys(FIELDS))
    assert "error" not in omitted and "error" not in explicit_null
    assert canonical_json(omitted) == canonical_json(explicit_null)


@pytest.mark.parametrize("kind", ["cast", "time"])
@pytest.mark.parametrize("field,value", VALID)
def test_supplied_facts_survive_the_current_options_boundary(
    kind: str, field, value
) -> None:
    topic = "reputation" if field == "reputation_context" else "general"
    output = result(kind, interpretation_topic=topic, **{field: value})
    assert "error" not in output
    facts = output["analysis_context"]
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
def test_invalid_supplied_optional_facts_are_rejected(field) -> None:
    with pytest.raises(ValidationError):
        MeihuaInterpretationOptions.model_validate(
            {
                "interpretation_topic": (
                    "reputation" if field == "reputation_context" else "general"
                ),
                field: "invalid",
            }
        )


def test_current_observation_model_retains_soil_generation_qualification() -> None:
    out = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111111", "moving_line": 6},
        external_observations=[{"manifestation": "soil", "label": "虚构新模型探针"}],
    )
    assert (
        out["interpretation"]["external_omens"]["observations"][0]["qualification"]
        == "substantive_generation"
    )


@pytest.mark.parametrize(
    "observation,wording,orientation_state",
    [
        ({"orientation": "approaching"}, "器物方來則吉", True),
        ({"orientation": "departing"}, "去則吉已過矣", True),
        ({"motion": "stationary"}, None, False),
        ({"motion": "moving"}, None, None),
    ],
)
def test_xiangbei_keeps_orientation_and_motion_separate(
    observation: dict[str, str], wording: str | None, orientation_state: bool | None
) -> None:
    output = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111111", "moving_line": 6},
        external_observations=[
            {"manifestation": "soil", "label": "所报器物", **observation}
        ],
    )
    layer = output["interpretation"]["motion_context"]
    assert layer["orientation_source"]["section"] == "卷二·向背"
    assert (
        layer["orientation_source"]["edition_status"]
        == "fixed_transcription_not_independently_collated_facsimile"
    )
    (row,) = layer["external_motion"]
    assert row["orientation"] == observation.get("orientation")
    assert row["motion"] == observation.get("motion")
    assert row["omen_valence"] is row["event_time"] is None
    matched = [
        c for c in row["orientation_clauses"] if c["symbolic_relation_condition_met"]
    ]
    assert len(matched) == 2
    assert all(c["cross_chapter_qualification_met"] is None for c in matched)
    if wording is None:
        assert all(c["orientation_condition_met"] is orientation_state for c in matched)
    else:
        (clause,) = [c for c in matched if c["orientation_condition_met"] is True]
        assert clause["relative_wording"] == wording
        assert clause["full_clause_applies"] is None


@pytest.mark.parametrize("key", ["meihua_cast", "meihua_time_cast"])
def test_xiangbei_projects_and_rejects_contradictions_on_all_transports(
    key: str, surface_calls
) -> None:
    if key == "meihua_cast":
        cast = {
            "casting": {
                "method": "existing",
                "hexagram_code": "111111",
                "moving_line": 6,
            }
        }
    else:
        cast = dict(
            analysis_year=2001,
            analysis_month=5,
            analysis_day=22,
            analysis_hour=23,
            analysis_timezone="Asia/Shanghai",
        )
    observation = {
        "manifestation": "soil",
        "label": "所报器物",
        "orientation": "departing",
    }
    projection = dict(
        fields=["interpretation.motion_context"],
    )
    http, mcp, code, cli = surface_calls(
        SPECS[key],
        {**cast, "external_observations": [observation]},
        projection=projection,
        rest_as_of=AS_OF,
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    row = cli["interpretation"]["motion_context"]["external_motion"][0]
    assert row["orientation"] == "departing" and row["motion"] is None

    http, mcp, code, _ = surface_calls(
        SPECS[key],
        {**cast, "external_observations": [{**observation, "motion": "stationary"}]},
        projection=projection,
        rest_as_of=AS_OF,
    )
    assert http.status_code == 422 and mcp.is_error and code != 0


def test_xiangbei_uses_the_original_body_of_each_count_candidate() -> None:
    output = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
        },
        external_observations=[
            {
                "manifestation": "furnace_flame",
                "label": "所报外物",
                "orientation": "departing",
            }
        ],
    )
    candidates = output["interpretation"]["casting_readings"]
    assert [row["body"] for row in candidates] == ["离", "乾"]
    matching_rules = []
    for candidate in candidates:
        (row,) = candidate["motion_context"]["external_motion"]
        matching_rules.append(
            [
                clause["rule_id"]
                for clause in row["orientation_clauses"]
                if clause["orientation_condition_met"]
                and clause["symbolic_relation_condition_met"]
            ]
        )
    assert matching_rules == [[], ["xiangbei_controlling_departure"]]
