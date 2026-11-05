"""Printed conflicts stay unresolved; comparable major-star placements are audited."""

import asyncio
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.audit_ziwei_days as days_audit
from fatebridge.cli import run
from fatebridge.core.ziwei_sources import ziwei_day_source_evidence
from fatebridge.mcp_server import create_mcp_app


def test_primary_day_tables_separate_coverage_conflicts_and_derived_cases():
    result = days_audit.audit_day_tables()
    assert result["printed_label_occurrences"] == 150
    assert result["unambiguous_direct_grid_positions"] == 147
    assert result["prose_derived_cases"] == 1
    assert result["unresolved_bureau_day_inputs"] == 2
    assert result["source_comparable_chart_count"] == 296
    assert result["derived_major_star_positions_checked"] == 4144
    assert not result["mismatches"]
    assert not result["classical_day_table_acceptance_passed"]
    assert not result["all_150_direct_grid_positions_verified"]
    assert not result["whole_book_acceptance_passed"]
    assert result["manual_reader_count"] == 1
    assert result["conflicting_grid_days"] == [
        {
            "bureau": 3,
            "day": 12,
            "candidates": [
                {"branch": "辰", "printed_label": "十二"},
                {"branch": "巳", "printed_label": "十二"},
            ],
        }
    ]


def test_original_transcription_and_unresolved_printed_conflicts_are_retained():
    root = days_audit.FIXTURES / "naj_ming_day_tables_v1"
    source = json.loads((root / "collation.json").read_text())
    initial = (root / "collation-pre-adjudication.json").read_bytes()
    assert hashlib.sha256(initial).hexdigest() == source["initial_collation_sha256"]
    draft = json.loads((root / "wood3-manual-before-comparison.json").read_text())
    assert "十一" in draft["literal_days_by_branch"]["巳"]
    final = next(t for t in source["tables"] if t["bureau"] == 3)
    assert "十二" in final["literal_days_by_branch"]["巳"]
    assert "十二" in final["literal_days_by_branch"]["辰"]
    assert source["post_comparison_adjudication_ledger"]


@pytest.mark.parametrize("day,branch", [(11, "辰"), (12, "巳")])
def test_matching_one_candidate_cannot_resolve_a_printed_conflict(day, branch):
    evidence = ziwei_day_source_evidence(bureau=3, lunar_day=day, actual_branch=branch)
    assert evidence["actual_ziwei_branch"] == branch
    assert evidence["expected_ziwei_branch"] is None
    assert evidence["matches_source_record"] is None
    assert evidence["source_kind"].startswith("unresolved_")
    if day == 12:
        assert {c["branch"] for c in evidence["source_candidates"]} == {"辰", "巳"}


def test_water_21_is_a_prose_derivation_and_never_a_direct_printed_match():
    evidence = ziwei_day_source_evidence(bureau=2, lunar_day=21, actual_branch="亥")
    assert evidence["matches_source_record"]
    assert evidence["printed_day_labels"] == []
    assert evidence["source_kind"] == "prose_derived_with_unresolved_grid_label"
    assert evidence["printed_label_unresolved"]
    assert "順行一宮安二日" in evidence["source_quote"]
    direct = ziwei_day_source_evidence(bureau=2, lunar_day=20, actual_branch="亥")
    assert direct["source_kind"] == "direct_grid_cell"
    assert direct["printed_day_labels"] == ["二十", "廿"]
    assert not ziwei_day_source_evidence(bureau=3, lunar_day=5, actual_branch="酉")[
        "matches_source_record"
    ]


def test_audit_detects_a_wrong_secondary_major_star_not_just_the_ziwei_anchor(
    monkeypatch,
):
    original = days_audit.build_ziwei_chart

    def move_wuqu(*args, **kwargs):
        chart = original(*args, **kwargs)
        for i, palace in enumerate(chart["palaces"]):
            match = next(
                (s for s in palace["stars_detail"] if s["name"] == "武曲"), None
            )
            if match:
                palace["stars_detail"].remove(match)
                chart["palaces"][(i + 1) % 12]["stars_detail"].append(match)
                break
        return chart

    monkeypatch.setattr(days_audit, "build_ziwei_chart", move_wuqu)
    result = days_audit.audit_day_tables()
    assert result["status"] == "failed"
    assert (
        len([d for d in result["mismatches"] if d["case"].startswith("major_stars/")])
        == 296
    )


def test_rewriting_runtime_source_data_cannot_change_frozen_readings(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-days.json"
    data = json.loads((days_audit.ROOT / name).read_text())
    row = next(r for r in data["records"] if (r["bureau"], r["day"]) == (3, 5))
    row["branch"] = "酉"
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(days_audit, "ROOT", tmp_path)
    result = days_audit.audit_day_tables()
    assert any(d["case"] == "production_source_data/3/5" for d in result["mismatches"])


def test_source_glyph_adjudication_requires_the_actual_image_bytes(tmp_path):
    destination = tmp_path / "checkout/tests/data/ziwei_independent"
    source = days_audit.FIXTURES / "naj_ming_day_tables_v1"
    copied = destination / source.name
    copied.mkdir(parents=True)
    manifest = json.loads((source / "checksums.json").read_text())
    shutil.copy2(source / "checksums.json", copied)
    for item in manifest["files"]:
        target = copied / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / item["path"], target)
    glyph = copied / "wood-si-label.jpg"
    glyph.write_bytes(glyph.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming day-table source checksum mismatch"):
        days_audit.audit_day_tables(destination)


@pytest.mark.parametrize("day", [11, 12])
def test_unresolved_source_expectations_survive_real_rest_mcp_and_cli(
    monkeypatch, capsys, day
):
    # 1984-04-11/12 00:00 Shanghai = lunar third month 11/12, resolved wood-three.
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=1984,
        birth_month=4,
        birth_day=day,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        rule_profile="quanshu_v2_excerpt",
    )
    options = dict(
        fields=["ziwei_birth.rule_trace"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("fields", "ziwei_birth.rule_trace"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", options["as_of"]),
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool("ziwei_birth", {**inputs, **options})

    native = asyncio.run(call())
    assert not native.is_error
    args = ["ziwei_birth"]
    for key, value in inputs.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.extend(
        [
            "--fields",
            "ziwei_birth.rule_trace",
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--as-of",
            options["as_of"],
        ]
    )
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {key: value for key, value in p.items() if key != "run_metadata"}
        for p in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    trace = next(
        t
        for t in bodies[0]["ziwei_birth"]["rule_trace"]
        if t["rule_id"] == "ziwei_tianfu_placement"
    )
    assert trace["inputs"] == {"lunar_day": day, "ju_number": 3}
    comparison = trace["outputs"]["source_comparison"]
    assert comparison["expected_ziwei_branch"] is None
    assert comparison["matches_source_record"] is None
