"""Independent astronomical clocks, real boundary cases and public parity."""

import asyncio
import csv
import hashlib
import importlib.util
import io
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from jsonschema import Draft202012Validator

from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import (
    EQUATION_OF_TIME_METHOD,
    calculate_equation_of_time_minutes,
    calculate_solar_time_adjustment,
)
from tests.fixtures.solar_reference import expected_solar_clock
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/bazi-solar-jpl-v1.json"
REFERENCE = json.loads(FIXTURE.read_text())
CASES = [
    {**case, "split": ref["split"]}
    for ref in REFERENCE["references"]
    for case in ref["rows"]
]


def test_external_reference_is_complete_frozen_and_separated_by_entire_year():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == FIXTURE.with_suffix(".sha256").read_text().strip()
    )
    assert len(CASES) == 96 and sum(c["split"] == "reserved" for c in CASES) == 72
    assert not set(REFERENCE["reserved_years"]) & set(REFERENCE["development_years"])
    assert REFERENCE["tolerance_seconds"] == 5
    for ref in REFERENCE["references"]:
        assert (
            hashlib.sha256(ref["response"]["result"].encode()).hexdigest()
            == ref["response_sha256"]
        )
        table = ref["response"]["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        for raw, recorded in zip(
            csv.reader(io.StringIO(table)), ref["rows"], strict=True
        ):
            dut1 = 0 if raw[4].strip() == "n.a." else float(raw[4])
            expected = ((float(raw[3]) - 12 + 12) % 24 - 12) * 60 - dut1 / 60
            assert recorded["equation_of_time_minutes"] == pytest.approx(
                expected, abs=1e-12
            )


def test_daily_sweep_covers_every_supported_date_with_the_original_tolerance():
    source = (
        Path(__file__).resolve().parents[1] / "scripts/audit_bazi_solar_accuracy.py"
    )
    spec = importlib.util.spec_from_file_location("bazi_solar_sweep_audit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows, manifest = module.load_daily_sweep()
    assert len(rows) == manifest["expected_total"] == 73414
    start = datetime(1900, 1, 1, 12, tzinfo=timezone.utc)
    assert all(
        datetime.fromisoformat(row["instant"]) == start + timedelta(days=i)
        for i, row in enumerate(rows)
    )
    result = module._summary(rows, manifest["tolerance_seconds"])
    assert result["failed_count"] == 0


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["instant"])
def test_full_instant_solar_equation_against_independent_jpl(case):
    actual = calculate_equation_of_time_minutes(datetime.fromisoformat(case["instant"]))
    assert (
        abs(actual - case["equation_of_time_minutes"]) * 60
        <= REFERENCE["tolerance_seconds"]
    )


def test_same_instant_same_equation_across_zones_and_fractional_day_is_retained():
    instant = datetime(2026, 9, 15, tzinfo=timezone.utc)
    original = calculate_equation_of_time_minutes(instant)
    assert original == calculate_equation_of_time_minutes(
        instant.astimezone(ZoneInfo("America/New_York"))
    )
    assert original == calculate_equation_of_time_minutes(
        instant.astimezone(ZoneInfo("Asia/Shanghai"))
    )
    assert (
        abs(
            original - calculate_equation_of_time_minutes(instant + timedelta(hours=12))
        )
        * 60
        > 1
    )
    assert (
        abs(
            calculate_equation_of_time_minutes(
                datetime(2024, 2, 29, 23, 59, tzinfo=timezone.utc)
            )
            - calculate_equation_of_time_minutes(
                datetime(2024, 3, 1, tzinfo=timezone.utc)
            )
        )
        * 60
        < 0.1
    )


def test_aware_instant_is_converted_instead_of_having_its_zone_replaced():
    utc = datetime(2026, 6, 15, 12, tzinfo=timezone.utc)
    local = utc.astimezone(ZoneInfo("America/New_York"))
    assert calculate_solar_time_adjustment(
        utc, "America/New_York", -74
    ) == calculate_solar_time_adjustment(
        local.replace(tzinfo=None), "America/New_York", -74
    )
    # The UTC instant resolves the DST fold; a naive NY 01:30 does not.
    fold = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)
    assert (
        calculate_solar_time_adjustment(fold, "America/New_York", -74)[
            "daylight_saving_minutes"
        ]
        == 0
    )
    with pytest.raises(ValueError, match="ambiguous"):
        calculate_solar_time_adjustment(
            datetime(2026, 11, 1, 1, 30), "America/New_York", -74
        )


INPUT = dict(
    birth_year=2026,
    birth_month=2,
    birth_day=15,
    birth_hour=9,
    birth_minute=14,
    gender="男",
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.1,
    use_true_solar_time=True,
    analysis_year=2028,
    analysis_month=4,
    analysis_day=1,
)


def test_independent_boundary_example_exposes_old_wrong_hour_without_moving_month():
    civil = datetime(2026, 2, 15, 9, 14)
    expected = expected_solar_clock(civil, "Asia/Shanghai", 120.1)
    assert expected.hour == 9 and expected.minute == 0
    # This deliberately documents the old bug, not the new oracle.
    n = civil.timetuple().tm_yday
    angle = 2 * math.pi * (n - 81) / 364
    old = civil + timedelta(
        minutes=0.4
        + 9.87 * math.sin(2 * angle)
        - 7.53 * math.cos(angle)
        - 1.5 * math.sin(angle)
    )
    assert old.hour == 8
    context = build_birth_computation_context(
        create_person_info(
            **{k: v for k, v in INPUT.items() if not k.startswith("analysis_")}
        )
    )
    assert context.birth_pillars["hour"][1] == "巳"
    assert (
        abs(
            (
                context.normalized_birth_time.corrected_datetime - expected
            ).total_seconds()
        )
        <= 5
    )
    assert (
        context.normalized_birth_time.as_dict()["equation_of_time_method"]
        == EQUATION_OF_TIME_METHOD
    )


@pytest.mark.parametrize("key", ["bazi_birth", "bazi_wealth", "bazi_personality"])
def test_corrected_clock_and_new_facts_match_rest_native_mcp_cli(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    response = rest.post(spec.rest_path, json=INPUT)
    code, local = call_cli(
        spec, INPUT, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, INPUT))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        if key == "bazi_birth":
            assert output["bazi_birth"]["four_pillars"]["hour"]["branch"] == "巳"
            assert output["bazi_birth"]["structure_profile"]["evidence_chain"][
                "classical_root_profile"
            ]
        if key == "bazi_wealth":
            assert (
                output["wealth_analysis"]["classical_context"]["formation_status"]
                == "not_adjudicated"
            )
            assert (
                output["wealth_analysis"]["wealth_structure"]["score_kind"]
                == "uncalibrated_rule_index"
            )


@pytest.mark.parametrize(
    "category,key,retired_claim,required_context",
    [
        ("wealth", "财库", "财库逢冲方能开库进财", "PDF43–45"),
        ("wealth", "食伤生财", "越做越旺", "PDF76–78"),
        ("personality", "强弱定刚柔", "日主强者主见足、外向主动", "计算模型"),
    ],
)
def test_public_knowledge_does_not_reintroduce_retired_calculation_claims(
    category, key, retired_claim, required_context, rest, tmp_path, capsys
):
    spec = SPECS["knowledge_read"]
    arguments = {"domain": "bazi", "category": category, "key": key}
    response = rest.post(spec.rest_path, json=arguments)
    code, local = call_cli(
        spec, arguments, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, arguments))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        text = json.dumps(output, ensure_ascii=False)
        assert retired_claim not in text
        assert required_context in text
