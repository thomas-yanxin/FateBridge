"""Independent published labels, calendar boundaries and no epoch guessing."""

import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest
import swisseph as swe

from fatebridge.core import guolao_calendar_date_bridge as bridge
from fatebridge.core.ephemeris_runtime import ephemeris_call
from fatebridge.validation.guolao_calendar_date_bridge import audit_calendar_date_bridge

ROOT = Path(__file__).parents[2]
FIXTURES = Path(__file__).parents[1] / "fixtures/guolao-calendar-date-bridge-v1"
SOURCE = json.loads(bridge.DATA.read_bytes())
MODEL = bridge.load_calendar_date_bridge(bridge.PROFILE)


@pytest.mark.parametrize("row", SOURCE["hko31_literal_day_labels"])
def test_all_literal_hko_labels_match_the_preselected_modern_anchor(row):
    label = MODEL.label(
        *map(int, row["gregorian_date"].split("-")), calendar=bridge.CALENDARS[0]
    )
    assert label["ganzhi"] == row["printed_ganzhi"]
    assert label["physical_julian_day"] is None
    assert label["timezone"] is None


@pytest.mark.parametrize("row", SOURCE["usno5_published_examples"])
def test_published_usno_numeric_examples_without_live_api_claim(row):
    serial = bridge.calendar_label_noon_jdn(*row["date"], calendar=row["calendar"])
    assert F(serial) - F(1, 2) + F(row["ut1_fraction"]) == F(row["jd"])


@pytest.mark.parametrize(
    "calendar,flag", tuple(zip(bridge.CALENDARS, (swe.GREG_CAL, swe.JUL_CAL)))
)
@pytest.mark.parametrize(
    "label",
    [
        (1, 1, 1),
        (1280, 12, 14),
        (1280, 12, 21),
        (1500, 3, 1),
        (1582, 10, 4),
        (1582, 10, 15),
        (1598, 12, 22),
        (1607, 12, 22),
        (1700, 3, 1),
        (1900, 3, 1),
        (2000, 2, 29),
        (2016, 10, 9),
        (9999, 12, 31),
    ],
)
def test_integer_calendar_roundtrip_against_separate_swiss_implementation(
    calendar, flag, label
):
    serial = bridge.calendar_label_noon_jdn(*label, calendar=calendar)
    assert serial == ephemeris_call("julday", *label, 12.0, flag)
    assert bridge.calendar_label_from_noon_jdn(serial, calendar=calendar) == list(label)


def test_reform_labels_are_explicit_and_no_automatic_switch_or_ten_day_skip():
    julian = bridge.calendar_label_noon_jdn(1582, 10, 4, calendar=bridge.CALENDARS[1])
    gregorian = bridge.calendar_label_noon_jdn(
        1582, 10, 15, calendar=bridge.CALENDARS[0]
    )
    assert gregorian - julian == 1
    assert bridge.calendar_label_from_noon_jdn(
        julian, calendar=bridge.CALENDARS[0]
    ) == [1582, 10, 14]
    assert (
        bridge.calendar_label_noon_jdn(1582, 10, 5, calendar=bridge.CALENDARS[0])
        == gregorian - 10
    )
    assert (
        MODEL.label(1280, 12, 14, calendar=bridge.CALENDARS[0])["ganzhi"]
        != MODEL.label(1280, 12, 14, calendar=bridge.CALENDARS[1])["ganzhi"]
    )
    # Mathematical proleptic Julian leap years, not an early Roman usage claim.
    assert bridge.calendar_label_from_noon_jdn(
        bridge.calendar_label_noon_jdn(4, 2, 29, calendar=bridge.CALENDARS[1]),
        calendar=bridge.CALENDARS[1],
    ) == [4, 2, 29]


@pytest.mark.parametrize(
    "label",
    [
        (0, 1, 1),
        (10000, 1, 1),
        (2016, 0, 1),
        (2016, 13, 1),
        (2016, 1, 0),
        (2016, 4, 31),
        (1700, 2, 29),
        (1900, 2, 29),
    ],
)
def test_gregorian_invalid_labels_rejected(label):
    with pytest.raises(ValueError):
        bridge.calendar_label_noon_jdn(*label, calendar=bridge.CALENDARS[0])


@pytest.mark.parametrize("value", [True, 1.0, "1", F(1)])
def test_no_implicit_casts_in_date_serial_or_year(value):
    with pytest.raises(TypeError):
        bridge.calendar_label_noon_jdn(2016, 10, value, calendar=bridge.CALENDARS[0])
    with pytest.raises(TypeError):
        bridge.calendar_label_from_noon_jdn(value, calendar=bridge.CALENDARS[1])
    with pytest.raises(TypeError):
        MODEL.winter_candidates(source_year=value, search_policy=bridge.SEARCH_POLICY)


def test_julian_leap_rules_and_declared_ranges():
    assert bridge.calendar_label_noon_jdn(
        1900, 2, 29, calendar=bridge.CALENDARS[1]
    ) + 1 == bridge.calendar_label_noon_jdn(1900, 3, 1, calendar=bridge.CALENDARS[1])
    for label in ((1901, 2, 29), (1900, 2, 30), (10000, 1, 1)):
        with pytest.raises(ValueError):
            bridge.calendar_label_noon_jdn(*label, calendar=bridge.CALENDARS[1])
    for calendar in bridge.CALENDARS:
        for serial in (-1, 10**10):
            with pytest.raises(ValueError):
                bridge.calendar_label_from_noon_jdn(serial, calendar=calendar)
    with pytest.raises(ValueError, match="明确"):
        MODEL.label(1582, 10, 4, calendar="automatic_1582")


@pytest.mark.parametrize(
    "source_year,gregorian,julian",
    [
        (1281, [1280, 12, 21], [1280, 12, 14]),
        (1599, [1598, 12, 22], [1598, 12, 12]),
        (1608, [1607, 12, 22], [1607, 12, 12]),
    ],
)
def test_calculated_candidates_are_conditional_and_not_external_observations(
    source_year, gregorian, julian
):
    # These are regression values from first-domain-audit, not frozen source labels.
    result = MODEL.winter_candidates(
        source_year=source_year, search_policy=bridge.SEARCH_POLICY
    )
    assert result["status"] == "conditional_unique_date_label"
    assert result["candidates"][0]["gregorian_date"] == gregorian
    assert result["candidates"][0]["julian_date"] == julian
    assert not result["source_midnight_to_published_date_label_continuity_accepted"]
    assert not result["modern_epoch_calibrated"]
    assert not result["used_in_native_birth_chart"]
    assert result["physical_julian_day"] is None


def test_no_match_does_not_move_anchor_or_expand_window(monkeypatch):
    context = bridge.guolao_year_labels.shoushi_year_context(source_year=1599)
    seen = {
        MODEL.label(1598, 12, d, calendar=bridge.CALENDARS[0])["ganzhi"]
        for d in range(1, 32)
    }
    missing = next(
        bridge.STEMS[i % 10] + bridge.BRANCHES[i % 12]
        for i in range(60)
        if bridge.STEMS[i % 10] + bridge.BRANCHES[i % 12] not in seen
    )
    monkeypatch.setattr(
        bridge.guolao_year_labels,
        "shoushi_year_context",
        lambda **kw: {**context, "winter_sexagenary_day": missing},
    )
    result = MODEL.winter_candidates(
        source_year=1599, search_policy=bridge.SEARCH_POLICY
    )
    assert result["status"] == "no_match"
    assert result["candidates"] == []
    assert result["searched_gregorian_date_range"] == [[1598, 12, 1], [1598, 12, 31]]
    assert (
        MODEL.source_counter_label(
            F(42),
            source_year=1599,
            search_policy=bridge.SEARCH_POLICY,
            counter_basis=bridge.COUNTER_BASIS,
        )["conditional_date_labels"]
        is None
    )


def test_unwrapped_counter_preserves_fraction_and_before_winter_midnight():
    for counter, offset, expected in [
        (F(42), 0, [1598, 12, 22]),
        (F("130.98875"), 88, [1599, 3, 20]),
        (F(131), 89, [1599, 3, 21]),
        (F(318), 276, [1599, 9, 24]),
        (F(319), 277, [1599, 9, 25]),
        (F(407), 365, [1599, 12, 22]),
    ]:
        result = MODEL.source_counter_label(
            counter,
            source_year=1599,
            search_policy=bridge.SEARCH_POLICY,
            counter_basis=bridge.COUNTER_BASIS,
        )
        assert result["integer_day_offset_from_source_winter_day"] == offset
        assert result["conditional_date_labels"]["gregorian_date"] == expected
        assert F(result["source_fraction_of_day_exact"]) == counter % 1
        assert not result["source_fraction_converted_to_modern_clock"]
    for counter in (F("10.98875"), F(41), F(408)):
        with pytest.raises(ValueError, match="窗口"):
            MODEL.source_counter_label(
                counter,
                source_year=1599,
                search_policy=bridge.SEARCH_POLICY,
                counter_basis=bridge.COUNTER_BASIS,
            )
    with pytest.raises(TypeError):
        MODEL.source_counter_label(
            42.0,
            source_year=1599,
            search_policy=bridge.SEARCH_POLICY,
            counter_basis=bridge.COUNTER_BASIS,
        )
    with pytest.raises(ValueError, match="未取模"):
        MODEL.source_counter_label(
            F(42),
            source_year=1599,
            search_policy=bridge.SEARCH_POLICY,
            counter_basis="modulo60",
        )


@pytest.mark.parametrize("year", [1280, 10000])
def test_source_year_bounds_and_search_policy_not_inferred(year):
    with pytest.raises(ValueError):
        MODEL.winter_candidates(source_year=year, search_policy=bridge.SEARCH_POLICY)
    with pytest.raises(ValueError, match="移锚"):
        MODEL.winter_candidates(source_year=1599, search_policy="nearest_match")


@pytest.mark.parametrize(
    "key",
    ["date", "calendar", "sexagenary_index", "printed_ganzhi", "source_pdf_sha256"],
)
def test_changed_anchor_fails_instead_of_fitting_historical_example(
    tmp_path, monkeypatch, key
):
    source = json.loads(bridge.DATA.read_bytes())
    source["anchor"][key] = {
        "date": [2016, 10, 10],
        "calendar": bridge.CALENDARS[1],
        "sexagenary_index": 1,
        "printed_ganzhi": "乙丑",
        "source_pdf_sha256": "changed",
    }[key]
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(source))
    monkeypatch.setattr(bridge, "DATA", changed)
    with pytest.raises(ValueError, match="固定纪日锚点"):
        bridge.load_calendar_date_bridge(bridge.PROFILE)


def test_frozen_artifacts_and_audit_do_not_inflate_reference_counts():
    reference = json.loads((FIXTURES / "reference.json").read_bytes())
    assert (
        reference["data_sha256"] == hashlib.sha256(bridge.DATA.read_bytes()).hexdigest()
    )
    for item in reference["artifacts"]:
        blob = (FIXTURES / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    assert reference["anchor_selected_before_historical_candidate_calculation"]
    assert not reference["USNO_live_API_reference_obtained"]
    assert not reference["Sinica_live_conversion_obtained"]
    report = audit_calendar_date_bridge()
    assert all(x["matches"] for x in report["hko31_label_checks"])
    assert all(x["matches"] for x in report["usno5_published_document_checks"])
    assert report["hko_published_anchor_count"] == 1
    assert not report["hko_remaining30_are_unseen_holdout"]
    assert not report["four_axis_perfect_scores_established"]


@pytest.mark.parametrize(
    "args",
    [
        [],
        [
            "label",
            "--profile",
            bridge.PROFILE,
            "--calendar",
            "automatic_1582",
            "--date",
            "1582",
            "10",
            "4",
        ],
        [
            "counter",
            "--profile",
            bridge.PROFILE,
            "--source-year",
            "1599",
            "--search-policy",
            bridge.SEARCH_POLICY,
            "--counter-basis",
            bridge.COUNTER_BASIS,
            "--counter",
            "10.98875",
        ],
    ],
)
def test_cli_invalid_inputs_are_errors_not_empty_success(monkeypatch, capsys, args):
    path = ROOT / "scripts/guolao/audit_guolao_calendar_date_bridge.py"
    monkeypatch.setattr(sys, "argv", [str(path), *args])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(path))["main"]()
    assert error.value.code == 2
    assert not capsys.readouterr().out


def test_actual_cli_audit_matches_domain_audit(monkeypatch, capsys):
    path = ROOT / "scripts/guolao/audit_guolao_calendar_date_bridge.py"
    monkeypatch.setattr(sys, "argv", [str(path), "audit"])
    assert runpy.run_path(str(path))["main"]() == 0
    assert json.loads(capsys.readouterr().out) == audit_calendar_date_bridge()
