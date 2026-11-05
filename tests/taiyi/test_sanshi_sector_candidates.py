"""Source sectors are alternatives, never a selected four-corner lodging."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.metaphysics import liureng, sanshi_correspondences
from fatebridge.core.output_sanshi import SanshiSynthesis
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.taiyi import audit_taiyi_dangshi_case as source_audit
from scripts.taiyi.audit_taiyi_dangshi_case import audit
from scripts.taiyi.audit_taiyi_dangshi_case import source_readings as readings

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_dangshi_case_v41"
FREEZE = "aa2c0929a54a50f68b162cd7210e758b8b92a3f4036b858da3bad4ca8fe0b13f"


@pytest.mark.parametrize(
    "fault",
    [
        "original_case_freeze",
        "original_noble_freeze",
        "missing_source_binding",
        "reading_and_rehashed_manifest",
        "noble_rebinding_and_rehashed_case",
        "source_image_bytes",
    ],
)
def test_original_source_chain_rejects_replacement_and_coordinated_rehash(
    tmp_path, monkeypatch, fault
):
    noble_name = "tests/fixtures/taiyi_dangshi_noble_v40"
    case_name = "tests/fixtures/taiyi_dangshi_case_v41"
    for name in (noble_name, case_name):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in (noble_name, case_name):
        manifest = json.loads((ROOT / name / "freeze.json").read_text())
        for path in manifest["prior_sources"]:
            target = tmp_path / path
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, target)
    corpus = tmp_path / case_name
    noble = tmp_path / noble_name
    manifest = json.loads((corpus / "freeze.json").read_text())
    if fault in {"original_case_freeze", "original_noble_freeze"}:
        folder = corpus if fault == "original_case_freeze" else noble
        with (folder / "freeze-original.json").open("ab") as stream:
            stream.write(b" ")
    elif fault == "missing_source_binding":
        manifest["prior_sources"].pop(noble_name + "/siku-native-page57.png")
    elif fault == "reading_and_rehashed_manifest":
        path = corpus / "readings.json"
        data = json.loads(path.read_text())
        data["manual_conditional_board_expected"][0]["god"] = "青龙"
        path.write_text(json.dumps(data))
        manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif fault == "noble_rebinding_and_rehashed_case":
        path = noble / "freeze.json"
        data = json.loads(path.read_text())
        data["files"].pop("ming-native-page24.png")
        path.write_text(json.dumps(data))
        manifest["prior_sources"][noble_name + "/freeze.json"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    else:
        with (noble / "siku-native-page57.png").open("ab") as stream:
            stream.write(b"changed")
    (corpus / "freeze.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(source_audit, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="changed"):
        readings(corpus)


def test_corner_lists_both_actual_branches_without_selecting_a_god():
    source = readings()
    board = {"twelve_board": source["manual_conditional_board_expected"]}
    helper = getattr(sanshi_correspondences, "liuren_at_taiyi_palace", None)
    assert helper is not None
    row = helper(9, board)
    assert row["status"] == "not_assessed"
    assert "god" not in row and "earth_branch" not in row
    assert [r["earth_branch"] for r in row["sector_candidates"]] == ["辰", "巳"]
    assert [r["god"] for r in row["sector_candidates"]] == ["勾陈", "青龙"]


def test_pure_ren_layout_can_use_the_source_context_without_inventing_a_ce_date():
    source = readings()
    helper = getattr(liureng, "twelve_god_layout", None)
    assert helper is not None
    args = source["conditional_inputs"]
    layout = helper(
        day_stem=args["day_stem"],
        hour_branch=args["hour_branch"],
        month_general_branch=args["month_general_branch"],
        is_diurnal=args["is_diurnal"],
    )
    assert layout["noble_start_branch"] == "丑"
    assert layout["noble_earth_branch"] == "子"
    assert layout["is_reverse"] is False
    for row in source["manual_conditional_board_expected"]:
        assert layout["sky_by_earth"][row["earth_branch"]] == row["sky_branch"]
        assert layout["god_by_sky"][row["sky_branch"]] == row["god"]


@pytest.mark.parametrize(
    "number,branches", [(1, "戌亥"), (3, "丑寅"), (7, "未申"), (9, "辰巳")]
)
def test_all_four_corners_preserve_both_branches_and_actual_paths(number, branches):
    source = readings()
    rows = list(reversed(source["manual_conditional_board_expected"]))
    original = deepcopy(rows)
    result = sanshi_correspondences.liuren_at_taiyi_palace(
        number, {"twelve_board": rows}
    )
    assert result["status"] == "not_assessed"
    assert result["candidate_scope"] == "same_sector_branches_not_adjudicated_lodging"
    assert not {"earth_branch", "sky_branch", "god", "source_path"} & result.keys()
    assert [r["earth_branch"] for r in result["sector_candidates"]] == list(branches)
    for candidate in result["sector_candidates"]:
        index = int(candidate["source_path"].rsplit(".", 1)[1])
        assert {k: v for k, v in candidate.items() if k != "source_path"} == rows[index]
    assert rows == original


@pytest.mark.parametrize("branch", list("丑寅辰巳未申戌亥"))
@pytest.mark.parametrize("failure", ["missing", "duplicate"])
def test_either_bad_corner_branch_rejects_the_join(branch, failure):
    rows = deepcopy(readings()["manual_conditional_board_expected"])
    number = next(
        n
        for n, branches in sanshi_correspondences.SECTOR_BRANCHES.items()
        if branch in branches
    )
    target = next(r for r in rows if r["earth_branch"] == branch)
    rows.remove(target) if failure == "missing" else rows.append(target)
    with pytest.raises(ValueError, match="唯一的六壬实际地盘"):
        sanshi_correspondences.liuren_at_taiyi_palace(number, {"twelve_board": rows})


@pytest.mark.parametrize("number,branch", [(8, "子"), (4, "卯"), (2, "午"), (6, "酉")])
def test_cardinal_is_still_one_exact_actual_row(number, branch):
    rows = readings()["manual_conditional_board_expected"]
    result = sanshi_correspondences.liuren_at_taiyi_palace(
        number, {"twelve_board": rows}
    )
    index = next(i for i, row in enumerate(rows) if row["earth_branch"] == branch)
    assert result == {
        "status": "direct_branch_match",
        "source_path": f"liureng.twelve_board.{index}",
        **rows[index],
    }


def test_center_keeps_no_branch_candidates_or_lodging():
    result = sanshi_correspondences.liuren_at_taiyi_palace(5, {"twelve_board": []})
    assert result == {"status": "not_assessed", "reason": "中宫无直接地支，不自动寄坤"}


@pytest.mark.parametrize("number", [True, False, "9", None, 0, 10])
def test_bad_palace_does_not_coerce_to_a_branch(number):
    with pytest.raises(ValueError, match="实际太乙宫数"):
        sanshi_correspondences.liuren_at_taiyi_palace(number, {"twelve_board": []})


@pytest.mark.parametrize(
    "field,value",
    [
        ("hour_branch", "寅卯"),
        ("month_general_branch", ""),
        ("day_stem", "庚申"),
        ("is_diurnal", 1),
        ("is_diurnal", None),
        ("guiren_profile", "best"),
    ],
)
def test_pure_layout_requires_explicit_symbolic_conditions(field, value):
    args = dict(
        hour_branch="寅", month_general_branch="卯", day_stem="庚", is_diurnal=True
    )
    args[field] = value
    with pytest.raises(ValueError):
        liureng.twelve_god_layout(**args)


def test_source_case_preserves_edition_difference_and_unselected_lodging():
    report = audit()
    assert report["source_freeze_sha256"] == FREEZE
    assert report["core_matching_rows"] == len(report["core_rows"]) == 10
    assert report["automatic_modern_diurnal_for_source_hour"]["is_diurnal"] is False
    for control in report["controls"]:
        ming, siku = control["editions"]
        if control["is_diurnal"]:
            assert (ming["compatible_rows"], ming["unique_direct_matching_rows"]) == (
                5,
                2,
            )
            assert (siku["compatible_rows"], siku["unique_direct_matching_rows"]) == (
                4,
                1,
            )
        else:
            assert ming["compatible_rows"] == siku["compatible_rows"] == 1
        assert ming["unselected_lodging_rows"] == siku["unselected_lodging_rows"] == 3
        assert siku["rows"][-1]["source_literal"] == "天定"
        assert siku["rows"][-1]["status"] == "unrecognized_source_literal"
        assert not ming["whole_case_passed"] and not siku["whole_case_passed"]
    assert not report["whole_goal_complete"] and report["new_model_invocations"] == 0
    assert report["new_complete_dated_joint_cases_passed"] == 0


def test_collation_keeps_the_facsimile_variant_separate_from_an_emendation():
    review = audit()["source_collation"]
    variant = review["literal_variant"]
    assert review["source_case_freeze_sha256"] == FREEZE
    assert variant["readings"] == {"ming": "天空", "siku": "天定"}
    assert variant["siku_emendation_candidate"] == "天空"
    assert variant["candidate_status"] == "plausible_emendation_not_adopted_as_literal"
    assert not variant["same_god_alias_attested_in_reviewed_passages"]
    assert not variant["frozen_reading_overwritten"]
    witnesses = {row["id"]: row for row in review["witnesses"]}
    assert witnesses["ming_case"]["literal"] == "客參將在天空下"
    assert witnesses["siku_case"]["literal"] == "客參將在天定下"
    assert witnesses["ming_god_roster"]["literal"] == "後六天空土"
    assert witnesses["siku_same_leaf_parallel"]["literal"] == "常侍玄命在天空"


def test_known_case_reverse_constraints_never_select_a_production_lodging():
    report = audit()
    review = report["source_collation"]["lodging_review"]
    assert review["unrepresented_palaces"] == [1, 3, 5]
    assert not review["independent_general_lodging_rule_found"]
    assert not review["production_lodging_selected"]
    for control in report["controls"]:
        if not control["matches_explicit_source_morning_condition"]:
            assert (
                control["control_role"] == "predeclared_modern_night_negative_control"
            )
            continue
        assert control["control_role"] == "explicit_source_morning_condition"
        ming, siku = control["editions"]
        # Read the existing hand board: 巳→午/青龙, 申→酉/太常,
        # 卯→辰/六合, 午→未/天空. These are reverse constraints,
        # not a newly established four-corner rule or independent cases.
        assert [row["source_constrained_earth_branches"] for row in ming["rows"]] == [
            ["巳"],
            ["巳"],
            ["申"],
            ["卯"],
            ["午"],
        ]
        assert siku["rows"][-1]["source_constrained_earth_branches"] == []
        assert siku["rows"][-1]["normalized_source_god"] is None
        for edition in (ming, siku):
            for row in edition["rows"][:3]:
                assert row["unselected_lodging"]
                assert row["actual"]["status"] == "not_assessed"
                assert not {"earth_branch", "god"} & row["actual"].keys()
            assert not edition["whole_case_passed"]


@pytest.mark.parametrize("fault", ["case_commitment", "page_commitment", "literal"])
def test_collation_rejects_rebound_sources_and_silent_literal_correction(
    tmp_path, monkeypatch, fault
):
    source = readings()
    shutil.copyfile(CORPUS / "freeze-original.json", tmp_path / "freeze-original.json")
    review = json.loads((CORPUS / "collation.json").read_text())
    if fault == "case_commitment":
        review["source_case_freeze_sha256"] = "0" * 64
    elif fault == "page_commitment":
        review["witnesses"][1]["sha256"] = "0" * 64
    else:
        review["literal_variant"]["readings"]["siku"] = "天空"
    (tmp_path / "collation.json").write_text(json.dumps(review))
    # Isolate the new collation boundary after verifying the unchanged raw case.
    monkeypatch.setattr(source_audit, "source_readings", lambda: source)
    monkeypatch.setattr(source_audit, "CORPUS", tmp_path)
    with pytest.raises(ValueError, match="changed|replaced"):
        audit()


@pytest.fixture(scope="module")
def actual():
    return calculate_sanshiunited_analysis(
        date="2026-06-21",
        time="17:00:02",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": "hour"},
    )


def test_actual_snapshot_and_export_keep_both_candidates_and_the_limitation(actual):
    SanshiSynthesis.model_validate(actual["synthesis"])
    section = next(
        s for s in actual["snapshot_export"]["sections"] if s["title"] == "三式宫位对应"
    )
    assert section["included"] is True
    assert (
        "未选寄支" in section["content"]
        and section["content"] in actual["snapshot_text"]
    )
    for row in actual["synthesis"]["palace_correspondences"]["entries"]:
        for candidate in row["liureng"].get("sector_candidates", []):
            index = int(candidate["source_path"].rsplit(".", 1)[1])
            assert all(
                candidate[k] == actual["liureng"]["twelve_board"][index][k]
                for k in ("earth_branch", "sky_branch", "god")
            )
            assert (
                f"地盘{candidate['earth_branch']}／天盘{candidate['sky_branch']}／{candidate['god']}"
                in section["content"]
            )
    assert (
        actual["synthesis"]["palace_correspondences"]["joint_judgment"]
        == "not_implemented"
    )


def test_join_reads_modified_actual_facts_instead_of_recalculating_or_ranking(actual):
    ren = deepcopy(actual["liureng"])
    for row in ren["twelve_board"]:
        if row["earth_branch"] == "辰":
            row["god"] = "独立算路检验值"
    row = sanshi_correspondences.liuren_at_taiyi_palace(9, ren)
    assert [c["god"] for c in row["sector_candidates"]][0] == "独立算路检验值"
    assert row["status"] == "not_assessed" and "god" not in row


def test_projection_rejects_bad_candidate_types():
    with pytest.raises(ValidationError):
        SanshiSynthesis.model_validate(
            {
                "palace_correspondences": {
                    "entries": [
                        {"liureng": {"sector_candidates": [{"earth_branch": 9}]}}
                    ]
                }
            }
        )


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
@pytest.mark.parametrize("mode", ["year", "hour"])
def test_sector_candidates_survive_rest_mcp_cli_projection(
    monkeypatch, capsys, profile, mode
):
    spec = next(s for s in CATALOG if s.key == "sanshiunited")
    fields = ["synthesis.palace_correspondences", "synthesis.time_scopes"]
    payload = dict(
        date="2026-06-21",
        time="17:00:02",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": mode},
        liureng_guiren_profile=profile,
        liureng_is_diurnal=True,
    )
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-06-21T17:00:02+08:00",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", opts["as_of"]),
        ],
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "sanshiunited", {**payload, **opts}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    protocol = asyncio.run(invoke())
    argv = ["sanshiunited"]
    for key, value in payload.items():
        argv += [
            "--" + key.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    argv += [
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--as-of",
        opts["as_of"],
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in (response.json(), protocol, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    entries = bodies[0]["synthesis"]["palace_correspondences"]["entries"]
    assert any(len(r["liureng"].get("sector_candidates", [])) == 2 for r in entries)


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
def test_default_mcp_budget_keeps_same_run_sector_candidates(profile):
    from fatebridge.application.examples import suggested_fields
    from tests.taiyi.test_taiyi_transports import _same_run_payload

    spec = next(s for s in CATALOG if s.key == "sanshiunited")

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "sanshiunited",
                dict(
                    date="2026-06-21",
                    time="17:00:02",
                    zone="+08:00",
                    use_true_solar_time=False,
                    taiyi_options={"calculation_mode": "hour"},
                    liureng_guiren_profile=profile,
                    fields=suggested_fields(spec, view="palace_correspondences"),
                    strict_fields=True,
                    include_snapshot_text=False,
                ),
                raise_on_error=False,
            )
            body = await _same_run_payload(client, result)
            entries = body["synthesis"]["palace_correspondences"]["entries"]
            assert any(
                len(r["liureng"].get("sector_candidates", [])) == 2 for r in entries
            )
            assert all(
                r["liureng"]["status"] == "not_assessed"
                for r in entries
                if r["taiyi_number"] in {1, 3, 7, 9}
            )

    asyncio.run(invoke())
