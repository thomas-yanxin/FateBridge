"""A provider switch cannot mix old pillars/windows with a new calendar basis."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core import almanac
from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.bazi import calendar, timing
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.bazi.timing import TimingAnalysis
from tests.support.transports import SPECS, business, call_cli, inputs, native
from tests.support.transports import rest as _shared_rest
from tests.unit_test.fixtures.bazi_year_cases import TOPICS


def clear_solar_caches() -> None:
    for function in (
        almanac.get_solar_terms_for_year,
        BaZiCalendar._get_four_pillars_cached,
        timing._calculate_liuyue_cached,
        timing._calculate_liuri_cached,
    ):
        function.cache_clear()


@pytest.fixture
def preserve_provider(monkeypatch):
    # Native selection retains Swiss files or uses the named bundled DE441 source.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    env = os.environ.get("SE_EPHE_PATH")
    previous = runtime.configured_ephemeris_path()
    clear_solar_caches()
    try:
        yield
    finally:
        if env is None:
            os.environ.pop("SE_EPHE_PATH", None)
        else:
            os.environ["SE_EPHE_PATH"] = env
        runtime.configure_ephemeris_path(previous)
        clear_solar_caches()


def select_provider(path):
    os.environ["SE_EPHE_PATH"] = str(path)
    runtime.configure_ephemeris_path(str(path))


def test_all_three_derived_caches_follow_an_injected_environment_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Hand-controlled dependencies test cache identity, not celestial accuracy.
    state = {"epoch": 0}
    clear_solar_caches()
    for module in (calendar, timing):
        monkeypatch.setattr(
            module,
            "get_solar_term_environment_key",
            lambda *, year=None: (state["epoch"],),
        )
        monkeypatch.setattr(module, "get_bazi_year", lambda *args: 1903)
        monkeypatch.setattr(
            module,
            "get_bazi_month_context",
            lambda *args: {
                "branch": "子" if state["epoch"] == 0 else "丑",
                "start_term": {
                    "name": "synthetic-old" if state["epoch"] == 0 else "synthetic-new"
                },
                "next_term": {"name": "synthetic-next"},
                "days_since_start": 1.0,
                "days_until_next": 2.0,
            },
        )
    birth = datetime(1904, 1, 6, 17, 37)
    try:
        for epoch, branch, term in [
            (0, "子", "synthetic-old"),
            (1, "丑", "synthetic-new"),
            (0, "子", "synthetic-old"),
        ]:
            state["epoch"] = epoch
            assert BaZiCalendar.get_four_pillars(birth, "UTC")["month"][1] == branch
            assert (
                TimingAnalysis.calculate_liuyue(1904, 1, 6, "UTC", birth)["branch"]
                == branch
            )
            assert (
                TimingAnalysis.calculate_liuri(birth, "UTC")["solar_term_window"][
                    "start_term"
                ]["name"]
                == term
            )
    finally:
        clear_solar_caches()


def test_real_file_to_bundled_source_switch_keeps_matching_pillars_and_windows(
    preserve_provider,
) -> None:
    folder = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_PATH",
            str(Path(__file__).resolve().parents[2] / "ephe"),
        )
    )
    if not (folder / "sepl_18.se1").exists():
        pytest.skip(
            "Optional Swiss files absent; synthetic epoch and bundled-source transport checks still run"
        )
    else:
        pass
    # Keep the first instant before both roots and the second between Moshier
    # (17:36:59.5 UTC) and SWIEPH (>17:37:00 UTC) so switching models without
    # clearing caches must move the boundary.
    with TemporaryDirectory(prefix="bazi-model-switch-") as empty:
        for path, model, boundary_branch, boundary_start in [
            (folder, "swieph", "子", "大雪"),
            (empty, "moshier", "丑", "小寒"),
            (folder, "swieph", "子", "大雪"),
        ]:
            select_provider(path)  # Intentionally no cache clearing here.
            term = next(
                t
                for t in almanac.get_solar_terms_for_year(1904, "UTC")
                if t.name == "小寒"
            )
            assert term.ephemeris_model == model
            for birth, branch, start in [
                (datetime(1904, 1, 6, 17, 36, 59), "子", "大雪"),
                (
                    datetime(1904, 1, 6, 17, 37, 0),
                    boundary_branch,
                    boundary_start,
                ),
            ]:
                assert BaZiCalendar.get_four_pillars(birth, "UTC")["month"][1] == branch
                assert almanac.get_bazi_month_context(birth, "UTC")["branch"] == branch
                assert (
                    TimingAnalysis.calculate_liuyue(1904, 1, 6, "UTC", birth)["branch"]
                    == branch
                )
                assert (
                    TimingAnalysis.calculate_liuri(birth, "UTC")["solar_term_window"][
                        "start_term"
                    ]["name"]
                    == start
                )


rest = _shared_rest


@pytest.mark.parametrize("topic", TOPICS)
def test_all_ten_calendar_views_publish_actual_bundled_model_on_three_surfaces(
    topic, preserve_provider, rest, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = SPECS["bazi_birth_chart" if topic == "birth" else "bazi_" + topic]
    payload = {**inputs(spec), "use_true_solar_time": False}
    fields = suggested_fields(spec, view="calendar_basis")
    with TemporaryDirectory(prefix="bazi-bundled-view-") as empty:
        select_provider(empty)
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", p) for p in fields],
        )
        protocol = asyncio.run(
            native(
                spec,
                payload,
                fields=fields,
            )
        )
        code, cli = call_cli(
            spec,
            payload,
            tmp_path,
            capsys,
            flags=[
                "--fields",
                *fields,
            ],
        )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    results = [response.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    root = "bazi_birth" if topic == "birth" else topic + "_analysis"
    for result in results:
        context = result[root]["calendar_context"]
        for term in [
            context["current_solar_term"],
            context["next_solar_term"],
            context["bazi_month_boundary"]["start_term"],
            context["bazi_month_boundary"]["next_term"],
        ]:
            assert term["resolution_provider"] == "swisseph"
            assert term["ephemeris_model"] == "moshier"
        assert result["run_metadata"]["engine_is_approximate"] is True
        assert "approximate_engine" in result["run_metadata"]["warnings"]
