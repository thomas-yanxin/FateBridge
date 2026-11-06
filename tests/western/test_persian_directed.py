"""波斯向运 / Persian Directed — historical values and independent ordering.

Layer 1 (historical value check): feed the core builder the SAME natal object set
星阙 fed its own engine (a trimmed capture of ``chart_1998_predictive.json``) and
check the hit multiset against 星阙's unchanged output. Independent Decimal
arithmetic checks the actual unrounded chronological sequence and first120
selection. The historical display-age ordering has14 changed positions, all
within equal display ages.

Layer 2 (end-to-end): cast a chart through FateBridge's own engine and assert the
tool runs, the hits stay bounded (0 < age ≤ max), are sorted by age, and never name
a target outside FateBridge's scope (10 planets + 12 cusps). We do NOT row-match this
against 星阙's published fixture — its birth geo isn't published, so the cast houses
can't be reproduced — but Layer 1 already byte-locks the arithmetic itself, so Layer 2
only needs to prove the cast→build wiring and the documented scope.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

from fatebridge.core.astrology_lifespan import build_persian_directed_payload
from fatebridge.services.western_lifespan import calculate_persian_directed

_FIXTURES = Path(__file__).parents[1] / "fixtures"


def _chart() -> dict:
    return json.loads(
        (_FIXTURES / "horosa_persiandirected_chart_1998.json").read_text("utf-8")
    )


def _oracle() -> list[dict]:
    return json.loads(
        (_FIXTURES / "persiandirected_oracle_1998.json").read_text("utf-8")
    )


def _structured(hits: list[dict]) -> list[tuple]:
    return [(h["age"], h["promittor"], h["aspect"], h["significator"]) for h in hits]


# Layer 1 — unchanged historical hit values plus independent exact chronology.
def test_historical_values_and_independent_decimal_chronology() -> None:
    chart = _chart()
    # Original iteration order resolves only genuine equal, unrounded ages.
    natal = {o["id"]: float(o["lon"]) for o in chart["objects"]}
    payload = build_persian_directed_payload(
        natal,
        [float(c) for c in chart["house_cusps"]],
        birth_datetime=dt.datetime.strptime(chart["birth"], "%Y-%m-%d %H:%M:%S"),
        max_age_years=90.0,
    )
    expected = _oracle()
    with localcontext() as context:
        context.prec = 100
        circle = Decimal(360)
        source = {name: Decimal.from_float(lon) for name, lon in natal.items()}
        targets = list(source.items()) + [
            (f"{index + 1}宫头", Decimal.from_float(float(cusp)))
            for index, cusp in enumerate(chart["house_cusps"])
        ]
        candidates = []
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
        independent = [
            (round(float(arc) * 100) / 100, mover, aspect, target)
            for arc, mover, aspect, target in candidates[:120]
        ]
    actual, historical = _structured(payload["hits"]), _structured(expected)
    assert actual == independent
    assert Counter(actual) == Counter(historical)
    changes = [
        (i, before, after)
        for i, (before, after) in enumerate(zip(historical, actual))
        if before != after
    ]
    assert len(changes) == 14
    assert all(before[0] == after[0] for _, before, after in changes)
    assert changes[0] == (
        33,
        (8.78, "Jupiter", 60, "IC"),
        (8.78, "Jupiter", 120, "4宫头"),
    )
    assert len(payload["hits"]) == 120


def test_dates_match_horosa_oracle() -> None:
    """The 应期 dates (birth + age × tropical year) also reproduce 星阙's golden."""
    chart = _chart()
    natal = {o["id"]: float(o["lon"]) for o in chart["objects"]}
    payload = build_persian_directed_payload(
        natal,
        [float(c) for c in chart["house_cusps"]],
        birth_datetime=dt.datetime.strptime(chart["birth"], "%Y-%m-%d %H:%M:%S"),
    )
    golden = (_FIXTURES / "horosa_golden_persiandirected.txt").read_text("utf-8")
    # Spot-check a handful of dated rows verbatim from 星阙's published golden table.
    assert payload["hits"][0]["date"] == "1998-06-17"  # 0.32 Mars 0° perigee
    assert "| 0.32 | 1998-06-17 |" in golden
    assert payload["hits"][1]["date"] == "1999-05-09"  # 1.21 Moon 60° JupiterVenus


# Layer 2 — end-to-end through FateBridge's own engine + subset cross-check.
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
