"""Independent table cases, cusp probes, provenance and fact/prose linkage."""

import math
from datetime import timedelta

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_strength import degree_condition
from tests.fixtures.surface_payloads import astro_payload


@pytest.mark.parametrize(
    "planet,peak,fall",
    [
        ("Sun", 10, 190),
        ("Moon", 33, 213),
        ("Mars", 298, 118),
        ("Mercury", 165, 345),
        ("Jupiter", 95, 275),
        ("Venus", 357, 177),
        ("Saturn", 200, 20),
    ],
)
def test_bphs_3_49_50_and_27_1_independent_peak_and_quadrature_table(
    planet, peak, fall
):
    # Hand-transcribed source table; not imported from production PEAKS.
    assert degree_condition(planet, peak)["uchcha_bala"]["value"] == 60
    assert degree_condition(planet, fall)["uchcha_bala"]["value"] == 0
    assert degree_condition(planet, fall + 90)["uchcha_bala"]["value"] == 30
    assert degree_condition(planet, fall - 90)["uchcha_bala"]["value"] == 30
    for longitude in range(360):
        value = degree_condition(planet, longitude)["uchcha_bala"]["value"]
        assert 0 <= value <= 60
        assert (
            degree_condition(planet, longitude + 360)["uchcha_bala"]["value"] == value
        )


@pytest.mark.parametrize(
    "planet,start,end",
    [
        ("Sun", 120, 140),
        ("Moon", 33, 60),
        ("Mars", 0, 12),
        ("Mercury", 165, 170),
        ("Jupiter", 240, 250),
        ("Venus", 180, 195),
        ("Saturn", 300, 320),
    ],
)
def test_bphs_3_51_54_moolatrikona_has_explicit_half_open_boundaries(
    planet, start, end
):
    assert degree_condition(planet, start)["degree_zone"] == "moolatrikona"
    assert (
        degree_condition(planet, math.nextafter(end, -math.inf))["degree_zone"]
        == "moolatrikona"
    )
    assert degree_condition(planet, end)["degree_zone"] != "moolatrikona"
    assert (
        degree_condition(planet, math.nextafter(start, -math.inf))["degree_zone"]
        != "moolatrikona"
    )


def test_mercury_peak_and_zone_are_distinct_and_not_collapsed_to_one_rank():
    before = degree_condition("Mercury", math.nextafter(165, -math.inf))
    at = degree_condition("Mercury", 165)
    assert before["degree_zone"] == "exaltation_portion"
    assert at["degree_zone"] == "moolatrikona"
    assert at["uchcha_bala"]["value"] == 60
    assert degree_condition("Mercury", 170)["degree_zone"] == "own_sign_portion"


@pytest.mark.parametrize(
    "sign,states",
    [
        (0, ["bala", "kumara", "yuva", "vriddha", "mrita"]),
        (1, ["mrita", "vriddha", "yuva", "kumara", "bala"]),
    ],
)
def test_bphs_45_3_baladi_odd_even_order_and_each_six_degree_boundary(sign, states):
    for part, state in enumerate(states):
        boundary = sign * 30 + part * 6
        assert degree_condition("Sun", boundary)["baladi_avastha"]["state"] == state
        if part:
            assert (
                degree_condition("Sun", math.nextafter(boundary, -math.inf))[
                    "baladi_avastha"
                ]["state"]
                == states[part - 1]
            )


@pytest.mark.parametrize(
    "planet,longitude", [("Rahu", 20), ("Ketu", 20), ("Sun", float("nan"))]
)
def test_unregistered_node_doctrines_and_nonfinite_angles_are_rejected(
    planet, longitude
):
    with pytest.raises(ValueError):
        degree_condition(planet, longitude)


@pytest.mark.native_engine_fault
def test_actual_backend_is_per_body_and_strict_policy_rejects_empty_data_path(
    monkeypatch, tmp_path
):
    from fatebridge.core import ephemeris_runtime

    # Set the actual shared native configuration, not one module's imported
    # alias; managed calls reapply this path before touching the C library.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    ephemeris_runtime.configure_ephemeris_path(str(tmp_path))
    birth = build_astro_birth_info(**astro_payload())
    auto = positions(birth)
    assert auto["ephemeris_quality"]["status"] == "analytical_fallback"
    assert set(auto["ephemeris_quality"]["fallback_bodies"]) == {
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
    }
    assert auto["ephemeris_by_body"]["Ketu"] == "derived_antipode_of_Rahu"
    with pytest.raises(ValueError, match="require_data_files"):
        positions(birth, ephemeris_policy="require_data_files")


def test_physical_states_remain_d1_only_and_topic_facts_match_actual_paths():
    birth = build_astro_birth_info(**astro_payload())
    india = build_india(birth)
    for name, chart in india["charts"].items():
        for point in chart["planets"]:
            assert ("physical_state" in point) == (name == "D1")
            if name == "D1" and point["id"] not in {"Sun", "Rahu", "Ketu"}:
                assert (
                    point["physical_state"]["combustion"]["source_layer"]
                    == "translator_commentary"
                )
    checked = 0
    ashtakavarga_checked = 0
    for topic in india["topic_evidence"].values():
        for factor in topic["factors"]:
            if "fact_path" not in factor:
                continue
            value = {"india": india}
            for key in factor["fact_path"].split("."):
                value = value[int(key)] if isinstance(value, list) else value[key]
            assert value == factor["fact"]
            if factor["rule_id"] == "jyotish.ashtakavarga_rao2000.v1":
                ashtakavarga_checked += 1
            else:
                checked += 1
    assert checked == 30  # Six strength facts per topic plus earlier physical facts.
    assert ashtakavarga_checked == 5  # D1 plus the requested D9/D10 themes.


def test_native_longitude_speed_matches_independent_centered_time_difference():
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    before = positions(birth, birth.utc_datetime - timedelta(seconds=60))
    after = positions(birth, birth.utc_datetime + timedelta(seconds=60))
    for planet, state in raw["physical_states"].items():
        change = (
            after["longitudes"][planet] - before["longitudes"][planet] + 180
        ) % 360 - 180
        assert state["longitude_speed_degrees_per_day"] == pytest.approx(
            change * 720, abs=0.0001
        )


def test_strict_policy_is_shared_by_all_indian_request_models():
    from fatebridge.services.tool_catalog import CATALOG

    specs = {s.key: s for s in CATALOG}
    for key in ("astro_india", "astro_vimshottari", "astro_chart"):
        payload = {**astro_payload(), "ephemeris_policy": "require_data_files"}
        if key == "astro_chart":
            assert (
                specs[key].request_model.model_validate(payload).ephemeris_policy
                == "require_data_files"
            )
            with pytest.raises(
                ValueError, match="ephemeris_policy is not implemented for Guolao"
            ):
                specs[key].request_model.model_validate(
                    {**payload, "chart_variant": "guolao_chart"}
                )
            payload["chart_variant"] = "india_chart"
        assert (
            specs[key].request_model.model_validate(payload).ephemeris_policy
            == "require_data_files"
        )


def test_brihat_jataka_relationship_table_matches_independent_sign_lord_derivation():
    from fatebridge.core.jyotish_relationships import relationship

    # Independent derivation from the rule in II.15 and its explanatory note;
    # production uses the separately enumerated II.16-17 table instead.
    owners = [
        "Mars",
        "Venus",
        "Mercury",
        "Moon",
        "Sun",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Saturn",
        "Jupiter",
    ]
    roots = {
        "Sun": 4,
        "Moon": 1,
        "Mars": 0,
        "Mercury": 5,
        "Jupiter": 8,
        "Venus": 6,
        "Saturn": 10,
    }
    exalt = {
        "Sun": 0,
        "Moon": 1,
        "Mars": 9,
        "Mercury": 5,
        "Jupiter": 3,
        "Venus": 11,
        "Saturn": 6,
    }
    signs = {p: 0 for p in roots}
    for p, root in roots.items():
        friendly_signs = {
            (root + distance - 1) % 12 for distance in [2, 4, 5, 8, 9, 12]
        } | {exalt[p]}
        friend_lords = {owners[s] for s in friendly_signs}
        enemy_lords = {owners[s] for s in set(range(12)) - friendly_signs}
        for other in roots:
            if p == other:
                continue
            expected = (
                "neutral"
                if other in friend_lords & enemy_lords
                else "friend" if other in friend_lords else "enemy"
            )
            assert relationship(p, other, signs)["natural"] == expected


def test_relationship_direction_compound_rule_and_cooccupancy_are_preserved():
    from fatebridge.core.jyotish_relationships import relationship

    signs = {"Sun": 0, "Moon": 0, "Mercury": 1, "Venus": 6, "Saturn": 3}
    assert relationship("Moon", "Mercury", signs)["compound"] == "great_friend"
    assert relationship("Mercury", "Moon", signs)["compound"] == "neutral"
    assert relationship("Sun", "Moon", signs)["temporary"] == "enemy"
    assert relationship("Sun", "Moon", signs)["compound"] == "neutral"
    assert relationship("Sun", "Venus", signs)["compound"] == "great_enemy"
    assert relationship("Sun", "Mercury", signs)["compound"] == "friend"
    assert relationship("Sun", "Saturn", signs)["compound"] == "neutral"
    assert relationship("Sun", "Sun", signs)["compound"] == "self"
    with pytest.raises(ValueError):
        relationship("Sun", "Rahu", signs)


def test_new_topic_facts_verify_against_the_original_calculation_receipt():
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = next(s for s in CATALOG if s.key == "astro_india")
    body = execute_tool(
        spec,
        spec.request_model.model_validate(astro_payload()),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    receipt = body["run_metadata"]
    claims = [
        CalculationClaim(
            path=f["fact_path"],
            value=f["fact"],
            run_id=receipt["run_id"],
        )
        for topic in body["india"]["topic_evidence"].values()
        for f in topic["factors"]
        if "fact_path" in f
    ]
    assert sum(not c.path.startswith("india.ashtakavarga.") for c in claims) == 30
    assert sum(c.path.startswith("india.ashtakavarga.") for c in claims) == 5
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    # Preserve the original physical-fact tamper check after adding count facts.
    next(c for c in claims if not c.path.startswith("india.ashtakavarga.")).value = (
        "invented condition"
    )
    assert verify_calculation_claims(body, claims)["status"] == "rejected"


def test_shared_delta_t_initializes_new_workers_before_the_first_calculation():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fatebridge.core import ephemeris_runtime

    swe = pytest.importorskip("swisseph")
    ready = Barrier(3)

    def worker(_):
        swe.close()
        ready.wait(timeout=10)
        return ephemeris_runtime.ephemeris_call("deltat_ex", 2451545.0, swe.FLG_SWIEPH)

    with ThreadPoolExecutor(max_workers=3) as pool:
        for value in pool.map(worker, range(3)):
            assert 0.0005 < value < 0.001


def test_india_rest_works_as_the_first_request_in_a_fresh_process():
    import subprocess
    import sys

    script = """
from fastapi.testclient import TestClient
import fatebridge.api as api
api._reset_runtime_state_for_tests()
api.API_KEY_AUTHENTICATOR = api.ApiKeyAuthenticator(header_name='X-API-Key', api_keys={})
response = TestClient(api.app).post('/api/astro/india', json=PAYLOAD, params={'fields':'india.profile', 'strict_fields':'true', 'include_snapshot_text':'false'})
assert response.status_code == 200, response.text
assert response.json()['india']['profile']['ruleset_id'] == 'parashari_lahiri_core_v29'
""".replace("PAYLOAD", repr(astro_payload()))
    result = subprocess.run(
        [sys.executable, "-c", script], text=True, capture_output=True, timeout=60
    )
    assert result.returncode == 0, result.stdout + result.stderr
