"""Public results retain corrected arithmetic and its actual dependencies."""

from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from tests.jyotish.test_jyotish_transports import call_surfaces

PEAKS = {
    "Sun": 10,
    "Moon": 33,
    "Mars": 298,
    "Mercury": 165,
    "Jupiter": 95,
    "Venus": 357,
    "Saturn": 200,
}


def decimal_value(longitude, point, shift=0):
    with localcontext() as context:
        context.prec = 1500
        left = Decimal.from_float(float(longitude))
        right = (Decimal.from_float(float(point)) + shift) % 360
        return float(min(abs(left - right + turn * 360) for turn in [-1, 0, 1]) / 3)


def resolve(body, path):
    for part in path.split("."):
        body = body[int(part)] if isinstance(body, list) else body[part]
    return body


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize(
    "year,month,day,hour,minute",
    [(2000, 1, 1, 0, 0), (1990, 4, 6, 15, 10), (2024, 6, 16, 0, 0)],
)
def test_actual_returned_angles_strengths_grid_and_prose_on_three_surfaces(
    monkeypatch, capsys, key, year, month, day, hour, minute
):
    payload = dict(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
        divisions=[],
        birth_time_uncertainty_minutes=0,
        name="工程合成：力量数值依赖",
    )
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
            "india.charts.D1",
            "india.strengths",
            "india.ashtakavarga",
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
    strengths = india["strengths"]
    dig = strengths["dig_bala"]
    axes = dig["basis"]["angles"]
    assert axes["Ascendant"] == india["charts"]["D1"]["ascendant"]["longitude"]
    assert "unrounded opposite points" in dig["basis"]["numerical_policy"]
    sensitivity = india["birth_time_sensitivity"]
    assert sensitivity["sample_count"] == 1
    for planet in india["charts"]["D1"]["planets"]:
        name = planet["id"]
        if name not in PEAKS:
            continue
        uccha = decimal_value(planet["longitude"], (PEAKS[name] + 180) % 360)
        assert (
            planet["physical_state"]["degree_condition"]["uchcha_bala"]["value"]
            == uccha
        )
        assert strengths["sthana_bala"]["summary"][name]["uchcha_bala"] == uccha
        assert sensitivity["uchcha_bala_sample_range"][name] == {
            "minimum": uccha,
            "maximum": uccha,
            "unit": "virupa",
        }
        point, shift = (
            (axes["Midheaven"], 180)
            if name in {"Sun", "Mars"}
            else (
                (axes["Midheaven"], 0)
                if name in {"Moon", "Venus"}
                else (
                    (axes["Ascendant"], 180)
                    if name in {"Mercury", "Jupiter"}
                    else (axes["Ascendant"], 0)
                )
            )
        )
        value = decimal_value(planet["longitude"], point, shift)
        assert dig["summary"][name] == value
        assert sensitivity["dig_bala_sample_ranges"][name] == {
            "minimum": value,
            "maximum": value,
        }
    for branch in strengths["kala_bala"]["components"]["yuddha_bala"][
        "evidence"
    ].values():
        for planet, basis in branch["prewar_basis"].items():
            assert basis["inputs"]["dig_bala"] == dig["summary"][planet]
            assert (
                basis["inputs"]["sthana_bala"]
                == strengths["sthana_bala"]["summary"][planet]["total_virupa"]
            )
            values = list(basis["inputs"].values())
            assert basis["total_virupa"] == (
                None
                if None in values
                else float(sum((Fraction(v) for v in values), Fraction(0)))
            )
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if "fact_path" in factor:
                assert factor["fact"] == resolve(body, factor["fact_path"])
            for scenario in factor.get("calculation_context", {}).get("scenarios", []):
                assert scenario["value"] == resolve(body, scenario["fact_path"])
