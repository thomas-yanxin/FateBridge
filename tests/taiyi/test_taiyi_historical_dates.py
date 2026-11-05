"""Independent printed historical dates, source retention and public adapters."""

import asyncio
import json
import shutil
from datetime import date

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_historical import (
    historical_date_records,
    julian_to_proleptic_gregorian,
)
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from scripts.taiyi.audit_taiyi_historical_dates import CORPUS, audit, public_case

CASES = [r for r in historical_date_records()["records"] if "mode" in r]


def test_historical_replay_preserves_every_prior_conflict_and_unknown():
    report = audit()
    assert len(report["calendar_observations"]) == 4
    assert report["selected_calendar_observations_passed"] is True
    day, hour = [report["public_historical_replays"][k] for k in ("day", "hour")]
    assert (
        day["required_observations"],
        day["evaluated_observations"],
        day["matching_observations"],
    ) == (34, 33, 28)
    assert {r["id"] for r in day["disagreements"]} == {
        "main_chart",
        "heshen_chart",
        "eight_winds_prose",
        "eight_winds_chart",
        "heaven_time",
    }
    assert {r["id"] for r in day["unadjudicated"]} == {
        "ordinal_palace_prose",
    }
    assert (
        hour["required_observations"],
        hour["evaluated_observations"],
        hour["matching_observations"],
    ) == (20, 19, 16)
    assert {r["id"] for r in hour["disagreements"]} == {
        "set_count",
        "set_general",
        "set_vice_general",
    }
    assert [r["id"] for r in hour["unadjudicated"]] == ["menju_jiangfa"]
    assert report["full_classical_acceptance_passed"] is False
    assert report["full_ancient_calendar_reconstructed"] is False
    assert report["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize(
    "original,expected",
    [
        ((1582, 10, 4), date(1582, 10, 14)),
        ((1500, 2, 29), date(1500, 3, 10)),
        ((1700, 2, 29), date(1700, 3, 11)),
    ],
)
def test_explicit_julian_math_does_not_infer_country_cutover(original, expected):
    assert julian_to_proleptic_gregorian(*original) == expected


@pytest.mark.parametrize(
    "invalid",
    [
        (1561, 2, 29),
        (1562, 2, 30),
        (1562, 13, 1),
        (0, 1, 1),
        (True, 1, 1),
        (1562.0, 1, 1),
        (9999, 12, 31),
    ],
)
def test_invalid_dates_and_overflow_are_rejected_without_normalization(invalid):
    with pytest.raises(ValueError):
        julian_to_proleptic_gregorian(*invalid)


@pytest.mark.parametrize("row", CASES, ids=lambda r: r["mode"])
def test_historical_source_reference_is_typed_projectable_and_exported_from_same_board(
    row,
):
    result = public_case(row)
    b = result["taiyi"]
    ref = b["calendar_rules"]["historical_date_reference"]
    assert ref["day_ganzhi_matches"] and ref["counter_matches"]
    assert b["calendar_rules"]["input_calendar"] == "proleptic_gregorian"
    assert "儒略历" + row["julian_date"] in result["snapshot_text"]
    assert "推算公历" + row["gregorian_date"] in result["snapshot_text"]
    assert "本盘" + str(row["expected_accumulation"]) in result["snapshot_text"]
    assert b["ruleset"]["classical_acceptance_passed"] is False
    Taiyi.model_validate(b)
    for leaf in ref:
        p = project_fields(
            {"taiyi": b},
            ["taiyi.calendar_rules.historical_date_reference." + leaf],
            strict_fields=True,
        )
        Taiyi.model_validate(p["taiyi"])


def test_wrong_calendar_label_can_falsely_pass_taiyi_and_gate_but_not_full_chain():
    hour = next(r for r in CASES if r["mode"] == "hour")
    correct = public_case(hour)["taiyi"]
    wrong = public_case(hour, selected_date=hour["julian_date"])["taiyi"]
    assert (
        correct["core_board"]["taiyi_number"]
        == wrong["core_board"]["taiyi_number"]
        == 9
    )
    assert (
        correct["gates"]["counter"]["duty_gate"]
        == wrong["gates"]["counter"]["duty_gate"]
        == "生"
    )
    assert (
        correct["gates"]["counter"]["unit_in_gate"]
        == wrong["gates"]["counter"]["unit_in_gate"]
        == 17
    )
    assert (
        correct["core_board"]["accumulation"],
        wrong["core_board"]["accumulation"],
    ) == (887, 767)
    assert (
        correct["core_board"]["kook_number"],
        wrong["core_board"]["kook_number"],
    ) == (23, 47)
    assert (correct["wenchang_palace"], wrong["wenchang_palace"]) == ("乾", "卯")
    assert "historical_date_reference" not in wrong["calendar_rules"]


def test_different_hour_on_source_date_is_not_certified_as_the_example():
    from fatebridge.core.metaphysics.taiyi_historical import source_date_reference

    ref = source_date_reference(date(1562, 2, 5), "hour", 886, "丁丑", "酉")
    assert ref and ref["day_ganzhi_matches"] is True
    assert ref["counter_matches"] is False and ref["hour_branch_matches"] is False


def test_audit_rejects_deleted_calendar_observation_even_after_rehash(tmp_path):
    # Include the mandatory V6/V7 source siblings so a failure is specific to V8.
    fixtures = tmp_path / "fixtures"
    for name in ("taiyi_jinjing_v6", "taiyi_jinjing_v7", "taiyi_jinjing_v5"):
        shutil.copytree(CORPUS.parent / name, fixtures / name)
    # Prior audit references can include earlier corpora; preserve all of them.
    for origin in CORPUS.parent.glob("taiyi_jinjing_v*"):
        if not (fixtures / origin.name).exists():
            shutil.copytree(origin, fixtures / origin.name)
    copy = fixtures / CORPUS.name
    manifest = json.loads((copy / "manifest.json").read_text())
    source = tmp_path / "source.json"
    content = historical_date_records().copy()
    content["records"] = content["records"][:-1]
    source.write_text(json.dumps(content))
    import hashlib

    manifest["source_reference"] = {
        "file": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    (copy / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="四观察"):
        audit(copy)


@pytest.mark.parametrize("row", CASES, ids=lambda r: r["mode"])
@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_historical_date_evidence_across_actual_rest_native_mcp_and_cli(
    monkeypatch, capsys, key, row
):
    d = date.fromisoformat(row["gregorian_date"])
    options = {"calculation_mode": row["mode"]}
    if row["mode"] == "hour":
        options["hour_profile"] = "key_hour_winter_jiazi_v1"
    payload = (
        {
            "analysis_year": d.year,
            "analysis_month": d.month,
            "analysis_day": d.day,
            "analysis_hour": int(row["representative_clock"][:2]),
            "analysis_timezone": "+08:00",
            **options,
        }
        if key == "taiyi"
        else {
            "date": row["gregorian_date"],
            "time": row["representative_clock"],
            "zone": "+08:00",
            "taiyi_options": options,
        }
    )
    payload["use_true_solar_time"] = False
    fields = [
        "taiyi.calendar_rules",
        "taiyi.core_board",
        "taiyi.wenchang_palace",
        "taiyi.ruleset",
        "snapshot_text",
    ]
    transport_options = {
        "fields": fields,
        "strict_fields": True,
        "response_char_limit": 0,
        "as_of": "2026-10-22T12:00:00+08:00",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    response = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", transport_options["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key, {**payload, **transport_options}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    mcp = asyncio.run(protocol())
    argv = [key]
    for name, value in payload.items():
        argv += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    argv += [
        "--as-of",
        transport_options["as_of"],
        "--strict-fields",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in r.items() if k != "run_metadata"}
        for r in (response.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    ref = bodies[0]["taiyi"]["calendar_rules"]["historical_date_reference"]
    assert ref["counter_matches"] and ref["day_ganzhi_matches"]
