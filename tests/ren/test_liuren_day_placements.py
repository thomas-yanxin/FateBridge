"""Literal source scope, same-board evidence and actual local transports."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_day_placements import (
    day_placement_patterns,
    day_placements_trace,
)
from fatebridge.core.output_liuren_day_placements import LiurenDayPlacements
from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.ren.audit_liuren_day_placements import CORPUS, expected_facts, reference
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.ren.test_liuren_ordered_patterns import raw

ROOT = Path(__file__).resolve().parents[2]
DATA = reference()
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))


def sky(rotation):
    branches = "子丑寅卯辰巳午未申酉戌亥"
    return {b: branches[(i + rotation) % 12] for i, b in enumerate(branches)}


def test_complete_independent_reference_keeps_all_twelve_headings():
    for case in DATA["contexts"]:
        value = day_placement_patterns(case["day_ganzhi"], case["sky_by_earth"])
        expected = expected_facts(case, DATA["reading"])
        assert {k: value[k] for k in expected} == expected
        assert len(value["evaluations"]) == 12
        assert value["evaluated_count"] == 10 and value["unresolved_count"] == 2
        assert [r["matched"] for r in value["evaluations"][-2:]] == [None, None]
        LiurenDayPlacements.model_validate(value)
    assert len(DATA["contexts"]) == 720


@pytest.mark.parametrize(
    "day,rotation,yes,no",
    [
        ("甲子", 2, ["D01"], ["D02", "D03", "D04"]),
        ("甲子", 10, ["D02"], ["D01", "D03"]),
        ("甲午", 4, ["D03"], ["D04"]),
        ("甲午", 8, ["D04"], ["D03"]),
        ("甲申", 6, ["D05", "D06"], ["D07", "D08"]),
        ("乙丑", 9, ["D07"], ["D09", "D08"]),
        ("乙丑", 3, ["D08"], ["D10", "D07"]),
        ("己未", 0, ["D09", "D10"], ["D07", "D08"]),
        (
            "甲子",
            0,
            [],
            ["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"],
        ),
    ],
)
def test_direction_and_stem_phase_discriminators(day, rotation, yes, no):
    value = day_placement_patterns(day, sky(rotation))
    assert set(yes) <= set(value["matched_ids"])
    assert not set(no) & set(value["matched_ids"])
    if day == "乙丑":
        assert value["day_stem_house"] == "辰" and value["day_stem_element"] == "木"
        assert value["element_relations"]["stem_controls_branch"] is True


@pytest.mark.parametrize("fault", ["bytes", "coordinated_rehash", "extra", "missing"])
def test_reference_identity_cannot_be_rewritten(tmp_path, fault):
    folder = tmp_path / "source"
    shutil.copytree(CORPUS, folder)
    path = folder / "reference.json"
    if fault in ("bytes", "coordinated_rehash"):
        path.write_text(path.read_text() + " ")
        if fault == "coordinated_rehash":
            from scripts.ren.audit_liuren_day_placements import sha

            manifest = json.loads((folder / "freeze.json").read_text())
            manifest["files"]["reference.json"] = sha(path)
            (folder / "freeze.json").write_text(json.dumps(manifest))
    elif fault == "extra":
        (folder / "extra.json").write_text("{}")
    else:
        path.unlink()
    with pytest.raises(ValueError):
        reference(folder)


@pytest.mark.parametrize(
    "day,mapping",
    [
        (None, sky(0)),
        ("甲丑", sky(0)),
        ("甲子", None),
        ("甲子", {}),
        ("甲子", {**sky(0), "子": []}),
        ("甲子", {**sky(0), "子": "丑"}),
        ("甲子", {**sky(0), "子": "丑", "丑": "子"}),
    ],
)
def test_invalid_day_or_noncyclic_board_is_not_guessed(day, mapping):
    with pytest.raises(ValueError):
        day_placement_patterns(day, mapping)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "phase",
        "house",
        "matched",
        "unknown",
        "numeric_bool",
        "prune",
        "reorder",
        "conformance",
    ],
)
def test_present_evidence_cannot_relabel_facts(fault):
    value = day_placement_patterns("乙丑", sky(9))
    if fault == "source":
        value["source_sha256"] = "invented"
    elif fault == "phase":
        value["day_stem_element"] = "土"
    elif fault == "house":
        value["day_stem_house"] = "卯"
    elif fault == "matched":
        value["matched_ids"] = []
    elif fault == "unknown":
        value["evaluations"][10]["matched"] = False
    elif fault == "numeric_bool":
        value["evaluations"][0]["matched"] = 0
    elif fault == "prune":
        value["evaluations"].pop()
    elif fault == "reorder":
        value["evaluations"].reverse()
    else:
        value["complete_classical_conformance"] = 0
    with pytest.raises(ValidationError):
        LiurenDayPlacements.model_validate(value)


def test_sparse_projection_keeps_only_observed_facts_and_unknowns():
    LiurenDayPlacements.model_validate({"matched_ids": ["D01"]})
    LiurenDayPlacements.model_validate(
        {"evaluations": [{"name": c["name"]} for c in DATA["reading"]["clauses"]]}
    )


@pytest.mark.parametrize(
    "value",
    [
        {"matched_ids": ["D11"]},
        {"matched_ids": ["invented"]},
        {"element_relations": {"invented_relation": True}},
    ],
)
def test_sparse_facts_cannot_invent_relation_keys_or_adjudicate_unknowns(value):
    with pytest.raises(ValidationError):
        LiurenDayPlacements.model_validate(value)


@pytest.fixture(scope="module")
def original_results():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        return {
            k: raw(k)
            for k in ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
        }


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "foreign_consistent",
        "trace",
        "duplicate",
        "old_version",
        "unknown_false",
        "numeric_bool",
    ],
)
def test_full_output_binds_evidence_to_actual_board_and_one_trace(
    original_results, key, fault
):
    value = copy.deepcopy(original_results[key])
    board = value["liureng"]
    evidence = board["day_placement_patterns"]
    trace = next(
        t
        for t in board["rule_trace"]
        if t["rule_id"] == "liuren.day_placement_patterns"
    )
    if fault in ("missing", "old_version"):
        board.pop("day_placement_patterns")
        if fault == "old_version":
            board["ruleset"]["version"] = "0.0.0"
    elif fault == "foreign_consistent":
        day = "乙丑" if evidence["day_ganzhi"] != "乙丑" else "甲子"
        fake = day_placement_patterns(day, evidence["sky_by_earth"])
        board["day_placement_patterns"] = fake
        trace.update(day_placements_trace(fake))
    elif fault == "trace":
        board["rule_trace"].remove(trace)
    elif fault == "duplicate":
        board["rule_trace"].append(copy.deepcopy(trace))
    elif fault == "unknown_false":
        evidence["evaluations"][10]["matched"] = False
    else:
        evidence["placements"]["stem_over_branch"] = int(
            evidence["placements"]["stem_over_branch"]
        )
    with pytest.raises(ValueError):
        require_complete_ren_anchors(key, value)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_real_rest_mcp_cli_return_same_new_facts(key, project, rest, tmp_path, capsys):
    spec = SPECS[key]
    path = "liureng.day_placement_patterns"
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [
            ("fields", path),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options.update(fields=[path], strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        value = body["liureng"]["day_placement_patterns"]
        assert len(value["evaluations"]) == 12 and value["unresolved_ids"] == [
            "D11",
            "D12",
        ]


@pytest.mark.parametrize("project", [False, True])
def test_broken_evidence_is_rejected_before_projection_on_all_ports(
    project, rest, monkeypatch, tmp_path, capsys
):
    key = "liureng_gods"
    spec = SPECS[key]
    value = raw(key)
    value["liureng"]["day_placement_patterns"]["evaluations"][0]["matched"] = not value[
        "liureng"
    ]["day_placement_patterns"]["evaluations"][0]["matched"]
    fake = replace(spec, bind=lambda _: (lambda: copy.deepcopy(value), (), {}))
    original = execution.execute_spec

    def broken(actual, request):
        return original(fake if actual.key == key else actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        options.update(fields=["four_pillars"], strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOADS[key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[key], **options))
    code, cli = call_cli(spec, PAYLOADS[key], tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code != 0
