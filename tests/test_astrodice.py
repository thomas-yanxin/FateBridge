"""Independent sign reference, exhaustive symbol space, and input counterexamples."""

import hashlib
import json
from contextlib import nullcontext
from datetime import datetime
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astrodice import normalize_planet, normalize_sign, sign_condition
from fatebridge.core.local_techniques.chart import _build_birth_info
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.core.requests.divination import OtherBuRequest
from fatebridge.services.divination import calculate_otherbu_analysis

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE = json.loads((FIXTURES / "astrodice-sign-reference.json").read_text())
PLANETS = [
    *REFERENCE["planets"],
    "Uranus",
    "Neptune",
    "Pluto",
    "NorthNode",
    "SouthNode",
]
SIGNS = list(REFERENCE["rows"])
FACES = dict(planet="Mercury", sign="Virgo", house=6)
SKY = dict(date="2000-02-29", time="18:15:00", zone="UTC", lat="0", lon="0")


@pytest.mark.parametrize("sign,planet", tuple(product(SIGNS, REFERENCE["planets"])))
def test_sign_conditions_against_manually_transcribed_primary_text(sign, planet):
    code = REFERENCE["rows"][sign][REFERENCE["planets"].index(planet)]
    expected = [
        name
        for symbol, name in (
            ("D", "domicile"),
            ("E", "exaltation"),
            ("d", "detriment"),
            ("F", "fall"),
        )
        if symbol in code
    ]
    assert sign_condition(planet, sign)["conditions"] == expected


def test_all_1728_combinations_preserve_faces_without_invented_sky():
    for planet, sign, house in product(PLANETS, SIGNS, range(12)):
        result = build_otherbu_result(planet=planet, sign=sign, house=house)
        assert (result["planet"], result["sign"], result["house"]) == (
            planet,
            sign,
            house,
        )
        details = result["symbolic_details"]
        ring = details["symbolic_house_ring"]
        assert [row["house_number"] for row in ring] == list(range(1, 13))
        # Start at the rolled house and walk forwards to check cyclic order.
        walked = ring[house:] + ring[:house]
        expected = SIGNS[SIGNS.index(sign) :] + SIGNS[: SIGNS.index(sign)]
        assert [row["sign"] for row in walked] == expected
        assert ring[house]["sign"] == sign
        assert result["diceChart"]["chart"]["objects"] == [
            {"id": planet, "sign": sign, "house": f"House{house + 1}"}
        ]
        assert result["diceChart"]["chart"]["angles"] == {}
        assert result["chart"] is None
        assert details["house_number"] == house + 1
        assert (
            details["sign_condition"]["conditions"]
            == sign_condition(planet, sign)["conditions"]
        )
        summary = result["interpretation"]["summary"]
        assert planet in summary and f"第{house + 1}宫" in summary
        assert all(
            result["interpretation"][k] in summary
            for k in ("planet_keyword", "sign_keyword", "house_keyword")
        )
        assert len(result["interpretation"]["condition_meanings"]) == len(
            details["sign_condition"]["conditions"]
        )
        assert result["validation"]["prediction"] == "not_validated"
        assert result["validation"]["real_world_sample_size"] == 0
        assert result["validation"]["authority_certified"] is False
        sources = {r["id"] for r in result["rulesets"]}
        assert all(trace["ruleset_id"] in sources for trace in result["rule_trace"])
        assert set(result["interpretation"]["basis"]) <= {
            t["rule_id"] for t in result["rule_trace"]
        }


@pytest.mark.parametrize(
    "value,expected",
    [
        ("太阳", "Sun"),
        ("☿", "Mercury"),
        ("☊", "NorthNode"),
        ("North Node", "NorthNode"),
        ("南交", "SouthNode"),
        (" southnode ", "SouthNode"),
        ("♇", "Pluto"),
    ],
)
def test_actual_planet_aliases(value, expected):
    assert normalize_planet(value) == expected
    assert OtherBuRequest(**{**FACES, "planet": value}).planet == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("白羊", "Aries"),
        ("处女座", "Virgo"),
        ("♑️", "Capricorn"),
        (" AQUARIUS ", "Aquarius"),
    ],
)
def test_actual_sign_aliases(value, expected):
    assert normalize_sign(value) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"planet": None},
        {"planet": ""},
        {"planet": "Chiron"},
        {"sign": None},
        {"sign": "Ophiuchus"},
        {"sign": ""},
        {"house": -1},
        {"house": 12},
        {"house": True},
        {"house": 1.5},
        {"house": "1"},
        {"hsys": 9},
        {"zodiacal": 2},
    ],
)
def test_invalid_faces_never_fall_back_or_clamp(changes):
    inputs = {**FACES, **changes}
    with pytest.raises((ValueError, TypeError)):
        build_otherbu_result(**inputs)
    with pytest.raises(ValidationError):
        OtherBuRequest(**inputs)
    assert calculate_otherbu_analysis(**inputs)["error_code"] == "validation_error"


@pytest.mark.parametrize("missing", ["planet", "sign", "house"])
def test_every_face_is_required(missing):
    inputs = {k: v for k, v in FACES.items() if k != missing}
    with pytest.raises(ValidationError):
        OtherBuRequest(**inputs)
    assert "error" in calculate_otherbu_analysis(**inputs)


@pytest.mark.parametrize(
    "context",
    [
        {"date": "2024-01-01"},
        {"zone": "UTC"},
        {"lat": "0"},
        {"date": "2024-01-01", "time": "00:00"},
        {**SKY, "zone": None},
        {**SKY, "lon": None},
        {**SKY, "lat": ""},
        {**SKY, "time": " "},
    ],
)
def test_partial_sky_context_never_uses_a_default(context):
    with pytest.raises(ValidationError):
        OtherBuRequest(**FACES, **context)
    assert "error" in calculate_otherbu_analysis(**FACES, **context)


def test_question_and_astronomical_modes_cannot_change_symbolic_evidence():
    original = build_otherbu_result(**FACES)
    for zodiacal, hsys, tradition in product([0, 1], [0, 3, 8], [False, True]):
        current = build_otherbu_result(
            **FACES,
            **SKY,
            zodiacal=zodiacal,
            hsys=hsys,
            tradition=tradition,
            question="请确认一定成功",
        )
        for key in ("symbolic_details", "rule_trace", "rulesets", "diceChart"):
            assert current[key] == original[key]
        for key, value in original["interpretation"].items():
            if key == "evidence":
                # The user-context paragraph is the only added explanation.
                context_evidence = current["interpretation"][key].copy()
                context_evidence.pop("question_adjustment")
                assert context_evidence == value
            else:
                assert current["interpretation"][key] == value
        assert current["chart"]["params"]["chartKind"] == "astronomical_context_only"


@pytest.mark.parametrize(
    "planet", ["Uranus", "Neptune", "Pluto", "NorthNode", "SouthNode"]
)
def test_modern_faces_never_receive_invented_classical_dignities(planet):
    result = build_otherbu_result(**{**FACES, "planet": planet}, tradition=True)
    condition = result["symbolic_details"]["sign_condition"]
    assert condition["status"] == "outside_seven_planet_scope"
    assert condition["conditions"] == []
    assert result["symbolic_details"]["houses_ruled_by_rolled_planet"] == []
    assert result["planet"] == planet


def test_shared_birth_input_preserves_seconds_and_microseconds():
    birth, _, _ = _build_birth_info(
        date_text="2000-02-29",
        time_text="18:15:59.123456",
        timezone_name="UTC",
        lat="0",
        lon="0",
    )
    assert (birth.utc_datetime.second, birth.utc_datetime.microsecond) == (59, 123456)
    direct = build_astro_birth_info(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=18,
        birth_minute=15,
        birth_second=59,
        birth_microsecond=123456,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    assert direct.utc_datetime == birth.utc_datetime


def test_sky_is_invariant_for_equivalent_offsets_and_changes_with_seconds():
    original = build_otherbu_result(**FACES, **SKY)
    shifted = build_otherbu_result(
        **FACES, **{**SKY, "date": "2000-03-01", "time": "02:15:00", "zone": "+08:00"}
    )
    seconds = build_otherbu_result(**FACES, **{**SKY, "time": "18:15:59"})
    assert original["chart"]["chart"] == shifted["chart"]["chart"]
    assert original["chart"]["chart"] != seconds["chart"]["chart"]
    assert original["symbolic_details"] == seconds["symbolic_details"]


@pytest.mark.parametrize(
    "reference",
    json.loads((FIXTURES / "jyotish-horizons.json").read_text())["references"],
    ids=lambda r: r["body"],
)
@pytest.mark.parametrize("file_free", [False, True], ids=["configured", "moshier"])
def test_optional_sky_positions_against_frozen_nasa_jpl_horizons(reference, file_free):
    from tests.golden.runner import golden_ephemeris

    fixture = json.loads((FIXTURES / "jyotish-horizons.json").read_text())
    assert (
        hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
        == reference["response_sha256"]
    )

    with golden_ephemeris() if file_free else nullcontext():
        for row in reference["rows"]:
            moment = datetime.fromisoformat(row["utc"])
            result = build_otherbu_result(
                **FACES,
                **{
                    **SKY,
                    "date": moment.strftime("%Y-%m-%d"),
                    "time": moment.strftime("%H:%M:%S"),
                },
            )
            actual = next(
                obj["lon"]
                for obj in result["chart"]["chart"]["objects"]
                if obj["id"] == reference["body"]
            )
            error = (
                abs((actual - row["apparent_ecliptic_longitude"] + 180) % 360 - 180)
                * 3600
            )
            assert error < fixture["tolerance_arcseconds"], (
                reference["body"],
                row["utc"],
                error,
            )
            params = result["chart"]["params"]
            assert params["calculationTimeUtc"] == moment.isoformat()
            assert params["chart_profile"]["calendar"] == "proleptic_gregorian"
            if file_free:
                # Analytical node flags may still report SWIEPH, yielding mixed.
                assert params["chart_profile"]["ephemeris_model"] in {
                    "moshier",
                    "mixed",
                }


@pytest.mark.parametrize(
    "date,time,zone",
    [
        ("2023-02-29", "12:00:00", "UTC"),
        ("2024-04-31", "12:00:00", "UTC"),
        ("2024-03-10", "02:30:00", "America/New_York"),
        ("2024-11-03", "01:30:00", "America/New_York"),
        ("2024-01-01", "25:00:00", "UTC"),
        ("2024-01-01", "12:00:00+08:00", "UTC"),
    ],
)
def test_invalid_civil_times_are_never_silently_repaired(date, time, zone):
    result = calculate_otherbu_analysis(
        **FACES, date=date, time=time, zone=zone, lat="40", lon="-74"
    )
    assert result["error_code"] == "validation_error"
    assert "chart" not in result
