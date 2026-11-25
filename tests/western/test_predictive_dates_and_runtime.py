"""Regression cases for date handling and shared ephemeris configuration."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from types import SimpleNamespace

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.predictive import _common, returns
from fatebridge.core.predictive.transit import build_transit_payload
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name
from tests.support.transports import SPECS, inputs, rest, surface_calls


def _birth_info():
    return _common.build_predictive_birth_info(
        birth_year=1990,
        birth_month=6,
        birth_day=15,
        birth_hour=10,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4,
        birth_latitude=39.9,
    )


@pytest.mark.parametrize(
    "analysis_year,has_firdaria",
    [(1989, False), (2500, True)],
)
def test_timing_aggregate_preserves_results_without_an_active_releasing_period(
    analysis_year: int, has_firdaria: bool
) -> None:
    from fatebridge.services.western_timing import calculate_western_timing_analysis
    from tests.support.ephemeris_context import empty_ephemeris_path

    with empty_ephemeris_path():
        result = calculate_western_timing_analysis(
            birth_year=1990,
            birth_month=5,
            birth_day=17,
            birth_hour=15,
            birth_minute=30,
            birth_timezone="UTC",
            birth_longitude=0.0,
            birth_latitude=40.0,
            analysis_year=analysis_year,
            analysis_month=5,
            analysis_day=20,
            analysis_hour=12,
            analysis_minute=0,
            house_system="W",
        )
    assert "error" not in result
    assert (
        result["time_lords"]["zodiacal_releasing"]["spirit"]["current_level_1"] is None
    )
    assert (
        result["time_lords"]["firdaria"]["current_major"] is not None
    ) == has_firdaria
    assert "Spirit 黄道释放 L1 未知" in result["summary"]
    assert (
        result["natal_reference"]["calculation_basis"]["ephemeris_model"] == "moshier"
    )
    assert result["returns"]["solar_return"]["solver"]["event_not_after_analysis"]
    assert result["returns"]["lunar_return"]["solver"]["event_not_after_analysis"]
    assert result["transits"]["current_transit"]["analysis_datetime"].startswith(
        str(analysis_year)
    )
    assert result["directions"]["secondary_progression"]["sun"]["absolute_degree"] >= 0


def test_partial_analysis_date_preserves_every_supplied_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 9, tzinfo=tz)

    monkeypatch.setattr(_common, "datetime", FixedDatetime)
    info = _birth_info()
    result = _common.build_analysis_datetime(info, analysis_year=2030, analysis_month=2)
    assert result.isoformat() == "2030-02-09T10:00:00+08:00"
    assert _common.build_analysis_datetime(info, analysis_day=4).day == 4
    with pytest.raises(ValueError):
        _common.build_analysis_datetime(info, 2025, 2, 31)


@pytest.mark.parametrize(
    "now, year, month, expected",
    [
        (datetime(2026, 10, 31), 2030, 2, "2030-02-28"),
        (datetime(2026, 10, 31), 2028, 2, "2028-02-29"),
        (datetime(2026, 10, 31), None, 4, "2026-04-30"),
        (datetime(2024, 2, 29), 2025, None, "2025-02-28"),
    ],
)
def test_default_analysis_day_fits_target_month(
    monkeypatch: pytest.MonkeyPatch,
    now,
    year: int | None,
    month: int | None,
    expected: str,
) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=tz)

    monkeypatch.setattr(_common, "datetime", FixedDatetime)
    result = _common.build_analysis_datetime(_birth_info(), year, month)
    assert result.isoformat() == f"{expected}T10:00:00+08:00"


def test_explicit_invalid_analysis_day_is_not_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 31, tzinfo=tz)

    monkeypatch.setattr(_common, "datetime", FixedDatetime)
    with pytest.raises(ValueError, match="day is out of range"):
        _common.build_analysis_datetime(_birth_info(), 2030, 2, 31)


def test_transit_timezone_conversion_preserves_the_instant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.core.predictive.transit as transit

    captured = {}

    def capture_subject(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(calculation_basis={})

    monkeypatch.setattr(transit, "build_subject", capture_subject)
    point = {"sign_label": "test", "house": 1}
    monkeypatch.setattr(
        transit,
        "extract_named_points",
        lambda *args: dict.fromkeys(
            ("sun", "moon", "ascendant", "medium_coeli"), point
        ),
    )
    monkeypatch.setattr(transit, "extract_named_longitudes", lambda *args: {})
    monkeypatch.setattr(transit, "collect_aspect_hits", lambda **kwargs: [])
    moment = datetime(2026, 10, 9, 10, tzinfo=parse_timezone_name("Asia/Shanghai"))
    payload = build_transit_payload(
        _birth_info(),
        None,
        analysis_datetime=moment,
        transit_longitude=-74,
        transit_latitude=40.7,
        transit_timezone="America/New_York",
    )
    assert captured["local_datetime"].isoformat() == "2026-10-08T22:00:00-04:00"
    assert captured["local_datetime"] == moment
    assert payload["analysis_datetime"] == "2026-10-08T22:00:00-04:00"


@pytest.mark.parametrize("raises", [False, True])
@pytest.mark.parametrize("env_path", [None, "/environment/ephe"])
def test_native_subject_keeps_operator_path_even_on_failure(
    monkeypatch: pytest.MonkeyPatch, raises: bool, env_path: str | None
) -> None:
    from fatebridge.core.predictive import native_chart

    paths = []
    original_set_path = runtime.swe.set_ephe_path

    def set_path(path):
        paths.append(path)
        original_set_path(path)

    monkeypatch.setattr(runtime.swe, "set_ephe_path", set_path)
    monkeypatch.setattr(runtime, "_configured_path", "/operator/ephe")
    if env_path is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", env_path)
    if raises:

        def fail(*args, **kwargs):
            raise RuntimeError("native ephemeris failure")

        monkeypatch.setattr(native_chart, "_swisseph_planet_state", fail)
        with pytest.raises(RuntimeError, match="native ephemeris failure"):
            _common.build_natal_subject(_birth_info())
    else:
        assert _common.build_natal_subject(_birth_info()).name
    assert paths and set(paths) == {env_path or "/operator/ephe"}


@pytest.mark.parametrize("env_path", [None, "/environment/ephe"])
def test_return_solver_failure_preserves_operator_path(
    monkeypatch: pytest.MonkeyPatch, env_path: str | None
) -> None:
    subject = _common.build_natal_subject(_birth_info())
    paths = []
    original_set_path = runtime.swe.set_ephe_path

    def set_path(path):
        paths.append(path)
        original_set_path(path)

    monkeypatch.setattr(runtime.swe, "set_ephe_path", set_path)
    monkeypatch.setattr(runtime, "_configured_path", "/operator/ephe")
    if env_path is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", env_path)

    def fail(*args, **kwargs):
        raise RuntimeError("return failure")

    monkeypatch.setattr(returns, "_longitude_tt", fail)
    with pytest.raises(RuntimeError, match="return failure"):
        returns.build_return_payload(
            subject,
            analysis_datetime=datetime(2026, 10, 9, tzinfo=parse_timezone_name("UTC")),
            return_longitude=116.4,
            return_latitude=39.9,
            return_timezone="Asia/Shanghai",
        )
    assert paths and set(paths) == {env_path or "/operator/ephe"}


@pytest.mark.parametrize("env_path", [None, "/environment/ephe"])
def test_concurrent_direct_call_waits_for_third_party_path_restoration(
    monkeypatch: pytest.MonkeyPatch, env_path: str | None
) -> None:
    state = {"path": "/operator/ephe"}
    attempted = Event()
    finished = Event()
    fake_swe = SimpleNamespace(
        set_ephe_path=lambda path: state.update(path=path),
        calc_ut=lambda *args: state["path"],
    )
    monkeypatch.setattr(runtime, "swe", fake_swe)
    monkeypatch.setattr(runtime, "_configured_path", state["path"])
    if env_path is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", env_path)

    def direct_call():
        attempted.set()
        result = runtime.ephemeris_call("calc_ut", 0)
        finished.set()
        return result

    with ThreadPoolExecutor(max_workers=1) as executor:
        with runtime.preserve_ephemeris_path():
            fake_swe.set_ephe_path("/third-party/ephe")
            future = executor.submit(direct_call)
            assert attempted.wait(2)
            assert not finished.wait(0.1)
        assert future.result(timeout=2) == (env_path or "/operator/ephe")


def test_predictive_chart_does_not_change_subsequent_core_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.astro.chart import build_core_chart_payload

    pytest.importorskip("swisseph")
    paths = []
    real_set_path = runtime.swe.set_ephe_path
    original_path = runtime._configured_path

    def capture_path(path):
        paths.append(path)
        real_set_path(path)

    monkeypatch.setattr(runtime.swe, "set_ephe_path", capture_path)
    monkeypatch.setattr(runtime, "_configured_path", original_path)
    before = build_core_chart_payload(_birth_info(), "chart")
    _common.build_natal_subject(_birth_info())
    assert paths[-1] == (original_path or "")
    after = build_core_chart_payload(_birth_info(), "chart")
    assert before == after


@pytest.mark.parametrize(
    "failure",
    [EphemerisSourceError("model_changed"), RuntimeError("unexpected house failure")],
)
def test_native_house_failure_preserves_source_and_programming_errors(
    monkeypatch: pytest.MonkeyPatch, failure
) -> None:
    from fatebridge.core.predictive import native_chart

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(native_chart, "ephemeris_call", fail)
    with pytest.raises(type(failure)) as caught:
        _common.build_natal_subject(_birth_info())
    assert caught.value is failure


@pytest.mark.native_engine_fault
def test_predictive_house_source_error_reaches_rest_mcp_cli(
    monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
    from fatebridge.core.predictive import native_chart

    def fail(*args, **kwargs):
        raise EphemerisSourceError("model_changed")

    monkeypatch.setattr(native_chart, "ephemeris_call", fail)
    spec = SPECS["transit"]
    http, protocol, code, local = surface_calls(spec, inputs(spec))
    assert http.status_code == 503 and protocol.is_error and code != 0
    for output in (http.json(), protocol.structured_content, local):
        assert output["error_code"] == "ephemeris_source_inconsistent"
        assert output["issues"][0]["code"] == "model_changed"
        assert output["retryable"] is False
