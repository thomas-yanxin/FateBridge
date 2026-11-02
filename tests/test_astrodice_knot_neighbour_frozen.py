"""Replay the frozen source reference; preserve first failures and blind roles."""

import hashlib
import json
import struct
import subprocess
import sys
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.output_charts import (
    CompletePositionMotion,
    DecimalApparentReduction,
)
from scripts.astrodice_apparent_source_reference import Reader as DecimalReader
from scripts.astrodice_apparent_source_reference import sample
from scripts.astrodice_clock_interval import I, Reader, apparent
from scripts.gen_astrodice_knot_neighbours import check_source
from scripts.historical_source_identity import HistoricalSources

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/astrodice-knot-neighbour-v1"
SOURCE = ROOT / "tests/fixtures/astrodice-de441-records-v1"
PASS = "declared_source_model_lines_satisfied"


def read(name):
    return json.loads((FIXTURE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_inputs_reference_code_and_first_failures_are_intact():
    assert sha(FIXTURE / "manifest.json") == (
        "7ceacff63d5999848d9af5b5a4951cb8bf24c48d56afb6db020f9725c10bac6c"
    )
    for name, expected in read("manifest.json")["files"].items():
        assert sha(FIXTURE / name) == expected
    provenance = read("provenance.json")
    originals = HistoricalSources(ROOT)
    for name, expected in provenance["reference_and_checker_code_sha256"].items():
        assert originals.matches(ROOT / name, expected)
    check_source(SOURCE)
    seals = provenance["seals"]
    assert (
        seals["A-repair-first-seal.json"]["production_files"]
        == seals["B-candidate-first-seal.json"]["production_files"]
    )
    assert seals["A-repair-first-seal.json"]["B_still_unopened"]
    ledger = read("outcome-ledger.json")
    before = ledger["A-native-first"]
    assert [i for i, row in enumerate(before) if row["status"] != PASS] == [
        10,
        11,
        12,
        13,
        26,
        27,
        28,
        29,
    ]
    assert all(row["position"]["status"] == PASS for row in before)
    for old, repaired in zip(before, ledger["A-repair-first"]):
        assert repaired["status"] == PASS
        assert old["position"] == repaired["position"]
        if old["status"] == PASS:
            for frame in ("tropical", "lahiri"):
                assert (
                    old["rate"]["frames"][frame][
                        "actual_delivered_rate_degrees_per_day"
                    ]
                    == repaired["rate"]["frames"][frame][
                        "actual_delivered_rate_degrees_per_day"
                    ]
                )
        else:
            assert old["status"] == "candidate_error"
            assert all(
                v["status"] == "candidate_error"
                and v["message"]
                == "Complete apparent-position motion failed its fixed step-convergence line"
                for v in old["rate"]["frames"].values()
            )
    assert len(ledger["B-native-first"]) == 32
    assert all(row["status"] == PASS for row in ledger["B-native-first"])
    for cohort in ledger.values():
        for row in cohort:
            assert not row["full_goal_complete"]
            assert not row["original_Horizons_results_regraded"]
            assert row["position"]["fixed_line_arcsec"] == 0.02
            assert row["rate"]["fixed_line_arcsec_per_day"] == 0.002


def test_all_64_source_intervals_reproduce_without_candidate_positions_or_rates():
    profile = read("source-solar-profile.json")["radius_mass_pairs"]
    selected = read("selection-first.json")["cohorts"]
    seen = set()
    with localcontext() as context:
        context.prec = 100
        for cohort in ("A", "B"):
            reference = read(cohort + "-reference-first.json")
            assert reference["selection_sha256"] == sha(
                FIXTURE / "selection-first.json"
            )
            assert len(reference["rows"]) == 32
            for case, row in zip(selected[cohort], reference["rows"]):
                assert all(row[k] == v for k, v in case.items())
                epoch = Q(row["native_numeric_argument"])
                assert (
                    row["native_numeric_argument"].hex() == row["native_argument_hex"]
                )
                seen.add((row["body"], row["native_argument_hex"]))
                value, cells = apparent(
                    Reader(SOURCE, row["window_index"]), row["body"], I(epoch), profile
                )
                assert json.loads(json.dumps(cells)) == row["source_cells"]
                assert [a.v.record() for a in value] == row["direction_icrf_intervals"]
                assert [a.d.record() for a in value] == row[
                    "derivative_per_TDB_day_intervals"
                ]
                precise = N(epoch.numerator) / N(epoch.denominator)
                point = sample(
                    DecimalReader(SOURCE, row["window_index"]),
                    row["body"],
                    precise,
                    profile,
                    precision=100,
                )
                assert json.loads(json.dumps(point)) == {
                    **row["independent_point"],
                    "light_time_model": "legacy_two_linearized_delays",
                    "light_time_convergence_certified": False,
                    "Horizons_emission_epoch_mapping_certified": False,
                }
                for kind, key in (("v", "direction_icrf"), ("d", "derivative_per_day")):
                    assert all(
                        getattr(box, kind).contains(N(scalar))
                        for box, scalar in zip(value, point[key])
                    )
                assert row["status"] == "exact_source_interval_qualified"
                assert (
                    row["old_fixed_FD_result"]["status"]
                    == "reference_quality_unresolved"
                )
                assert not row["candidate_accuracy_pass"]
    assert len(seen) == 64


def test_neighbour_selection_is_source_only_and_keeps_the_predeclared_words(tmp_path):
    path = tmp_path / "selection.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.gen_astrodice_knot_neighbours",
            "select",
            "--run",
            str(FIXTURE),
            "--fixture",
            str(SOURCE),
            "--output",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(path.read_text()) == read("selection-first.json")
    plan = read("plan-before-geometry.json")
    assert plan["binary64_neighbours"] == [-32, -8, -2, -1, 1, 2, 8, 32]
    assert plan["position_line_arcsec"] == 0.02
    assert plan["rate_line_arcsec_per_day"] == 0.002
    selection = read("selection-first.json")
    for root in selection["roots"]:
        central = struct.unpack(
            ">Q", struct.pack(">d", float.fromhex(root["rounded_root_hex"]))
        )[0]
        cases = [
            row
            for row in selection["cohorts"][root["cohort"]]
            if row["window_index"] == root["window_index"]
            and row["crossing"] == root["crossing"]
        ]
        assert len(cases) == 8
        for row in cases:
            word = struct.unpack(
                ">Q", struct.pack(">d", row["native_numeric_argument"])
            )[0]
            assert word - central == row["word_offset"]


def test_actual_v2_fallback_policy_survives_the_public_output_contract():
    policy = read("delivered-Mercury-tropical-policy.json")
    assert (
        CompletePositionMotion.model_validate(policy).model_dump(exclude_unset=True)
        == policy
    )
    checks = read("fallback-evidence-field-check.json")
    assert checks["status"] == "all_v2_fields_retained"
    for transport in checks["transports"].values():
        reduction = transport["decimal_reduction"]
        assert (
            reduction["method_id"] == "native_geometric_decimal_apparent_reduction_v2"
        )
        assert reduction["ephemeris_model"] == "jpl"
        assert (
            reduction["center_interpolation_branch"]["status"]
            == "interior_sampled_cell"
        )
        assert transport["convergence_line_arcsec_per_day"] == 0.0002
        assert transport["required_consecutive_levels"] == 3
        assert (
            transport["primary_status"]
            == transport["previous_status"]
            == "not_converged"
        )
        assert not reduction["displayed_native_position_changed"]
        assert not reduction["independent_astronomical_accuracy_certified"]
    first = read("fallback-transport-first-process.json")
    assert (
        first["returncode"] == 1
        and "native_geometric_decimal_apparent_reduction_v1" in first["stderr"]
    )


@pytest.mark.parametrize(
    "method",
    [
        "native_geometric_decimal_apparent_reduction_v1",
        "native_geometric_decimal_apparent_reduction_v2",
    ],
)
def test_both_declared_reduction_contract_versions_remain_readable(method):
    assert (
        DecimalApparentReduction.model_validate({"method_id": method}).method_id
        == method
    )


def test_an_undeclared_reduction_version_cannot_be_serialized_as_accepted():
    with pytest.raises(ValidationError):
        DecimalApparentReduction.model_validate(
            {"method_id": "native_geometric_decimal_apparent_reduction_v999"}
        )
