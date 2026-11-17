"""Independent FLINT targets for exact-source opposite-node placement."""

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime, guolao
from fatebridge.core.astro.birth import build_astro_birth_info
from tests.support.ephemeris_context import empty_ephemeris_path

DATA = Path(__file__).parents[1] / "data/guolao/opposition_flint_v1"


@pytest.fixture(scope="module")
def reference():
    raw = gzip.decompress((DATA / "source.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (DATA / "source.json.sha256").read_text().strip()
    )
    data = json.loads(raw)
    assert len(data["inputs"]) == len(data["reference"]) == 12352
    return data


def test_all_frozen_flint_exact_source_palace_and_mansion_owners(reference):
    # These are declared component stress inputs and synthetic RA boundaries,
    # not paired physical vectors or independent ancient mansion evidence.
    boundaries = [
        {
            "su28": guolao.MANSION_NAMES[i] + "宿",
            "star": f"synthetic-{i}",
            "right_ascension": value,
        }
        for i, value in enumerate(reference["boundaries"])
    ]
    for case, expected in zip(reference["inputs"], reference["reference"], strict=True):
        assert case["id"] == expected["id"]
        state = {
            "longitude": float.fromhex(expected["longitude_hex"]),
            "right_ascension": float.fromhex(expected["right_ascension_hex"]),
            "derived_from": "罗",
            "derivation_source_longitude": case["source_longitude"],
            "derivation_source_right_ascension": case["source_right_ascension"],
        }
        body = guolao.body_placement("计", state, boundaries, case["ayanamsha"])
        assert (
            body["palace_branch"] == guolao.PALACE_BRANCHES[expected["palace_index"]]
        ), case["id"]
        assert (
            body["mansion"]["su28"] == boundaries[expected["mansion_index"]]["su28"]
        ), case["id"]


@pytest.mark.parametrize(
    "case_id",
    [
        "boundary-0",
        "boundary-672",
        "boundary-1008",
        "boundary-1344",
        "boundary-5712",
        "boundary-6048",
        "boundary-6384",
        "boundary-11760",
        "boundary-8",
        "boundary-12",
        "boundary-16",
        "random-0",
    ],
)
def test_actual_positions_retains_the_node_source_before_rounding(
    monkeypatch, reference, case_id
):
    index = next(i for i, row in enumerate(reference["inputs"]) if row["id"] == case_id)
    case, expected = reference["inputs"][index], reference["reference"][index]
    original = guolao.runtime.ephemeris_call

    def inject_node(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == ephemeris_runtime.swe.MEAN_NODE:
            coords, flags = result
            field = (
                "source_right_ascension"
                if args[2] & ephemeris_runtime.swe.FLG_EQUATORIAL
                else "source_longitude"
            )
            # Only the node's component is controlled. All other native calls
            # and source checks still execute; this is not a physical sample.
            return (case[field], *coords[1:]), flags
        return result

    monkeypatch.setattr(guolao.runtime, "ephemeris_call", inject_node)
    with empty_ephemeris_path():
        raw = guolao.positions(
            build_astro_birth_info(
                birth_year=2000,
                birth_month=1,
                birth_day=1,
                birth_hour=12,
                birth_minute=0,
                birth_timezone="UTC",
                birth_longitude=0,
                birth_latitude=0,
            ),
            observer_geometry=False,
        )
    source, derived = raw["extra"]["罗"], raw["extra"]["计"]
    assert derived["longitude"].hex() == expected["longitude_hex"]
    assert derived["right_ascension"].hex() == expected["right_ascension_hex"]
    assert derived["derived_from"] == "罗"
    assert (
        derived["derivation_source_longitude"]
        == source["longitude"]
        == case["source_longitude"]
    )
    assert (
        derived["derivation_source_right_ascension"]
        == source["right_ascension"]
        == case["source_right_ascension"]
    )
    assert derived["latitude"] == -source["latitude"]
    assert derived["longitude_speed"] == source["longitude_speed"]
