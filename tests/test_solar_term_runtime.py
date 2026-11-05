"""Changed numerical environments must not reuse the prior solar boundary.

Synthetic solver instants exercise cache behavior, not celestial accuracy.
Real Swiss return flags are tested separately from the requested flag.
"""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import almanac
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def data_environment(monkeypatch, tmp_path):
    # These controls perturb the native solver and its file environment.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    if almanac.swe is None:
        pytest.skip("Swiss package is needed for the environment control")
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
        if provenance is not None:
            provenance.update(
                ephemeris_model="swieph",
                ephemeris_retflags=(2,),
                ephemeris_library_version="synthetic",
            )
        return anchor + timedelta(seconds=seconds)

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    return calls


def test_changing_selected_path_recalculates_without_manual_cache_clear(
    data_environment, monkeypatch, tmp_path
):
    first = str(data_environment)
    second = tmp_path / "other"
    second.mkdir()
    calls = install_symbolic_solver(
        monkeypatch, lambda: 1 if configured_ephemeris_path() == first else 8
    )
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    assert almanac.get_solar_terms_for_year(2026, "UTC") is before
    assert len(calls) == 24
    configure_ephemeris_path(str(second))
    after = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) == 48
    assert all(
        (b.moment - a.moment).total_seconds() == 7 for a, b in zip(before, after)
    )


@pytest.mark.parametrize("name", ["sepl_18.se1", "semo_18.se1", "swe_deltat.txt"])
def test_installing_or_replacing_data_in_same_directory_invalidates_old_year(
    data_environment, monkeypatch, name
):
    file = data_environment / name
    install_symbolic_solver(
        monkeypatch, lambda: int(file.read_text()) if file.exists() else 1
    )
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    file.write_text("4")
    installed = almanac.get_solar_terms_for_year(2026, "UTC")
    assert (installed[0].moment - before[0].moment).total_seconds() == 3
    file.write_text("9")
    replaced = almanac.get_solar_terms_for_year(2026, "UTC")
    assert (replaced[0].moment - installed[0].moment).total_seconds() == 5
    file.unlink()
    removed = almanac.get_solar_terms_for_year(2026, "UTC")
    assert removed[0].moment == before[0].moment


def test_provider_availability_recovers_without_caching_an_approximate_year(
    data_environment, monkeypatch
):
    library = almanac.swe
    install_symbolic_solver(monkeypatch, lambda: 7)
    monkeypatch.setattr(almanac, "swe", None)
    with pytest.raises(EphemerisSourceError, match="no linear approximation"):
        almanac.get_solar_terms_for_year(2026, "UTC")
    monkeypatch.setattr(almanac, "swe", library)
    after = almanac.get_solar_terms_for_year(2026, "UTC")
    assert {t.resolution_provider for t in after} == {"swisseph"}


def test_transient_solver_failure_does_not_poison_the_same_environment_cache(
    data_environment, monkeypatch
):
    calls = 0

    def solve(year, longitude, anchor, provenance=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        if provenance is not None:
            provenance.update(ephemeris_model="swieph", ephemeris_retflags=(2,))
        return anchor + timedelta(seconds=7)

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    with pytest.raises(EphemerisSourceError, match="no linear approximation"):
        almanac.get_solar_terms_for_year(2026, "UTC")
    recovered = almanac.get_solar_terms_for_year(2026, "UTC")
    assert all(t.resolution_provider == "swisseph" for t in recovered)
    assert calls == 25


def test_file_change_during_a_year_discards_the_inconsistent_result(
    data_environment, monkeypatch
):
    file = data_environment / "sepl_18.se1"
    file.write_text("1")
    first = True

    def observation():
        nonlocal first
        value = int(file.read_text())
        if first:
            first = False
            file.write_text("2")
        return value

    calls = install_symbolic_solver(monkeypatch, observation)
    result = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) > 24
    assert all(
        t.moment
        == almanac._solar_term_search_anchor_utc(2026, i) + timedelta(seconds=2)
        for i, t in enumerate(result)
    )


def test_continuously_changing_files_fail_instead_of_returning_a_mixed_year(
    data_environment, monkeypatch
):
    file = data_environment / "sepl_18.se1"
    file.write_text("1")

    def observation():
        value = int(file.read_text())
        file.write_text(str(value + 1))
        return value

    install_symbolic_solver(monkeypatch, observation)
    with pytest.raises(RuntimeError, match="持续变化"):
        almanac.get_solar_terms_for_year(2026, "UTC")


@pytest.mark.parametrize("actual_model", ["swieph", "moshier"])
def test_solver_records_the_returned_model_rather_than_the_requested_one(
    monkeypatch, actual_model
):
    from fatebridge.core import moshier_solar, native_solar_source

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
        return ((at - tt) % 360, 0, 1, 0, 0, 0), actual_flag

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    monkeypatch.setattr(moshier_solar, "solar_longitude", lambda at: (at - tt) % 360)
    # This unit fixture has symbolic coordinates, hence symbolic file state.
    # Real compressed-file identities and warmup orders are covered separately.
    monkeypatch.setattr(
        native_solar_source,
        "native_solar_file_context",
        lambda native: {"symbolic_source_fixture": True},
    )
    provenance = {}
    resolved = almanac._solar_term_utc_via_swe(2020, 0, civil, provenance)
    assert resolved is not None and abs((resolved - civil).total_seconds()) < 0.0002
    if actual_model == "moshier":
        assert provenance["ephemeris_model"] == moshier_solar.MODEL_ID
        assert provenance["resolution_provider"] == moshier_solar.PROVIDER
        assert provenance["ephemeris_retflags"] == ()
    else:
        assert provenance["ephemeris_model"] == actual_model
        assert provenance["ephemeris_retflags"] == (returned_flag,)


@pytest.mark.parametrize(
    "bad", ["negative_flag", "unknown_model", "nonfinite", "mixed"]
)
def test_invalid_or_mixed_model_samples_cannot_become_a_valid_crossing(
    monkeypatch, bad
):
    civil = datetime(2020, 3, 20, tzinfo=timezone.utc)
    tt = 2458928.5 + 69.184 / 86400
    calls = 0

    def sun(operation, at, body, flags):
        nonlocal calls
        calls += 1
        retflag = {"negative_flag": -1, "unknown_model": 0}.get(bad, 2)
        if bad == "mixed" and calls > 1:
            retflag = 4
        longitude = float("nan") if bad == "nonfinite" else (at - tt) % 360
        return (longitude, 0, 1, 0, 0, 0), retflag

    monkeypatch.setattr(almanac, "ephemeris_call", sun)
    assert almanac._solar_term_utc_via_swe(2020, 0, civil) is None
