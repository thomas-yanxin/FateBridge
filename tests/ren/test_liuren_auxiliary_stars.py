"""Literal anchors, plate inversion and faithful public 德禄马 facts."""

import asyncio
import copy
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_auxiliary_stars import build_auxiliary_stars
from fatebridge.core.output_liuren_auxiliary import LiurenAuxiliaryStars
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.ren.test_ren_classical_depth import AUDIT as REN
from tests.ren.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "auxiliary_audit", ROOT / "scripts/ren/audit_liuren_auxiliary_stars.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()


def synthetic():
    branches = AUDIT.BRANCHES
    return dict(
        day_ganzhi="乙丑",
        month_branch="寅",
        sky_by_earth={b: branches[(i + 3) % 12] for i, b in enumerate(branches)},
        god_by_sky=dict(zip(branches, AUDIT.GODS)),
        lessons=[dict(index=i + 1, upper_branch=b) for i, b in enumerate("申申亥亥")],
        transmissions=list("申亥申"),
    )


def test_literal_labels_and_derived_denominators_stay_separate():
    result = AUDIT.audit()
    assert result["literal_table_entries"] == result["literal_anchor_match_count"] == 80
    assert result["reused_lu_entries"] == 10
    assert result["synthetic_contexts"] == 8640
    assert (
        result["derived_position_checks"]
        == result["derived_position_match_count"]
        == 60480
    )
    assert len(result["civil_probes"]) == 2 and all(
        p["matched"] for p in result["civil_probes"]
    )
    assert not result["failures"] and result["selected_excerpt_checks_passed"]
    assert result["new_historical_examples"] == result["new_real_world_outcomes"] == 0
    assert result["goal_complete"] is result["classical_acceptance_passed"] is False


def test_removing_one_rule_cannot_improve_the_audit(monkeypatch):
    import fatebridge.core.metaphysics.liureng_auxiliary_stars as implementation

    original = implementation.build_auxiliary_stars

    def missing_rule(**kwargs):
        result = original(**kwargs)
        result["stars"].pop()
        return result

    monkeypatch.setattr(implementation, "build_auxiliary_stars", missing_rule)
    result = AUDIT.audit()
    assert not result["selected_excerpt_checks_passed"]
    assert result["synthetic_contexts"] == 8640
    assert result["derived_position_checks"] == 51840
    assert len(result["failures"]) == 8640


@pytest.mark.parametrize("mode", ["edit", "missing", "extra"])
def test_frozen_inventory_cannot_hide_or_change_a_label(tmp_path, mode):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if mode == "edit":
        path = target / "reference.json"
        ref = json.loads(path.read_text())
        ref["tables"]["day_de"]["乙"] = "卯"
        path.write_text(json.dumps(ref))
    elif mode == "missing":
        (target / "source-pages.pdf").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen auxiliary-star"):
        AUDIT.reference(target)


def test_yin_de_is_not_its_own_lu_and_heaven_de_uses_explicit_lodging():
    actual = build_auxiliary_stars(**synthetic())
    stars = {s["id"]: s for s in actual["stars"]}
    assert stars["day_de"]["branch"] == "申" and stars["day_lu"]["branch"] == "卯"
    assert stars["heaven_de"]["source_token"] == "丁未"
    assert stars["heaven_de"]["branch"] == "未"  # 丁禄午 must not replace 原表丁未.
    assert stars["day_de"]["earth_branch"] == "巳"  # Inverse, not sky[申]=亥.
    assert stars["day_de"]["lesson_indices"] == [1, 2]
    assert stars["day_de"]["transmission_positions"] == ["initial", "final"]
    assert stars["day_de"]["on_day_stem"] and not stars["day_de"]["on_day_branch"]
    assert actual["complete_classical_conformance"] is False
    args = {**synthetic(), "day_ganzhi": "丁卯"}
    stars = {s["id"]: s for s in build_auxiliary_stars(**args)["stars"]}
    assert stars["day_de"]["branch"] == "亥" and stars["day_lu"]["branch"] == "午"


@pytest.mark.parametrize(
    "fault", ["day", "month", "plate", "rotation", "gods", "lessons", "transmissions"]
)
def test_incomplete_or_impossible_inputs_are_rejected(fault):
    args = synthetic()
    if fault == "day":
        args["day_ganzhi"] = "甲丑"
    elif fault == "month":
        args["month_branch"] = "寅卯"
    elif fault == "plate":
        args["sky_by_earth"].pop("子")
    elif fault == "rotation":
        p = args["sky_by_earth"]
        p["子"], p["丑"] = p["丑"], p["子"]
    elif fault == "gods":
        args["god_by_sky"]["子"] = "螣蛇"
    elif fault == "lessons":
        args["lessons"][0]["index"] = 2
    else:
        args["transmissions"] = ["甲", "丑", "寅"]
    with pytest.raises(ValueError):
        build_auxiliary_stars(**args)


def test_empty_lu_retains_its_position_and_does_not_cancel_stage():
    seed = REN.make_seed({"day": "戊戌", "hour": "酉"})
    boards = [
        build_liureng_board(seed, month_general_override="子", guiren_profile=p)
        for p in ("liuren_common_v1", "tanyuan_xieji_v1")
    ]
    anchors = []
    for board in boards:
        aux = board["auxiliary_stars"]
        LiurenAuxiliaryStars.model_validate(aux)
        lu = next(s for s in aux["stars"] if s["id"] == "day_lu")
        assert lu["branch"] == "巳" and lu["xun_kong"]
        assert lu["ganzhi"] is lu["dun_stem"] is None
        assert lu["day_stem_life_stage"] == "临官"
        anchors.append(
            [(s["id"], s["branch"], s["earth_branch"]) for s in aux["stars"]]
        )
        assert (
            next(
                t
                for t in board["rule_trace"]
                if t["rule_id"] == "liuren.tanyuan_auxiliary_stars"
            )["result"]
            == aux
        )
    assert anchors[0] == anchors[1]


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_auxiliary_facts_agree_on_rest_mcp_cli(
    key, project, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = dict(PAYLOAD)
    if key == "jinkou":
        payload["di_fen"] = "酉"
    elif key == "liureng_runyear":
        payload.update(
            birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="女"
        )
    fields = [
        "liureng.auxiliary_stars",
        "liureng.twelve_board",
        "liureng.four_lessons",
        "liureng.three_transmissions",
        "four_pillars",
    ]
    params = [("response_char_limit", "0"), ("as_of", AS_OF)]
    flags = ["--response-char-limit", "0"]
    options = {}
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
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    bodies = [http.json(), protocol.structured_content, cli]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        spec.output_model.model_validate(body)
        b = body["liureng"]
        aux = b["auxiliary_stars"]
        assert (
            len(aux["stars"]) == 7
            and aux["source_sha256"] == REFERENCE["source_sha256"]
        )
        assert (
            aux["day_ganzhi"]
            == body["four_pillars"]["day"]["stem"]
            + body["four_pillars"]["day"]["branch"]
        )
        for star in aux["stars"]:
            seat = next(
                r for r in b["twelve_board"] if r["sky_branch"] == star["branch"]
            )
            assert (
                star["earth_branch"] == seat["earth_branch"]
                and star["god"] == seat["god"]
            )
            assert star["lesson_indices"] == [
                l["index"]
                for l in b["four_lessons"]
                if l["upper_branch"] == star["branch"]
            ]
            assert star["transmission_positions"] == [
                p
                for p in ("initial", "middle", "final")
                if b["three_transmissions"][p]["branch"] == star["branch"]
            ]
        if not project and key != "jinkou":
            assert (
                "日德：" in body["snapshot_text"] and "天马：" in body["snapshot_text"]
            )
            assert aux["month_basis"] in body["snapshot_text"]
    if key != "jinkou":
        assert "liureng.auxiliary_stars" in evidence_views(spec)["core"]["fields"]


@pytest.mark.parametrize(
    "fault",
    [
        "full_claim",
        "numeric_claim",
        "duplicate",
        "missing",
        "wrong_branch",
        "wrong_boolean",
    ],
)
@pytest.mark.parametrize("project", [False, True])
def test_corrupt_auxiliary_facts_fail_before_projection(
    fault, project, rest, monkeypatch, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    from fatebridge.services.metaphysics import calculate_liureng_gods

    valid = calculate_liureng_gods(**PAYLOAD)
    execution.validate_output(spec, valid)
    bad = copy.deepcopy(valid)
    aux = bad["liureng"]["auxiliary_stars"]
    if fault == "full_claim":
        aux["complete_classical_conformance"] = True
    elif fault == "numeric_claim":
        aux["complete_classical_conformance"] = 0
    elif fault == "duplicate":
        aux["stars"][0]["id"] = aux["stars"][1]["id"]
    elif fault == "missing":
        aux["stars"].pop()
    elif fault == "wrong_branch":
        aux["stars"][0]["branch"] = "甲"
    else:
        aux["stars"][0]["xun_kong"] = "false"
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
        options.update(fields=["analysis_type"], strict_fields=True)
    http = rest.post(spec.rest_path, json=PAYLOAD, params=params)
    protocol = asyncio.run(native(spec, PAYLOAD, **options))
    code, out = call_cli(spec, PAYLOAD, tmp_path, capsys, flags=flags)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert out["error_code"] == "internal_error"


@pytest.mark.parametrize(
    "field",
    [
        "liureng.auxiliary_stars.stars",
        "liureng.auxiliary_stars.nominal_month",
        "liureng.auxiliary_stars.complete_classical_conformance",
    ],
)
def test_sparse_object_projections_survive(field, rest, tmp_path, capsys):
    spec = SPECS["liureng_gods"]
    options = dict(fields=[field], strict_fields=True, include_snapshot_text=False)
    http = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=dict(
            fields=field,
            strict_fields="true",
            include_snapshot_text="false",
            response_char_limit=0,
            as_of=AS_OF,
        ),
    )
    protocol = asyncio.run(native(spec, PAYLOAD, **options))
    code, cli = call_cli(
        spec,
        PAYLOAD,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            field,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    spec.output_model.model_validate(cli)


def test_sanshi_embedded_board_carries_same_stars(rest, tmp_path, capsys):
    spec = SPECS["sanshiunited"]
    fields = [
        "liureng.auxiliary_stars",
        "subresults.liureng_gods.liureng.auxiliary_stars",
    ]
    payload = inputs(spec)
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", AS_OF),
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert (
        cli["liureng"]["auxiliary_stars"]
        == cli["subresults"]["liureng_gods"]["liureng"]["auxiliary_stars"]
    )


@pytest.mark.parametrize(
    "section,names",
    [
        ("干煞", ["日德", "日禄"]),
        ("月煞", ["天德", "月德", "天马"]),
        ("支煞", ["日支德", "驿马"]),
    ],
)
def test_selected_section_exports_exact_placement_facts(
    section, names, rest, tmp_path, capsys
):
    spec = SPECS["liureng_gods"]
    payload = {**PAYLOAD, "selected_sections": [section]}
    http = rest.post(
        spec.rest_path, json=payload, params=dict(as_of=AS_OF, response_char_limit=0)
    )
    protocol = asyncio.run(native(spec, payload))
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    exported = cli["snapshot_export"]
    assert exported["selected_sections"] == [section]
    assert "[起盘信息]" not in exported["export_text"]
    for star in cli["liureng"]["auxiliary_stars"]["stars"]:
        if star["name"] in names:
            assert (
                f"{star['name']}：{star['branch']}临{star['earth_branch']}乘{star['god']}；"
                in exported["export_text"]
            )


def test_claim_receipt_rejects_a_changed_auxiliary_branch(rest):
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = SPECS["liureng_gods"]
    body = rest.post(
        spec.rest_path, json=PAYLOAD, params=dict(as_of=AS_OF, response_char_limit=0)
    ).json()
    aux = body["liureng"]["auxiliary_stars"]
    index = next(i for i, s in enumerate(aux["stars"]) if s["id"] == "day_de")
    actual = aux["stars"][index]["branch"]
    receipt = body["run_metadata"]
    claim = CalculationClaim(
        path=f"liureng.auxiliary_stars.stars.{index}.branch",
        value=actual,
        run_id=receipt["run_id"],
        business_output_sha256=receipt["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(body, [claim])["status"]
        == "verified_structured_facts"
    )
    wrong = "子" if actual != "子" else "丑"
    assert (
        verify_calculation_claims(body, [claim.model_copy(update={"value": wrong})])[
            "status"
        ]
        == "rejected"
    )
