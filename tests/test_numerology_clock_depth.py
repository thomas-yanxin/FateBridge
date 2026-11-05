"""Known longitude, physical birth instant and independent JPL solar clocks."""

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import (
    CLOCK_POLICY_ID,
    resolve_numerology_longitude,
)
from fatebridge.core.output_numerology import NumerologyEvidence
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from tests.fixtures.solar_reference import expected_solar_clock

ROOT = Path(__file__).parent / "fixtures"
JPL = json.loads((ROOT.parent / "data/bazi-solar-regression-jpl-v1.json").read_text())
BUILDERS = [build_heluo_result, build_canping_result]
BASE = dict(date="2000-05-15", time="09:00:00", zone="Asia/Shanghai", gender="男")


@pytest.mark.parametrize("model", [HeluoRequest, CanpingRequest])
def test_public_default_on_needs_longitude_and_civil_mode_needs_none(model):
    with pytest.raises(ValidationError, match="经度"):
        model(**BASE)
    with pytest.raises(ValidationError, match="经度"):
        model(**BASE, use_true_solar_time=True)
    assert model(**BASE, use_true_solar_time=False).lon is None
    assert model(**BASE, gps_lon=0).gps_lon == 0


@pytest.mark.parametrize("build", BUILDERS)
@pytest.mark.parametrize("longitude", [None, "", " ", "未知"])
def test_direct_domain_never_uses_a_default_place_for_solar_time(build, longitude):
    with pytest.raises(ValueError):
        build(**BASE, lon=longitude, use_true_solar_time=True)


@pytest.mark.parametrize("model", [HeluoRequest, CanpingRequest])
@pytest.mark.parametrize("gps", [True, False, 181, -181, float("nan"), float("inf")])
def test_invalid_gps_does_not_turn_into_a_numeric_place(model, gps):
    with pytest.raises(ValidationError):
        model(**BASE, gps_lon=gps)
    with pytest.raises(ValueError):
        resolve_numerology_longitude(None, gps, True)


@pytest.mark.parametrize("build", BUILDERS)
def test_civil_mode_has_no_invented_coordinate_and_known_unused_longitude_is_distinct(
    build,
):
    a = build(**BASE, use_true_solar_time=False)
    b = build(**BASE, lon="75", use_true_solar_time=False)
    assert a["analysis_context"]["longitude"] is None
    assert b["analysis_context"]["longitude"] == 75
    assert a["four_pillars"] == b["four_pillars"]
    ca, cb = (r["numerology_evidence"]["birth_clock"] for r in (a, b))
    assert ca["longitude"] is ca["longitude_source"] is None
    assert cb["longitude_source"] == "lon" and cb["longitude"] == 75
    assert not ca["longitude_used"] and not cb["longitude_used"]
    assert ca["mode"] == "civil" and ca["total_correction_minutes"] == 0
    assert datetime.fromisoformat(ca["calculation_wall_clock"]).tzinfo is None
    assert "经度：未提供" in a["snapshot_text"]


@pytest.mark.parametrize("build", BUILDERS)
def test_gps_precedence_zero_and_west_longitude_are_explicit(build):
    gps = build(**BASE, lon="121e28", gps_lon=75, use_true_solar_time=True)
    single = build(**BASE, lon="75", use_true_solar_time=True)
    assert gps["four_pillars"] == single["four_pillars"]
    clock = gps["numerology_evidence"]["birth_clock"]
    assert clock["longitude_source"] == "gps_lon" and clock["longitude"] == 75
    assert gps["input_normalized"]["lon"] == "121e28"
    zero = build(**BASE, gps_lon=0, use_true_solar_time=True)
    assert zero["analysis_context"]["longitude"] == 0
    assert zero["numerology_evidence"]["birth_clock"]["longitude_source"] == "gps_lon"
    west = build(**BASE, lon="75w0", use_true_solar_time=True)
    assert west["analysis_context"]["longitude"] == -75


@pytest.mark.parametrize("build", BUILDERS)
def test_clock_trace_is_the_same_run_but_not_a_mutable_alias(build):
    result = build(**BASE, lon="75", use_true_solar_time=True)
    evidence = result["numerology_evidence"]
    clock = evidence["birth_clock"]
    trace = next(
        t["facts"] for t in evidence["rule_trace"] if t["rule_id"] == CLOCK_POLICY_ID
    )
    assert trace == clock
    NumerologyEvidence.model_validate(evidence)
    before = copy.deepcopy(trace)
    clock["longitude"] = 0
    assert trace == before


@pytest.mark.parametrize("build", BUILDERS)
@pytest.mark.parametrize("longitude", [0, 75])
@pytest.mark.parametrize("case", JPL["rows"], ids=lambda c: c["instant"])
def test_actual_calculation_wall_clock_against_frozen_independent_jpl(
    build, longitude, case
):
    at = datetime.fromisoformat(case["instant"]).astimezone(ZoneInfo("Asia/Shanghai"))
    result = build(
        date=at.strftime("%Y-%m-%d"),
        time=at.strftime("%H:%M:%S"),
        zone="Asia/Shanghai",
        gender="男",
        gps_lon=longitude,
        use_true_solar_time=True,
    )
    clock = result["numerology_evidence"]["birth_clock"]
    expected = expected_solar_clock(at.replace(tzinfo=None), "Asia/Shanghai", longitude)
    actual = datetime.fromisoformat(clock["calculation_wall_clock"])
    assert abs((actual - expected).total_seconds()) <= JPL["tolerance_seconds"] == 5
    assert clock["birth_instant_utc"] == case["instant"]
    assert clock["civil_datetime"] == at.isoformat()
    # Hours away from the civil zone are calculation coordinates, not a new
    # physical UTC timestamp. The two clocks can even belong to different dates.
    assert actual.tzinfo is None and clock["longitude_used"] is True
    branches = "子丑寅卯辰巳午未申酉戌亥"
    expected_branch = branches[((expected.hour + 1) // 2) % 12]
    assert result["four_pillars"]["hour"]["branch"] == expected_branch
    if "solar_term" in result:
        assert result["solar_term"]["anchor_utc"] == case["instant"]


def test_reference_reuse_is_identified_without_inventing_new_external_instants():
    reference = json.loads((ROOT / "numerology_clock_v1/reference.json").read_text())
    assert (
        hashlib.sha256(
            (ROOT.parent / "data" / reference["jpl_fixture"]).read_bytes()
        ).hexdigest()
        == reference["jpl_fixture_sha256"]
    )
    assert reference["reused_independent_instants"] == 4
    assert reference["new_independent_instants"] == 0
    assert reference["new_classical_worked_horoscopes"] == 0
