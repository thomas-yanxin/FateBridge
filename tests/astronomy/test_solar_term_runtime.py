"""Changed numerical environments must not reuse the prior solar boundary.

Synthetic solver instants exercise cache behavior, not celestial accuracy.
Real Swiss return flags are tested separately from the requested flag.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac, analytic_solar, de441_solar, native_solar_source
from fatebridge.core.de441_solar import MODEL_ID, PROVIDER
from fatebridge.core.ephemeris_runtime import (
    bump_ephemeris_generation,
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.civil_time import CivilPoint, UTCCalendar
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def data_environment(monkeypatch, tmp_path):
    # These controls perturb the native solver and its file environment.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    if almanac.swe is None:
        pytest.skip("Swiss package is needed for the environment control")
    else:
        pass
    original = configured_ephemeris_path()
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    folder = tmp_path / "ephe"
    folder.mkdir()
    configure_ephemeris_path(str(folder))
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        yield folder
    finally:
        configure_ephemeris_path(original if original is not None else "")
        almanac.get_solar_terms_for_year.cache_clear()


def install_symbolic_solver(monkeypatch, observation):
    calls = []

    def solve(year, longitude, anchor, provenance=None):
        seconds = observation()
        calls.append((year, longitude, seconds))
        civil = UTCCalendar(
            anchor.ordinal, anchor.microseconds_of_day + seconds * 1_000_000
        )
        if provenance is not None:
            provenance.update(
                ephemeris_model="swieph",
                ephemeris_retflags=(2,),
                ephemeris_library_version="synthetic",
                resolved_civil_point=CivilPoint(civil.julian_day_exact()),
            )
        else:
            pass
        return civil

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    return calls


def test_changing_selected_path_recalculates_without_manual_cache_clear(
    data_environment, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = str(data_environment)
    second = tmp_path / "other"
    second.mkdir()
    calls = install_symbolic_solver(
        monkeypatch, lambda: 1 if configured_ephemeris_path() == first else 8
    )
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    cache_hits = almanac.get_solar_terms_for_year.cache_info().hits
    assert almanac.get_solar_terms_for_year(2026, "UTC") == before
    assert almanac.get_solar_terms_for_year.cache_info().hits == cache_hits + 1
    assert len(calls) == 24
    configure_ephemeris_path(str(second))
    after = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) == 48
    assert all(
        (b.moment - a.moment).total_seconds() == 7 for a, b in zip(before, after)
    )


def test_bumping_ephemeris_generation_invalidates_old_year(
    data_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = {"seconds": 1}
    calls = install_symbolic_solver(monkeypatch, lambda: phase["seconds"])
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) == 24
    # Same generation hits cache without re-running solver.
    assert almanac.get_solar_terms_for_year(2026, "UTC") == before
    assert len(calls) == 24
    phase["seconds"] = 4
    bump_ephemeris_generation()
    installed = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) == 48
    assert (installed[0].moment - before[0].moment).total_seconds() == 3
    phase["seconds"] = 9
    bump_ephemeris_generation()
    replaced = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) == 72
    assert (replaced[0].moment - installed[0].moment).total_seconds() == 5


def test_provider_availability_changes_do_not_reuse_the_other_sources_year(
    data_environment, monkeypatch: pytest.MonkeyPatch
) -> None:

    library = almanac.swe
    monkeypatch.setattr(almanac, "swe", None)
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    assert {t.resolution_provider for t in before} == {"fatebridge_analytic"}
    assert {t.ephemeris_model for t in before} == {analytic_solar.MODEL_ID}
    assert {t.ephemeris_library_version for t in before} == {
        "fatebridge.analytic_solar/1.0.0"
    }
    monkeypatch.setattr(almanac, "swe", library)
    install_symbolic_solver(monkeypatch, lambda: 7)
    after = almanac.get_solar_terms_for_year(2026, "UTC")
    assert {t.resolution_provider for t in after} == {"swisseph"}


def test_transient_solver_failure_does_not_poison_the_same_environment_cache(
    data_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def solve(year, longitude, anchor, provenance=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        else:
            pass
        civil = UTCCalendar(anchor.ordinal, anchor.microseconds_of_day + 7_000_000)
        if provenance is not None:
            provenance.update(
                ephemeris_model="swieph",
                ephemeris_retflags=(2,),
                resolved_civil_point=CivilPoint(civil.julian_day_exact()),
            )
        else:
            pass
        return civil

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    with pytest.raises(EphemerisSourceError, match="no linear approximation"):
        almanac.get_solar_terms_for_year(2026, "UTC")
    recovered = almanac.get_solar_terms_for_year(2026, "UTC")
    assert all(t.resolution_provider == "swisseph" for t in recovered)
    assert calls == 25


def test_generation_change_during_a_year_discards_the_inconsistent_result(
    data_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"value": 1, "bumped": False}

    def observation():
        val = state["value"]
        if not state["bumped"]:
            state["bumped"] = True
            state["value"] = 2
            bump_ephemeris_generation()
        return val

    calls = install_symbolic_solver(monkeypatch, observation)
    result = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) > 24
    for i, term in enumerate(result):
        anchor = almanac._solar_term_search_anchor_utc(2026, i)
        assert term.calendar.utc == UTCCalendar(
            anchor.ordinal, anchor.microseconds_of_day + 2_000_000
        )


def test_continuously_changing_generation_fails_instead_of_returning_a_mixed_year(
    data_environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = {"value": 1}

    def observation():
        val = state["value"]
        state["value"] = val + 1
        bump_ephemeris_generation()
        return val

    install_symbolic_solver(monkeypatch, observation)
    with pytest.raises(RuntimeError, match="持续变化"):
        almanac.get_solar_terms_for_year(2026, "UTC")


@pytest.mark.parametrize("actual_model", ["swieph", "moshier"])
@pytest.mark.parametrize("unused_coarse_switch", [False, True])
def test_solver_records_the_returned_model_rather_than_the_requested_one(
    monkeypatch: pytest.MonkeyPatch, actual_model: str, unused_coarse_switch: bool
) -> None:

    civil = datetime(2020, 3, 20, 3, 50, tzinfo=timezone.utc)
    # Independent civil JD anchor and published TT-UTC = 69.184 seconds.
    tt = (
        2451544.5
        + ((civil - datetime(2000, 1, 1, tzinfo=timezone.utc)).total_seconds() + 69.184)
        / 86400
    )
    returned_flag = 2 if actual_model == "swieph" else 4

    def sun(operation, at, body, flags):
        assert operation == "calc" and flags in (2, 4)
        # A same-epoch Moshier preflight is discarded before requesting the
        # target source. Model assertions below still describe the target.
        actual_flag = 4 if flags == 4 else returned_flag
        if flags == 2 and unused_coarse_switch and at < tt - 10:
            actual_flag = 4 if returned_flag == 2 else 2
        else:
            pass
        return ((at - tt) % 360, 0, 1, 0, 0, 0), actual_flag

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    monkeypatch.setattr(de441_solar, "solar_longitude", lambda at: (at - tt) % 360)
    # This unit fixture has symbolic coordinates, hence symbolic file state.
    # Real compressed-file identities and warmup orders are covered separately.
    monkeypatch.setattr(
        native_solar_source,
        "native_solar_file_context",
        lambda native: {"symbolic_source_fixture": True},
    )
    provenance = {}
    resolved = almanac._solar_term_utc_via_swe(2020, 0, civil, provenance)
    assert resolved is not None
    resolved_datetime = resolved.as_datetime()
    assert resolved_datetime is not None
    assert abs((resolved_datetime - civil).total_seconds()) < 0.0002
    assert provenance["ephemeris_model"] == actual_model
    assert provenance["ephemeris_retflags"] == (returned_flag,)


def test_explicit_de441_dir_routes_moshier_probe_to_de441_solar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    civil = datetime(2020, 3, 20, 3, 50, tzinfo=timezone.utc)
    tt = (
        2451544.5
        + ((civil - datetime(2000, 1, 1, tzinfo=timezone.utc)).total_seconds() + 69.184)
        / 86400
    )

    def sun(operation, at, body, flags):
        assert operation == "calc" and flags in (2, 4)
        return ((at - tt) % 360, 0, 1, 0, 0, 0), 4

    monkeypatch.setenv("FATEBRIDGE_DE441_DIR", str(tmp_path))
    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    monkeypatch.setattr(de441_solar, "solar_longitude", lambda at: (at - tt) % 360)
    provenance = {}
    resolved = almanac._solar_term_utc_via_swe(2020, 0, civil, provenance)
    assert resolved is not None
    assert provenance["ephemeris_model"] == MODEL_ID
    assert provenance["resolution_provider"] == PROVIDER
    assert provenance["ephemeris_retflags"] == ()


@pytest.mark.parametrize(
    "bad", ["negative_flag", "unknown_model", "nonfinite", "mixed"]
)
def test_invalid_or_mixed_model_samples_cannot_become_a_valid_crossing(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    civil = datetime(2020, 3, 20, tzinfo=timezone.utc)
    tt = 2458928.5 + 69.184 / 86400

    def sun(operation, at, body, flags):
        retflag = {"negative_flag": -1, "unknown_model": 0}.get(bad, 2)
        if bad == "mixed":
            # Both ends of the consumed bracket must use one source. An
            # unrelated first coarse sample is not part of that bracket.
            retflag = 4 if at < tt else 2
        else:
            pass
        longitude = float("nan") if bad == "nonfinite" else (at - tt) % 360
        return (longitude, 0, 1, 0, 0, 0), retflag

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    if bad == "mixed":

        monkeypatch.setattr(de441_solar, "solar_longitude", lambda at: (at - tt) % 360)
    else:
        pass
    assert almanac._solar_term_utc_via_swe(2020, 0, civil) is None


def test_changed_native_file_context_cannot_survive_actual_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    civil = datetime(2020, 3, 20, tzinfo=timezone.utc)
    tt = 2458928.5 + 69.184 / 86400

    def sun(operation, at, body, flags):
        return ((at - tt) % 360, 0, 1, 0, 0, 0), flags

    observations = 0

    def context(native):
        nonlocal observations
        observations += 1
        return {"symbolic_source_fixture": 1 if observations < 3 else 2}

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    monkeypatch.setattr(native_solar_source, "native_solar_file_context", context)
    with pytest.raises(EphemerisSourceError) as rejected:
        almanac._solar_term_utc_via_swe(2020, 0, civil, {})
    assert rejected.value.reason == "solar_configuration_changed"


@pytest.mark.parametrize("actual_model", ["swieph", "moshier"])
@pytest.mark.parametrize("root_offset_days", [-9, 9])
def test_solver_does_not_require_an_unavailable_unused_search_prefix(
    monkeypatch: pytest.MonkeyPatch, actual_model: str, root_offset_days
) -> None:

    civil = datetime(2020, 3, 20, tzinfo=timezone.utc)
    root = 2458928.5 + 69.184 / 86400 + root_offset_days
    returned_flag = 2 if actual_model == "swieph" else 4
    sampled = []

    def sun(operation, at, body, flags):
        sampled.append(at)
        if at < root - 10:
            raise RuntimeError("unavailable source in an unused search prefix")
        else:
            pass
        actual_flag = 4 if flags == 4 else returned_flag
        return ((at - root) % 360, 0, 1, 0, 0, 0), actual_flag

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    monkeypatch.setattr(de441_solar, "solar_longitude", lambda at: (at - root) % 360)
    monkeypatch.setattr(
        native_solar_source,
        "native_solar_file_context",
        lambda native: {"symbolic_source_fixture": True},
    )
    provenance = {}
    resolved = almanac._solar_term_utc_via_swe(2020, 0, civil, provenance)
    assert resolved is not None
    resolved_datetime = resolved.as_datetime()
    assert resolved_datetime is not None
    assert (
        abs((resolved_datetime - civil).total_seconds() - root_offset_days * 86400)
        < 0.0002
    )
    assert all(at >= root - 10 for at in sampled)
    assert provenance["ephemeris_model"] == actual_model
