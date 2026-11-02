"""Selected printed cells/examples, independent Decimal boundaries and gates.

The fixture was frozen before runtime implementation. Table parity is manual
transcription evidence, not independent expert criticism or outcome accuracy.
Synthetic route states and event brackets below are explicitly not ephemerides.
"""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.astro.parts import _essential_dignity
from fatebridge.core.astrology_election import _dignity
from fatebridge.core.astrology_horary import _applying_aspect, _planet_state
from fatebridge.core.classical_western import (
    build_planet_classical,
    essential_dignities,
)
from fatebridge.core.horary_conditions import (
    _moon_next_target,
    evaluate_lilly_conditions,
)
from fatebridge.core.lilly import dignity_at, pair_reception, reception
from fatebridge.core.output_western import Horary
from fatebridge.core.ptolemy_terms import terms_at
from fatebridge.services.astrology import _build_classical_lines
from fatebridge.services.western_horary import calculate_horary
from tests.test_western_horary import QUESTION

PATH = Path(__file__).parent / "fixtures/western-lilly-reception-1647.json"
REFERENCE = json.loads(PATH.read_text())


def test_manual_source_frozen_before_runtime_and_not_substituted_by_another_edition():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "23f6494920ed94e9e5c82f8a4710590b3fcb3652c3f29e5f3314031c71fb4a99"
    )
    assert len(REFERENCE["term_endpoints"]) == 12
    for longitude, printed, robbins in (
        (55.0, "Saturn", "Mars"),
        (73.5, "Jupiter", "Venus"),
        (122.0, "Saturn", "Jupiter"),
        (192.0, "Jupiter", "Mercury"),
        (292.0, "Mars", "Saturn"),
        (355.5, "Mars", "Saturn"),
    ):
        selected = dignity_at("Mercury", longitude, "day")["lords"]["bound"]
        assert selected == printed
        assert terms_at(longitude, "day")["ptolemaic"]["lord"] == robbins
        assert printed != robbins


def printed_lords(longitude, sect):
    # Independent arithmetic, manual source cells. No runtime tables consulted.
    with localcontext() as context:
        context.prec = 1200
        value = Decimal.from_float(longitude) % Decimal(360)
        if value < 0:
            value += 360
        index, degree = int(value // 30), value % 30
        sign = REFERENCE["term_endpoints"][index][0]
        term = next(
            lord for lord, end in REFERENCE["term_endpoints"][index][1:] if degree < end
        )
        trip = next(
            group[sect] for group in REFERENCE["triplicity"] if sign in group["signs"]
        )
        exalted = next(
            (p for p, (s, _) in REFERENCE["exaltations"].items() if s == sign), None
        )
        return {
            "rulership": REFERENCE["domicile"][index],
            "exaltation": exalted,
            "triplicity": trip,
            "bound": term,
            "face": REFERENCE["faces"][index][int(degree // 10) + 1],
        }


@pytest.mark.parametrize("sect", ["day", "night"])
def test_all_printed_cells_and_every_term_boundary_have_decimal_reference(sect):
    count = 0
    for index, row in enumerate(REFERENCE["term_endpoints"]):
        for _, endpoint in row[1:]:
            boundary = float(index * 30 + endpoint)
            for value in (
                math.nextafter(boundary, -math.inf),
                boundary,
                math.nextafter(boundary, math.inf),
            ):
                expected = printed_lords(value, sect)
                actual = dignity_at("Sun", value, sect)
                assert actual["lords"] == expected, (value, sect)
                for planet in REFERENCE["exaltations"]:
                    result = dignity_at(planet, value, sect)
                    assert result["dignities"] == [
                        k for k, lord in expected.items() if lord == planet
                    ]
                    assert result["peregrine"] == (not result["dignities"])
                    count += 1
    assert count == 1260


@pytest.mark.parametrize(
    "value", [-math.ulp(0.0), math.nextafter(30.0, 0), math.nextafter(360.0, 0)]
)
def test_unrounded_partition_is_not_promoted_during_float_delivery(value):
    result = dignity_at("Venus", value, "day")
    assert result["lords"] == printed_lords(value, "day")
    assert 0 <= result["degree_in_sign"] < 30 and 0 <= result["longitude"] < 360


@pytest.mark.parametrize("row", REFERENCE["p112_examples"])
def test_printed_p112_reciprocal_examples(row):
    (first, lon_a), (second, lon_b) = row["bodies"].items()
    result = pair_reception(first, lon_a, second, lon_b, row.get("sect", "day"))
    assert result["mutual"] is True
    assert result["mutual_same_kind"] == row["mutual_same_kind"]


def test_sect_specific_triplicity_and_mars_both_sects_water():
    day = pair_reception("Venus", 18, "Sun", 31, "day")
    night = pair_reception("Venus", 18, "Sun", 31, "night")
    assert "triplicity" in day["mutual_same_kind"]
    assert "triplicity" not in night["mutual_same_kind"]
    # The night pair still has mixed exaltation/domicile reception; do not
    # confuse 'not mutual by triplicity' with 'no reception of any kind'.
    assert night["mutual"] is True
    for sect in ("day", "night", None):
        for longitude in (91, 211, 331):
            assert "triplicity" in dignity_at("Mars", longitude, sect)["dignities"]


def test_unknown_sect_is_unknown_only_for_affected_fact_not_an_invented_night():
    result = dignity_at("Jupiter", 123.0, None)
    assert result["peregrine"] is None and result["unknown_dignities"] == ["triplicity"]
    assert reception("Jupiter", "Mercury", 123.0, None)["receives"] is None
    assert (
        reception("Jupiter", "Mercury", 123.0, None, allowed=("bound",))["receives"]
        is False
    )
    assert dignity_at("Saturn", 10, None)["peregrine"] is True
    shared = build_planet_classical(
        planet="Jupiter",
        sign="Aries",
        degree_in_sign=15.0,
        longitude=15.0,
        house=1,
        sun_longitude=100.0,
        chart_sect=None,
    )["essential"]
    assert shared["peregrine"] is None and shared["score"] is None
    assert shared["known_score"] == 0 and shared["unknown_dignities"] == ["triplicity"]
    text = _build_classical_lines(
        {"classical": {"planets": {"Jupiter": {"essential": shared}}}}
    )
    assert "三分待定" in text and "分值待定" in text and "(+0)" not in text


def test_one_way_reception_is_not_mutual_and_same_body_not_bilateral():
    result = pair_reception("Sun", 10, "Mars", 100, "day")
    assert result["mutual"] is False
    assert {
        (row["receiver"], row["guest"]): row["receives"] for row in result["directions"]
    } == {("Sun", "Mars"): False, ("Mars", "Sun"): True}
    same = pair_reception("Sun", 10, "Sun", 10, "day")
    assert same["mutual"] is None and same["directions"] == []


def test_sign_only_summary_does_not_claim_peregrine_without_all_five_dignities():
    for sign, longitude, minor_dignity in [
        ("Taurus", 55.0, "bound"),
        ("Sagittarius", 267.0, "face"),
    ]:
        assert minor_dignity in dignity_at("Saturn", longitude, "day")["dignities"]
        summary = _essential_dignity("Saturn", sign)
        assert summary["dignity"] == _dignity("Saturn", sign) == "no_major_dignity"
        assert "not_classified" in summary["scope"]


@pytest.mark.parametrize("row", REFERENCE["peregrine_examples"])
def test_peregrine_means_no_positive_dignity_even_if_fallen(row):
    result = dignity_at(row["planet"], row["longitude"], row["sect"])
    assert result["peregrine"] is row["peregrine"]
    if "simultaneous_debility" in row:
        assert row["simultaneous_debility"] in result["debilities"]
    if "positive_dignity" in row:
        assert row["positive_dignity"] in result["dignities"]
    shared = essential_dignities("Saturn", "Aries", 10.0, True)
    assert shared["peregrine"] is True and "fall" in shared["debilities"]
    assert "游离" in shared["labels_zh"] and "平" not in shared["labels_zh"]


def synthetic_states(**changes):
    positions = {
        "Saturn": (20, 0.03),
        "Jupiter": (310, 0.08),
        "Mars": (15, 0.5),
        "Sun": (260, 1),
        "Venus": (230, 1.2),
        "Mercury": (16, 1.5),
        "Moon": (100, 13),
    }
    positions.update(changes)
    return {
        p: {"planet": p, "longitude": float(lon), "speed": float(speed)}
        for p, (lon, speed) in positions.items()
    }


def evaluate(states, first, second, *, sect="day", motion=None, zodiac="Tropic"):
    result = evaluate_lilly_conditions(
        states,
        first,
        second,
        sect,
        _applying_aspect,
        lunar_motion=motion,
        zodiac_type=zodiac,
    )
    partial = {"perfection": {"lilly_conditions": result}}
    Horary.model_validate(partial)
    Draft202012Validator(Horary.model_json_schema()).validate(partial)
    return result


def test_all_routes_are_kept_and_p126_translation_does_not_accept_exaltation_alone():
    states = synthetic_states(Sun=(15, 1.0))
    result = evaluate(states, "Sun", "Saturn", sect="night")
    assert any(r["mode"] == "direct" for r in result["routes"])
    route = next(r for r in result["routes"] if r.get("carrier") == "Mercury")
    assert route["source_planet"] == "Sun" and route["target_planet"] == "Saturn"
    assert reception("Sun", "Mercury", 16, "night")["receives"] is True
    assert route["receptions"][0]["receives"] is False
    assert route["status"] == "nominal_condition_not_met"
    assert route["full_path_accepted"] is False
    assert any(c["passed"] is None for c in route["conditions"])
    states["Mercury"]["speed"] = 0.0
    assert not any(
        r.get("carrier") == "Mercury"
        for r in evaluate(states, "Sun", "Saturn")["routes"]
    )


def test_p126_collection_reception_direction_is_endpoints_receive_collector():
    states = synthetic_states(Saturn=(350, 0.03), Venus=(42, 1.0), Mars=(256, 0.5))
    result = evaluate(states, "Venus", "Mars")
    route = next(r for r in result["routes"] if r.get("collector") == "Saturn")
    assert [
        (r["receiver"], r["guest"], r["receives"]) for r in route["receptions"]
    ] == [("Venus", "Saturn", True), ("Mars", "Saturn", True)]
    assert not reception("Saturn", "Venus", 42, "day")["receives"]
    assert not reception("Saturn", "Mars", 256, "day")["receives"]
    assert route["status"] == "remaining_conditions_unverified"


def test_p125_opposition_does_not_replace_mutual_domicile_with_exaltation():
    result = evaluate(
        synthetic_states(Saturn=(10, 0.03), Sun=(189, 1.0)), "Saturn", "Sun"
    )
    assert result["principal_reception"]["mutual_same_kind"] == [
        "exaltation",
        "triplicity",
    ]
    route = next(r for r in result["routes"] if r["mode"] == "direct")
    assert (
        next(
            c["passed"]
            for c in route["conditions"]
            if c["code"] == "mutual_reception_by_domicile_now"
        )
        is False
    )
    assert result["p112_mutual_reception"]["premise_satisfied"] is True
    assert "成事支持" in result["p112_mutual_reception"]["conditional_reading_zh"]


def fake_motion(*events, ambiguous=()):
    # Synthetic event-bracket controls, not observed/native ephemerides.
    return {
        "constant_velocity_projection": False,
        "status": "computed",
        "contacts": [
            {"other": p, "root_bracket_tt": [t, math.nextafter(t, math.inf)]}
            for p, t in events
        ],
        "ambiguous_boundary_contacts": list(ambiguous),
    }


def test_native_window_order_gate_is_tristate_and_not_inferred_from_orb_order():
    assert _moon_next_target("Saturn", fake_motion(("Saturn", 2451546.0)))[0] is True
    assert (
        _moon_next_target(
            "Saturn", fake_motion(("Jupiter", 2451546.0), ("Saturn", 2451547.0))
        )[0]
        is False
    )
    assert _moon_next_target("Saturn", fake_motion())[0] is None
    assert (
        _moon_next_target(
            "Saturn", fake_motion(("Saturn", 2451546.0), ("Jupiter", 2451546.0))
        )[0]
        is None
    )
    linear = fake_motion(("Saturn", 2451546.0))
    linear["constant_velocity_projection"] = True
    assert _moon_next_target("Saturn", linear)[0] is None


def test_lunar_translation_route_uses_actual_event_order_gate_not_only_current_orb():
    states = synthetic_states(Moon=(24, 13), Mars=(23, 0.5), Saturn=(28, 0.03))
    for events, expected in [
        ((("Saturn", 2451546.0),), True),
        ((("Jupiter", 2451546.0), ("Saturn", 2451547.0)), False),
    ]:
        result = evaluate(states, "Mars", "Saturn", motion=fake_motion(*events))
        route = next(r for r in result["routes"] if r.get("carrier") == "Moon")
        assert route["receptions"][0]["receives"] is True
        assert (
            next(
                c["passed"]
                for c in route["conditions"]
                if c["code"] == "lunar_next_contact_is_recipient_in_search_window"
            )
            is expected
        )
        assert route["next_lunar_contact"]["other"] == events[0][0]
        assert route["full_path_accepted"] is False


def test_unknown_zodiac_and_illegal_self_reception_do_not_get_source_acceptance():
    result = evaluate(synthetic_states(), "Mars", "Saturn", zodiac=None)
    assert result["coordinate_scope"] == "unknown_or_unsupported_zodiac"
    with pytest.raises(ValueError, match="Distinct"):
        reception("Sun", "Sun", 120.0, "day")
    with pytest.raises(ValueError):
        pair_reception("Pluto", 0, "Pluto", 0, "day")


def test_native_service_carries_source_fact_receipts_and_keeps_whole_judgement_open():
    result = calculate_horary(**QUESTION, category="marriage")
    assert "error" not in result, result
    h = result["horary"]
    assert len(h["planets"]) == 7
    assert all(
        p["dignities"] == p["essential_condition"]["dignities"]
        for p in h["planets"].values()
    )
    condition = h["perfection"]["lilly_conditions"]
    assert condition["chart_sect"] == "day"
    assert condition["coordinate_scope"] == "tropical_selected_edition"
    assert h["perfection"]["perfects"] is None and h["verdict"] == "uncertain"
    assert condition["principal_reception"]["mutual_same_kind"] == ["face"]
    assert condition["p112_mutual_reception"]["premise_satisfied"] is True
    assert h["perfection"]["candidate"] is False
    assert "reported_separately" in h["perfection"]["candidate_scope"]
    assert "历史分离" in h["reasoning"]
    assert "lilly_conditions" in result["snapshot_text"]
    fake = SimpleNamespace(sun=SimpleNamespace(abs_pos=123, speed=1))
    assert _planet_state(fake, "Sun")["essential_condition"]["chart_sect"] is None


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_invalid_longitude_is_rejected(value):
    with pytest.raises(ValueError):
        dignity_at("Sun", value, "day")
