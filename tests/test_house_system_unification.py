"""House-system parameter unification (#2b).

FateBridge historically exposed two parallel conventions for the same concept:
the core/relative chart family takes an integer ``hsys`` (0..8) while the
western timing/lifespan/horary/election family takes a ``house_system`` letter
string ('P', 'R', ...). That split made agents and users guess which knob a
given tool wants.

The integer side already accepts letters and keys (via
``_coerce_house_system_code``). These tests pin the symmetric direction: the
``house_system`` chokepoint (``normalize_house_system``) must also accept the
integer codes 0..8 and the canonical keys ("equal_mc", "sripati", ...), so a
single mental model — int code, SE letter, or key — works on every surface.
"""

from __future__ import annotations

import pytest

from fatebridge.utils.house_systems import house_system_fields, normalize_house_system

# Integer code -> Swiss Ephemeris letter, identical to the core chart's
# RELATIVE_HOUSE_SYSTEM_SPECS (0=whole_sign ... 8=equal_mc).
_CODE_TO_LETTER = {
    0: "W",
    1: "B",
    2: "R",
    3: "P",
    4: "K",
    5: "V",
    6: "T",
    7: "S",
    8: "D",
}


@pytest.mark.parametrize("code,letter", sorted(_CODE_TO_LETTER.items()))
def test_normalize_accepts_integer_codes(code, letter):
    assert normalize_house_system(code) == letter
    assert normalize_house_system(str(code)) == letter


def test_normalize_accepts_canonical_keys():
    # These keys are the ones the integer (hsys) family reports; the letter
    # family must understand them too. equal_mc and sripati were the gaps that
    # silently fell back to Placidus.
    assert normalize_house_system("equal_mc") == "D"
    assert normalize_house_system("equal_mc".upper()) == "D"
    assert normalize_house_system("sripati") == "S"
    assert normalize_house_system("whole_sign") == "W"


def test_unknown_never_substitutes_a_default_chart():
    # Explicit invalid selectors fail; only a missing override uses a default.
    with pytest.raises(ValueError):
        normalize_house_system(99)
    with pytest.raises(ValueError):
        normalize_house_system("not-a-system")
    assert normalize_house_system(None, default="R") == "R"
    assert normalize_house_system(0, default="R") == "W"  # valid code wins over default


@pytest.mark.parametrize("value", [8, "8", "equal_mc", "R", "regiomontanus"])
def test_western_models_accept_every_convention(value):
    # The western timing/horary/election models must accept an integer code, a
    # numeric string, a key, or an SE letter — the same mental model as the
    # integer ``hsys`` family. (Previously the field was typed ``str`` and a bare
    # integer raised a ValidationError.)
    from fatebridge.core.requests.western_events import AstroHoraryRequest
    from fatebridge.core.requests.western_timing import WesternTimingRequest

    common = dict(
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_longitude=120.0,
        birth_latitude=30.0,
    )
    timing = WesternTimingRequest(**common, house_system=value)
    assert normalize_house_system(timing.house_system) in {
        "W",
        "B",
        "R",
        "P",
        "K",
        "V",
        "T",
        "S",
        "D",
    }
    horary = AstroHoraryRequest(
        question_year=2000,
        question_month=12,
        question_day=10,
        question_hour=9,
        longitude=121.47,
        latitude=31.23,
        house_system=value,
    )
    assert isinstance(horary.house_system, (int, str))


def test_western_default_house_system_unchanged():
    # The unification must not move any default: timing stays Placidus, horary
    # stays Regiomontanus (golden output must be byte-stable).
    from fatebridge.core.requests.western_events import AstroHoraryRequest
    from fatebridge.core.requests.western_timing import WesternTimingRequest

    timing = WesternTimingRequest(
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_longitude=120.0,
        birth_latitude=30.0,
    )
    assert normalize_house_system(timing.house_system) == "P"
    horary = AstroHoraryRequest(
        question_year=2000,
        question_month=12,
        question_day=10,
        question_hour=9,
        longitude=121.47,
        latitude=31.23,
    )
    assert normalize_house_system(horary.house_system) == "R"


def test_house_system_fields_descriptor():
    # The shared descriptor mirrors the core/relative chart_profile keys.
    assert house_system_fields("P") == {
        "house_system": "P",
        "house_system_code": 3,
        "house_system_label_zh": "Placidus",
    }
    assert house_system_fields(8)["house_system_label_zh"] == "天顶为第10宫宫头的等宫制"
    # A letter outside the 0..8 set still gets a readable label, code=None.
    assert house_system_fields("C") == {
        "house_system": "C",
        "house_system_code": None,
        "house_system_label_zh": "Campanus",
    }


def test_western_results_report_house_system_code_and_label():
    # Western horary/timing results must report the house system the same way the
    # core/relative charts do: a readable label and a numeric code alongside the
    # SE letter, so an agent never has to guess which system produced the result.
    from fatebridge.services.western_horary import calculate_horary
    from fatebridge.services.western_timing import calculate_western_timing_analysis

    horary = calculate_horary(
        question_year=2000,
        question_month=12,
        question_day=10,
        question_hour=9,
        longitude=121.47,
        latitude=31.23,
    )
    ctx = horary["analysis_context"]
    assert ctx["house_system"] == "R"  # horary default Regiomontanus
    assert ctx["house_system_code"] == 2
    assert ctx["house_system_label_zh"] == "Regiomontanus"

    timing = calculate_western_timing_analysis(
        name="x",
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_longitude=120.45,
        birth_latitude=32.54,
        birth_timezone="Asia/Shanghai",
    )
    tctx = timing["analysis_context"]
    assert tctx["house_system"] == "P"  # timing default Placidus
    assert tctx["house_system_code"] == 3
    assert tctx["house_system_label_zh"] == "Placidus"
