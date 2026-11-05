"""Direction invariants remain known without inventing missing gender."""

import asyncio
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_cycles as audit
from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.ziwei_auxiliary import attach_natal_cycles
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.ziwei.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import assert_same_run_receipt, verified_inline_business


def test_independent_cycles_keep_real_software_differences_and_unresolved_slots():
    r = audit.audit_cycles()
    assert not r["mismatches"]
    assert r["source_start_rows"] == 5 and r["lucun_stem_rows"] == 10
    assert r["conditional_input_cases"] == 300
    assert r["cycle_position_checks"] == 7200
    assert r["unknown_gender_invariant_labels_checked"] == 400
    assert r["unknown_gender_unresolved_slots"] == 2000
    assert r["source_position_comparison"]["iztro_2_5_8"]["changsheng"] == dict(
        matches=800, differences=500, unresolved=500
    )
    assert r["source_position_comparison"]["quanshu_v2_excerpt"]["changsheng"] == dict(
        matches=1300, differences=0, unresolved=500
    )
    assert not r["calendar_and_bureau_derivation_certified"]
    assert not r["whole_book_acceptance_passed"]


def test_discarding_all_unknown_labels_is_detected(monkeypatch):
    original = audit.attach_natal_cycles

    def discard(palaces, **kwargs):
        r = original(palaces, **kwargs)
        if kwargs["gender"] == "未知":
            for p in palaces:
                p["changsheng12"] = p["boshi12"] = None
        return r

    monkeypatch.setattr(audit, "attach_natal_cycles", discard)
    assert audit.audit_cycles()["mismatches"]


def test_runtime_source_cannot_rewrite_the_ming_reading(tmp_path, monkeypatch):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-cycles.json"
    r = json.loads((audit.ROOT / name).read_text())
    r["boshi"]["sequence_as_read"][9] = "天耗"
    p = tmp_path / name
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(r))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert dict(case="production_source_data") in audit.audit_cycles()["mismatches"]


def test_official_boshi_crop_is_required(tmp_path):
    folder = "naj_ming_cycles_v1"
    shutil.copytree(audit.FIXTURES / folder, tmp_path / folder)
    p = tmp_path / folder / "boshi-region.jpg"
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Cycle source checksum mismatch"):
        audit.audit_cycles(tmp_path)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("element", ["水", "木", "金", "土", "火"])
def test_two_labels_per_cycle_are_known_without_gender(element, profile):
    p = [dict(ganzhi="甲" + b) for b in "子丑寅卯辰巳午未申酉戌亥"]
    r = attach_natal_cycles(
        p, element=element, year_stem="乙", gender="未知", rule_profile=profile
    )
    assert r["status"] == "partial_missing_gender"
    assert r["changsheng_direction"] is r["boshi_direction"] is None
    for key, labels in (
        ("changsheng12", {"长生", "病"}),
        ("boshi12", {"博士", "飞廉"}),
    ):
        assert {row[key] for row in p if row[key] is not None} == labels
        assert sum(row[key] is None for row in p) == 10
        assert len(r["gender_invariant_positions"][key]) == 2


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("year", [1984, 1985])
def test_unknown_chart_is_the_intersection_of_both_directions(profile, year):
    charts = {
        g: build_ziwei_chart(_seed(year), g, rule_profile=profile)
        for g in ("男", "女", "未知")
    }
    by_branch = {
        g: {p["ganzhi"][1]: p for p in c["palaces"]} for g, c in charts.items()
    }
    for branch, row in by_branch["未知"].items():
        for key in ("changsheng12", "boshi12"):
            m, f = by_branch["男"][branch][key], by_branch["女"][branch][key]
            assert row[key] == (m if m == f else None)
        assert (
            row["stars_detail"]
            == by_branch["男"][branch]["stars_detail"]
            == by_branch["女"][branch]["stars_detail"]
        )
        assert row["daxian"] is None
    e = charts["未知"]["cycle_source_comparison"]
    assert e["changsheng"]["start_match"] and e["boshi"]["start_match"]
    assert e["changsheng"]["direction_match"] is None
    assert sum(r["match"] is None for r in e["positions"]["changsheng"].values()) == 10


def test_yin_year_software_difference_is_not_hidden_by_same_anchors():
    c = build_ziwei_chart(_seed(1985), "男")
    e = c["cycle_source_comparison"]
    assert c["wuxing_ju"]["element"] == "土"
    assert not e["changsheng"]["direction_match"]
    assert e["positions"]["changsheng"]["酉"]["actual"] == "养"
    assert e["positions"]["changsheng"]["酉"]["candidates"] == ["沐浴"]
    assert e["positions"]["changsheng"]["酉"]["match"] is False
    assert not e["source_rule_applied"]["changsheng"]
    assert e["source_name_mapping"]["明刊大耗"] == "大耗"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("gender", ["男", "未知"])
def test_cycle_view_survives_three_surfaces_and_default_mcp_budget(
    profile, gender, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)["cycle_sources"]["fields"]
    inputs = dict(
        birth_year=1985,
        birth_month=6,
        birth_day=1,
        birth_hour=2,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        gender=gender,
        rule_profile=profile,
    )
    options = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(
                "ziwei_birth", {**inputs, **options}, raise_on_error=False
            )
            assert not r.is_error, r.content
            await verified_inline_business(client, r.structured_content)
            if gender == "未知":
                normal = await client.call_tool(
                    "ziwei_birth",
                    {**inputs, **options, "fields": suggested_fields(spec)},
                )
                await verified_inline_business(client, normal.structured_content)
                view = normal.structured_content["ziwei_birth"]["reading_view"]
                assert view["distinct_star_count"] == 66
                assert view["star_occurrence_count"] == (
                    67 if profile == "quanshu_v2_excerpt" else 66
                )
                assert sum(p["changsheng12"] is not None for p in view["palaces"]) == 2
            return r

    native = asyncio.run(call())
    args = ["ziwei_birth"]
    for name, value in inputs.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    assert rest.status_code == 200, rest.text
    bodies = [
        {k: v for k, v in r.items() if k not in ("run_metadata", "result_delivery")}
        for r in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_birth"]["cycle_source_comparison"]
    assert all(len(e["positions"][k]) == 12 for k in ("changsheng", "boshi"))
    assert e["inputs"]["gender"] == gender


def test_metadata_reference_helper_never_allows_business_deferral():
    with pytest.raises(AssertionError):
        asyncio.run(
            verified_inline_business(
                None, {"result_delivery": {"deferred_fields": ["ziwei_birth"]}}
            )
        )


@pytest.mark.parametrize(
    "field", ["run_id", "environment_sha256", "ephemeris_inventory_sha256"]
)
def test_receipt_compaction_cannot_hide_changed_identity_or_fingerprints(field):
    files = {"0/test.se1": "a" * 64}
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    full = {
        "run_id": "same",
        "runtime": {
            "environment_sha256": "environment",
            "ephemeris": {"sha256": digest, "files": files},
        },
    }
    inline = {
        "run_id": "same",
        "runtime": {
            "delivery_path": "run_metadata.runtime",
            "environment_sha256": "environment",
            "ephemeris_inventory_sha256": digest,
            "ephemeris_files_count": 1,
        },
    }
    assert_same_run_receipt(inline, full)
    if field == "run_id":
        inline[field] = "changed"
    else:
        inline["runtime"][field] = "changed"
    with pytest.raises(AssertionError):
        assert_same_run_receipt(inline, full)
