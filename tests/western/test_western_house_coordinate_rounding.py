"""Independent Arb targets for the original72 R/C/T supplied arguments.

The native values are recorded BEFORE diagnostic inputs, never expected values.
R/C retain their declared shifted profile; T consumes the original unshifted
profile. This checks supplied mathematical arguments, not whole-book source
authority, actual-body latitude or physical sky accuracy.
"""

import gzip
import hashlib
import math
import struct
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Literal

import pytest
from pydantic import TypeAdapter
from typing_extensions import TypedDict

from fatebridge.core.astro.house_projection_precision import (
    checked_house_plane_position,
)
from fatebridge.core.astro.topocentric_precision import checked_topocentric_position


class _HexInput(TypedDict):
    hex: str


class _Input(TypedDict):
    id: str
    ordinal: int
    house_code: Literal["R", "C", "T"]
    latitude: _HexInput
    armc: _HexInput
    obliquity: _HexInput
    backend_longitude_exact: str


class _InputBundle(TypedDict):
    rows: list[_Input]


class _Interval(TypedDict):
    lower: str
    upper: str


class _Binary64(TypedDict):
    bits: str
    hex: str


class _Profile(TypedDict):
    phase_degrees: _Interval
    phase_rne: _Binary64
    phase_circular_delivery: _Binary64
    position_rne: _Binary64
    half_open_delivery: _Binary64
    house: int


class _Reference(TypedDict):
    id: str
    ordinal: int
    house_code: Literal["R", "C", "T"]
    unshifted_continuous: _Profile
    declared_shifted_policy: _Profile


class _NativeDiagnostic(TypedDict):
    id: str
    role: Literal["diagnostic_input_not_target"]
    position: _Binary64


@dataclass(frozen=True)
class _Case:
    supplied: _Input
    reference: _Reference
    native: _NativeDiagnostic


FIXTURE = Path(__file__).parents[1] / "data/house_coordinate_rounding_arb_v1"
PAYLOAD_HASHES = {
    "inputs.json": "6dccb27c0cc269aaa6952a401e76b76fa6f4d53c4de4ccd526a806bedc4f5e2f",
    "reference.jsonl.gz": "61f8283c98afb0390e7aa17bdcd20a098c6ee7cdc91971b6ccc69aca1472cd76",
    "native-diagnostic-inputs.json": "0ecfa3ae4e900dbccbb52f0ccfe2e8d314cd8ef849b8b057787e1aaa83e08efe",
}


def _load_cases() -> list[_Case]:
    # Validate the owned JSON boundary once; the test consumes typed records.
    payloads = {name: (FIXTURE / name).read_bytes() for name in PAYLOAD_HASHES}
    for name, expected in PAYLOAD_HASHES.items():
        assert hashlib.sha256(payloads[name]).hexdigest() == expected, name
    supplied = TypeAdapter(_InputBundle).validate_json(payloads["inputs.json"])["rows"]
    reference_adapter = TypeAdapter(_Reference)
    references = [
        reference_adapter.validate_json(line)
        for line in gzip.decompress(payloads["reference.jsonl.gz"]).splitlines()
    ]
    natives = TypeAdapter(list[_NativeDiagnostic]).validate_json(
        payloads["native-diagnostic-inputs.json"]
    )
    ids = [row["id"] for row in supplied]
    assert len(ids) == len(set(ids)) == len(references) == len(natives) == 72
    assert ids == [row["id"] for row in references] == [row["id"] for row in natives]
    assert Counter(row["house_code"] for row in supplied) == {
        "R": 24,
        "C": 24,
        "T": 24,
    }
    return [
        _Case(given, reference, native)
        for given, reference, native in zip(supplied, references, natives)
    ]


CASES = _load_cases()


def _bits(value: float) -> str:
    return "0x" + struct.pack(">d", value).hex()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.supplied["id"])
def test_house_coordinate_matches_independent_rounding(case: _Case) -> None:
    supplied = case.supplied
    latitude = float.fromhex(supplied["latitude"]["hex"])
    armc = float.fromhex(supplied["armc"]["hex"])
    obliquity = float.fromhex(supplied["obliquity"]["hex"])
    longitude = Fraction(supplied["backend_longitude_exact"])
    native = float.fromhex(case.native["position"]["hex"])
    assert _bits(native) == case.native["position"]["bits"]

    if supplied["house_code"] == "T":
        result = checked_topocentric_position(
            latitude=latitude,
            armc=armc,
            obliquity=obliquity,
            longitude=longitude,
            native_position=native,
        )
        recomputed_action = "topocentric_scalar_inverse_recomputed"
    else:
        result = checked_house_plane_position(
            latitude=latitude,
            armc=armc,
            obliquity=obliquity,
            longitude=longitude,
            house_code=supplied["house_code"].encode("ascii"),
            native_position=native,
        )
        recomputed_action = "scalar_plane_recomputed"

    target = case.reference[
        (
            "unshifted_continuous"
            if supplied["house_code"] == "T"
            else "declared_shifted_policy"
        )
    ]
    assert _bits(result.position) == target["half_open_delivery"]["bits"]
    assert result.house == target["house"] == math.floor(result.position)
    assert 1 <= result.position < 13

    # Nearest rounding and the separately labelled half-open delivery differ
    # at some boundaries; retain both independent targets.
    working = result.phase_degrees_working
    assert _bits(float(working / 30 + 1)) == target["position_rne"]["bits"]
    assert _bits(float(working)) == target["phase_rne"]["bits"]
    assert _bits(result.phase_degrees) == target["phase_circular_delivery"]["bits"]

    unshifted = (
        working
        if supplied["house_code"] == "T"
        else (working - Fraction(1, 3600000)) % 360
    )
    enclosure = case.reference["unshifted_continuous"]["phase_degrees"]
    lower, upper = Fraction(enclosure["lower"]), Fraction(enclosure["upper"])
    errors = [
        abs((unshifted - endpoint + 180) % 360 - 180) for endpoint in (lower, upper)
    ]
    # Include the circle's antipode when taking the interval supremum.
    maximum_error = (
        Fraction(180) if lower <= (unshifted + 180) % 360 <= upper else max(errors)
    )
    assert maximum_error <= Fraction(1, 10**50)

    # Action is the product contract; all numerical targets above are Arb-owned.
    expected = float.fromhex(target["half_open_delivery"]["hex"])
    assert result.action == (
        "native_coordinate_retained" if native == expected else recomputed_action
    )
