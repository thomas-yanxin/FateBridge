"""Systematic coverage of natal interpretation without multiplying test nodes."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.core.fengshui.models import (
    Placement,
    XuankongInterpretationRequest,
    XuankongRequest,
)
from fatebridge.core.fengshui.natal_interpretation import (
    analyze_natal_interpretation,
    interpretation_provenance,
)
from fatebridge.core.fengshui.xuankong import xuankong_natal

DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
NUMBER_FIELDS = (
    "period_star_number",
    "mountain_star_number",
    "facing_star_number",
)


def _natal(period, angle, uncertainty=0):
    return xuankong_natal(
        XuankongRequest.model_validate(
            {
                "house": {"facing_degrees": angle, "north_reference": "magnetic"},
                "period": {
                    "basis": "expert_confirmed",
                    "period_number": period,
                    "evidence": "独立确认历史宅运",
                },
                "bearing_uncertainty_degrees": uncertainty,
            }
        )
    )


def _config(current):
    return XuankongInterpretationRequest.model_validate(
        {
            "current_period_number": current,
            "period_evidence": "单独确认评价时运，不改变历史宅运",
            "external_forms": [
                {
                    "direction": direction,
                    "mountain_present": False,
                    "water_present": False,
                    "observation_basis": "measured",
                    "evidence": f"{direction}全宅外宫独立核对，山形水形均不存在",
                }
                for direction in DIRECTIONS
            ],
        }
    )


def _assert_candidate_facts(original, interpreted, current):
    assert interpreted["candidate_id"] == original["candidate_id"]
    assert interpreted["natal_period_number"] == original["period_number"]
    for direction, palace in interpreted["palaces"].items():
        numbers = original["palaces"][direction]
        assert {key: palace[key] for key in NUMBER_FIELDS} == {
            key: numbers[key] for key in NUMBER_FIELDS
        }
        for role, form_key in (("mountain", "mountain"), ("facing", "water")):
            is_current = numbers[f"{role}_star_number"] == current
            assert palace["timeliness"][role]["status"] == (
                "current" if is_current else "not_current"
            )
            condition = palace["external_form_analysis"][form_key]
            expected = (
                "not_applicable_center"
                if direction == "C"
                else (
                    "required_form_absent"
                    if is_current
                    else "rule_not_covered_not_inauspicious"
                )
            )
            assert condition["status"] == expected
            assert condition["condition_match"] is (
                False if direction != "C" and is_current else None
            )
            assert condition["candidate_only"] is False
    for role in ("mountain", "facing"):
        assert (
            sum(
                p["timeliness"][role]["status"] == "current"
                for p in interpreted["palaces"].values()
            )
            == 1
        )


def test_all_periods_mountains_lower_replacement_and_current_periods_preserve_chart():
    # 9 natal periods × 24 mountains × centre/left/right × 9 evaluation periods.
    # This exercises 5,832 independent evaluations in one test, including five
    # yellow and replacement charts, without regenerating any numeric oracle.
    configs = [_config(current) for current in range(1, 10)]
    placements = [
        Placement(object_id="bed", purpose="bed", location_direction="N"),
        Placement(object_id="door", purpose="door", location_direction="S"),
    ]
    modes = set()
    evaluated = 0
    for natal_period in range(1, 10):
        for mountain in range(24):
            for offset in (-6, 0, 6):
                natal = _natal(natal_period, (mountain * 15 + offset) % 360)
                before = deepcopy(natal)
                assert natal["status"] == "complete"
                original = natal["chart"]
                modes.add(original["chart_mode"])
                for current, config in enumerate(configs, start=1):
                    result = analyze_natal_interpretation(config, natal, placements)
                    assert result["status"] == "complete"
                    assert result["missing_inputs"] == []
                    assert result["rule_coverage_status"] == "limited"
                    assert result["overall_auspiciousness"] == "not_produced"
                    assert result["current_period_context"]["number"] == current
                    assert len(result["candidates"]) == 1
                    interpreted = result["candidates"][0]
                    assert interpreted["candidate_only"] is False
                    _assert_candidate_facts(original, interpreted, current)
                    for finding in interpreted["placement_findings"]:
                        assert finding["selected_star_role"] == (
                            "mountain" if finding["purpose"] == "bed" else "facing"
                        )
                        assert finding["condition_match"] in (False, None)
                        assert finding["overall_auspiciousness"] == "not_produced"
                    assert natal == before
                    evaluated += 1
    assert modes == {"lower", "replacement"}
    assert evaluated == 5832


def test_all_mountain_boundaries_keep_each_candidate_separate_with_complete_forms():
    config = _config(9)
    saw_distinct = False
    for natal_period in range(1, 10):
        for mountain in range(24):
            natal = _natal(natal_period, (mountain * 15 + 7.5) % 360)
            before = deepcopy(natal)
            originals = {c["candidate_id"]: c for c in natal["candidates"]}
            result = analyze_natal_interpretation(config, natal, [])
            assert len(originals) > 1
            assert result["status"] == "partial"
            assert result["missing_inputs"] == ["xuankong_natal.unambiguous_bearing"]
            interpreted = {c["candidate_id"]: c for c in result["candidates"]}
            assert set(interpreted) == set(originals)
            for candidate_id, candidate in interpreted.items():
                assert candidate["candidate_only"] is True
                _assert_candidate_facts(originals[candidate_id], candidate, 9)
            fingerprints = {
                tuple(
                    tuple(p[key] for key in NUMBER_FIELDS)
                    for p in candidate["palaces"].values()
                )
                for candidate in interpreted.values()
            }
            saw_distinct |= len(fingerprints) > 1
            assert natal == before
    assert saw_distinct


def test_every_returned_rule_and_source_resolves_to_the_versioned_bundle():
    bundle = json.loads(
        (
            Path(__file__).parents[2]
            / "src/fatebridge/data/fengshui/natal-interpretation-v1.json"
        ).read_text(encoding="utf-8")
    )
    registered = {rule["rule_id"] for rule in bundle["rules"].values()}
    result = analyze_natal_interpretation(
        _config(9),
        _natal(8, 355.5),
        [Placement(object_id="bed", purpose="bed", location_direction="N")],
    )
    observed_rules = set()

    def visit(value):
        if isinstance(value, dict):
            if "rule_id" in value:
                assert value["rule_id"] in registered
                assert value["source_ids"]
                assert set(value["source_ids"]) <= set(bundle["sources"])
                assert value["conditions"]
                observed_rules.add(value["rule_id"])
            for rule_id in value.get("related_rule_ids", []):
                assert rule_id in registered
                observed_rules.add(rule_id)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)
    assert observed_rules == registered
    sources = interpretation_provenance()["sources"]
    assert {source["source_id"] for source in sources} == set(bundle["sources"])
    assert all(source["url"].startswith("https://") for source in sources)


def test_new_crossfield_schema_rejects_runtime_invalid_whitespace_and_duplicate_sectors():
    validator = Draft202012Validator(XuankongInterpretationRequest.model_json_schema())
    duplicate = _config(9).model_dump(mode="json")
    duplicate["external_forms"] = duplicate["external_forms"][:1] * 2
    blank_form = _config(9).model_dump(mode="json")
    blank_form["external_forms"][0]["evidence"] = " \t\n"
    invalid = [
        {"current_period_number": 9, "period_evidence": " \t\n"},
        blank_form,
        duplicate,
    ]
    for inputs in invalid:
        with pytest.raises(ValidationError):
            XuankongInterpretationRequest.model_validate(inputs)
        assert list(validator.iter_errors(inputs)), inputs
