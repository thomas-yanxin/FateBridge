"""Declared source-day endpoints, same-sky root brackets and native scopes."""

import copy
import hashlib
import importlib.util
import json
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import guolao
from fatebridge.core import guolao_anchor_days as days
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao import build_chart, reading
from fatebridge.core.guolao_classical import life_branch
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest

FIXTURE = Path(__file__).parent / "fixtures/guolao-anchor-days-v1"


def birth(**updates):
    args = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
        name="虚构安命日界测试",
        use_true_solar_time=True,
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    args.update(updates)
    return build_astro_birth_info(**args)


@pytest.mark.parametrize(
    "start,end,exclusive,inclusive",
    [
        ("269", "270", "卯", "卯"),
        ("269.5", "270.5", "卯", "辰"),
        ("270", "271", "卯", "辰"),
        ("270.001", "271.001", "辰", "辰"),
        ("299.5", "300.5", "辰", "辰"),
        ("300", "301", "辰", "辰"),
        ("300.001", "301.001", "卯", "卯"),
        ("89", "90", "卯", "卯"),
        ("89.5", "90.5", "寅", "寅"),
        ("90", "91", "寅", "寅"),
        ("104.5", "105.5", "寅", "寅"),
        ("105", "106", "寅", "寅"),
        ("105.001", "106.001", "卯", "卯"),
        ("359.5", ".5", "卯", "卯"),
    ],
)
def test_printed_day_endpoints_and_explicit_winter_hypotheses(
    start, end, exclusive, inclusive
):
    assert (
        days.anchor_from_day_longitudes(F(start), F(end), include_winter_day=False)
        == exclusive
    )
    assert (
        days.anchor_from_day_longitudes(F(start), F(end), include_winter_day=True)
        == inclusive
    )


@pytest.mark.parametrize(
    "start,end,winter",
    [
        (F(1), F(1), True),
        (F(1), F(4), True),
        (F(360), F(1), True),
        (1.0, F(2), True),
        (F(1), F(2), 1),
    ],
)
def test_bad_or_implicit_day_edges_rejected(start, end, winter):
    with pytest.raises((TypeError, ValueError)):
        days.anchor_from_day_longitudes(start, end, include_winter_day=winter)


def _linear_evaluator(origin, serial):
    return lambda at: dict(
        julian_day_ut1_exact=str(F(at)),
        apparent_solar_label_serial_exact=str(serial + F(at) - F(origin)),
    )


def test_root_brackets_enclose_an_independent_linear_clock_oracle_without_rounding():
    at = 2451545.1
    serial = F("730120.25")
    roots, grid = days._day_brackets(at, serial, _linear_evaluator(at, serial))
    assert len(grid) == 13 and F(grid[-1]) - F(grid[0]) == 3
    for root, expected in zip(roots, [F(at) - F(1, 4), F(at) + F(3, 4)]):
        lo = F(root["lower"]["julian_day_ut1_exact"])
        hi = F(root["upper"]["julian_day_ut1_exact"])
        assert lo < expected <= hi
        assert F(root["bracket_width_UT1_seconds_exact"]) <= F(1, 1000)


def test_birth_inside_a_numerical_midnight_bracket_errors_instead_of_picking_a_day():
    at = 2451545.0
    serial = F(730120)
    with pytest.raises(ValueError, match="数值日界"):
        days._day_brackets(at, serial, _linear_evaluator(at, serial))


def test_nonmonotonic_full_search_scan_does_not_return_a_local_fitted_root():
    with pytest.raises(ValueError, match="单调"):
        days._day_brackets(
            2451545.0,
            F("730120.5"),
            lambda at: dict(apparent_solar_label_serial_exact=str(-F(at))),
        )


@pytest.mark.parametrize("policy", days.POLICIES[1:])
def test_real_native_day_policy_changes_only_symbolic_mapping_and_keeps_physical_planets(
    policy,
):
    b = birth()
    original = build_chart(b)
    updated = build_chart(b, seasonal_anchor_policy=policy)
    assert original["guolao"]["life_palace"]["branch"] == "辰"
    life = updated["guolao"]["life_palace"]
    evidence = life["seasonal_anchor_evidence"]
    assert life["branch"] == "卯"
    assert life["branch"] == life_branch(
        life["sun_palace_branch"], life["birth_hour_branch"], evidence["anchor_branch"]
    )
    assert updated["guolao"]["profile"]["ruleset_id"] == days.DAY_RULESET
    for key in ["planets", "angles", "houses", "person_info"]:
        assert updated[key] == original[key]
    for key in [
        "julian_day_tt",
        "julian_day_ut1",
        "utc_datetime",
        "apparent_solar_clock",
    ]:
        assert updated["guolao"]["profile"][key] == original["guolao"]["profile"][key]
    assert (
        evidence["actual_sun_model"]
        == updated["guolao"]["profile"]["ephemeris_provenance"]["by_body"]["Sun"][
            "ecliptic_model"
        ]
    )
    for root in evidence["day_edge_brackets"]:
        target = root["target_solar_label_ordinal"]
        assert (
            F(root["lower"]["apparent_solar_label_serial_exact"])
            < target
            <= F(root["upper"]["apparent_solar_label_serial_exact"])
        )
        assert F(root["bracket_width_UT1_seconds_exact"]) <= F(1, 1000)
    assert evidence["physical_time_accuracy_certified"] is False
    assert evidence["historical_local_day_boundary_accepted"] is False
    assert evidence["actual_sunrise_used_for_anchor"] is False
    text = reading(updated)
    assert "真太阳日" in text["interpretation"]["core_identity"]
    assert (
        text["interpretation_evidence"]["core_identity"]["policy_id"]
        == "guolao_calculation_reading_v3"
    )
    assert (
        "guolao.life_palace"
        in text["interpretation_evidence"]["core_identity"]["source_paths"]
    )


@pytest.mark.parametrize(
    "month,day", [(1, 20), (1, 21), (6, 21), (7, 7), (12, 21), (12, 22)]
)
@pytest.mark.parametrize("longitude", [-180.0, 0.0, 116.4, 180.0])
def test_same_physical_birth_and_both_zodiacs_keep_the_same_solar_day_anchor(
    month, day, longitude
):
    b = birth(birth_month=month, birth_day=day, birth_longitude=longitude)
    anchors = []
    for zodiac in [0, 1]:
        result = build_chart(
            b, zodiacal=zodiac, seasonal_anchor_policy=days.POLICIES[1]
        )
        anchors.append(result["guolao"]["life_palace"]["counting_anchor_branch"])
    assert anchors[0] == anchors[1]


def test_explicit_term_instants_keeps_complete_legacy_output():
    b = birth()
    assert build_chart(b) == build_chart(b, seasonal_anchor_policy="term_instants")


@pytest.mark.parametrize("policy", ["other", True, days.POLICIES[1]])
def test_core_scope_and_required_solar_clock_are_checked_before_calculation(policy):
    with pytest.raises(ValueError):
        build_chart(birth(use_true_solar_time=False), seasonal_anchor_policy=policy)


@pytest.mark.parametrize("model", [AstroGuolaoRequest, AstroChartPolyRequest])
def test_request_policy_requires_true_solar_and_alias_scope(model):
    args = dict(
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
        guolao_seasonal_anchor_policy=days.POLICIES[1],
    )
    if model is AstroChartPolyRequest:
        args["chart_variant"] = "guolao_chart"
    with pytest.raises(ValidationError):
        model(**args)
    assert (
        model(**args, use_true_solar_time=True).guolao_seasonal_anchor_policy
        == days.POLICIES[1]
    )
    if model is AstroChartPolyRequest:
        args["chart_variant"] = "chart"
        with pytest.raises(ValidationError):
            model(**args, use_true_solar_time=True)


def test_germany_alias_does_not_forward_guolao_only_policy_to_its_service():
    from fatebridge.services.catalog.astro_bindings import _astro_chart_bind

    request = AstroChartPolyRequest(
        chart_variant="germany",
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
    )
    _, _, kwargs = _astro_chart_bind(request)
    assert "guolao_seasonal_anchor_policy" not in kwargs


def test_backend_change_never_silently_falls_back_to_a_different_solar_day():
    b = birth()
    original = build_chart(b)
    g = original["guolao"]
    model = g["profile"]["ephemeris_provenance"]["by_body"]["Sun"]["ecliptic_model"]
    wrong = "moshier" if model != "moshier" else "jpl"
    with pytest.raises(Exception, match="model|coordinate|ephemeris"):
        days.apparent_solar_day_anchor(
            b,
            birth_clock=g["profile"]["apparent_solar_clock"],
            birth_ut1=g["profile"]["julian_day_ut1"],
            expected_sun_model=wrong,
            birth_sun_source=g["profile"]["longitude_motion"][
                "physical_ephemeris_source"
            ],
            policy=days.POLICIES[1],
        )


def test_birth_source_edition_change_is_not_conflated_with_a_day_policy():
    b = birth()
    original = build_chart(b)
    g = original["guolao"]
    source = copy.deepcopy(
        g["profile"]["longitude_motion"]["physical_ephemeris_source"]
    )
    if not source["files"]:
        source["files"] = [
            {
                "id": "synthetic-unknown",
                "slot": 0,
                "filename": "synthetic.se1",
                "sha256": "synthetic",
                "de_number": 431,
            }
        ]
        source["by_factor"]["Sun"]["file_ids"] = ["synthetic-unknown"]
    else:
        for f in source["files"]:
            f["de_number"] += 1
    with pytest.raises(Exception, match="edition|model|source|ephemeris"):
        days.apparent_solar_day_anchor(
            b,
            birth_clock=g["profile"]["apparent_solar_clock"],
            birth_ut1=g["profile"]["julian_day_ut1"],
            expected_sun_model=g["profile"]["ephemeris_provenance"]["by_body"]["Sun"][
                "ecliptic_model"
            ],
            birth_sun_source=source,
            policy=days.POLICIES[1],
        )
