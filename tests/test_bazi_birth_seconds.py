"""Known clock components survive binding, normalization and luck boundaries.

All birth inputs are fictional engineering fixtures. A supplied component is
not evidence of the accuracy of an actual birth record.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from fatebridge.core.requests.bazi import BaziBirthRequest
from fatebridge.core.requests.birth import BaziClockRequest
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import PersonInfo, create_person_info
from fatebridge.utils.solar_time import normalize_birth_time
from tests.test_agentic_nested_outputs import inputs

TIMING_KEYS = {
    "timing_analysis",
    "dayun_analysis",
    "liunian_analysis",
    "liuyue_analysis",
    "liuri_analysis",
    "liushi_analysis",
    "jieqi_timeline_analysis",
}
SPECS = [
    s
    for s in CATALOG
    if (s.family == "bazi" and issubclass(s.request_model, BaziClockRequest))
    or s.key in TIMING_KEYS
]
BASE = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_timezone="UTC",
    use_true_solar_time=False,
)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.key)
def test_every_actual_bazi_and_timing_binding_preserves_second_and_presence(spec):
    req = spec.request_model.model_validate(
        {**inputs(spec), **BASE, "birth_minute": 20, "birth_second": 59}
    )
    _, args, kwargs = spec.bind(req)
    person = args[0]
    assert person.birth_second == 59
    assert "birth_minute" in person.model_fields_set
    assert "birth_second" not in kwargs
    assert normalize_birth_time(person).input_datetime == datetime(
        1990, 5, 15, 10, 20, 59
    )


@pytest.mark.parametrize("bad", [-1, 60, True, False, 0.5, "1"])
def test_invalid_birth_second_is_rejected_without_rounding(bad):
    with pytest.raises(ValidationError):
        BaziBirthRequest(**BASE, birth_minute=20, birth_second=bad)
    with pytest.raises(ValidationError):
        PersonInfo(**BASE, birth_minute=20, birth_second=bad)


@pytest.mark.parametrize("second", [0, 59])
def test_second_requires_an_explicit_minute_instead_of_assuming_one(second):
    with pytest.raises(ValidationError):
        BaziBirthRequest(**BASE, birth_second=second)
    with pytest.raises(ValidationError):
        PersonInfo(**BASE, birth_second=second)


@pytest.mark.parametrize(
    "minute,second,omitted",
    [
        (None, None, ["minute", "second"]),
        (0, None, ["second"]),
        (20, None, ["second"]),
        (0, 0, []),
        (20, 59, []),
    ],
)
def test_receipt_distinguishes_provided_zero_from_compatibility_defaults(
    minute, second, omitted
):
    from fatebridge.utils.birth_clock import birth_clock_input_receipt

    data = dict(BASE)
    if minute is not None:
        data["birth_minute"] = minute
    if second is not None:
        data["birth_second"] = second
    spec = next(s for s in SPECS if s.key == "bazi_birth")
    _, args, _ = spec.bind(spec.request_model.model_validate(data))
    person = args[0]
    receipt = birth_clock_input_receipt(person, normalize_birth_time(person))
    assert receipt["omitted_components"] == omitted
    assert receipt["calculation_defaults"] == {key: 0 for key in omitted}
    assert receipt["uncertainty_interval"] is None
    assert receipt["observed_precision_certified"] is False
    assert (
        receipt["nominal_civil_datetime"]
        == datetime(1990, 5, 15, 10, minute or 0, second or 0).isoformat() + "+00:00"
    )
    assert person.birth_minute == (minute or 0)
    assert person.birth_second == second


def test_helper_preserves_the_distinction_between_omitted_and_zero_minute():
    omitted = create_person_info(1990, 5, 15, 10)
    zero = create_person_info(1990, 5, 15, 10, birth_minute=0)
    assert "birth_minute" not in omitted.model_fields_set
    assert "birth_minute" in zero.model_fields_set
    assert (
        normalize_birth_time(omitted).input_datetime
        == normalize_birth_time(zero).input_datetime
    )


def test_known_seconds_survive_solar_clock_and_minute_uncertainty_grid(monkeypatch):
    import fatebridge.services.timing_uncertainty as uncertainty

    person = PersonInfo(
        **{**BASE, "use_true_solar_time": True},
        birth_longitude=0,
        birth_minute=20,
        birth_second=59,
    )
    nominal = normalize_birth_time(person)
    earlier = normalize_birth_time(person.model_copy(update={"birth_second": 0}))
    assert (nominal.input_datetime - earlier.input_datetime).total_seconds() == 59
    assert (
        nominal.corrected_datetime - earlier.corrected_datetime
    ).total_seconds() == pytest.approx(59, abs=0.02)
    # Gender is unknown, so this check intentionally evaluates natal candidates.
    seen = []
    original = uncertainty.normalize_birth_time

    def observe(sample, **kwargs):
        result = original(sample, **kwargs)
        seen.append(result.input_datetime.second)
        return result

    monkeypatch.setattr(uncertainty, "normalize_birth_time", observe)
    result = uncertainty.analyze_birth_time_range(
        person, 1, analysis_moment=datetime(2026, 1, 1)
    )
    assert result["sample_count"] == 3
    assert seen == [59, 59, 59, 59]
    assert "未证明采样间秒级无变化" in result["interpretation_scope"]


def test_seconds_reach_dayun_elapsed_time_and_declared_conversion():
    a = PersonInfo(**BASE, birth_minute=20, birth_second=0, gender="男")
    b = a.model_copy(update={"birth_second": 59})
    aa, bb = normalize_birth_time(a), normalize_birth_time(b)
    first = TimingAnalysis.calculate_dayun_timeline(
        aa.input_datetime, "男", ("辛", "巳"), timezone_name="UTC"
    )
    second = TimingAnalysis.calculate_dayun_timeline(
        bb.input_datetime, "男", ("辛", "巳"), timezone_name="UTC"
    )
    assert first["start_details"]["elapsed_seconds"] - second["start_details"][
        "elapsed_seconds"
    ] == pytest.approx(59, abs=1e-6)
    start_difference = datetime.fromisoformat(
        second["start_at"]
    ) - datetime.fromisoformat(first["start_at"])
    assert start_difference == timedelta(seconds=59 - 59 * 120)


def test_public_birth_context_and_display_keep_seconds_and_default_receipt():
    from fatebridge.services.birth_context import build_birth_computation_context
    from fatebridge.services.birth_payload import build_destiny_payload

    person = PersonInfo(**BASE, birth_minute=20, birth_second=59)
    result = build_destiny_payload(build_birth_computation_context(person))
    assert result["person_info"]["birth_datetime"].endswith("10时20分59秒")
    assert result["calendar_context"]["birth_time_input"]["omitted_components"] == []


def test_other_systems_do_not_gain_an_accepted_but_ignored_second_parameter():
    from fatebridge.core.requests.metaphysics import ZiweiBirthRequest

    assert "birth_second" not in ZiweiBirthRequest.model_fields
    with pytest.raises(ValidationError):
        ZiweiBirthRequest(**BASE, birth_minute=20, birth_second=59)
