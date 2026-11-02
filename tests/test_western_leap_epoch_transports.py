"""Actual REST/native MCP/CLI charts for the same inserted-second epoch."""

import json
from pathlib import Path

import pytest

from tests.ephemeris_case_runtime import native_ephemeris_files_module

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


from tests.test_agentic_nested_outputs import rest
from tests.test_western_event_clock_transports import surfaces

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/western-leap-epoch-reference.json").read_text()
)


@pytest.mark.parametrize(
    "tool,prefix,body,basis",
    [
        ("astro_election", "candidate", "election", "local_mean_solar"),
        ("astro_election", "candidate", "election", "local_apparent_solar"),
        ("astro_horary", "question", "horary", "local_mean_solar"),
    ],
)
def test_leap_epoch_is_retained_on_rest_mcp_cli(
    tool, prefix, body, basis, rest, tmp_path, capsys
):
    lon = (
        0
        if basis == "local_mean_solar"
        else REFERENCE["reused_ut1_epoch"]["synthetic_lat_longitude"]
    )
    values = surfaces(
        tool,
        {
            prefix + "_year": 1977,
            prefix + "_month": 12,
            prefix + "_day": 31,
            prefix + "_hour": 12,
            prefix + "_hour_origin": "noon",
            prefix + "_clock_basis": basis,
            "longitude": lon,
            "latitude": 40,
        },
        [
            "analysis_context",
            "clock_conversion",
            body + ".calculation_basis",
            body + ".verdict",
        ],
        rest,
        tmp_path,
        capsys,
    )
    for value in values:
        c = value["clock_conversion"]
        b = value[body]["calculation_basis"]
        assert c["input_wall_datetime"] == "1978-01-01T00:00:00"
        assert c["converted_utc"].startswith("1977-12-31T23:59:60.")
        assert c["julian_day_ut1"] == b["julian_day_ut1"] == 2443509.5
        assert c["julian_day_tt"] == b["julian_day_tt"]
        assert c["utc_representation"] == b["utc_representation"]
        assert c["utc_representation"]["utc_is_leap_second"]
        assert not c["utc_representation"]["datetime_representable"]
        assert not c["source_clock_identification_performed"]
        assert value["analysis_context"]["timezone"] is None


def test_partial_utc_representation_contract(rest, tmp_path, capsys):
    values = surfaces(
        "astro_election",
        dict(
            candidate_year=1978,
            candidate_month=1,
            candidate_day=1,
            candidate_hour=0,
            candidate_clock_basis="local_mean_solar",
            longitude=0,
            latitude=40,
        ),
        [
            "clock_conversion.utc_representation.datetime_representable",
            "election.calculation_basis.utc_representation.utc_is_leap_second",
        ],
        rest,
        tmp_path,
        capsys,
    )
    assert values[0]["clock_conversion"]["utc_representation"] == {
        "datetime_representable": False
    }
    assert values[0]["election"]["calculation_basis"]["utc_representation"] == {
        "utc_is_leap_second": True
    }
