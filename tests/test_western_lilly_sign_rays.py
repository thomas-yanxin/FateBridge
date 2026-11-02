"""Pre-edit manual source cells; synthetic angles do not prove prediction."""

import hashlib
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astrology_horary import (
    _degree_aspect_candidate,
    build_horary_payload,
)
from fatebridge.core.lilly_rays import (
    describe_sign_relationship,
    directed_sign_relationship,
)
from fatebridge.core.output_western import LillyDirectedSignRelationship
from tests.test_western_event_angle import synthetic_subject

PATH = Path(__file__).parent / "fixtures/western-lilly-sign-rays-1647.json"
REFERENCE = json.loads(PATH.read_text())
SIGNS = [row[0] for row in REFERENCE["manual_rows"]]


def test_reference_is_the_preedit_manual_primary_source_not_production_output():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "57d16dcd8c5d6431f169d6ca44dab761416c3cf164e133f514e2c2936afc1b3a"
    )
    assert REFERENCE["production_imports"] is False
    assert REFERENCE["independent_expert_reviewed"] is False
    assert REFERENCE["counts"] == {
        "ray": 84,
        "co_present": 12,
        "listed_inconjunct": 32,
        "not_in_either_table": 16,
    }


@pytest.mark.parametrize(
    "row", REFERENCE["cases"], ids=lambda r: r["caster_sign"] + "-" + r["receiver_sign"]
)
def test_every_ordered_printed_cell_and_every_omission(row):
    a, b = SIGNS.index(row["caster_sign"]), SIGNS.index(row["receiver_sign"])
    actual = directed_sign_relationship(
        "Mars", a * 30 + 7.0, "Venus", b * 30 + 19.0, zodiac_type="Tropic"
    )
    assert actual["caster_sign"] == row["caster_sign"]
    assert actual["receiver_sign"] == row["receiver_sign"]
    assert actual["sign_ray"] == row["ray"]
    assert actual["ray_direction"] == row["direction"]
    assert actual["relation_status"] == row["relation_status"]
    assert actual["listed_inconjunct"] == row["listed_inconjunct"]
    assert actual["selected_degree_aspect_agrees"] is None
    assert (
        actual["quantitative_bonus_added"]
        is actual["full_original_text_acceptance"]
        is False
    )
    LillyDirectedSignRelationship.model_validate(actual)
    text = describe_sign_relationship(actual, "火星", "金星")
    assert "火星向金星" in text and "不加权" in text and "无主星度数相位候选" in text
    if row["direction"]:
        assert ("右" if row["direction"] == "dexter" else "左") in text
    if row["relation_status"] == "not_in_either_table":
        assert "不补推正负关系" in text


def decimal_sign(value):
    with localcontext() as context:
        context.prec = 1200
        x = Decimal.from_float(value) % Decimal(360)
        if x < 0:
            x += 360
        return SIGNS[int(x // Decimal(30))]


@pytest.mark.parametrize("boundary", list(range(-360, 721, 30)))
def test_exact_sign_partition_matches_independent_decimal_at_adjacent_doubles(boundary):
    for value in [
        math.nextafter(float(boundary), -math.inf),
        float(boundary),
        math.nextafter(float(boundary), math.inf),
    ]:
        expected = decimal_sign(value)
        assert (
            directed_sign_relationship("A", value, "B", 5.0)["caster_sign"] == expected
        )
        assert (
            directed_sign_relationship("A", 5.0, "B", value)["receiver_sign"]
            == expected
        )


def test_fraction_sign_partition_keeps_sub_float_negative_and_boundary_sides():
    delta = Fraction(1, 10**400)
    assert directed_sign_relationship("A", -delta, "B", 0.0)["caster_sign"] == "Pisces"
    assert (
        directed_sign_relationship("A", 30 - delta, "B", 30 + delta)["caster_sign"]
        == "Aries"
    )
    assert (
        directed_sign_relationship("A", 30 - delta, "B", 30 + delta)["receiver_sign"]
        == "Taurus"
    )


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_angle_is_not_classified(value):
    with pytest.raises(ValueError):
        directed_sign_relationship("A", value, "B", 0.0)
    with pytest.raises(ValueError):
        directed_sign_relationship("A", 0.0, "B", value)


@pytest.mark.parametrize(
    "a,b,degree,status,agreement",
    [
        (29.0, 90.0, "sextile", "ray", False),
        (0.0, 89.0, "square", "ray", False),
        (29.0, 30.0, "conjunction", "listed_inconjunct", False),
        (0.0, 179.0, "opposition", "not_in_either_table", None),
        (0.0, 60.0, "sextile", "ray", True),
        (0.0, 20.0, None, "co_present", None),
        (0.0, 30.0, None, "listed_inconjunct", None),
        (0.0, 43.0, None, "listed_inconjunct", None),
    ],
)
def test_actual_orb_candidate_and_sign_table_are_not_substituted(
    a, b, degree, status, agreement
):
    candidate = _degree_aspect_candidate(
        {"planet": "Mars", "longitude": a}, {"planet": "Venus", "longitude": b}
    )
    actual_degree = candidate["aspect"] if candidate else None
    assert actual_degree == degree
    receipt = directed_sign_relationship(
        "Mars",
        a,
        "Venus",
        b,
        selected_degree_aspect=actual_degree,
        zodiac_type="Tropic",
    )
    assert receipt["relation_status"] == status
    assert receipt["selected_degree_aspect_agrees"] is agreement
    text = describe_sign_relationship(receipt, "火星", "金星")
    assert ("不一致，两者分别保留" in text) is (agreement is False)
    assert ("候选同类" in text) is (agreement is True)
    assert ("两表不足以核定" in text) is (degree is not None and agreement is None)


@pytest.mark.parametrize(
    "zodiac,scope",
    [
        ("Tropic", "tropical_selected_edition"),
        ("Tropical", "tropical_selected_edition"),
        ("Sidereal", "sidereal_extension_not_original_edition_acceptance"),
        (None, "coordinate_system_not_qualified"),
    ],
)
def test_coordinate_qualification_is_not_lost(zodiac, scope):
    receipt = directed_sign_relationship("A", 0.0, "B", 300.0, zodiac_type=zodiac)
    assert receipt["coordinate_scope"] == scope
    text = describe_sign_relationship(receipt, "A", "B")
    assert ("未获此版本原典接受认证" in text) is (zodiac not in {"Tropic", "Tropical"})


def test_same_ruler_and_unresolved_ascendant_do_not_create_independent_actors():
    subject = synthetic_subject(resolved=True)
    actual = build_horary_payload(subject, category="general")
    receipt = actual["significators"]["directed_sign_relationship"]
    assert receipt["distinct_bodies"] is False
    assert "不构成两个独立行为星" in actual["reasoning"]
    assert actual["perfection"]["perfects"] is None and actual["verdict"] == "uncertain"
    unresolved = build_horary_payload(synthetic_subject(), category="general")
    assert unresolved["significators"]["directed_sign_relationship"] is None
    assert (
        unresolved["backend_convention"]["significators"]["directed_sign_relationship"]
        is not None
    )
    assert "按Lilly1647第108" not in unresolved["reasoning"]


@pytest.mark.parametrize(
    "field", ["quantitative_bonus_added", "full_original_text_acceptance"]
)
def test_contract_cannot_upgrade_source_witness_to_strength_or_full_acceptance(field):
    with pytest.raises(ValidationError):
        LillyDirectedSignRelationship.model_validate({field: True})
