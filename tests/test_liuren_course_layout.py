"""Necessary layout sets are not predicate matches, full classes or forecasts."""

import asyncio
import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_course_conditions import course_conditions
from fatebridge.core.metaphysics.liureng_course_layout import pair_layout_necessity
from fatebridge.core.output_liuren_course_conditions import LiurenCourseConditions
from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.audit_liuren_course_conditions import transmissions
from scripts.audit_liuren_course_layout import CORPUS, audit, reference
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_liuren_ordered_patterns import raw

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = json.loads((ROOT / "tests/fixtures/ren_anchors_v1/faults.json").read_text())[
    "payloads"
]


@pytest.fixture(autouse=True)
def native_solar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))


def test_primary_anchors_and_entire_supported_layout_space():
    result = audit()
    assert result["engineering_checks_passed"] and not result["failures"]
    assert len(result["literal_peak_anchors"]) == 10
    assert (
        result["new_common_noble_anchors"]
        == result["reused_tanyuan_noble_anchors"]
        == 20
    )
    assert len(result["derived_pair_rows"]) == 120
    assert len(result["orientation_contexts"]) == 960
    assert result["actual_layout_count"] == 5760
    assert not result["chongwei_compatible_stems"]
    assert all(r["layout_union_passed"] for r in result["derived_pair_rows"])
    assert result["authorial_intent_adjudicated"] is None
    assert result["full_classical_conformance"] is result["goal_complete"] is False
    assert (
        result["new_historical_events"]
        == result["new_empirical_events"]
        == result["new_model_processes"]
        == 0
    )


@pytest.mark.parametrize(
    "stem,peak", tuple(zip("甲乙丙丁戊己庚辛壬癸", "卯寅午巳午巳酉申子亥"))
)
def test_chongwei_zero_is_explained_by_a_necessary_condition(stem, peak):
    result = pair_layout_necessity(stem, "帝旺", "贵人")
    assert result["required_stage_branch"] == peak
    assert peak not in result["possible_god_branches"]
    assert result["compatible_in_any_supported_noble_layout"] is False


def test_symbolic_literal_match_does_not_fabricate_a_reachable_board():
    value = course_conditions("甲子", transmissions(["卯", "寅", "卯"], "贵人", "子"))
    row = value["stage_god_patterns"][4]
    assert row["id"] == "S05" and row["matched"] is True
    assert row["compatible_in_any_supported_noble_layout"] is False
    assert (
        value["layout_compatibility_basis"]["is_initial_transmission_guarantee"]
        is False
    )
    assert value["layout_compatibility_basis"]["authorial_intent_adjudicated"] is None
    LiurenCourseConditions.model_validate(value)


@pytest.mark.parametrize("fault", ["manifest", "bytes", "extra", "missing"])
def test_primary_reference_cannot_be_relabelled(fault, tmp_path):
    target = tmp_path / "reference"
    # Copy small annotations and symlink the untouched, read-only large scans.
    # No operation in this test mutates a PDF or its target.
    target.mkdir()
    for f in CORPUS.iterdir():
        if f.suffix == ".pdf":
            (target / f.name).symlink_to(f.resolve())
        else:
            shutil.copy2(f, target / f.name)
    if fault == "manifest":
        (target / "freeze.json").write_text("{}")
    elif fault == "bytes":
        with (target / "readings.json").open("ab") as handle:
            handle.write(b" ")
    elif fault == "extra":
        (target / "extra").write_text("")
    else:
        (target / "gugong-419.pdf").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        reference(target)


@pytest.mark.parametrize(
    "fault",
    [
        "stage_branch",
        "god_set",
        "compatible",
        "numeric_bool",
        "source",
        "profile",
        "daynight",
        "guarantee",
        "intent",
        "rewrite",
    ],
)
def test_present_layout_claims_cannot_be_substituted(fault):
    value = course_conditions("甲子", transmissions(["辰", "寅", "卯"], "天后", "子"))
    row = value["stage_god_patterns"][4]
    basis = value["layout_compatibility_basis"]
    if fault == "stage_branch":
        row["required_stage_branch"] = "丑"
    elif fault == "god_set":
        row["possible_god_branches"].append("卯")
    elif fault == "compatible":
        row["compatible_in_any_supported_noble_layout"] = True
    elif fault == "numeric_bool":
        row["compatible_in_any_supported_noble_layout"] = 0
    elif fault == "source":
        basis["witnesses"][0]["source_sha256"] = "fake"
    elif fault == "profile":
        basis["noble_profiles"].reverse()
    elif fault == "daynight":
        basis["diurnal_alternatives"] = [True]
    elif fault == "guarantee":
        basis["is_initial_transmission_guarantee"] = True
    elif fault == "intent":
        basis["authorial_intent_adjudicated"] = True
    else:
        basis["original_conditions_rewritten"] = True
    with pytest.raises(ValidationError):
        LiurenCourseConditions.model_validate(value)


def test_sparse_projection_does_not_invent_a_missing_day():
    LiurenCourseConditions.model_validate(
        {
            "stage_god_patterns": [
                {"compatible_in_any_supported_noble_layout": False} for _ in range(12)
            ]
        }
    )
    LiurenCourseConditions.model_validate(
        {"layout_compatibility_basis": {"authorial_intent_adjudicated": None}}
    )


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_real_ports_keep_matches_and_necessary_conditions_distinct(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    path = "liureng.transmission_relations.course_conditions"
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
        value = body["liureng"]["transmission_relations"]["course_conditions"]
        row = value["stage_god_patterns"][4]
        assert (
            row["matched"] is False
            and row["compatible_in_any_supported_noble_layout"] is False
        )
        assert value["layout_compatibility_basis"][
            "unresolved_authorial_intent_ids"
        ] == ["S05"]


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize(
    "field",
    [
        "layout_compatibility_basis",
        "required_stage_branch",
        "possible_god_branches",
        "compatible_in_any_supported_noble_layout",
    ],
)
def test_complete_gate_requires_same_day_layout_evidence(key, field):
    value = raw(key)
    course = value["liureng"]["transmission_relations"]["course_conditions"]
    if field == "layout_compatibility_basis":
        course.pop(field)
    else:
        course["stage_god_patterns"][4].pop(field)
    with pytest.raises(ValueError):
        require_complete_ren_anchors(key, value)


@pytest.mark.parametrize("project", [False, True])
def test_false_compatibility_fails_before_an_unrelated_projection(
    project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    value = raw(spec.key)
    value["liureng"]["transmission_relations"]["course_conditions"][
        "stage_god_patterns"
    ][4]["compatible_in_any_supported_noble_layout"] = True
    fake = replace(spec, bind=lambda _: (lambda: copy.deepcopy(value), (), {}))
    original = execution.execute_spec
    monkeypatch.setattr(
        execution,
        "execute_spec",
        lambda actual, request: original(
            fake if actual.key == spec.key else actual, request
        ),
    )
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", "four_pillars"), ("strict_fields", "true")]
        flags += ["--fields", "four_pillars", "--strict-fields", "true"]
        options.update(fields=["four_pillars"], strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOADS[spec.key], params=params)
    protocol = asyncio.run(native(spec, PAYLOADS[spec.key], **options))
    code, _ = call_cli(spec, PAYLOADS[spec.key], tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code != 0
