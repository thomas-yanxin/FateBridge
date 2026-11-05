"""Frozen independent ERFA sky positions, frame fidelity and failure semantics."""

import hashlib
import json
import math
import os
from pathlib import Path

import pytest

from fatebridge.core import fixed_stars
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.classical_western import FIXED_STARS
from fatebridge.core.ephemeris_runtime import preserve_ephemeris_path, swe
from fatebridge.services.astrology import (
    _build_fixed_stars_lines,
    calculate_core_chart_analysis,
)
from tests.western.test_western_accuracy import BIRTH

FIXTURES = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURES / "western-fixed-stars-erfa.json").read_text())
PROTOCOL = json.loads((FIXTURES / "western-fixed-star-protocol.json").read_text())


def test_reference_inputs_have_not_been_replaced_with_runtime_answers():
    assert (
        hashlib.sha256((fixed_stars.DATA / "sources.json").read_bytes()).hexdigest()
        == REFERENCE["source_sha256"]
    )
    assert (
        hashlib.sha256(
            (FIXTURES / "western-fixed-star-protocol.json").read_bytes()
        ).hexdigest()
        == REFERENCE["protocol_sha256"]
    )
    assert len(REFERENCE["rows"]) == 120
    assert PROTOCOL["tolerance_arcsec"] == 1.0


@pytest.mark.parametrize("epoch", PROTOCOL["epochs_tt"])
def test_twenty_stars_at_each_declared_epoch_match_independent_erfa(epoch):
    rows = [r for r in REFERENCE["rows"] if r["epoch_tt"] == epoch]
    positions, profile = fixed_stars.apparent_positions(rows[0]["julian_day_tt"])
    assert profile["status"] == "computed"
    assert set(positions) == {r["star"] for r in rows}
    for row in rows:
        actual = positions[row["star"]]
        error = abs((actual["longitude"] - row["longitude"] + 180) % 360 - 180) * 3600
        assert error <= PROTOCOL["tolerance_arcsec"], row
        assert (
            abs(actual["latitude"] - row["latitude"]) * 3600
            <= PROTOCOL["tolerance_arcsec"]
        ), row


def test_lahiri_stars_and_native_planets_share_the_same_frame():
    tropical, _ = fixed_stars.apparent_positions(2451545)
    sidereal, profile = fixed_stars.apparent_positions(2451545, sidereal=True)
    with preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        _, offset = runtime.ephemeris_call("get_ayanamsa_ex", 2451545, swe.FLG_SWIEPH)
    assert profile["longitude_frame"] == "sidereal_lahiri"
    for name in tropical:
        expected = (tropical[name]["longitude"] - offset) % 360
        assert abs((sidereal[name]["longitude"] - expected + 180) % 360 - 180) < 1e-8
    birth = build_astro_birth_info(
        **{
            **BIRTH,
            "birth_year": 2000,
            "birth_month": 12,
            "birth_day": 10,
            "birth_hour": 1,
            "birth_minute": 55,
            "birth_longitude": 120.4667,
            "birth_latitude": 32.5417,
        }
    )
    charts = [
        build_core_chart_payload(birth, "hellen_chart", zodiacal=z) for z in (0, 1)
    ]
    contacts = [
        {(r["star"], r["point"]): r["orb"] for r in p["fixed_stars"]} for p in charts
    ]
    assert contacts[0].keys() == contacts[1].keys()
    assert ("Antares", "Mercury") in contacts[0]
    for pair in contacts[0]:
        assert contacts[0][pair] == pytest.approx(contacts[1][pair], abs=1e-8)
    # Moving all factors to another origin must not change physical contact membership.
    assert (
        charts[1]["chart_profile"]["fixed_stars"]["longitude_frame"]
        == "sidereal_lahiri"
    )


@pytest.mark.parametrize(
    "value,included",
    [
        (math.nextafter(1.0, 0), True),
        (1.0, True),
        (math.nextafter(1.0, math.inf), False),
    ],
)
def test_unrounded_longitude_contact_boundary(value, included):
    position = {
        "Spica": {
            "longitude": 0.0,
            "latitude": 40.0,
            "source_url": "source",
            "identifier": "test",
        }
    }
    hits = fixed_stars.conjunction_hits({"Sun": value}, position, FIXED_STARS)
    assert bool(hits) is included
    if hits:
        assert hits[0]["orb"] == value
        # This traditional contact uses longitude only, not angular separation.
        assert hits[0]["star_latitude"] == 40


@pytest.mark.parametrize(
    "offset,included",
    [
        (math.nextafter(0.5, 0), True),
        (0.5, True),
        (math.nextafter(0.5, math.inf), False),
    ],
)
@pytest.mark.parametrize("swap", [False, True])
def test_wrap_boundary_retains_residual_erased_by_two_float_subtractions(
    offset, included, swap
):
    star, point = (offset, 359.5) if not swap else (359.5, offset)
    position = {
        "Spica": {
            "longitude": star,
            "latitude": 0.0,
            "source_url": "source",
            "identifier": "test",
        }
    }
    assert (
        bool(fixed_stars.conjunction_hits({"Sun": point}, position, FIXED_STARS))
        is included
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_invalid_star_time_cannot_become_an_empty_success(value):
    with pytest.raises(ValueError, match="finite"):
        fixed_stars.apparent_positions(value)


@pytest.mark.parametrize("value", [math.nan, math.inf, -1, 181])
def test_invalid_orb_cannot_become_an_empty_success(value):
    with pytest.raises(ValueError, match="orb"):
        fixed_stars.conjunction_hits({}, {}, FIXED_STARS, orb=value)


def test_catalogue_fingerprint_mismatch_is_explicit(monkeypatch, tmp_path):
    (tmp_path / "sources.json").write_bytes(
        (fixed_stars.DATA / "sources.json").read_bytes()
    )
    (tmp_path / "sefstars.txt").write_text("corrupt catalogue")
    monkeypatch.setattr(fixed_stars, "DATA", tmp_path)
    with pytest.raises(ValueError, match="source receipt"):
        fixed_stars.apparent_positions(2451545)


def test_unavailable_star_layer_is_rendered_as_uncomputed(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    hits, profile = fixed_stars.build_layer({}, 2451545, FIXED_STARS)
    assert hits == [] and profile["status"] == "unavailable"
    text = _build_fixed_stars_lines(
        {"fixed_stars": hits, "chart_profile": {"fixed_stars": profile}}
    )
    assert "未计算" in text and "不表示没有" in text and text != "无"


def test_catalogue_selection_survives_prior_cache_and_restores_operator_path(
    monkeypatch, tmp_path
):
    # The C library ignores set_ephe_path when this override is nonempty.
    # Clear it only for the deliberate prior-catalogue cache setup below.
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    alternate = fixed_stars.DATA.parent / "guolao"
    with preserve_ephemeris_path():
        swe.close()
        swe.set_ephe_path(str(alternate))
        swe.fixstar2("FBJ00", 2451545, swe.FLG_MOSEPH)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    positions, profile = fixed_stars.apparent_positions(2451545)
    assert profile["status"] == "computed" and len(positions) == 20
    assert os.environ["SE_EPHE_PATH"] == str(tmp_path)
    assert profile["earth_ephemeris_model"] == "moshier"
    # The nominal fixed-star SWIEPH flag is not promoted to Earth model proof.
    assert profile["native_flags"] == [swe.FLG_SWIEPH]
    with preserve_ephemeris_path():
        saved = os.environ.pop("SE_EPHE_PATH")
        try:
            swe.set_ephe_path(str(alternate))
            _, name, _ = swe.fixstar2("FBJ00", 2451545, swe.FLG_MOSEPH)
            assert name.startswith("FBJ00,")
        finally:
            swe.close()
            os.environ["SE_EPHE_PATH"] = saved


def test_native_error_does_not_leak_environment_or_fabricate_absence(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))

    def fail(*args):
        raise swe.Error("synthetic star error")

    monkeypatch.setattr(swe, "fixstar2", fail)
    positions, profile = fixed_stars.apparent_positions(2451545)
    assert not positions and profile["status"] == "unavailable"
    assert os.environ["SE_EPHE_PATH"] == str(tmp_path)


def test_pleiades_original_text_nature_is_not_the_praesepe_nature():
    # Robbins 1940 I.9 explicitly gives the Pleiades Moon and Jupiter;
    # the Cancer cloud (Praesepe) is Mars and Moon.
    assert FIXED_STARS["Alcyone"]["nature"] == ["Moon", "Jupiter"]


def test_source_degree_qualifiers_are_preserved_without_numeric_weights():
    rules = fixed_stars.nature_rules()
    assert len(rules["stars"]) == 20
    assert rules["stars"]["Spica"]["components"] == [
        {"planet": "Venus", "qualifier": "unqualified"},
        {"planet": "Mars", "qualifier": "lesser_degree"},
    ]
    assert rules["stars"]["Antares"]["components"][-1] == {
        "planet": "Jupiter",
        "qualifier": "some_degree",
    }
    positions, _ = fixed_stars.apparent_positions(2451545)
    hit = fixed_stars.conjunction_hits(
        {"Sun": positions["Spica"]["longitude"]},
        {"Spica": positions["Spica"]},
        FIXED_STARS,
    )[0]
    assert hit["nature_components"] == rules["stars"]["Spica"]["components"]
    text = _build_fixed_stars_lines({"fixed_stars": [hit]})
    assert "金星/火星（较轻程度）" in text


def test_clock_and_frame_provenance_reach_the_readable_export():
    result = calculate_core_chart_analysis(**BIRTH, chart_variant="hellen_chart")
    profile = result["chart_profile"]["fixed_stars"]
    assert profile["julian_day_tt"] == result["chart_profile"]["julian_day_tt"]
    assert profile["note_zh"] in result["snapshot_text"]
    assert profile["note_zh"] in result["summary"]
