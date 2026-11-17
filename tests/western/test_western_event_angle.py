"""Unresolved native ASC is not a physical ruler or a known score input."""

import json
import sys
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import mpmath as mp
import pytest

from fatebridge.core.astrology_election import build_election_payload
from fatebridge.core.astrology_horary import build_horary_payload
from fatebridge.core.astrology_tables import SIGNS
from fatebridge.core.predictive.native_chart import build_native_subject
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/event_angle"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
SELECTED_FRAME_NULL_CASES = [
    {
        "id": f"selected-frame-null-{index}-{hemisphere}",
        "utc": instant,
        "selected_frame_null": hemisphere,
    }
    for index, instant in enumerate(sorted({row["utc"] for row in REFERENCE["rows"]}))
    for hemisphere in ("north", "south")
]


def test_geometry_reference_precedes_candidate_and_retains_all_conditions():
    verify_source_files(FIXTURE)
    assert len(REFERENCE["rows"]) == 28
    assert not REFERENCE["fatebridge_imported"]


@pytest.mark.parametrize(
    "row", REFERENCE["rows"] + SELECTED_FRAME_NULL_CASES, ids=lambda r: r["id"]
)
@pytest.mark.parametrize("house", ["R", "E", "W"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_native_subject_qualifies_the_selected_physical_angle_model(row, house, zodiac):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.earth_attitude import earth_attitude
    from fatebridge.core.astro.time_scales import ephemeris_time

    moment = datetime.fromisoformat(row["utc"])
    if hemisphere := row.get("selected_frame_null"):
        clock = ephemeris_time(moment)
        selected = earth_attitude(runtime.swe, clock.jd_ut1, julian_day_tt=clock.jd_tt)
        latitude = (1 if hemisphere == "north" else -1) * (
            90 - selected.reduction.house_obliquity
        )
        target_armc = 270 if hemisphere == "north" else 90
        longitude = float(
            (Fraction(target_armc) - Fraction(selected.house_sidereal_degrees) + 180)
            % 360
            - 180
        )
    else:
        latitude, longitude = row["latitude"], row["longitude"]
    subject = build_native_subject(
        name="Synthetic geometry fixture",
        local_datetime=moment,
        longitude=longitude,
        latitude=latitude,
        timezone_name="UTC",
        house_system=house,
        zodiac_type=zodiac,
    )
    # The frozen inputs approach the OLD native frame's degeneracy. The
    # managed equator has a different pole/origin, so reuse their coordinates,
    # not their old frame's boolean. The physical frame itself has separate
    # official SOFA and original house-kernel controls.
    attitude = earth_attitude(
        runtime.swe, subject.julian_day, julian_day_tt=subject.julian_day_tt
    )
    armc = float(
        (Fraction(attitude.house_sidereal_degrees) + Fraction(longitude)) % 360
    )
    obliquity = attitude.reduction.house_obliquity
    with mp.workdps(100):
        phi, theta, eps = (
            mp.mpf(value) * mp.pi / 180 for value in (latitude, armc, obliquity)
        )
        zenith = (
            mp.cos(phi) * mp.cos(theta),
            mp.cos(phi) * mp.sin(theta),
            mp.sin(phi),
        )
        pole = (mp.mpf(0), -mp.sin(eps), mp.cos(eps))
        cross = (
            zenith[1] * pole[2] - zenith[2] * pole[1],
            zenith[2] * pole[0] - zenith[0] * pole[2],
            zenith[0] * pole[1] - zenith[1] * pole[0],
        )
        norm = mp.sqrt(mp.fsum(value * value for value in cross))
        resolution_guard = mp.mpf(64) * mp.mpf(2) ** -52
        condition_threshold = mp.sqrt(mp.mpf(2) ** -52)
    if row.get("selected_frame_null"):
        assert norm <= resolution_guard
    definition = subject.calculation_basis.get("angle_definition")
    if norm > condition_threshold:
        assert definition is None
    else:
        assert definition is not None
        resolved = norm > resolution_guard
        assert definition["geometric_ascendant_resolved"] is bool(resolved)
        assert definition["geometry_inputs"]["armc"] == armc
        assert definition["geometry_inputs"]["obliquity"] == obliquity
        assert (
            abs(definition["conditioning"]["intersection_normal_norm"] - float(norm))
            <= 64 * sys.float_info.epsilon
        )
        assert definition["status"] == (
            "ecliptic_horizon_ill_conditioned"
            if resolved
            else "ecliptic_horizon_numerically_unresolved"
        )
        assert definition["midheaven_restricted_by_this_condition"] is False
    assert subject.sun.abs_pos is not None and subject.medium_coeli.abs_pos is not None


def synthetic_subject(*, mc=90, code="R", resolved=False):
    """Predicate controls, not an astronomical person or an independent sky."""
    s = SimpleNamespace(
        houses_system_identifier=code,
        zodiac_type="Tropical",
        is_diurnal=True,
        calculation_basis={
            "angle_definition": {
                "geometric_ascendant_resolved": resolved,
                "status": (
                    "ecliptic_horizon_numerically_unresolved"
                    if not resolved
                    else "ecliptic_horizon_ill_conditioned"
                ),
            }
        },
    )
    names = [
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
    ]

    def point(lon):
        return SimpleNamespace(
            abs_pos=lon,
            sign=SIGNS[int(lon // 30)],
            position=lon % 30,
            house="First_House",
            speed=1.0,
            retrograde=False,
        )

    for i, name in enumerate(names):
        setattr(s, name + "_house", point(i * 30.0))
    for name, lon in [
        ("sun", 220),
        ("moon", 250),
        ("mercury", 210),
        ("venus", 70),
        ("mars", 2),
        ("jupiter", 120),
        ("saturn", 30),
    ]:
        setattr(s, name, point(float(lon)))
    s.ascendant, s.medium_coeli = point(0.0), point(float(mc))
    return s


def test_horary_keeps_sky_but_not_formal_ruler_fortune_or_house_awards():
    value = build_horary_payload(synthetic_subject(), category="general")
    assert value["ascendant"]["longitude"] is None
    assert value["significators"]["querent"] is None
    assert value["significators"]["moon_co_significator"]["longitude"] == 250
    assert value["fortune"]["longitude"] is None
    assert value["radicality"]["ascendant_degree_gate"]["early"] is None
    assert value["perfection"]["candidate"] is None
    assert value["heuristic_verdict"] is None
    assert value["backend_convention"]["ascendant"]["longitude"] == 0
    for state in value["planets"].values():
        assert state["longitude"] is not None and state["occupied_house"] is None
    assert value["fortitudes"]["planets"]["Mars"]["literal_table_balance"] is None


@pytest.mark.parametrize("mc,known_hard", [(90, False), (2, True)])
def test_election_or_condition_keeps_known_mc_hit_and_unknown_asc(mc, known_hard):
    value = build_election_payload(synthetic_subject(mc=mc), topic_id="general")
    assert value["score"] is None
    assert value["ascendant"]["ruler"] is None
    assert value["axes"]["midheaven_longitude"] == mc
    assert value["axes"]["ascendant_longitude"] is None
    codes = {r["code"] for r in value["factors"]}
    missing = {r["code"] for r in value["unresolved_factors"]}
    assert ("malefic_on_angle_mars" in codes) is known_hard
    assert ("malefic_on_angle_mars" in missing) is (not known_hard)
    assert "ascendant_ruler_condition" in missing
    assert value["backend_convention"]["ascendant"]["ruler"] == "Mars"


@pytest.mark.parametrize("code", ["D", "N", "X", "M", "H"])
def test_independent_house_methods_keep_house_facts_but_not_an_asc_ruler(code):
    value = build_horary_payload(synthetic_subject(code=code), category="general")
    assert value["significators"]["querent"] is None
    assert value["planets"]["Mars"]["occupied_house"] == 1
    assert value["fortune"]["longitude"] is None


@pytest.mark.parametrize(
    "builder,options",
    [
        (build_horary_payload, {"category": "general"}),
        (build_election_payload, {"topic_id": "general"}),
    ],
)
def test_ill_conditioned_but_resolved_asc_is_not_reclassified_as_unknown(
    builder, options
):
    value = builder(synthetic_subject(resolved=True), **options)
    assert "reference_geometry" not in value
    assert "backend_convention" not in value
    assert value["ascendant"]["longitude"] == 0


@pytest.mark.parametrize("code", ["R", "N", "D", "X", "M", "H"])
def test_unknown_reference_does_not_erase_independent_lunar_or_essential_facts(code):
    value = build_horary_payload(synthetic_subject(code=code), category="career")
    backend = value["backend_convention"]
    assert value["moon"]["sign"] == backend["planets"]["Moon"]["sign"]
    assert value["moon"]["speed"] == backend["planets"]["Moon"]["speed"]
    assert (
        value["perfection"]["event_history"] == backend["perfection"]["event_history"]
    )
    assert value["radicality"]["hour_inputs"] == backend["radicality"]["hour_inputs"]
    for code_id in ("C03", "C04", "C05"):
        actual = next(
            row for row in value["radicality"]["clauses"] if row["code"] == code_id
        )
        original = next(
            row for row in backend["radicality"]["clauses"] if row["code"] == code_id
        )
        assert actual == original
    for name, state in value["planets"].items():
        for key in ("longitude", "speed", "essential_condition", "sign"):
            assert state[key] == backend["planets"][name][key]
    if code != "R":
        assert value["significators"]["quesited"] is not None
