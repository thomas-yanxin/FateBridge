"""Reference identity, independent oracle integrity and honest coverage."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.astro import ephemeris
from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.astro.reference_points import ephemeris_reference_points
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from scripts.astrodice.audit_astrodice_kernel import validate_reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "tests/data/astrodice/tables/kernel-protocol.json").read_text()
)
REFERENCE = json.loads(
    (ROOT / "tests/data/astrodice/tables/kernel-horizons.json").read_text()
)


def test_frozen_reference_hashes_frame_time_and_target_identity():
    validate_reference(PROTOCOL, REFERENCE)
    assert (
        REFERENCE["protocol_sha256"]
        == hashlib.sha256(
            (ROOT / "tests/data/astrodice/tables/kernel-protocol.json").read_bytes()
        ).hexdigest()
    )
    assert (
        REFERENCE["generator_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts/astrodice/gen_astrodice_kernel_reference.py").read_bytes()
        ).hexdigest()
    )
    assert len(REFERENCE["references"]) == 10
    for item in REFERENCE["references"]:
        raw = item["raw_response_utf8"]
        assert hashlib.sha256(raw.encode()).hexdigest() == item["raw_response_sha256"]
        assert json.loads(raw) == item["response"]
        text = item["response"]["result"]
        assert hashlib.sha256(text.encode()).hexdigest() == item["result_sha256"]
        assert item["target_id"] == PROTOCOL["targets"][item["body"]]
        assert item["parameters"]["COMMAND"] == f"'{item['target_id']}'"
        assert item["parameters"]["TIME_TYPE"] == "'TT'"
        assert item["parameters"]["REF_SYSTEM"] == "'ICRF'"
        assert item["parameters"]["VEC_CORR"] == "'NONE'"
        assert "Reference frame : ICRF" in text and "GEOMETRIC cartesian" in text


@pytest.mark.parametrize(
    "mutation", ["drop_body", "drop_row", "change_vector", "invent_missing"]
)
def test_reference_validation_detects_coverage_and_data_reward_hacking(mutation):
    bad = copy.deepcopy(REFERENCE)
    if mutation == "drop_body":
        bad["references"].pop()
    elif mutation == "drop_row":
        bad["references"][0]["rows"].pop(0)
    elif mutation == "change_vector":
        bad["references"][0]["rows"][0]["position_au"][0] += 1e-7
    else:
        bad["references"][0]["unavailable_requested_epochs"][0][
            "reason"
        ] = "claimed passed"
    with pytest.raises(ValueError):
        validate_reference(PROTOCOL, bad)


def test_missing_original_endpoint_is_retained_not_replaced_by_supplement():
    requested = set(PROTOCOL["dates_tt"])
    for item in REFERENCE["references"]:
        available = {r["date_tt"] for r in item["rows"]}
        absent = {r["date_tt"] for r in item["unavailable_requested_epochs"]}
        assert (available & requested) | absent == requested
        assert not available & absent
        assert absent == {"9999-12-31T12:00:00"}
        assert set(PROTOCOL["supplemental_dates_tt"]) <= available
        failed = item["failed_original_request"]
        assert "No ephemeris" in failed["response"].get(
            "error", failed["response"].get("result", "")
        )
        assert (
            hashlib.sha256(failed["raw_response_utf8"].encode()).hexdigest()
            == failed["raw_response_sha256"]
        )


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("failed_body", [None, "Pluto", "Moon", "North Node"])
def test_actual_model_reference_points_and_snapshot_agree(
    zodiacal, failed_body, monkeypatch
):
    original = ephemeris._swisseph_planet_state
    if failed_body:
        monkeypatch.setattr(
            ephemeris,
            "_swisseph_planet_state",
            lambda name, *a, **kw: (
                None if name == failed_body else original(name, *a, **kw)
            ),
        )
    faces = {"planet": "Jupiter", "sign": "Aries", "house": 0}
    plain = build_otherbu_result(**faces)
    result = build_otherbu_result(
        **faces,
        date="2024-03-20",
        time="06:30",
        zone="UTC",
        lat=51.5,
        lon=0,
        zodiacal=zodiacal,
    )
    basis = result["chart"]["params"]["ephemerisReferencePoints"]
    assert basis["center_body_correction_applied"] is False
    assert basis["body_centers"] == [
        p for p in ["Sun", "Moon", "Mercury", "Venus"] if p != failed_body
    ]
    assert basis["system_barycenters"] == [
        p
        for p in ["Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        if p != failed_body
    ]
    assert basis["theoretical_points"] == (
        [] if failed_body == "North Node" else ["North Node"]
    )
    assert basis["approximate_points"] == ([failed_body] if failed_body else [])
    assert basis["derived_points"] == ["South Node", "Pars Fortuna"]
    assert basis["unresolved_points"] == []
    assert basis["note_zh"] in result["snapshot_text"]
    for key in [
        "symbolic_details",
        "interpretation",
        "rule_trace",
        "rulesets",
        "diceChart",
    ]:
        assert plain[key] == result[key]


def test_unknown_model_cannot_inherit_a_native_center_claim():
    result = ephemeris_reference_points(
        {"Jupiter": "unknown", "Moon": "unavailable"}, []
    )
    assert result["body_centers"] == result["system_barycenters"] == []
    assert result["unresolved_points"] == ["Jupiter", "Moon"]


def test_declared_mean_node_theory_is_theoretical_and_cannot_label_a_body():
    result = ephemeris_reference_points(
        {"North Node": ANALYTICAL_MEAN_NODE_MODEL, "Sun": ANALYTICAL_MEAN_NODE_MODEL},
        ["South Node"],
    )
    assert result["theoretical_points"] == ["North Node"]
    assert result["unresolved_points"] == ["Sun"]
    assert result["body_centers"] == result["system_barycenters"] == []


def test_all_approximate_points_are_not_described_as_native_centers():
    result = ephemeris_reference_points(
        {
            "Sun": "fatebridge_approximate_orbital_model",
            "Jupiter": "fatebridge_approximate_orbital_model",
        },
        ["Pars Fortuna"],
    )
    assert result["body_centers"] == result["system_barycenters"] == []
    assert "原生" not in result["note_zh"]
    assert result["approximate_points"] == ["Sun", "Jupiter"]
