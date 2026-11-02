"""Independent primary month counters constrain the nominal-year correction."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.services.metaphysics import calculate_taiyi_analysis

ROOT = Path(__file__).resolve().parents[1]
SOFTWARE = ROOT / "tests/fixtures/taiyi_month_nominal_v39"
SOFTWARE_FREEZE = "5d609db2a3ec70a0ec13f03a815a05143562f683aa17b090accf18a24103c884"


def _predeclared_repair():
    assert (
        hashlib.sha256((SOFTWARE / "freeze.json").read_bytes()).hexdigest()
        == SOFTWARE_FREEZE
    )
    frozen = json.loads((SOFTWARE / "freeze.json").read_text())
    for base, key in ((SOFTWARE, "files"), (ROOT, "source_pins")):
        for name, digest in frozen[key].items():
            assert hashlib.sha256((base / name).read_bytes()).hexdigest() == digest
    return json.loads((SOFTWARE / "predeclared-repair.json").read_text())


PREDECLARED = _predeclared_repair()


def with_prior_default_origin_in_current_runtime(arguments, monkeypatch):
    """Causal control with identical current astronomy, not an old release replay.

    Restore the pre-V39 numerical origin once. Other profiles must ignore it.
    The call spy prevents a cached/no-op comparison from passing unnoticed.
    Historical whole-payload hashes remain separately reported as changed.
    """
    from fatebridge.core.metaphysics import taiyi_periods

    current_origin = taiyi_periods.jinjing_month_origin
    calls = []

    def prior_origin(cycle_year, month_offset):
        origin = current_origin(cycle_year, month_offset)
        annual = 1937281 + cycle_year - 724
        origin.update(
            counted_year=cycle_year,
            annual_accumulation=annual,
            completed_annual_accumulation=annual - 1,
            accumulation=(annual - 1) * 12 + month_offset + 1,
        )
        calls.append((cycle_year, month_offset))
        return origin

    with monkeypatch.context() as controlled:
        controlled.setattr(taiyi_periods, "jinjing_month_origin", prior_origin)
        result = calculate_taiyi_analysis(**arguments)
    assert "taiyi" in result
    assert len(calls) == (
        1 if arguments.get("calculation_mode", "year") == "month" else 0
    )
    return result


@pytest.mark.parametrize("index", [0, 1])
def test_default_month_counter_reproduces_primary_nominal_year(index, monkeypatch):
    source = PREDECLARED["primary_expected"][index]
    kwargs = source.get("input") or dict(
        analysis_year=1043,
        analysis_month=12,
        analysis_day=15,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode="month",
    )
    board = calculate_taiyi_analysis(**kwargs)["taiyi"]
    counter = board["core_board"]["accumulation"]
    if index == 0:
        assert counter == source["expected_accumulation"]
    else:
        assert (counter - 1) % 360 + 1 == source["expected_cycle360"]
        assert board["core_board"]["kook_number"] == source["expected_ju"]
    # Positive control: the actual numerical origin must be exercised and
    # differ by12; an ignored patch or cached result cannot satisfy this.
    prior = with_prior_default_origin_in_current_runtime(kwargs, monkeypatch)["taiyi"]
    assert counter == prior["core_board"]["accumulation"] + 12
    origin = board["calendar_rules"]["month_origin"]
    assert origin["counted_year"] == origin["cycle_year"] + 1
    assert origin["counter_unit"] == "twelve_jie_months"
    assert origin["mean_lunation_counter"] is False
    assert not board["ruleset"]["classical_acceptance_passed"]
