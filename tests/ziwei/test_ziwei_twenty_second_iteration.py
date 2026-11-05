"""Expose textual uncertainty and reject unsupported childhood certifications."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.discovery import select_mcp_specs
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.output_chinese import ZiweiChildhoodLimit
from fatebridge.core.ziwei_childhood import childhood_limit
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.ziwei.audit_ziwei_independent_readings import audit_independent_readings
from scripts.ziwei.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import verified_inline_business

SOURCE = json.loads(
    (
        Path(__file__).parents[1]
        / "data/ziwei_independent/naj_ming_childhood_v1/collation.json"
    ).read_text()
)


def test_independent_reading_cannot_hide_the_failed_first_pass_or_unknowns():
    result = audit_independent_readings()
    assert result["requested_day_inputs"] == 150
    assert result["original_report_single_direct_inputs"] == 147
    assert result["corrected_single_direct_inputs"] == 146
    assert (
        len(result["directly_read_positions_agreeing_with_selected_transcription"])
        == 146
    )
    assert result["direct_position_differences"] == []
    assert result["inputs_without_directly_readable_label"] == [
        {"bureau": 2, "day": 21},
        {"bureau": 3, "day": 11},
        {"bureau": 6, "day": 6},
    ]
    assert len(result["conflicting_direct_inputs"]) == 1
    assert not result["all_150_day_inputs_uniquely_confirmed"]
    assert not result["modern_clock_mapping_established"]
    assert not result["lunar_year_age_boundary_established"]
    assert not result["whole_book_acceptance_passed"]
    assert result["clock_review_reported_distinct_full_frames"] == 39
    assert result["clock_review_reported_failed_attempts"] == 16


def test_independent_review_rejects_a_rewritten_raw_first_answer(tmp_path):
    name = "independent_readings_r22_v1"
    fixtures = Path(__file__).parents[1] / "data/ziwei_independent"
    shutil.copytree(fixtures / name, tmp_path / name)
    path = tmp_path / name / "reports/day-review.json"
    record = json.loads(path.read_text())
    record["coverage"]["inputs_with_single_directly_readable_branch"] = 150
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Independent reading checksum mismatch"):
        audit_independent_readings(tmp_path)


@pytest.mark.parametrize("scope", ["topic", "complete"])
def test_specified_method_scenario_advertises_and_executes_ziwei_rules(scope):
    selected = select_mcp_specs(CATALOG, scenario="onda-xingpan", tool_scope=scope)
    assert "ziwei_rules" in {s.key for s in selected}

    async def call():
        async with Client(
            create_mcp_app(scenarios="onda-xingpan", tool_scope=scope)
        ) as client:
            tools = {t.name for t in await client.list_tools()}
            assert "ziwei_rules" in tools
            result = await client.call_tool(
                "ziwei_rules",
                {
                    "year_stem": "庚",
                    "sihua_source": "naj_ming_v1",
                    "fields": [
                        "rule_catalogue.ruleset",
                        "focused_rules",
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            assert not result.is_error, result.content
            payload = await verified_inline_business(client, result.structured_content)
            assert payload["rule_catalogue"]["ruleset"]["sihua_source"] == "naj_ming_v1"
            assert payload["focused_rules"]["year_stem"] == "庚"

    asyncio.run(call())


@pytest.mark.parametrize("age", [1, 6, 7, 15])
def test_uncertain_glyph_is_disclosed_without_extrapolating_the_verse(age):
    chart = build_ziwei_chart(_seed(1984), "男")
    result = childhood_limit(chart, age)
    assert result["source_reading"] == SOURCE["quote"]
    assert result["source_reading_caveat"] == SOURCE["tail_glyph_note"]
    assert result["age_boundary_rule_verified"] is False
    assert result["childhood_sihua_supported"] is False
    if age <= 6:
        row = next(r for r in SOURCE["ordinal_rows"] if r["age"] == age)
        palace = next(
            p for p in chart["palaces"] if p["name"] == row["modern_palace_name"]
        )
        assert result["natal_stars_detail"] == palace["stars_detail"]
        assert result["natal_palace_ganzhi"] == palace["ganzhi"]
    else:
        assert result["status"] == "unresolved_from_source"
        assert result["natal_palace_name"] is None
        assert result["natal_stars_detail"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_boundary_rule_verified", True),
        ("pre_decade_substitution_verified", True),
        ("childhood_sihua_supported", True),
        ("natal_stars_are_not_childhood_transformations", False),
    ],
)
def test_public_output_cannot_certify_unverified_childhood_rules(field, value):
    with pytest.raises(ValidationError):
        ZiweiChildhoodLimit.model_validate({field: value})
    assert ZiweiChildhoodLimit.model_validate({}).model_fields_set == set()


@pytest.mark.parametrize("year,age", [(1984, 1), (1990, 7)])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_childhood_caveat_survives_rest_native_mcp_cli_with_original_budget(
    year, age, profile, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=1984,
        birth_month=2,
        birth_day=2,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        target_year=year,
        target_month=2,
        target_day=2,
        target_hour=13,
        target_minute=0,
        target_timezone="Asia/Shanghai",
        rule_profile=profile,
    )
    fields = ["ziwei_horoscope.nominal_age", "ziwei_horoscope.childhood_limit"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/horoscope",
        json=inputs,
        params=[
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "8192"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(
                "ziwei_horoscope", {**inputs, **options}, raise_on_error=False
            )
            assert not result.is_error, result.content
            return await verified_inline_business(client, result.structured_content)

    native = asyncio.run(call())
    args = ["ziwei_horoscope"]
    for key, value in inputs.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.extend(
        [
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "8192",
            "--fields",
            *fields,
        ]
    )
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200, rest.text
    assert code == 0, cli
    facts = [r["ziwei_horoscope"] for r in [rest.json(), native, cli]]
    assert facts[0] == facts[1] == facts[2]
    assert facts[0]["nominal_age"] == age
    receipt = facts[0]["childhood_limit"]
    assert receipt["source_reading_caveat"] == SOURCE["tail_glyph_note"]
    assert receipt["natal_stars_are_not_childhood_transformations"] is True
