"""The TT sampler and Design root must use the civil forward time policy."""

from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time, tt_from_ut1
from fatebridge.core.human_design import chart_at, chart_at_tt
from fatebridge.core.human_design_time import epoch_context_at_tt
from tests.ephemeris_context import moshier_ephemeris


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize(
    "year", [1800, 1850, 1900, 1955, 1959, 1960, 1961, 1965, 1972, 2000, 2399]
)
def test_epoch_ut1_is_the_inverse_of_the_declared_forward_policy(year, empty_files):
    def check():
        moment = datetime(year, 1, 1, 12, tzinfo=timezone.utc)
        forward = ephemeris_time(moment)
        context = epoch_context_at_tt(forward.jd_tt, method="test")["time"]
        assert context["jd_tt"] == forward.jd_tt
        assert context["jd_ut1"] == forward.jd_ut1
        assert tt_from_ut1(context["jd_ut1"]) == forward.jd_tt

    if empty_files:
        with moshier_ephemeris():
            check()
    else:
        check()


@pytest.mark.parametrize("year", [1800, 1900, 1959, 1960, 1965, 2000])
def test_tt_sampler_and_design_context_round_trip_without_changing_the_chart(year):
    moment = datetime(year, 4, 6, 1, 33, tzinfo=timezone.utc)
    civil = chart_at(moment)
    sampled = chart_at_tt(civil["time_scales"]["personality"]["jd_tt"])
    assert sampled["time_scales"]["personality"]["jd_ut1"] == (
        civil["time_scales"]["personality"]["jd_ut1"]
    )
    for side in ("personality", "design"):
        context = sampled["time_scales"][side]
        assert tt_from_ut1(context["jd_ut1"]) == context["jd_tt"]
    for field in ("activations", "bodygraph", "profile", "variables"):
        assert civil[field] == sampled[field]
    # datetime inversion can round a civil label by microseconds; it must not
    # move the physical TT root or its numerical convergence diagnostics.
    assert {
        k: v for k, v in civil["design_solver"].items() if k != "civil_elapsed_days"
    } == {
        k: v for k, v in sampled["design_solver"].items() if k != "civil_elapsed_days"
    }
    assert (
        abs(
            civil["design_solver"]["civil_elapsed_days"]
            - sampled["design_solver"]["civil_elapsed_days"]
        )
        * 86400
        <= 0.0002
    )


@pytest.mark.parametrize("year,expected_flag", [(1800, -1), (1965, 2)])
def test_epoch_context_obeys_the_shared_historical_delta_t_flag(
    monkeypatch, year, expected_flag
):
    # A controlled model makes this regression independent of installed files.
    # The old copied SWIEPH loop incorrectly used flag 2 before the UTC era.
    moment = datetime(year, 6, 1, tzinfo=timezone.utc)
    tt = ephemeris_time(moment).jd_tt
    monkeypatch.setattr(
        "fatebridge.core.human_design_time.utc_from_tt",
        lambda jd: (moment.isoformat(), moment, False),
    )
    flags = []

    def delta_t(operation, jd, flag):
        assert operation == "deltat_ex"
        flags.append(flag)
        return (60 if flag == -1 else 61) / 86400

    monkeypatch.setattr(runtime, "ephemeris_call", delta_t)
    result = epoch_context_at_tt(tt, method="test")["time"]
    assert flags == [expected_flag] * 4
    assert result["jd_ut1"] == tt - (60 if year < 1960 else 61) / 86400
