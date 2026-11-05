"""Nested periods retain original cycles and the actual candidate birth context."""

import copy
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import jyotish
from fatebridge.core.jyotish_dasha_grid import DashaGrid
from fatebridge.core.jyotish_dasha_levels import (
    ORDER,
    RULE,
    SOURCE,
    YEAR_MICROSECONDS,
    YEARS,
)
from fatebridge.core.output_jyotish import Vimshottari
from fatebridge.core.requests.astrology import AstroVimshottariRequest
from fatebridge.services.jyotish import calculate_vimshottari
from tests.fixtures.surface_payloads import astro_payload


@pytest.mark.parametrize("basis", YEAR_MICROSECONDS)
@pytest.mark.parametrize("target_year", [2001, 2026, 2250])
def test_complete_cycle_and_original_boundaries_do_not_change(basis, target_year):
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    target = datetime(target_year, 1, 1, tzinfo=timezone.utc)
    legacy = jyotish.vimshottari(birth, 123.456, target, year_basis=basis)
    assert legacy == jyotish.vimshottari(
        birth, 123.456, target, year_basis=basis, dasha_depth=2
    )
    assert "subdivisions" not in legacy
    assert list(ORDER) == jyotish.DASHA_ORDER
    assert YEARS == jyotish.DASHA_YEARS
    assert YEAR_MICROSECONDS[basis] == round(jyotish.YEAR_DAYS[basis] * 86400000000)
    for depth in range(3, 7):
        deeper = jyotish.vimshottari(
            birth, 123.456, target, year_basis=basis, dasha_depth=depth
        )
        nested = deeper.pop("subdivisions")
        assert deeper.pop("rule_ids") == [*legacy["rule_ids"], RULE]
        assert {k: v for k, v in deeper.items()} == {
            k: v for k, v in legacy.items() if k != "rule_ids"
        }
        assert nested["depth"] == depth
        assert len(nested["current_levels"]) == depth
        assert len(nested["siblings_by_level"]) == depth - 1
        assert all(len(g["periods"]) == 9 for g in nested["siblings_by_level"])
        for old, new in zip(
            [legacy["current_major"], legacy["current_sub"]],
            nested["current_levels"][:2],
        ):
            assert all(old[k] == new[k] for k in ["lord", "start", "end"])


@pytest.mark.parametrize("depth", [True, False, 1, 7, 2.0, "3"])
def test_request_and_domain_reject_invalid_depth(depth):
    with pytest.raises(ValueError):
        AstroVimshottariRequest.model_validate(
            {**astro_payload(), "dasha_depth": depth}
        )
    with pytest.raises(ValueError):
        jyotish.vimshottari(
            datetime(2000, 1, 1, tzinfo=timezone.utc),
            0,
            datetime(2001, 1, 1, tzinfo=timezone.utc),
            dasha_depth=depth,
        )


@pytest.mark.native_engine_fault
def test_all_selected_levels_use_own_complete_grid_and_natal_context(monkeypatch):
    # Observe real native calls in this process; worker transport is tested separately.
    observed = []
    original = DashaGrid.observe

    def recording(self, offset, raw):
        observed.append((offset, copy.deepcopy(raw)))
        return original(self, offset, raw)

    monkeypatch.setattr(DashaGrid, "observe", recording)
    payload = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    result = calculate_vimshottari(
        **payload,
        analysis_year=2001,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=12,
        divisions=[9, 30],
        birth_time_uncertainty_minutes=1,
        dasha_depth=6,
    )
    vim = result["vimshottari"]
    sensitivity = vim["birth_time_sensitivity"]
    assert (
        len(observed)
        == sensitivity["requested_sample_count"]
        == sensitivity["evaluated_sample_count"]
        == 5
    )
    assert sensitivity["requested_dasha_depth"] == 6
    assert sum(v["sample_count"] for v in sensitivity["stage_variants"]) == 5
    expected = {}
    roles = ("major", "sub", "pratyantar", "sookshma", "prana", "deha")
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    target = datetime(2001, 1, 1, 12, tzinfo=timezone.utc)
    for index, (offset, raw) in enumerate(observed):
        period = jyotish.vimshottari(
            birth + timedelta(seconds=offset),
            raw["longitudes"]["Moon"],
            target,
            dasha_depth=6,
        )
        expected[index] = period
    for variant in sensitivity["stage_variants"]:
        indices = [
            i
            for s in variant["sample_segments"]
            for i in range(s["first_grid_index"], s["last_grid_index"] + 1)
        ]
        assert len(indices) == variant["sample_count"]
        for index in indices:
            chain = [
                r["lord"] for r in expected[index]["subdivisions"]["current_levels"]
            ]
            assert variant["period_lord_chain"] == chain
            for context in variant["natal_ruler_contexts"]:
                own_indices = [
                    i
                    for s in context["sample_segments"]
                    for i in range(s["first_grid_index"], s["last_grid_index"] + 1)
                ]
                if index not in own_indices:
                    continue
                chart = jyotish.divisional_chart(
                    observed[index][1], int(context["chart"][1:])
                )
                planet = next(
                    p for p in chart["planets"] if p["id"] == context["planet_id"]
                )
                assert (context["sign"], context["house"]) == (
                    planet["sign"],
                    planet["house"],
                )
                assert context["roles"] == [
                    role for role, lord in zip(roles, chain) if lord == planet["id"]
                ]
        for level in range(2, 6):
            for edge in ("start", "end"):
                values = [
                    expected[i]["subdivisions"]["current_levels"][level][edge]
                    for i in indices
                ]
                assert variant["period_boundary_ranges"][
                    f"subdivisions.current_levels.{level}.{edge}"
                ] == {"minimum": min(values), "maximum": max(values)}
    assert all(
        len(s["subdivisions"]["current_levels"]) == 6 for s in sensitivity["samples"]
    )
    nominal = vim["subdivisions"]["current_levels"]
    assert {r["planet"]["id"] for r in vim["natal_ruler_context"]} == {
        p["lord"] for p in nominal
    }
    for context in vim["natal_ruler_context"]:
        assert context["period_roles"] == [
            p["name"] for p in nominal if p["lord"] == context["planet"]["id"]
        ]
    assert any(r["id"] == SOURCE["id"] for r in result["india"]["rulesets"])
    assert any(r["rule_id"] == RULE for r in result["india"]["rule_trace"])
    typed = Vimshottari.model_validate(vim).model_dump(exclude_unset=True)
    assert typed["subdivisions"] == vim["subdivisions"]
    assert all(f"{p['abbreviation']}=" in result["summary"] for p in nominal)
