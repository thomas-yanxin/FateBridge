"""Real REST, native MCP and CLI agree, including partial calendar results."""

import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

SPECS = {spec.key: spec for spec in CATALOG}
AS_OF = "2026-10-22T12:00:00+08:00"


@pytest.mark.parametrize(
    "key,payload,fields",
    [
        (
            "suzhan",
            {
                "date": "2025-02-07",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "clothing",
                "activity_details": ["tailoring_garments"],
            },
            [
                "sukuyo.clothing_reference",
                "sukuyo.activity_assessment",
                "sukuyo.candidate_days",
                "sukuyo.reading_text",
                "rulesets.clothing",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-02-11",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "clothing",
                "activity_details": ["tailoring_garments"],
            },
            [
                "sukuyo.clothing_reference",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.clothing",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2024-08-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "clothing",
                "activity_details": ["tailoring_garments"],
                "calendar_profile": "hinoo_t1299_host27",
            },
            [
                "sukuyo.clothing_reference",
                "sukuyo.activity_assessment",
                "sukuyo.calendar",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-02-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "clothing",
                "activity_details": ["wearing_new_garments", "royal_wearer"],
            },
            [
                "sukuyo.clothing_reference",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "0903-07-13",
                "time": "00:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "sukuyo.calendar.calendar_reference.day_ganzhi_reference",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-02-06",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["eastbound_journey"],
            },
            [
                "sukuyo.taibai_direction_reference",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.taibai_directions",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-02-07",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["eastbound_journey"],
            },
            [
                "sukuyo.taibai_direction_reference",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.taibai_directions",
            ],
        ),
        (
            "suzhan",
            {
                "date": "0806-01-28",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "sukuyo.calendar",
                "sukuyo.day_mansion",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
                "input_normalized",
            ],
        ),
        (
            "suzhan",
            {
                "date": "0820-03-22",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "sukuyo.calendar",
                "sukuyo.day_mansion",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
                "input_normalized",
            ],
        ),
        (
            "suzhan",
            {
                "date": "1872-12-31",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "sukuyo.calendar",
                "sukuyo.day_mansion",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
                "input_normalized",
            ],
        ),
        (
            "suzhan",
            {
                "date": "0806-09-20",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            [
                "sukuyo.calendar",
                "sukuyo.day_mansion",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
                "input_normalized",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "0001-01-01",
                "person1_zone": "+15:00",
                "person2_date": "0001-01-01",
                "person2_zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "status",
                "person1",
                "person2",
                "pair",
                "candidate_relation_analysis",
                "summary",
                "rulesets",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1872-12-31",
                "person1_zone": "UTC",
                "person2_date": "1872-12-31",
                "person2_zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
            },
            [
                "status",
                "person1",
                "person2",
                "pair",
                "candidate_relation_analysis",
                "summary",
                "rulesets",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "婁",
                "activity": "social",
            },
            [
                "sukuyo.six_palace_reference",
                "sukuyo.personal_day",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.six_palace_positions",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2017-06-24",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
                "natal_mansion": "娄",
            },
            [
                "sukuyo.six_palace_reference",
                "sukuyo.day_mansion",
                "sukuyo.personal_day",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2017-06-24",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
            },
            [
                "sukuyo.calendar",
                "sukuyo.weekday",
                "sukuyo.lower_methods.weekday",
                "sukuyo.reading_text",
                "rulesets.calendar_reference",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2017-06-23",
                "time": "15:00:00",
                "zone": "UTC",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
            },
            ["sukuyo.calendar", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2024-08-04",
                "time": "12:00:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            ["sukuyo.calendar", "sukuyo.day_mansion", "sukuyo.reading_text"],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2017-06-24",
                "person1_zone": "+09:00",
                "person2_date": "2017-07-23",
                "person2_zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
            },
            [
                "calendar_basis",
                "status",
                "person1",
                "person2",
                "pair",
                "candidate_relation_analysis",
                "rulesets",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1969-09-30",
                "person1_zone": "Pacific/Kwajalein",
                "person2_date": "1969-10-01",
                "person2_zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
            },
            [
                "calendar_basis",
                "status",
                "person1",
                "person2",
                "candidate_relation_analysis",
                "summary",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2031-01-22",
                "person1_zone": "UTC",
                "person2_date": "2031-01-22",
                "person2_zone": "+09:00",
                "calendar_basis": "japanese_hutime_1002_1_utc09",
            },
            [
                "calendar_basis",
                "status",
                "person1",
                "person2",
                "candidate_relation_analysis",
                "summary",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-03",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "social",
                "activity_details": ["social_gathering"],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-03",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "social",
                "activity_details": ["forming_friendship"],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-03",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["personal_departure"],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-03",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["private_journey"],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-02",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["long_distance_journey"],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-02",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": [
                    "long_distance_journey",
                    "royal_or_official_traveler",
                ],
            },
            ["sukuyo.activity_assessment", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "奎",
                "activity": "travel",
            },
            ["sukuyo.personal_day", "sukuyo.activity_assessment"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "娄",
                "activity": "travel",
                "activity_details": ["long_distance_traveler_entering_residence"],
            },
            ["sukuyo.personal_day", "sukuyo.activity_assessment"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "昴",
                "activity": "study",
                "activity_details": ["monastic_dharma_request"],
            },
            ["sukuyo.personal_day", "sukuyo.activity_assessment"],
        ),
        (
            "suzhan",
            {
                "date": "2024-08-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "calendar_profile": "hinoo_t1299_host27",
            },
            [
                "sukuyo.calendar.profile_calculation.source_bundle_sha256",
                "sukuyo.calendar.profile_calculation.host_calculation.source_bundle_sha256",
                "sukuyo.calendar.profile_calculation.short_month_assignment",
                "sukuyo.calendar.profile_calculation.hinoo_source.cached_primary_excerpt",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2024-08-04",
                "person2_date": "2024-08-04",
                "calendar_profile": "hinoo_t1299_host27",
            },
            [
                "person1.calendar.profile_calculation.source_bundle_sha256",
                "person1.calendar.profile_calculation.host_calculation.source_bundle_sha256",
                "person2.calendar.profile_calculation.hinoo_source.cached_primary_excerpt",
                "candidate_relation_analysis",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-06-24",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "study",
                "activity_details": ["religious_learning"],
            },
            [
                "sukuyo.special_day_labels",
                "sukuyo.special_day_evidence",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.special_days",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-02-02",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "study",
            },
            [
                "sukuyo.special_day_evidence.comparisons",
                "sukuyo.activity_assessment.conditional_rules",
                "sukuyo.activity_assessment.unresolved_source_rules_present",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-04-15",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "study",
                "activity_details": ["religious_learning"],
            },
            [
                "sukuyo.special_day_evidence",
                "sukuyo.activity_assessment.matched_rules",
                "sukuyo.activity_assessment.layers",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-13",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["northbound_journey"],
            },
            [
                "sukuyo.directional_travel",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
                "rulesets.travel_directions",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-01-30",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["southbound_journey"],
            },
            [
                "sukuyo.directional_travel.selected_records",
                "sukuyo.activity_assessment.matched_rules",
                "sukuyo.activity_assessment.evidence_status",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {"date": "2025-01-29", "time": "20:00:00", "zone": "+08:00"},
            [
                "sukuyo.calendar_day",
                "sukuyo.reading_text",
                "rulesets.textual_resolutions",
            ],
        ),
        (
            "suzhan",
            {"date": "2025-01-29", "zone": "8.0000000002777778"},
            ["sukuyo.calendar", "sukuyo.reading_text"],
        ),
        (
            "suzhan",
            {
                "date": "0806-07-23",
                "time": "23:59:00",
                "zone": "+09:00",
                "calendar_basis": "japanese_naoj_historical_utc09",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            [
                "sukuyo.calendar",
                "sukuyo.calendar_day.clock_doctrine.arc_printed_reference",
                "sukuyo.reading_text",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2025-01-29",
                "person1_zone": "8.0000000002777778",
                "person2_date": "2025-03-04",
            },
            ["person1.calendar", "candidate_relation_analysis", "summary"],
        ),
        (
            "suzhan",
            {"date": "2025-02-08", "time": "20:00:00", "zone": "+08:00"},
            [
                "sukuyo.calendar_day.verse_abbreviation_resolution",
                "sukuyo.calendar_day.time_restrictions",
                "sukuyo.calendar_day.prose_verse_time_semantic_conflict",
                "sukuyo.reading_text",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2025-01-29",
                "person1_zone": "UTC",
                "person2_date": "2025-03-04",
            },
            [
                "person1.calendar.date_support.possible_calendar_dates",
                "candidate_relation_analysis.rows",
                "candidate_relation_analysis.calendar_date_uncertainty_remains",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2025-01-29",
                "person1_zone": "UTC",
                "person2_date": "2025-03-04",
            },
            [
                "status",
                "person1.calendar",
                "person2.natal_su27",
                "candidate_relation_analysis",
                "pair",
                "summary",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1969-09-30",
                "person1_zone": "Pacific/Kwajalein",
                "person2_date": "2025-03-04",
            },
            [
                "status",
                "person1.calendar.date_support",
                "person1.calendar.calendar_candidates",
                "candidate_relation_analysis",
                "pair",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "commerce",
                "activity_details": ["collecting_debt"],
            },
            [
                "sukuyo.lower_methods",
                "sukuyo.activity_assessment",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "commerce",
                "activity_details": ["purchase_precious_goods"],
            },
            [
                "sukuyo.activity_assessment.effective_activity_details",
                "sukuyo.activity_assessment.detail_inferences",
                "sukuyo.lower_methods.nature.selected_group",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-13",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "travel",
                "activity_details": ["journey_abroad", "long_distance_journey"],
            },
            [
                "sukuyo.activity_assessment",
                "sukuyo.calendar_day.clock_doctrine",
                "sukuyo.reading_text",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "textual_pada": 2,
            },
            ["sukuyo.palace_reference", "sukuyo.reading_text", "input_normalized"],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1990-06-15",
                "person2_date": "1992-03-20",
                "person1_textual_pada": 1,
                "person2_textual_pada": 4,
            },
            [
                "person1.palace_reference",
                "person2.palace_reference",
                "pair",
                "person1_to_person2",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "commerce",
                "activity_details": ["borrowing"],
            },
            [
                "sukuyo.activity_assessment",
                "sukuyo.lower_mansion_day",
                "sukuyo.conjunction_doctrine",
                "sukuyo.reading_text",
                "input_normalized",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "activity": "commerce",
            },
            [
                "sukuyo.activity_assessment.conditional_rules",
                "sukuyo.lower_mansion_day",
                "sukuyo.conjunction_doctrine",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2024-08-04",
                "person2_date": "2025-03-04",
                "calendar_profile": "hinoo_t1299_host27",
            },
            [
                "status",
                "person1",
                "person2",
                "person1_to_person2",
                "rulesets",
                "candidate_relation_analysis",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2024-08-04",
                "person2_date": "2024-08-04",
                "calendar_profile": "hinoo_t1299_host27",
                "person1_calendar_day_part": "first_half",
                "person2_calendar_day_part": "second_half",
            },
            [
                "status",
                "su27_basis",
                "person1",
                "person2",
                "person1_to_person2",
                "person2_to_person1",
                "pair",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2024-08-04",
                "time": "09:00:00",
                "zone": "+08:00",
                "calendar_profile": "hinoo_t1299_host27",
            },
            [
                "sukuyo.calendar",
                "sukuyo.day_mansion",
                "sukuyo.reading_text",
                "rulesets",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2024-08-04",
                "time": "09:00:00",
                "zone": "+08:00",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            ["sukuyo", "input_normalized", "rulesets", "summary"],
        ),
        (
            "sukuyo_compatibility",
            {"person1_date": "1990-06-15", "person2_date": "1992-03-20"},
            [
                "status",
                "person1",
                "person2",
                "person1_to_person2",
                "person2_to_person1",
                "rulesets",
                "validation",
            ],
        ),
        (
            "sukuyo_compatibility",
            {"person1_date": "2025-07-25", "person2_date": "2025-03-04"},
            ["status", "pair", "person1", "person2", "person1_to_person2", "rulesets"],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "2025-07-25",
                "person2_date": "2025-03-04",
                "leap_month_policy": "repeat_month",
            },
            ["status", "pair", "person1_to_person2", "person2_to_person1"],
        ),
        (
            "suzhan",
            {"date": "1954-11-25", "time": "12:00:00", "zone": "+08:00"},
            ["sukuyo", "rulesets", "params", "validation"],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "奎",
                "activity": "marriage",
            },
            [
                "astronomy",
                "sukuyo.activity_assessment",
                "sukuyo.calendar_day",
                "sukuyo.reading_text",
                "sukuyo.personal_day",
                "params",
            ],
        ),
        (
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "mansion_method": "legacy_equal28",
            },
            ["astronomy", "params", "sukuyo.day_mansion"],
        ),
    ],
)
def test_calendar_and_relations_across_all_real_transports(
    monkeypatch, capsys, key, payload, fields
):
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

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = [spec.tool_name]
    for name, value in payload.items():
        args += ["--" + name.replace("_", "-")]
        args += [str(v) for v in value] if isinstance(value, list) else [str(value)]
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
    assert not native.is_error, native.structured_content
    assert code == 0, cli
    payloads = [response.json(), native.structured_content, cli]
    for body in payloads:
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
    business = [
        {k: v for k, v in body.items() if k != "run_metadata"} for body in payloads
    ]
    assert business[0] == business[1] == business[2]
    assert native.structured_content == json.loads(native.content[0].text)


def test_discovery_exposes_calendar_evidence_and_typed_nested_contracts():
    for key in ("suzhan", "sukuyo_compatibility"):
        description = describe_spec(SPECS[key])
        assert description["evidence_views"] and description["call_guidance"]
        assert "SukuyoCalendar" in SPECS[key].output_model.model_json_schema()["$defs"]
    fields = SPECS["sukuyo_compatibility"].request_model.model_fields
    assert not fields["person1_time"].is_required()
    assert fields["leap_month_policy"].default == "unresolved"


def test_separator_catalogue_still_computes_all_real_transports(
    monkeypatch, capsys, tmp_path
):
    from fatebridge.core import guolao

    catalogue = tmp_path / "catalogue;copy"
    catalogue.mkdir()
    for name in ["sefstars.txt", "sources.json"]:
        shutil.copy2(guolao.DATA / name, catalogue / name)
    monkeypatch.setattr(guolao, "DATA", catalogue)
    test_calendar_and_relations_across_all_real_transports(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": "2025-03-04", "time": "12:00:00", "zone": "+08:00", "szchart": 1},
        ["astronomy", "chart", "sukuyo", "params"],
    )
