"""Source variants, actual candidate roles and source-specific summaries."""

import hashlib
import json

import pytest

from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.meihua_households_reference import (
    CASES,
    FOLDER,
    assert_candidate_chapter_summary,
    validate,
)


def test_source_and_decisions_remain_frozen_before_new_chapter_production():
    freeze = json.loads((FOLDER / "reference-freeze.json").read_bytes())
    assert not freeze["new_production_implemented_before_freeze"]
    assert freeze["reused_geometries"] == 384
    assert freeze["literal_source_relation_unknown_rows"] == 1
    for name, digest in freeze["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(
    "case", CASES, ids=lambda row: f"{row['topic']}-{row['code']}-{row['line']}"
)
def test_all_768_reused_geometry_topic_contexts_keep_literal_variants_roles_and_unknowns(
    case,
):
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic=case["topic"],
    )
    validate(result, case["topic"])


TOPICS = [
    "planning",
    "reputation",
    "wealth",
    "transaction",
    "travel",
    "meeting",
    "lost_property",
    "traveler",
    "household",
    "dwelling",
]


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_every_explicit_chapter_candidate_explains_its_own_chapter_instead_of_generic_initial_judgement(
    topic, basis
):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 10,
            "second_count": 3,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        interpretation_topic=topic,
        season_month_branch="辰",
    )
    rows = result["interpretation"]["casting_readings"]
    manual = json.loads((FOLDER / "manual-candidate-probe.json").read_bytes())
    expected_by_basis = {record["basis"]: record for record in manual["candidates"]}
    assert len(rows) == 2
    assert {row["line_sum_basis"] for row in rows} == set(expected_by_basis)
    for row in rows:
        expected = expected_by_basis[row["line_sum_basis"]]
        assert row["base_code"] == manual["code"]
        assert (
            row["line_sum_basis"],
            row["moving_line"],
            row["body"],
            row["use"],
            row["body_use_relation"],
        ) == (
            expected["basis"],
            expected["line"],
            expected["body"],
            expected["use"],
            expected["relation"],
        )
        assert_candidate_chapter_summary(row)
    assert len({row["topic_clause"]["quote"] for row in rows}) == 2
    if topic in {"household", "dwelling"}:
        validate(result, topic)


@pytest.mark.parametrize("topic", ["household", "dwelling"])
def test_new_chapter_does_not_recast_the_analysis_clock_or_calendar(topic):
    arguments = {
        "analysis_year": 2026,
        "analysis_month": 2,
        "analysis_day": 16,
        "analysis_hour": 23,
        "analysis_timezone": "Asia/Shanghai",
    }
    baseline = calculate_meihua_analysis(**arguments)
    result = calculate_meihua_analysis(**arguments, interpretation_topic=topic)
    validate(result, topic)
    for key in (
        "seed",
        "base_hexagram",
        "changed_hexagram",
        "mutual_hexagram",
        "body_trigram",
        "use_trigram",
        "stage_relations",
        "seasonal_strength",
        "calendar_policy",
        "rule_trace",
    ):
        assert result["meihua"][key] == baseline["meihua"][key]


def test_household_words_in_question_do_not_change_default_branch():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "000000", "moving_line": 1},
        question="家宅、屋舍",
    )
    assert result["interpretation"]["interpretation_topic"] == "general"
    assert result["interpretation"]["topic_reading"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "automatic_bili",
        "emended_quote",
        "borrowed_chapter_summary",
        "missing_chapter_summary",
    ],
)
def test_independent_content_checks_reject_automatic_source_emendation_or_candidate_summary_borrowing(
    mutation,
):
    result = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 10,
            "second_count": 3,
            "hour_branch": "子",
        },
        interpretation_topic="household",
    )
    if mutation in {"automatic_bili", "emended_quote"}:
        result = calculate_meihua_cast(
            casting={"method": "existing", "hexagram_code": "000000", "moving_line": 1},
            interpretation_topic="household",
        )
        clause = result["interpretation"]["topic_reading"]
        if mutation == "automatic_bili":
            clause["source_relation_condition"] = True
        else:
            clause["quote"] = "體用比和家宅安穩"
    else:
        rows = result["interpretation"]["casting_readings"]
        rows[0]["traditional_judgement"] = (
            rows[1]["traditional_judgement"]
            if mutation == "borrowed_chapter_summary"
            else ""
        )
    with pytest.raises(AssertionError):
        validate(result, "household")
