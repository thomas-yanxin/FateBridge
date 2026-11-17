"""A derived Lichun uses the same solver and source guards as its full year."""

import pytest

from fatebridge.core import almanac
from fatebridge.core.canping_solar import projection_boundary
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def empty_ephemeris(monkeypatch, tmp_path):
    original = configured_ephemeris_path()
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        with monkeypatch.context() as environment:
            environment.setenv("SE_EPHE_PATH", str(tmp_path))
            environment.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            environment.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
            yield
    finally:
        # The environment must be restored first: Swiss's nonempty SE_EPHE_PATH
        # overrides the explicit original path and would leak this deleted temp dir.
        configure_ephemeris_path(original)
        almanac.get_solar_terms_for_year.cache_clear()


@pytest.mark.parametrize("mode", ["auto", "de440", "analytic", "native"])
@pytest.mark.parametrize(
    "year,context_year,zone",
    [(2000, 2000, "UTC"), (1799, 1800, "+14:00"), (2201, 2200, "-12:00")],
)
def test_single_lichun_preserves_every_full_year_field(
    empty_ephemeris, monkeypatch, mode, year, context_year, zone
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    full = almanac._solar_terms_for_context_year(year, zone, context_year)
    assert len(full) == 24 and full[2].name == "立春"
    single = almanac._solar_terms_for_context_year(
        year, zone, context_year, term_index=2
    )
    assert len(single) == 1
    assert single[0].as_dict() == full[2].as_dict()
    assert almanac.is_calculated_solar_term(single[0])
    cache_hits = almanac.get_solar_terms_for_year.cache_info().hits
    assert almanac._solar_terms_for_context_year(year, zone, context_year) == full
    assert almanac.get_solar_terms_for_year.cache_info().hits == cache_hits + 1


def test_canping_solves_one_crossing_and_keeps_full_year_cache_separate(
    empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    original = almanac._solar_term_utc_via_analytic
    observed = []

    def measured(year, index, *args, **kwargs):
        observed.append((year, index))
        return original(year, index, *args, **kwargs)

    monkeypatch.setattr(almanac, "_solar_term_utc_via_analytic", measured)
    full = almanac.get_solar_terms_for_year(2001, "UTC")
    assert observed == [(2001, index) for index in range(24)]
    almanac.get_solar_terms_for_year.cache_clear()
    observed.clear()
    args = dict(origin_civil_year=2000, origin_bazi_year=2000, horizon=120)
    selected = projection_boundary(2001, "UTC", **args)
    assert observed == [(2001, 2)]
    assert selected["record"] == full[2].as_dict()
    assert projection_boundary(2001, "UTC", **args) == selected
    assert observed == [(2001, 2)]
    repeated_full = almanac.get_solar_terms_for_year(2001, "UTC")
    assert len(repeated_full) == 24
    assert repeated_full[2].as_dict() == selected["record"]
    assert observed[1:] == [(2001, index) for index in range(24)]


@pytest.mark.parametrize(
    "year,context_year", [(1799, 1799), (1798, 1800), (2201, 2201)]
)
def test_selector_does_not_expand_analytic_public_or_context_bounds(
    empty_ephemeris, monkeypatch, year, context_year
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    with pytest.raises(ValueError):
        almanac._solar_terms_for_context_year(year, "UTC", context_year, term_index=2)


def test_selector_cannot_substitute_for_required_swiss_files(
    empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "swiss")
    with pytest.raises(EphemerisSourceError) as failure:
        almanac._solar_terms_for_context_year(2000, "UTC", 2000, term_index=2)
    assert failure.value.reason == "solar_swiss_files_required"
