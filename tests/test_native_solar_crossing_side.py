"""Native boundaries must be the first representable TT point after crossing.

This checks the declared complete Moshier equation, not physical accuracy.
Independent DE440 gates and retained stock failures are checked separately.
"""

import math
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from fatebridge.core import almanac, moshier_solar, solar_term_clock
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe
from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize("year", [1799, 1800, 2200, 2201])
def test_all_original_native_events_select_the_first_post_crossing_point(
    year, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term, target in zip(terms, almanac.SOLAR_TERM_LONGITUDES, strict=True):
        details = term.solar_model_details
        point = details["selected_crossing_jd_tt"]
        before = math.nextafter(point, -math.inf)
        assert term.resolution_provider == moshier_solar.PROVIDER
        assert term.ephemeris_model == moshier_solar.MODEL_ID
        left = moshier_solar.solar_longitude(before)
        right = moshier_solar.solar_longitude(point)
        assert math.remainder(left - target, 360) < 0, term.name
        assert math.remainder(right - target, 360) >= 0, term.name
        assert details["root_bracket_tt"] == [before, point]
        assert details["root_selection_policy"] == "first_post_crossing_tt_float"
        assert ephemeris_time(term.moment).jd_tt == point
        assert details["accuracy_certified"] is False
        require_ren_solar_term(term)


def test_exact_crossing_at_the_first_scan_sample_is_not_lost(monkeypatch):
    anchor = datetime(2000, 6, 1, tzinfo=timezone.utc)
    root = ephemeris_time(anchor).jd_tt - 30.0

    def linear_sun(operation, point, body, flags):
        assert operation == "calc" and body == swe.SUN
        return ((point - root) % 360, 0, 1, 1, 0, 0), swe.FLG_MOSEPH

    monkeypatch.setattr(almanac, "ephemeris_call", linear_sun)
    monkeypatch.setattr(
        moshier_solar, "solar_longitude", lambda point: (point - root) % 360
    )
    provenance = {}
    moment = almanac._solar_term_utc_via_swe(2000, 0, anchor, provenance)
    assert moment is not None
    assert provenance["resolved_jd_tt"] == root
    assert ephemeris_time(moment).jd_tt == root


def test_new_post_crossing_contract_rejects_a_coherent_pre_crossing_point(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    term = almanac.get_solar_terms_for_year(2026, "UTC")[0]
    details = dict(term.solar_model_details)
    low = details["root_bracket_tt"][0]
    details["selected_crossing_jd_tt"] = low
    bad = replace(
        term,
        moment=solar_term_clock.native_solar_root_datetime(low),
        solar_model_details=details,
    )
    with pytest.raises(EphemerisSourceError) as caught:
        require_ren_solar_term(bad)
    assert caught.value.reason == "ren_solar_term_longitude_inconsistent"

    # A retired model name cannot bypass the current crossing contract.
    historical = dict(details)
    historical["model_id"] = "native_swiss_tt_solar_bisection_v1"
    historical.pop("root_selection_policy")
    with pytest.raises((EphemerisSourceError, RuntimeError)):
        require_ren_solar_term(replace(bad, solar_model_details=historical))
