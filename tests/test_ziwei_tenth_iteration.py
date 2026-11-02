"""The literal childhood rows are an independent method, never new 四化."""

import asyncio
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_childhood as audit
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.ziwei_childhood import childhood_limit
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_ziwei_horoscope
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from scripts.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import verified_inline_business

BIRTH = dict(
    birth_year=1984,
    birth_month=2,
    birth_day=2,
    birth_hour=2,
    gender="男",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
)
LITERAL_ROWS = [
    (1, "命宫", "丑"),
    (2, "财帛宫", "酉"),
    (3, "疾厄宫", "申"),
    (4, "夫妻宫", "亥"),
    (5, "福德宫", "卯"),
    (6, "官禄宫", "巳"),
]


def test_independent_childhood_audit_retains_six_cells_and_unresolved_tail():
    r = audit.audit_childhood()
    assert r["independent_explicit_ordinal_cells"] == 6
    assert r["conditional_chart_age_cases_checked"] == 288
    assert r["natal_star_joins_checked"] == 1700
    assert r["unresolved_age_cases_retained"] == 576
    assert not r["mismatches"]
    assert not r["whole_childhood_verse_acceptance_passed"]
    assert not r["age_boundary_certified"]
    assert not r["pre_decade_substitution_certified"]


def test_mutated_actual_branch_does_not_redefine_independent_expectation(monkeypatch):
    original = audit.childhood_limit

    def wrong(*args, **kwargs):
        r = original(*args, **kwargs)
        if r["status"] == "computed_given_age_ordinal":
            r["natal_branch"] = "bad"
        return r

    monkeypatch.setattr(audit, "childhood_limit", wrong)
    assert len(audit.audit_childhood()["mismatches"]) == 288


def test_runtime_source_rewrite_is_not_accepted_as_the_original(tmp_path, monkeypatch):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-childhood.json"
    r = json.loads((audit.ROOT / name).read_text())
    r["ordinal_rows"][1]["modern_palace_name"] = "父母宫"
    p = tmp_path / name
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(r))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert dict(case="production_source_data") in audit.audit_childhood()["mismatches"]


def test_original_childhood_page_is_required(tmp_path):
    name = "naj_ming_childhood_v1"
    shutil.copytree(audit.FIXTURES / name, tmp_path / name)
    p = tmp_path / name / "frame_0080.jpg"
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Childhood source checksum mismatch"):
        audit.audit_childhood(tmp_path)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("age,name,branch", LITERAL_ROWS)
def test_real_lunar_age_rows_join_actual_palace_and_natal_stars(
    profile, age, name, branch
):
    r = calculate_ziwei_horoscope(
        create_person_info(**BIRTH),
        rule_profile=profile,
        target_year=1983 + age,
        target_month=6,
        target_day=1,
        target_hour=12,
    )
    h = r["ziwei_horoscope"]
    c = h["childhood_limit"]
    assert h["nominal_age"] == c["given_age_ordinal"] == age
    assert c["natal_palace_name"] == name
    assert c["natal_branch"] == branch
    assert c["status"] == "computed_given_age_ordinal"
    chart = build_ziwei_chart(_seed(1984, hour="丑"), "男", rule_profile=profile)
    p = next(p for p in chart["palaces"] if p["name"] == name)
    assert c["natal_stars_detail"] == p["stars_detail"]
    assert c["natal_palace_ganzhi"] == p["ganzhi"]
    assert not c["childhood_sihua_supported"]
    assert "mutagen" not in c
    assert f"明文童限（给定岁序{age}）：本命{name}" in r["snapshot_text"]
    assert len(h["scopes"]) == 6


def test_childhood_second_age_does_not_replace_formal_first_decade():
    chart = build_ziwei_chart(
        _seed(1984, hour="丑"), "男", rule_profile="quanshu_v2_excerpt"
    )
    h = build_ziwei_horoscope(
        nominal_age_basis="legacy_mixed_clock",
        chart=chart,
        gender="男",
        target_seed=_seed(1985),
    )
    assert h["nominal_age"] == 2
    assert h["childhood_limit"]["natal_palace_name"] == "财帛宫"
    daxian = next(s for s in h["scopes"] if s["scope"] == "大限")
    assert daxian["natal_palace_name"] == "父母宫"
    assert daxian["is_childhood_limit"] is False
    assert h["childhood_limit"]["pre_decade_substitution_verified"] is False


@pytest.mark.parametrize("age", [7, 14, 15, 16, 40])
def test_unresolved_tail_and_adult_age_never_default_to_ming(age):
    chart = build_ziwei_chart(_seed(1984), "女")
    r = childhood_limit(chart, age)
    assert r["status"] == "unresolved_from_source"
    assert r["natal_palace_name"] is None and r["natal_branch"] is None
    assert r["natal_stars_detail"] == []
    assert r["unresolved_reason"]


def test_returned_natal_star_details_cannot_mutate_the_chart_or_cached_source():
    chart = build_ziwei_chart(_seed(1984), "女")
    before = deepcopy(chart)
    r = childhood_limit(chart, 1)
    assert r["natal_stars_detail"]
    r["natal_stars_detail"][0]["label"] = "changed"
    assert chart == before
    assert childhood_limit(chart, 1)["natal_stars_detail"][0]["label"] != "changed"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("age", [2, 8])
def test_childhood_view_is_equal_in_rest_mcp_cli_and_fits_default_mcp_budget(
    profile, age, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = evidence_views(next(s for s in CATALOG if s.key == "ziwei_horoscope"))[
        "childhood"
    ]["fields"]
    inputs = {
        **BIRTH,
        "rule_profile": profile,
        "target_year": 1983 + age,
        "target_month": 6,
        "target_day": 1,
        "target_hour": 12,
    }
    options = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/horoscope",
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
            result = await client.call_tool(
                "ziwei_horoscope", {**inputs, **options}, raise_on_error=False
            )
            await verified_inline_business(client, result.structured_content)
            return result

    native = asyncio.run(call())
    args = ["ziwei_horoscope"]
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
    assert not native.is_error, native.content
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    r = bodies[0]["ziwei_horoscope"]["childhood_limit"]
    assert r["status"] == (
        "computed_given_age_ordinal" if age == 2 else "unresolved_from_source"
    )
    assert r["natal_palace_name"] == ("财帛宫" if age == 2 else None)
