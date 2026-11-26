"""Frozen source-direction and equal-house recipe controls.

Expectations come from the sealed BEFORE reference and given-ASC recipe.
They qualify numerical direction and source consistency, not physical sky.
"""

import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.reference_frames import rotate_spherical

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "tests/data/geometry-source-constraints-v1.json").read_text())


@pytest.mark.parametrize("case", DATA["rotate"], ids=lambda c: c["input"]["id"])
def test_spherical_direction_retains_halfopen_side(case) -> None:
    given = case["input"]
    matrix = tuple(tuple(float.fromhex(v) for v in row) for row in given["matrix_hex"])
    longitude, latitude = rotate_spherical(
        matrix,
        float.fromhex(given["longitude_hex"]),
        float.fromhex(given["latitude_hex"]),
    )
    assert 0 <= longitude < 360
    assert longitude.hex() == case["expected_longitude_hex"]
    assert latitude.hex() == case["expected_latitude_hex"]


@pytest.mark.parametrize("case", DATA["equal"], ids=lambda c: c["id"])
def test_selected_precision_equal_recipe_uses_delivered_asc(
    case, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert runtime.swe is not None
    assert runtime.swe.version == "2.10.03"
    with runtime.preserve_ephemeris_path():
        with monkeypatch.context() as environment:
            environment.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            environment.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
            code = case["house_code"].encode("ascii")
            raw, angles = runtime.ephemeris_call(
                "houses_ex",
                case["jd_ut1"],
                case["latitude"],
                case["longitude"],
                code,
                0,
                _julian_day_tt=case["jd_tt"],
            )
            cusps, axes, receipt = canonical_house_geometry(
                julian_day_ut1=case["jd_ut1"],
                julian_day_tt=case["jd_tt"],
                latitude=case["latitude"],
                longitude=case["longitude"],
                house_code=code,
                native_cusps=raw,
                native_angles=angles,
                flags=0,
            )
    # Identify the frozen conditional operand, not a physical ASC reference.
    assert (
        axes[0].hex() == case["given_before_ASC_hex"]
    ), "Source operand/context drift; frozen conditional targets are unqualified"
    assert len(cusps) == len(case["source_recipe_targets"]) == 12
    assert receipt is not None
    precision = receipt["eastern_direction_precision"]
    assert precision["house_cusp_scope"] == (
        "equal_A_E_V_rebuilt_from_delivered_ASC_on_selected_precision_path"
    )
    assert [v.hex() for v in cusps] == [v["hex"] for v in case["source_recipe_targets"]]
    assert precision["corrected_cusps"] == [
        i + 1 for i, (old, new) in enumerate(zip(raw, cusps)) if old != new
    ]
