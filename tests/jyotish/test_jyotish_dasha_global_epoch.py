"""Whole-birth-epoch references were frozen before the numerical change."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.jyotish import vimshottari
from fatebridge.core.jyotish_dasha_levels import active_levels
from fatebridge.core.output_jyotish import DashaExactFraction, Vimshottari
from fatebridge.services.jyotish import calculate_vimshottari
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parents[1] / "fixtures"
PRIMARY_PATH = FIXTURES / "jyotish-dasha-global-primary.json"
BOUNDARY_PATH = FIXTURES / "jyotish-dasha-global-boundaries.json"
PRIMARY = json.loads(PRIMARY_PATH.read_text())
BOUNDARIES = json.loads(BOUNDARY_PATH.read_text())
BIRTH = datetime.fromisoformat(PRIMARY["birth_utc"])
TARGET = datetime.fromisoformat(PRIMARY["analysis_utc"])


def microseconds(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def test_reference_inputs_and_precision_target_predate_implementation():
    assert (
        hashlib.sha256(PRIMARY_PATH.read_bytes()).hexdigest()
        == "b196d7d600c44c021eab440457218ebe520a59b8bd23d3a076514f9ebe98e974"
    )
    assert (
        hashlib.sha256(BOUNDARY_PATH.read_bytes()).hexdigest()
        == "cc6eca17cc86a35ea62bf5ab6d7d5209f31c8083a9de755ba942ffbe717bd3a3"
    )
    assert len(PRIMARY["rows"]) == 5211
    assert len(BOUNDARIES["rows"]) == 348
    assert PRIMARY["real_event_cases"] == BOUNDARIES["real_event_cases"] == 0


@pytest.mark.parametrize("case", PRIMARY["rows"])
def test_every_anchor_and_all_six_levels_equal_common_epoch_reference(case):
    result = vimshottari(
        BIRTH,
        float.fromhex(case["moon_hex"]),
        TARGET,
        year_basis=case["year_basis"],
        dasha_depth=6,
    )
    balance = result["birth_balance"]
    q = result["time_quantization"]
    assert balance["major_start"] == case["major_start"]
    assert balance["major_end"] == case["major_end"]
    assert result["timeline_scope"]["cycle_index"] == case["cycle_index"]
    assert q["reference_epoch_utc"] == PRIMARY["birth_utc"]
    assert [
        q["source_mansion_fraction_exact"][name]
        for name in ["numerator", "denominator"]
    ] == case["fraction_elapsed_exact"]
    assert q["method_id"] == "fatebridge_birth_epoch_rational_microseconds_v1"
    assert balance["elapsed_microseconds"] == microseconds(
        BIRTH - datetime.fromisoformat(case["major_start"])
    )
    assert balance["remaining_microseconds"] == microseconds(
        datetime.fromisoformat(case["major_end"]) - BIRTH
    )
    full_years = Fraction(
        microseconds(
            datetime.fromisoformat(case["major_end"])
            - datetime.fromisoformat(case["major_start"])
        ),
        q["year_microseconds"],
    )
    fraction = Fraction(*map(int, case["fraction_elapsed_exact"]))
    assert balance["elapsed_years"] == float(fraction * full_years)
    assert balance["remaining_years"] == float((1 - fraction) * full_years)
    for actual, expected in zip(
        result["subdivisions"]["current_levels"], case["current_levels"], strict=True
    ):
        assert {name: actual[name] for name in ["lord", "start", "end"]} == {
            name: expected[name] for name in ["lord", "start", "end"]
        }
    for name, expected in zip(
        ["current_major", "current_sub"], case["current_levels"][:2], strict=True
    ):
        assert all(
            result[name][field] == expected[field] for field in ["lord", "start", "end"]
        )
    epoch = result["subdivisions"]["epoch_context"]
    assert epoch["reference_epoch_utc"] == PRIMARY["birth_utc"]
    assert [
        epoch["complete_major_start_offset_microseconds_fraction"][name]
        for name in ["numerator", "denominator"]
    ] == case["current_levels"][0]["exact_start_offset_us"]


@pytest.mark.parametrize("case", BOUNDARIES["rows"])
def test_every_predeclared_boundary_probe_uses_the_same_global_quantizer(case):
    result = vimshottari(
        BIRTH,
        float.fromhex(case["moon_hex"]),
        datetime.fromisoformat(case["analysis_utc"]),
        year_basis=case["year_basis"],
        dasha_depth=6,
    )
    actual = result["subdivisions"]["current_levels"]
    assert [
        {name: row[name] for name in ["lord", "start", "end"]} for row in actual
    ] == case["current_levels"]


@pytest.mark.parametrize("index", range(0, 5211, 97))
def test_default_two_levels_and_deep_levels_share_the_complete_epoch(index):
    case = PRIMARY["rows"][index]
    shallow = vimshottari(
        BIRTH, float.fromhex(case["moon_hex"]), TARGET, year_basis=case["year_basis"]
    )
    deep = vimshottari(
        BIRTH,
        float.fromhex(case["moon_hex"]),
        TARGET,
        year_basis=case["year_basis"],
        dasha_depth=6,
    )
    assert "subdivisions" not in shallow
    for field in [
        "current_major",
        "current_sub",
        "birth_balance",
        "time_quantization",
        "timeline",
        "timeline_scope",
    ]:
        assert shallow[field] == deep[field]


def test_exact_epoch_offsets_cannot_contradict_the_supplied_major_start():
    target = BIRTH + timedelta(days=1)
    for extra in [
        {"_reference_epoch": BIRTH},
        {"_major_start_offset_us": Fraction(1, 3)},
        {
            "_reference_epoch": BIRTH.replace(tzinfo=None),
            "_major_start_offset_us": Fraction(1, 3),
        },
        {"_reference_epoch": BIRTH, "_major_start_offset_us": 0.0},
    ]:
        with pytest.raises(ValueError):
            active_levels(
                "Sun", BIRTH, target, year_basis="savana_360", depth=6, **extra
            )
    with pytest.raises(ValueError, match="contradicts"):
        active_levels(
            "Sun",
            BIRTH + timedelta(microseconds=1),
            target,
            year_basis="savana_360",
            depth=6,
            _reference_epoch=BIRTH,
            _major_start_offset_us=Fraction(1, 3),
        )
    valid = active_levels(
        "Sun",
        BIRTH,
        target,
        year_basis="savana_360",
        depth=6,
        _reference_epoch=BIRTH,
        _major_start_offset_us=Fraction(-1, 3),
    )
    assert valid["epoch_context"][
        "complete_major_start_offset_microseconds_fraction"
    ] == {"numerator": "-1", "denominator": "3"}


@pytest.mark.parametrize(
    "value",
    [
        {"numerator": 1, "denominator": "3"},
        {"numerator": "01", "denominator": "3"},
        {"numerator": "1", "denominator": "0"},
    ],
)
def test_exact_fraction_contract_retains_strings_and_rejects_lossy_substitutions(value):
    with pytest.raises(ValidationError):
        DashaExactFraction.model_validate(value)


def test_actual_service_records_each_endpoint_epoch_and_separate_policy_source():
    body = calculate_vimshottari(
        **astro_payload(),
        analysis_year=2026,
        divisions=[],
        birth_time_uncertainty_minutes=1,
        dasha_depth=6,
    )
    vim = body["vimshottari"]
    origin = datetime.fromisoformat(body["person_info"]["utc_datetime"])
    for sample in vim["birth_time_sensitivity"]["samples"]:
        assert datetime.fromisoformat(
            sample["time_quantization"]["reference_epoch_utc"]
        ) == origin + timedelta(seconds=sample["offset_seconds"])
        assert (
            sample["subdivisions"]["epoch_context"]["reference_epoch_utc"]
            == sample["time_quantization"]["reference_epoch_utc"]
        )
    sources = {row["id"]: row for row in body["india"]["rulesets"]}
    policy = vim["time_quantization"]["source_id"]
    assert sources[policy]["source_kind"] == "implementation_policy"
    assert any(row["source_id"] == policy for row in body["india"]["rule_trace"])
    typed = Vimshottari.model_validate(vim).model_dump(exclude_unset=True)
    assert typed["time_quantization"] == vim["time_quantization"]
    assert typed["subdivisions"] == vim["subdivisions"]
