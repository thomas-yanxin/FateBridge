"""Related contract regressions with shared imports; original cases retained."""

import copy
import hashlib
import os
import shutil
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import ephemeris_runtime, guolao
from fatebridge.core import sukuyo_xuanying as xuanying
from fatebridge.core import sukuyo_zhidu_pointer_scope as scopes
from fatebridge.core.fixed_star_paths import fixed_star_search_path
from fatebridge.core.local_techniques import suzhan
from fatebridge.core.requests.divination import SuZhanRequest
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from fatebridge.core.sukuyo_sources import LoadedSource, load_source
from fatebridge.core.sukuyo_zhidu_calendar import SOURCE as LEGACY_SOURCE
from fatebridge.core.sukuyo_zhidu_calendar import zhidu_lines, zhidu_reference
from fatebridge.services.divination import calculate_suzhan_analysis
from scripts.sukuyo.check_sukuyo_xuanying import verify_primary
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as check_surfaces,
)
from tests.sukuyo.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize("relative_to_data", [False, True])
def test_long_catalogue_plus_operator_path_keeps_coordinates_and_configuration(
    monkeypatch, tmp_path, relative_to_data
):
    # Each directory is a valid native input, but concatenating both exceeds
    # the actual AS_MAXCH-1-13 limit in Swiss 2.10's swe_set_ephe_path().
    # macOS's pytest root happens to be longer than Linux's. Construct each
    # input at a declared byte length so both platforms actually exceed the
    # combined native limit, while either input remains individually valid.
    tail_bytes = 220 - len(os.fsencode(str(tmp_path.resolve()))) - 1
    assert tail_bytes > 0, "Test root already exceeds the intended input length"
    catalogue = tmp_path / ("c" * tail_bytes)
    operator = tmp_path / ("e" * tail_bytes)
    catalogue.mkdir()
    operator.mkdir()
    for name in ["sefstars.txt", "sources.json"]:
        shutil.copy2(guolao.DATA / name, catalogue / name)
    assert len(os.fsencode(str(catalogue.resolve()))) <= 242
    assert len(os.fsencode(str(operator.resolve()))) <= 242
    assert (
        len(
            os.fsencode(str(catalogue.resolve()) + os.pathsep + str(operator.resolve()))
        )
        > 242
    )
    previous = ephemeris_runtime.configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(operator))
    try:
        ephemeris_runtime.configure_ephemeris_path(str(operator))
        baseline = calculate_suzhan_analysis(
            date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
        )
        assert "error" not in baseline, baseline
        monkeypatch.setattr(guolao, "DATA", catalogue)
        if relative_to_data:
            monkeypatch.chdir(tmp_path)
        cwd = Path.cwd()
        with fixed_star_search_path(catalogue, str(operator)) as search:
            assert len(os.fsencode(search)) <= 242
            assert [Path(p).resolve() for p in search.split(os.pathsep)] == [
                catalogue.resolve(),
                operator.resolve(),
            ]
        actual = calculate_suzhan_analysis(
            date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
        )
        assert "error" not in actual, actual
        assert actual["astronomy"] == baseline["astronomy"]
        assert actual["chart"] == baseline["chart"]
        assert Path.cwd() == cwd
        assert os.environ["SE_EPHE_PATH"] == str(operator)
        assert ephemeris_runtime.configured_ephemeris_path() == str(operator)
    finally:
        monkeypatch.delenv("SE_EPHE_PATH")
        ephemeris_runtime.configure_ephemeris_path(previous)


def test_unsupported_compact_directory_links_fail_explicitly(monkeypatch, tmp_path):
    long_catalogue = tmp_path / ("a" * 100)
    long_operator = tmp_path / ("b" * 100)

    def denied(*args, **kwargs):
        raise OSError("synthetic platform denies directory links")

    monkeypatch.setattr(Path, "symlink_to", denied)
    with pytest.raises(ValueError, match="Cannot create compact fixed-star paths"):
        with fixed_star_search_path(long_catalogue, str(long_operator)):
            pytest.fail("A silent native default would use a different catalogue")


@pytest.mark.parametrize("separator", [";", ":"])
@pytest.mark.skipif(os.name == "nt", reason="Colon is not a Windows directory name")
def test_literal_catalogue_separator_is_not_a_native_search_list(
    monkeypatch, tmp_path, separator
):
    catalogue = tmp_path / ("catalogue" + separator + "copy")
    catalogue.mkdir()
    for name in ["sefstars.txt", "sources.json"]:
        shutil.copy2(guolao.DATA / name, catalogue / name)
    baseline = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
    )
    assert "error" not in baseline, baseline
    monkeypatch.setattr(guolao, "DATA", catalogue)
    cwd = Path.cwd()
    configured = ephemeris_runtime.configured_ephemeris_path()
    environment = os.environ.get("SE_EPHE_PATH")
    actual = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
    )
    assert "error" not in actual, actual
    assert actual["chart"] == baseline["chart"]
    assert actual["astronomy"] == baseline["astronomy"]
    assert Path.cwd() == cwd
    assert ephemeris_runtime.configured_ephemeris_path() == configured
    assert os.environ.get("SE_EPHE_PATH") == environment


@pytest.mark.skipif(os.name == "nt", reason="POSIX separator-bearing directory")
def test_separator_in_temporary_root_never_escapes_to_native_code(
    monkeypatch, tmp_path
):
    from fatebridge.core import fixed_star_paths

    temporary = tmp_path / "temporary;root"
    temporary.mkdir()

    @contextmanager
    def use_temporary(**kwargs):
        yield str(temporary)

    monkeypatch.setattr(fixed_star_paths, "TemporaryDirectory", use_temporary)
    with pytest.raises(ValueError, match="native search separator"):
        with fixed_star_search_path(tmp_path / "catalogue;copy", ""):
            pytest.fail("An ambiguous native search path must never be used")


@pytest.mark.parametrize("provided", [{}, {"time": None}])
def test_omitted_and_null_clock_do_not_call_any_astronomy_or_house_builder(
    monkeypatch, provided
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unknown clock reached physical sky or chart")

    for name in [
        "_build_local_chart_response",
        "_build_birth_info",
        "build_equatorial_mansions",
        "apply_equatorial_mansions",
    ]:
        monkeypatch.setattr(suzhan, name, forbidden)
    request = SuZhanRequest(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        natal_mansion="室",
        activity="travel",
        **provided,
    )
    result = suzhan.build_suzhan_result(**request.model_dump())
    assert result["input_normalized"]["time"] is None
    assert result["chart"] is None and result["astronomy"] is None
    assert result["params"]["birthTimeImputed"] is False
    assert result["params"]["coordinatesApplied"] is False
    assert result["validation"]["calculation_layers"] == {
        "calendar": "partial",
        "chart": "not_computed_birth_time_unknown",
        "astronomy": "not_computed_birth_time_unknown",
    }
    day = result["sukuyo"]
    assert day["calendar"]["birth_time_known"] is False
    assert day["day_mansion"] is None and day["personal_day"] is None
    assert [
        (r["day_mansion"], r["personal_day"]["relation"]["relation"])
        for r in day["candidate_mansion_days"]
    ] == [("星", "安"), ("张", "危")]
    assert "未知" in result["snapshot_text"]
    assert "已生成星图" not in result["summary"]
    assert "宫制：equal" not in result["snapshot_text"]


@pytest.mark.parametrize("clock", ["", " ", "\t"])
def test_blank_clock_is_invalid_rather_than_imputed_or_accepted_as_unknown(clock):
    with pytest.raises(ValueError, match="空字符串"):
        suzhan.build_suzhan_result(date="2024-08-04", time=clock)


@pytest.mark.parametrize("clock", ["not-time", "25:00:00", "12:00:60"])
def test_invalid_known_clock_is_not_downgraded_to_date_only(clock):
    result = calculate_suzhan_analysis(date="2024-08-04", time=clock, zone="+08:00")
    assert "error" in result


def test_request_schema_exposes_optional_clock_without_using_example_as_default():
    schema = SuZhanRequest.model_json_schema()
    assert "time" not in schema["required"]
    assert SuZhanRequest(date="2024-08-04").time is None
    assert SuZhanRequest(date="2024-08-04", time=None).time is None
    with pytest.raises(ValidationError):
        SuZhanRequest(date="2024-08-04", time=93000)


@pytest.mark.parametrize(
    "basis,date,zone",
    [
        ("chinese_hko_utc08", "2024-08-04", "Asia/Tokyo"),
        ("japanese_hutime_1002_1_utc09", "2017-06-24", "+08:00"),
        ("japanese_naoj_historical_utc09", "0806-09-20", "+08:00"),
        ("japanese_hutime_1002_1_utc09", "2031-01-22", "UTC"),
        ("japanese_naoj_historical_utc09", "0001-01-01", "+15:00"),
    ],
)
def test_public_date_only_retains_every_existing_calendar_and_day_branch(
    basis, date, zone
):
    expected_calendar = calendar_mansion(
        date, zone=zone, calendar_basis=basis, calendar_profile="hinoo_t1299_host27"
    )
    expected_day = day_evidence(
        expected_calendar, "室", "travel", ["personal_departure"]
    )
    result = calculate_suzhan_analysis(
        date=date,
        zone=zone,
        calendar_basis=basis,
        calendar_profile="hinoo_t1299_host27",
        natal_mansion="室",
        activity="travel",
        activity_details=["personal_departure"],
    )
    assert result["sukuyo"] == expected_day
    assert result["chart"] is None and result["astronomy"] is None
    if expected_calendar["out_of_range_calendar_dates"]:
        assert result["sukuyo"]["day_mansion"] is None
        assert not expected_calendar["profile_calculation"][
            "candidate_set_complete_under_declared_reconstructions"
        ]


def test_explicit_textual_half_does_not_establish_a_clock_or_physical_sky():
    result = calculate_suzhan_analysis(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert result["sukuyo"]["day_mansion"] == "星"
    assert result["sukuyo"]["calendar"]["birth_time_known"] is False
    assert result["chart"] is None and result["astronomy"] is None


def test_date_only_does_not_infer_a_natal_mansion_or_a_place():
    result = calculate_suzhan_analysis(
        date="2024-08-04",
        zone="+08:00",
        calendar_profile="hinoo_t1299_host27",
        activity="study",
        gps_lat=0,
        gps_lon=0,
    )
    assert result["sukuyo"]["personal_day"] is None
    assert all(
        r["personal_day"] is None for r in result["sukuyo"]["candidate_mansion_days"]
    )
    assert result["params"]["coordinatesApplied"] is False
    assert "birthLongitude" not in result["params"]


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"zone": "Asia/Tokyo"},
        {"calendar_day_part": "first_half"},
        {"calendar_day_part": "second_half"},
        {
            "date": "0806-09-20",
            "zone": "+08:00",
            "calendar_basis": "japanese_naoj_historical_utc09",
        },
        {
            "date": "2031-01-22",
            "zone": "UTC",
            "calendar_basis": "japanese_hutime_1002_1_utc09",
        },
    ],
)
def test_omitted_clock_across_all_surfaces(monkeypatch, capsys, extra):
    payload = {
        "date": "2024-08-04",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
        "activity": "travel",
        "natal_mansion": "室",
        **extra,
    }
    check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "input_normalized",
            "params",
            "chart",
            "astronomy",
            "sukuyo.calendar",
            "sukuyo.candidate_days",
            "sukuyo.candidate_mansion_days",
            "sukuyo.personal_day",
            "sukuyo.reading_text",
            "validation",
            "summary",
        ],
    )


def test_null_clock_rest_and_native_mcp_equal_cli_omission(monkeypatch, capsys):
    import asyncio
    import json

    from fastapi.testclient import TestClient
    from fastmcp import Client
    from jsonschema import Draft202012Validator

    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.mcp_server import create_mcp_app
    from tests.sukuyo.test_sukuyo_transports import AS_OF, SPECS

    spec = SPECS["suzhan"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = [
        "input_normalized",
        "params",
        "chart",
        "astronomy",
        "sukuyo",
        "validation",
        "summary",
    ]
    payload = {
        "date": "2024-08-04",
        "time": None,
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
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
            *[("fields", v) for v in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app()) as client:
            schemas = await client.list_tools()
            schema = next(t.inputSchema for t in schemas if t.name == spec.tool_name)
            assert "time" not in schema.get("required", [])
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--date",
            "2024-08-04",
            "--zone",
            "+08:00",
            "--calendar-profile",
            "hinoo_t1299_host27",
            "--as-of",
            AS_OF,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not native.is_error, native.structured_content
    assert code == 0, cli
    bodies = [response.json(), native.structured_content, cli]
    for body in bodies:
        assert body["input_normalized"]["time"] is None
        assert body["chart"] is None and body["astronomy"] is None
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
    stripped = [
        {k: v for k, v in body.items() if k != "run_metadata"} for body in bodies
    ]
    assert stripped[0] == stripped[1] == stripped[2]


@pytest.mark.parametrize(
    "key,payload,fields",
    [
        (
            "suzhan",
            {
                "date": "1903-06-25",
                "time": "12:00:00",
                "zone": "+08:00",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            [
                "sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "sukuyo.reading_text",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1903-06-25",
                "person1_time": "12:00:00",
                "person2_date": "1957-09-24",
                "person2_time": "12:00:00",
                "calendar_profile": "hinoo_t1299_host27",
                "person1_calendar_day_part": "first_half",
                "person2_calendar_day_part": "first_half",
            },
            [
                "person1.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "person2.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "candidate_relation_analysis",
                "summary",
            ],
        ),
    ],
)
def test_actual_transports_deliver_the_added_source_reference(
    monkeypatch, capsys, key, payload, fields
):
    _check_surfaces(monkeypatch, capsys, key, payload, fields)


def test_standalone_entry_does_not_inherit_branches_from_later_nested_gloss():
    result = commentarial_boundary_reference()
    direct = result["standalone_xuanying_reference"]
    assert direct["selected_juan"] == 8
    assert direct["selected_locator"] == "C056n1163_p0945b10-14"
    assert "二月八日鬼宿合時" in direct["selected_literal"]
    assert "二月九日曙夜分属九日" in direct["selected_literal"]
    assert "寅" not in direct["selected_literal"]
    assert "卯" not in direct["selected_literal"]
    context = direct["T2216_context"]
    assert context["direct_quote_name_variant"]["C1163_literal"] == "佛星"
    assert context["direct_quote_name_variant"]["T2216_literal"] == "弗星"
    assert not context["cited_exemplar_identity_established"]
    assert not context["C1163_juan8_and_T2216_inline_9_17_note_reconciled"]
    assert not direct["applied_to_calendar_or_clock"]
    assert not direct["interpretation_scope"]["all_T2216_nested_originals_acquired"]


def test_facsimile_selected_fragments_do_not_complete_the_unaccepted_glyph():
    result = commentarial_boundary_reference()["standalone_xuanying_reference"]
    physical = result["facsimile_reference"]
    assert physical["pdf_pages"] == 302
    assert physical["selected_pdf_page_one_based"] == 92
    assert physical["visible_added_zhuang_page_label"] == "383"
    assert "夜分屬九日故也" in physical["selected_image_clear_fragments"]
    assert physical["glyph_before_night"]["accepted_unique_glyph"] is None
    assert not physical["same_physical_exemplar_as_C1163_or_T2216_proved"]
    assert not physical["full_text_collation_completed"]


def test_changed_commentary_cannot_inherit_the_old_entry_binding():
    reference = commentarial_boundary_reference()
    reference["sources"][0]["capture_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="注疏来源不一致"):
        xuanying.standalone_reference(reference)


def test_detached_output_cannot_change_later_reference():
    first = commentarial_boundary_reference()
    first["standalone_xuanying_reference"]["selected_literal"] = "寅時換日"
    first["standalone_xuanying_reference"]["facsimile_reference"]["glyph_before_night"][
        "accepted_unique_glyph"
    ] = "曙"
    again = commentarial_boundary_reference()["standalone_xuanying_reference"]
    assert "寅時" not in again["selected_literal"]
    assert (
        again["facsimile_reference"]["glyph_before_night"]["accepted_unique_glyph"]
        is None
    )


def test_complete_reading_keeps_explicit_half_and_both_leap_reconstructions():
    calendar = calendar_mansion(
        "0806-07-23",
        "23:59:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    original = deepcopy(calendar)
    evidence = day_evidence(calendar)
    assert calendar == original
    assert evidence["calendar"]["candidate_su27s"] == ["星", "鬼"]
    assert evidence["day_mansion"] is None
    text = evidence["reading_text"]
    assert evidence["calendar"]["calendar_day_part"] == "first_half"
    assert "未写寅、卯钟界" in text
    assert "C1163作佛星，T2216此处作弗星" in text
    assert "章实等原本仍未取得" in text
    assert "夜字前一字的原图唯一字形未接纳" in text
    assert "所引音义、章实等原本尚未独立取得" not in text


@pytest.mark.parametrize("name", ["C1163", "T2216", "SINICA_PDF"])
def test_checker_rejects_substituted_actual_source_bytes(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="字节指纹不一致"):
        verify_primary({name: path})


def test_offline_checker_does_not_claim_to_have_read_source_bytes():
    result = verify_primary()
    assert result["actual_captures_rechecked"] == []
    assert not result["facsimile_glyph_uniquely_accepted"]
    assert not result["historical_clock_or_hinoo_priority_established"]


def test_modern_default_reports_actual_null_half_and_three_source_identities():
    evidence = day_evidence(calendar_mansion("2024-03-17", "12:00:00", "+08:00"))
    assert evidence["calendar"]["calendar_day_part"] is None
    text = evidence["reading_text"]
    assert "calendar_day_part=null（未声明）" in text
    assert "中華大藏經（中華書局版）數位版" in text
    assert "弘教書院排印之高麗藏本影印" in text
    assert "尚未认证为同一实物，也未证明谱系独立" in text


def test_pair_retains_source_chain_and_unconstrained_matrix():
    from fatebridge.services.divination import calculate_sukuyo_compatibility

    result = calculate_sukuyo_compatibility(
        person1_date="0814-08-23",
        person1_time="00:01:00",
        person1_zone="+09:00",
        person1_calendar_day_part="first_half",
        person2_date="0806-07-23",
        person2_time="23:59:00",
        person2_zone="+09:00",
        person2_calendar_day_part="first_half",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
    )
    reference = result["standalone_xuanying_reference"]
    assert (
        reference == commentarial_boundary_reference()["standalone_xuanying_reference"]
    )
    assert not reference["applied_to_calendar_or_clock"]
    assert "未写寅、卯钟界" in result["summary"]
    assert "未移动历日或主宿" in result["summary"]
    assert result["candidate_relation_analysis"]["unconstrained_rows"]


@pytest.mark.parametrize("date", ["2024-03-17", "2024-09-25"])
def test_standalone_source_reference_across_all_real_transports(
    monkeypatch, capsys, date
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {"date": date, "time": "04:30:00", "zone": "+08:00"},
        [
            "sukuyo.calendar_day.clock_doctrine.commentarial_boundary_reference.standalone_xuanying_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )


def test_original_source_and_numerical_controls_remain_unchanged():
    reference = zhidu_reference()
    assert hashlib.sha256(LEGACY_SOURCE.read_bytes()).hexdigest() == (
        "b140a869f1b4a13eb8e1ab72061160393118d17f9ee9b3867f08a1a80fc5d3c2"
    )
    assert reference["nominal_arithmetic"]["models"]["T1509"] == [
        {"slot_id": "month_1", "numerator": 61, "denominator": 2},
        {"slot_id": "month_2", "numerator": 30, "denominator": 1},
        {"slot_id": "month_3", "numerator": 914, "denominator": 31},
        {"slot_id": "month_4", "numerator": 1830, "denominator": 67},
    ]
    scope = reference["apparatus_pointer_scope"]
    assert scope["sources"]["T1509"]["own_local_locating_tokens"] == 71497
    assert scope["sources"]["T2122"]["own_local_locating_tokens"] == 72189
    assert (
        scope["sources"]["T1509"]["records_without_own_local_locating_tokens"] == 1513
    )
    assert scope["counting_policy"]["locating_attributes"] == ["target", "from", "to"]
    assert (
        "corresp"
        in scope["counting_policy"]["excluded_from_legacy_locating_denominator"]
    )
    assert (
        scope["sources"]["T1509"]["selected_reuse"]["corresp_matches_exact_xml_id"]
        is False
    )
    assert all(value is False for value in scope["interpretation_flags"].values())
    text = "\n".join(zhidu_lines(reference))
    assert "不能读成所有TEI关联均已认证" in text
    assert "两处app自身字位仍有可解析起讫" in text


@pytest.mark.parametrize("change", ["missing", "zero_for_false", "changed_count"])
def test_native_cannot_omit_or_coerce_the_current_scope(change):
    reference = zhidu_reference()
    if change == "missing":
        reference.pop("apparatus_pointer_scope")
    elif change == "zero_for_false":
        reference["apparatus_pointer_scope"]["interpretation_flags"][
            "all_TEI_associations_semantically_verified"
        ] = 0
    else:
        reference["apparatus_pointer_scope"]["sources"]["T1509"][
            "own_local_locating_tokens"
        ] = 71498
    with pytest.raises(ValueError, match="定位说明"):
        zhidu_lines(reference)


@pytest.mark.parametrize("change", ["flag", "missing_flag", "corresp", "scope"])
def test_even_a_new_review_digest_cannot_promote_association_scope(monkeypatch, change):
    loaded = load_source(scopes.SOURCE)
    data = loaded.data
    if change == "flag":
        data["interpretation_flags"][
            "all_TEI_associations_semantically_verified"
        ] = True
    elif change == "missing_flag":
        data["interpretation_flags"].pop("all_TEI_associations_semantically_verified")
    elif change == "corresp":
        data["sources"]["T1509"]["selected_reuse"][
            "corresp_matches_exact_xml_id"
        ] = True
    else:
        data["counting_policy"]["locating_attributes"].append("corresp")
    monkeypatch.setattr(scopes, "FACTS_SHA256", scopes._digest(data))
    monkeypatch.setattr(
        scopes, "load_source", lambda _: LoadedSource(data, loaded.sha256)
    )
    with pytest.raises(ValueError, match="不能"):
        zhidu_reference()


def test_returned_scope_is_detached_from_next_source_load():
    first = zhidu_reference()
    original = copy.deepcopy(first["apparatus_pointer_scope"])
    first["apparatus_pointer_scope"]["sources"]["T1509"][
        "own_local_locating_tokens"
    ] = 0
    assert zhidu_reference()["apparatus_pointer_scope"] == original


def test_bad_legacy_identity_cannot_be_bound_to_a_valid_scope():
    reference = zhidu_reference()
    with pytest.raises(ValueError, match="来源身份"):
        scopes.pointer_count_scope(reference["source_data"], "0" * 64)


@pytest.mark.parametrize("half", ["first_half", "second_half"])
def test_scope_and_native_qualification_reach_all_actual_local_adapters(
    monkeypatch, capsys, half
):
    path = (
        "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration."
        "daybreak_source_comparison.T2217_printed_collation."
        "subsequent_quotation_comparison.upstream_calendar_context."
        "apparatus_pointer_scope"
    )
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": "1903-06-25",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": half,
        },
        [path, "sukuyo.reading_text", "rulesets"],
    )
