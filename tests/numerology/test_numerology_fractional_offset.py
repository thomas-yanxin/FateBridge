"""Fractional offsets preserve instants, receipts and Canping query boundaries."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.application.execution import validate_output
from fatebridge.core.execution_context import (
    ExecutionOptions,
    call_clock,
    current_datetime,
)
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_canping_solar import CanpingSolarBoundary
from fatebridge.core.output_chinese import CHINESE_TOOL_FIELDS, SolarTerm
from fatebridge.core.output_heluo_solar import HeluoSolarBoundary
from fatebridge.core.output_numerology import NumerologyBirthClock, NumerologyEvidence
from fatebridge.core.requests.divination import CanpingRequest, HeluoRequest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.civil_clock import parse_iso_datetime, utc_instant

FIXTURE = Path(__file__).parents[1] / "fixtures/numerology_fractional_offset_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
PAIRS = [(HeluoRequest, build_heluo_result), (CanpingRequest, build_canping_result)]
SPECS = {spec.key: spec for spec in CATALOG}


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    empty = tmp_path / "empty-ephe"
    empty.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))


def payload(case):
    date, clock = case["wall"].split("T")
    return dict(
        date=date,
        time=clock,
        zone=case["zone"],
        gender="男",
        use_true_solar_time=False,
    )


def test_source_first_reference_and_primary_bytes_are_unchanged():
    seal = json.loads((FIXTURE / "reference-seal.json").read_text())
    assert hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest() == (
        seal["reference_sha256"]
    )
    assert REFERENCE["frozen_before_production_edits"]
    assert not REFERENCE["derived_with_fatebridge"]
    assert not REFERENCE["aware_fromisoformat_used_for_expected_values"]
    for source in REFERENCE["primary_sources"]:
        assert hashlib.sha256((FIXTURE / source["path"]).read_bytes()).hexdigest() == (
            source["sha256"]
        )
    assert not REFERENCE["whole_history_accuracy_established"]
    assert not REFERENCE["real_world_forecasting_validated"]


@pytest.mark.parametrize("case", REFERENCE["iso_parse_cases"], ids=lambda c: c["id"])
def test_iso_offsets_match_independent_integer_microsecond_instants(case):
    at = parse_iso_datetime(case["text"])
    assert at.utcoffset() // timedelta(microseconds=1) == (
        case["expected_offset_microseconds"]
    )
    assert utc_instant(at).isoformat() == case["expected_utc"]


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("case", REFERENCE["clock_cases"], ids=lambda c: c["id"])
def test_numerology_receipts_keep_fractional_offsets_and_validate(model, build, case):
    request = model(**payload(case))
    result = build(**request.model_dump())
    validate_output(
        SPECS["heluo" if build is build_heluo_result else "canping"],
        result,
        request=request,
    )
    evidence = result["numerology_evidence"]
    clock = evidence["birth_clock"]
    assert clock["civil_datetime"] == case["civil_iso"]
    assert clock["birth_instant_utc"] == case["utc"]
    assert Decimal(str(clock["civil_utc_offset_seconds"])) == Decimal(
        case["offset_seconds_decimal"]
    )
    assert type(clock["civil_utc_offset_seconds"]) is (
        int if case["offset_microseconds"] % 1000000 == 0 else float
    )
    assert clock["input_representation"]["observed_precision_certified"] is False
    assert clock["timezone_spec"] == case["zone"]
    assert (
        next(
            r["facts"]
            for r in evidence["rule_trace"]
            if r["rule_id"] == clock["policy_id"]
        )
        == clock
    )
    NumerologyEvidence.model_validate(evidence)
    if build is build_canping_result:
        series = result["liunian_series"]
        for i, row in enumerate(series["rows"]):
            lo, hi = series["year_boundaries"][i : i + 2]
            expected_start = max(
                datetime.fromisoformat(case["utc"]),
                utc_instant(parse_iso_datetime(lo["record"]["datetime_with_offset"])),
            )
            assert utc_instant(parse_iso_datetime(row["start_at"])) == expected_start
            assert utc_instant(parse_iso_datetime(row["end_at"])) == utc_instant(
                parse_iso_datetime(hi["record"]["datetime_with_offset"])
            )


@pytest.mark.parametrize("method", ["bazi_appendix_v1", "bazi_continuous_v1"])
@pytest.mark.parametrize(
    "case", REFERENCE["canping_query_cases"], ids=lambda c: c["id"]
)
def test_canping_queries_respect_actual_birth_microsecond_and_return_same_instant(
    method, case
):
    args = {
        **payload(case["birth"]),
        "analysis_datetime": case["query_iso"],
        "dayun_method": method,
    }
    request = CanpingRequest(**args)
    if case["must_reject_before_birth"]:
        with pytest.raises(ValueError, match="不能早于出生"):
            build_canping_result(**request.model_dump())
    else:
        result = build_canping_result(**request.model_dump())
        validate_output(SPECS["canping"], result, request=request)
        selected = result["canping_timing"]["selected"]
        assert selected is not None
        assert utc_instant(parse_iso_datetime(selected["at"])).isoformat() == (
            case["query_utc"]
        )
        assert (
            utc_instant(parse_iso_datetime(selected["start_at"]))
            <= (datetime.fromisoformat(case["query_utc"]))
            < utc_instant(parse_iso_datetime(selected["end_at"]))
        )
        NumerologyEvidence.model_validate(result["numerology_evidence"])


@pytest.mark.parametrize("model,build", PAIRS)
@pytest.mark.parametrize("zone", ["0.0000001", "-0.0000001"])
def test_solar_wall_correction_does_not_replace_the_civil_instant(model, build, zone):
    case = next(
        c
        for c in REFERENCE["clock_cases"]
        if c["zone"] == zone and c["id"].endswith("year_edge")
    )
    request = model(**{**payload(case), "use_true_solar_time": True, "lon": "0"})
    result = build(**request.model_dump())
    validate_output(
        SPECS["heluo" if build is build_heluo_result else "canping"],
        result,
        request=request,
    )
    clock = result["numerology_evidence"]["birth_clock"]
    assert clock["birth_instant_utc"] == case["utc"]
    assert clock["mode"] == "apparent_solar"
    assert clock["calculation_wall_clock"] != case["wall"].replace("T", " ")
    NumerologyEvidence.model_validate(result["numerology_evidence"])


@pytest.mark.parametrize(
    "seconds", [0.00036, -0.00036, 19800.00036, -19800.00036, 54822]
)
def test_fractional_offset_receipt_is_independently_projectable(seconds):
    value = NumerologyBirthClock(civil_utc_offset_seconds=seconds)
    assert value.model_dump(exclude_unset=True) == {"civil_utc_offset_seconds": seconds}


@pytest.mark.parametrize(
    "seconds",
    [float("nan"), float("inf"), -float("inf"), 86400, -86400, True, "0.00036"],
)
def test_offset_metadata_rejects_nonfinite_out_of_range_and_coerced_values(seconds):
    with pytest.raises(ValidationError):
        NumerologyBirthClock(civil_utc_offset_seconds=seconds)


@pytest.mark.parametrize("wrong_seconds", [0, -0.00036, 0.000361])
def test_fractional_clock_coherence_still_rejects_truncated_or_wrong_offsets(
    wrong_seconds,
):
    case = REFERENCE["clock_cases"][0]
    clock = dict(
        civil_datetime=case["civil_iso"],
        birth_instant_utc=case["utc"],
        civil_utc_offset_seconds=wrong_seconds,
    )
    with pytest.raises(ValidationError, match="偏移秒数不一致"):
        NumerologyBirthClock(**clock)


def test_correct_offset_does_not_hide_a_wrong_utc_receipt():
    case = REFERENCE["clock_cases"][0]
    clock = dict(
        civil_datetime=case["civil_iso"],
        birth_instant_utc=case["utc"],
        civil_utc_offset_seconds=0.00036,
    )
    NumerologyBirthClock(**clock)
    corrupted = deepcopy(clock)
    corrupted["birth_instant_utc"] = (
        datetime.fromisoformat(case["utc"]) + timedelta(microseconds=1)
    ).isoformat()
    with pytest.raises(ValidationError, match="UTC瞬间回执不一致"):
        NumerologyBirthClock(**corrupted)


@pytest.mark.parametrize("text", ["2000-01-01T00:00:00.000360", "2000-01-01+00.000360"])
def test_naive_clocks_remain_naive_even_when_separator_resembles_an_offset(text):
    assert parse_iso_datetime(text) == datetime(2000, 1, 1, microsecond=360)
    assert parse_iso_datetime(text).tzinfo is None


@pytest.mark.parametrize("text", [None, 8, "not-a-date", "2000-01-01T00:00:00+24:00"])
def test_invalid_iso_inputs_keep_their_rejection(text):
    with pytest.raises((ValueError, TypeError)):
        parse_iso_datetime(text)


@pytest.mark.parametrize("model,build", PAIRS)
def test_whole_second_confirmation_cannot_replace_a_fractional_fixed_zone(model, build):
    args = {**payload(REFERENCE["clock_cases"][0]), "birth_utc_offset": "+00:00"}
    with pytest.raises(ValueError, match="不一致"):
        build(**model(**args).model_dump())


@pytest.mark.parametrize("case", REFERENCE["clock_cases"], ids=lambda c: c["id"])
def test_public_asof_and_direct_call_clock_keep_the_same_frozen_instant(case):
    from datetime import timezone

    options = ExecutionOptions(as_of=case["civil_iso"])
    assert options.as_of == case["utc"].replace("+00:00", "Z")
    with call_clock(case["civil_iso"]):
        assert current_datetime(timezone.utc).isoformat() == case["utc"]
    with call_clock(options.as_of):
        assert current_datetime(timezone.utc).isoformat() == case["utc"]


@pytest.mark.parametrize("case", REFERENCE["clock_cases"], ids=lambda c: c["id"])
def test_outer_solar_receipts_preserve_the_independently_known_instant(case):
    # Synthetic DTO timestamps exercise serialization, not real solar events.
    SolarTerm(
        datetime=case["wall"].replace("T", " "),
        datetime_with_offset=case["civil_iso"],
        utc_offset_seconds=float(Decimal(case["offset_seconds_decimal"])),
    )
    record = {"datetime_with_offset": case["civil_iso"]}
    for model in [HeluoSolarBoundary, CanpingSolarBoundary]:
        model(record=record, instant_utc=case["utc"])


@pytest.mark.parametrize(
    "case",
    [
        c
        for c in REFERENCE["clock_cases"]
        if 0 < abs(c["offset_microseconds"]) < 1000000
    ],
    ids=lambda c: c["id"],
)
def test_outer_solar_receipts_do_not_accept_offsets_or_utc_instants_lost_to_zero(case):
    with pytest.raises(ValidationError, match="utc_offset_seconds不一致"):
        SolarTerm(datetime_with_offset=case["civil_iso"], utc_offset_seconds=0)
    record = {"datetime_with_offset": case["civil_iso"]}
    wrong_utc = case["wall"] + "+00:00"
    for model in [HeluoSolarBoundary, CanpingSolarBoundary]:
        with pytest.raises(ValidationError, match="不一致|不是同一时刻"):
            model(record=record, instant_utc=wrong_utc)


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_declared_numerology_roots_are_in_the_actual_public_model(key):
    spec = SPECS[key]
    assert set(CHINESE_TOOL_FIELDS[key]) <= set(spec.output_model.model_fields)
    assert "numerology_evidence" in spec.required_output_fields
    if key == "canping":
        assert "canping_timing" in spec.required_output_fields
    # Schema projections can omit the evidence root, but cannot make supplied
    # contradictory evidence opaque by treating it as an extension field.
    spec.output_model.model_validate({})
    case = REFERENCE["clock_cases"][0]
    corrupt = {
        "numerology_evidence": {
            "birth_clock": {
                "civil_datetime": case["civil_iso"],
                "birth_instant_utc": case["utc"],
                "civil_utc_offset_seconds": 0,
            }
        }
    }
    with pytest.raises(ValidationError, match="偏移秒数不一致"):
        spec.output_model.model_validate(corrupt)


SCHEMA_BOUNDS = json.loads(
    (FIXTURE / "schema-bounds-addendum-reference.json").read_text()
)


def test_schema_bounds_reference_is_a_retained_post_c4_addendum():
    seal = json.loads((FIXTURE / "schema-bounds-addendum-seal.json").read_text())
    assert (
        hashlib.sha256(
            (FIXTURE / "schema-bounds-addendum-reference.json").read_bytes()
        ).hexdigest()
        == seal["sha256"]
    )
    assert not SCHEMA_BOUNDS["frozen_before_initial_edits"]
    assert SCHEMA_BOUNDS["frozen_before_field_annotation_edit"]
    assert SCHEMA_BOUNDS["wrong_before"] == 8


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "case", SCHEMA_BOUNDS["cases"], ids=lambda c: str(c["seconds"])
)
def test_public_json_schema_and_runtime_agree_on_offset_range(key, case):
    spec = SPECS[key]
    schema = spec.output_model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    value = {
        "numerology_evidence": {
            "birth_clock": {"civil_utc_offset_seconds": case["seconds"]}
        }
    }
    accepted = not list(Draft202012Validator(schema).iter_errors(value))
    assert accepted == case["must_accept"]
    if accepted:
        model = spec.output_model.model_validate(value)
        actual = model.numerology_evidence.birth_clock.civil_utc_offset_seconds
        assert type(actual) is type(case["seconds"])
        assert actual == case["seconds"]
    else:
        with pytest.raises(ValidationError):
            spec.output_model.model_validate(value)
