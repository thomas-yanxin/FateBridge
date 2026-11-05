"""Literal seven-change pairs, directed element facts and regional-clock failures."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from dateutil.tz import gettz
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui import calendar
from fatebridge.core.fengshui.bazhai import sectors
from fatebridge.core.fengshui.bazhai_interpretation import palace_star_relationship
from fatebridge.core.fengshui.method_details import method_details
from fatebridge.core.fengshui.models import AnnualRequest, HousePeriod, MingguaRequest
from fatebridge.services.fengshui import (
    assess,
    calculate_annual_stars,
    calculate_bazhai,
    calculate_minggua,
)
from fatebridge.utils.timezones import parse_timezone_name
from fatebridge.validation.fengshui import audit_bazhai_depth
from tests.fixtures.fengshui import payload
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport

FOLDER = Path(__file__).parent / "data/fengshui_classical_v2"
CHANGES = json.loads((FOLDER / "you-nian-origin.json").read_text())
ELEMENTS = json.loads((FOLDER / "elements.json").read_text())
TRIGRAM_DIRECTIONS = dict(zip("乾坎艮震巽离坤兑", "NW N NE E SE S SW W".split()))


def test_complete_depth_source_audit_and_new_counterexample_detection():
    result = audit_bazhai_depth(CHANGES, ELEMENTS)
    assert result["scoped_acceptance_passed"]
    assert result["checked_transformation_pairs"] == 56
    assert result["checked_directed_element_pairs"] == 25
    assert result["checked_star_elements"] == 8
    assert not result["whole_book_conformity_established"]
    changed = deepcopy(ELEMENTS)
    changed["palace_by_star_labels"][0][1] = "星生宫"
    failed = audit_bazhai_depth(CHANGES, changed)
    assert not failed["scoped_acceptance_passed"]
    assert len(failed["disagreements"]) == 1


def test_incomplete_or_duplicate_classical_source_cannot_manufacture_a_pass():
    changed = deepcopy(CHANGES)
    changed["cases"][0] = changed["cases"][1]
    with pytest.raises(ValueError, match="56"):
        audit_bazhai_depth(changed, ELEMENTS)
    partial = deepcopy(ELEMENTS)
    partial["palace_by_star_labels"].pop()
    with pytest.raises(ValueError, match="five-by-five"):
        audit_bazhai_depth(CHANGES, partial)


@pytest.mark.parametrize("case", CHANGES["cases"])
def test_each_literal_classical_change_matches_computed_trace(case):
    assert len(CHANGES["cases"]) == 56
    chart = sectors(case["base"], "literal-reference", "source")
    entry = chart[TRIGRAM_DIRECTIONS[case["target"]]]
    trace = entry["you_nian_trace"]
    assert entry["star"]["name"] == case["star_name"]
    assert trace["operation_count"] == case["operation_count"]
    assert trace["operation_count"] == len(trace["cumulative_flip_sequence"])
    assert trace["changed_line_mask"] == entry["changed_line_mask"]
    assert trace["net_changed_line_count"] == len(trace["net_changed_lines"])


@pytest.mark.parametrize("base", list(TRIGRAM_DIRECTIONS))
def test_unchanged_trigram_is_zero_operations_and_not_a_missing_step(base):
    entry = sectors(base, "test", "source")[TRIGRAM_DIRECTIONS[base]]
    assert entry["star"]["name"] == "伏位"
    assert entry["you_nian_trace"]["operation_count"] == 0
    assert entry["you_nian_trace"]["cumulative_flip_sequence"] == []
    assert entry["you_nian_trace"]["net_changed_lines"] == []


def test_seven_operations_are_not_seven_distinct_changed_lines_or_years():
    entry = sectors("乾", "test", "source")["S"]
    trace = entry["you_nian_trace"]
    assert entry["star"]["name"] == "绝命"
    assert trace["operation_count"] == 7
    assert trace["cumulative_flip_sequence"] == [3, 2, 1, 2, 3, 2, 1]
    assert trace["net_changed_lines"] == [2]
    assert trace["net_changed_line_count"] == 1
    assert "not_elapsed_years" in trace["scope"]


@pytest.mark.parametrize("row", range(5))
@pytest.mark.parametrize("column", range(5))
def test_all_directed_palace_star_relations_against_literal_five_by_five_matrix(
    row, column
):
    palace, star = ELEMENTS["elements"][row], ELEMENTS["elements"][column]
    actual = palace_star_relationship(palace, "source-test", star)
    assert actual["traditional_label"] == ELEMENTS["palace_by_star_labels"][row][column]
    assert actual["palace_element"] == palace and actual["star_element"] == star


def test_every_bazhai_chart_preserves_source_elements_and_fuwei_context_variation():
    for base in TRIGRAM_DIRECTIONS:
        for entry in sectors(base, "test", "source").values():
            star = entry["star"]
            relation = entry["palace_star_relationship"]
            assert star["element"] == ELEMENTS["selected_star_elements"][star["name"]]
            assert relation["star_element"] == star["element"]
            if star["name"] == "伏位":
                context = relation["source_context_variation"]
                assert context["other_clause"] == ELEMENTS["fuwei_alternative_clause"]
                assert not context["other_context_applied"]
                assert context["selected_source_ids"] == ["S10"]


def test_element_relation_does_not_silently_override_basic_purpose_convention():
    result = calculate_bazhai(
        house={"sitting_trigram": "坎"},
        placements=[{"object_id": "bed", "purpose": "bed", "location_direction": "E"}],
    )
    finding = result["layers"]["bazhai"]["placement_findings"][0]
    # 坎宅震宫 is 天医土: a basic auspicious star, yet palace wood controls it.
    assert finding["star"]["name"] == "天医"
    assert finding["matches_convention"]
    assert finding["palace_star_relationship"]["traditional_label"] == "宫克星"
    assert (
        finding["matches_convention_scope"]
        == "basic_star_polarity_only_not_element_or_whole_house_verdict"
    )
    assert "宫克星" in result["snapshot_text"]


def test_method_reference_and_actual_chart_agree_on_selected_fuwei_context():
    reference = method_details(["bazhai"])
    fuwei = reference["bazhai_you_nian_references"]["伏位"]
    actual = sectors("坎", "test", "source")["N"]["palace_star_relationship"]
    assert fuwei["element"] == actual["star_element"] == "木"
    assert (
        fuwei["source_context_variation"]["other_clause"]
        == actual["source_context_variation"]["other_clause"]
    )
    registered = {source["source_id"] for source in reference["ruleset"]["sources"]}
    assert {"FOUNDATION_S10", "FOUNDATION_S12"} <= registered


@pytest.mark.parametrize("factory", [gettz, ZoneInfo])
@pytest.mark.parametrize(
    "model,field",
    [
        (AnnualRequest, "query_at"),
        (MingguaRequest, "birth_at"),
        (HousePeriod, "event_at"),
    ],
)
def test_native_regional_gap_is_rejected_before_any_calendar_computation(
    factory, model, field
):
    at = datetime(2026, 3, 8, 2, 30, tzinfo=factory("America/New_York"))
    extra = (
        {"basis": "first_occupancy", "evidence": "Known historical event"}
        if model is HousePeriod
        else {}
    )
    with pytest.raises(ValidationError, match="nonexistent"):
        model.model_validate({field: at, "timezone_name": "America/New_York", **extra})


@pytest.mark.parametrize("factory", [gettz, ZoneInfo])
@pytest.mark.parametrize("fold", [0, 1])
@pytest.mark.parametrize(
    "model,field",
    [
        (AnnualRequest, "query_at"),
        (MingguaRequest, "birth_at"),
        (HousePeriod, "event_at"),
    ],
)
def test_aware_fold_selection_is_preserved_instead_of_discarded(
    factory, fold, model, field
):
    at = datetime(2026, 11, 1, 1, 30, tzinfo=factory("America/New_York"), fold=fold)
    extra = (
        {
            "basis": "first_occupancy",
            "evidence": "Explicitly selected repeated-hour instant",
        }
        if model is HousePeriod
        else {}
    )
    parsed = model.model_validate(
        {field: at, "timezone_name": "America/New_York", **extra}
    )
    assert getattr(parsed, field).isoformat() == at.isoformat()
    assert getattr(parsed, field).fold == fold
    result = calculate_annual_stars(query_at=at, timezone_name="America/New_York")
    wire = calculate_annual_stars(
        query_at=at.isoformat(), timezone_name="America/New_York"
    )
    assert result == wire


def test_year_boundary_compares_instants_even_when_wall_clock_order_is_reversed(
    monkeypatch,
):
    # Synthetic transition-aligned boundary tests datetime semantics only.
    # It is deliberately not an astronomical Li Chun reference or calendar claim.
    def terms(year, zone):
        return [
            SimpleNamespace(
                name="立春",
                moment=datetime(
                    year, 11, 1, 1, 30, tzinfo=parse_timezone_name(zone), fold=1
                ),
                resolution_provider="swisseph",
            )
        ]

    monkeypatch.setattr(calendar.almanac, "get_solar_terms_for_year", terms)
    before = datetime(
        2026, 11, 1, 1, 45, tzinfo=parse_timezone_name("America/New_York"), fold=0
    )
    after = before.replace(fold=1)
    assert (
        calendar.year_context(None, before, "America/New_York")["effective_year"]
        == 2025
    )
    assert (
        calendar.year_context(None, after, "America/New_York")["effective_year"] == 2026
    )


def test_aggregate_cannot_bypass_invalid_query_or_occupant_clock():
    at = datetime(2026, 3, 8, 2, 30, tzinfo=parse_timezone_name("America/New_York"))
    with pytest.raises(ValidationError, match="nonexistent"):
        assess(methods=["annual_stars"], query_at=at, timezone_name="America/New_York")
    with pytest.raises(ValidationError, match="nonexistent"):
        assess(methods=["bazhai"], occupants=[{"subject_id": "a", "birth_at": at}])


def test_explicit_iso_instants_remain_accepted_and_normalize_to_real_local_clock():
    for at in (
        "2026-03-08T02:30:00-04:00",
        "2026-11-01T01:30:00-04:00",
        "2026-11-01T01:30:00-05:00",
    ):
        annual = calculate_annual_stars(query_at=at, timezone_name="America/New_York")[
            "layers"
        ]["annual_stars"]["time_context"]
        birth = calculate_minggua(
            birth_at=at, timezone_name="America/New_York", gender_convention="female"
        )["layers"]["minggua"]["time_context"]
        assert annual["local_moment"] == birth["local_moment"]
        assert annual["effective_year"] == 2026
    assert (
        calculate_annual_stars(
            query_at="2026-03-08T02:30:00-04:00", timezone_name="America/New_York"
        )["layers"]["annual_stars"]["time_context"]["local_moment"]
        == "2026-03-08T01:30:00-05:00"
    )


@pytest.mark.parametrize("name", ["bazhai", "minggua", "assess", "annual_stars"])
def test_deep_bazhai_facts_and_explicit_clock_instants_match_all_transports(
    monkeypatch, tmp_path, capsys, name
):
    request = payload(name)
    if name == "annual_stars":
        request = {
            "query_at": "2026-03-08T02:30:00-04:00",
            "timezone_name": "America/New_York",
        }
    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=request)
    protocol = asyncio.run(mcp_call(name, request))
    path = tmp_path / "deep.json"
    path.write_text(json.dumps(request))
    assert run(["fengshui_" + name, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    if name in {"bazhai", "minggua"}:
        assert "palace_star_relationship" in http.text
        assert "you_nian_trace" in http.text
