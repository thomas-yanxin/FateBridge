"""Printed operands, official minutes and explicit month/year boundary cases."""

import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core import almanac
from fatebridge.core.fengshui.models import MonthlyRequest
from fatebridge.core.fengshui.monthly import monthly_position_reading
from fatebridge.core.fengshui.monthly_time import solar_month_context
from fatebridge.services.fengshui import assess, calculate_monthly_stars
from fatebridge.services.replay_metadata import digest
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.fengshui_monthly import (
    audit_monthly_reference,
    verify_monthly_reading,
)
from tests.fengshui.test_fengshui_surfaces import (
    mcp_call,
    rest_client,
    without_transport,
)

FOLDER = Path(__file__).parents[1] / "data/fengshui_monthly_v1"
REFERENCE = json.loads((FOLDER / "reference.json").read_text())
YEARS = [
    (2020, "子"),
    (2021, "丑"),
    (2022, "寅"),
    (2023, "卯"),
    (2024, "辰"),
    (2025, "巳"),
    (2026, "午"),
    (2027, "未"),
    (2028, "申"),
    (2029, "酉"),
    (2030, "戌"),
    (2031, "亥"),
]
TERMS = [
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
    "大雪",
]
OFFICIAL = []
for year in [2024, 2026, 2027, 2028]:
    folder = "fengshui_calendar_v1" if year == 2024 else "calendar_hko_v1"
    root = "data" if year == 2024 else "fixtures"
    file = Path(__file__).parents[1] / root / folder / f"24SolarTerms_{year}.xml"
    rows = list(ET.fromstring(file.read_text()))
    for term, row in zip(TERMS, rows[::2]):
        clock = datetime.fromisoformat(
            f"{year}-{row.findtext('M')}-{row.findtext('D')}T{row.findtext('hm')}:00+08:00"
        )
        OFFICIAL.append((term, clock))


def layer(**data):
    return calculate_monthly_stars(**data)["layers"]["monthly_stars"]


def confirmed(year, month):
    return layer(effective_solar_year=year, solar_month_number=month)


def test_printed_table_and_literal_reference_fingerprints_are_unchanged():
    for filename, expected in json.loads((FOLDER / "hashes.json").read_text()).items():
        assert hashlib.sha256((FOLDER / filename).read_bytes()).hexdigest() == expected
    audit = audit_monthly_reference(REFERENCE)
    assert audit["source_cell_count"] == 36
    assert audit["branch_month_checks"] == 144
    assert audit["numeric_scoped_acceptance_passed"]
    assert not audit["printed_calendar_labels_all_conform"]
    assert audit["printed_calendar_label_differences"] == [
        {
            "solar_month_number": 6,
            "printed_terms": ["大暑", "小暑"],
            "selected_start_term": "小暑",
            "resolution": "independent_author_and_official_astronomical_order_not_rewriting_print",
        }
    ]
    assert not audit["whole_book_conformity_established"]
    bad = deepcopy(REFERENCE)
    bad["printed_center_columns"][0]["centers"][0] = 7
    assert not audit_monthly_reference(bad)["numeric_scoped_acceptance_passed"]
    bad["printed_center_columns"][0]["centers"].pop()
    with pytest.raises(ValueError):
        audit_monthly_reference(bad)


@pytest.mark.parametrize("year,branch", YEARS)
@pytest.mark.parametrize("month", range(1, 13))
def test_all_twelve_year_branches_and_all_printed_month_center_numbers(
    year, branch, month
):
    column = next(
        g for g in REFERENCE["printed_center_columns"] if branch in g["branches"]
    )
    actual = confirmed(year, month)
    assert actual["year_branch"] == branch
    assert actual["center_star_number"] == column["centers"][month - 1]
    assert (
        actual["time_context"]["month_branch"] == "寅卯辰巳午未申酉戌亥子丑"[month - 1]
    )
    assert sorted(p["monthly_star_number"] for p in actual["palaces"].values()) == list(
        range(1, 10)
    )
    assert not any("polarity" in p["monthly_star"] for p in actual["palaces"].values())
    assert "current_period" not in actual


@pytest.mark.parametrize("month", range(1, 13))
def test_all_108_authored_2026_palace_numbers_and_each_rendered_target(month):
    published = REFERENCE["published_2026"]
    actual = confirmed(2026, month)
    reading = actual["position_reading"]
    texts = {s["target_path"]: s for s in reading["statements"]}
    assert len(texts) == 10
    for direction, expected in zip(
        published["directions"], published["rows"][month - 1]
    ):
        palace = actual["palaces"][direction]
        assert palace["monthly_star_number"] == expected
        path = "layers.monthly_stars.palaces." + direction
        sentence = texts[path]
        assert (
            f"{direction}宫固定宫数{palace['palace_number']}，本节月飞临月星{expected}（"
            in sentence["text"]
        )
        assert sentence["basis"][path] == palace
        assert "layers.monthly_stars.time_context" in sentence["basis_paths"]
        assert "layers.monthly_stars.ruleset" in sentence["basis_paths"]


@pytest.mark.parametrize("term,official", OFFICIAL)
def test_48_official_published_jie_minutes_and_before_after_membership(term, official):
    result = layer(query_at=official + timedelta(seconds=61))
    time = result["time_context"]
    assert result["status"] == "complete"
    assert time["timing"]["start_resolution"]["term_name"] == term
    start = datetime.fromisoformat(time["valid_from"])
    assert abs((start - official).total_seconds()) <= 60
    previous = layer(query_at=official - timedelta(seconds=61))
    assert previous["time_context"]["solar_month_number"] != time["solar_month_number"]
    expected_year = official.year - 1 if term == "小寒" else official.year
    assert time["effective_solar_year"] == expected_year
    assert time["solar_month_number"] == (12 if term == "小寒" else TERMS.index(term))
    for edge, expected in [(-1, False), (0, True), (1, True)]:
        # This asserts the model's half-open interval, separately from the
        # independent official-minute comparison above; no second certification.
        response = layer(query_at=start + timedelta(microseconds=edge))
        exact = response["time_context"]
        if exact.get("month_status") == "requires_confirmation":
            assert response["palaces"] == {}
            assert len(exact["candidate_months"]) == 2
            observed = (
                exact["provisional_effective_solar_year"],
                exact["provisional_solar_month_number"],
            )
        else:
            observed = (exact["effective_solar_year"], exact["solar_month_number"])
        same = observed == (time["effective_solar_year"], time["solar_month_number"])
        assert same is expected


@pytest.mark.parametrize("month", range(1, 13))
def test_zhongqi_does_not_switch_the_month(month):
    # Official 2026 XML alternates jie and zhongqi; January is the prior year.
    file = Path(__file__).parents[1] / "fixtures/calendar_hko_v1/24SolarTerms_2026.xml"
    row = list(ET.fromstring(file.read_text()))[(month - 1) * 2 + 1]
    t = datetime.fromisoformat(
        f"2026-{row.findtext('M')}-{row.findtext('D')}T{row.findtext('hm')}:00+08:00"
    )
    before = layer(query_at=t - timedelta(minutes=2))["time_context"]
    after = layer(query_at=t + timedelta(minutes=2))["time_context"]
    assert (before["effective_solar_year"], before["solar_month_number"]) == (
        after["effective_solar_year"],
        after["solar_month_number"],
    )


@pytest.mark.parametrize(
    "clock,year,month,center",
    [
        ("2026-01-03T12:00:00+08:00", 2025, 11, 1),
        ("2026-01-10T12:00:00+08:00", 2025, 12, 9),
        ("2027-01-10T12:00:00+08:00", 2026, 12, 6),
        ("2026-02-02T12:00:00+08:00", 2025, 12, 9),
        ("2026-02-05T12:00:00+08:00", 2026, 1, 8),
    ],
)
def test_january_and_pre_lichun_use_the_prior_effective_year(
    clock, year, month, center
):
    actual = layer(query_at=clock)
    assert (
        actual["time_context"]["effective_solar_year"],
        actual["time_context"]["solar_month_number"],
        actual["center_star_number"],
    ) == (year, month, center)


@pytest.mark.parametrize(
    "zone",
    ["UTC", "Asia/Hong_Kong", "America/New_York", "Pacific/Kiritimati", "UTC-12:00"],
)
def test_one_instant_has_one_month_in_different_display_timezones(monkeypatch, zone):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    t = "2026-10-08T06:29:18+00:00"
    a = layer(query_at=t, timezone_name=zone)
    b = layer(query_at=t)
    # Keep the original instant: it is inside the existing five-second guard.
    # A timezone change must preserve both candidates, not invent one interval.
    assert a["status"] == b["status"] == "partial"
    assert a["palaces"] == b["palaces"] == {}
    for value in (a, b):
        context = value["time_context"]
        assert context["month_status"] == "requires_confirmation"
        assert context["valid_from"] is context["valid_until"] is None
        assert len(context["candidate_months"]) == 2
    for left, right in zip(
        a["time_context"]["candidate_months"],
        b["time_context"]["candidate_months"],
    ):
        for key in ("effective_solar_year", "solar_month_number", "month_branch"):
            assert left[key] == right[key]
        for key in ("valid_from", "valid_until"):
            assert datetime.fromisoformat(left[key]) == datetime.fromisoformat(
                right[key]
            )
    # Also exercise a definite interval outside the guard; retain the numerical
    # one-second acceptance gate and all five original display timezones.
    far = (datetime.fromisoformat(t) + timedelta(seconds=10)).isoformat()
    a = layer(query_at=far, timezone_name=zone)
    b = layer(query_at=far)
    assert a["status"] == b["status"] == "complete"
    assert a["palaces"] == b["palaces"]
    for key in ("valid_from", "valid_until"):
        assert datetime.fromisoformat(a["time_context"][key]) == datetime.fromisoformat(
            b["time_context"][key]
        )


def test_actual_instants_control_a_repeated_wall_clock_boundary(monkeypatch):
    import fatebridge.core.fengshui.monthly_time as module

    zone = ZoneInfo("America/New_York")
    clocks = {
        "寒露": datetime(2021, 10, 8, 1, 30, tzinfo=zone),
        "立冬": datetime(2021, 11, 7, 1, 30, tzinfo=zone, fold=1),
        "大雪": datetime(2021, 12, 7, 1, 30, tzinfo=zone),
    }
    monkeypatch.setattr(
        module.almanac,
        "get_solar_terms_for_year",
        lambda year, zone: (
            [SimpleNamespace(name=n, moment=t) for n, t in clocks.items()]
            if year == 2021
            else []
        ),
    )
    monkeypatch.setattr(
        module,
        "solar_term_resolution",
        lambda year, name, zone: {
            "moment": clocks[name].isoformat(),
            "provider": "synthetic_fold_fixture",
            "approximate": False,
        },
    )
    first = solar_month_context(
        None,
        None,
        datetime(2021, 11, 7, 1, 45, tzinfo=zone, fold=0),
        "America/New_York",
    )
    second = solar_month_context(
        None,
        None,
        datetime(2021, 11, 7, 1, 45, tzinfo=zone, fold=1),
        "America/New_York",
    )
    assert first["solar_month_number"] == 9 and second["solar_month_number"] == 10


def test_missing_native_crossings_cannot_supply_month_boundaries(monkeypatch, request):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setattr(almanac, "swe", None)
    almanac.get_solar_terms_for_year.cache_clear()
    request.addfinalizer(almanac.get_solar_terms_for_year.cache_clear)
    for _, official in OFFICIAL:
        if official.year == 2026:
            with pytest.raises(EphemerisSourceError, match="no linear approximation"):
                calculate_monthly_stars(query_at=official.isoformat())
    for inputs in (
        {"query_at": "2026-10-20T12:00:00+08:00"},
        {"effective_solar_year": 2026, "solar_month_number": 9},
    ):
        with pytest.raises(EphemerisSourceError, match="no linear approximation"):
            calculate_monthly_stars(**inputs)


@pytest.mark.parametrize(
    "data",
    [
        {"effective_solar_year": 2026},
        {"solar_month_number": 1},
        {"effective_solar_year": 2026, "solar_month_number": 13},
        {"effective_solar_year": True, "solar_month_number": 1},
        {"effective_solar_year": 2026, "solar_month_number": True},
        {"query_at": "2026-01-10T12:00:00"},
        {
            "query_at": "2026-01-10T12:00:00+08:00",
            "effective_solar_year": 2026,
            "solar_month_number": 1,
        },
        {"lunar_month": 1},
        {"gregorian_month": 1},
    ],
)
def test_incomplete_conflicting_or_wrong_calendar_inputs_are_rejected(data):
    with pytest.raises(ValidationError):
        MonthlyRequest.model_validate(data)
    errors = list(
        Draft202012Validator(MonthlyRequest.model_json_schema()).iter_errors(data)
    )
    # Cross-field conditions are added to public JSON Schema in the contract.
    if (
        any(k in data for k in ["lunar_month", "gregorian_month"])
        or data.get("solar_month_number") in [True, 13]
        or data.get("effective_solar_year") is True
    ):
        assert errors


def test_missing_time_stays_partial_and_does_not_use_today():
    actual = layer()
    assert actual["status"] == "partial" and not actual["palaces"]
    assert "center_star_number" not in actual
    assert len(actual["position_reading"]["statements"]) == 1


def test_assess_reuses_query_only_when_monthly_is_explicitly_selected_and_never_guesses_from_year():
    automatic = assess(scene="workstation", query_at="2026-10-22T12:00:00+08:00")
    assert list(automatic["layers"]) == ["annual_stars"]
    monthly = assess(methods=["monthly_stars"], query_at="2026-10-22T12:00:00+08:00")
    assert monthly["layers"]["monthly_stars"]["center_star_number"] == 9
    partial = assess(methods=["monthly_stars"], effective_year=2026)
    assert (
        partial["status"] == "partial"
        and not partial["layers"]["monthly_stars"]["palaces"]
    )
    explicit = assess(monthly={"effective_solar_year": 2026, "solar_month_number": 9})
    assert list(explicit["layers"]) == ["monthly_stars"]


def test_monthly_does_not_overwrite_annual_or_natal_and_location_is_not_facing():
    base = {
        "methods": ["annual_stars", "xuankong_natal"],
        "effective_year": 2026,
        "xuankong": {
            "house": {"facing_degrees": 180, "north_reference": "magnetic"},
            "period": {
                "basis": "expert_confirmed",
                "period_number": 8,
                "evidence": "synthetic history",
            },
        },
    }
    prior = assess(**base)
    both = assess(
        **{
            **base,
            "methods": [*base["methods"], "monthly_stars"],
            "monthly": {"effective_solar_year": 2026, "solar_month_number": 9},
        }
    )
    for name in ["annual_stars", "xuankong_natal"]:
        assert both["layers"][name] == prior["layers"][name]
    result = assess(
        methods=["monthly_stars"],
        monthly={"effective_solar_year": 2026, "solar_month_number": 9},
        analyze_layout=True,
        placements=[
            {
                "object_id": "desk",
                "purpose": "desk",
                "location_direction": "N",
                "facing_direction": "S",
                "facing_role": "desk_facing",
            }
        ],
    )
    layout = result["layout_analysis"]
    assert len(layout["placement_findings"]) == 1
    finding = layout["placement_findings"][0]
    assert finding["direction"] == "N" and finding["monthly_star_number"] == 5
    assert finding["usage_interpretation"] == "not_covered_not_inauspicious"
    assert not layout["adjustment_options"] and not layout["element_relationships"]


def test_rest_mcp_cli_projection_and_trusted_monthly_receipts(
    monkeypatch, tmp_path, capsys
):
    data = {"query_at": "2027-01-10T12:00:00+08:00"}
    with rest_client(monkeypatch) as client:
        response = client.post("/api/fengshui/monthly_stars", json=data)
        assert response.status_code == 200, response.text
        rest = response.json()
        projected = client.post(
            "/api/fengshui/monthly_stars",
            json=data,
            params={
                "fields": [
                    "layers.monthly_stars.palaces.N.monthly_star_number",
                    "layers.monthly_stars.time_context",
                ],
                "strict_fields": "true",
                "include_snapshot_text": "false",
            },
        )
        assert projected.status_code == 200, projected.text
        assert (
            projected.json()["layers"]["monthly_stars"]["palaces"]["N"][
                "monthly_star_number"
            ]
            == 2
        )
    protocol = asyncio.run(mcp_call("monthly_stars", data))
    assert not protocol.is_error
    mcp = protocol.structured_content
    p = tmp_path / "monthly.json"
    p.write_text(json.dumps(data))
    assert run(["fengshui_monthly_stars", "--request-file", str(p)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert without_transport(rest) == without_transport(mcp) == without_transport(cli)
    for body in [rest, mcp, cli]:
        anchor = deepcopy(body["run_metadata"])
        checked = verify_monthly_reading(body, trusted_run_metadata=anchor)
        assert checked["status"] == "verified_served_fixed_monthly_reading", checked
        assert checked["monthly_position_coverage_verified"]
        bad = deepcopy(body)
        bad["layers"]["monthly_stars"]["position_reading"][
            "text"
        ] += " guaranteed fortune"
        bad["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in bad.items() if k != "run_metadata"}
        )
        assert (
            verify_monthly_reading(bad, trusted_run_metadata=anchor)["status"]
            == "rejected"
        )
        wrong = deepcopy(body)
        wrong["layers"]["monthly_stars"]["position_reading"]["statements"][1][
            "target_path"
        ] = "layers.monthly_stars.palaces.N"
        # A synthetic trusted receipt isolates semantic/coverage checks, not authentication.
        wrong["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in wrong.items() if k != "run_metadata"}
        )
        assert (
            verify_monthly_reading(
                wrong, trusted_run_metadata=deepcopy(wrong["run_metadata"])
            )["status"]
            == "rejected"
        )
    with rest_client(monkeypatch) as client:
        partial = client.post("/api/fengshui/monthly_stars", json={}).json()
    checked = verify_monthly_reading(
        partial, trusted_run_metadata=deepcopy(partial["run_metadata"])
    )
    assert (
        checked["status"] == "verified_served_fixed_monthly_reading"
        and not checked["monthly_position_coverage_verified"]
    )


def test_renderer_only_consumes_returned_fields_instead_of_recomputing_month_or_chart(
    monkeypatch,
):
    actual = confirmed(2026, 9)
    import fatebridge.core.fengshui.monthly as module

    monkeypatch.setattr(
        module,
        "solar_month_context",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("forbidden recalc")),
    )
    assert monthly_position_reading(actual) == actual["position_reading"]
