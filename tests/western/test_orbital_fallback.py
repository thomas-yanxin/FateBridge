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


@pytest.mark.parametrize("row", MOTION_REFERENCE["rows"])
def test_full_TT_mapping_matches_independent_high_precision_curve(row):
    actual = ApproximateEphemeris(row["jd_tt"], row["jd_tt"]).state(row["body"])
    assert (
        abs(actual["longitude_speed"] - float(row["longitude_rate_deg_TT_day"])) * 3600
        <= MOTION_REFERENCE["gate_arcsec_per_TT_day"]
    )


@pytest.mark.parametrize("row", MOON_REFERENCE["rate_regressions"])
def test_lunar_pipeline_retains_native_rate_counterexamples(row):
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
def test_lunar_pipeline_retains_fine_clock_counterexamples(tt, monkeypatch):
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
    monkeypatch,
):
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
def test_object_motion_uses_its_actual_provider_source_and_numerical_method(name):
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


def test_missing_node_or_lot_motion_does_not_gain_a_computed_source_receipt():
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


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_solar_corner_keeps_physical_position_and_unknown_motion_across_transports(
    zodiacal, monkeypatch, surface_calls
):
    from fatebridge.core.astro import analytic_observer

    native = ephemeris._swisseph_planet_state
    bending = analytic_observer.finite_source_solar_deflection

    def selected(planet, *args, **kwargs):
        return None if planet == "Saturn" else native(planet, *args, **kwargs)

    def at_corner(*args, **kwargs):
        # Component tests exercise actual profile/limiter corners. Inject
        # their domain result here to verify all public delivery consumers.
        result = bending(*args, **kwargs)
        return CartesianMotion(result.position, None)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", selected)
    monkeypatch.setattr(analytic_observer, "finite_source_solar_deflection", at_corner)
    payload = {
        "planet": "Saturn",
        "sign": "Aries",
        "house": 0,
        "date": "2000-01-01",
        "time": "12:00",
        "zone": "UTC",
        "gps_lat": 40.0,
        "gps_lon": 0.0,
        "hsys": 0,
        "zodiacal": zodiacal,
    }
    http, protocol, code, cli = surface_calls(
        SPECS["otherbu"],
        payload,
        projection={
            "fields": [
                "chart.chart.objects",
                "chart.params.chart_profile.orbital_fallback",
            ],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        chart = result["chart"]
        saturn = next(p for p in chart["chart"]["objects"] if p["id"] == "Saturn")
        assert math.isfinite(saturn["lon"])
        assert saturn["motion"]["longitude_speed"] is None
        assert saturn["motion"]["direction"] == "not_computed"
        assert "method_id" not in saturn["motion"]
        receipt = chart["params"]["chart_profile"]["orbital_fallback"]
        assert receipt["uncomputed_motion_reasons"] == {
            "Saturn": "solar_deflection_has_no_unique_local_TT_derivative_at_profile_or_limiter_corner"
        }


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("mode", ["mixed", "all", "offline"])
def test_actual_object_motion_source_ownership_across_transports(
    zodiacal, mode, monkeypatch, surface_calls
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if mode == "offline":
        monkeypatch.setattr(runtime, "swe", None)
    original = ephemeris._swisseph_planet_state
    failed = (
        {"Moon", "Saturn", "North Node"}
        if mode == "mixed"
        else set(PHYSICAL_BODIES) | {"North Node"}
    )

    def selected(name, *args, **kwargs):
        return None if name in failed else original(name, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", selected)
    payload = {
        "planet": "Saturn",
        "sign": "Aries",
        "house": 0,
        "date": "2000-01-01",
        "time": "12:00",
        "zone": "UTC",
        "gps_lat": 40.0,
        "gps_lon": 0.0,
        "hsys": 0,
        "zodiacal": zodiacal,
    }
    projection = {
        "fields": [
            "chart.chart.objects",
            "chart.params.chart_profile.orbital_fallback",
        ],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http, protocol, code, local = surface_calls(
        SPECS["otherbu"], payload, projection=projection
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [
        business(http.json()),
        business(protocol.structured_content),
        business(local),
    ]
    assert outputs[0] == outputs[1] == outputs[2]
    provider = outputs[0]["chart"]["params"]["chart_profile"]["orbital_fallback"]
    observed = set()
    for item in outputs[0]["chart"]["chart"]["objects"]:
        source_name = "North Node" if item["id"] == "South Node" else item["id"]
        if source_name in failed and item["motion"]["longitude_speed"] is not None:
            observed.add(source_name)
            assert (
                item["motion"]["method_id"]
                == provider["factor_longitude_motion_methods"][source_name]
            )
            assert (
                item["motion"]["source_url"]
                == provider["factor_source_urls"][source_name]
            )
    assert observed == failed


@pytest.mark.parametrize("planet", (*PHYSICAL_BODIES, "North Node"))
def test_physical_positions_keep_tt_when_ut1_changes(planet):
    """Light-time iteration must not substitute a different Delta T model."""
    tt = 2488235.001
    a = ApproximateEphemeris(2488235.0, tt).state(planet)
    b = ApproximateEphemeris(2488234.9, tt).state(planet)
    assert a == b


@pytest.mark.parametrize("tt", [1721424.5, 5373488.5])
@pytest.mark.parametrize("planet", ["Sun", "Moon"])
def test_physical_frame_keeps_real_tt_beyond_local_civil_year_edges(tt, planet):
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
def test_longitude_motion_converges_including_longitude_wrap(planet):
    sky = ApproximateEphemeris(2460389.63, 2460389.631)
    state = sky.state(planet)
    # A smaller independent three-point stencil also includes the complete
    # displayed-frame rotation. This checks numerical differentiation only.
    for step in (0.0005, 0.001):
        left = sky.state(planet, -step)["longitude"]
        right = sky.state(planet, step)["longitude"]
        rate = ((right - left + 180) % 360 - 180) / (2 * step)
        assert abs(state["longitude_speed"] - rate) < 5e-6


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("date", [(1990, 4, 19, 0), (2026, 9, 15, 12)])
@pytest.mark.parametrize("mode", ["mixed", "all", "node"])
def test_actual_apparent_fallback_across_three_transports(
    date, mode, monkeypatch, surface_calls, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    year, month, day, hour = date
    times = ephemeris_time(datetime(year, month, day, hour, tzinfo=timezone.utc))
    failed = {
        "all": set(PHYSICAL_BODIES) | {"North Node"},
        "mixed": {"Moon", "Jupiter", "Saturn", "Uranus", "Pluto"},
        "node": {"North Node"},
    }[mode]
    reference = {}
    for name in failed:
        values, flags = runtime.ephemeris_call(
            "calc",
            times.jd_tt,
            (
                runtime.swe.MEAN_NODE
                if name == "North Node"
                else getattr(runtime.swe, name.upper())
            ),
            runtime.swe.FLG_MOSEPH,
        )
        assert flags & 7 == runtime.swe.FLG_MOSEPH
        reference[name] = values
    original = ephemeris._swisseph_planet_state

    def selected(planet, *args, **kwargs):
        return None if planet in failed else original(planet, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", selected)
    payload = {
        "birth_year": year,
        "birth_month": month,
        "birth_day": day,
        "birth_hour": hour,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 40.0,
        "use_true_solar_time": False,
        "chart_variant": "chart",
    }
    fields = [
        "planets",
        "chart_profile.orbital_fallback",
        "chart_profile.planetary_models",
        "chart_profile.julian_day_ut1",
        "chart_profile.julian_day_tt",
        "chart_profile.ephemeris_reference_points",
    ]
    http, protocol, code, cli = surface_calls(
        SPECS["astro_chart"],
        payload,
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [http.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        planets = {p["id"]: p for p in result["planets"]}
        for name, expected in reference.items():
            tolerance = (
                0.001 if name == "North Node" else 120 if name == "Moon" else 60
            ) / 3600
            assert (
                abs((planets[name]["longitude"] - expected[0] + 180) % 360 - 180)
                <= tolerance
            )
            assert abs(planets[name]["latitude"] - expected[1]) <= tolerance
        profile = result["chart_profile"]
        fallback = profile["orbital_fallback"]
        assert profile["julian_day_ut1"] == times.jd_ut1
        assert profile["julian_day_tt"] == fallback["julian_day_tt"] == times.jd_tt
        assert set(fallback["approximate_planets"]) == failed
        assert fallback["tt_source"] == "chart_tt"
        assert fallback["method_reference_url"] == (
            MEAN_NODE_SOURCE_URL if mode == "node" else PLANETARY_SOURCE_URL
        )
        assert fallback["accuracy_certified"] is False
        assert fallback["library_version"] == (
            MEAN_NODE_MODEL if mode == "node" else ORBITAL_MODEL
        )
        assert fallback["library"] == "FateBridge analytic ephemeris"
        assert "astronomy-engine" not in fallback["dependency_versions"]
        physical = failed - {"North Node"}
        if physical:
            assert "JPL DE441 bounded source" in fallback["dependency_versions"]
            for name in physical:
                assert fallback["factor_source_urls"][name] == PLANETARY_SOURCE_URL
        assert fallback["time_argument"] == "TT"
        assert fallback["light_time_method"] == (
            "not_applicable" if mode == "node" else "per_factor"
        )
        assert fallback["factor_light_time_methods"] == {
            name: LIGHT_TIME_METHOD for name in failed if name != "North Node"
        }
        assert fallback["uncomputed_motion_reasons"] == {}
        if "North Node" in failed:
            assert (
                "North Node"
                in profile["ephemeris_reference_points"]["theoretical_points"]
            )
            assert (
                "North Node"
                not in profile["ephemeris_reference_points"]["approximate_points"]
            )
            assert "2.10.03" in fallback["factor_source_versions"]["North Node"]
        for name, model in profile["planetary_models"].items():
            assert (model in FALLBACK_MODELS) == (name in failed)
            if name in failed:
                assert model == (
                    MEAN_NODE_MODEL if name == "North Node" else ORBITAL_MODEL
                )
                assert fallback["factor_time_arguments"][name] == (
                    "TT"
                    if name == "North Node"
                    else "TT; DE441 evaluated at geocentric TDB(TT)"
                )


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
    tt,
    mean_longitude,
    true_longitude,
    mean_rate,
    true_rate,
    mean_declination,
    true_declination,
):
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


def test_mean_node_correction_corner_is_not_an_invented_instantaneous_speed():
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


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_public_mean_node_corner_keeps_positions_and_only_unknown_motion(
    zodiacal, monkeypatch, surface_calls, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    original = ephemeris._swisseph_planet_state

    def selected(planet, *args, **kwargs):
        return None if planet == "North Node" else original(planet, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", selected)
    payload = {
        "planet": "Saturn",
        "sign": "Aries",
        "house": 0,
        "date": "2899-12-31",
        "time": "23:58:50.816000",
        "zone": "UTC",
        "lat": "40",
        "lon": "0",
        "hsys": 0,
        "zodiacal": zodiacal,
    }
    # Under the explicitly assumed future UTC offset, this actual civil input
    # round-trips to the published TT knot. No clock or coordinates are mocked.
    http, mcp, code, cli = surface_calls(
        SPECS["otherbu"],
        payload,
        projection={
            "fields": [
                "chart.chart.objects",
                "chart.params.chart_profile.orbital_fallback",
                "chart.params.chart_profile.julian_day_tt",
            ],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        profile = result["chart"]["params"]["chart_profile"]
        assert profile["julian_day_tt"] == 2780263.5
        assert set(profile["orbital_fallback"]["uncomputed_motion_reasons"]) == {
            "North Node"
        }
        points = {p["id"]: p for p in result["chart"]["chart"]["objects"]}
        for name in ["North Node", "South Node"]:
            assert math.isfinite(points[name]["lon"])
            assert points[name]["motion"]["longitude_speed"] is None
            assert points[name]["motion"]["direction"] == "not_computed"
        assert points["Moon"]["motion"]["direction"] == "direct"


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


def test_full_DE441_lunar_rate_reference_identity(lunar_rate_reference):
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
        ("retained-holdout4096", 4096),
        ("retained-Horizons97", 97),
        ("new-full-range128", 128),
    ],
)
def test_bounded_moon_complete_motion_against_independent_original_DE441(
    cohort, count, lunar_rate_reference
):
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
