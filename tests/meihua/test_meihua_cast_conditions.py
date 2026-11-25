"""Self-contained clock and Xiangbei regressions without private audit fixtures."""

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from scripts.meihua.audit_meihua_cast_conditions import audit_cast_clocks
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

CASTING = {
    "method": "existing",
    "hexagram_code": "000111",
    "moving_line": 1,
}
TIME = {
    "analysis_year": 2001,
    "analysis_month": 5,
    "analysis_day": 22,
    "analysis_hour": 23,
    "analysis_timezone": "+08:00",
}


def test_hko_labels_ordinal_days_and_synthetic_calendar_vectors() -> None:
    report = audit_cast_clocks()
    assert report["checks_passed"], report
    assert report["case_count"] == 40
    assert report["synthetic_1993_lunar_vector"] == {
        "year_branch": "酉",
        "lunar_month": 1,
        "lunar_day": 12,
        "hour_branch": "午",
        "upper_number": 7,
        "lower_number": 6,
        "moving_line": 6,
    }
    assert report["synthetic_1993_solar_term_vector"] == {
        "year": {"stem": "壬", "branch": "申"},
        "month_branch": "丑",
    }


@pytest.mark.parametrize("orientation", [None, "approaching", "departing"])
@pytest.mark.parametrize(
    "manifestation,relation",
    [("soil", "用生体"), ("furnace_flame", "用克体"), ("actual_water", "体生用")],
)
def test_orientation_does_not_supply_motion_valence_or_cross_chapter_qualification(
    orientation: str | None, manifestation: str, relation: str
) -> None:
    output = calculate_meihua_cast(
        casting=CASTING,
        external_observations=[
            {
                "manifestation": manifestation,
                "label": "synthetic",
                "orientation": orientation,
            }
        ],
    )
    assert "error" not in output, output
    assert output["meihua"]["body_trigram"]["name"] == "乾"
    motion = output["interpretation"]["motion_context"]
    row = motion["external_motion"][0]
    assert row["motion"] is row["omen_valence"] is None
    assert row["orientation"] == orientation
    assert motion["orientation_source"]["section"] == "卷二·向背"
    assert (
        motion["orientation_source"]["edition_status"]
        == "fixed_transcription_not_independently_collated_facsimile"
    )
    for clause in row["orientation_clauses"]:
        assert clause["symbolic_relation_condition_met"] == (
            clause["relation"] == relation
        )
        assert clause["orientation_condition_met"] == (
            None if orientation is None else clause["orientation"] == orientation
        )
        assert clause["cross_chapter_qualification_met"] is None
        assert clause["full_clause_applies"] is (
            None
            if clause["relation"] == relation
            and orientation in (None, clause["orientation"])
            else False
        )
    assert all(clause["omen_condition_met"] is None for clause in row["moving_clauses"])
    assert motion["event_time"] is motion["combined_outcome"] is None


def test_come_and_go_keep_distinct_named_source_wording() -> None:
    output = calculate_meihua_cast(
        casting=CASTING,
        external_observations=[
            {
                "manifestation": "soil",
                "label": "synthetic approach",
                "orientation": "approaching",
                "motion": "moving",
            },
            {
                "manifestation": "soil",
                "label": "synthetic departure",
                "orientation": "departing",
                "motion": "moving",
            },
            {"manifestation": "soil", "label": "来去文本不供推断", "motion": "moving"},
        ],
    )
    rows = output["interpretation"]["motion_context"]["external_motion"]
    selected_words = [
        [
            clause["relative_wording"]
            for clause in row["orientation_clauses"]
            if clause["orientation_condition_met"]
            and clause["symbolic_relation_condition_met"]
        ]
        for row in rows
    ]
    assert selected_words == [["器物方來則吉"], ["去則吉已過矣"], []]
    assert [row["motion"] for row in rows] == ["moving"] * 3
    assert rows[2]["orientation"] is None


def test_named_source_clauses_and_each_count_candidates_own_body() -> None:
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
                "label": "synthetic",
                "orientation": "departing",
            }
        ],
    )
    candidates = output["interpretation"]["casting_readings"]
    assert [candidate["body"] for candidate in candidates] == ["离", "乾"]
    for candidate, expected_relation in zip(candidates, ["体用比和", "用克体"]):
        row = candidate["motion_context"]["external_motion"][0]
        assert [clause["rule_id"] for clause in row["orientation_clauses"]] == [
            "xiangbei_controlling_approach",
            "xiangbei_controlling_departure",
            "xiangbei_generating_approach",
            "xiangbei_generating_departure",
        ]
        assert [
            clause["relative_wording"] for clause in row["orientation_clauses"]
        ] == [
            "其禍將至",
            "去則禍散",
            "器物方來則吉",
            "去則吉已過矣",
        ]
        assert [clause["quote"] for clause in row["orientation_clauses"]] == [
            "其克體之卦，器物方來，其禍將至，去則禍散。",
            "其克體之卦，器物方來，其禍將至，去則禍散。",
            "其生體之卦，器物方來則吉，去則吉已過矣。",
            "其生體之卦，器物方來則吉，去則吉已過矣。",
        ]
        assert [
            clause["symbolic_relation_condition_met"]
            for clause in row["orientation_clauses"]
        ] == (
            [False] * 4
            if expected_relation == "体用比和"
            else [True, True, False, False]
        )


def test_stationary_observation_rules_out_both_directions() -> None:
    """Declared stationary objects cannot leave either come/go clause pending."""
    output = calculate_meihua_cast(
        casting=CASTING,
        external_observations=[
            {"manifestation": "soil", "label": "synthetic", "motion": "stationary"}
        ],
    )
    row = output["interpretation"]["motion_context"]["external_motion"][0]
    assert row["orientation"] is None
    assert all(
        clause["orientation_condition_met"] is False
        for clause in row["orientation_clauses"]
    )
    assert all(
        clause["full_clause_applies"] is False for clause in row["orientation_clauses"]
    )


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize("projected", [False, True])
def test_clock_and_orientation_real_surfaces(tool, projected, surface_calls) -> None:
    payload = {"casting": CASTING} if tool == "meihua_cast" else dict(TIME)
    payload["external_observations"] = [
        {
            "manifestation": "soil",
            "label": "synthetic",
            "orientation": "departing",
            "motion": "moving",
        }
    ]
    fields = ["meihua.seed", "interpretation.motion_context"]
    if tool == "meihua_analysis":
        fields += ["meihua.calendar_policy", "interpretation.day_qi"]
    else:
        pass
    projection = {"response_char_limit": 0, "include_snapshot_text": False}
    if projected:
        projection.update(fields=fields, strict_fields=True)
    else:
        pass
    response, protocol, code, cli = surface_calls(
        SPECS[tool], payload, projection=projection, rest_as_of=AS_OF
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(cli)
    )
    layer = cli["interpretation"]["motion_context"]
    assert layer["external_motion"][0]["orientation"] == "departing"
    if tool == "meihua_analysis":
        days = cli["interpretation"]["day_qi"]["calendar_candidates"]
        assert [day["calendar"] for day in days] == [
            {
                "id": "local_midnight",
                "date": "2001-05-22",
                "ganzhi": "乙酉",
                "day_branch": "酉",
                "day_boundary": "local_midnight",
            },
            {
                "id": "zi_start",
                "date": "2001-05-23",
                "ganzhi": "丙戌",
                "day_branch": "戌",
                "day_boundary": "zi_start",
            },
        ]
        assert cli["meihua"]["seed"]["lunar_day"] == 30
    else:
        pass


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
@pytest.mark.parametrize(
    "observation",
    [
        {"orientation": "approaching", "motion": "stationary"},
        {"orientation": "north"},
        {"orientation": True},
    ],
)
def test_invalid_orientation_real_surfaces(tool, observation, surface_calls) -> None:
    payload = {"casting": CASTING} if tool == "meihua_cast" else dict(TIME)
    payload["external_observations"] = [
        {"manifestation": "soil", "label": "synthetic", **observation}
    ]
    response, protocol, code, cli = surface_calls(
        SPECS[tool], payload, projection={"response_char_limit": 0}, rest_as_of=AS_OF
    )
    assert response.status_code == 422 and code != 0 and protocol.is_error
    for output in [response.json(), protocol.structured_content, cli]:
        assert output["error_code"] == "validation_error"
