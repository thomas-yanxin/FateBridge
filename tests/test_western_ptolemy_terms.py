"""Printed-edition terms, continuous boundaries and faithful text delivery."""

import copy
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.classical_western import bound_lord
from fatebridge.core.output_charts import PtolemyLayer
from fatebridge.core.ptolemy import build_ptolemy_layer
from fatebridge.core.ptolemy_terms import terms_at
from fatebridge.services.astrology import (
    _build_ptolemy_term_reading,
    calculate_core_chart_analysis,
)
from tests.test_western_accuracy import BIRTH

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/western-ptolemy-terms-robbins-1940.json"
    ).read_text()
)


def segments(system, index, sect):
    if system == "chaldaean":
        order = REFERENCE["chaldaean_order_by_triangle"][sect][index % 4]
        return list(zip(order, REFERENCE["chaldaean_lengths"]))
    row = REFERENCE[system][index]
    assert row[0] == SIGNS[index]
    return row[1:]


@pytest.mark.parametrize("sect", ["day", "night"])
@pytest.mark.parametrize("system", ["egyptian", "chaldaean", "ptolemaic"])
@pytest.mark.parametrize("index", range(12))
def test_all_printed_segments_integer_degrees_and_float_boundaries(sect, system, index):
    row = segments(system, index, sect)
    assert len(row) == 5 and sum(n for _, n in row) == 30
    assert len({lord for lord, _ in row}) == 5
    start = 0
    for position, (lord, count) in enumerate(row):
        end = start + count
        for degree in range(start, end):
            # Every integer degree and midpoint, independently derived from source lengths.
            for fraction in (0, 0.5):
                term = terms_at(index * 30 + degree + fraction, sect)[system]
                assert term["lord"] == lord
                assert (term["start_degree"], term["end_degree"]) == (start, end)
        global_start = index * 30 + start
        assert terms_at(global_start, sect)[system]["lord"] == lord
        assert (
            terms_at(math.nextafter(global_start, math.inf), sect)[system]["lord"]
            == lord
        )
        # Use nextafter on the absolute longitude so addition cannot erase the residual.
        before = math.nextafter(global_start, -math.inf)
        if start:
            previous = row[position - 1][0]
        else:
            previous = segments(system, (index - 1) % 12, sect)[-1][0]
        assert terms_at(before, sect)[system]["lord"] == previous
        start = end


@pytest.mark.parametrize("sect", ["day", "night"])
def test_chaldaean_totals_match_the_main_text_not_fitted_cells(sect):
    counts = Counter(
        terms_at(degree + 0.5, sect)["chaldaean"]["lord"] for degree in range(360)
    )
    assert counts == REFERENCE["chaldaean_totals"][sect]


def test_printed_libra_mars_cell_is_not_the_html_transcription():
    term = terms_at(205, "day")["ptolemaic"]
    assert term["lord"] == REFERENCE["online_discrepancy"]["printed_lord"] == "Mars"
    assert term["lord"] != REFERENCE["online_discrepancy"]["html_lord"]
    assert (term["start_degree"], term["end_degree"]) == (24, 30)


def test_systems_and_day_night_cannot_be_substituted_for_each_other():
    day, night = terms_at(16, "day"), terms_at(16, "night")
    assert day["chaldaean"]["lord"] == "Saturn"
    assert night["chaldaean"]["lord"] == "Mercury"
    assert day["egyptian"] == night["egyptian"]
    assert day["ptolemaic"] == night["ptolemaic"]
    assert terms_at(13, "day")["egyptian"]["lord"] == "Mercury"
    assert terms_at(13, "day")["ptolemaic"]["lord"] == "Venus"
    # The existing eclectic score continues to use its declared Egyptian terms.
    assert bound_lord("Aries", 13) == "Mercury"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_terms_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        terms_at(value, "day")


def test_unknown_sect_is_not_silently_a_day_chart():
    with pytest.raises(ValueError, match="explicit"):
        terms_at(16, "unknown")


def test_new_layer_is_typed_bounded_and_sidereal_is_unsupported():
    layer = build_ptolemy_layer({"Sun": 205}, "day", tropical=True)
    typed = PtolemyLayer.model_validate(layer)
    assert (
        typed.planets["Sun"].terms["ptolemaic"].model_dump()
        == layer["planets"]["Sun"]["terms"]["ptolemaic"]
    )
    assert layer["planets"]["Sun"]["terms"]["ptolemaic"]["lord"] == "Mars"
    assert "Libra" in layer["term_transcription_note"]
    assert "score" not in json.dumps(layer)
    unsupported = build_ptolemy_layer({"Sun": 205}, "day", tropical=False)
    assert unsupported["status"] == "unsupported_zodiac"
    assert unsupported["planets"] == {}


def test_term_reading_tracks_returned_facts_and_sect_without_a_strength_claim():
    payload = {
        "classical": {
            "sect": "day",
            "ptolemy": build_ptolemy_layer({"Sun": 205}, "day", tropical=True),
        }
    }
    text = _build_ptolemy_term_reading(payload)
    assert "昼盘" in text and "托勒密界主火星[24,30)°" in text
    changed = copy.deepcopy(payload)
    changed["classical"]["ptolemy"]["planets"]["Sun"]["terms"]["ptolemaic"] = {
        "lord": "Venus",
        "start_degree": 6,
        "end_degree": 11,
    }
    altered = _build_ptolemy_term_reading(changed)
    assert "托勒密界主金星[6,11)°" in altered
    assert "托勒密界主火星[24,30)°" not in altered
    assert "不据此推断整体强弱或现实事件" in text


def test_complete_reading_export_and_dependencies_include_same_term_text():
    result = calculate_core_chart_analysis(**BIRTH, chart_variant="hellen_chart")
    assert "error" not in result
    text = result["interpretation"]["original_text_terms"]
    assert text in result["summary"] and text in result["snapshot_text"]
    evidence = result["interpretation_evidence"]["original_text_terms"]
    assert evidence["kind"] == "primary_text_rule_interpretation"
    assert evidence["policy_id"] == "ptolemy_robbins_printed_terms_v1"
    for path in evidence["source_paths"]:
        value = result
        for token in path.split("."):
            value = value[token]
        assert value is not None
