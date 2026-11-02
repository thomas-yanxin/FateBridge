"""Reject internally inconsistent motion receipts without grading astronomy."""

import copy

import pytest

from fatebridge.core.jyotish_evidence import cheshta_ruler_provenance
from fatebridge.core.jyotish_mean import STAR_PLANETS
from tests.test_jyotish_ruler_provenance import computed  # noqa: F401

FAULTS = [
    "mean_operand",
    "true_operand",
    "apogee_operand",
    "mean_model_value",
    "declared_TT",
    "geometry_longitude",
    "angular_midpoint",
    "model_frame",
    "geometry_frame",
    "coordinated_end_value",
    "invented_opposed_null",
]


def mutate(packet, planet, fault):
    model = packet["model_context"]
    evidence = model["planet_evidence"][planet]
    if fault in {"mean_operand", "true_operand", "apogee_operand"}:
        evidence[
            {
                "mean_operand": "mean_longitude",
                "true_operand": "true_longitude",
                "apogee_operand": "seeghrochcha",
            }[fault]
        ] += 1
    elif fault == "mean_model_value":
        model["mean_longitudes"][planet] += 1
    elif fault == "declared_TT":
        model["julian_day_tt"] += 1
    elif fault == "geometry_longitude":
        model["true_position_provenance"][planet]["longitude"] += 1
    elif fault == "angular_midpoint":
        evidence["arc"]["branches"][0]["midpoint"] += 1
    elif fault == "model_frame":
        model["frame"] = "sidereal_Lahiri"
    elif fault == "geometry_frame":
        model["true_position_provenance"][planet]["frame"] = "sidereal_Lahiri"
    elif fault == "coordinated_end_value":
        evidence["arc"]["value"] += 1
        packet["summary"][planet] += 1
        for row in packet["scenarios"].values():
            row[planet] += 1
    elif fault == "invented_opposed_null":
        evidence["arc"]["status"] = "opposed_midpoint_not_adjudicated"
        evidence["arc"]["value"] = None
        packet["summary"][planet] = None
        for row in packet["scenarios"].values():
            row[planet] = None
    else:
        raise AssertionError("Unregistered controlled fault")


@pytest.mark.parametrize("planet", STAR_PLANETS)
@pytest.mark.parametrize("fault", FAULTS)
def test_same_terminal_value_does_not_authenticate_inconsistent_operands(
    computed, planet, fault
):
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    mutate(motion, planet, fault)
    with pytest.raises(ValueError, match="model inputs"):
        cheshta_ruler_provenance(planet, motion, computed["strengths"]["kala_bala"])


@pytest.mark.parametrize("planet", ["Sun", "Moon", *STAR_PLANETS])
def test_source_label_must_agree_with_the_rule_the_receipt_names(computed, planet):
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    motion["source_id"] = "an_unrelated_author"
    with pytest.raises(ValueError, match="declared source"):
        cheshta_ruler_provenance(planet, motion, computed["strengths"]["kala_bala"])


@pytest.mark.parametrize("planet", STAR_PLANETS)
def test_a_valid_receipt_does_not_mutate_same_run_inputs(computed, planet):
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    before = copy.deepcopy(motion)
    receipt = cheshta_ruler_provenance(
        planet, motion, computed["strengths"]["kala_bala"]
    )
    assert motion == before
    assert receipt["method_context"]["calculation_status"] == "calculated_arc"


@pytest.mark.parametrize(
    "fault", ["branch_removed", "non_numeric_value", "boolean_value"]
)
def test_arc_shape_and_scalar_type_cannot_masquerade_as_computed_values(
    computed, fault
):
    motion = copy.deepcopy(computed["strengths"]["cheshta_bala"])
    arc = motion["model_context"]["planet_evidence"]["Mars"]["arc"]
    if fault == "branch_removed":
        arc["branches"].clear()
    else:
        arc["value"] = str(arc["value"]) if fault == "non_numeric_value" else True
    with pytest.raises(ValueError, match="model inputs"):
        cheshta_ruler_provenance("Mars", motion, computed["strengths"]["kala_bala"])
