"""Compute determined magnitudes without inventing unresolved strength signs.

Raman76-77's magnitude formula is independent of which planet receives it.
Cheshta controls here are mathematical operands, not observed natal positions.
"""

import asyncio
import copy
import json
import math
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.jyotish import jyotish_mean
from fatebridge.core.jyotish.jyotish_balas import PLANETS, moon_nature_readings
from fatebridge.core.jyotish.jyotish_evidence import cheshta_ruler_provenance
from fatebridge.core.jyotish.jyotish_motion import cheshta_arc
from fatebridge.core.jyotish.jyotish_sthana import drekkana
from fatebridge.core.jyotish.jyotish_strength import SOURCE_ID
from fatebridge.core.jyotish.jyotish_war import STARS, THROUGH_HORA, war_bala
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import (
    AS_OF,
    SPECS,
    cached_mcp_app,
    call_calculation,
    three_surfaces,
)


def call_surfaces(monkeypatch, capsys, key, payload, fields):
    spec = SPECS[key]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client, spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    protocol_result = asyncio.run(protocol())
    native = protocol_result.structured_content
    args = [spec.tool_name]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            *([str(x) for x in value] if isinstance(value, list) else [str(value)]),
        ]
    args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol_result.is_error, native
    assert code == 0, cli
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    return response.json()


DISCS = {
    "Mars": "9.4",
    "Mercury": "6.6",
    "Jupiter": "190.4",
    "Venus": "16.6",
    "Saturn": "158.0",
}


def war_inputs():
    longitudes = dict(zip(PLANETS, [200, 250, 30, 80, 130, 180, 230]))
    components = {key: {"summary": dict.fromkeys(PLANETS, 0.0)} for key in THROUGH_HORA}
    sthana = {
        "profile": {"id": "independent_hand_operands"},
        "summary": {p: {"total_virupa": 0.0} for p in PLANETS},
    }
    dig = {
        "source_id": "independent_hand_operands",
        "summary": dict.fromkeys(PLANETS, 0.0),
    }
    return longitudes, components, sthana, dig


def test_unknown_pair_winner_does_not_erase_the_determined_raman_magnitude() -> None:
    for a, b in combinations(STARS, 2):
        for positions in [(120.0, 120.0), (359.75, 0.25)]:
            longitudes, components, sthana, dig = war_inputs()
            # Move all uninvolved stars away from the artificial selected pair.
            for index, planet in enumerate(p for p in STARS if p not in [a, b]):
                longitudes[planet] = 30.0 + 60 * index
            longitudes[a], longitudes[b] = positions
            sthana["summary"][a]["total_virupa"] = 200.0
            sthana["summary"][b]["total_virupa"] = 100.0
            value = war_bala(
                longitudes,
                components,
                {"fixed": components["paksha_bala"]["summary"]},
                sthana,
                dig,
            )
            pair = value["evidence"]["fixed"]["pairs"][0]
            expected = float(
                Fraction(100) / abs(Fraction(DISCS[a]) - Fraction(DISCS[b]))
            )
            assert pair["amount_virupa"] == expected
            assert pair["winner"] is None
            assert value["summary"][a] is value["summary"][b] is None
            assert value["status"] == "partial_unadjudicated_pairs"
            assert set(value["unresolved_planets"]) == {a, b}


def test_zero_magnitude_is_known_without_creating_a_signed_zero_award() -> None:
    l, c, s, d = war_inputs()
    l.update(Mars=359.75, Venus=0.25)
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert value["evidence"]["fixed"]["pairs"][0]["amount_virupa"] == 0
    assert value["summary"]["Mars"] is value["summary"]["Venus"] is None


def test_missing_prewar_input_keeps_even_the_pair_magnitude_unknown() -> None:
    l, c, s, d = war_inputs()
    l.update(Mars=359.75, Venus=0.25)
    d["summary"]["Mars"] = None
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert value["evidence"]["fixed"]["pairs"][0]["amount_virupa"] is None


def test_simultaneous_three_star_war_does_not_acquire_unregistered_pair_magnitudes() -> (
    None
):
    l, c, s, d = war_inputs()
    l.update(Mars=120, Venus=120.25, Mercury=120.5)
    s["summary"]["Mars"]["total_virupa"] = 200.0
    value = war_bala(l, c, {"fixed": c["paksha_bala"]["summary"]}, s, d)
    assert len(value["pairs"]) == 3
    assert all(
        row["amount_virupa"] is None for row in value["evidence"]["fixed"]["pairs"]
    )


def test_cheshta_opposed_midpoints_keep_a_unique_exact_strength() -> None:
    # The two opposite midpoints are each 90deg from either original endpoint.
    expected = float(Fraction(90, 3))
    for rotation in range(0, 360, 30):
        for apogee_offset in (0, 180):
            value = cheshta_arc(
                rotation,
                rotation + 180,
                rotation + apogee_offset,
                mean_frame="controlled_same_frame",
                true_frame="controlled_same_frame",
                seeghrochcha_frame="controlled_same_frame",
            )
            assert value["value"] == expected == 30
            assert value["status"] == "opposed_midpoint_not_adjudicated"
            assert len(value["branches"]) == 2
            assert all(branch["virupa"] == expected for branch in value["branches"])


def test_cheshta_display_rounding_cannot_turn_distinct_exact_branches_into_consensus() -> (
    None
):
    value = cheshta_arc(
        0,
        180,
        math.nextafter(0.0, 1.0),
        mean_frame="controlled_same_frame",
        true_frame="controlled_same_frame",
        seeghrochcha_frame="controlled_same_frame",
    )
    assert [branch["virupa"] for branch in value["branches"]] == [30.0, 30.0]
    assert value["value"] is None


@pytest.fixture
def controlled_opposed_component(monkeypatch):
    # Isolate the angular/source receipt contract. These are artificial model
    # operands, not a claim that Simon1994 or a real birth produces this sky.
    def component(apogee):
        means = {"Sun": apogee, "Mars": 0.0}
        monkeypatch.setattr(jyotish_mean, "mean_longitudes", lambda jd: means)
        arc = cheshta_arc(
            0.0,
            180.0,
            apogee,
            mean_frame=jyotish_mean.FRAME,
            true_frame=jyotish_mean.FRAME,
            seeghrochcha_frame=jyotish_mean.FRAME,
        )
        return {
            "source_id": SOURCE_ID,
            "scenarios": {"controlled": {"Mars": arc["value"]}},
            "model_context": {
                "selected": jyotish_mean.MODEL,
                "status": "computed_declared_secular_model",
                "source_id": jyotish_mean.SOURCE["id"],
                "frame": jyotish_mean.FRAME,
                "julian_day_tt": 2451545.0,
                "mean_longitudes": means,
                "true_position_provenance": {
                    "Mars": {
                        "longitude": 180.0,
                        "frame": jyotish_mean.FRAME,
                        "ephemeris_model": "controlled_geometric_operand",
                    }
                },
                "planet_evidence": {
                    "Mars": {
                        "mean_longitude": 0.0,
                        "true_longitude": 180.0,
                        "seeghrochcha": apogee,
                        "arc": arc,
                    }
                },
            },
        }

    return component


def test_same_run_source_receipt_accepts_only_the_exact_opposed_consensus(
    controlled_opposed_component,
) -> None:
    component = controlled_opposed_component(0.0)
    receipt = cheshta_ruler_provenance("Mars", component, {})
    assert component["scenarios"]["controlled"]["Mars"] == 30
    assert receipt["method_context"]["calculation_status"] == (
        "opposed_midpoint_not_adjudicated"
    )
    assert receipt["method_context"]["five_star_mean_model_applied"] is True


@pytest.mark.parametrize("apogee", [100.0, math.nextafter(0.0, 1.0)])
def test_same_run_source_receipt_rejects_fabricated_opposed_consensus(
    controlled_opposed_component, apogee
) -> None:
    component = controlled_opposed_component(apogee)
    assert component["scenarios"]["controlled"]["Mars"] is None
    # Keep the correct ambiguous branches but fabricate a common scalar.
    component["model_context"]["planet_evidence"]["Mars"]["arc"]["value"] = 30.0
    component["scenarios"]["controlled"]["Mars"] = 30.0
    with pytest.raises(ValueError, match="mean/geometry/arc chain"):
        cheshta_ruler_provenance("Mars", component, {})


@pytest.mark.parametrize("field", ["mean_longitude", "true_longitude", "seeghrochcha"])
def test_same_run_consensus_receipt_rejects_forged_angular_operands(
    controlled_opposed_component, field: str
) -> None:
    component = copy.deepcopy(controlled_opposed_component(0.0))
    component["model_context"]["planet_evidence"]["Mars"][field] += 1.0
    with pytest.raises(ValueError, match="mean/geometry/arc chain"):
        cheshta_ruler_provenance("Mars", component, {})


def test_actual_1977_origin_pair_magnitude_reaches_three_surfaces_without_a_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions

    payload = dict(
        birth_year=1977,
        birth_month=5,
        birth_day=29,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        saptavargaja_profile="raman_30",
        drekkana_profile="raman_36",
        divisions=[9],
    )
    india_surfaces = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        payload,
        [
            "india.strengths.kala_bala.components.yuddha_bala",
            "india.strengths.shadbala_assessment",
            "india.profile.saptavargaja_profile",
            "india.profile.drekkana_profile",
        ],
    )
    vimshottari_spec = SPECS["astro_vimshottari"]
    vimshottari_direct = execute_tool(
        vimshottari_spec,
        vimshottari_spec.request_model.model_validate(payload),
        options=ExecutionOptions(as_of=AS_OF),
    )
    for value in (india_surfaces, vimshottari_direct):
        india = value["india"]
        war = india["strengths"]["kala_bala"]["components"]["yuddha_bala"]
        assert india["profile"]["saptavargaja_profile"] == "raman_30"
        assert india["profile"]["drekkana_profile"] == "raman_36"
        assert war["pairs"][0]["planets"] == ["Mars", "Venus"]
        assert war["pairs"][0]["winner"] is None
        assert war["status"] == "partial_unadjudicated_pairs"
        assert war["summary"]["Mars"] is war["summary"]["Venus"] is None
        for branch in war["evidence"].values():
            inputs = branch["prewar_basis"]
            totals = []
            for p in ("Mars", "Venus"):
                basis = inputs[p]
                exact_inputs = basis["exact_inputs_virupa"]
                assert {
                    key: None if amount is None else float(Fraction(amount))
                    for key, amount in exact_inputs.items()
                } == basis["inputs"]
                totals.append(
                    sum((Fraction(v) for v in exact_inputs.values()), Fraction())
                )
            assert branch["pairs"][0]["amount_virupa"] == float(
                abs(totals[0] - totals[1]) / Fraction("7.2")
            )
        assert india["strengths"]["shadbala_assessment"]["total_virupa"] is None


@pytest.mark.parametrize(
    "elongation_degrees,waxing_natures,eighth_day_natures",
    [
        (0, ["benefic", "malefic"], ["malefic"]),
        (83, ["benefic"], ["malefic"]),
        (84, ["benefic"], ["benefic", "malefic"]),
        (96, ["benefic"], ["benefic"]),
        (180, ["benefic", "malefic"], ["benefic"]),
        (263, ["malefic"], ["benefic"]),
        (264, ["malefic"], ["benefic", "malefic"]),
        (276, ["malefic"], ["malefic"]),
    ],
)
def test_named_moon_readings_keep_disagreement_and_eighth_tithi_endpoints(
    elongation_degrees: int,
    waxing_natures: list[str],
    eighth_day_natures: list[str],
) -> None:
    readings = moon_nature_readings(Fraction(elongation_degrees))
    assert readings["readings"] == {
        "raman_117_118_waxing_waning": waxing_natures,
        "raman_53_eighth_day_window": eighth_day_natures,
    }
    assert set(readings["options"]) == set(waxing_natures + eighth_day_natures)


@pytest.mark.parametrize(
    "planet,longitude_degrees,santhanam_virupa,raman_virupa",
    [
        ("Sun", 9.0, 15, 15),
        ("Sun", 10.0, 0, 0),
        ("Moon", 10.0, 15, 0),
        ("Moon", 20.0, 0, 15),
        ("Mercury", 10.0, 0, 15),
        ("Mercury", 20.0, 15, 0),
        ("Venus", 19.0, 15, 0),
        ("Saturn", 29.0, 15, 0),
    ],
)
def test_drekkana_uses_named_d1_groups_and_detailed_fifteen_virupa(
    planet: str,
    longitude_degrees: float,
    santhanam_virupa: int,
    raman_virupa: int,
) -> None:
    assert drekkana(longitude_degrees, planet, "santhanam_27_6")["value"] == (
        santhanam_virupa
    )
    assert drekkana(longitude_degrees, planet, "raman_36")["value"] == raman_virupa


@pytest.mark.parametrize("mean_model", ["unadjudicated", "simon1994_j2000"])
def test_named_strength_sources_and_partial_facts_on_actual_public_chart(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    mean_model: str,
) -> None:
    payload = {
        "birth_year": 2023,
        "birth_month": 3,
        "birth_day": 2,
        "birth_hour": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
        "birth_time_uncertainty_minutes": 0,
        "divisions": [],
        "saptavargaja_profile": "raman_30",
        "drekkana_profile": "raman_36",
        "cheshta_model": mean_model,
    }
    result = three_surfaces(
        SPECS["astro_india"],
        payload,
        ["india.charts.D1", "india.strengths", "india.rulesets"],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )["india"]
    strengths = result["strengths"]
    sources = {source["id"]: source for source in result["rulesets"]}
    assert "R. Santhanam" in sources[SOURCE_ID]["title"]
    positional = strengths["sthana_bala"]
    conflict = positional["source_reading_conflicts"][0]
    assert (conflict["detailed_value_virupa"], conflict["summary_value_virupa"]) == (
        15,
        60,
    )
    assert conflict["applies_to_selected_profile"] is True
    assert conflict["whole_book_acceptance"] is False
    assert positional["profile"]["id"] == "raman_30"
    assert positional["profile"]["drekkana_profile"]["id"] == "raman_36"
    aspect = strengths["drik_bala"]
    assert aspect["nature_context"]["mercury_status"] == (
        "association_predicate_not_adjudicated"
    )
    assert aspect["source_witness"]["complete_single_original_accepted"] is False
    assert aspect["source_id"] == "raman_graha_bhava_balas_section30_preview"
    assert (
        sources[aspect["source_id"]]["title"]
        == "B.V. Raman, Graha and Bhava Balas (selected sections)"
    )
    for branch in aspect["scenarios"].values():
        assert branch["natures"]["Mercury"] in {"benefic", "malefic"}
    temporal = strengths["kala_bala"]["components"]
    motion = strengths["cheshta_bala"]
    for branch_name, branch in motion["scenarios"].items():
        assert branch["Sun"] == temporal["ayana_bala"]["summary"]["Sun"]
        assert (
            branch["Moon"] == temporal["paksha_bala"]["scenarios"][branch_name]["Moon"]
        )
    model = motion["model_context"]
    assert model["selected"] == mean_model
    if mean_model == "unadjudicated":
        assert model["status"] == "mean_model_unadjudicated"
        assert motion["missing_planets"] == list(STARS)
        assert all(motion["summary"][planet] is None for planet in STARS)
    else:
        assert model["status"] == "computed_declared_secular_model"
        assert model["source_id"] == "simon1994_mean_j2000_1730fe5b"
        assert "Simon et al.(1994)" in sources[model["source_id"]]["title"]
        assert model["frame"] == "mean_dynamical_ecliptic_equinox_J2000"
        assert motion["missing_planets"] == []
        for planet, evidence in model["planet_evidence"].items():
            mean_body, apogee_body = (
                ("Sun", planet) if planet in {"Mercury", "Venus"} else (planet, "Sun")
            )
            assert evidence["mean_longitude"] == model["mean_longitudes"][mean_body]
            assert evidence["seeghrochcha"] == model["mean_longitudes"][apogee_body]
            assert (
                evidence["true_longitude"]
                == model["true_position_provenance"][planet]["longitude"]
            )
            assert model["true_position_provenance"][planet]["frame"] == model["frame"]
            # note (FateBridge): Unwrap around the true position to independently check the circular midpoint.
            true_degrees = Fraction(evidence["true_longitude"])
            mean_degrees = Fraction(evidence["mean_longitude"])
            turns = (-360, 0, 360)
            unwrapped_mean_degrees = min(
                (mean_degrees + turn for turn in turns),
                key=lambda candidate: abs(candidate - true_degrees),
            )
            midpoint_degrees = (unwrapped_mean_degrees + true_degrees) / 2
            apogee_degrees = Fraction(evidence["seeghrochcha"])
            distance_degrees = min(
                abs(apogee_degrees + turn - midpoint_degrees) for turn in turns
            )
            assert motion["summary"][planet] == float(distance_degrees / 3)
    war = temporal["yuddha_bala"]
    assert [pair["planets"] for pair in war["pairs"]] == [
        ["Mercury", "Saturn"],
        ["Jupiter", "Venus"],
    ]
    assert war["upstream_profile"]["sthana"]["id"] == "raman_30"
    for branch in war["evidence"].values():
        assert branch["pairs"][1]["fixed_disc_difference_arcseconds"] == 173.8
        assert branch["pairs"][1]["winner"] == "Venus"
        totals_virupa = []
        for planet in ("Jupiter", "Venus"):
            basis = branch["prewar_basis"][planet]
            assert set(basis["inputs"]) == {"sthana_bala", "dig_bala", *THROUGH_HORA}
            totals_virupa.append(
                sum(map(Fraction, basis["exact_inputs_virupa"].values()), Fraction())
            )
        assert branch["pairs"][1]["amount_virupa"] == float(
            abs(totals_virupa[0] - totals_virupa[1]) / Fraction("173.8")
        )
    assert strengths["shadbala_assessment"]["status"] == "not_complete"
    assert strengths["shadbala_assessment"]["total_virupa"] is None
