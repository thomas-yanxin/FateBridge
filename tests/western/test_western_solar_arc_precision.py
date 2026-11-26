"""Symbolic solar-arc source controls; no observed-date precision claim."""

import gzip
import json
import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import astrology_lifespan
from fatebridge.core.astro.mixed_pairs import mixed_pair_geometry
from fatebridge.core.astro.sensitivity_grid import civil_recorded_sample
from fatebridge.core.astro.sensitivity_timing import SpecialtySampleTime
from fatebridge.core.astro.solar_arc import biwheel_geometry, rotate_factors
from fatebridge.core.astro.solar_arc_state import resolve_solar_arc_state
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.predictive import native_chart
from fatebridge.core.predictive._common import TIMING_POINT_NAMES, point_attribute_name
from fatebridge.core.predictive.solar_arc import build_solar_arc_payload
from tests.support.transports import SPECS, business, rest, surface_calls


def subjects(sun, progressed_sun, moon):
    positions = {p: 5.0 for p in TIMING_POINT_NAMES}
    positions.update(Sun=sun, Moon=moon, Mercury=31.5)
    natal = SimpleNamespace(
        **{
            point_attribute_name(k): SimpleNamespace(abs_pos=v)
            for k, v in positions.items()
        }
    )
    return (
        natal,
        SimpleNamespace(sun=SimpleNamespace(abs_pos=progressed_sun)),
        positions,
    )


def test_source_exact_rotation_controls_sign_and_aspect_eligibility_before_display() -> (
    None
):
    natal, progressed, positions = subjects(1.0, 11.1, 19.9)
    out = build_solar_arc_payload(natal, progressed)
    exact = (F(positions["Moon"]) + F(11.1) - F(1.0)) % 360
    assert exact < 30
    assert out["moon"]["sign"] == "Aries"
    assert not any(
        h["source"] == "Moon"
        and h["target"] == "Mercury"
        and h["aspect"] == "conjunction"
        for h in out["hits"]
    )
    # This pair is strictly outside the unchanged1.5-degree orb from the raw source formula.
    assert F(31.5) - exact > F(1.5)


def test_all_thirty_degree_cuts_neighbor_floats_and_both_arc_signs() -> None:
    for sun, progressed_sun in [(1.0, 11.1), (11.1, 1.0)]:
        arc = (F(progressed_sun) - F(sun)) % 360
        for boundary in range(0, 360, 30):
            source = float((F(boundary) - arc) % 360)
            for moon in [
                math.nextafter(source, -math.inf),
                source,
                math.nextafter(source, math.inf),
            ]:
                natal, progressed, _ = subjects(sun, progressed_sun, moon)
                exact = (F(moon) + F(progressed_sun) - F(sun)) % 360
                out = build_solar_arc_payload(natal, progressed)
                assert (
                    out["moon"]["sign"]
                    == (
                        "Aries",
                        "Taurus",
                        "Gemini",
                        "Cancer",
                        "Leo",
                        "Virgo",
                        "Libra",
                        "Scorpio",
                        "Sagittarius",
                        "Capricorn",
                        "Aquarius",
                        "Pisces",
                    )[int(exact // 30)]
                ), (
                    sun,
                    progressed_sun,
                    boundary,
                    moon,
                    exact,
                    out["moon"],
                )
                assert 0 <= out["moon"]["longitude"] < 360
                assert out["sun"]["longitude"] == progressed_sun
                assert out["arc_degrees"] == round(float(arc), 4)


def test_public_solar_arc_keeps_source_rotation_side_and_orb_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch, surface_calls
) -> None:
    birth_tt = ephemeris_time(datetime(2000, 5, 3, tzinfo=timezone.utc)).jd_tt
    original = native_chart._swisseph_planet_state

    def controlled(planet, *args, **kwargs):
        value = original(planet, *args, **kwargs)
        if value is None:
            return value
        else:
            pass
        state, model = value
        jd = kwargs["julian_day_tt"]
        if (planet == "Sun") or (planet in {"Moon", "Mercury"} and jd == birth_tt):
            state = {
                **state,
                "longitude": (
                    (1.0 if jd == birth_tt else 11.1)
                    if planet == "Sun"
                    else 19.9 if planet == "Moon" else 31.5
                ),
            }
        else:
            pass
        return state, model

    monkeypatch.setattr(native_chart, "_swisseph_planet_state", controlled)
    spec = SPECS["solararc"]
    inputs = dict(
        birth_year=2000,
        birth_month=5,
        birth_day=3,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=40.0,
        analysis_year=2001,
        analysis_month=5,
        analysis_day=3,
        analysis_hour=0,
        analysis_minute=0,
        house_system="W",
    )
    fields = [
        "solararc",
        "natal_reference.sun",
        "natal_reference.moon",
        "analysis_context",
    ]
    query = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http, mcp, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--strict-fields", "--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        assert out["natal_reference"]["sun"]["longitude"] == 1.0
        assert out["natal_reference"]["moon"]["longitude"] == 19.9
        assert out["solararc"]["moon"]["sign"] == "Aries", out["solararc"]["moon"]
        assert out["solararc"]["arc_degrees"] == 10.1


HAMBURG_DATA = Path(__file__).parents[1] / "data" / "hamburg_source_arc_v1"
HAMBURG_INPUTS = json.loads((HAMBURG_DATA / "inputs.json").read_text())["cases"]
HAMBURG_REFERENCE = {
    row["id"]: row
    for row in json.loads(
        gzip.decompress((HAMBURG_DATA / "reference.json.gz").read_bytes())
    )["rows"]
}


class HamburgSourceOperands(SolarEphemerisBatch):
    """Original invented binary64 Suns; no ephemeris/physical-source claim."""

    def __init__(self, natal: float, progressed: float):
        self.operands = (natal, progressed)
        self.calls = []

    def sun(self, jd_tt):
        index = len(self.calls)
        self.calls.append(jd_tt)
        return {
            "longitude": self.operands[index],
            "model": "synthetic_component_operand_not_ephemeris",
            "index": index,
        }


@pytest.mark.parametrize(
    "birth_label,old_progressed,exact_progressed",
    [
        (
            "2017-01-01T00:00:30+00:00",
            "0x1.2c04d407f5492p+21",
            "0x1.2c04d407f5491p+21",
        ),
        (
            "2016-12-31T23:55:33.546151+00:00",
            "0x1.2c04d400ed377p+21",
            "0x1.2c04d400ed378p+21",
        ),
    ],
)
def test_hamburg_progressed_sun_uses_retained_tt_before_projection(
    birth_label: str, old_progressed: str, exact_progressed: str
) -> None:
    birth = datetime.fromisoformat(birth_label)
    target = datetime(2017, 1, 2, 0, 0, 30, tzinfo=timezone.utc)
    recorded = civil_recorded_sample(birth)
    clock = SpecialtySampleTime(recorded, recorded.epoch, recorded.nominal_calendar)
    analysis_tt = TTInstant.from_utc(target, tai_minus_utc_seconds=37)
    batch = HamburgSourceOperands(5.0, 6.0)
    state = resolve_solar_arc_state(
        birth,
        recorded.tt.as_float(),
        target,
        batch=batch,
        clock=clock,
        analysis_tt=analysis_tt,
    )
    # Independent rational TT and calendar arithmetic in both rounding directions.
    assert state.progressed_julian_day_tt.hex() == exact_progressed
    assert [point.hex() for point in batch.calls] == [
        recorded.tt.as_float().hex(),
        exact_progressed,
    ]
    assert state.sun_observation_indices == (0, 1)

    ordinary_batch = HamburgSourceOperands(5.0, 6.0)
    ordinary = resolve_solar_arc_state(
        birth, recorded.tt.as_float(), target, batch=ordinary_batch
    )
    assert ordinary.progressed_julian_day_tt.hex() == old_progressed
    assert ordinary_batch.calls[1].hex() == old_progressed
    assert state.key_years == ordinary.key_years


@pytest.mark.parametrize("case", HAMBURG_INPUTS, ids=lambda case: case["id"])
def test_hamburg_retains_original_source_arc_through_complete_catalogues(case) -> None:
    expected = HAMBURG_REFERENCE[case["id"]]
    batch = HamburgSourceOperands(
        case["natal_tropical_sun"], case["progressed_tropical_sun"]
    )
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    state = resolve_solar_arc_state(
        birth,
        2451544.5007428704,
        birth + timedelta(days=30 * 365.25),
        batch=batch,
    )
    assert len(batch.calls) == 2
    assert state.arc == F(expected["arc"]["exact"])
    assert (
        state.to_record()["solar_arc_degrees"].hex() == expected["arc"]["nearest_hex"]
    )
    values = case["factor_longitudes"]
    rotated = rotate_factors(values, state.arc)
    assert set(rotated) == set(expected["rotated_factors"])
    for name, target in expected["rotated_factors"].items():
        assert rotated[name].hex() == target["nearest_hex"]

    biwheel = biwheel_geometry(values, state.arc, orb_degrees=case["orb_degrees"])
    mixed = mixed_pair_geometry(values, state.arc, orb_degrees=case["orb_degrees"])
    for period in ("90", "45"):
        for category in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            actual = {
                row["equation"]: row for row in biwheel["dials"][period][category]
            }
            targets = {
                row["equation"]: row for row in expected["biwheel"][period][category]
            }
            assert set(actual) == set(targets)
            for equation, target in targets.items():
                row = actual[equation]
                assert row["orb"].hex() == target["orb_hex"]
                assert row["signed_orb"].hex() == target["signed_orb_hex"]
                for field in (
                    "contains_hypothetical",
                    "zero_arc_identity",
                    "id_a",
                    "id_b",
                    "id_c",
                    "id_d",
                    "layer_a",
                    "layer_b",
                    "layer_c",
                    "layer_d",
                    "point",
                    "point_layer",
                    "axis_layer",
                ):
                    if field in target:
                        assert row.get(field) == target[field]
                    else:
                        pass
        for category in ("arc_dependent_contacts", "arc_invariant_contacts"):
            actual = {
                tuple(row[name] for name in ("id_a", "id_b", "id_c", "id_d"))
                + (int(2 * row["midpoint_arc_coefficient"]),): row
                for row in mixed["dials"][period][category]
            }
            targets = {
                tuple(row[name] for name in ("id_a", "id_b", "id_c", "id_d"))
                + (row["coefficient_numerator"],): row
                for row in expected["mixed_pairs"][period][category]
            }
            assert set(actual) == set(targets)
            for key, target in targets.items():
                row = actual[key]
                assert row["orb"].hex() == target["orb_hex"]
                assert row["signed_orb"].hex() == target["signed_orb_hex"]
                assert sorted(
                    tuple(sorted(a.items())) for a in row["factor_layer_assignments"]
                ) == sorted(
                    tuple(sorted(a.items())) for a in target["factor_layer_assignments"]
                )


PLANETARY_ARC_DATA = Path(__file__).parents[1] / "data" / "planetary_source_arc_v1"
PLANETARY_ARC_INPUTS = json.loads((PLANETARY_ARC_DATA / "inputs.json").read_text())[
    "cases"
]
PLANETARY_ARC_REFERENCE = {
    row["id"]: row
    for row in json.loads(
        gzip.decompress((PLANETARY_ARC_DATA / "reference.json.gz").read_bytes())
    )["cases"]
}
PLANETARY_ARC_DELIVERY = json.loads(
    (PLANETARY_ARC_DATA / "delivery-contract.json").read_text()
)


@pytest.mark.parametrize("case", PLANETARY_ARC_INPUTS, ids=lambda case: case["id"])
def test_planetary_arc_retains_source_values_through_full_hits_and_delivery(
    case, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = PLANETARY_ARC_REFERENCE[case["id"]]
    calls = []
    original = astrology_lifespan.collect_aspect_hits

    def record_collector(**kwargs):
        hits = original(**kwargs)
        calls.append((kwargs["source_longitudes"], hits))
        return hits

    monkeypatch.setattr(astrology_lifespan, "collect_aspect_hits", record_collector)
    result = astrology_lifespan.build_planetary_arc_payload(
        case["natal_longitudes"],
        case["progressed_longitudes"],
        arc_source=case["arc_source"],
        orb=case["orb"],
    )
    assert len(calls) == 1
    source_positions, full_hits = calls[0]
    assert tuple(source_positions) == tuple(case["natal_longitudes"])
    for name, target in expected["position_math"].items():
        assert source_positions[name] == F(target["directed"]["exact"])
    assert full_hits == expected["successful_hits_complete"]
    assert result["hits"] == expected["public_hits_top12"]
    for row, target in zip(full_hits, expected["successful_hits_complete"]):
        assert row["orb"].hex() == target["orb"].hex()
    assert tuple(result["positions"]) == tuple(expected["positions"])
    assert result["positions"] == expected["positions"]
    for name, target in expected["positions"].items():
        for field in ("degree", "absolute_degree", "longitude"):
            assert result["positions"][name][field].hex() == target[field].hex()
    assert result["arc_degrees"].hex() == expected["arc_degrees"].hex()
    assert result["arc_source"] == case["arc_source"]
    assert (
        result["arc_source_label"]
        == PLANETARY_ARC_DELIVERY["planet_labels"][case["arc_source"]]
    )
    assert result["orb"] == case["orb"]
