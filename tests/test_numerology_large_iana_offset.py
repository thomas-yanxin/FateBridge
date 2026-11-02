"""Actual historical offsets follow IANA rules, with independent UTC literals."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import normalize_numerology_utc_offset
from fatebridge.core.output_numerology import NumerologyEvidence
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from fatebridge.utils.civil_clock import (
    format_utc_offset,
    resolve_civil_clock,
    utc_instant,
)
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

FIXTURE = Path(__file__).parent / "fixtures/numerology_large_iana_offset_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
NEGATIVE = json.loads((FIXTURE / "negative-reference.json").read_text())
CASES = REFERENCE["cases"] + NEGATIVE["cases"]
PAIRS = [(HeluoRequest, build_heluo_result), (CanpingRequest, build_canping_result)]


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    empty = tmp_path / "empty-ephe"
    empty.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))


def payload(case):
    date, clock = case["wall"].split("T")
    return dict(
        date=date,
        time=clock,
        zone=case["zone"],
        birth_utc_offset=case["confirmed_offset"],
        gender="男",
        use_true_solar_time=False,
    )


def test_independent_references_and_primary_bytes_are_preserved():
    for name, seal, key in [
        ("reference.json", "reference-seal.json", "reference_sha256"),
        ("negative-reference.json", "negative-reference-seal.json", "sha256"),
    ]:
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == (
            json.loads((FIXTURE / seal).read_text())[key]
        )
        reference = json.loads((FIXTURE / name).read_text())
        assert reference["frozen_before_production_edits"]
        assert not reference["derived_with_fatebridge"]
        assert not reference["derived_with_zoneinfo"]
    for row in REFERENCE["source_files"]:
        assert hashlib.sha256((FIXTURE / row["path"]).read_bytes()).hexdigest() == (
            row["sha256"]
        )
    assert set(REFERENCE["other_large_offset_zones"]) == {
        "America/Juneau",
        "America/Metlakatla",
        "Asia/Manila",
        "Pacific/Palau",
    }
    assert not REFERENCE["requirements"]["whole_history_accuracy_established"]
    assert not REFERENCE["requirements"]["reality_prediction_validated"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_resolver_matches_independent_seconds_instants_and_fold_edges(case):
    local = resolve_civil_clock(
        datetime.fromisoformat(case["wall"]),
        case["zone"],
        case["confirmed_offset"],
    )
    assert local.tzinfo.key == case["zone"]
    assert local.fold == case["fold"]
    assert local.utcoffset().total_seconds() == case["offset_seconds"]
    assert format_utc_offset(local.utcoffset()) == case["confirmed_offset"]
    assert utc_instant(local).isoformat() == case["utc"]
    assert local.replace(tzinfo=None).isoformat() == case["wall"]
    assert timezone_rules_metadata(case["zone"])["iana_version"] == (
        REFERENCE["source_version"]
    )


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_numerology_preserves_confirmed_historical_instants(model, build, case):
    result = build(**model(**payload(case)).model_dump())
    evidence = result["numerology_evidence"]
    clock = evidence["birth_clock"]
    assert clock["birth_instant_utc"] == case["utc"]
    assert clock["civil_utc_offset_seconds"] == case["offset_seconds"]
    assert clock["civil_fold"] == case["fold"]
    assert clock["civil_time_ambiguous"] is case["ambiguous"]
    assert clock["timezone_spec"] == result["input_normalized"]["zone"] == case["zone"]
    assert clock["civil_utc_offset"] == case["confirmed_offset"]
    assert clock["requested_utc_offset"] == case["confirmed_offset"]
    assert f"已确认出生偏移：{case['confirmed_offset']}" in result["snapshot_text"]
    assert datetime.fromisoformat(clock["civil_datetime"]).replace(
        tzinfo=None
    ) == datetime.fromisoformat(case["wall"])
    NumerologyEvidence.model_validate(evidence)
    if build is build_canping_result:
        timing = result["canping_timing"]
        assert timing["timezone"] == case["zone"]
        assert utc_instant(datetime.fromisoformat(timing["start_at"])) >= (
            datetime.fromisoformat(case["utc"])
        )
        for a, b in zip(result["dayun"], result["dayun"][1:]):
            assert utc_instant(datetime.fromisoformat(a["end_at"])) == utc_instant(
                datetime.fromisoformat(b["start_at"])
            )


@pytest.mark.parametrize("boundary", REFERENCE["boundaries"], ids=lambda c: c["zone"])
@pytest.mark.parametrize("edge", ["fold_lower", "fold_upper"])
def test_24_hour_fold_requires_offset_only_inside_its_half_open_interval(
    boundary, edge
):
    wall = datetime.fromisoformat(boundary[edge])
    if edge == "fold_lower":
        with pytest.raises(ValueError, match="ambiguous"):
            resolve_civil_clock(wall, boundary["zone"])
    else:
        local = resolve_civil_clock(wall, boundary["zone"])
        assert format_utc_offset(local.utcoffset()) == boundary["offset_after"]


@pytest.mark.parametrize("gap", NEGATIVE["gaps"], ids=lambda c: c["zone"])
@pytest.mark.parametrize("side", [0, 1])
def test_confirmed_offsets_cannot_fill_a_24_hour_gap(gap, side):
    with pytest.raises(ValueError, match="nonexistent"):
        resolve_civil_clock(
            datetime.fromisoformat(gap["wall"]), gap["zone"], gap["offsets"][side]
        )


@pytest.mark.parametrize("offset", ["+15:00:01", "-15:00:01", "+23:59:59", "-23:59:59"])
def test_valid_syntax_cannot_invent_a_regional_offset_or_fixed_zone(offset):
    assert normalize_numerology_utc_offset(offset) == offset
    with pytest.raises(ValueError, match="不一致"):
        resolve_civil_clock(datetime(2026, 1, 1), "UTC", offset)
    with pytest.raises(ValueError):
        parse_timezone_name(offset)


@pytest.mark.parametrize(
    "offset", ["+24:00", "-24:00", "+25:00", "+15:60", "+15:59:60"]
)
def test_invalid_syntax_is_rejected_before_region_matching(offset):
    with pytest.raises(ValueError, match="范围"):
        normalize_numerology_utc_offset(offset)
    with pytest.raises(ValueError, match="范围"):
        resolve_civil_clock(datetime(2026, 1, 1), "UTC", offset)
    for model, _ in PAIRS:
        with pytest.raises(ValidationError):
            model(**{**payload(CASES[0]), "birth_utc_offset": offset})


@pytest.mark.parametrize(
    "offset",
    [
        timedelta(hours=24),
        timedelta(hours=-24),
        timedelta(hours=25),
        timedelta(microseconds=1),
    ],
)
def test_offset_formatter_rejects_invalid_magnitude_and_subseconds(offset):
    with pytest.raises(ValueError):
        format_utc_offset(offset)


def test_fixed_zone_input_policy_remains_at_15_hours():
    for text, seconds in [("+15:00", 54000), ("-15:00", -54000)]:
        assert parse_timezone_name(text).utcoffset(None).total_seconds() == seconds
        assert format_utc_offset(timedelta(seconds=seconds)) == text
