"""Image-based annotation corrections must not alter chart calculations."""

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
import fatebridge.core.ziwei_conditions as conditions
import scripts.ziwei.audit_ziwei_conditions as audit
from fatebridge.application.result_delivery import RESULT_STORE
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.output_chinese import ZiweiConditionSourceRevision
from fatebridge.mcp_server import create_mcp_app
from scripts.ziwei.audit_ziwei_conditions import FIXTURES, revised_condition_source
from scripts.ziwei.audit_ziwei_limits import _seed


def test_two_corrections_and_one_dispute_keep_original_readings():
    source, revision = revised_condition_source()
    package = conditions._source()
    assert package["clauses"] == source["clauses"]
    assert package["source_revision"] == revision
    assert package["version"] == "1.1.0"
    prior = FIXTURES / "naj_ming_conditions_v1/collation.json"
    assert (
        hashlib.sha256(prior.read_bytes()).hexdigest()
        == revision["prior_collation_sha256"]
    )
    rows = {r["id"]: r for r in source["clauses"]}
    fubi = rows["fubi_flank_ming"]
    assert "九月十一月" in fubi["annotation"]
    assert "九月十月" in fubi["annotation_revision"]["prior_annotation"]
    kuiyue = rows["kuiyue_flank_ming"]
    assert kuiyue["annotation"] == "如命安在辰宮魁在卯鉞在巳宮是也"
    assert "加吉方論" in kuiyue["annotation_revision"]["prior_annotation"]
    disputed = rows["ziwei_fubi_conjunction"]
    assert disputed["annotation"] is None
    assert len(set(disputed["annotation_revision"]["reader_annotations"])) == 2
    assert (
        disputed["annotation_revision"]["status"]
        == "unresolved_after_independent_rereading"
    )


@pytest.mark.parametrize(
    "name",
    [
        "first_blind_read_frozen.json",
        "ziwei-r25-conditions-glyph-peer-review.json",
        "naj_0059_left_lower_native_region.jpg",
    ],
)
def test_source_revision_requires_actual_frozen_evidence(tmp_path, name):
    shutil.copytree(
        FIXTURES / "naj_ming_conditions_r25_v1", tmp_path / "naj_ming_conditions_r25_v1"
    )
    shutil.copytree(
        FIXTURES / "naj_ming_conditions_r25_v2", tmp_path / "naj_ming_conditions_r25_v2"
    )
    path = tmp_path / "naj_ming_conditions_r25_v2" / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="rereading checksum mismatch"):
        revised_condition_source(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("external_human_experts", 1),
        ("new_witnesses", 1),
        ("numeric_or_geometric_rules_modified", True),
        ("whole_book_acceptance_passed", True),
    ],
)
def test_public_source_receipt_rejects_unearned_certification(field, value):
    with pytest.raises(ValidationError):
        ZiweiConditionSourceRevision.model_validate({field: value})


@pytest.mark.parametrize(
    "kind",
    [
        "missing_image",
        "prior_fingerprint",
        "primary_freeze",
        "reader_metadata",
        "peer_columns",
        "predecessor",
        "peer_ownership",
    ],
)
def test_revision_rejects_self_rehashed_contradictory_evidence(tmp_path, kind):
    for folder in [
        "naj_ming_conditions_v1",
        "naj_ming_conditions_r25_v1",
        "naj_ming_conditions_r25_v2",
    ]:
        shutil.copytree(FIXTURES / folder, tmp_path / folder)
    folder = tmp_path / "naj_ming_conditions_r25_v2"
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changed = None
    if kind == "missing_image":
        manifest["files"].pop("naj_0059_left_lower_native_region.jpg")
    elif kind == "predecessor":
        manifest["prior_evidence_manifest_sha256"] = "0" * 64
    elif kind == "reader_metadata":
        manifest.update(isolated_model_readers=0, external_human_experts=20)
    elif kind == "prior_fingerprint":
        changed = folder / "corrections.json"
        data = json.loads(changed.read_text())
        data["prior_compiled_sha256"] = "0" * 64
    elif kind == "primary_freeze":
        changed = folder / "ziwei-r25-conditions-independent-review.json"
        data = json.loads(changed.read_text())
        data["independence"]["freeze"]["sha256"] = "0" * 64
    elif kind == "peer_columns":
        changed = folder / "ziwei-r25-conditions-glyph-peer-review.json"
        data = json.loads(changed.read_text())
        data["targets"][0]["small_note_columns"][0]["raw"] = "FORGED"
    else:
        changed = folder / "ziwei-r25-conditions-glyph-peer-review.json"
        data = json.loads(changed.read_text())
        data["targets"][0]["small_note_columns"][0][
            "belongs_to_large_text"
        ] = "紫府夾命"
    if changed is not None:
        changed.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        manifest["files"][changed.name] = hashlib.sha256(
            changed.read_bytes()
        ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    with pytest.raises(ValueError, match="Ming condition"):
        revised_condition_source(tmp_path)


def test_audit_checks_all_public_source_and_record_fields(monkeypatch):
    original_source = audit.revised_condition_source
    original_build = audit.build_ziwei_chart

    def bounded_source(fixtures=FIXTURES):
        source, revision = original_source(fixtures)
        source["conditional_grid"].update(years=[1984], months=[9], hours=[0])
        return source, revision

    def forged(*args, **kwargs):
        chart = original_build(*args, **kwargs)
        evidence = chart["ming_structural_conditions"]
        evidence.update(source="https://invalid.example/forged", manual_reader_count=99)
        for index, record in zip(evidence["index"], evidence["records"], strict=True):
            record.update(
                source_frame=999,
                geometry_rule="FORGED",
                source_literal_example_matches=True,
                ming_branch_requirement_met=False,
                year_stem_requirement_met=False,
                literal_example={"ming": "子", "positions": {}},
                missing_or_duplicated_stars=["FORGED"],
            )
            for key in index:
                index[key] = deepcopy(record[key])
        return chart

    monkeypatch.setattr(audit, "revised_condition_source", bounded_source)
    monkeypatch.setattr(audit, "build_ziwei_chart", forged)
    report = audit.audit_conditions()
    assert report["conditional_chart_inputs"] == 60
    assert (
        len(report["differences"]) == 360
    )  # sixty metadata and three hundred record failures


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_text_corrections_preserve_numeric_chart_and_geometric_premises(
    profile, monkeypatch
):
    revised = deepcopy(conditions._source())
    original = json.loads(
        (FIXTURES / "naj_ming_conditions_v1/collation.json").read_text()
    )
    former = {**deepcopy(revised), "clauses": original["clauses"]}
    for year, month, day, hour in [
        (1984, 9, 1, "子"),
        (1992, 11, 12, "丑"),
        (2024, 10, 21, "午"),
    ]:
        seed = _seed(year, month, day, hour)
        monkeypatch.setattr(conditions, "_source", lambda: revised)
        after = build_ziwei_chart(seed, "男", rule_profile=profile)
        monkeypatch.setattr(conditions, "_source", lambda: former)
        before = build_ziwei_chart(seed, "男", rule_profile=profile)
        after_conditions = after.pop("ming_structural_conditions")
        before_conditions = before.pop("ming_structural_conditions")
        assert after == before
        for a, b in zip(
            after_conditions["records"], before_conditions["records"], strict=True
        ):
            for key in (
                "geometry_match",
                "evaluated_necessary_premises_match",
                "source_literal_example_matches",
                "actual_occurrences",
            ):
                assert a[key] == b[key]
            assert a["full_traditional_judgment"] is None
            assert a["source_outcome_claim_adopted"] is False


def _verified_conditions(reply):
    assert len(json.dumps(reply, ensure_ascii=False, separators=(",", ":"))) <= 8192
    delivery = reply.get("result_delivery")
    if delivery is None:
        return reply["ziwei_birth"]["ming_structural_conditions"]
    offset, parts = 0, []
    while True:
        page = RESULT_STORE.verified_page(
            delivery["result_id"],
            delivery["sha256"],
            reply["run_metadata"]["run_id"],
            offset=offset,
            path="ziwei_birth.ming_structural_conditions",
        )
        parts.append(page["text"])
        offset = page["next_offset"]
        if offset is None:
            break
    return json.loads("".join(parts))


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_corrected_and_disputed_annotations_survive_rest_mcp_cli(
    profile, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=1992,
        birth_month=10,
        birth_day=1,
        birth_hour=12,
        birth_timezone="Asia/Shanghai",
        gender="未知",
        use_true_solar_time=False,
        rule_profile=profile,
    )
    flags = dict(
        fields=["ziwei_birth.ming_structural_conditions"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
        as_of="2026-10-22T12:00:00+08:00",
    )
    params = [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in flags.items()
        if k != "fields"
    ]
    params.append(("fields", flags["fields"][0]))
    response = TestClient(api.app).post(
        "/api/cn/ziwei/birth", json=inputs, params=params
    )
    assert response.status_code == 200, response.text

    async def native():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool("ziwei_birth", {**inputs, **flags})
            assert not result.is_error
            return result.structured_content

    args = ["ziwei_birth"]
    for key, value in inputs.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--fields",
        *flags["fields"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "8192",
        "--as-of",
        flags["as_of"],
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    receipts = [
        _verified_conditions(r) for r in (response.json(), asyncio.run(native()), cli)
    ]
    assert receipts[0] == receipts[1] == receipts[2]
    receipt = receipts[0]
    assert receipt["source_revision"]["external_human_experts"] == 0
    assert receipt["source_revision"]["numeric_or_geometric_rules_modified"] is False
    assert receipt["records"][1]["source_annotation"] is None
    assert "加吉方論" not in receipt["records"][3]["source_annotation"]
    assert "九月十一月" in receipt["records"][4]["source_annotation"]
