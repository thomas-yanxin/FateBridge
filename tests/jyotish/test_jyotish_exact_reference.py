"""Frozen independent source allocation and exact final-scalar arithmetic."""

import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.astrology_tables import SIGNS
from fatebridge.core.jyotish.jyotish_balas import resolve_directional_strength
from fatebridge.core.jyotish.jyotish_charts import GRAHAS, divisional_chart
from fatebridge.core.jyotish.jyotish_kala import nathonnatha
from fatebridge.core.jyotish.jyotish_mean import mean_longitudes
from fatebridge.core.jyotish.jyotish_sthana import calculate_sthana, resolve_sthana
from fatebridge.core.jyotish.jyotish_vargas import (
    varga_coordinates,
    varga_longitude,
    varga_sign,
)
from fatebridge.core.jyotish.jyotish_war import war_bala_result

FIXTURE = Path(__file__).parents[1] / "data/jyotish_varga_flint_v1"
RAW = gzip.decompress((FIXTURE / "source.json.gz").read_bytes())
REFERENCE = json.loads(RAW)
DIVISIONS = (1, 2, 3, 7, 9, 10, 12, 30)
COMPLEMENT_FIXTURE = Path(__file__).parents[1] / "data/jyotish_complement_flint_v1"
COMPLEMENT_RAW = gzip.decompress((COMPLEMENT_FIXTURE / "source.json.gz").read_bytes())
COMPLEMENT_REFERENCE = json.loads(COMPLEMENT_RAW)
TOTAL_REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/jyotish_sthana_total_flint_v1.json").read_text()
)


def test_frozen_reference_integrity_and_complete_declared_scope() -> None:
    assert (
        hashlib.sha256(RAW).hexdigest()
        == (FIXTURE / "source.json.sha256").read_text().strip()
    )
    provenance = REFERENCE["provenance"]
    assert provenance["python_flint"] == "0.9.0"
    assert provenance["flint"] == "3.6.0"
    assert provenance["reference_imports_project"] is False
    assert provenance["uses_fraction_or_fmpq_float"] is False
    assert (
        provenance["source_table_sha256"]
        == hashlib.sha256((FIXTURE / "source-tables.json").read_bytes()).hexdigest()
    )
    assert (
        provenance["criteria_sha256"]
        == hashlib.sha256((FIXTURE / "criteria.json").read_bytes()).hexdigest()
    )
    for name, count in (("development", 13498), ("validation", 1280)):
        data = REFERENCE["datasets"][name]
        assert data["divisions"] == list(DIVISIONS)
        assert len(data["cases"]) == count


@pytest.mark.parametrize("dataset", ["development", "validation"])
@pytest.mark.parametrize("division", DIVISIONS)
def test_every_frozen_component_matches_independent_reference(
    dataset: str, division
) -> None:
    for row in REFERENCE["datasets"][dataset]["cases"]:
        encoded = row["value"]
        value = (
            float.fromhex(encoded["hex"])
            if encoded["kind"] == "float"
            else Fraction(int(encoded["numerator"]), int(encoded["denominator"]))
        )
        expected = row["expected"][str(division)]
        sign, degree = varga_coordinates(value, division)
        assert sign == expected["sign"], row["id"]
        assert varga_sign(value, division) == expected["sign"], row["id"]
        assert (None if degree is None else degree.hex()) == expected[
            "degree_hex"
        ], row["id"]
        if division == 30:
            with pytest.raises(ValueError, match="D30"):
                varga_longitude(value, division)
        else:
            assert (
                varga_longitude(value, division).hex() == expected["longitude_hex"]
            ), row["id"]


@pytest.mark.parametrize("function", [varga_coordinates, varga_longitude, varga_sign])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_inputs_remain_explicit_errors(function, value) -> None:
    for division in DIVISIONS:
        with pytest.raises(ValueError, match="有限"):
            function(value, division)


@pytest.mark.parametrize("function", [varga_coordinates, varga_longitude, varga_sign])
@pytest.mark.parametrize("division", [-1, 0, 5, 108])
def test_unsupported_divisions_never_fall_back(function, division) -> None:
    with pytest.raises(ValueError, match="D1"):
        function(23.0, division)


@pytest.mark.parametrize("division", DIVISIONS)
def test_real_chart_consumer_preserves_original_counterexample(division) -> None:
    row = next(
        row
        for row in REFERENCE["datasets"]["development"]["cases"]
        if row["id"] == "development-23"
    )
    value = float.fromhex(row["value"]["hex"])
    expected = row["expected"][str(division)]
    chart = divisional_chart(
        {"ascendant": value, "longitudes": dict.fromkeys(GRAHAS, value)}, division
    )
    for point in (chart["ascendant"], *chart["planets"]):
        assert point["sign"] == SIGNS[expected["sign"]]
        assert (
            None if point["longitude"] is None else point["longitude"].hex()
        ) == expected["longitude_hex"]
    if division == 30:
        assert all(
            point["degree_in_sign"] is None
            for point in (chart["ascendant"], *chart["planets"])
        )
    else:
        pass


@pytest.mark.parametrize(
    "case_id",
    [
        "development-0",
        "development-2",
        "development-6",
        "development-14",
        "development-23",
        "development-10000",
        "development-10003",
    ],
)
def test_chart_points_keep_independently_rendered_frozen_degree(case_id: str) -> None:
    row = next(
        row
        for row in REFERENCE["datasets"]["development"]["cases"]
        if row["id"] == case_id
    )
    encoded = row["value"]
    value = (
        float.fromhex(encoded["hex"])
        if encoded["kind"] == "float"
        else Fraction(int(encoded["numerator"]), int(encoded["denominator"]))
    )
    for division in DIVISIONS:
        expected = row["expected"][str(division)]
        chart = divisional_chart(
            {"ascendant": value, "longitudes": dict.fromkeys(GRAHAS, value)}, division
        )
        for point in (chart["ascendant"], *chart["planets"]):
            assert point["sign"] == SIGNS[expected["sign"]]
            assert (
                None if point["longitude"] is None else point["longitude"].hex()
            ) == expected["longitude_hex"]
            assert (
                None
                if point["degree_in_sign"] is None
                else point["degree_in_sign"].hex()
            ) == expected["degree_hex"]


@pytest.mark.parametrize(
    "case", TOTAL_REFERENCE["cases"], ids=lambda row: str(row["index"])
)
def test_historical_reported_components_keep_frozen_flint_total_target(case) -> None:
    # This fixture froze the earlier sum-of-delivered-leaves contract. Keep its
    # original target without forcing the new source-formula totals to equal it.
    components = (
        "uchcha_bala",
        "saptavargaja_bala",
        "ojayugma_bala",
        "kendradi_bala",
        "drekkana_bala",
    )
    for profile in ("santhanam_27", "raman_30"):
        for drekkana in ("santhanam_27_6", "raman_36"):
            result = calculate_sthana(case["raw"], profile, drekkana)
            for row in case["expected"]:
                if row["profile"] != profile or row["drekkana"] != drekkana:
                    continue
                else:
                    pass
                summary = result["summary"][row["planet"]]
                total = sum(
                    (Fraction(summary[name]) for name in components), Fraction()
                )
                expected = row["expected_hex"]
                assert float(total).hex() == expected["total_virupa"]
                assert float(total / 60).hex() == expected["total_rupa"]


def test_frozen_complement_reference_integrity_and_complete_scope() -> None:
    assert (
        hashlib.sha256(COMPLEMENT_RAW).hexdigest()
        == (COMPLEMENT_FIXTURE / "source.json.sha256").read_text().strip()
    )
    provenance = COMPLEMENT_REFERENCE["provenance"]
    assert provenance["python_flint"] == "0.9.0"
    assert provenance["flint"] == "3.6.0"
    assert provenance["imports_product"] is False
    assert provenance["uses_fraction_or_fmpq_float_for_expected"] is False
    criteria_raw = (COMPLEMENT_FIXTURE / "criteria.json").read_bytes()
    assert hashlib.sha256(criteria_raw).hexdigest() == provenance["criteria_sha256"]
    criteria = json.loads(criteria_raw)
    for name, expected in criteria["source_sha256"].items():
        assert hashlib.sha256((COMPLEMENT_FIXTURE / name).read_bytes()).hexdigest() == (
            expected
        )
    for family, development_count in (("mean", 12067), ("natha", 10716)):
        for dataset, count in (
            ("development", development_count),
            ("validation", 2000),
        ):
            data = COMPLEMENT_REFERENCE["families"][family][dataset]
            assert data["family"] == family and data["dataset"] == dataset
            assert len(data["cases"]) == count
            assert count == criteria["inputs"][family + "_" + dataset]["cases"]


@pytest.mark.parametrize("family", ["mean", "natha"])
@pytest.mark.parametrize("dataset", ["development", "validation"])
def test_all_exact_complements_match_independent_reference(
    family: str, dataset: str
) -> None:
    for row in COMPLEMENT_REFERENCE["families"][family][dataset]["cases"]:
        actual = (
            mean_longitudes(float.fromhex(row["jd_hex"]))
            if family == "mean"
            else nathonnatha(
                float.fromhex(row["meridian_hex"]),
                float.fromhex(row["sun_ra_hex"]),
            )
        )
        assert {name: value.hex() for name, value in actual.items()} == row[
            "expected_hex"
        ], row["id"]


def test_temporal_source_values_remain_unrounded_through_kala_and_war() -> None:
    from fatebridge.core.jyotish.jyotish_kala import temporal_balas

    directory = Path(__file__).parents[1] / "data/jyotish_temporal_chain_flint_v1"
    raw = gzip.decompress((directory / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (directory / "reference.json.sha256").read_text().strip()
    )
    reference = json.loads(raw)
    assert len(reference["cases"]) == reference["original_cases"] == 36
    assert sum(len(row["expected"]) for row in reference["cases"]) == 3782
    for row in reference["cases"]:
        actual = temporal_balas(
            row["raw"],
            row["packet"],
            row["longitude"],
            sthana=row["sthana"],
            dig=row["dig"],
        )
        for expected in row["expected"]:
            value = actual
            for key in expected["path"]:
                value = value[key]
            assert (None if value is None else value.hex()) == expected["hex"], (
                row["id"],
                expected["path"],
            )
        for branch in actual["kala_bala"]["components"]["yuddha_bala"][
            "evidence"
        ].values():
            for basis in branch["prewar_basis"].values():
                exact_inputs = basis["exact_inputs_virupa"]
                assert {
                    key: None if value is None else float(Fraction(value))
                    for key, value in exact_inputs.items()
                } == basis["inputs"]
                values = [
                    None if value is None else Fraction(value)
                    for value in exact_inputs.values()
                ]
                assert basis["total_virupa"] == (
                    None if None in values else float(sum(values, Fraction()))
                )


POSITIONAL_FIXTURE = (
    Path(__file__).parents[1] / "data/jyotish_positional_chain_flint_v1"
)
POSITIONAL_RAW = gzip.decompress((POSITIONAL_FIXTURE / "source.json.gz").read_bytes())
POSITIONAL_REFERENCE = json.loads(POSITIONAL_RAW)
POSITIONAL_COHORT = json.loads(
    (POSITIONAL_FIXTURE / "proposed-cohort.json").read_text()
)
POSITIONAL_PRIMITIVES = json.loads(
    (POSITIONAL_FIXTURE / "source-primitives.json").read_text()
)
POSITIONAL_CASES = {row["id"]: row for row in POSITIONAL_COHORT["source_raw_cases"]}


def test_positional_source_reference_keeps_original_blind_identity() -> None:
    assert hashlib.sha256(POSITIONAL_RAW).hexdigest() == (
        "0bd4c1e24ea5b5a9c5413183faf878d19b69db5bed7fd7739df78df4fb9f3583"
    )
    provenance = POSITIONAL_REFERENCE["provenance"]
    assert provenance["imports_product"] is False
    assert provenance["python_flint"] == "0.9.0"
    assert provenance["flint"] == "3.6.0"
    for name, field in (
        ("proposed-cohort.json", "inputs_sha256"),
        ("source-primitives.json", "source_primitives_sha256"),
    ):
        assert hashlib.sha256((POSITIONAL_FIXTURE / name).read_bytes()).hexdigest() == (
            provenance[field]
        )
    assert len(POSITIONAL_REFERENCE["profile_records"]) == 16
    assert len(POSITIONAL_REFERENCE["direct_delivered_operand_controls"]) == 2


@pytest.mark.parametrize("expected", POSITIONAL_REFERENCE["profile_records"])
def test_positional_source_values_reach_totals_and_war_without_leaf_projection(
    expected,
) -> None:
    raw = POSITIONAL_CASES[expected["id"]]
    selection = expected["selection"]
    sthana = resolve_sthana(
        raw["longitudes"],
        raw["ascendant"],
        selection["saptavargaja"],
        selection["drekkana"],
    )
    dig = resolve_directional_strength(
        raw["longitudes"], raw["ascendant"], raw["midheaven"]
    )
    planets = POSITIONAL_PRIMITIVES["planet_order"]
    components = {
        name: {"summary": dict.fromkeys(planets, 0.0)}
        for name in POSITIONAL_PRIMITIVES["through_hora"]
    }
    branch = "supplied_zero_temporal_components"
    war, exact = war_bala_result(
        raw["longitudes"],
        components,
        {branch: dict.fromkeys(planets, Fraction())},
        sthana,
        dig,
    )
    for planet in planets:
        for component, target in expected["source_components"][planet].items():
            if component == "sapta_terms":
                continue
            else:
                pass
            assert sthana.record["summary"][planet][component].hex() == (
                target["nearest_hex"]
            )
        assert dig.record["summary"][planet].hex() == (
            expected["dig"][planet]["nearest_hex"]
        )
        assert str(sthana.totals[planet]) == (
            expected["source_sthana"][planet]["total_virupa"]["exact"]
        )
        assert str(dig.values[planet]) == expected["dig"][planet]["exact"]
        for field in ("total_virupa", "total_rupa"):
            assert sthana.record["summary"][planet][field].hex() == (
                expected["source_sthana"][planet][field]["nearest_hex"]
            )
        total_hex = expected["source_sthana"][planet]["total_virupa"]["nearest_hex"]
        for field, profile in (
            ("profile_comparison", selection["saptavargaja"]),
            ("drekkana_profile_comparison", selection["drekkana"]),
        ):
            assert sthana.record[field][profile][planet]["total_virupa"].hex() == (
                total_hex
            )
        target = expected["war"]["source_full_unrounded"]["values"][planet]
        assert str(exact[branch][planet]) == target["exact"]
        assert war["scenarios"][branch][planet].hex() == target["nearest_hex"]
    basis = war["evidence"][branch]["prewar_basis"]
    for planet in POSITIONAL_PRIMITIVES["war_planets"]:
        assert basis[planet]["total_virupa"].hex() == (
            expected["prewar"]["source_full_unrounded"][planet]["nearest_hex"]
        )
    expected_pairs = expected["war"]["source_full_unrounded"]["pairs"]
    pairs = war["evidence"][branch]["pairs"]
    assert len(pairs) == len(expected_pairs)
    for pair, target in zip(pairs, expected_pairs):
        assert pair["planets"] == target["planets"]
        assert pair["winner"] == target["winner"]
        assert pair["amount_virupa"].hex() == target["amount"]["nearest_hex"]


@pytest.mark.parametrize(
    "control", POSITIONAL_COHORT["direct_delivered_operand_controls"]
)
def test_direct_positional_operands_keep_their_values_and_missingness(control) -> None:
    raw = POSITIONAL_CASES[control["longitudes_case"]]
    expected = next(
        row
        for row in POSITIONAL_REFERENCE["direct_delivered_operand_controls"]
        if row["id"] == control["id"]
    )
    planets = POSITIONAL_PRIMITIVES["planet_order"]
    sthana = {
        "profile": {"id": "synthetic_direct_delivered_operands"},
        "summary": {
            p: {
                "total_virupa": (
                    control["sthana_Mercury"]
                    if p == "Mercury"
                    else control["sthana_total_all"]
                )
            }
            for p in planets
        },
    }
    dig = {
        "source_id": "synthetic_direct_delivered_operands",
        "summary": {
            p: control["dig_Mercury"] if p == "Mercury" else control["dig_all"]
            for p in planets
        },
    }
    components = {
        name: {"summary": dict.fromkeys(planets, 0.0)}
        for name in POSITIONAL_PRIMITIVES["through_hora"]
    }
    branch = "supplied_zero_temporal_components"
    war, exact = war_bala_result(
        raw["longitudes"],
        components,
        {branch: dict.fromkeys(planets, Fraction())},
        sthana,
        dig,
    )
    for planet in planets:
        target = expected["war"]["values"][planet]
        value = war["scenarios"][branch][planet]
        assert (None if value is None else value.hex()) == (
            None if target is None else target["nearest_hex"]
        )
        value = exact[branch][planet]
        assert (None if value is None else str(value)) == (
            None if target is None else target["exact"]
        )
    pairs, expected_pairs = war["evidence"][branch]["pairs"], expected["war"]["pairs"]
    assert len(pairs) == len(expected_pairs)
    for pair, target in zip(pairs, expected_pairs):
        amount = pair["amount_virupa"]
        assert pair["planets"] == target["planets"]
        assert pair["winner"] == target["winner"]
        assert (None if amount is None else amount.hex()) == (
            None if target["amount"] is None else target["amount"]["nearest_hex"]
        )
