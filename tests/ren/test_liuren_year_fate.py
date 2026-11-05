"""Original diagram positions, birth-year convention and faithful delivery."""

import asyncio
import importlib.util
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_year_fate import build_year_fate
from fatebridge.services.metaphysics import calculate_liureng_runyear
from fatebridge.utils.birth_input import create_person_info
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.evaluation.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_fault,
)
from tests.ren.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "year_fate_audit", ROOT / "scripts/ren/audit_liuren_year_fate.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def source_board(profile="tanyuan_xieji_v1"):
    return build_liureng_board(
        AUDIT.symbolic_seed(), month_general_override="亥", guiren_profile=profile
    )


def facts(board=None, birth=1941, annual="己酉"):
    return build_year_fate(
        board or source_board(),
        day_ganzhi="甲辰",
        birth_lunar_year=birth,
        runyear_ganzhi=annual,
    )


def test_complete_frozen_tables_and_single_diagram_keep_separate_denominators():
    report = AUDIT.audit()
    assert report["literal_runyear_count"] == report["literal_runyear_matches"] == 120
    assert len(report["literal_natal_definition_checks"]) == 2
    assert report["source_diagram_count"] == 1
    assert report["source_diagram_position_matches"] == 3
    assert not report["failures"]
    assert report["selected_excerpt_checks_passed"]
    assert not report["classical_acceptance_passed"]
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["goal_complete"]


def test_year_fate_and_upper_xun_stems_are_distinct_and_lookup_is_not_inverted():
    male = facts()
    female = facts(annual="己丑")
    assert male["natal"] == female["natal"]
    assert male["natal"]["subject_ganzhi"] == "辛巳"
    assert male["natal"]["upper_ganzhi"] == "癸丑"
    assert male["natal"]["upper_relation"] == "妻财"
    assert male["annual"]["subject_ganzhi"] == "己酉"
    assert male["annual"]["upper_ganzhi"] == "乙巳"
    assert male["annual"]["upper_relation"] == "子孙"
    assert female["annual"]["upper_ganzhi"] == "己酉"
    assert female["annual"]["upper_relation"] == "官鬼"
    # The inverse lookup would select earth 酉 for natal sky 巳.
    assert male["natal"]["earth_branch"] == "巳"
    assert male["natal"]["sky_branch"] == "丑"


@pytest.mark.parametrize("profile", ["tanyuan_xieji_v1", "liuren_common_v1"])
def test_existing_board_is_the_only_source_of_sky_and_god_and_is_not_mutated(profile):
    board = source_board(profile)
    before = deepcopy(board)
    result = facts(board)
    for key in ("natal", "annual"):
        item = result[key]
        row = next(
            r
            for r in board["twelve_board"]
            if r["earth_branch"] == item["earth_branch"]
        )
        assert item["sky_branch"] == row["sky_branch"] and item["god"] == row["god"]
    assert board == before
    assert result["guiren_profile"] == profile


@pytest.mark.parametrize(
    "birth,earth,sky,upper_empty,earth_empty",
    [(2002, "午", "寅", True, False), (1998, "寅", "戌", False, True)],
)
def test_upper_empty_and_earth_empty_are_independent(
    birth, earth, sky, upper_empty, earth_empty
):
    item = facts(birth=birth)["natal"]
    assert item["earth_branch"] == earth and item["sky_branch"] == sky
    assert item["upper_xun_kong"] is upper_empty
    assert item["earth_xun_kong"] is earth_empty
    assert (item["upper_dun_stem"] is None) is upper_empty
    assert (item["upper_ganzhi"] is None) is upper_empty
    # Empty sky branches still have a branch, a god and a phase relation.
    assert item["god"] and item["upper_relation"]


def test_unknown_gender_keeps_natal_and_does_not_fabricate_annual():
    result = facts(annual=None)
    assert result["natal"]["status"] == "calculated"
    annual = result["annual"]
    assert annual["status"] == "not_calculated"
    assert all(v is None for k, v in annual.items() if k not in ("status", "reason"))


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_frozen_source_tamper_does_not_create_a_pass(tmp_path, change):
    corpus = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "reference.json"
    if change == "edit":
        data = json.loads(p.read_text())
        data["diagram"]["placements"][0]["sky_branch"] = "酉"
        p.write_text(json.dumps(data))
    elif change == "missing":
        p.unlink()
    else:
        (corpus / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen year-fate"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("bad", [True, "1941", None])
def test_birth_year_cannot_be_a_boolean_or_coerced_value(bad):
    with pytest.raises(ValueError):
        facts(birth=bad)


def test_duplicate_earth_plate_and_invalid_day_or_year_are_rejected():
    board = source_board()
    board["twelve_board"][1] = board["twelve_board"][0]
    with pytest.raises(ValueError, match="天地盘"):
        facts(board)
    with pytest.raises(ValueError, match="有效干支"):
        facts(annual="甲丑")
    with pytest.raises(ValueError, match="占日干支"):
        build_year_fate(
            source_board(),
            day_ganzhi="甲丑",
            birth_lunar_year=1941,
            runyear_ganzhi=None,
        )


@pytest.mark.parametrize("day,natal", [(7, "癸卯"), (10, "甲辰")])
@pytest.mark.parametrize("gender", ["女", "未知"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_lunar_birth_year_and_placements_agree_on_all_surfaces(
    day, natal, gender, project, rest, tmp_path, capsys
):
    spec = SPECS["liureng_runyear"]
    payload = dict(
        PAYLOAD,
        birth_year=2024,
        birth_month=2,
        birth_day=day,
        birth_hour=12,
        birth_timezone="Asia/Shanghai",
        gender=gender,
    )
    fields = ["runyear.year_fate", "runyear.ganzhi", "liureng.twelve_board"]
    params = [("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        yf = body["runyear"]["year_fate"]
        assert yf["natal"]["subject_ganzhi"] == natal
        assert yf["original_pdf_pages"] == [70, 71, 72, 73]
        assert yf["annual"]["status"] == (
            "calculated" if gender == "女" else "not_calculated"
        )
        for key in ("natal", "annual"):
            item = yf[key]
            if item["status"] != "calculated":
                continue
            row = next(
                r
                for r in body["liureng"]["twelve_board"]
                if r["earth_branch"] == item["earth_branch"]
            )
            assert item["sky_branch"] == row["sky_branch"] and item["god"] == row["god"]
        if not project:
            assert f"本命干支{natal}书地盘{natal[1]}" in body["snapshot_text"]
            assert "不取出生四柱年柱" in body["snapshot_text"]
            assert body["runyear"]["source_section"] == "大六壬探原·卷上推演篇·年命"
            if gender == "未知":
                assert "行年落盘：未计算" in body["snapshot_text"]


def test_1900_prefix_keeps_1899_birth_lunar_year_for_natal():
    person = create_person_info(
        birth_year=1900,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="Asia/Shanghai",
        gender="未知",
    )
    result = calculate_liureng_runyear(
        person,
        analysis_year=1900,
        analysis_month=2,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    assert "error" not in result
    assert result["runyear"]["year_fate"]["natal"]["subject_ganzhi"] == "己亥"
    assert result["runyear"]["birth_lunar_year"] == 1899


def test_same_run_claims_do_not_substitute_natal_stem_for_upper_dun_stem(rest):
    spec = SPECS["liureng_runyear"]
    payload = dict(
        PAYLOAD,
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=12,
        birth_timezone="Asia/Shanghai",
        gender="女",
    )
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    assert response.status_code == 200
    body = response.json()
    item = body["runyear"]["year_fate"]["natal"]
    receipt = body["run_metadata"]
    claim = CalculationClaim(
        path="runyear.year_fate.natal.upper_ganzhi",
        value=item["upper_ganzhi"],
        run_id=receipt["run_id"],
        business_output_sha256=receipt["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(body, [claim])["status"]
        == "verified_structured_facts"
    )
    assert item["subject_ganzhi"] != item["upper_ganzhi"]
    wrong = claim.model_copy(update={"value": item["subject_ganzhi"]})
    assert verify_calculation_claims(body, [wrong])["status"] == "rejected"


@pytest.mark.parametrize(
    "payload",
    [
        {"runyear": {"year_fate": {"natal": {"upper_xun_kong": 0}}}},
        {"runyear": {"year_fate": {"annual": {"status": "assumed_male"}}}},
        {"runyear": {"year_fate": {"ruleset_id": "all_books_certified"}}},
    ],
)
def test_invalid_facts_cannot_be_hidden_with_projection(
    payload, rest, monkeypatch, tmp_path, capsys
):
    reject_fault("liureng_runyear", payload, rest, monkeypatch, tmp_path, capsys)
