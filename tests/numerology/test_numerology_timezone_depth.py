"""Explicit civil-zone policy for the two birth numerologies."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.almanac import get_day_ganzhi
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import TIMEZONE_POLICY_ID
from fatebridge.core.output_numerology import NumerologyEvidence
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from fatebridge.utils.timezones import parse_timezone_name

PAIRS = [(HeluoRequest, build_heluo_result), (CanpingRequest, build_canping_result)]
BASE = dict(
    date="1990-06-15",
    time="09:30",
    gender="男",
    lon="120",
    use_true_solar_time=True,
)
FIXTURES = Path(__file__).parents[1] / "fixtures/numerology_timezone_v1"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())


@pytest.mark.parametrize("model,build", PAIRS)
def test_omitted_and_null_zone_use_the_published_fixed_offset(model, build):
    public = build(**model(**BASE).model_dump())
    direct = build(**BASE)
    null = build(**BASE, zone=None)
    fixed = build(**BASE, zone="+08:00")
    for result in (public, direct, null, fixed):
        assert result["input_normalized"]["zone"] == "+08:00"
        clock = result["numerology_evidence"]["birth_clock"]
        assert clock["birth_instant_utc"] == "1990-06-15T01:30:00+00:00"
        assert result["four_pillars"] == fixed["four_pillars"]
        assert result["four_pillars"]["hour"] == {"stem": "癸", "branch": "巳"}


@pytest.mark.parametrize("model,build", PAIRS)
def test_explicit_historical_zone_remains_a_distinct_birth_clock(model, build):
    named = build(**model(**BASE, zone="Asia/Shanghai").model_dump())
    fixed = build(**BASE, zone="+08:00")
    assert named["input_normalized"]["zone"] == "Asia/Shanghai"
    assert (
        named["numerology_evidence"]["birth_clock"]["birth_instant_utc"]
        == "1990-06-15T00:30:00+00:00"
    )
    assert named["four_pillars"]["hour"] == {"stem": "壬", "branch": "辰"}
    assert named["four_pillars"]["hour"] != fixed["four_pillars"]["hour"]


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("zone", ["", " ", "未知", "UTC+08:90", 8, True])
def test_blank_or_invalid_zone_never_becomes_a_default(model, build, zone):
    with pytest.raises(ValidationError):
        model(**BASE, zone=zone)
    with pytest.raises(ValueError):
        build(**BASE, zone=zone)


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("solar", [False, True])
def test_explicit_historical_zone_and_fixed_dst_offset_are_same_solar_instant(
    model, build, solar
):
    args = {**BASE, "use_true_solar_time": solar}
    named = build(**model(**args, zone=" Asia/Shanghai ").model_dump())
    fixed = build(**model(**args, zone="+09:00").model_dump())
    assert named["four_pillars"] == fixed["four_pillars"]
    if "chart" in named:
        assert named["chart"] == fixed["chart"]
        # The same physical instant preserves every pre-receipt fact. Named
        # Shanghai includes winter +08 and summer +09, unlike a fixed +09;
        # consumed boundary labels must retain those actual offsets.
        a, b = deepcopy(named["solar_term"]), deepcopy(fixed["solar_term"])
        ca, cb = a.pop("boundary_context"), b.pop("boundary_context")
        assert a == b
        assert ca.pop("context_timezone") == "Asia/Shanghai"
        assert cb.pop("context_timezone") == "+09:00"
        da, db = ca.pop("dependencies"), cb.pop("dependencies")
        assert ca == cb and len(da) == len(db) == 3
        local_fields = {
            "datetime",
            "datetime_with_offset",
            "date_key",
            "day_ganzhi",
            "utc_offset_seconds",
            "fold",
            "timezone",
        }
        for x, y in zip(da, db):
            rx, ry = x.pop("record"), y.pop("record")
            assert x == y
            assert {k: v for k, v in rx.items() if k not in local_fields} == {
                k: v for k, v in ry.items() if k not in local_fields
            }
            for record, zone in [(rx, "Asia/Shanghai"), (ry, "+09:00")]:
                instant = datetime.fromisoformat(x["instant_utc"])
                expected = instant.astimezone(parse_timezone_name(zone))
                assert record["datetime_with_offset"] == expected.isoformat()
                assert record["datetime"] == expected.replace(tzinfo=None).isoformat(
                    sep=" "
                )
                assert record["date_key"] == expected.strftime("%Y%m%d")
                assert record["day_ganzhi"] == get_day_ganzhi(
                    expected.year, expected.month, expected.day
                )
                assert (
                    record["utc_offset_seconds"] == expected.utcoffset().total_seconds()
                )
                assert record["fold"] == expected.fold
                label = (
                    getattr(expected.tzinfo, "key", None)
                    or getattr(expected.tzinfo, "zone", None)
                    or expected.tzname()
                )
                assert record["timezone"] == label
        winter_named = next(
            x
            for x in named["solar_term"]["boundary_context"]["dependencies"]
            if x["role"] == "preceding_solstice"
        )
        winter_fixed = next(
            x
            for x in fixed["solar_term"]["boundary_context"]["dependencies"]
            if x["role"] == "preceding_solstice"
        )
        assert winter_named["record"]["utc_offset_seconds"] == 28800
        assert winter_fixed["record"]["utc_offset_seconds"] == 32400
    else:
        assert named["element"] == fixed["element"]
        for key in ("shun", "ni", "numShun", "numNi", "verses"):
            assert named["benming"][key] == fixed["benming"][key]
    ca, cb = [r["numerology_evidence"]["birth_clock"] for r in (named, fixed)]
    assert ca["birth_instant_utc"] == cb["birth_instant_utc"]
    assert ca["calculation_wall_clock"] == cb["calculation_wall_clock"]
    assert ca["timezone_spec"] == "Asia/Shanghai"
    assert cb["timezone_spec"] == "+09:00"
    assert ca["civil_utc_offset_seconds"] == cb["civil_utc_offset_seconds"] == 32400
    assert ca["civil_daylight_saving_seconds"] == 3600
    assert cb["civil_daylight_saving_seconds"] == 0
    assert ca["timezone_rules"]["database"] == "pytz"
    assert cb["timezone_rules"]["database"] == "explicit_fixed_offset"
    for result in (named, fixed):
        evidence = result["numerology_evidence"]
        clock = evidence["birth_clock"]
        NumerologyEvidence.model_validate(evidence)
        assert clock["timezone_policy_id"] == TIMEZONE_POLICY_ID
        assert (
            next(
                row["facts"]
                for row in evidence["rule_trace"]
                if row["rule_id"] == clock["policy_id"]
            )
            == clock
        )
        assert "未提供时区仅约定固定+08:00，不推定出生地" in result["snapshot_text"]


@pytest.mark.parametrize(
    "row", REFERENCE["transition_instants"], ids=lambda r: r["utc"]
)
def test_historical_transition_labels_from_named_notice(row):
    # Expected constants were transcribed from the named notice/rules. They
    # are not produced with the timezone engine under test.
    instant = datetime.fromisoformat(row["utc"])
    local = instant.astimezone(parse_timezone_name("Asia/Shanghai"))
    assert local.isoformat() == row["local"]
    assert int(local.dst().total_seconds()) == row["daylight_saving_seconds"]
    assert local.astimezone(timezone.utc) == instant


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("case", REFERENCE["invalid_regional_clocks"])
def test_historical_gap_and_fold_are_not_guessed(model, build, solar, case):
    args = dict(
        date=case["date"],
        time=case["time"],
        gender="男",
        lon="120",
        use_true_solar_time=solar,
    )
    # Syntax validation cannot assign a physical instant to either case.
    request = model(**args, zone="Asia/Shanghai")
    with pytest.raises(ValueError, match=case["error"]):
        build(**request.model_dump())


@pytest.mark.parametrize("model,build", PAIRS)
def test_repeated_clock_requires_a_known_explicit_offset(model, build):
    args = {**BASE, "date": "1990-09-16", "time": "01:30"}
    clocks = []
    for zone, instant in (
        ("+09:00", "1990-09-15T16:30:00+00:00"),
        ("+08:00", "1990-09-15T17:30:00+00:00"),
    ):
        result = build(**model(**args, zone=zone).model_dump())
        clock = result["numerology_evidence"]["birth_clock"]
        assert clock["birth_instant_utc"] == instant
        clocks.append(clock["calculation_wall_clock"])
    assert clocks[0] != clocks[1]


def test_reference_source_identity_and_bounded_scope():
    source = REFERENCE["iana_source"]
    assert (
        hashlib.sha256((FIXTURES / source["file"]).read_bytes()).hexdigest()
        == source["sha256"]
    )
    assert (
        REFERENCE["government_notice"]["access"]
        == "search_index_text; direct_open_http_403"
    )
    assert REFERENCE["independent_solar_instants_added"] == 0
    assert REFERENCE["classical_worked_horoscopes_added"] == 0
    assert REFERENCE["prospective_outcomes_added"] == 0
