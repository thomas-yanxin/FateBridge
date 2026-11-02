"""Exact consumed civil clocks survive REST, CLI, MCP and same-run delivery."""

from datetime import datetime, timedelta

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

pytest_plugins = ["tests.test_agentic_nested_outputs"]


@pytest.mark.parametrize("offset", [-1, 0])
def test_fractional_boundary_clock_on_all_surfaces(offset, rest, tmp_path, capsys):
    term = next(t for t in get_solar_terms_for_year(2026) if t.name == "立春")
    moment = term.moment + timedelta(microseconds=offset)
    payload = dict(
        date=str(moment.date()),
        time=moment.time().isoformat(),
        zone="Asia/Shanghai",
        gua_code="111111",
    )
    fields = [
        "nongli.birth",
        "nongli.monthGanZi",
        "calendar_context.solar_datetime",
        "calendar_context.lunar_calendar.birth",
        "calendar_context.lunar_calendar.solar_datetime",
        "calendar_context.bazi_month_boundary",
        "liuyao_evidence.calendar_conventions",
    ]
    for result in all_surfaces(payload, fields, rest, tmp_path, capsys):
        expected = moment.replace(tzinfo=None)
        calendar = result["calendar_context"]
        for text in [
            result["nongli"]["birth"],
            calendar["solar_datetime"],
            calendar["lunar_calendar"]["birth"],
            calendar["lunar_calendar"]["solar_datetime"],
        ]:
            assert datetime.fromisoformat(text) == expected
        assert result["nongli"]["monthGanZi"][1] == ("丑" if offset < 0 else "寅")


def test_fractional_clock_same_run_delivery(rest, tmp_path, capsys, monkeypatch):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "solar-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2026-02-04",
        time="04:02:07.500001",
        zone="Asia/Shanghai",
        gua_code="111111",
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert original["nongli"]["birth"] == "2026-02-04 04:02:07.500001"
        assert "04:02:07.500001" in original["snapshot_text"]


def test_fractional_clock_leaf_projection(rest, tmp_path, capsys):
    for result in all_surfaces(
        dict(date="2026-02-04", time="04:02:07.500001", gua_code="111111"),
        ["calendar_context.solar_datetime"],
        rest,
        tmp_path,
        capsys,
    ):
        assert result["calendar_context"] == {
            "solar_datetime": "2026-02-04 04:02:07.500001"
        }
