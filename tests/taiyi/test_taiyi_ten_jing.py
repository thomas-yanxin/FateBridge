"""Source-supported twelve-branch rule with explicit worked-example conflicts."""

import asyncio
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_ten_jing import key_ten_jing
from fatebridge.core.output_taiyi_day import TaiyiTenJing
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_ten_jing import CORPUS, audit


def test_all_annual_remainders_and_locations_preserve_direction_difference_and_absence():
    report = audit()
    annual = report["annual_cross_period_reference"]
    assert (
        annual["required_observations"],
        annual["evaluated_observations"],
        annual["matching_observations"],
    ) == (22, 21, 20)
    assert [
        (r["id"], r["expected"], r["computed_value"]) for r in annual["disagreements"]
    ] == [("heaven_venerable_location", "卯", "酉")]
    assert [r["id"] for r in annual["unadjudicated"]] == ["three_winds_location"]
    assert annual["unadjudicated"][0]["computed_value"] == "酉"
    assert annual["unadjudicated"][0]["expected"] is None
    assert annual["source_example_acceptance_passed"] is False
    day = report["unchanged_complete_day_case"]
    assert (
        day["required_observations"],
        day["evaluated_observations"],
        day["matching_observations"],
    ) == (34, 33, 28)
    assert {r["id"] for r in day["disagreements"]} == {
        "heaven_time",
        "main_chart",
        "heshen_chart",
        "eight_winds_prose",
        "eight_winds_chart",
    }
    assert [r["id"] for r in day["unadjudicated"]] == ["ordinal_palace_prose"]
    assert report["source_example_acceptance_passed"] is False


@pytest.mark.parametrize(
    "count,yang,yin",
    [
        (1, "寅", "申"),
        (8, "酉", "卯"),
        (10, "亥", "巳"),
        (12, "丑", "未"),
        (13, "寅", "申"),
        (44, "酉", "卯"),
        (10155478, "亥", "巳"),
    ],
)
def test_twelve_branches_and_opposition_do_not_insert_corner_palaces(count, yang, yin):
    for reverse, expected in [(False, yang), (True, yin)]:
        data = key_ten_jing(count, reverse)
        h = data["records"]["heaven_time"]
        assert h["palace"] == expected and h["yang_position"] == yang
        assert h["period"] == 12 and h["status"] == "computed"
        assert h["sequence"] == list("寅卯辰巳午未申酉戌亥子丑")
        assert h["candidates"][0]["adopted"] is True
        assert len(h["rule_evidence"]["sources"]) == 3
        assert data["version"] == "1.1.0"
        assert data["classical_acceptance_passed"] is False
        TaiyiTenJing.model_validate(data)


def test_same_phase_comparison_is_explicit_and_does_not_change_arithmetic_to_kun():
    a, b, other, yin = [
        key_ten_jing(n, y)["records"]["heaven_time"]
        for n, y in [(44, False), (56, False), (45, False), (44, True)]
    ]
    assert a["palace"] == b["palace"] == "酉"
    assert [
        (r["source_value"], r["rule_derived_value"]) for r in a["source_comparisons"]
    ] == [("坤", "酉")]
    assert other["source_comparisons"] == yin["source_comparisons"] == []
    assert "历史日期匹配另列" in b["source_comparisons"][0]["scope"]
    assert key_ten_jing(44, False)["records"]["taiyi_ordinal"]["palace"] is None
    assert key_ten_jing(44, True)["records"]["taiyi_ordinal"]["ordinal"] == 44


@pytest.mark.parametrize(
    "mutation", ["drop_direction_disagreement", "drop_unstated_location", "alter_scan"]
)
def test_source_freeze_rejects_removing_inconvenient_observations_even_after_rehash(
    tmp_path, mutation
):
    fixtures = tmp_path / "fixtures"
    for original in CORPUS.parent.glob("taiyi_jinjing_v*"):
        shutil.copytree(original, fixtures / original.name)
    c = fixtures / CORPUS.name
    if mutation == "alter_scan":
        with (c / "key-page33-hi.jpg").open("ab") as f:
            f.write(b"changed")
    else:
        p = c / "annual-ten-essences.json"
        data = json.loads(p.read_text())
        target = (
            "heaven_venerable_location"
            if mutation == "drop_direction_disagreement"
            else "three_winds_location"
        )
        data["observations"] = [r for r in data["observations"] if r["id"] != target]
        p.write_text(json.dumps(data))
        manifest = json.loads((c / "manifest.json").read_text())
        for row in manifest["source_files"]:
            if row["file"] == p.name:
                row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest["annual_observation_count"] = len(data["observations"])
        (c / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit(c)


def test_actual_public_board_and_snapshot_distinguish_rule_from_source_observation():
    r = calculate_taiyi_analysis(
        analysis_year=1562,
        analysis_month=1,
        analysis_day=6,
        analysis_hour=12,
        analysis_timezone="+08:00",
        calculation_mode="day",
        use_true_solar_time=False,
    )
    board = r["taiyi"]
    assert board["core_board"]["accumulation"] == 44
    marked = [p["palace"] for p in board["palace_marks"] if "天时" in p["markers"]]
    assert marked == ["酉"]
    assert all(
        "天时" not in p["markers"] for p in board["palace_marks"] if p["palace"] == "坤"
    )
    assert "天时：酉" in r["snapshot_text"]
    assert "均作大武坤" in r["snapshot_text"] and "本盘规则推算酉" in r["snapshot_text"]
    assert "未认定为传抄错误" in r["snapshot_text"]
    assert (
        board["calendar_rules"]["historical_date_reference"]["counter_matches"] is True
    )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_source_rule_and_disagreement_are_identical_on_actual_transports(
    monkeypatch, capsys, key
):
    payload = (
        {
            "analysis_year": 1562,
            "analysis_month": 1,
            "analysis_day": 6,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "calculation_mode": "day",
        }
        if key == "taiyi"
        else {
            "date": "1562-01-06",
            "time": "12:00:00",
            "zone": "+08:00",
            "taiyi_options": {"calculation_mode": "day"},
        }
    )
    payload["use_true_solar_time"] = False
    fields = [
        "taiyi.ten_jing.records.heaven_time",
        "taiyi.ten_jing.records.taiyi_ordinal",
        "taiyi.ten_jing.version",
        "snapshot_text",
    ]
    opts = {
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
    rest = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def native():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key, {**payload, **opts}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    mcp = asyncio.run(native())
    args = [key]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in (rest.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    h = bodies[0]["taiyi"]["ten_jing"]["records"]["heaven_time"]
    assert h["palace"] == "酉" and h["source_comparisons"][0]["source_value"] == "坤"
    assert h["rule_evidence"]["unresolved"]
