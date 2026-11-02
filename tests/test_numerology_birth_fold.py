"""Confirmed birth offsets preserve regional rules and actual birth instants."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.canping_timing import APPENDIX, CONTINUOUS, luck_timeline
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology_inputs import BIRTH_OFFSET_POLICY_ID
from fatebridge.core.output_numerology import NumerologyBirthClock, NumerologyEvidence
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from fatebridge.utils.timezones import parse_timezone_name

FIXTURE = Path(__file__).parent / "fixtures/numerology_birth_fold_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
PAIRS = [(HeluoRequest, build_heluo_result), (CanpingRequest, build_canping_result)]
BASE = {
    k: REFERENCE[k] for k in ("date", "time", "zone", "gender", "use_true_solar_time")
}


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


def utc(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def test_preimplementation_reference_and_reused_primary_sources():
    assert REFERENCE["frozen_before_implementation"]
    assert not REFERENCE["whole_history_accuracy_established"]
    for source in REFERENCE["source_files"]:
        assert (
            hashlib.sha256((FIXTURE / source["path"]).read_bytes()).hexdigest()
            == source["sha256"]
        )
    anchor = REFERENCE["anchor"]
    actual = next(
        t.moment for t in get_solar_terms_for_year(2021, "+08:00") if t.name == "立冬"
    )
    assert (
        abs((actual.astimezone(timezone.utc) - utc(anchor["at"])).total_seconds())
        <= anchor["tolerance_seconds"]
    )


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize(
    "case", REFERENCE["cases"], ids=lambda c: c["birth_utc_offset"]
)
def test_selected_occurrence_straddles_the_independent_term_anchor(model, build, case):
    result = build(
        **model(**BASE, birth_utc_offset=case["birth_utc_offset"]).model_dump()
    )
    e = result["numerology_evidence"]
    clock = e["birth_clock"]
    assert result["input_normalized"]["zone"] == clock["timezone_spec"] == BASE["zone"]
    assert clock["birth_utc_offset_policy_id"] == BIRTH_OFFSET_POLICY_ID
    assert clock["birth_instant_utc"] == case["utc"]
    assert clock["civil_fold"] == case["fold"] and clock["civil_time_ambiguous"] is True
    assert (
        clock["requested_utc_offset"]
        == clock["civil_utc_offset"]
        == case["birth_utc_offset"]
    )
    assert result["four_pillars"]["month"] == dict(
        stem=case["month"][0], branch=case["month"][1]
    )
    assert result["four_pillars"]["day"] == dict(
        stem=case["day"][0], branch=case["day"][1]
    )
    assert clock["calculation_wall_clock"] == "2021-11-07 00:30:00"
    assert clock["timezone_rules"]["tzif_sha256"]
    assert (
        next(r["facts"] for r in e["rule_trace"] if r["rule_id"] == clock["policy_id"])
        == clock
    )
    assert f"已确认出生偏移：{case['birth_utc_offset']}" in result["snapshot_text"]
    NumerologyEvidence.model_validate(e)
    if build is build_canping_result:
        timing = result["canping_timing"]
        assert timing["calendar_offset"]["whole_years"] == case["appendix_whole_years"]
        assert timing["start_at"] == case["appendix_start_at"]
        assert utc(timing["start_at"]) >= utc(clock["birth_instant_utc"])
        assert timing["timezone"] == BASE["zone"]
        for a, b in zip(result["dayun"], result["dayun"][1:]):
            assert utc(a["end_at"]) == utc(b["start_at"])


def test_same_gu_natal_numbers_do_not_erase_different_month_pillar_luck():
    a, b = [
        build_canping_result(**BASE, birth_utc_offset=c["birth_utc_offset"])
        for c in REFERENCE["cases"]
    ]
    assert a["benming"] == b["benming"]
    assert a["dayun"][0]["pillar"] == "丁酉" and b["dayun"][0]["pillar"] == "戊戌"
    assert a["dayun"][0]["numShun"] != b["dayun"][0]["numShun"]
    ha, hb = [
        build_heluo_result(**BASE, birth_utc_offset=c["birth_utc_offset"])
        for c in REFERENCE["cases"]
    ]
    assert ha["chart"]["tian"] != hb["chart"]["tian"]
    assert ha["chart"]["di"] != hb["chart"]["di"]


def test_birth_offset_is_not_a_fixed_zone_for_future_boundaries():
    named = build_canping_result(**BASE, birth_utc_offset="-04:00")
    fixed = build_canping_result(**{**BASE, "zone": "-04:00"})
    assert (
        named["numerology_evidence"]["birth_clock"]["birth_instant_utc"]
        == fixed["numerology_evidence"]["birth_clock"]["birth_instant_utc"]
    )
    assert named["benming"] == fixed["benming"]
    assert named["canping_timing"]["start_at"] == "2031-11-07T00:30:00-05:00"
    assert fixed["canping_timing"]["start_at"] == "2031-11-07T00:30:00-04:00"
    assert (
        utc(named["canping_timing"]["start_at"])
        - utc(fixed["canping_timing"]["start_at"])
    ).total_seconds() == 3600


@pytest.mark.parametrize("method", [APPENDIX, CONTINUOUS])
def test_initial_luck_boundary_cannot_precede_confirmed_second_birth(method):
    birth = utc("2021-11-07T05:30:00+00:00").astimezone(
        parse_timezone_name(BASE["zone"])
    )
    timeline = luck_timeline(birth, "男", ("己", "亥"), BASE["zone"], method)
    assert utc(timeline["start_at"]) >= utc(birth.isoformat())
    if method == APPENDIX:
        assert timeline["start_at"] == birth.isoformat()
        assert timeline["dst_policy"] == "fold_0_gap_forward_initial_birth_preserved"
    # The birth occurrence is not blindly carried into every later anniversary.
    for row in timeline["periods"]:
        assert utc(row["start_at"]) < utc(row["end_at"])


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("offset", [None, "-03:00"])
def test_unknown_or_region_inconsistent_offset_never_selects_a_fold(
    model, build, offset
):
    request = model(**BASE, birth_utc_offset=offset)
    with pytest.raises(ValueError):
        build(**request.model_dump())


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("offset", ["+08:00", "+09:00"])
def test_confirmed_offset_cannot_make_a_nonexistent_birth_clock_valid(
    model, build, offset
):
    args = {
        **BASE,
        "date": "1990-04-15",
        "time": "02:30",
        "zone": "Asia/Shanghai",
        "birth_utc_offset": offset,
    }
    with pytest.raises(ValueError, match="不存在"):
        build(**model(**args).model_dump())


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize(
    "offset", ["", "未知", "-5:00", "+15:00:01", "+08:60", True, 8]
)
def test_invalid_offset_never_turns_into_a_default(model, build, offset):
    if offset == "+15:00:01":
        # Valid offset syntax, still invalid for this New York birth clock.
        request = model(**BASE, birth_utc_offset=offset)
        with pytest.raises(ValueError, match="不一致"):
            build(**request.model_dump())
    else:
        with pytest.raises(ValidationError):
            model(**BASE, birth_utc_offset=offset)
    with pytest.raises(ValueError):
        build(**BASE, birth_utc_offset=offset)


@pytest.mark.parametrize("model,build", PAIRS)
def test_explicit_fixed_offset_preserves_seconds_and_supplied_clock_precision(
    model, build
):
    args = {
        **BASE,
        "zone": "+00:00:30",
        "time": "12:00:00.123456",
        "birth_utc_offset": " +00:00:30 ",
    }
    result = build(**model(**args).model_dump())
    clock = result["numerology_evidence"]["birth_clock"]
    assert clock["birth_instant_utc"] == "2021-11-07T11:59:30.123456+00:00"
    assert clock["civil_fold"] == 0 and clock["civil_time_ambiguous"] is False
    assert clock["civil_utc_offset_seconds"] == 30
    assert result["input_normalized"]["birth_utc_offset"] == "+00:00:30"


def test_selected_birth_receipt_allows_projection_but_rejects_internal_conflicts():
    clock = build_heluo_result(**BASE, birth_utc_offset="-05:00")[
        "numerology_evidence"
    ]["birth_clock"]
    for key in clock:
        NumerologyBirthClock.model_validate({key: clock[key]})
    for update in [
        dict(requested_utc_offset="-04:00"),
        dict(civil_utc_offset_seconds=-14400),
        dict(birth_instant_utc="2021-11-07T04:30:00+00:00"),
        dict(civil_fold=True),
        dict(civil_time_ambiguous=False),
    ]:
        bad = {**deepcopy(clock), **update}
        with pytest.raises(ValidationError):
            NumerologyBirthClock.model_validate(bad)


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("offset", ["-04:00", "-05:00"])
def test_solar_label_uses_the_confirmed_instant_without_second_dst_conversion(
    model, build, offset
):
    args = {**BASE, "lon": "-82.3667", "use_true_solar_time": True}
    named = build(**model(**args, birth_utc_offset=offset).model_dump())
    fixed = build(**model(**{**args, "zone": offset}).model_dump())
    a, b = [x["numerology_evidence"]["birth_clock"] for x in (named, fixed)]
    assert a["birth_instant_utc"] == b["birth_instant_utc"]
    assert a["calculation_wall_clock"] == b["calculation_wall_clock"]
    assert a["total_correction_minutes"] == b["total_correction_minutes"]
    assert a["mode"] == b["mode"] == "apparent_solar"
    assert a["longitude"] == b["longitude"] == -82.3667
    assert named["four_pillars"] == fixed["four_pillars"]
    if build is build_heluo_result:
        assert named["chart"] == fixed["chart"]
    else:
        assert named["benming"] == fixed["benming"]
