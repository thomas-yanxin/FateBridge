"""Frozen-input integrity and anti-score-laundering checks for the experiment."""

import copy
import json
from pathlib import Path

import pytest

from scripts.astrodice_swe_coefficients import PackedFile, crc32_msb, evaluate
from scripts.verify_astrodice_compressed_tail_grading import verify_rows
from scripts.verify_astrodice_swe_coefficients import reflected_crc

RUN = Path("docs/validation/astrodice-compressed-tail-run-2026-10-28")


def test_crc_matches_independent_known_bzip2_vector():
    assert crc32_msb(b"123456789") == reflected_crc(b"123456789") == 0xFC891918


def test_missing_coefficient_has_known_polynomial_and_derivative():
    segment = {
        "ncoef": 4,
        "flags": 2,
        "last_significant_index": 3,
        "segment_start": 0,
        "span": 2,
        "rotated_coefficients": [[4, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    }
    # x=1/2, T3(x)=-1; T3'(x)=0. The constant is c0/2.
    assert evaluate(segment, 1.5, "rebuilt_original") == [2, 0, 0, 0, 0, 0]
    assert evaluate(segment, 1.5, "index_plus_one") == [1, 0, 0, 0, 0, 0]
    # x=1/4, T3=-11/16 and T3'=-9/4. This tests the rate too.
    assert evaluate(segment, 1.25, "index_plus_one") == [21 / 16, 0, 0, -9 / 4, 0, 0]


@pytest.mark.parametrize("mutation", ["truncate", "crc"])
def test_real_packed_file_corruption_is_rejected(tmp_path, mutation):
    original = Path("ephe/semo_30.se1")
    raw = bytearray(original.read_bytes())
    if mutation == "truncate":
        del raw[-1]
    else:
        first = raw.split(b"\r\n", 3)
        start = sum(len(s) + 2 for s in first[:3])
        raw[start + 12] ^= 1  # file start JD, within the CRC protected header
    path = tmp_path / original.name
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="length|CRC"):
        PackedFile(path)


def inputs():
    protocol = json.loads((RUN / "plan-before-evaluation.json").read_text())
    report = json.loads((RUN / "development-audit-first.json").read_text())
    reference = json.loads((RUN / "development-reference-first.json").read_text())[
        "rows"
    ]
    captures = {
        (i, profile): json.loads(
            (RUN / f"development-{profile}-{i}-first.json").read_text()
        )
        for i in range(5)
        for profile in protocol["source_profiles"]
    }
    return protocol, report, reference, captures


def test_independent_replay_retains_primary_candidate_failure():
    protocol, report, reference, captures = inputs()
    rows = verify_rows(protocol, report, reference, captures)
    assert len(rows) == 60
    assert report["primary_candidate_gate"] == 1
    assert sum(not r["passed"] for r in rows) == 4


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "pass",
        "line",
        "budget",
        "maximum",
        "gate",
        "source",
        "epoch",
        "interval",
    ],
)
def test_independent_replay_rejects_laundering(mutation):
    protocol, report, reference, captures = copy.deepcopy(inputs())
    if mutation == "missing":
        del report["rows"][0]
    elif mutation == "pass":
        next(r for r in report["rows"] if not r["passed"])["passed"] = True
    elif mutation == "line":
        report["fixed_rate_line_arcsec_per_source_day"] = "0.003"
    elif mutation == "budget":
        report["decoder_component_budget_au_and_au_per_source_day"] = 1
    elif mutation == "maximum":
        report["summary"]["index_plus_one"][
            "max_direction_rate_error_arcsec_per_source_day_upper"
        ] = 0
    elif mutation == "gate":
        report["primary_candidate_gate"] = 0
    elif mutation == "source":
        captures[0, "installed_baseline"]["rows"][0]["returned_flags"] = 139121
    elif mutation == "epoch":
        captures[0, "installed_baseline"]["numeric_jd"] += 1
    else:
        report["rows"][0]["metrics"]["direction_rate_error_arcsec_per_source_day"] = [
            "0",
            "1",
        ]
    with pytest.raises(ValueError):
        verify_rows(protocol, report, reference, captures)
