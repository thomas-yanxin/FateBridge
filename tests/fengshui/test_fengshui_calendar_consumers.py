"""The consumer gate must retain the full queue and reject wrong decisions."""

from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.fengshui.annual import annual_stars
from fatebridge.core.fengshui.bazhai import minggua
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    HousePeriod,
    MingguaRequest,
    MonthlyRequest,
)
from fatebridge.core.fengshui.monthly import monthly_stars
from fatebridge.core.fengshui.xuankong import period_context
from fatebridge.utils.timezones import parse_timezone_name
from fatebridge.validation.fengshui_calendar_consumers import (
    check_consumer_observation,
    expected_sides,
    load_consumer_protocol,
    load_literal_month_table,
)
from fatebridge.validation.fengshui_solar_terms import load_solar_terms_reference

FIXTURES = Path(__file__).parents[1] / "data"


@pytest.fixture(scope="module")
def reference():
    return load_solar_terms_reference(FIXTURES / "fengshui_all_terms_v1")


def test_full_public_year_protocol_does_not_remove_the_old_numeric_gate(reference):
    p = load_consumer_protocol(
        FIXTURES / "fengshui_calendar_consumers_v1/protocol.json"
    )
    rows = [
        r
        for r in reference["rows"]
        if 1801 <= r["year"] <= 2199 and r["term_index"] % 2 == 0
    ]
    assert len(rows) == p["reference_events"] == 4788
    assert p["query_offsets_seconds_tt"] == [-10, 0, 10]
    assert p["required_queries_per_model"] == 14364
    assert reference["protocol"]["rows"] == 10104
    assert (
        p["numeric_gate_seconds_unchanged"]
        == reference["protocol"]["numeric_implementation_tolerance_seconds"]
        == 1.0
    )


def test_a_self_rehashed_or_shortened_protocol_cannot_replace_the_before_run_plan(
    tmp_path,
):
    p = tmp_path / "protocol.json"
    p.write_text('{"years":[2026,2026]}')
    with pytest.raises(ValueError):
        load_consumer_protocol(p)


@pytest.mark.parametrize(
    "index,expected",
    [
        (0, ((2025, 11), (2025, 12))),
        (2, ((2025, 12), (2026, 1))),
        (4, ((2026, 1), (2026, 2))),
        (22, ((2026, 10), (2026, 11))),
    ],
)
def test_independent_term_index_arithmetic_keeps_january_and_lichun_distinct(
    index, expected
):
    assert expected_sides({"year": 2026, "term_index": index}) == expected


def results(reference, offset, zone="UTC"):
    row = next(
        r for r in reference["rows"] if r["year"] == 2026 and r["term_index"] == 2
    )
    moment = datetime_from_tt(row["jd_tt"] + offset / 86400).astimezone(
        parse_timezone_name(zone)
    )
    annual = annual_stars(AnnualRequest(query_at=moment, timezone_name=zone))
    month = monthly_stars(MonthlyRequest(query_at=moment, timezone_name=zone))
    personal = minggua(
        MingguaRequest(birth_at=moment, timezone_name=zone, gender_convention="male")
    )
    period = period_context(
        HousePeriod(
            basis="construction_completion",
            event_at=moment,
            timezone_name=zone,
            evidence="Synthetic independent TT boundary query",
        )
    )
    return row, moment, annual, month, personal, period


@pytest.mark.parametrize("offset", [-10, 0, 10])
@pytest.mark.parametrize(
    "zone",
    [
        "UTC",
        "Asia/Shanghai",
        "America/New_York",
        "Australia/Lord_Howe",
        "Pacific/Kiritimati",
    ],
)
def test_selected_timezones_keep_the_same_actual_reference_side(
    reference, monkeypatch, offset, zone
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    row, moment, a, m, g, p = results(reference, offset, zone)
    literal = load_literal_month_table(FIXTURES / "fengshui_monthly_v1/reference.json")
    assert check_consumer_observation(row, offset, moment, a, m, literal, g, p) == []


@pytest.mark.parametrize(
    "fault",
    [
        "unique_month",
        "missing_candidate",
        "interval",
        "center",
        "flight",
        "annual_year",
        "minggua_year",
        "period_year",
    ],
)
def test_semantic_counterexamples_are_rejected_by_the_independent_gate(
    reference, monkeypatch, fault
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    offset = 0 if fault in {"unique_month", "missing_candidate"} else 10
    row, moment, a, m, g, p = deepcopy(results(reference, offset))
    if fault == "unique_month":
        m["status"] = "complete"
        m["time_context"]["solar_month_number"] = 1
    elif fault == "missing_candidate":
        m["time_context"]["candidate_months"].pop()
    elif fault == "interval":
        m["time_context"]["valid_from"] = m["time_context"]["valid_until"]
    elif fault == "center":
        m["center_star_number"] = 9
    elif fault == "flight":
        m["palaces"]["N"]["monthly_star_number"] = 9
    elif fault == "annual_year":
        a["effective_year"] = 2025
    elif fault == "minggua_year":
        g["time_context"]["effective_year"] = 2025
    else:
        p["effective_event_year"] = 2025
    literal = load_literal_month_table(FIXTURES / "fengshui_monthly_v1/reference.json")
    assert check_consumer_observation(row, offset, moment, a, m, literal, g, p)
