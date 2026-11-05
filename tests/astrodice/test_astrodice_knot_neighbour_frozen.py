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
    DecimalApparentReduction,
)
from scripts.astrodice.astrodice_apparent_source_reference import (
    Reader as DecimalReader,
)
from scripts.astrodice.astrodice_apparent_source_reference import sample
from scripts.astrodice.astrodice_clock_interval import I, Reader, apparent

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/astrodice/reference_sets/fixture-knot-neighbour-v1"
SOURCE = ROOT / "tests/data/astrodice/reference_sets/fixture-de441-records-v1"
PASS = "declared_source_model_lines_satisfied"


def read(name):
    return json.loads((FIXTURE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            "scripts.astrodice.gen_astrodice_knot_neighbours",
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


def test_an_undeclared_reduction_version_cannot_be_serialized_as_accepted():
    with pytest.raises(ValidationError):
        DecimalApparentReduction.model_validate(
            {"method_id": "native_geometric_decimal_apparent_reduction_v999"}
        )
