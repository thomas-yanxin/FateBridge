"""A selected printed Si Hua table changes facts, never merely a source badge."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_sihua_selection as audit
from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei_rulesets import (
    ZIWEI_SIHUA_RULES,
    sihua_rules_for,
    ziwei_ruleset_metadata,
)
from fatebridge.core.ziwei_sources import sihua_source_comparison
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei_limits import _seed
from scripts.ziwei.ziwei_conditional_inputs import synthetic_birth_clock
from tests.fixtures.mcp_receipt import verified_inline_business

BIRTH = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    gender="女",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
)
GENG = {"化禄": "太阳", "化权": "武曲", "化科": "天同", "化忌": "天相"}


def test_frozen_cells_and_preimplementation_coverage_are_not_new_independent_cases():
    r = audit.audit_sihua_selection()
    assert not r["differences"]
    assert (
        r["independent_literal_source_cells"],
        r["table_cells_checked_across_profiles"],
    ) == (40, 80)
    assert (r["conditional_natal_cases"], r["natal_assignment_joins_checked"]) == (
        60,
        240,
    )
    assert (
        r["software_coverage_candidates"],
        r["selected_coverage_inputs"],
        r["scope_profile_geng_ren_coverage"],
    ) == (124, 15, 24)
    assert r["dynamic_natal_joins_checked"] == 360
    assert r["new_independent_sources"] == 0 and r["manual_source_readers"] == 1
    assert not r["independent_calendar_or_star_placement_oracle"]
    assert (
        not r["dynamic_reuse_classically_verified"]
        and not r["whole_book_conformance_claimed"]
    )
    assert r["live_model_blind_evaluation"] == "not_run"


def test_wrong_applied_values_cannot_redefine_the_frozen_expected_table(monkeypatch):
    original = audit.build_ziwei_chart

    def wrong(*a, **kw):
        c = original(*a, **kw)
        if kw.get("sihua_source") == "naj_ming_v1":
            c["sihua"]["化科"] = "太阳"
        return c

    monkeypatch.setattr(audit, "build_ziwei_chart", wrong)
    rows = audit.audit_sihua_selection()["differences"]
    assert len(rows) == 60 and all("sihua" in row["failed"] for row in rows)


def test_original_scan_not_only_compiled_table_is_required(tmp_path):
    shutil.copy(audit.FIXTURES / "sihua_selection_vectors.json", tmp_path)
    shutil.copytree(
        audit.FIXTURES / "naj_ming_anxing_v1", tmp_path / "naj_ming_anxing_v1"
    )
    (tmp_path / "naj_ming_anxing_v1/frame_0076_geng_detail.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Ming selection source checksum mismatch"):
        audit.audit_sihua_selection(tmp_path)


def test_selected_table_does_not_merge_an_unrelated_baseline_or_mutate_cached_source():
    a = sihua_rules_for({}, "iztro_2_5_8", sihua_source="naj_ming_v1")
    assert a["庚"] == GENG
    a["庚"]["化忌"] = "天同"
    b = sihua_rules_for({}, "iztro_2_5_8", sihua_source="naj_ming_v1")
    assert b["庚"] == GENG
    assert ZIWEI_SIHUA_RULES["庚"]["化忌"] == "天同"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_an_applied_source_badge_requires_the_actual_whole_table_to_match(profile):
    old = sihua_rules_for(ZIWEI_SIHUA_RULES, profile)
    with pytest.raises(ValueError, match="实际四化表与来源不符"):
        sihua_source_comparison(old, compared_assignments_applied=True)


@pytest.mark.parametrize(
    "call",
    [
        lambda: build_ziwei_chart(_seed(1990), "女", sihua_source="invented"),
        lambda: build_ziwei_rules(sihua_source="invented"),
        lambda: ziwei_ruleset_metadata("iztro_2_5_8", sihua_source="invented"),
        lambda: sihua_rules_for({}, "iztro_2_5_8", sihua_source="invented"),
    ],
)
def test_unknown_source_never_silently_falls_back(call):
    with pytest.raises(ValueError, match="不支持的紫微四化来源"):
        call()


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_actual_geng_markers_and_symbolic_hua_yin_remain_separate(profile):
    r = calculate_ziwei_birth(
        create_person_info(**BIRTH), rule_profile=profile, sihua_source="naj_ming_v1"
    )
    c = r["ziwei_birth"]
    stars = {s["name"]: s for p in c["palaces"] for s in p["stars_detail"]}
    assert dict(c["sihua"]) == GENG
    assert stars["天同"]["mutagen"] == "化科" and stars["天相"]["mutagen"] == "化忌"
    assert stars["太阴"]["mutagen"] is None
    assert "化印" in c["ming_textual_properties"]["definitions"]["tianxiang"]["quote"]
    assert "化印" not in c["sihua"]
    assert any(
        x["kind"] == "natal_transformation"
        and x["name"] == "化忌"
        and x["star"] == "天相"
        for x in c["ming_textual_properties"]["occurrences"]
    )
    assert c["ruleset"]["version"].endswith("+sihua.naj-ming-v1")
    assert c["ruleset"]["sihua_source_url"].endswith("/item/4468520")
    assert c["sihua_source_comparison"]["compared_assignments_applied"] is True
    assert c["sihua_source_comparison"]["differences"] == []
    assert "所选四化表：明刊卷三" in r["snapshot_text"]
    assert "庚日武同相為首" in r["snapshot_text"]


@pytest.mark.parametrize(
    "fault", ["lost_selection", "projected_ruleset", "retagged_old_chart"]
)
def test_horoscope_rejects_missing_or_contradictory_natal_source_identity(fault):
    if fault in ("lost_selection", "projected_ruleset"):
        chart = build_ziwei_chart(_seed(1990), "女", sihua_source="naj_ming_v1")
        if fault == "lost_selection":
            chart["ruleset"].pop("sihua_source")
        else:
            chart["ruleset"] = {k: chart["ruleset"][k] for k in ("id", "version")}
    else:
        chart = build_ziwei_chart(_seed(1990), "女")
        chart["ruleset"] = ziwei_ruleset_metadata(
            "iztro_2_5_8", sihua_source="naj_ming_v1"
        )
    with pytest.raises(ValueError, match="四化.*不一致"):
        build_ziwei_horoscope(
            birth_seed=synthetic_birth_clock(int((chart)["lunar_date"]["year"])),
            chart=chart,
            gender="女",
            target_seed=_seed(2026),
        )


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_selected_source_does_not_create_pre_decade_transformations(profile):
    h = calculate_ziwei_horoscope(
        create_person_info(**BIRTH),
        rule_profile=profile,
        sihua_source="naj_ming_v1",
        target_year=1991,
        target_month=6,
        target_day=15,
        target_hour=12,
    )["ziwei_horoscope"]
    assert h["scopes"][0]["status"] == "not_started"
    assert h["scopes"][0]["mutagen"] is None
    expected = audit.frozen_table()[1]
    assert all(s["mutagen"] == expected[s["stem"]] for s in h["scopes"][1:])
    assert not h["sihua_source_comparison"]["dynamic_reuse_classically_verified"]


def test_source_selection_does_not_masquerade_as_solving_the_clock_age_boundary():
    m = json.loads((audit.FIXTURES / "clock_manifest.json").read_text())
    r = calculate_ziwei_horoscope(
        create_person_info(**m["cases"][0]["input"]),
        sihua_source="naj_ming_v1",
        target_year=1984,
        target_month=2,
        target_day=1,
        target_hour=23,
        target_minute=59,
    )
    age = r["ziwei_horoscope"]["nominal_age_calendar"]
    assert age["basis"] == "birth_civil_timezone"
    assert age["birth_placement_lunar_year"] == 1984
    assert age["birth_lunar_year"] == age["target_lunar_year"] == 1983
    assert age["nominal_age"] == 1
    assert age["age_boundary_classically_verified"] is False


def test_same_run_claims_reject_the_former_marker_on_the_new_source():
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    p = execute_tool(
        spec,
        spec.request_model.model_validate({**BIRTH, "sihua_source": "naj_ming_v1"}),
    )
    receipt = p["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="ziwei_birth.sihua.化忌",
            value=value,
            run_id=receipt["run_id"],
        )

    assert (
        verify_calculation_claims(p, [claim("天相")])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(p, [claim("天同")])["status"] == "rejected"


@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_horoscope", "ziwei_rules"])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("source", ["rule_profile", "naj_ming_v1"])
def test_source_identity_and_applied_values_match_rest_native_mcp_cli(
    tool, profile, source, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == tool)
    inputs = {"rule_profile": profile, "sihua_source": source}
    if tool == "ziwei_rules":
        inputs["year_stem"] = "庚"
    else:
        inputs.update(BIRTH)
    if tool == "ziwei_horoscope":
        inputs.update(
            target_year=2075 if profile == "iztro_2_5_8" else 2065,
            target_month=6,
            target_day=15,
            target_hour=12,
        )
    fields = evidence_views(spec)["sihua_source"]["fields"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(tool, {**inputs, **opts}, raise_on_error=False)
            assert not r.is_error, r.content
            return await verified_inline_business(client, r.structured_content)

    native = asyncio.run(call())
    args = [tool]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    c = bodies[0][tool] if tool != "ziwei_rules" else bodies[0]["rule_catalogue"]
    selected = source == "naj_ming_v1"
    assert c["sihua_source_comparison"]["compared_assignments_applied"] is selected
    assert c["ruleset"]["version"].endswith("+sihua.naj-ming-v1") is selected
    if tool == "ziwei_rules":
        assert c["sihua_by_year_stem"]["庚"] == (
            GENG if selected else ZIWEI_SIHUA_RULES["庚"]
        )
    if tool == "ziwei_birth":
        assert dict(c["sihua"]) == (GENG if selected else ZIWEI_SIHUA_RULES["庚"])


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_selected_source_default_natal_view_keeps_every_star_and_new_marker(profile):
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(
                "ziwei_birth",
                {
                    **example_input(spec),
                    "rule_profile": profile,
                    "sihua_source": "naj_ming_v1",
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "as_of": "2026-10-22T12:00:00+08:00",
                },
            )
            assert not r.is_error
            return await verified_inline_business(client, r.structured_content)

    c = asyncio.run(call())["ziwei_birth"]
    rows = [s for p in c["reading_view"]["palaces"] for s in p["stars"]]
    assert len(rows) == (67 if profile == "quanshu_v2_excerpt" else 66)
    changed = {s["mutagen"]: s["name"] for s in rows if s.get("mutagen")}
    assert len(changed) == 4 and changed == GENG
