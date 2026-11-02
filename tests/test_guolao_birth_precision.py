"""Record fidelity, independent fractional-second sky and a solar-hour crossing."""

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from fractions import Fraction as F
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from tests.test_guolao_depth import chart

FIXTURE = Path(__file__).parent / "fixtures/guolao-birth-precision-v1"
REF = json.loads((FIXTURE / "reference.json").read_text())
CASE = REF["case"]


def rows(path):
    result = json.loads(path.read_text())["result"]
    return list(
        csv.reader(io.StringIO(result.split("$$SOE")[1].split("$$EOE")[0].strip()))
    )


def test_frozen_independent_responses_and_request_fingerprints():
    for a in REF["assets"] + REF["existing_zero_second_operands"]:
        raw = (FIXTURE / a["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == a["sha256"]
        if "bytes" in a:
            assert len(raw) == a["bytes"]
    for name in ("sun", "moon", "sidereal"):
        request = json.loads((FIXTURE / f"{name}-request.json").read_text())
        assert (
            request["response_sha256"]
            == hashlib.sha256((FIXTURE / f"{name}.json").read_bytes()).hexdigest()
        )
        assert request["parameters"]["START_TIME"] == "'2000-01-01 00:00:30.500'"
    assert not REF["physical_microsecond_accuracy_certified"]
    assert REF["real_world_career_events"] == 0


@pytest.mark.parametrize("model", [AstroGuolaoRequest, AstroChartPolyRequest])
@pytest.mark.parametrize("second,microsecond", [(0, 0), (30, 500000), (59, 999999)])
def test_dedicated_and_polymorphic_inputs_preserve_explicit_record_components(
    model, second, microsecond
):
    extra = {"chart_variant": "guolao_chart"} if model is AstroChartPolyRequest else {}
    request = model.model_validate(
        {**CASE, **extra, "birth_second": second, "birth_microsecond": microsecond}
    )
    assert request.birth_second == second
    assert request.birth_microsecond == microsecond


@pytest.mark.parametrize("model", [AstroGuolaoRequest, AstroChartPolyRequest])
@pytest.mark.parametrize(
    "field,value",
    [
        ("birth_second", -1),
        ("birth_second", 60),
        ("birth_second", 1.5),
        ("birth_microsecond", -1),
        ("birth_microsecond", 1000000),
        ("birth_microsecond", 1.5),
    ],
)
def test_invalid_components_and_leap_second_labels_are_not_rounded(model, field, value):
    extra = {"chart_variant": "guolao_chart"} if model is AstroChartPolyRequest else {}
    with pytest.raises(ValidationError):
        model.model_validate({**CASE, **extra, field: value})


@pytest.mark.parametrize("solar", [False, True])
def test_physical_instant_and_same_birth_target_keep_the_recorded_fraction(solar):
    instant = datetime.fromisoformat(REF["utc_epochs"][0])
    result = chart(
        **{**CASE, "use_true_solar_time": solar, "analysis_datetime": instant}
    )
    assert "guolao" in result, result
    assert result["person_info"]["birth_datetime"] == instant.isoformat()
    assert result["person_info"]["utc_datetime"] == instant.isoformat()
    timing = result["guolao"]["timing"]
    assert timing["analysis_datetime"] == instant.isoformat()
    assert [
        {k: v for k, v in b.items() if k != "natal_functional_palace"}
        for b in timing["transit_bodies"]
    ] == result["guolao"]["bodies"]
    before_birth = chart(
        **{
            **CASE,
            "use_true_solar_time": solar,
            "analysis_datetime": instant - timedelta(microseconds=1),
        }
    )
    assert before_birth["error_code"] == "validation_error"
    assert "不能早于" in before_birth["error"]


@pytest.mark.parametrize("index", [0, 1])
def test_fractional_second_positions_against_predeclared_horizons_tolerance(index):
    result = chart(**{**CASE, "birth_minute": index})
    assert "guolao" in result, result
    assert result["person_info"]["utc_datetime"] == REF["utc_epochs"][index]
    for name, body in (("sun", "Sun"), ("moon", "Moon")):
        row = rows(FIXTURE / f"{name}.json")[index]
        actual = next(b for b in result["guolao"]["bodies"] if b["id"] == body)
        for key, column in (("longitude", 5), ("right_ascension", 3)):
            error = abs((actual[key] - float(row[column]) + 180) % 360 - 180) * 3600
            assert error < REF["coordinate_tolerance_arcsec"]


def test_truncating_the_recorded_second_changes_the_independently_bracketed_hour():
    sun = rows(FIXTURE / "sun.json")[0]
    sidereal = rows(FIXTURE / "sidereal.json")[0]
    # This oracle uses JPL's printed operands, never the returned FateBridge RA.
    phase = (
        12
        + F(sidereal[3].strip())
        + (F(str(CASE["birth_longitude"])) - F(sun[3].strip())) / 15
    ) % 24
    assert abs(float((phase - 1) * 3600) - 15) < 0.000001
    zero_sun = rows(FIXTURE / REF["existing_zero_second_operands"][0]["file"])[0]
    zero_sidereal = rows(FIXTURE / REF["existing_zero_second_operands"][1]["file"])[0]
    zero_phase = (
        12
        + F(zero_sidereal[3].strip())
        + (F(str(CASE["birth_longitude"])) - F(zero_sun[3].strip())) / 15
    ) % 24
    assert zero_phase < 1 < phase
    precise = chart(**CASE)
    truncated = chart(**{**CASE, "birth_second": 0, "birth_microsecond": 0})
    g = precise["guolao"]
    assert g["life_palace"]["birth_hour_branch"] == REF["expected_precise_branch"]
    assert (
        truncated["guolao"]["life_palace"]["birth_hour_branch"]
        == REF["expected_zero_second_branch"]
    )
    assert g["life_palace"]["branch"] != truncated["guolao"]["life_palace"]["branch"]
    clock = g["profile"]["apparent_solar_clock"]
    delta_seconds = (F(clock["apparent_day_fraction_exact"]) * 24 - phase) * 3600
    assert abs(float(delta_seconds)) < REF["solar_clock_tolerance_seconds"]
    assert "生时丑" in precise["interpretation"]["core_identity"]
    assert "30.500000" in precise["snapshot_text"]
    assert not g["validation"]["full_marks_established"]


@pytest.mark.parametrize("variant", ["chart", "hellen_chart"])
def test_other_variants_still_reject_nonzero_unsupported_precision(variant):
    for fields in ({"birth_second": 1}, {"birth_microsecond": 1}):
        base = {
            k: v
            for k, v in CASE.items()
            if k not in {"birth_second", "birth_microsecond"}
        }
        with pytest.raises(ValidationError):
            AstroChartPolyRequest.model_validate(
                {**base, **fields, "chart_variant": variant}
            )
