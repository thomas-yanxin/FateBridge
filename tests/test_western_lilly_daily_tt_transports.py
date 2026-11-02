"""C04's covered nominal horary needs no UT1 for the next TT day's motion."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.test_western_event_clock_transports import surfaces


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_c04_last_nominal_epoch_computes_lilly_daily_motion_on_all_protocols(
    zodiac, rest, tmp_path, capsys
):
    values = surfaces(
        "astro_horary",
        dict(
            question_year=2026,
            question_month=9,
            question_day=19,
            question_hour=0,
            timezone_name="UTC",
            longitude=0,
            latitude=40,
            ut1_source="iers_c04",
            zodiac_type=zodiac,
            category="career",
        ),
        [
            "clock_conversion",
            "horary.calculation_basis",
            "horary.fortitudes.physical_inputs",
            "horary.fortitudes.summary",
            "horary.fortitudes.full_original_text_acceptance",
            "horary.verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        clock = value["clock_conversion"]
        horary = value["horary"]
        assert clock["ut1_reference"]["instant_value_kind"] == "published_daily_sample"
        assert clock["julian_day_tt"] == horary["calculation_basis"]["julian_day_tt"]
        ledger = horary["fortitudes"]
        data = ledger["physical_inputs"]
        assert data["status"] == "computed"
        assert data["day_interval_tt"] == [
            clock["julian_day_tt"],
            clock["julian_day_tt"] + 1,
        ]
        assert len(data["motion"]) == 7
        assert all(
            row["status"] == "computed" and len(row["samples"]) == 5
            for row in data["motion"].values()
        )
        assert all(row["row_count"] == 41 for row in ledger["summary"].values())
        assert ledger["full_original_text_acceptance"] is False
        assert horary["verdict"] == "uncertain"


def test_uncovered_nominal_ut1_is_still_rejected_on_all_protocols(
    rest, tmp_path, capsys
):
    spec = SPECS["astro_horary"]
    args = dict(
        question_year=2026,
        question_month=9,
        question_day=20,
        question_hour=0,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
    )
    response = rest.post(spec.rest_path, json=args)
    code, cli = call_cli(spec, args, tmp_path, capsys)
    mcp = asyncio.run(native(spec, args))
    # Runtime coverage validation uses the existing 400 envelope; schema
    # validation uses 422. The TT-only change must not make this request valid.
    assert response.status_code == 400 and code != 0 and mcp.is_error
    assert response.json()["error_code"] == cli["error_code"] == "validation_error"
    assert response.json()["retryable"] is False and cli["retryable"] is False
    assert "horary" not in cli
