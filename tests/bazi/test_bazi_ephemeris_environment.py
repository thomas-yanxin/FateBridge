"""A provider switch cannot mix old pillars/windows with a new calendar basis."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core import almanac, calendar
from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core import timing
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from tests.bazi.test_bazi_solar_provider import clear_solar_caches
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.support.transports import SPECS, business, call_cli, inputs, native
from tests.support.transports import rest as _shared_rest


@pytest.fixture
def preserve_provider(monkeypatch):
    # These original controls still assert the actual native Moshier path.
    # The newer auto and explicit SPK paths have separate tests and identities.
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


def test_all_three_derived_caches_follow_an_injected_environment_epoch(monkeypatch):
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


def test_real_file_to_moshier_switch_never_keeps_old_pillars_or_windows(
    preserve_provider,
):
    folder = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_PATH",
            str(Path(__file__).resolve().parents[2] / "ephe"),
        )
    )
    if not (folder / "sepl_18.se1").exists():
        pytest.skip(
            "Optional Swiss files absent; synthetic epoch and Moshier transport checks still run"
        )
    birth = datetime(1904, 1, 6, 17, 37)
    # This minute straddles the two configured model results. It is a
    # consistency counterexample, not an independent correctness oracle.
    with TemporaryDirectory(prefix="bazi-model-switch-") as empty:
        for path, model, branch, start in [
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
def test_all_ten_calendar_views_publish_actual_model_and_downgrade_on_three_surfaces(
    topic, preserve_provider, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    payload = {**inputs(spec), "use_true_solar_time": False}
    fields = suggested_fields(spec, view="calendar_basis")
    with TemporaryDirectory(prefix="bazi-moshier-view-") as empty:
        select_provider(empty)
        response = rest.post(
            spec.rest_path,
            json=payload,
            params=[("fields", p) for p in fields]
            + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        )
        protocol = asyncio.run(
            native(
                spec,
                payload,
                fields=fields,
                strict_fields=True,
                include_snapshot_text=False,
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
                "--strict-fields",
                "true",
                "--include-snapshot-text",
                "false",
                "--response-char-limit",
                "0",
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
        assert result["run_metadata"]["provenance"]["ephemeris_model"] == ["moshier"]
