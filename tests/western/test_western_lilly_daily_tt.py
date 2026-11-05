"""Lilly's declared TT-day model and native Lahiri definition at the same TT."""

import gzip
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.iers_ut1 import use_ut1_source
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.lilly_fortitude_inputs import collect_fortitude_inputs
from fatebridge.core.predictive.native_chart import build_native_subject
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.western.test_western_tt_events import refuse_ut1

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/astro/lilly_daily_tt"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
EXTERNAL = json.loads(
    gzip.decompress(
        (ROOT / "tests/data/astro/tt_common_frame/reference.json.gz").read_bytes()
    )
)
EXTERNAL_PLAN = json.loads(
    (ROOT / "tests/data/astro/tt_common_frame/protocol.json").read_text()
)


@pytest.fixture(scope="module")
def isolated_native_build_controls(tmp_path_factory):
    # Arithmetic conformance compares the same native build. Frozen macOS
    # numbers cannot define a compiler-independent 2e-12 degree truth for
    # Linux's Moshier implementation. Both historical failed comparisons are
    # retained; independent daily displacements still use the fixed .02" line.
    output = tmp_path_factory.mktemp("raw-native-controls") / "controls.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/western/gen_western_lilly_isolated_native_controls.py"),
            "--protocol",
            str(FIXTURE / "protocol.json"),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "SE_EPHE_PATH": configured_ephemeris_path() or ""},
    )
    result = json.loads(output.read_text())
    assert (
        result["protocol_sha256"]
        == hashlib.sha256((FIXTURE / "protocol.json").read_bytes()).hexdigest()
    )
    assert not result["production_imports"] and not result["independent_astronomy"]
    return result


@pytest.mark.parametrize(
    "case", PROTOCOL["cases"], ids=lambda r: f"{r['source']}-{r['stamp']}-{r['zodiac']}"
)
def test_native_subject_and_fortitudes_share_tt_frame_without_trial_ut1(
    case, monkeypatch, isolated_native_build_controls
):
    original = runtime.ephemeris_call

    def native(operation, *args, **kwargs):
        if operation == "get_ayanamsa_ex_ut":
            raise AssertionError(
                "A known physical TT must not be converted again for Lahiri"
            )
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    with use_ut1_source(case["source"]):
        subject = build_native_subject(
            name="fictional TT-day control",
            local_datetime=datetime.fromisoformat(case["stamp"]),
            longitude=0,
            latitude=40,
            timezone_name="UTC",
            house_system="R",
            zodiac_type=case["zodiac"],
        )
        assert subject.julian_day_tt == case["tt"]
        if case["zodiac"] == "Sidereal":
            assert (
                abs(
                    subject.calculation_basis["ayanamsha_degrees"]
                    - next(
                        row
                        for row in isolated_native_build_controls["rows"]
                        if all(row[k] == case[k] for k in ("stamp", "source", "zodiac"))
                    )["ayanamsha_tt"]
                )
                <= PROTOCOL["native_api_arithmetic_line_degrees"]
            )
            isolated = next(
                row
                for row in isolated_native_build_controls["rows"]
                if all(row[k] == case[k] for k in ("stamp", "source", "zodiac"))
            )
            for planet, expected in isolated["positions"].items():
                value = getattr(subject, planet.lower()).abs_pos
                error = abs((value - expected["longitude"] + 180) % 360 - 180)
                assert error <= PROTOCOL["native_api_arithmetic_line_degrees"], (
                    planet,
                    error,
                )
        # The nominal chart legitimately needed covered UT1 for its houses.
        # Only the subsequent geocentric daily sampling must not ask for it.
        refuse_ut1(monkeypatch)
        data = collect_fortitude_inputs(subject)
    assert data["status"] == "computed", data
    assert data["day_interval_tt"] == [case["tt"], case["tt"] + 1]
    assert len(data["motion"]) == 7
    for planet, row in data["motion"].items():
        assert row["status"] == "computed" and len(row["samples"]) == 5
        assert (
            row["nominal_coordinate_check"]
            == "agrees_with_supplied_coordinate_within_arithmetic_allowance"
        )
        assert row["samples"][0]["longitude"] == pytest.approx(
            getattr(subject, planet.lower()).abs_pos, abs=2e-12
        )


@pytest.mark.parametrize("index", [0, 1])
def test_complete_one_tt_day_displacements_match_preexisting_external_reference(index):
    case = next(
        c
        for c in PROTOCOL["cases"]
        if c["source"] == "iers_c04"
        and c["zodiac"] == "Tropic"
        and c["stamp"].startswith(("1962-01-01", "2026-09-19")[index])
    )
    with use_ut1_source("iers_c04"):
        subject = build_native_subject(
            name="fictional external day",
            local_datetime=datetime.fromisoformat(case["stamp"]),
            longitude=0,
            latitude=40,
            timezone_name="UTC",
            house_system="R",
        )
        actual = collect_fortitude_inputs(subject)
    reference = EXTERNAL["cases"][index]
    for planet, data in actual["motion"].items():
        rows = reference["targets"][planet]["rows"]
        expected = [
            rows[i]["projections"][EXTERNAL_PLAN["primary_projection"]][0]
            for i in (0, 36, 72, 108, 144)
        ]
        displacement = sum(
            (b - a + 180) % 360 - 180 for a, b in zip(expected, expected[1:])
        )
        error = (
            abs(float(Fraction(data["daily_motion_exact_degrees"])) - displacement)
            * 3600
        )
        assert error <= PROTOCOL["external_daily_line_arcseconds"], (planet, error)
