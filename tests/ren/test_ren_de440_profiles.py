"""Ren validates the actual admitted DE440 profile, without moving its root."""

import copy
from dataclasses import replace

import pytest

from fatebridge.core import almanac, de440_solar
from fatebridge.core.astro.time_scales import datetime_from_tt_point
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.metaphysics import ren_calendar
from fatebridge.core.output_chinese import RenTermDependency
from fatebridge.services.metaphysics import _build_analysis_seed
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.ren_de440_profile_reference import reference
from tests.support.transports import SPECS, business, rest, surface_calls


@pytest.fixture(autouse=True)
def model_selection(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("year", [1700, 1799, 1800, 2200, 2201, 2300])
def test_all24_actual_terms_are_accepted_in_both_public_modes(mode, year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    expected = (
        de440_solar.MODEL_ID if 1800 <= year <= 2200 else de440_solar.EXTENDED_MODEL_ID
    )
    for term in almanac.get_solar_terms_for_year(year, "UTC"):
        assert term.ephemeris_model == expected
        ren_calendar.require_ren_solar_term(term)
        RenTermDependency.model_validate(
            dict(
                name=term.name,
                provider=term.resolution_provider,
                ephemeris_model=term.ephemeris_model,
                ephemeris_retflags=[],
                ephemeris_library_version=term.ephemeris_library_version,
                solar_model_details=term.solar_model_details,
                civil_moment=term.moment.isoformat(),
            )
        )


@pytest.mark.parametrize("year", [1700, 1799, 1800, 2200, 2201, 2300])
def test_all_declared_independent_sample_points_keep_original_one_second_gate(year):
    refs = [r for r in reference()["rows"] if r["year"] == year]
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(refs) == 24
    for row in refs:
        assert (
            abs(
                (
                    terms[row["index"]].solar_model_details["selected_crossing_jd_tt"]
                    - row["jd_tt"]
                )
                * 86400
            )
            <= 1
        )


@pytest.mark.parametrize("year", [1700, 2000, 2300])
def test_longitude_reobservation_uses_actual_profile_for_both_endpoints(
    year, monkeypatch
):
    term = almanac.get_solar_terms_for_year(year, "UTC")[0]
    observed = []
    original = de440_solar.solar_longitude_parts

    def spy(*parts, profile_id=de440_solar.MODEL_ID):
        observed.append(profile_id)
        return original(*parts, profile_id=profile_id)

    monkeypatch.setattr(de440_solar, "solar_longitude_parts", spy)
    ren_calendar.require_ren_solar_term(term)
    assert observed == [term.ephemeris_model, term.ephemeris_model]


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("coefficient_sha256", "0" * 64),
        ("source_kernel_sha256", "0" * 64),
        ("accuracy_certified", True),
        ("model_id", de440_solar.MODEL_ID),
        ("public_auto_and_de440_input_years", [1, 9999]),
        ("native_moshier_relabelled", True),
    ],
)
def test_extended_receipt_still_rejects_corrupt_or_relabelled_source(field, wrong):
    term = almanac.get_solar_terms_for_year(1700, "UTC")[0]
    details = copy.deepcopy(term.solar_model_details)
    details[field] = wrong
    expected_error = RuntimeError if field == "model_id" else EphemerisSourceError
    with pytest.raises(expected_error):
        ren_calendar.require_ren_solar_term(replace(term, solar_model_details=details))


@pytest.mark.parametrize(
    "model", [de440_solar.HISTORICAL_MODEL_ID, de440_solar.CANPING_MODEL_ID, "invented"]
)
def test_private_profiles_are_not_admitted_as_public_year_grid_models(model):
    term = almanac.get_solar_terms_for_year(1700, "UTC")[0]
    with pytest.raises((RuntimeError, EphemerisSourceError)):
        ren_calendar.require_ren_solar_term(replace(term, ephemeris_model=model))


def test_coherent_tt_receipt_is_not_enough_for_wrong_extended_crossing():
    term = almanac.get_solar_terms_for_year(1700, "UTC")[0]
    details = copy.deepcopy(term.solar_model_details)
    details["selected_crossing_jd_tt"] += 1
    details["selected_crossing_tt_parts"][0] += 1
    details["root_bracket_tt"] = [v + 1 for v in details["root_bracket_tt"]]
    for p in details["root_bracket_tt_parts"]:
        p[0] += 1
    bad = replace(
        term,
        solar_model_details=details,
        moment=datetime_from_tt_point(
            TTInstant.from_parts(*details["selected_crossing_tt_parts"])
        ),
    )
    from fatebridge.core.metaphysics.ren_term_point import validate_term_point

    validate_term_point(details, bad.moment, complete=True)
    with pytest.raises(EphemerisSourceError) as e:
        ren_calendar.require_ren_solar_term(bad)
    assert e.value.reason == "ren_solar_term_longitude_inconsistent"


@pytest.mark.parametrize(
    "year,month,day,expected",
    [
        (1700, 12, 31, {de440_solar.EXTENDED_MODEL_ID}),
        (1799, 12, 31, {de440_solar.MODEL_ID, de440_solar.EXTENDED_MODEL_ID}),
        (2200, 12, 31, {de440_solar.MODEL_ID}),
        (2201, 1, 1, {de440_solar.MODEL_ID, de440_solar.EXTENDED_MODEL_ID}),
        (2300, 12, 31, {de440_solar.EXTENDED_MODEL_ID}),
    ],
)
def test_actual_dependencies_keep_selected_and_mixed_profile_identities(
    year, month, day, expected
):
    seed = _build_analysis_seed(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="UTC",
        use_true_solar_time=False,
    )
    policy = ren_calendar.require_ren_calendar(seed)
    assert {d["ephemeris_model"] for d in policy["solar_term_dependencies"]} == expected
    assert (
        policy["solar_longitude_definition"]["astronomical_model"]
        == "per_dependency_named_models"
    )
    assert "DE440" in policy["solar_longitude_definition"]["source_section"]


@pytest.mark.parametrize("year", [1700, 2300])
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_extended_full_request_reaches_rest_mcp_cli_with_actual_source(
    year, key, surface_calls
):
    payload = dict(
        analysis_year=year,
        analysis_month=6,
        analysis_day=15,
        analysis_hour=12,
        analysis_timezone="UTC",
        use_true_solar_time=False,
        is_diurnal=True,
    )
    if key == "jinkou":
        payload["di_fen"] = "酉"
    s = SPECS[key]
    fields = ["four_pillars", "liureng.calendar_policy", "liureng.meta"]
    options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    h, m, ccode, c = surface_calls(
        s, payload, projection={**options, "response_char_limit": 0}
    )
    assert h.status_code == 200 and ccode == 0 and not m.is_error
    assert business(h.json()) == business(c) == business(m.structured_content)
    deps = h.json()["liureng"]["calendar_policy"]["solar_term_dependencies"]
    assert {d["ephemeris_model"] for d in deps} == {de440_solar.EXTENDED_MODEL_ID}
    assert all(d["solar_model_details"]["accuracy_certified"] is False for d in deps)
