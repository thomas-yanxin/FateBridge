"""Conflicting source selectors, exact products and faithful daily evidence."""

import csv
import hashlib
import json
from decimal import Decimal, localcontext
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_midnight_anchors as subject
from fatebridge.core.guolao_daily_solar import POLICIES
from fatebridge.validation.guolao_midnight_anchors import audit_midnight_anchors

FIXTURE = Path(__file__).parent / "fixtures/guolao-midnight-anchors-v1"


def test_original_pages_and_selector_readings_keep_frozen_source_identity():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    assert (
        hashlib.sha256(subject.DATA.read_bytes()).hexdigest()
        == reference["data_sha256"]
    )
    for item in reference["artifacts"]:
        blob = (FIXTURE / item["path"]).read_bytes()
        assert len(blob) == item["bytes"]
        assert hashlib.sha256(blob).hexdigest() == item["sha256"]
    assert reference["single_unblinded_collator"]
    assert not reference["independent_expert"]
    with (FIXTURE / "selector-reading.csv").open() as stream:
        for row in csv.DictReader(stream):
            distance = (
                int(row["distance_source_days"])
                if row["distance_source_days"]
                else None
            )
            assert subject.gujin39_cardinal_rate(
                row["cardinal"], distance_days=distance
            ) == F(row["rate_ancient_du"])


@pytest.mark.parametrize(
    "cardinal,distance,rate",
    [
        ("spring", 93, ".999703"),
        ("spring", 94, "1"),
        ("autumn", 88, "1.000505"),
        ("autumn", 89, "1"),
    ],
)
def test_Gujin39_selector_does_not_substitute_the_Gujin43_previous_table_row(
    cardinal, distance, rate
):
    assert subject.gujin39_cardinal_rate(cardinal, distance_days=distance) == F(rate)


def test_three_spring_anchors_differ_and_no_best_lane_is_selected():
    report = audit_midnight_anchors()
    lanes = report["all_rate_policies"]
    expected = ["94.96098690875", "94.9601", "94.9603943607625"]
    for policy, value in zip(subject.RATE_POLICIES, expected, strict=True):
        rows = lanes[policy]["cardinal_anchor_records"]
        assert F(rows[1]["recomputed_midnight_du_exact"]) == F(value)
        assert rows[1]["legacy_normalized_printed_rate_du"] == "0.999103"
        assert rows[1]["spring_source_lexeme"] == "初度九九九十〇三"
        assert rows[1]["legacy_spring_normalization_not_adjudicated"]
        assert not lanes[policy]["rate_policy_automatically_selected_as_best"]
    assert not report["best_policy_selected_by_match_or_closure"]
    assert not report["four_axis_perfect_scores_established"]


def test_generated_cardinal_products_keep_all_precision_and_printed_residuals():
    model = subject.load_recomputed_midnight(
        subject.PROFILE, rate_policy=subject.RATE_POLICIES[2]
    )
    rows = model.audit()["cardinal_anchor_records"]
    expected = [
        "4.554333579076",
        "94.9603943607625",
        "186.592973250311",
        "278.1576912279855",
        "369.543160624958",
    ]
    assert [F(q["recomputed_midnight_du_exact"]) for q in rows] == [
        F(v) for v in expected
    ]
    assert [q["Gujin43_declared_generator_index"]["index"] for q in rows] == [
        0,
        93,
        0,
        88,
        0,
    ]
    assert all(F(q["recomputed_minus_printed_midnight_du_exact"]) != 0 for q in rows)
    assert all(not q["source_cells_emended"] for q in rows)
    assert all(q["readding_product_recovers_printed_event_by_identity"] for q in rows)
    # The unwrapped next-winter value must remain past one source circle.
    assert F(rows[-1]["recomputed_midnight_du_exact"]) > model.generated.literal.circle


def test_spring_product_against_independent_decimal_cubic_evaluation():
    # This oracle directly evaluates the source cubic, not the domain's
    # finite-difference recurrence or its Fraction multiplication.
    with localcontext() as context:
        context.prec = 60

        def polynomial(n):
            return n * (Decimal(4870600) - n * (Decimal(22100) + 27 * n)) / 100000000

        rate = 1 - (polynomial(Decimal(94)) - polynomial(Decimal(93)))
        expected = Decimal("95.94885") - Decimal(".98875") * rate
    assert rate == Decimal(".99970229")
    assert expected == Decimal("94.9603943607625")
    model = subject.load_recomputed_midnight(
        subject.PROFILE, rate_policy=subject.RATE_POLICIES[2]
    )
    actual = model.audit()["cardinal_anchor_records"][1]["recomputed_midnight_du_exact"]
    assert F(actual) == F(expected)


@pytest.mark.parametrize("rate_policy", subject.RATE_POLICIES)
@pytest.mark.parametrize("policy", POLICIES)
def test_complete_daily_grid_uses_selected_anchors_and_retains_boundary_semantics(
    rate_policy, policy
):
    model = subject.load_recomputed_midnight(subject.PROFILE, rate_policy=rate_policy)
    audit = model.audit()
    for n in range(366):
        row = model.day(n, policy=policy)
        assert row["profile_id"] == subject.PROFILE
        assert row["anchor_rate_policy"] == rate_policy
        assert row["cardinal_anchors_recomputed_from_products"]
        assert not row["retained_Gujin43_span_section_midnight_anchors"]
        assert not row["anchor_products_are_printed_values"]
        assert row["folded_sunrise_argument"] is None
        assert not row["modern_calendar_date_assigned"]
        assert not row["used_in_native_birth_chart"]
        assert not row["physical_solar_position_validated"]
        if n < 365:
            assert (
                F(row["noon_unwrapped_from_ji_start_du_exact"])
                - F(row["midnight_unwrapped_from_ji_start_du_exact"])
                == F(row["following_corrected_daily_motion_du_exact"]) / 2
            )
        else:
            assert row["noon_unwrapped_from_ji_start_du_exact"] is None
            assert row["following_corrected_daily_motion_du_exact"] is None
    for index, offset in enumerate(model.generated.trajectory.offsets):
        row = model.day(offset, policy=policy)
        assert row["midnight_unwrapped_from_ji_start_du_exact"] == (
            audit["cardinal_anchor_records"][index]["recomputed_midnight_du_exact"]
        )
        boundary = row["cardinal_boundary_left_limit"]
        if boundary is not None:
            assert "printed_right_anchor_du_exact" not in boundary
            assert (
                boundary["recomputed_right_anchor_du_exact"]
                == row["midnight_unwrapped_from_ji_start_du_exact"]
            )
            if policy == POLICIES[0]:
                assert boundary["left_minus_right_du_exact"] == "0"
            else:
                assert F(boundary["left_minus_right_du_exact"]) != 0
    for segment in audit["segments"]:
        assert "printed_midnight_span_du_exact" not in segment
        assert "recomputed_midnight_span_du_exact" in segment
        assert "literal_rate_sum_du_exact" not in segment
        assert "generated_rate_sum_du_exact" in segment


@pytest.mark.parametrize("distance", [None, True, 93.0, "93", F(93)])
def test_unknown_or_noninteger_source_distance_is_not_coerced(distance):
    with pytest.raises(TypeError):
        subject.gujin39_cardinal_rate("spring", distance_days=distance)


@pytest.mark.parametrize(
    "cardinal,distance",
    [
        ("spring", 92),
        ("spring", 95),
        ("autumn", 87),
        ("autumn", 90),
        ("winter", 88),
        ("summer", 94),
        ("unknown", None),
    ],
)
def test_source_selector_has_no_nearest_rate_fallback(cardinal, distance):
    with pytest.raises(ValueError):
        subject.gujin39_cardinal_rate(cardinal, distance_days=distance)


@pytest.mark.parametrize("value", [True, 1.0, "1", F(1)])
def test_daily_source_indices_do_not_accept_modern_or_coerced_inputs(value):
    model = subject.load_recomputed_midnight(
        subject.PROFILE, rate_policy=subject.RATE_POLICIES[0]
    )
    with pytest.raises(TypeError):
        model.day(value, policy=POLICIES[0])


def test_no_implicit_profile_rate_selector_or_daily_difference_policy():
    with pytest.raises(ValueError):
        subject.load_recomputed_midnight("best", rate_policy=subject.RATE_POLICIES[0])
    with pytest.raises(ValueError):
        subject.load_recomputed_midnight(subject.PROFILE, rate_policy="best")
    with pytest.raises(TypeError):
        subject.load_recomputed_midnight(subject.PROFILE)
    with pytest.raises(TypeError):
        subject.load_recomputed_midnight(
            subject.PROFILE, rate_policy=subject.RATE_POLICIES[0]
        ).day(0)


@pytest.mark.parametrize(
    "mutation",
    ["source_sha", "generator_sha", "bool_index", "index_shift", "float_rate"],
)
def test_changed_source_parameters_reject_instead_of_rebaselining(
    monkeypatch, tmp_path, mutation
):
    raw = json.loads(subject.DATA.read_bytes())
    if mutation == "source_sha":
        raw["source_daily_data_sha256"] = "0" * 64
    elif mutation == "generator_sha":
        raw["generator_parameter_sha256"] = "0" * 64
    elif mutation == "bool_index":
        raw["gujin43_explicit_generator_indices"][0]["index"] = False
    elif mutation == "index_shift":
        raw["gujin43_explicit_generator_indices"][1]["index"] = 92
    else:
        raw["gujin39_literal_selector_rates"]["spring"]["94"] = 1.0
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(subject, "DATA", path)
    with pytest.raises(ValueError):
        subject.load_recomputed_midnight(
            subject.PROFILE, rate_policy=subject.RATE_POLICIES[1]
        )
