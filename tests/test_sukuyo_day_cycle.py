"""Day labels add source checks without changing old month facts or boundaries."""

import base64
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_historical_calendar as historical
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.validation.sukuyo_historical_sources import (
    _day_cycle_errors,
    parse_naoj,
    printed_day_ganzhi,
)
from scripts.check_sukuyo_documentary_dates import verify_documentary_controls
from scripts.check_sukuyo_historical_daily import verify_daily_controls


@pytest.mark.parametrize(
    "value", ["甲丑 (invalid)", "己卯", "己卯 (reading) extra", "丁辰 (invalid)"]
)
def test_malformed_or_non_cycle_source_labels_are_rejected(value):
    with pytest.raises(ValueError, match="sexagenary"):
        printed_day_ganzhi(value)


def test_syntactically_valid_one_day_source_shift_is_detected():
    facts = json.loads(
        (
            Path(__file__).parent / "fixtures/sukuyo-historical-edge-probes.json"
        ).read_bytes()
    )
    record = next(row for row in facts["naoj"] if row["lunar_year"] == 806)
    months = parse_naoj(base64.b64decode(record["raw_csv_base64"]), 806)
    assert not _day_cycle_errors(months, months[0])
    changed = replace(
        months[1], day_ganzhi="甲子" if months[1].day_ganzhi != "甲子" else "乙丑"
    )
    errors = _day_cycle_errors([months[0], changed, *months[2:]], months[0])
    assert len(errors) == 1 and errors[0]["ordinal"] == changed.ordinal


def test_direct_daily_ganzhi_facts_keep_all_source_disagreements():
    result = verify_daily_controls()
    assert result["naoj_daily_printed_ganzhi_checked"] == 225
    assert not result["naoj_daily_printed_ganzhi_mismatches"]
    assert result["hutime_direct_disagreement_dates"] == 210
    assert len(result["separate_post_reform_legal_calendar_controls"]) == 1


def test_every_printed_ganzhi_heading_in_the_bounded_chronicle_month_is_retained():
    result = verify_documentary_controls()
    assert result["printed_controls_checked"] == 4
    assert result["bounded_month_count"] == 1
    assert [row["lunar_fields"][2] for row in result["controls"]] == [1, 5, 11, 20]
    assert not result["mismatches"]
    conflict = result["retained_secondary_paper_conflicts"][0]
    assert conflict["paper_day_ganzhi"] == "己卯"
    assert conflict["calculated_day_ganzhi"] == "庚辰"
    assert conflict["paper_and_printed_chronicle_disagree"]
    assert not conflict["engine_day_shift_applied"]
    assert not result["independent_original_manuscript_collation"]


def test_documentary_control_keeps_engine_errors_in_the_report(monkeypatch):
    from scripts import check_sukuyo_documentary_dates as checker

    def corrupted(*args, **kwargs):
        result = calendar_mansion(*args, **kwargs)
        result["calendar_reference"]["day_ganzhi_reference"]["name"] = "壬寅"
        return result

    monkeypatch.setattr(checker, "calendar_mansion", corrupted)
    report = checker.verify_documentary_controls()
    assert report["printed_controls_checked"] == 4
    assert len(report["mismatches"]) == 4


def test_documentary_capture_hash_is_checked_before_calendar_calculation(tmp_path):
    from scripts import check_sukuyo_documentary_dates as checker

    fixture = json.loads(checker.FIXTURE.read_bytes())
    (tmp_path / fixture["captured_source_files"][0]["file"]).write_bytes(
        b"changed source"
    )
    with pytest.raises(ValueError, match="fingerprint changed"):
        verify_documentary_controls(capture_dir=tmp_path)


def test_reference_midnight_is_explicit_and_is_not_a_bazi_or_ancient_boundary():
    before = calendar_mansion(
        "0903-07-12",
        time_text="23:59:59",
        zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    after = calendar_mansion(
        "0903-07-13",
        time_text="00:00:00",
        zone="+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert before["calendar_reference"]["day_ganzhi_reference"]["name"] == "己卯"
    ref = after["calendar_reference"]["day_ganzhi_reference"]
    assert ref["name"] == "庚辰"
    assert ref["reference_boundary"] == "fixed_utc09_civil_midnight"
    assert (
        not ref["bazi_day_pillar_evaluated"]
        and not ref["historical_day_boundary_accepted"]
    )
    assert "日干支为庚辰" in day_evidence(after)["reading_text"]
    shifted_zone = calendar_mansion(
        "0903-07-12",
        time_text="23:00:00",
        zone="+08:00",
        calendar_basis="japanese_naoj_historical_utc09",
    )
    assert shifted_zone["calendar_reference"]["day_ganzhi_reference"] == ref


@pytest.mark.parametrize(
    "key,value",
    [
        ("civil_ordinal", True),
        ("civil_ordinal", 1),
        ("day_ganzhi", "甲丑"),
        ("source_response_sha256", "0" * 64),
        ("source_lunar_year_query", True),
    ],
)
def test_anchor_tampering_cannot_silently_change_reference_day_labels(
    tmp_path, monkeypatch, key, value
):
    data = json.loads(historical.SOURCE.read_bytes())
    data["day_cycle_anchor"][key] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(historical, "SOURCE", path)
    with pytest.raises(ValueError, match="day-cycle anchor"):
        historical.date_reference(date(903, 7, 13))
