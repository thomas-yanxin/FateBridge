"""Compute determined magnitudes without inventing unresolved strength signs.

Raman76-77's magnitude formula is independent of which planet receives it.
Cheshta controls here are mathematical operands, not observed natal positions.
"""

import copy
import math
from fractions import Fraction
from itertools import combinations

import pytest

from fatebridge.core import jyotish_mean
from fatebridge.core.jyotish_balas import PLANETS
from fatebridge.core.jyotish_evidence import cheshta_ruler_provenance
from fatebridge.core.jyotish_motion import cheshta_arc
from fatebridge.core.jyotish_strength import SOURCE_ID
from fatebridge.core.jyotish_war import STARS, THROUGH_HORA, war_bala
from tests.test_jyotish_transports import call_surfaces

DISCS = {
    "Mars": "9.4",
    "Mercury": "6.6",
    "Jupiter": "190.4",
    "Venus": "16.6",
    "Saturn": "158.0",
}


def war_inputs():
    longitudes = dict(zip(PLANETS, [200, 250, 30, 80, 130, 180, 230]))
    components = {key: {"summary": dict.fromkeys(PLANETS, 0.0)} for key in THROUGH_HORA}
    sthana = {
        "profile": {"id": "independent_hand_operands"},
        "summary": {p: {"total_virupa": 0.0} for p in PLANETS},
    }
    dig = {
        "source_id": "independent_hand_operands",
        "summary": dict.fromkeys(PLANETS, 0.0),
    }
    return longitudes, components, sthana, dig


@pytest.mark.parametrize("a,b", list(combinations(STARS, 2)))
@pytest.mark.parametrize("positions", [(120.0, 120.0), (359.75, 0.25)])
def test_unknown_pair_winner_does_not_erase_the_determined_raman_magnitude(
    a, b, positions
):
    longitudes, components, sthana, dig = war_inputs()
    # Move all uninvolved stars away from the artificial selected pair.
    for index, planet in enumerate(p for p in STARS if p not in [a, b]):
        longitudes[planet] = 30.0 + 60 * index
    longitudes[a], longitudes[b] = positions
    sthana["summary"][a]["total_virupa"] = 200.0
    sthana["summary"][b]["total_virupa"] = 100.0
    value = war_bala(
        longitudes,
        components,
        {"fixed": components["paksha_bala"]["summary"]},
        sthana,
        dig,
    )
    pair = value["evidence"]["fixed"]["pairs"][0]
    expected = float(Fraction(100) / abs(Fraction(DISCS[a]) - Fraction(DISCS[b])))
    assert pair["amount_virupa"] == expected
    assert pair["winner"] is None
    assert value["summary"][a] is value["summary"][b] is None
    assert value["status"] == "partial_unadjudicated_pairs"
    assert set(value["unresolved_planets"]) == {a, b}


def test_zero_magnitude_is_known_without_creating_a_signed_zero_award():
    l, c, s, d = war_inputs()
    l.update(Mars=359.75, Venus=0.25)
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert value["evidence"]["fixed"]["pairs"][0]["amount_virupa"] == 0
    assert value["summary"]["Mars"] is value["summary"]["Venus"] is None


def test_missing_prewar_input_keeps_even_the_pair_magnitude_unknown():
    l, c, s, d = war_inputs()
    l.update(Mars=359.75, Venus=0.25)
    d["summary"]["Mars"] = None
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert value["evidence"]["fixed"]["pairs"][0]["amount_virupa"] is None


def test_simultaneous_three_star_war_does_not_acquire_unregistered_pair_magnitudes():
    l, c, s, d = war_inputs()
    l.update(Mars=120, Venus=120.25, Mercury=120.5)
    s["summary"]["Mars"]["total_virupa"] = 200.0
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert len(value["pairs"]) == 3
    assert all(
        row["amount_virupa"] is None for row in value["evidence"]["fixed"]["pairs"]
    )


@pytest.mark.parametrize("rotation", range(0, 360, 30))
@pytest.mark.parametrize("apogee_offset", [0, 180])
def test_cheshta_opposed_midpoints_keep_a_unique_exact_strength(
    rotation, apogee_offset
):
    value = cheshta_arc(
        rotation,
        rotation + 180,
        rotation + apogee_offset,
        mean_frame="controlled_same_frame",
        true_frame="controlled_same_frame",
        seeghrochcha_frame="controlled_same_frame",
    )
    # The two opposite midpoints are each90deg from either original endpoint.
    expected = float(Fraction(90, 3))
    assert value["value"] == expected == 30
    assert value["status"] == "opposed_midpoint_not_adjudicated"
    assert len(value["branches"]) == 2
    assert all(branch["virupa"] == expected for branch in value["branches"])


def test_cheshta_display_rounding_cannot_turn_distinct_exact_branches_into_consensus():
    value = cheshta_arc(
        0,
        180,
        math.nextafter(0.0, 1.0),
        mean_frame="controlled_same_frame",
        true_frame="controlled_same_frame",
        seeghrochcha_frame="controlled_same_frame",
    )
    assert [branch["virupa"] for branch in value["branches"]] == [30.0, 30.0]
    assert value["value"] is None


@pytest.fixture
def controlled_opposed_component(monkeypatch):
    # Isolate the angular/source receipt contract. These are artificial model
    # operands, not a claim that Simon1994 or a real birth produces this sky.
    def component(apogee):
        means = {"Sun": apogee, "Mars": 0.0}
        monkeypatch.setattr(jyotish_mean, "mean_longitudes", lambda jd: means)
        arc = cheshta_arc(
            0.0,
            180.0,
            apogee,
            mean_frame=jyotish_mean.FRAME,
            true_frame=jyotish_mean.FRAME,
            seeghrochcha_frame=jyotish_mean.FRAME,
        )
        return {
            "source_id": SOURCE_ID,
            "scenarios": {"controlled": {"Mars": arc["value"]}},
            "model_context": {
                "selected": jyotish_mean.MODEL,
                "status": "computed_declared_secular_model",
                "source_id": jyotish_mean.SOURCE["id"],
                "frame": jyotish_mean.FRAME,
                "julian_day_tt": 2451545.0,
                "mean_longitudes": means,
                "true_position_provenance": {
                    "Mars": {
                        "longitude": 180.0,
                        "frame": jyotish_mean.FRAME,
                        "ephemeris_model": "controlled_geometric_operand",
                    }
                },
                "planet_evidence": {
                    "Mars": {
                        "mean_longitude": 0.0,
                        "true_longitude": 180.0,
                        "seeghrochcha": apogee,
                        "arc": arc,
                    }
                },
            },
        }

    return component


def test_same_run_source_receipt_accepts_only_the_exact_opposed_consensus(
    controlled_opposed_component,
):
    component = controlled_opposed_component(0.0)
    receipt = cheshta_ruler_provenance("Mars", component, {})
    assert component["scenarios"]["controlled"]["Mars"] == 30
    assert receipt["method_context"]["calculation_status"] == (
        "opposed_midpoint_not_adjudicated"
    )
    assert "两分支精确同值" in receipt["description"]
    assert receipt["method_context"]["five_star_mean_model_applied"] is True


@pytest.mark.parametrize("apogee", [100.0, math.nextafter(0.0, 1.0)])
def test_same_run_source_receipt_rejects_fabricated_opposed_consensus(
    controlled_opposed_component, apogee
):
    component = controlled_opposed_component(apogee)
    assert component["scenarios"]["controlled"]["Mars"] is None
    # Keep the correct ambiguous branches but fabricate a common scalar.
    component["model_context"]["planet_evidence"]["Mars"]["arc"]["value"] = 30.0
    component["scenarios"]["controlled"]["Mars"] = 30.0
    with pytest.raises(ValueError, match="mean/geometry/arc chain"):
        cheshta_ruler_provenance("Mars", component, {})


@pytest.mark.parametrize("field", ["mean_longitude", "true_longitude", "seeghrochcha"])
def test_same_run_consensus_receipt_rejects_forged_angular_operands(
    controlled_opposed_component, field
):
    component = copy.deepcopy(controlled_opposed_component(0.0))
    component["model_context"]["planet_evidence"]["Mars"][field] += 1.0
    with pytest.raises(ValueError, match="mean/geometry/arc chain"):
        cheshta_ruler_provenance("Mars", component, {})


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_actual_1977_origin_pair_magnitude_reaches_three_surfaces_without_a_verdict(
    monkeypatch, capsys, key
):
    payload = dict(
        birth_year=1977,
        birth_month=5,
        birth_day=29,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        saptavargaja_profile="raman_30",
        drekkana_profile="raman_36",
        divisions=[9],
    )
    value = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.strengths.kala_bala.components.yuddha_bala",
            "india.strengths.shadbala_assessment",
            "india.profile.saptavargaja_profile",
            "india.profile.drekkana_profile",
        ],
    )
    india = value["india"]
    war = india["strengths"]["kala_bala"]["components"]["yuddha_bala"]
    assert india["profile"]["saptavargaja_profile"] == "raman_30"
    assert india["profile"]["drekkana_profile"] == "raman_36"
    assert war["pairs"][0]["planets"] == ["Mars", "Venus"]
    assert war["pairs"][0]["winner"] is None
    assert war["status"] == "partial_unadjudicated_pairs"
    assert war["summary"]["Mars"] is war["summary"]["Venus"] is None
    for branch in war["evidence"].values():
        inputs = branch["prewar_basis"]
        left = sum((Fraction(v) for v in inputs["Mars"]["inputs"].values()), Fraction())
        right = sum(
            (Fraction(v) for v in inputs["Venus"]["inputs"].values()), Fraction()
        )
        assert branch["pairs"][0]["amount_virupa"] == float(
            abs(left - right) / Fraction("7.2")
        )
    assert india["strengths"]["shadbala_assessment"]["total_virupa"] is None
