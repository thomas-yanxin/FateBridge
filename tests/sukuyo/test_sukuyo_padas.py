"""108 manually annotated source cells and counterexamples to birth inference."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.compatibility import SukuyoCompatibilityRequest
from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_padas import palace_reference, reference_cell, source_bundle
from fatebridge.services.divination import (
    calculate_sukuyo_compatibility,
    calculate_suzhan_analysis,
)

REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-palace-pada-primary.json").read_text()
)


def test_all_108_cells_against_manually_annotated_source_grid():
    bundle = source_bundle()
    assert bundle["source_sha256"] == REFERENCE["source_sha256"]
    assert [p["literal_name"] for p in bundle["palaces"]] == REFERENCE["source_names"]
    assert [p["ruler_luminary"] for p in bundle["palaces"]] == REFERENCE["source_lords"]
    assert set(REFERENCE["expected_palace_ordinals"]) == set(SU27_ORDER)
    counts = {p: 0 for p in range(1, 13)}
    for name, expected in REFERENCE["expected_palace_ordinals"].items():
        for pada, ordinal in enumerate(expected, 1):
            actual = reference_cell(name, pada)
            assert actual["palace_ordinal"] == ordinal, (name, pada)
            assert actual["locator"] == REFERENCE["clauses"][ordinal - 1]["locator"]
            counts[ordinal] += 1
    assert list(counts.values()) == [9] * 12
    assert not bundle["pada_ordinals_explicit_in_source"]


def test_cow_palace_is_not_a_28th_mansion_and_literal_variants_are_preserved():
    assert reference_cell("毕", 1)["palace_name"] == "牛宫"
    with pytest.raises(ValueError):
        reference_cell("牛", 1)
    palaces = source_bundle()["palaces"]
    assert palaces[0]["literal_name"] == "師子宮"
    assert palaces[5]["literal_name"] == "磨竭宮"
    assert palaces[5]["textual_variants"][0]["variant"] == "摩竭"
    assert [p["division"] for p in palaces] == ["太阳分"] * 6 + ["太阴分"] * 6


def test_split_mansion_requires_explicit_reference_pada_without_guessing():
    context = {"natal_su27": "翼"}
    unknown = palace_reference(context)
    first, second = palace_reference(context, 1), palace_reference(context, 2)
    assert unknown["selected_palace"] is None
    assert [r["pada"] for r in unknown["rows"]] == [1, 2, 3, 4]
    assert [r["name"] for r in unknown["candidate_palaces"]] == ["师子宫", "女宫"]
    assert first["selected_palace"]["name"] == "师子宫"
    assert second["selected_palace"]["name"] == "女宫"
    assert not second["birth_pada_established"]
    single = palace_reference({"natal_su27": "毕"})
    assert single["selected_palace"]["name"] == "牛宫"
    assert single["textual_pada"] is None and len(single["rows"]) == 4


def test_partial_mansion_does_not_block_other_layers_or_hide_incomplete_candidates():
    same_palace = calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    assert same_palace["natal_su27"] is None
    r = palace_reference(same_palace)
    assert r["status"] == "palace_resolved_from_complete_candidates"
    assert r["selected_palace"]["name"] == "师子宫"
    r = palace_reference(calendar_mansion("2025-07-25"))
    assert r["status"] == "candidate_set_incomplete" and r["selected_palace"] is None
    assert [p["name"] for p in r["candidate_palaces"]] == ["蟹宫"]
    changed = deepcopy(same_palace)
    changed["candidate_su27s"] = ["张", "翼"]
    assert palace_reference(changed)["selected_palace"] is None


@pytest.mark.parametrize("pada", [0, 5, True, 1.5, "1"])
def test_invalid_pada_is_rejected_without_coercion_by_domain_and_public_requests(pada):
    with pytest.raises(ValueError):
        palace_reference({"natal_su27": "翼"}, pada)
    with pytest.raises(ValidationError):
        SuZhanRequest(date="2025-03-04", time="12:00:00", textual_pada=pada)
    with pytest.raises(ValidationError):
        SukuyoCompatibilityRequest(
            person1_date="1990-06-15",
            person2_date="1992-03-20",
            person1_textual_pada=pada,
        )


def test_reference_pada_does_not_change_calendar_sanjiu_activities_or_sky():
    kwargs = dict(
        date="2025-03-04",
        time="12:00:00",
        zone="+08:00",
        natal_mansion="奎",
        activity="marriage",
    )
    first = calculate_suzhan_analysis(**kwargs, textual_pada=1)
    fourth = calculate_suzhan_analysis(**kwargs, textual_pada=4)
    assert (
        first["astronomy"] == fourth["astronomy"] and first["chart"] == fourth["chart"]
    )
    for key in ("calendar", "personal_day", "activity_assessment"):
        assert first["sukuyo"][key] == fourth["sukuyo"][key]
    assert first["sukuyo"]["palace_reference"]["textual_pada"] == 1
    assert fourth["sukuyo"]["palace_reference"]["textual_pada"] == 4
    args = dict(person1_date="1990-06-15", person2_date="1992-03-20")
    pair = calculate_sukuyo_compatibility(**args)
    query = calculate_sukuyo_compatibility(
        **args, person1_textual_pada=1, person2_textual_pada=4
    )
    for key in ("pair", "person1_to_person2", "person2_to_person1", "status"):
        assert pair[key] == query[key]


def test_known_civil_clocks_and_natal_parameter_do_not_determine_padas():
    for clock in ("00:00:00", "06:00:00", "12:00:00", "23:59:59"):
        r = day_evidence(
            calendar_mansion("2025-03-04", clock, "+08:00"), natal_mansion="翼"
        )
        ref = r["palace_reference"]
        assert ref["mansion"] == "毕" and ref["textual_pada"] is None
        assert not ref["birth_pada_established"] and not ref["applied_to_modern_chart"]
        assert "未确定个人本命宫" in r["reading_text"]
