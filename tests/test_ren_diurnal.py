"""A selected noble table is not an observation of dawn or stellar visibility."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.core.output_chinese import RenDiurnalEvidence
from tests.test_ren_classical_depth import AUDIT as V1

CORPUS = Path(__file__).parent / "fixtures/ren_diurnal_v1"
REFERENCE = json.loads((CORPUS / "reference.json").read_text())


def test_independent_source_and_software_policy_inventory_have_not_changed():
    freeze = json.loads((CORPUS / "freeze.json").read_text())
    assert set(freeze["files"]) == {"reference.json", "source-pages.pdf"}
    for name, checksum in freeze["files"].items():
        assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == checksum
    assert REFERENCE["classical_clause"]["numeric_solar_altitude_threshold"] is None
    assert (
        REFERENCE["software_policy"]["source_kind"]
        == "existing_public_input_contract_not_classical_certification"
    )


@pytest.mark.parametrize("hour", list("子丑寅卯辰巳午未申酉戌亥"))
def test_every_fixed_hour_choice_keeps_the_stellar_observation_unknown(hour):
    result = resolve_diurnal(hour)
    policy = REFERENCE["software_policy"]
    assert result["is_diurnal"] == (hour in policy["day_branches"])
    assert result["explicit_choice"] is None
    assert result["selection_source"] == "hour_branch_convention"
    assert result["stellar_visibility_observed"] is None
    assert result["astronomical_boundary_computed"] is False
    assert result["solar_altitude_threshold_degrees"] is None


@pytest.mark.parametrize("case", REFERENCE["explicit_cases"])
def test_explicit_choice_wins_without_becoming_an_observation(case):
    result = resolve_diurnal(case["hour"], case["selected"])
    assert result["is_diurnal"] is case["selected"]
    assert result["explicit_choice"] is case["selected"]
    assert result["selection_source"] == "explicit_parameter"
    assert result["stellar_visibility_observed"] is None


@pytest.mark.parametrize("selected", [None, False, True])
def test_both_methods_preserve_the_actual_choice_and_same_transmission_branches(
    selected,
):
    case = dict(day="戊辰", hour="申", ground="午", general="子", month="子")
    seed = V1.make_seed(case)
    from fatebridge.core.metaphysics.jinkou import build_jinkou_board

    jk = build_jinkou_board(
        seed,
        {"month_general": {"branch": "子"}},
        di_fen="午",
        is_diurnal_override=selected,
    )
    lr = build_liureng_board(
        seed, month_general_override="子", is_diurnal_override=selected
    )
    expected = resolve_diurnal("申", selected)
    assert jk["overview"]["is_diurnal"] is expected["is_diurnal"]
    assert jk["overview"]["diurnal_evidence"] == expected
    assert lr["meta"]["diurnal_evidence"] == expected
    baseline = build_liureng_board(seed, month_general_override="子")
    assert [
        lr["three_transmissions"][k]["branch"] for k in ("initial", "middle", "final")
    ] == [
        baseline["three_transmissions"][k]["branch"]
        for k in ("initial", "middle", "final")
    ]


@pytest.mark.parametrize("value", [0, 1, "false", "night"])
def test_domain_does_not_treat_truthy_nonboolean_values_as_day(value):
    with pytest.raises(ValueError, match="布尔"):
        resolve_diurnal("卯", value)


@pytest.mark.parametrize(
    "field,value",
    [("stellar_visibility_observed", False), ("solar_altitude_threshold_degrees", -6)],
)
def test_schema_cannot_forge_an_observation_or_numeric_classical_threshold(
    field, value
):
    with pytest.raises(ValidationError):
        RenDiurnalEvidence.model_validate({field: value})
