"""Regression cases for date handling and shared ephemeris configuration."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from types import SimpleNamespace

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.predictive import _common, returns
from fatebridge.core.predictive.transit import build_transit_payload
from fatebridge.utils.timezones import parse_timezone_name


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


def test_partial_analysis_date_preserves_every_supplied_field(monkeypatch):
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
    monkeypatch, now, year, month, expected
):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=tz)

    monkeypatch.setattr(_common, "datetime", FixedDatetime)
    result = _common.build_analysis_datetime(_birth_info(), year, month)
    assert result.isoformat() == f"{expected}T10:00:00+08:00"


def test_explicit_invalid_analysis_day_is_not_clamped(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 31, tzinfo=tz)

    monkeypatch.setattr(_common, "datetime", FixedDatetime)
    with pytest.raises(ValueError, match="day is out of range"):
        _common.build_analysis_datetime(_birth_info(), 2030, 2, 31)


def test_transit_timezone_conversion_preserves_the_instant(monkeypatch):
    import fatebridge.core.predictive.transit as transit

    captured = {}
    monkeypatch.setattr(
        transit, "build_subject", lambda **kwargs: captured.update(kwargs)
    )
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
def test_kerykeion_subject_restores_path_even_on_failure(monkeypatch, raises):
    paths = []
    fake_swe = SimpleNamespace(set_ephe_path=paths.append)
    monkeypatch.setattr(runtime, "swe", fake_swe)
    monkeypatch.setattr(runtime, "_configured_path", "/operator/ephe")

    def from_birth_data(**kwargs):
        fake_swe.set_ephe_path("/third-party/ephe")
        if raises:
            raise RuntimeError("third-party failure")
        return "subject"

    monkeypatch.setattr(
        _common,
        "AstrologicalSubjectFactory",
        SimpleNamespace(from_birth_data=from_birth_data),
    )
    if raises:
        with pytest.raises(RuntimeError, match="third-party failure"):
            _common.build_natal_subject(_birth_info())
    else:
        assert _common.build_natal_subject(_birth_info()) == "subject"
    assert paths == ["/third-party/ephe", "/operator/ephe"]


def test_return_factory_failure_restores_path(monkeypatch):
    paths = []
    fake_swe = SimpleNamespace(set_ephe_path=paths.append)
    monkeypatch.setattr(runtime, "swe", fake_swe)
    monkeypatch.setattr(runtime, "_configured_path", "/operator/ephe")

    def factory(*args, **kwargs):
        fake_swe.set_ephe_path("/third-party/returns")
        raise RuntimeError("return failure")

    monkeypatch.setattr(returns, "PlanetaryReturnFactory", factory)
    with pytest.raises(RuntimeError, match="return failure"):
        returns.build_return_payload(
            None,
            analysis_datetime=datetime(2026, 10, 9),
            return_longitude=116.4,
            return_latitude=39.9,
            return_timezone="Asia/Shanghai",
        )
    assert paths == ["/third-party/returns", "/operator/ephe"]


def test_concurrent_direct_call_waits_for_third_party_path_restoration(monkeypatch):
    state = {"path": "/operator/ephe"}
    attempted = Event()
    finished = Event()
    fake_swe = SimpleNamespace(
        set_ephe_path=lambda path: state.update(path=path),
        calc_ut=lambda *args: state["path"],
    )
    monkeypatch.setattr(runtime, "swe", fake_swe)
    monkeypatch.setattr(runtime, "_configured_path", state["path"])

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
        assert future.result(timeout=2) == "/operator/ephe"


def test_real_kerykeion_does_not_change_subsequent_core_precision(monkeypatch):
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
