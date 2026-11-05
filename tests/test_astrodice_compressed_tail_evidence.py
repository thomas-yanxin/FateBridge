"""Frozen-input integrity and anti-score-laundering checks for the experiment."""

from pathlib import Path

import pytest

from scripts.astrodice_swe_coefficients import PackedFile, crc32_msb, evaluate
from scripts.verify_astrodice_swe_coefficients import reflected_crc

RUN = Path("tests/data/astrodice/reference_sets/study-compressed-tail")


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
