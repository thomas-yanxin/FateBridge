"""Printed-edition terms, continuous boundaries and faithful text delivery."""

import copy
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.astro.ptolemy import build_ptolemy_layer
from fatebridge.core.astro.ptolemy_terms import terms_at
from fatebridge.core.classical_western import bound_lord
from fatebridge.core.contracts.output_charts import PtolemyLayer
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
)
from tests.unit_test.fixtures.western_natal import GREENWICH_EQUINOX_BIRTH as BIRTH

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-ptolemy-terms-robbins-1940.json"
    ).read_text()
)


def segments(system, index, sect):
    if system == "chaldaean":
        order = REFERENCE["chaldaean_order_by_triangle"][sect][index % 4]
        return list(zip(order, REFERENCE["chaldaean_lengths"]))
    else:
        pass
    row = REFERENCE[system][index]
    assert row[0] == SIGNS[index]
    return row[1:]


@pytest.mark.parametrize("sect", ["day", "night"])
@pytest.mark.parametrize("system", ["egyptian", "chaldaean", "ptolemaic"])
@pytest.mark.parametrize("index", range(12))
def test_all_printed_segments_integer_degrees_and_float_boundaries(
    sect: str, system: str, index
) -> None:
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
def test_chaldaean_totals_match_the_main_text_not_fitted_cells(sect: str) -> None:
    counts = Counter(
        terms_at(degree + 0.5, sect)["chaldaean"]["lord"] for degree in range(360)
    )
    assert counts == REFERENCE["chaldaean_totals"][sect]


def test_printed_libra_mars_cell_is_not_the_html_transcription() -> None:
    term = terms_at(205, "day")["ptolemaic"]
    assert term["lord"] == REFERENCE["online_discrepancy"]["printed_lord"] == "Mars"
    assert term["lord"] != REFERENCE["online_discrepancy"]["html_lord"]
    assert (term["start_degree"], term["end_degree"]) == (24, 30)


def test_systems_and_day_night_cannot_be_substituted_for_each_other() -> None:
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
def test_nonfinite_terms_are_rejected(value) -> None:
    with pytest.raises(ValueError, match="finite"):
        terms_at(value, "day")


def test_unknown_sect_is_not_silently_a_day_chart() -> None:
    with pytest.raises(ValueError, match="explicit"):
        terms_at(16, "unknown")


def test_new_layer_is_typed_bounded_and_sidereal_is_unsupported() -> None:
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


def test_chart_retains_ptolemy_term_evidence() -> None:
    result = calculate_core_chart_analysis(**BIRTH)
    ptolemy = result["classical"]["ptolemy"]
    assert ptolemy["planets"]
    assert ptolemy["term_policy"]
    assert ptolemy["term_source_url"]
