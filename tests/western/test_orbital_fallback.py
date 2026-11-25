"""Independent apparent-position controls and actual fallback delivery."""

import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import erfa
import pytest

from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.analytic_observer import (
    LIGHT_TIME_METHOD,
)
from fatebridge.core.astro.cartesian import CartesianMotion
from fatebridge.core.astro.de441_source import SOURCE_URL as PLANETARY_SOURCE_URL
from fatebridge.core.astro.de441_source import barycentric_state
from fatebridge.core.astro.mean_node import SOURCE_URL as MEAN_NODE_SOURCE_URL
from fatebridge.core.astro.mean_node import mean_lunar_node
from fatebridge.core.astro.native_motion import context_motion
from fatebridge.core.astro.orbits import (
    FALLBACK_MODELS,
    MEAN_NODE_MODEL,
    ORBITAL_MODEL,
    ApproximateEphemeris,
)
from fatebridge.core.astro.reference import PHYSICAL_BODIES
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from tests.support.transports import SPECS, business, rest, surface_calls

MOON_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/lunar-motion-source-reference-v1.json"
    ).read_text()
)
MOTION_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/analytic-tt-motion-reference-v1.json"
    ).read_text()
)


def test_offline_orbit_receives_the_retained_relative_tt_without_scalar_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Original SOFA source-arithmetic control modern_tt:0. This checks the
    # real source argument, separately from bounded orbit/physical accuracy.
    point = TTInstant(Fraction(26397351585456151, 10800000000))
    engine = ApproximateEphemeris(0.0, point)
    original = engine.observer.apparent_state
    epochs = []

    def observe(planet, days, offset=0.0):
        epochs.append((planet, days, offset))
        return original(planet, days, offset)

    monkeypatch.setattr(engine.observer, "apparent_state", observe)
    result = engine.state("Sun")
    assert math.isfinite(result["longitude"])
    assert engine.tt is point
    assert epochs == [("Sun", point.days - 2451545, 0.0)]
    assert engine.julian_day_tt == point.as_float()


def test_local_node_offsets_reach_the_same_typed_model_point() -> None:
    # The old existing offset API erased all three supplied epochs by
    # adding them to the large JD. No new model or coefficient is selected.
    scalar = float.fromhex("0x1.2a5d39c45a692p+21")
    engine = ApproximateEphemeris(scalar, scalar)
    points = []
    for micros in (-1, 0, 1):
        offset = micros / 86400000000
        point = TTInstant(Fraction(scalar) + Fraction(offset))
        result = engine.state("North Node", offset)
        assert result == mean_lunar_node(point)
        points.append(point.days)
    assert len(set(points)) == 3


@pytest.mark.parametrize("row", MOTION_REFERENCE["rows"])
def test_full_TT_mapping_matches_independent_high_precision_curve(row) -> None:
    actual = ApproximateEphemeris(row["jd_tt"], row["jd_tt"]).state(row["body"])
    assert (
        abs(actual["longitude_speed"] - float(row["longitude_rate_deg_TT_day"])) * 3600
        <= MOTION_REFERENCE["gate_arcsec_per_TT_day"]
    )


@pytest.mark.parametrize("row", MOON_REFERENCE["rate_regressions"])
def test_lunar_pipeline_retains_native_rate_counterexamples(row) -> None:
    sky = ApproximateEphemeris(row["jd_tt"], row["jd_tt"])
    actual = sky.state("Moon")
    for key, value in row["position"].items():
        error = (
            math.remainder(actual[key] - value, 360)
            if key == "longitude"
            else actual[key] - value
        )
        assert abs(error) * 3600 <= MOON_REFERENCE["apparent_position_gate_arcsec"]
    assert (
        abs(actual["longitude_speed"] - row["longitude_speed"]) * 3600
        <= MOON_REFERENCE["longitude_speed_gate_arcsec_day"]
    )


@pytest.mark.parametrize("tt", MOON_REFERENCE["fine_rate_failures"])
def test_lunar_pipeline_retains_fine_clock_counterexamples(
    tt, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fatebridge.core.astro import analytic_observer

    original = analytic_observer.solve_light_cone
    receipts = []

    def observe(epoch, observer, sample):
        solution = original(epoch, observer, sample)
        receipts.append((epoch, solution))
        return solution

    monkeypatch.setattr(analytic_observer, "solve_light_cone", observe)
    sky = ApproximateEphemeris(tt, tt)
    rate = sky.state("Moon")["longitude_speed"]
    for step in MOON_REFERENCE["fine_rate_steps_TT_days"]:
        left = sky.state("Moon", -step)["longitude"]
        right = sky.state("Moon", step)["longitude"]
        fine = math.remainder(right - left, 360) / (2 * step)
        assert abs(rate - fine) < MOON_REFERENCE["fine_rate_gate_deg_TT_day"]
    assert receipts
    for epoch, solution in receipts:
        assert epoch == 0.0
        assert 1 <= solution.iterations <= 20
        assert solution.lower.residual_squared < 0 < solution.upper.residual_squared
        assert math.nextafter(solution.lower.epoch, math.inf) == solution.upper.epoch


def test_explicit_TT_lunar_source_does_not_load_unrelated_solar_or_Brown_orbits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import astronomy

    from fatebridge.core import de440_solar

    def unrelated(*args, **kwargs):
        raise AssertionError("Unused orbital source was loaded")

    monkeypatch.setattr(de440_solar, "_profile", unrelated)
    monkeypatch.setattr(astronomy, "GeoMoon", unrelated)
    sky = ApproximateEphemeris(2451545.0, 2451545.0)
    assert all(math.isfinite(v) for v in sky.state("Moon").values())
    provenance = sky.provenance(["Moon"])
    assert "astronomy-engine" not in provenance["dependency_versions"]
    assert "JPL DE441 bounded source" in provenance["dependency_versions"]
    assert "TDB(TT)" in provenance["factor_time_arguments"]["Moon"]


@pytest.mark.parametrize("name", (*PHYSICAL_BODIES, "North Node", "South Node"))
def test_object_motion_uses_its_actual_provider_source_and_numerical_method(
    name,
) -> None:
    source_name = "North Node" if name == "South Node" else name
    model = MEAN_NODE_MODEL if source_name == "North Node" else ORBITAL_MODEL
    provider = ApproximateEphemeris(2451545.0, 2451545.0).provenance([source_name])
    motion = context_motion(
        name, {source_name: 1e-15}, {source_name: model}, "tropical_ecliptic_of_date"
    )
    assert (
        motion["method_id"] == provider["factor_longitude_motion_methods"][source_name]
    )
    assert motion["source_url"] == provider["factor_source_urls"][source_name]
    assert motion["longitude_speed"] == 1e-15


def test_missing_node_or_lot_motion_does_not_gain_a_computed_source_receipt() -> None:
    for name in ("North Node", "South Node", "Pars Fortuna"):
        motion = context_motion(
            name,
            {"North Node": None},
            {"North Node": MEAN_NODE_MODEL},
            "tropical_ecliptic_of_date",
        )
        assert motion["longitude_speed"] is None
        assert motion["direction"] == "not_computed"
        assert "method_id" not in motion and "source_url" not in motion


@pytest.mark.parametrize("planet", (*PHYSICAL_BODIES, "North Node"))
def test_physical_positions_keep_tt_when_ut1_changes(planet) -> None:
    """Light-time iteration must not substitute a different Delta T model."""
    tt = 2488235.001
    a = ApproximateEphemeris(2488235.0, tt).state(planet)
    b = ApproximateEphemeris(2488234.9, tt).state(planet)
    assert a == b


@pytest.mark.parametrize("tt", [1721424.5, 5373488.5])
@pytest.mark.parametrize("planet", ["Sun", "Moon"])
def test_physical_frame_keeps_real_tt_beyond_local_civil_year_edges(
    tt: float, planet: str
) -> None:
    # Civil years1/9999 can project outside those TT years through timezone
    # offsets and DeltaT. The bounded Lahiri auxiliary API is a separate layer.
    sky = ApproximateEphemeris(tt - 0.1, tt)
    state = sky.state(planet)
    assert sky.julian_day_tt == tt and sky.tt_source == "chart_tt"
    assert 0 <= state["longitude"] < 360
    assert all(math.isfinite(value) for value in state.values())
    assert sky.state(planet) != ApproximateEphemeris(
        min(max(tt, 1721425.5), 5373485.5),
        min(max(tt, 1721425.5), 5373485.5),
    ).state(planet)


@pytest.mark.parametrize("planet", PHYSICAL_BODIES)
def test_longitude_motion_converges_including_longitude_wrap(planet) -> None:
    sky = ApproximateEphemeris(2460389.63, 2460389.631)
    state = sky.state(planet)
    # A smaller independent three-point stencil also includes the complete
    # displayed-frame rotation. This checks numerical differentiation only.
    for step in (0.0005, 0.001):
        left = sky.state(planet, -step)["longitude"]
        right = sky.state(planet, step)["longitude"]
        rate = ((right - left + 180) % 360 - 180) / (2 * step)
        assert abs(state["longitude_speed"] - rate) < 5e-6


# Frozen unmodified Swiss 2.10.03 analytical mean-node controls, not outputs
# recomputed by FateBridge. Mean and true ecliptic frames share numerical TT.
@pytest.mark.parametrize(
    "tt,mean_longitude,true_longitude,mean_rate,true_rate,mean_declination,true_declination",
    [
        (
            1721621.0,
            258.0782451259575,
            258.08302494460526,
            -0.05295594583778047,
            -0.05295210840172619,
            -23.153585900528565,
            -23.15341142662104,
        ),
        (
            2086498.0,
            15.862902781562264,
            15.861900451819869,
            -0.052954809336537255,
            -0.052976665086431576,
            6.274582694930876,
            6.274789157685318,
        ),
        (
            2451741.0,
            114.6656169012112,
            114.66150194686199,
            -0.052953774765710476,
            -0.05292934810690087,
            21.191256790093068,
            21.190933478472836,
        ),
        (
            3182226.0,
            313.57895705061816,
            313.58279223251566,
            -0.052951452197459885,
            -0.05291790661730818,
            -16.57009098670422,
            -16.570152928488273,
        ),
        (
            5373315.0,
            220.0435289333196,
            220.04720970472255,
            -0.052944391467844784,
            -0.05294901768717538,
            -14.345769686609717,
            -14.345627139787805,
        ),
    ],
)
def test_sourced_mean_node_against_frozen_native_vectors(
    tt: float,
    mean_longitude: float,
    true_longitude: float,
    mean_rate,
    true_rate,
    mean_declination,
    true_declination,
) -> None:
    for include_nutation, longitude, rate in [
        (False, mean_longitude, mean_rate),
        (True, true_longitude, true_rate),
    ]:
        state = mean_lunar_node(tt, include_nutation=include_nutation)
        assert abs((state["longitude"] - longitude + 180) % 360 - 180) * 3600 <= 0.001
        assert abs(state["longitude_speed"] - rate) * 3600 <= 0.001
        assert state["latitude"] == 0.0
        declination = true_declination if include_nutation else mean_declination
        assert abs(state["declination"] - declination) * 3600 <= 0.001


def test_mean_node_correction_corner_is_not_an_invented_instantaneous_speed() -> None:
    # Published correction changes slope here. Immediately adjacent float
    # epochs are distinct segments, even when a float quotient rounds to an int.
    knot = 2780263.5
    center = mean_lunar_node(knot)
    left = mean_lunar_node(math.nextafter(knot, -math.inf))
    right = mean_lunar_node(math.nextafter(knot, math.inf))
    assert (
        abs((center["longitude"] - 358.3311603595848 + 180) % 360 - 180) * 3600 <= 0.001
    )
    assert "longitude_speed" not in center
    assert right["longitude_speed"] - left["longitude_speed"] == pytest.approx(
        9.965981505438167e-09, abs=1e-12
    )
    provider = ApproximateEphemeris(knot, knot)
    assert "longitude_speed" not in provider.state("North Node")
    assert set(provider.uncomputed_motion_reasons) == {"North Node"}
    # At a flat published knot, the two slopes agree and the derivative exists.
    assert "longitude_speed" in mean_lunar_node(2451545.25)


@pytest.fixture(scope="module")
def lunar_rate_reference():
    directory = Path(__file__).parents[1] / "data/de441_lunar_motion_v1"
    raw = gzip.decompress((directory / "reference.json.gz").read_bytes())
    assert (
        hashlib.sha256(raw).hexdigest()
        == (directory / "reference.json.sha256").read_text().strip()
        == "24b44d423c7d8130165b270c4034b1b7435979a73d140531e4d847f9c38789cd"
    )
    return json.loads(raw)


def test_full_DE441_lunar_rate_reference_identity(lunar_rate_reference) -> None:
    reference = lunar_rate_reference
    assert len(reference["rows"]) == 4565
    assert len({row["jd_tt"] for row in reference["rows"]}) == 4560
    assert reference["native_frame_source_commit"] == (
        "696bda432298d482d27e67a0cf1238920301a7dd"
    )
    assert reference["reference_versions"] == {
        "skyfield": "1.55",
        "jplephem": "2.23",
        "numpy": "2.5.4",
        "pyerfa": "2.0.1.5",
        "sgp4": "2.27",
    }
    assert reference["new_civil_or_physical_observations"] == 0
    assert reference["global_SOTA_accepted"] is False


@pytest.mark.parametrize(
    "cohort,count",
    [
        ("retained-original244", 244),
        ("retained-Horizons97", 97),
        ("new-full-range128", 128),
    ],
)
def test_bounded_moon_complete_motion_against_independent_original_DE441(
    cohort: str, count: int, lunar_rate_reference
) -> None:
    reference = lunar_rate_reference
    selected = [row for row in reference["rows"] if row["cohort"] == cohort]
    assert len(selected) == count
    criteria = reference["criteria"]
    bias = erfa.bp06(2451545.0, 0.0)[0]
    for row in selected:
        tt = row["jd_tt"]
        sky = ApproximateEphemeris(tt, tt)
        state = sky.state("Moon")
        motion = sky.observer.apparent_state("Moon", tt - 2451545.0)
        assert motion.velocity is not None and not sky.uncomputed_motion_reasons
        radius = math.hypot(*motion.position)
        direction = tuple(p / radius for p in motion.position)
        radial_rate = math.fsum(
            u * v for u, v in zip(direction, motion.velocity, strict=True)
        )
        direction_rate = bias.T @ tuple(
            (v - u * radial_rate) / radius
            for u, v in zip(direction, motion.velocity, strict=True)
        )
        for expected in row["references"].values():
            # Uncertain reference rows fail explicitly; no skip or subset pass.
            assert (
                max(
                    expected["direction_stencil_difference"],
                    expected["longitude_stencil_difference"],
                )
                <= criteria["reference_convergence_arcsec_per_TT_day"]
            )
            assert (
                expected["radial_stencil_difference"]
                <= criteria["radial_rate_metres_per_TT_day"]
            )
            assert (
                math.hypot(
                    *(
                        a - b
                        for a, b in zip(
                            direction_rate,
                            expected["direction_derivative"],
                            strict=True,
                        )
                    )
                )
                * 180
                / math.pi
                * 3600
                <= criteria["angular_rate_arcsec_per_TT_day"]
            )
            assert (
                abs(state["longitude_speed"] - expected["longitude_speed"]) * 3600
                <= criteria["angular_rate_arcsec_per_TT_day"]
            )
            assert (
                abs(radial_rate - expected["radial_rate"]) * 149597870700
                <= criteria["radial_rate_metres_per_TT_day"]
            )
        source_epoch = Fraction(row["source_TDB_whole"] - 2451545.0) + Fraction(
            row["source_TDB_fraction"]
        )
        moon = barycentric_state("Moon", source_epoch)
        earth = barycentric_state("Earth", source_epoch)
        for m, e, expected in zip(
            moon.velocity, earth.velocity, row["raw_geometric_velocity"], strict=True
        ):
            error = abs(m - e - expected)
            assert error <= criteria["raw_source_velocity_AU_per_TDB_day"]
            assert (
                error
                <= criteria["additional_existing_source_velocity_line_AU_per_TDB_day"]
            )
