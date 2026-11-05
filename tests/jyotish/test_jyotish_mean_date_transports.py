"""Real public calls expose corrected calendar dependencies under v26."""

import json
import math
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from tests.jyotish.test_jyotish_transports import call_surfaces

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads(
    (ROOT / "tests/fixtures/jyotish-mean-date-api-reference.json").read_text()
)["cases"]
WEEK = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def resolve(body, path):
    for part in path.split("."):
        body = body[int(part)] if isinstance(body, list) else body[part]
    return body


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize(
    "row", CASES, ids=lambda r: f"{r['payload']['birth_month']}:{r['side']}"
)
def test_calendar_and_theme_values_follow_actual_returned_UT1_on_three_surfaces(
    monkeypatch, capsys, key, row
):
    payload = {**row["payload"], "birth_time_uncertainty_minutes": 0}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    body = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.ruleset_id",
            "india.profile",
            "india.strengths.kala_bala",
            "india.birth_time_sensitivity",
            "india.topic_evidence",
        ],
    )
    india = body["india"]
    assert (
        india["ruleset_id"]
        == india["profile"]["ruleset_id"]
        == "parashari_lahiri_core_v29"
    )
    jd = india["profile"]["julian_day_ut"]
    anchor = date(payload["birth_year"], payload["birth_month"], payload["birth_day"])
    midnight = Fraction(2 * anchor.toordinal() + 3442849, 2)
    offset = math.floor(
        Fraction(jd) - midnight + Fraction(payload["birth_longitude"]) / 360
    )
    expected = anchor + timedelta(days=offset)
    calendar = india["strengths"]["kala_bala"]["calendar_context"]
    assert calendar["local_mean_date"] == expected.isoformat()
    # The frozen host-specific UT1 probes remain exact; other admitted source
    # contexts are checked against their actual returned UT1, never against a
    # guessed UTC=UT1 identity or an adjusted floating tolerance.
    if jd == row["jd_ut1"]:
        for k, v in row["expected_calendar"].items():
            assert calendar[k] == v
    n = 714404108573 + (expected - date(1860, 1, 1)).days
    for key, lord, amount in [
        ("abda_bala", WEEK[3 * (n // 360) % 7], 15),
        ("masa_bala", WEEK[2 * (n // 30) % 7], 30),
    ]:
        part = india["strengths"]["kala_bala"]["components"][key]
        assert part["ruler"] == lord
        assert part["summary"] == {p: amount if p == lord else 0.0 for p in WEEK}
    kala = india["strengths"]["kala_bala"]
    for evidence in kala["components"]["yuddha_bala"]["evidence"].values():
        for planet, basis in evidence["prewar_basis"].items():
            for component in ("abda_bala", "masa_bala"):
                assert (
                    basis["inputs"][component]
                    == kala["components"][component]["summary"][planet]
                )
            values = list(basis["inputs"].values())
            expected_total = (
                None
                if None in values
                else float(sum((Fraction(v) for v in values), Fraction(0)))
            )
            assert basis["total_virupa"] == expected_total
    sensitivity = india["birth_time_sensitivity"]
    assert sensitivity["sample_count"] == 1
    ranges = sensitivity["temporal_bala_scenario_sample_ranges"]["kala_bala"]
    for scenario, amounts in kala["scenarios"].items():
        for planet, value in amounts.items():
            if value is not None:
                assert ranges[scenario][planet] == {
                    "minimum": value,
                    "maximum": value,
                    "sample_count": 1,
                }
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor.get("rule_id") == "jyotish.kala_components.v1":
                context = factor["calculation_context"]
                assert factor["fact"] == resolve(body, factor["fact_path"])
                for scenario in context["scenarios"]:
                    assert scenario["value"] == resolve(body, scenario["fact_path"])
