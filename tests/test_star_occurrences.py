"""Hand-frozen source counts are not weighted force scores or extra subjects."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.output_star_occurrences import StarOccurrenceCount, StarOccurrences
from fatebridge.core.star_occurrences import build_star_occurrences

FIXTURE = Path(__file__).parent / "data/bazi/star-count-source-cases.json"
CASES = [
    c
    for c in json.loads(FIXTURE.read_text())["cases"]
    if c.get("local_count_constraints") or c.get("local_visibility_constraints")
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_source_integer_counts_and_visible_absence_match_the_published_receipt(case):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, case["pillars"])))
    evidence = build_natal_evidence(pillars)
    result = evidence["star_occurrences"]
    assert not result["day_stem_counted_as_support"]
    assert result["status"] == "complete_star_categories"
    for rule in case.get("local_count_constraints", []) + case.get(
        "local_visibility_constraints", []
    ):
        field = {None: "total_count", "天干": "visible_count", "藏干": "hidden_count"}[
            rule.get("location")
        ]
        assert sum(result["gods"][g][field] for g in rule["gods"]) == rule["count"]
    StarOccurrences.model_validate(result)


def test_missing_categories_stay_missing_and_count_units_cannot_be_forged():
    result = build_star_occurrences({"正印": []})
    assert (
        result["status"] == "partial_star_categories" and "偏印" not in result["gods"]
    )
    assert result["gods"]["正印"] == {
        "visible_count": 0,
        "hidden_count": 0,
        "total_count": 0,
    }
    with pytest.raises(ValidationError, match="实数总量"):
        StarOccurrenceCount.model_validate(
            {"visible_count": 1, "hidden_count": 2, "total_count": 2}
        )
    with pytest.raises(ValidationError):
        StarOccurrenceCount.model_validate({"hidden_count": 0.5})
    with pytest.raises(ValidationError):
        StarOccurrences.model_validate({"quantity_kind": "effective_force"})
    with pytest.raises(ValueError, match="日干"):
        build_star_occurrences({"比肩": [{"pillar": "day", "location": "天干"}]})
