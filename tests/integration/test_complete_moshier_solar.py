"""Independent author-C vectors, derivatives and unchanged DE440 root witnesses.

Inline vectors come from the original December-1996 g3plan + ear404 + epsiln C
implementation, compiled separately from FateBridge and Swiss. Velocity uses
an independent five-point derivative with h=0.125 TT day. These comparisons
validate the series implementation, not its physical accuracy.
"""

import json
import math
from pathlib import Path

import pytest

from fatebridge.core import moshier_solar

# Original author archive da6142ca4a0808d53ae4e21d57ab72008ecedc7b12cf73f31e0599e7acad0a0e
# https://www.moshier.net/aa-56.zip ; ear404.c original byte SHA below.
AUTHOR_EARTH_SHA = "9c3eb73355905f5f89d7bff6f8d22a7374ddbaa75ff59431ca19f51b1ea2f2ed"
AUTHOR_C_STATES = [
    (
        2300000.0,
        (-0.7265394908344506, 0.6116553299455095, 0.26581821621732243),
        (-0.011918243931212658, -0.01167722911983867, -0.005076711710737647),
    ),
    (
        2320965.625,
        (0.1817563678755983, -0.91762029909652, -0.3987155885196237),
        (0.016643035589750072, 0.002765680721398859, 0.0012028481401465212),
    ),
    (
        2341931.25,
        (0.44875971784827334, 0.8060958373235678, 0.35016681003933536),
        (-0.015606124331387009, 0.007120981772560597, 0.0030922116621984186),
    ),
    (
        2362896.875,
        (-0.8710578492278955, -0.4595838003110231, -0.19959593916843554),
        (0.008295577408434488, -0.013735198003495023, -0.005963556266622798),
    ),
    (
        2383862.5,
        (0.9913463622811655, -0.1572790479020798, -0.06823168052631153),
        (0.0026501128568411727, 0.015494848770711464, 0.0067256863040691854),
    ),
    (
        2404828.125,
        (-0.7207435552114673, 0.6173632732822737, 0.26785263432399414),
        (-0.012023362984590133, -0.011593295303294152, -0.00503061954277421),
    ),
    (
        2425793.75,
        (0.17469609810561373, -0.9188613002041305, -0.39854427978367357),
        (0.016668272411259805, 0.002653905587346831, 0.001151362491758327),
    ),
    (
        2446759.375,
        (0.45618274334177755, 0.8032087232576971, 0.34826155075659865),
        (-0.01553739669278346, 0.007234802908903992, 0.003136860801587593),
    ),
    (
        2467725.0,
        (-0.8745634782017374, -0.4533298897391627, -0.19648058334010332),
        (0.008182046894423515, -0.013803389478239114, -0.005982921456373691),
    ),
    (
        2488690.625,
        (0.9903896285048391, -0.16400263645253144, -0.07108126063331657),
        (0.0027764624454016396, 0.01547543371858301, 0.006705103159105441),
    ),
    (
        2547394.375,
        (-0.321570291794516, -0.8824803000395341, -0.3819571009823134),
        (0.016039249140732886, -0.00506967167700223, -0.00219540567377959),
    ),
    (
        2451545.0,
        (-0.177158713322775, 0.8874068665848459, 0.384736696598258),
        (-0.017203109405390087, -0.0029028427067444205, -0.0012585101755943444),
    ),
]

# Unmodified original DE440/Skyfield14904 TT rows at the largest independently
# solved residuals in the complete 1784..2204 source cohort. No SUT root values.
SUPPORTED_DE440_WITNESSES = [
    (2125, 17, 2497465.4705256997, 180),
    (1813, 19, 2383540.295279529, 210),
    (2058, 20, 2473039.6796426717, 225),
    (2050, 23, 2470162.194475987, 270),
    (2125, 16, 2497450.059526193, 165),
    (1830, 18, 2389734.309392214, 195),
]


def crossing(target, reference):
    low, high = reference - 60 / 86400, reference + 60 / 86400

    def residual(epoch):
        return math.remainder(moshier_solar.solar_longitude(epoch) - target, 360)

    assert residual(low) < 0 <= residual(high)
    for _ in range(40):
        mid = (low + high) / 2
        if mid in (low, high):
            break
        if residual(mid) < 0:
            low = mid
        else:
            high = mid
    assert residual(low) < 0 <= residual(high)
    return high


@pytest.mark.parametrize("epoch,position,velocity", AUTHOR_C_STATES)
def test_complete_emb_matches_original_author_c_position(epoch, position, velocity):
    actual, _ = moshier_solar.earth_moon_barycenter(epoch)
    assert actual == pytest.approx(position, abs=1e-12, rel=0)


@pytest.mark.parametrize("epoch,position,velocity", AUTHOR_C_STATES)
def test_analytic_emb_derivative_matches_independent_author_c_differences(
    epoch, position, velocity
):
    _, actual = moshier_solar.earth_moon_barycenter(epoch)
    assert actual == pytest.approx(velocity, abs=2e-11, rel=0)


def test_model_identifies_the_source_revision_and_preserves_precision_limits():
    details = moshier_solar.model_details()
    assert details["model_id"] == "fatebridge_complete_moshier_solar_v1"
    assert details["source_file_sha256"] == AUTHOR_EARTH_SHA
    assert (
        details["source_archive_sha256"]
        == "da6142ca4a0808d53ae4e21d57ab72008ecedc7b12cf73f31e0599e7acad0a0e"
    )
    assert details["native_moshier_relabelled"] is False
    assert details["reference_values_used_at_runtime"] is False
    assert details["accuracy_certified"] is False


@pytest.mark.parametrize("year,index,reference,target", SUPPORTED_DE440_WITNESSES)
def test_supported_high_residual_crossings_keep_original_one_second_gate(
    year, index, reference, target
):
    actual = crossing(target, reference)
    assert abs((actual - reference) * 86400) <= 1.0


def test_outside_scope_counterexample_still_exceeds_the_original_gate():
    # Original DE440 source row: this named revision has a real outside-domain
    # failure. Passing this limitation check is not an accuracy-gate pass.
    reference = 2556572.3605933925
    actual = crossing(120, reference)
    assert (actual - reference) * 86400 < -1.0
    assert moshier_solar.model_details()["accuracy_certified"] is False


@pytest.mark.local_data
@pytest.mark.parametrize(
    "name,count", [("de440-guard-tt.json", 96), ("de440-holdout576-tt.json", 576)]
)
def test_full_independent_tt_cohorts_keep_unchanged_one_second_gate(name, count):
    # External source packets are opened only inside local-data tests.
    packet = json.loads((Path(__file__).parents[1] / "data/solar" / name).read_text())
    assert len(packet["rows"]) == count
    assert packet["production_imports"] is False
    assert packet["tolerance_seconds"] == 1.0
    for row in packet["rows"]:
        actual = crossing(row["longitude"], row["jd_tt"])
        assert abs((actual - row["jd_tt"]) * 86400) <= 1.0, (row["year"], row["index"])
