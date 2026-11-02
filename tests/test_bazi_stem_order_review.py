"""Source-local month/hour candidates never silently become force verdicts."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.output_stem_order_review import StemOrderSourceReview
from fatebridge.core.stem_effects import PAIRS
from fatebridge.core.stem_order_review import (
    build_stem_order_review,
    stem_order_review_snapshot_line,
)
from fatebridge.validation.stem_order_candidate import extend_non_day_links
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
FIXTURE = Path(__file__).parent / "fixtures/bazi_ordered_conditions_v1"
SOURCE = json.loads((FIXTURE / "source-review-first.json").read_text())
KEYS = ["analyze_destiny", "bazi_birth"] + [
    "bazi_" + x
    for x in [
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ]
]


@pytest.mark.parametrize(
    "case", SOURCE["partial_stem_layout_expectations"], ids=lambda c: c["id"]
)
def test_complete_source_local_layouts_use_only_supplied_stems(case):
    from itertools import pairwise

    stems = case["stems"]
    original = [
        (a, b)
        for a, b in pairwise(("year", "month", "day", "hour"))
        if frozenset((stems[a], stems[b])) in PAIRS
    ]
    links = extend_non_day_links(stems, original, PAIRS)
    assert [[a, b] for a, b in links if "day" not in (a, b)] == case[
        "non_day_combination_pairs"
    ]
    review = build_stem_order_review(stems, [], PAIRS)
    assert bool(review["candidates"]) == (case["id"] == "S12")
    assert review["candidate_numeric_policy_adopted"] is False
    assert review["effective_combination"] == "not_adjudicated"


@pytest.mark.parametrize("pair", ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"])
@pytest.mark.parametrize("reverse", [False, True])
def test_all_five_glyph_pairs_keep_unknown_empty_and_actual_events_separate(
    pair, reverse
):
    left, right = pair[::-1] if reverse else pair
    stems = {"year": "甲", "month": left, "day": "丙", "hour": right}
    unknown = build_stem_order_review(stems, None, PAIRS)
    empty = build_stem_order_review(stems, [], PAIRS)
    supplied = build_stem_order_review(
        stems,
        [
            {"kind": "六合", "positions": ["month", "hour"]},
            {
                "kind": "天干合",
                "positions": ["month", "hour"],
                "status": "day_master_or_contested_review",
            },
        ],
        PAIRS,
    )
    assert unknown["unrecorded_source_candidate_count"] is None
    assert unknown["candidates"][0]["recorded_relation_refs"] is None
    assert empty["unrecorded_source_candidate_count"] == 1
    assert supplied["unrecorded_source_candidate_count"] == 0
    assert supplied["candidates"][0]["recorded_relation_refs"] == [
        "assessment.relations:1"
    ]
    for value in (unknown, empty, supplied):
        StemOrderSourceReview.model_validate(value)
        assert value["candidates"][0]["stems"] == [left, right]
        assert value["calculation_effect"] == "none"


def test_day_and_year_partner_observations_do_not_choose_a_binding_winner():
    review = build_stem_order_review(
        {"year": "甲", "month": "己", "day": "甲", "hour": "甲"}, [], PAIRS
    )
    assert review["candidates"][0]["other_matching_stem_positions"] == ["year", "day"]
    assert review["candidates"][0]["effective_combination"] == "not_adjudicated"
    assert "月时己甲" in stem_order_review_snapshot_line(review)


def test_contradictory_full_review_rejected_and_partial_does_not_invent_missing_events():
    value = build_stem_order_review(
        {"year": "甲", "month": "癸", "day": "丙", "hour": "戊"}, [], PAIRS
    )
    value["unrecorded_source_candidate_count"] = 0
    with pytest.raises(ValidationError, match="未记录数"):
        StemOrderSourceReview.model_validate(value)
    partial = {"candidates": [{"stems": ["癸", "戊"]}]}
    assert (
        StemOrderSourceReview.model_validate(partial).model_dump(exclude_none=True)
        == partial
    )


@pytest.mark.parametrize("key", KEYS)
def test_published_source_order_view_matches_actual_public_transports(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {
        "name": "虚构月时原典关系核对",
        "birth_year": 1993,
        "birth_month": 12,
        "birth_day": 12,
        "birth_hour": 18,
        "birth_minute": 0,
        "birth_second": 0,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
        "gender": "男",
    }
    if key != "analyze_destiny":
        payload.update(analysis_year=2026, analysis_month=10, analysis_day=12)
    fields = suggested_fields(spec, view="stem_order")
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    result = asyncio.run(native(spec, payload, **flags))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    assert not result.is_error and code == 0
    assert business(local) == business(result.structured_content)
    if spec.rest_path:
        response = rest.post(spec.rest_path, json=payload, params=flags)
        assert response.status_code == 200, response.text
        assert business(response.json()) == business(local)
    spec.output_model.model_validate(local)
    accounting = local
    for part in fields[0].split("."):
        accounting = accounting[part]
    review = accounting["source_order_review"]
    assert review["candidates"][0]["stems"] == ["甲", "己"]
    assert review["unrecorded_source_candidate_count"] == 1
    assert review["candidate_numeric_policy_adopted"] is False
    before = copy.deepcopy(local)
    spec.output_model.model_validate(local)
    assert local == before
