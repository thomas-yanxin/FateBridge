"""Source-ordinal temporal rule, independent target astronomy and input bounds."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import guolao, guolao_timing
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from tests.fixtures.surface_payloads import astro_payload
from tests.guolao.test_guolao_depth import chart

FIXTURES = Path(__file__).parents[1] / "fixtures"
TARGET = datetime(2027, 6, 1, tzinfo=timezone(timedelta(hours=8)))


def test_small_limit_facsimile_and_transcribed_cases_are_preserved():
    folder = FIXTURES / "guolao-small-limit-v1"
    reference = json.loads((folder / "reference.json").read_text())
    assert (
        hashlib.sha256((folder / reference["source_file"]).read_bytes()).hexdigest()
        == reference["sha256"]
    )
    assert reference["small_limit"]["text"] == "以生年支加在命宮逆數至太歲宮是"
    assert not reference["calendar_policy"]["source_year_boundary_adjudicated"]
    assert not reference["large_limit_dependency"]["full_method_reconstructed"]
    for case in reference["small_limit"]["ordinal_cases"]:
        assert (
            guolao.guolao_classical.small_limit_branch(
                case["life"], case["birth_year"], case["target_year"]
            )
            == case["small_limit"]
        )


@pytest.mark.parametrize(
    "year,stem,year_branch,limit,palace",
    [
        (2026, "丙", "午", "申", "命"),
        (2027, "丁", "未", "未", "财帛"),
        (2028, "戊", "申", "午", "兄弟"),
    ],
)
def test_source_reverse_small_limit_is_connected_to_explicit_year(
    year, stem, year_branch, limit, palace
):
    source = json.loads((FIXTURES / "guolao-classical-source.json").read_text())
    assert (
        source["transcription"]["small_limit_rule"] == "以生年支加在命宮逆數至太歲宮是"
    )
    result = chart(analysis_datetime=datetime(year, 6, 1, tzinfo=timezone.utc))
    g = result["guolao"]
    small = g["timing"]["small_limit"]
    assert (small["life_branch"], small["birth_year_branch"]) == ("申", "午")
    assert (small["target_year_stem"], small["target_year_branch"]) == (
        stem,
        year_branch,
    )
    assert (small["branch"], small["natal_functional_palace"]) == (limit, palace)
    assert not small["placement_classical_acceptance"]
    assert "not_source_adjudicated" in small["year_boundary_basis"]
    assert len(g["rule_trace"]) == 16
    assert (
        sum(
            t["rule_id"] == "moira_compatibility_conditions_v2" for t in g["rule_trace"]
        )
        == 1
    )
    trace = g["rule_trace"][-1]
    assert trace["rule_id"] == "source_small_limit_reverse_count"
    assert trace["outputs"]["small_limit_branch"] == limit
    assert trace["source_id"] == source["edition_id"]
    text = result["interpretation"]["timing"]
    assert f"小限在{limit}，对应本命{palace}" in text
    assert f"{stem}{year_branch}年" in text
    assert "目标时刻小限与十一曜研究位置" in result["snapshot_text"]
    assert "full_marks_established" in g["validation"]
    assert not g["validation"]["full_marks_established"]


def test_declared_lichun_policy_on_each_side_of_independent_hko_minute():
    # HKO's retained raw XML replaces the retired duplicate JSON transcription.
    raw = (
        Path(__file__).parents[1] / "fixtures/calendar_hko_v1/24SolarTerms_2026.xml"
    ).read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "3af98679f43d4d689941c55ba2a19f146ff111a6dff681235dc2b7110974ac74"
    )
    assert b"<Data><M>02</M><D>04</D><hm>04:02</hm></Data>" in raw
    instant = datetime.fromisoformat("2026-02-04T04:02:00+08:00")
    before = chart(analysis_datetime=instant - timedelta(minutes=3))
    after = chart(analysis_datetime=instant + timedelta(minutes=3))
    a, b = (x["guolao"]["timing"]["small_limit"] for x in (before, after))
    assert (a["target_year_stem"], a["target_year_branch"], a["branch"]) == (
        "乙",
        "巳",
        "酉",
    )
    assert (b["target_year_stem"], b["target_year_branch"], b["branch"]) == (
        "丙",
        "午",
        "申",
    )


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_equivalent_target_offsets_and_solar_display_preserve_target_sky(zodiacal):
    a = chart(analysis_datetime=TARGET, zodiacal=zodiacal, birth_longitude=75)
    b = chart(
        analysis_datetime=TARGET.astimezone(timezone.utc),
        zodiacal=zodiacal,
        birth_longitude=75,
    )
    assert a["guolao"]["timing"] == b["guolao"]["timing"]
    solar = chart(
        analysis_datetime=TARGET,
        zodiacal=zodiacal,
        birth_longitude=75,
        use_true_solar_time=True,
    )
    assert (
        a["guolao"]["life_palace"]["branch"] != solar["guolao"]["life_palace"]["branch"]
    )
    for key in ("mansion_boundaries", "profile"):
        assert a["guolao"]["timing"][key] == solar["guolao"]["timing"][key]

    # A different natal life branch legitimately changes the *natal* palace label.
    def sky(result):
        return [
            {k: v for k, v in row.items() if k != "natal_functional_palace"}
            for row in result["guolao"]["timing"]["transit_bodies"]
        ]

    assert sky(a) == sky(solar)
    moved = chart(
        analysis_datetime=TARGET,
        zodiacal=zodiacal,
        birth_longitude=-73.9,
        birth_latitude=40.7,
        birth_timezone="America/New_York",
    )
    assert sky(a) == sky(moved)


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_target_uses_geocentric_layer_without_observer_geometry(monkeypatch, zodiacal):
    birth = build_astro_birth_info(
        **{k: v for k, v in astro_payload().items() if k != "name"}
    )
    result = chart(zodiacal=zodiacal)

    def forbidden(*args, **kwargs):
        pytest.fail("a target geocentric sky must not calculate observer angles/houses")

    monkeypatch.setattr(guolao.runtime.swe, "houses_ex", forbidden)
    monkeypatch.setattr(guolao.runtime.swe, "azalt", forbidden)
    monkeypatch.setattr(guolao, "reference_geometry", forbidden)
    guolao_timing.enrich_guolao_timing(result, birth, TARGET, zodiacal=zodiacal)
    assert len(result["guolao"]["timing"]["transit_bodies"]) == 11


def test_no_target_is_not_the_present_and_target_does_not_mutate_natal(monkeypatch):
    natal = chart()
    target = chart(analysis_datetime=TARGET)
    assert natal["guolao"]["timing"] == {"status": "not_requested"}
    assert len(natal["guolao"]["rule_trace"]) == 15
    assert (
        sum(
            t["rule_id"] == "moira_compatibility_conditions_v2"
            for t in natal["guolao"]["rule_trace"]
        )
        == 1
    )
    for key in (
        "bodies",
        "life_palace",
        "palaces",
        "profile",
        "god_positions",
        "conditions",
        "mansion_boundaries",
        "purple_model_audit",
        "validation",
    ):
        assert natal["guolao"][key] == target["guolao"][key]
    assert natal["guolao"]["rule_trace"] == target["guolao"]["rule_trace"][:-1]
    for key in ("person_info", "planets", "houses", "angles"):
        assert natal[key] == target[key]
    for key, value in natal["interpretation"].items():
        assert target["interpretation"][key] == value
    birth = build_astro_birth_info(
        **{k: v for k, v in astro_payload().items() if k != "name"}
    )
    unchanged = copy.deepcopy(natal)
    monkeypatch.setattr(
        guolao, "positions", lambda *a, **k: pytest.fail("no target supplied")
    )
    guolao_timing.enrich_guolao_timing(natal, birth, None)
    assert natal == unchanged


@pytest.mark.parametrize("instant", ["2027-01-01T00:00:00", "not-a-date"])
def test_target_contract_requires_explicit_offset(instant):
    for model, extra in [
        (AstroGuolaoRequest, {}),
        (AstroChartPolyRequest, {"chart_variant": "guolao_chart"}),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(
                {**astro_payload(), **extra, "analysis_datetime": instant}
            )


@pytest.mark.parametrize(
    "instant",
    [datetime(2027, 1, 1), datetime(1990, 4, 6, 1, 32, 59, tzinfo=timezone.utc)],
)
def test_direct_domain_rejects_naive_or_prebirth_targets(instant):
    birth = build_astro_birth_info(
        **{k: v for k, v in astro_payload().items() if k != "name"}
    )
    with pytest.raises(ValueError):
        guolao_timing.enrich_guolao_timing(chart(), birth, instant)


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_exact_birth_target_reproduces_sky_and_does_not_invent_age_offset(zodiacal):
    natal = chart(zodiacal=zodiacal)
    target = chart(
        zodiacal=zodiacal,
        analysis_datetime=datetime.fromisoformat(natal["person_info"]["utc_datetime"]),
    )
    t = target["guolao"]["timing"]
    assert t["small_limit"]["branch"] == natal["guolao"]["life_palace"]["branch"]
    assert [
        {k: v for k, v in b.items() if k != "natal_functional_palace"}
        for b in t["transit_bodies"]
    ] == natal["guolao"]["bodies"]
    assert t["mansion_boundaries"] == natal["guolao"]["mansion_boundaries"]


def test_repeated_local_dst_hour_keeps_explicit_target_instant():
    # Both instants have a legitimate 01:30 New York clock, with different offsets.
    results = [
        chart(
            birth_timezone="America/New_York",
            analysis_datetime=datetime.fromisoformat(t),
        )
        for t in ("2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00")
    ]
    timing = [r["guolao"]["timing"] for r in results]
    assert timing[0]["calendar_datetime"].endswith("-04:00")
    assert timing[1]["calendar_datetime"].endswith("-05:00")
    assert timing[0]["transit_bodies"] != timing[1]["transit_bodies"]


def test_target_seven_bodies_against_21_external_nasa_positions():
    fixture = json.loads((FIXTURES / "jyotish-horizons.json").read_text())
    cache = {}
    errors = []
    for reference in fixture["references"]:
        assert (
            hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
            == reference["response_sha256"]
        )
        for row in reference["rows"]:
            if row["utc"] not in cache:
                result = chart(
                    birth_year=1980,
                    analysis_datetime=datetime.fromisoformat(row["utc"]),
                )
                cache[row["utc"]] = {
                    b["id"]: b for b in result["guolao"]["timing"]["transit_bodies"]
                }
            body = cache[row["utc"]][reference["body"]]
            errors.append(
                abs(
                    (body["longitude"] - row["apparent_ecliptic_longitude"] + 180) % 360
                    - 180
                )
                * 3600
            )
    assert len(errors) == 21
    assert (
        max(errors) < 2.0
    )  # Same predeclared model tolerance, not a new efficacy score.
