"""Full-payload integrity and independently disputed day-table receipts."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.ziwei_sources import ziwei_day_source_evidence
from fatebridge.mcp_server import create_mcp_app
from scripts.ziwei.audit_ziwei_review_disclosure import audit_review_disclosure
from scripts.ziwei.build_ziwei_review_disclosure import TARGET, build
from tests.support.result_delivery import store


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


@pytest.mark.parametrize(
    "field", ["whole_day_table_certified", "external_human_experts"]
)
def test_review_audit_does_not_equate_json_booleans_and_integers(monkeypatch, field):
    import scripts.ziwei.audit_ziwei_review_disclosure as audit

    original = audit.ziwei_day_source_evidence

    def corrupted(**kwargs):
        value = original(**kwargs)
        value["independent_review"][field] = (
            0 if field == "whole_day_table_certified" else False
        )
        return value

    monkeypatch.setattr(audit, "ziwei_day_source_evidence", corrupted)
    assert len(audit.audit_review_disclosure()["mismatches"]) == 1800


def test_corrected_independent_rows_reach_all_150_public_receipts():
    expected = build()
    assert json.loads(TARGET.read_text()) == expected
    assert len(expected["records"]) == 150
    for row in expected["records"]:
        direct = row["branches_from_direct_labels"]
        for actual in "子丑寅卯辰巳午未申酉戌亥":
            receipt = ziwei_day_source_evidence(
                bureau=row["bureau"], lunar_day=row["day"], actual_branch=actual
            )
            review = receipt["independent_review"]
            assert review["status"] == row["status"]
            assert review["direct_label_branches"] == direct
            assert review["matches_unique_direct_branch"] == (
                actual == direct[0] if len(direct) == 1 else None
            )
            assert review["whole_day_table_certified"] is False
            assert review["external_human_experts"] == 0
    assert (
        hashlib.sha256(
            (TARGET.parent / "ziwei-naj-ming-days.json").read_bytes()
        ).hexdigest()
        == "4f19e3426fd3fcb03e2be94fdf8ad8121de0449f27d4d93cd9f38d308bc0634a"
    )


@pytest.mark.parametrize(
    "bureau,day,actual",
    [(2, 21, "亥"), (3, 11, "辰"), (3, 12, "辰"), (6, 6, "寅"), (6, 8, "未")],
)
def test_disputed_readings_cannot_become_unambiguous_by_matching_a_calculation(
    bureau, day, actual
):
    result = ziwei_day_source_evidence(
        bureau=bureau, lunar_day=day, actual_branch=actual
    )
    review = result["independent_review"]
    assert not review["unambiguous_after_rereading"]
    if (bureau, day) == (6, 8):
        assert review["matches_unique_direct_branch"] is True
        assert review["unresolved_label_candidates"] == ["寅"]
    else:
        assert review["matches_unique_direct_branch"] is None
    if (bureau, day) == (6, 6):
        assert result["source_kind"] == "direct_grid_cell"
        assert result["matches_source_record"] is True
        assert review["status"] == "unknown_no_directly_read_label"


def test_review_audit_detects_a_runtime_claim_that_hides_the_unknown(monkeypatch):
    import fatebridge.core.ziwei_sources as sources

    fake = copy.deepcopy(build())
    row = next(r for r in fake["records"] if (r["bureau"], r["day"]) == (6, 6))
    row["status"] = "directly_read_single_branch"
    row["branches_from_direct_labels"] = ["寅"]
    monkeypatch.setattr(sources, "_ming_day_review", lambda: fake)
    report = audit_review_disclosure()
    assert len(report["mismatches"]) == 12
    assert report["source_inputs"] == 150


@pytest.mark.parametrize("field", ["agrees_with_selected_branch", "method_id"])
def test_review_audit_rejects_every_corrupted_public_review_field(monkeypatch, field):
    import scripts.ziwei.audit_ziwei_review_disclosure as audit

    original = audit.ziwei_day_source_evidence

    def corrupted(**kwargs):
        value = original(**kwargs)
        value["independent_review"][field] = "invalid-review-value"
        return value

    monkeypatch.setattr(audit, "ziwei_day_source_evidence", corrupted)
    assert len(audit.audit_review_disclosure()["mismatches"]) == 1800


def test_review_audit_rejects_a_different_package_manifest_identity(
    tmp_path, monkeypatch
):
    import scripts.ziwei.audit_ziwei_review_disclosure as audit

    value = json.loads(TARGET.read_text())
    value["frozen_manifest_sha256"] = "0" * 64
    changed = tmp_path / TARGET.name
    changed.write_text(json.dumps(value))
    # Keep the unchanged original selected transcription beside this altered package.
    (tmp_path / "ziwei-naj-ming-days.json").write_bytes(
        (TARGET.parent / "ziwei-naj-ming-days.json").read_bytes()
    )
    monkeypatch.setattr(audit, "TARGET", changed)
    report = audit.audit_review_disclosure()
    assert report["source_inputs"] == 150
    assert len(report["mismatches"]) == 1


@pytest.mark.parametrize(
    "mutation", ["edition_false_as_zero", "experts_zero_as_false", "day_one_as_true"]
)
def test_review_audit_rejects_package_boolean_integer_substitutions(
    tmp_path, monkeypatch, mutation
):
    import scripts.ziwei.audit_ziwei_review_disclosure as audit

    value = json.loads(TARGET.read_text())
    if mutation == "edition_false_as_zero":
        value["new_edition"] = 0
    elif mutation == "experts_zero_as_false":
        value["external_human_experts"] = False
    else:
        for row in value["records"]:
            if row["day"] == 1:
                row["day"] = True
    changed = tmp_path / TARGET.name
    changed.write_text(json.dumps(value))
    (tmp_path / "ziwei-naj-ming-days.json").write_bytes(
        (TARGET.parent / "ziwei-naj-ming-days.json").read_bytes()
    )
    monkeypatch.setattr(audit, "TARGET", changed)
    report = audit.audit_review_disclosure()
    assert report["source_inputs"] == 150
    assert report["mismatches"] == [
        {"case": "packaged_reading_differs_from_frozen_report_and_erratum"}
    ]


@pytest.mark.parametrize("day,lunar_day", [(7, 6), (9, 8)])
@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_disputed_source_reaches_real_birth_rest_mcp_cli(
    store, monkeypatch, capsys, day, lunar_day, profile
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
        birth_day=day,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
        rule_profile=profile,
    )
    options = dict(
        fields=["ziwei_birth.rule_trace"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("fields", "ziwei_birth.rule_trace"),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "8192"),
            ("as_of", options["as_of"]),
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as c:
            result = await c.call_tool("ziwei_birth", {**inputs, **options})
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(call())
    args = ["ziwei_birth"]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--fields",
        "ziwei_birth.rule_trace",
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "8192",
        "--as-of",
        options["as_of"],
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    comparisons = []
    for reply in [rest.json(), native, cli]:
        assert len(canonical(reply)) <= 8192
        if "result_delivery" in reply:
            ref = reply["result_delivery"]
            payload = store.get(ref["result_id"])
            traces = payload["ziwei_birth"]["rule_trace"]
            index = next(
                i
                for i, t in enumerate(traces)
                if t["rule_id"] == "ziwei_tianfu_placement"
            )
            page = store.verified_page(
                ref["result_id"],
                reply["run_metadata"]["run_id"],
                path=f"ziwei_birth.rule_trace.{index}.outputs.source_comparison",
            )
            assert page["next_offset"] is None
            comparison = json.loads(page["text"])
        else:
            trace = next(
                t
                for t in reply["ziwei_birth"]["rule_trace"]
                if t["rule_id"] == "ziwei_tianfu_placement"
            )
            comparison = trace["outputs"]["source_comparison"]
        assert comparison["independent_review"]["unambiguous_after_rereading"] is False
        comparisons.append(comparison)
    assert comparisons[0] == comparisons[1] == comparisons[2]
    assert comparisons[0]["independent_review"]["matches_unique_direct_branch"] == (
        True if lunar_day == 8 else None
    )
