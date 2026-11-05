"""A complete same-run Drik receipt must match physical D1, not just end values."""

import copy
import math

import pytest

from fatebridge.core import jyotish
from fatebridge.core.jyotish_balas import PLANETS, aspect_strength, verify_drik_evidence
from fatebridge.utils.errors import JyotishCalculationError
from tests.jyotish.test_jyotish_ruler_provenance import computed  # noqa: F401

FAULTS = [
    "matrix",
    "transposed",
    "contribution",
    "coordinated_summary",
    "nature",
    "removed_branch",
    "invented_branch",
    "elongation",
    "mercury_options",
    "source",
    "method",
    "source_accepted",
    "alternative_applied",
    "bool_zero",
    "missing_matrix",
    "other_D1",
    "all_zero",
]


def mutate(packet, d1, target, fault):
    first = next(iter(packet["scenarios"]))
    if fault == "matrix":
        packet["matrix"]["Mars"]["Saturn"] += 1
    elif fault == "transposed":
        packet["matrix"] = {
            a: {b: packet["matrix"][b][a] for b in PLANETS} for a in PLANETS
        }
    elif fault == "contribution":
        packet["scenarios"][first]["contributions"][target]["Jupiter"] += 1
    elif fault == "coordinated_summary":
        for row in packet["scenarios"].values():
            row["summary"][target] += 1
        if packet["summary"][target] is not None:
            packet["summary"][target] += 1
    elif fault == "nature":
        nature = packet["scenarios"][first]["natures"]["Mercury"]
        packet["scenarios"][first]["natures"]["Mercury"] = (
            "benefic" if nature == "malefic" else "malefic"
        )
    elif fault == "removed_branch":
        packet["scenarios"].pop(next(reversed(packet["scenarios"])))
        for q in PLANETS:
            values = {r["summary"][q] for r in packet["scenarios"].values()}
            packet["summary"][q] = next(iter(values)) if len(values) == 1 else None
        packet["conditional_targets"] = [
            q for q in PLANETS if packet["summary"][q] is None
        ]
        packet["status"] = (
            "conditional_nature_results"
            if packet["conditional_targets"]
            else "same_value_in_all_nature_branches"
        )
    elif fault == "invented_branch":
        packet["scenarios"]["invented"] = packet["scenarios"].pop(first)
    elif fault == "elongation":
        packet["nature_context"]["moon_directed_elongation"] += 1
    elif fault == "mercury_options":
        packet["nature_context"]["mercury_options"] = ["benefic"]
    elif fault == "source":
        packet["source_id"] = "unrelated"
    elif fault == "method":
        packet["method"] = "unverified"
    elif fault == "source_accepted":
        packet["source_witness"]["complete_single_original_accepted"] = True
    elif fault == "alternative_applied":
        packet["alternative_source_witnesses"]["santhanam_26_27_19"][
            "applied_to_native_drik"
        ] = True
    elif fault == "bool_zero":
        packet["matrix"]["Sun"]["Sun"] = False
    elif fault == "missing_matrix":
        packet.pop("matrix")
    elif fault == "other_D1":
        values = {p["id"]: p["longitude"] for p in d1["planets"] if p["id"] in PLANETS}
        values["Mars"] = (values["Mars"] + 17) % 360
        packet.update(aspect_strength(values))
    elif fault == "all_zero":
        packet.update(aspect_strength(dict.fromkeys(PLANETS, 0.0)))
    else:
        raise AssertionError("Unknown registered fault")


@pytest.mark.parametrize("fault", FAULTS)
def test_formal_topic_rejects_full_graph_inconsistency_before_prose(computed, fault):
    strengths = copy.deepcopy(computed["strengths"])
    target = computed["charts"]["D1"]["houses"][0]["lord"]
    mutate(strengths["drik_bala"], computed["charts"]["D1"], target, fault)
    with pytest.raises(JyotishCalculationError):
        jyotish.topic_evidence(
            computed["charts"],
            strengths["sthana_bala"],
            strengths,
            computed["ashtakavarga"],
        )


def test_valid_whole_topic_and_receipt_are_not_mutated(computed):
    before = copy.deepcopy(computed)
    verify_drik_evidence(computed["strengths"]["drik_bala"], computed["charts"]["D1"])
    assert (
        jyotish.topic_evidence(
            computed["charts"],
            computed["strengths"]["sthana_bala"],
            computed["strengths"],
            computed["ashtakavarga"],
        )
        == computed["topic_evidence"]
    )
    assert computed == before


@pytest.mark.parametrize(
    "fault",
    [
        "division",
        "boolean_division",
        "method",
        "duplicate",
        "missing",
        "boolean_operand",
        "nonfinite",
        "outside",
    ],
)
def test_natal_D1_operand_identity_is_not_a_varga_or_invalid_scalar(computed, fault):
    chart = copy.deepcopy(computed["charts"]["D1"])
    if fault == "division":
        chart["division"] = 9
    elif fault == "boolean_division":
        chart["division"] = True
    elif fault == "method":
        chart["method"] = "navamsa"
    elif fault == "duplicate":
        chart["planets"].append(copy.deepcopy(chart["planets"][0]))
    elif fault == "missing":
        chart["planets"].pop(0)
    elif fault == "boolean_operand":
        chart["planets"][0]["longitude"] = False
    elif fault == "nonfinite":
        chart["planets"][0]["longitude"] = math.nan
    else:
        chart["planets"][0]["longitude"] = 360.0
    with pytest.raises(JyotishCalculationError):
        verify_drik_evidence(computed["strengths"]["drik_bala"], chart)


@pytest.mark.parametrize(
    "elongation",
    [
        0.0,
        math.nextafter(180.0, 0),
        180.0,
        math.nextafter(180.0, 360),
        359.99999999999994,
    ],
)
def test_real_ambiguous_phases_and_zero_consensus_remain_computed(elongation):
    values = dict.fromkeys(PLANETS, 0.0)
    values["Moon"] = elongation
    packet = aspect_strength(values)
    d1 = {
        "division": 1,
        "method": "rasi_whole_sign",
        "planets": [dict(id=p, longitude=v) for p, v in values.items()],
    }
    before = copy.deepcopy(packet)
    verify_drik_evidence(packet, d1)
    assert packet == before
    assert packet["nature_context"]["mercury_options"] == ["benefic", "malefic"]
    assert packet["source_witness"]["complete_single_original_accepted"] is False
    if elongation == 0:
        assert packet["summary"] == dict.fromkeys(PLANETS, 0.0)
        assert len(packet["scenarios"]) == 4


@pytest.mark.native_engine_fault
def test_a_corrupted_component_returned_by_calculator_cannot_reach_full_build(
    monkeypatch,
):
    original = jyotish.other_balas

    def altered(raw):
        result = original(raw)
        result["drik_bala"]["matrix"]["Sun"]["Sun"] = False
        return result

    monkeypatch.setattr(jyotish, "other_balas", altered)
    from fatebridge.core.astro.birth import build_astro_birth_info

    with pytest.raises(JyotishCalculationError):
        jyotish.build_india(
            build_astro_birth_info(
                birth_year=2000,
                birth_month=1,
                birth_day=1,
                birth_hour=0,
                birth_timezone="UTC",
                birth_longitude=0.0,
                birth_latitude=0.0,
                preserve_instant=True,
            ),
            divisions=[],
        )


def test_exact_D1_recomputation_preserves_rounded_elongation_near360():
    values = dict.fromkeys(PLANETS, 0.0)
    values["Sun"] = math.nextafter(0.0, 1.0)
    packet = aspect_strength(values)
    assert packet["nature_context"]["moon_directed_elongation"] == 360.0
    assert packet["nature_context"]["moon_options"] == ["malefic"]
    d1 = {
        "division": 1,
        "method": "rasi_whole_sign",
        "planets": [dict(id=p, longitude=v) for p, v in values.items()],
    }
    verify_drik_evidence(packet, d1)
