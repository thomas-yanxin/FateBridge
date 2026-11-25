"""Nested periods retain original cycles and the actual candidate birth context."""

import copy
from datetime import datetime, timedelta, timezone
from fractions import Fraction

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
from tests.support.transports import AS_OF, SPECS, business
from tests.support.transports import rest as rest
from tests.support.transports import surface_calls as surface_calls
from tests.support.transports import three_surfaces
from tests.support.vimshottari import (
    DAY_MICROSECONDS,
    LORD_YEARS,
    YEAR_DAYS,
    quantize_microseconds,
    reference_periods,
)


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
        elapsed = target - (birth + timedelta(seconds=offset))
        target_microseconds = (
            elapsed.days * DAY_MICROSECONDS
            + elapsed.seconds * 1_000_000
            + elapsed.microseconds
        )
        _, reference_chain = reference_periods(
            Fraction(raw["longitudes"]["Moon"]),
            target_microseconds,
            "sidereal_365_25636",
            6,
        )
        assert [row["lord"] for row in period["subdivisions"]["current_levels"]] == [
            row.lord_chain[-1] for row in reference_chain
        ]
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


@pytest.mark.parametrize("year_basis", YEAR_DAYS)
@pytest.mark.parametrize("depth", [2, 6])
@pytest.mark.parametrize("case", ["original_integration", "rao50_clock"])
def test_complete_timeline_and_target_chain_across_real_surfaces(
    year_basis, depth, case, tmp_path, monkeypatch, capsys
):
    payload = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
        analysis_year=2001,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="UTC",
        divisions=[],
        year_basis=year_basis,
        dasha_depth=depth,
    )
    if case == "rao50_clock":
        payload.update(
            birth_month=4,
            birth_day=28,
            birth_hour=5,
            birth_minute=50,
            birth_timezone="-04:00",
            analysis_year=2000,
            analysis_month=4,
            analysis_day=28,
            analysis_hour=9,
            analysis_minute=50,
        )
    else:
        pass
    body = three_surfaces(
        SPECS["astro_vimshottari"],
        payload,
        ["person_info.utc_datetime", "analysis_context", "vimshottari"],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    birth = datetime.fromisoformat(body["person_info"]["utc_datetime"])
    analysis = datetime.fromisoformat(body["analysis_context"]["analysis_datetime"])
    elapsed = analysis - birth
    target_microseconds = (
        elapsed.days * DAY_MICROSECONDS
        + elapsed.seconds * 1_000_000
        + elapsed.microseconds
    )
    result = body["vimshottari"]
    moon_degrees = result["seed"]["moon_longitude"]
    timeline, current = reference_periods(
        Fraction(moon_degrees), target_microseconds, year_basis, depth
    )
    assert len(result["timeline"]) == 9
    assert sum(len(period["antardashas"]) for period in result["timeline"]) == 81
    for major, expected in zip(result["timeline"], timeline[:9], strict=True):
        assert major["lord"] == expected.lord_chain[-1]
        assert (major["start"], major["end"]) == expected.clocks(birth)
    subperiods = [sub for major in result["timeline"] for sub in major["antardashas"]]
    for sub, expected in zip(subperiods, timeline[9:], strict=True):
        assert [sub["major_lord"], sub["lord"]] == list(expected.lord_chain)
        assert (sub["start"], sub["end"]) == expected.clocks(birth)
    for actual, expected in zip(
        [result["current_major"], result["current_sub"]], current[:2], strict=True
    ):
        assert actual["lord"] == expected.lord_chain[-1]
        assert (actual["start"], actual["end"]) == expected.clocks(birth)
    if depth > 2:
        subdivisions = result["subdivisions"]
        assert len(subdivisions["current_levels"]) == depth
        assert len(subdivisions["siblings_by_level"]) == depth - 1
        assert all(
            len(group["periods"]) == 9 for group in subdivisions["siblings_by_level"]
        )
        for actual, expected in zip(
            subdivisions["current_levels"], current, strict=True
        ):
            assert actual["lord_chain"] == list(expected.lord_chain)
            assert (actual["start"], actual["end"]) == expected.clocks(birth)
    else:
        assert "subdivisions" not in result
    if case == "rao50_clock":
        assert birth.isoformat() == "2000-04-28T09:50:00+00:00"
        assert (result["seed"]["name"], result["seed"]["pada"]) == ("Dhanishta", 3)
        assert abs(moon_degrees - float(Fraction(18143, 60))) < 1 / 60
    else:
        pass
    _, mansion_fraction = divmod(Fraction(moon_degrees) * 3 / 40, 1)
    first_major = result["birth_balance"]["lord"]
    years = next(years for lord, years in LORD_YEARS if lord == first_major)
    exact_elapsed_microseconds = (
        mansion_fraction * years * YEAR_DAYS[year_basis] * DAY_MICROSECONDS
    )
    assert result["birth_balance"]["remaining_microseconds"] == (
        int(years * YEAR_DAYS[year_basis] * DAY_MICROSECONDS)
        - quantize_microseconds(exact_elapsed_microseconds)
    )


@pytest.mark.parametrize("depth", [6, 7])
def test_full_response_and_invalid_depth_across_real_surfaces(surface_calls, depth):
    options = dict(include_snapshot_text=False, response_char_limit=0)
    response, protocol, code, local = surface_calls(
        SPECS["astro_vimshottari"],
        {
            **astro_payload(),
            "analysis_year": 2001,
            "divisions": [],
            "dasha_depth": depth,
        },
        params={"as_of": AS_OF, **options},
        options=options,
        flags=["--no-include-snapshot-text", "--response-char-limit", "0"],
    )
    if depth == 6:
        assert response.status_code == 200
        assert not protocol.is_error
        assert code == 0
        assert (
            business(response.json())
            == business(protocol.structured_content)
            == business(local)
        )
        assert len(local["vimshottari"]["subdivisions"]["current_levels"]) == 6
        source = next(
            source
            for source in local["india"]["rulesets"]
            if source["id"] == "pvr_2000_recursive_dasha_1cafa828"
        )
        assert source["sections"] == [
            "16.1 names printed209/PDF221",
            "16.2 Table38 printed210/PDF222; Example50 printed211/PDF223",
            "16.3 printed212/PDF224",
        ]
    else:
        assert response.status_code == 422
        assert protocol.is_error
        assert code != 0
