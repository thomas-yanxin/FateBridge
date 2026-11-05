"""Real protocol UT1 source selection, numerical axes, and nullable projection."""

import asyncio
import gzip
import json
from pathlib import Path

import pytest

from tests.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.test_agentic_nested_outputs import SPECS, call_cli, native
from tests.test_agentic_nested_outputs import rest as rest
from tests.test_western_event_clock_transports import surfaces

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

REF = json.loads(
    gzip.decompress(
        (Path(__file__).parent / "data/astro/iers_c04/controls.json.gz").read_bytes()
    )
)
NORMAL = next(r for r in REF if r["utc"] == "2024-06-01T12:00:00")
LEAP = next(r for r in REF if r["utc"] == "2016-12-31T23:59:60.5")
GEOMETRY = json.loads(
    (Path(__file__).parent / "data/astro/iers_c04/geometry.json").read_text()
)


@pytest.mark.parametrize(
    "tool,prefix,body,variant",
    [
        ("astro_election", "candidate", "election", "civil"),
        ("astro_election", "candidate", "election", "sidereal"),
        ("astro_election", "candidate", "election", "leap_lmt"),
        ("astro_election", "candidate", "election", "leap_lat"),
        ("astro_horary", "question", "horary", "civil"),
    ],
)
def test_required_observed_ut1_on_rest_mcp_cli(
    tool, prefix, body, variant, rest, tmp_path, capsys
):
    row = LEAP if variant.startswith("leap_") else NORMAL
    if variant.startswith("leap_"):
        # Supplemental after-candidate input derived only from the sealed
        # external UT1: choose a minute LMT label at the same physical instant.
        solar = GEOMETRY["synthetic_solar_inputs"][variant == "leap_lat"]
        args = {
            prefix + "_year": 2017,
            prefix + "_month": 1,
            prefix + "_day": 1,
            prefix + "_hour": 0,
            prefix + "_clock_basis": solar["basis"],
            "longitude": solar["longitude"],
        }
    else:
        args = {
            prefix + "_year": 2024,
            prefix + "_month": 6,
            prefix + "_day": 1,
            prefix + "_hour": 12,
            "timezone_name": "UTC",
            "longitude": 0,
        }
    args.update(ut1_source="iers_c04", latitude=40)
    if variant == "sidereal":
        args["zodiac_type"] = "Sidereal"
    values = surfaces(
        tool,
        args,
        [
            "analysis_context",
            "clock_conversion",
            body + ".calculation_basis",
            body + ".verdict",
        ],
        rest,  # noqa: F811 - pytest fixture dependency
        tmp_path,
        capsys,
    )
    for value in values:
        c = value["clock_conversion"]
        b = value[body]["calculation_basis"]
        r = c["ut1_reference"]
        assert abs(c["julian_day_tt"] - row["jd_tt"]) * 86400 <= 0.0002
        assert abs(c["julian_day_ut1"] - row["jd_ut1_continuous"]) * 86400 <= 0.0002
        assert (
            c["julian_day_tt"] == b["julian_day_tt"]
            and c["julian_day_ut1"] == b["julian_day_ut1"]
        )
        assert (
            r == b["earth_rotation"]["ut1_reference"]
            and b["earth_rotation"]["measured_eop_applied"]
        )
        assert value["analysis_context"]["ut1_source"] == "iers_c04"
        assert r["measured_ut1_series_applied"] and not r["polar_motion_applied"]
        assert r["interpolation_error_bound_seconds"] is None
        if variant.startswith("leap_"):
            assert c["converted_utc"].startswith("2016-12-31T23:59:60.")
            assert c["utc_representation"]["utc_is_leap_second"]


def test_observed_partial_source_and_default_null_source(
    rest, tmp_path, capsys
):  # noqa: F811 - pytest fixture dependency
    fields = [
        "clock_conversion.ut1_reference",
        "election.calculation_basis.earth_rotation.measured_eop_applied",
    ]
    base = dict(
        candidate_year=2024,
        candidate_month=6,
        candidate_day=1,
        candidate_hour=12,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
    )
    observed = surfaces(
        "astro_election",
        {**base, "ut1_source": "iers_c04"},
        fields,
        rest,  # noqa: F811 - pytest fixture dependency
        tmp_path,
        capsys,
    )
    assert observed[0]["clock_conversion"]["ut1_reference"]["source_mjd"] == [
        60462,
        60463,
    ]
    modeled = surfaces("astro_election", base, fields, rest, tmp_path, capsys)
    assert modeled[0]["clock_conversion"]["ut1_reference"] is None
    assert (
        modeled[0]["election"]["calculation_basis"]["earth_rotation"][
            "measured_eop_applied"
        ]
        is False
    )


@pytest.mark.parametrize("source", ["auto_observed", "unverified"])
def test_invalid_source_on_real_protocols(
    source, rest, tmp_path, capsys
):  # noqa: F811 - pytest fixture dependency
    spec = SPECS["astro_election"]
    args = dict(
        candidate_year=2024,
        candidate_month=6,
        candidate_day=1,
        candidate_hour=12,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source=source,
    )
    http = rest.post(spec.rest_path, json=args)
    code, cli = call_cli(spec, args, tmp_path, capsys)
    mcp = asyncio.run(native(spec, args))
    assert http.status_code == 422 and code != 0 and mcp.is_error


def test_closed_source_edge_preserves_nominal_facts_and_computes_tt_lunar_events(
    rest,  # noqa: F811 - pytest fixture dependency tmp_path, capsys
):
    args = dict(
        candidate_year=2026,
        candidate_month=9,
        candidate_day=19,
        candidate_hour=0,
        timezone_name="UTC",
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
    )
    values = surfaces(
        "astro_election",
        args,
        [
            "clock_conversion",
            "election.axes",
            "election.moon",
            "election.verdict",
            "election.calculation_basis",
        ],
        rest,  # noqa: F811 - pytest fixture dependency
        tmp_path,
        capsys,
    )
    for value in values:
        assert (
            value["clock_conversion"]["ut1_reference"]["instant_value_kind"]
            == "published_daily_sample"
        )
        assert value["election"]["axes"]["ascendant_longitude"] is not None
        # Geocentric TT event positions need no UT1 outside source coverage.
        # The sealed external TT corpus gives no contact before this ingress.
        moon = value["election"]["moon"]
        assert moon["void_of_course"] is True
        motion = moon["motion_basis"]
        assert motion["status"] == "computed"
        assert motion["contacts"] == []
        assert abs(motion["sign_exit_julian_day_tt"] - 2461302.705536775) * 86400 <= 30
