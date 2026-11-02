"""Original Unicode inputs, exact quantization and native ISO offset transport."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Inexact, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.native_execution import decode, encode
from fatebridge.core.human_design_cycles import reference_epoch
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.utils.civil_time import (
    datetime_fromisoformat_preserving_offset,
    utc_calendar,
)
from fatebridge.utils.timezones import parse_timezone_name, timezone_rules_metadata

PATH = (
    Path(__file__).parent
    / "fixtures/human_design_decimal_offset_v1/precision-followup-plan.json"
)
PLAN = json.loads(PATH.read_text())


def test_followup_counterexamples_and_original_shared_oracle_are_frozen():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "3483084e17cf4a23dd7a09646c16dbdd572cdc5ae9564dee61f5d9916f63ea57"
    )
    root = Path(__file__).resolve().parents[1]
    for name, digest in PLAN["unchanged_existing_astrodice_oracle_sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert len(PLAN["unicode_cases"]) == 6
    assert all(not c["ascii_only_repair_accepted"] for c in PLAN["unicode_cases"])
    assert PLAN["before_birth_reference"]["before_accepted"] is True


@pytest.mark.parametrize("case", PLAN["unicode_cases"], ids=lambda c: c["id"])
def test_all_original_unicode_aliases_retain_their_exact_offset(case):
    value = parse_timezone_name(case["offset"]).utcoffset(None)
    ticks = (value.days * 86400 + value.seconds) * 1000000 + value.microseconds
    assert ticks == case["expected_offset_microseconds"]


@pytest.mark.parametrize("case", PLAN["rounding_cases"], ids=lambda c: c["id"])
def test_independent_fraction_rounding_facts_and_visible_bound(case):
    if not case["accepted_in_original_scope"]:
        with pytest.raises(ValueError):
            parse_timezone_name(case["offset"])
        return
    value = parse_timezone_name(case["offset"]).utcoffset(None)
    ticks = (value.days * 86400 + value.seconds) * 1000000 + value.microseconds
    assert ticks == case["expected_offset_microseconds"]
    assert abs(Fraction(ticks) - Fraction(case["offset"]) * 3600000000) <= Fraction(
        1, 2
    )
    metadata = timezone_rules_metadata(case["offset"])
    assert (
        metadata.get("decimal_hour_rounding") == "nearest_microsecond_ties_even"
    ) == case["quantized"]


@pytest.mark.parametrize("case", PLAN["iso_cases"], ids=lambda c: c["id"])
def test_iso_reference_and_native_envelope_preserve_the_actual_instant(case):
    moment = datetime(
        1980,
        7,
        1,
        12,
        tzinfo=timezone(timedelta(microseconds=case["offset_microseconds"])),
    )
    restored = decode(encode(moment))
    assert restored.utcoffset() == moment.utcoffset()
    assert restored == moment
    assert datetime_fromisoformat_preserving_offset(case["iso"]) == moment
    label, _ = reference_epoch(case["iso"])
    assert datetime.fromisoformat(label) == datetime.fromisoformat(
        case["expected_utc_label"]
    )


def test_decimal_resolution_does_not_depend_on_caller_decimal_context():
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        value = parse_timezone_name("+5.500010000000000000001").utcoffset(None)
    assert value == timedelta(microseconds=19800036000)


@pytest.mark.parametrize("year", [1, 9999])
@pytest.mark.parametrize("micros", [-36000, 36000])
def test_native_offset_roundtrip_does_not_rebase_or_clip_calendar_extremes(
    year, micros
):
    moment = datetime(
        year,
        1 if year == 1 else 12,
        1 if year == 1 else 31,
        tzinfo=timezone(timedelta(microseconds=micros)),
    )
    restored = decode(encode(moment))
    assert restored.utcoffset() == moment.utcoffset()
    assert utc_calendar(restored) == utc_calendar(moment)


def test_prebirth_iso_offset_cannot_be_accepted_as_equal_to_birth():
    with pytest.raises(ValueError):
        HumanDesignRequest(**PLAN["before_birth_reference"]["input"])


def test_iso_fix_does_not_invent_a_timezone_for_a_naive_timestamp():
    assert (
        datetime_fromisoformat_preserving_offset("1980-07-01T12:00:00.036").tzinfo
        is None
    )


@pytest.mark.parametrize("micros", [-36000, 36000])
def test_actual_fresh_native_positions_receive_the_same_subsecond_instant(micros):
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.jyotish import positions

    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        preserve_instant=True,
    )
    local = datetime(2000, 1, 1, 12, tzinfo=timezone(timedelta(microseconds=micros)))
    actual = positions(birth, moment=local)
    expected = positions(birth, moment=local.astimezone(timezone.utc))
    assert actual["native_execution_context"]["mechanism"] == "fresh_exec_process"
    assert actual == expected
