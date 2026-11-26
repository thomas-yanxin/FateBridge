"""Persian direction chronology, dates and public calculation scope."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from decimal import Decimal, localcontext

from fatebridge.core.astro.astrology_lifespan import build_persian_directed_payload
from fatebridge.services.western_lifespan import calculate_persian_directed

# Natal inputs captured from 星阙's chart_1998_predictive.json. Keep the original
# object order for exact ties and the original floats for near ties.
_CAPTURE_BIRTH = dt.datetime(1998, 2, 20, 20, 48)
_CAPTURE_LONGITUDES: dict[str, float] = {
    "Ceres": 0.3154204091126323,
    "SaturnMars": 3.872421656806182,
    "Desc": 11.828761129407894,
    "Saturn": 17.20238090584932,
    "Vesta": 33.776176114035465,
    "MC": 102.62473000876905,
    "Syzygy": 142.4870480887366,
    "North Node": 161.05001753954215,
    "Purple Clouds": 164.80172577759032,
    "Juno": 184.512170721687,
    "Dark Moon": 187.5089502028239,
    "Asc": 191.82876112940787,
    "Intp_Apog": 193.16345447065265,
    "Pholus": 201.03966872752036,
    "Chiron": 228.69194016197002,
    "Pluto": 247.9619190988538,
    "Moon": 251.8884206564945,
    "Pars Fortuna": 271.616088054603,
    "IC": 282.62473000876906,
    "MoonSun": 291.7820841190921,
    "Venus": 292.35097273282724,
    "Neptune": 300.8068886252994,
    "Uranus": 310.00837602893785,
    "JupiterVenus": 313.1000326970054,
    "Pallas": 327.5989661175372,
    "Mercury": 330.183730801573,
    "Sun": 331.6757475816897,
    "Jupiter": 333.8490926611836,
    "South Node": 341.0500175395422,
    "Mars": 350.5424624077631,
    "Intp_Perg": 350.86214295603276,
}
_CAPTURE_CUSPS: list[float] = [
    11.828761129407894,
    44.28464762521202,
    74.11830321448798,
    102.62473000876905,
    130.3234439772292,
    160.3110054978165,
    191.82876112940787,
    224.28464762521202,
    254.11830321448798,
    282.62473000876906,
    310.3234439772292,
    340.3110054978165,
]


def test_independent_decimal_chronology_and_dates() -> None:
    # Fingerprint the captured input, including target order, to catch transcriptions
    # that would otherwise affect both the Decimal check and production calculation.
    captured = [
        _CAPTURE_BIRTH.isoformat(sep=" "),
        list(_CAPTURE_LONGITUDES.items()),
        _CAPTURE_CUSPS,
    ]
    digest = hashlib.sha256(json.dumps(captured, separators=(",", ":")).encode())
    assert digest.hexdigest() == (
        "1367bca7d4146fcc8e08dbc1f2b237ef287a08459c2a8bc8e61bf6217486a54e"
    )

    payload = build_persian_directed_payload(
        _CAPTURE_LONGITUDES.copy(),
        _CAPTURE_CUSPS.copy(),
        birth_datetime=_CAPTURE_BIRTH,
    )
    assert payload["max_age_years"] == 90.0
    with localcontext() as context:
        context.prec = 100
        circle = Decimal(360)
        source = {
            name: Decimal.from_float(lon) for name, lon in _CAPTURE_LONGITUDES.items()
        }
        targets = list(source.items()) + [
            (f"{index}宫头", Decimal.from_float(cusp))
            for index, cusp in enumerate(_CAPTURE_CUSPS, start=1)
        ]
        candidates: list[tuple[Decimal, str, int, str]] = []
        for mover in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
            for target, longitude in targets:
                if mover == target:
                    continue
                for aspect in (0, 60, 90, 120, 180):
                    for direction in ((1,) if aspect in (0, 180) else (1, -1)):
                        arc = (longitude + direction * aspect - source[mover]) % circle
                        if arc < 0:
                            arc += circle
                        if 0 < arc <= 90:
                            candidates.append((arc, mover, aspect, target))
        candidates.sort(key=lambda row: row[0])
        tropical_year_days = Decimal("365.2421904")
        independent = [
            (
                round(float(arc) * 100) / 100,
                mover,
                aspect,
                target,
                (_CAPTURE_BIRTH + dt.timedelta(days=float(arc * tropical_year_days)))
                .date()
                .isoformat(),
            )
            for arc, mover, aspect, target in candidates[:120]
        ]
    actual = [
        (hit["age"], hit["promittor"], hit["aspect"], hit["significator"], hit["date"])
        for hit in payload["hits"]
    ]
    assert payload["hit_count"] == len(actual) == 120
    assert actual == independent
    # Published date anchors include a wrapped contact and the last kept hit.
    assert actual[:2] == [
        (0.32, "Mars", 0, "Intp_Perg", "1998-06-17"),
        (1.21, "Moon", 60, "JupiterVenus", "1999-05-09"),
    ]
    assert (7.96, "Venus", 60, "Ceres", "2006-02-07") in actual
    assert actual[-1] == (20.81, "Venus", 120, "Intp_Apog", "2018-12-14")
    # The MC and fourth cusp contacts are earlier than the IC and tenth cusp
    # contacts, even though all four display the same age.
    assert actual[32:36] == [
        (8.78, "Jupiter", 120, "MC", "2006-12-01"),
        (8.78, "Jupiter", 120, "4宫头", "2006-12-01"),
        (8.78, "Jupiter", 60, "IC", "2006-12-01"),
        (8.78, "Jupiter", 60, "10宫头", "2006-12-01"),
    ]


def test_age_limit_includes_exact_boundary() -> None:
    payload = build_persian_directed_payload(
        {"Sun": 0.0}, [89.0, 90.0, 90.004], max_age_years=90.0
    )
    assert [
        (hit["age"], hit["significator"])
        for hit in payload["hits"]
        if hit["aspect"] == 0
    ] == [(89.0, "1宫头"), (90.0, "2宫头")]


# This separate cast uses explicit coordinates to test the public service wiring.
_BIRTH_1998 = dict(
    birth_year=1998,
    birth_month=2,
    birth_day=20,
    birth_hour=20,
    birth_minute=48,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.0,
    birth_latitude=30.0,
    use_true_solar_time=False,  # match 星阙's raw-time /chart
)


def test_end_to_end_runs_and_is_bounded() -> None:
    result = calculate_persian_directed(max_age_years=90.0, **_BIRTH_1998)
    assert result.get("error") is None, result
    hits = result["persian_directed"]["hits"]
    assert hits, "expected at least one 波斯向运 hit"
    assert all(0 < h["age"] <= 90.0 for h in hits)
    assert all(
        h["promittor"]
        in {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
        for h in hits
    )
    # FateBridge scope: only the 10 planets + 12 cusps appear as targets.
    for h in hits:
        sig = h["significator"]
        assert "宫头" in sig or sig in {
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
        }


def test_hits_are_sorted_by_age() -> None:
    result = calculate_persian_directed(**_BIRTH_1998)
    ages = [h["age"] for h in result["persian_directed"]["hits"]]
    assert ages == sorted(ages)
