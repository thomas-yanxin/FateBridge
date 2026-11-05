"""Independent rounded geometry, interval bounds and full receipt fidelity."""

import copy
import gzip
import hashlib
import json
import math
import random
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_apparent_positions import geometry
from fatebridge.core.human_design_interval_geometry import (
    METHOD,
    ProjectionRoundingUnresolved,
    _add,
    _Arithmetic,
    _MorePrecision,
    _sub,
)
from fatebridge.core.human_design_solar_projection import nominal_solar_projection
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_all_original21600_and27_predeclared_independent_rounded_values():
    path = ROOT / "tests/fixtures/human-design-portable-projection-reference.json.gz"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "db9332d15b084392afc27e5818c88bb61810b346411dc50f5b25e039a608ac9d"
    )
    reference = json.loads(gzip.decompress(path.read_bytes()))
    assert reference["original_count"] == 21600 and reference["additional_count"] == 27
    assert (
        hashlib.sha256(
            (
                ROOT / "tests/fixtures/human-design-portable-projection-plan.json"
            ).read_bytes()
        ).hexdigest()
        == reference["plan_sha256"]
    )
    for row in reference["rows"]:
        actual = nominal_solar_projection(row["sun"], row["target"])
        for key, expected in row["rounded_hex"].items():
            assert actual[key].hex() == expected, (row["id"], key)
        assert actual["projection_relation"] == row["relation"], row["id"]
        assert actual["arithmetic_method"] == METHOD
        assert (
            actual["arithmetic_rounding_status"]
            == "enclosure_endpoints_round_to_same_binary64"
        )
        assert actual["arithmetic_comparison_resolution_radians"] == 1e-12
        assert actual["physical_accuracy_certified"] is False


def test_primitive_outward_bounds_against_exact_rational_arithmetic():
    rng = random.Random(17290419)
    for bits in (16, 64, 128):
        a = _Arithmetic(bits)
        for _ in range(80):
            x, y = (
                Fraction(rng.randint(-1000, 1000), rng.randint(1, 1000))
                for _ in range(2)
            )
            ix, iy = a.rational(x.numerator, x.denominator), a.rational(
                y.numerator, y.denominator
            )
            cases = [
                (_add(ix, iy), x + y),
                (_sub(ix, iy), x - y),
                (a.multiply(ix, iy), x * y),
                (a.square(ix), x * x),
            ]
            if iy[0] > 0:
                cases.append((a.divide(ix, iy), x / y))
            for interval, exact in cases:
                assert Fraction(interval[0], a.s) <= exact <= Fraction(interval[1], a.s)
            root = a.sqrt(a.square(ix))
            assert Fraction(root[0], a.s) <= abs(x) <= Fraction(root[1], a.s)


def test_all36_independent_equatorial_neighbors_at_the_unchanged_cuts():
    path = ROOT / "tests/fixtures/human-design-portable-limb-reference.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "61fa0b8a6f078b9a325b8bb18df5bbacb2fa1a6725086097d1d1d89bf394840d"
    )
    reference = json.loads(path.read_text())
    assert reference["case_count"] == len(reference["rows"]) == 36
    for row in reference["rows"]:
        value = nominal_solar_projection(row["sun"], row["target"])
        assert value["projection_relation"] == row["relation"], row["id"]
        for key, expected in row["rounded_hex"].items():
            assert value[key].hex() == expected, (row["id"], key)


def test_unresolved_budget_is_explicit_without_silent_platform_fallback():
    path = "fatebridge.core.human_design_interval_geometry._separation"
    with patch(path, side_effect=_MorePrecision) as attempt:
        with pytest.raises(ProjectionRoundingUnresolved):
            nominal_solar_projection([0, 0, 1], [1, 1, 2])
        assert [call.args[2].bits for call in attempt.call_args_list] == [
            128,
            256,
            512,
            1024,
            2048,
            4096,
            8192,
        ]
        value = geometry(
            [
                {"body": "Sun", "native_coordinates": [0, 0, 1, 1]},
                {"body": "Moon", "native_coordinates": [1, 1, 2, 1]},
            ]
        )
    assert value == [
        {
            "body": "Moon",
            "status": "arithmetic_rounding_unresolved",
            "arithmetic_method": METHOD,
            "arithmetic_precision_budget_bits": 8192,
            "physical_accuracy_certified": False,
        }
    ]


def test_portable_projection_does_not_use_platform_transcendentals():
    names = (
        "sin",
        "cos",
        "tan",
        "atan",
        "atan2",
        "asin",
        "acos",
        "sqrt",
        "hypot",
        "fsum",
        "radians",
    )
    with patch.multiple(
        math,
        **{
            name: lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("platform transcendental used")
            )
            for name in names
        },
    ):
        value = nominal_solar_projection(
            [223.65628018018444, -0.00012843784749170037, 0.9911390881585062],
            [326.80917577971803, -2.6431076733589998, 0.002577133498751259],
        )
    assert value["arithmetic_method"] == METHOD
    reference = json.loads(
        gzip.decompress(
            (
                ROOT
                / "tests/fixtures/human-design-portable-projection-reference.json.gz"
            ).read_bytes()
        )
    )
    frozen = next(
        r
        for r in reference["rows"]
        if r["id"] == "unchanged-macos-linux-counterexample"
    )
    assert (
        value["separation_radians"].hex() == frozen["rounded_hex"]["separation_radians"]
    )


@pytest.fixture(scope="module")
def complete():
    value = execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1981,
            birth_month=5,
            birth_day=6,
            birth_hour=16,
            birth_minute=22,
            birth_timezone="Europe/London",
        ),
    )
    assert (
        verify_human_design_reading(value)["status"]
        == "verified_fixed_template_reading"
    )
    return value


def test_complete_portable_context_and_reading_replay_without_native_calls(complete):
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier recalculated native positions"),
    ):
        proof = verify_human_design_reading(complete)
    assert proof["status"] == "verified_fixed_template_reading", proof
    context = complete["apparent_position_context"]
    assert (
        context["arithmetic_method"]
        == context["ruleset"]["arithmetic_method"]
        == METHOD
    )
    assert context["ruleset"]["version"] == "1.1.0"
    assert all(
        r["arithmetic_method"] == METHOD
        for b in context["batches"]
        for r in b["solar_projection"]
        if r["status"] == "supplied_coordinates_evaluated"
    )
    assert (
        "https://dlmf.nist.gov/4.45"
        in complete["interpretation"]["apparent_position_context"]["source_urls"]
    )
    assert complete["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "one_ulp",
        "bits",
        "relation",
        "remove_method",
        "wrong_method",
        "current_contract_downgrade",
    ],
)
def test_rehashed_current_receipt_cannot_change_arithmetic_or_claim_legacy(
    complete, fault
):
    value = copy.deepcopy(complete)
    context = value["apparent_position_context"]
    row = context["batches"][0]["solar_projection"][0]
    if fault == "one_ulp":
        row["separation_radians"] = math.nextafter(row["separation_radians"], math.inf)
    elif fault == "bits":
        row["arithmetic_interval_bits"] *= 2
    elif fault == "relation":
        row["projection_relation"] = "physical_occultation_certified"
    elif fault == "remove_method":
        context.pop("arithmetic_method")
    elif fault == "wrong_method":
        context["arithmetic_method"] = "platform_libm"
    elif fault == "current_contract_downgrade":
        context.pop("arithmetic_method")
        context["ruleset"]["version"] = "1.0.0"
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected", fault
