"""Declared 探原 convention, actual board facts and faithful delivery."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.core.metaphysics.liureng_life_stages import (
    build_life_stages,
    life_stage_cycle,
)
from fatebridge.core.public_output import same_public_value
from scripts.ren import audit_ren_classical
from tests.support.transports import SPECS, business, inputs, rest, surface_calls
from tests.unit_test.fixtures.ren_protocol import REN_PROTOCOL_PAYLOAD
from tests.unit_test.fixtures.schema_assertions import (
    reject_nested_fact_fault as reject_fault,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ren_life_audit", ROOT / "scripts/ren/audit_liuren_life_stages.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()


@pytest.mark.parametrize("row", REFERENCE["anchors"])
def test_all_ten_source_anchor_sets_and_direction(row) -> None:
    cycle = life_stage_cycle(row["stem"])
    assert cycle[row["changsheng"]] == "长生"
    assert cycle[row["linguan"]] == "临官"
    assert cycle[row["mu"]] == "墓"
    assert set(cycle.values()) == set(REFERENCE["stage_order"])
    branches = "子丑寅卯辰巳午未申酉戌亥"
    identity = build_life_stages(row["stem"], dict(zip(branches, branches)))
    assert all(p["matched"] is False for p in identity["placements"])


def test_audit_keeps_literal_and_expanded_denominators_separate() -> None:
    report = AUDIT.audit()
    assert report["literal_anchor_sets"] == 10
    assert (
        report["literal_anchor_match_count"]
        == len(report["literal_anchor_checks"])
        == 30
    )
    assert (
        report["derived_cycle_match_count"]
        == len(report["derived_cycle_checks"])
        == 120
    )
    assert (
        report["source_placement_match_count"]
        == len(report["source_placement_checks"])
        == 20
    )
    assert report["selected_excerpt_checks_passed"]
    assert not report["classical_acceptance_passed"] and not report["goal_complete"]


def test_empty_transmission_retains_stage_and_rule_is_independent_of_noble_profile() -> (
    None
):
    seed = audit_ren_classical.make_seed({"day": "丙寅", "hour": "申"})
    boards = [
        build_liureng_board(seed, month_general_override="亥", guiren_profile=p)
        for p in ("liuren_common_v1", "tanyuan_xieji_v1")
    ]
    assert boards[0]["life_stages"] == boards[1]["life_stages"]
    for board in boards:
        middle = board["three_transmissions"]["middle"]
        assert middle["branch"] == "亥" and middle["xun_kong"]
        assert middle["ganzhi"] is middle["dun_stem"] is None
        assert middle["day_stem_life_stage"] == "绝"
        assert middle["seated_day_stem_life_stage"] == "病"
        for lesson in board["four_lessons"]:
            assert (
                lesson["upper_day_stem_life_stage"]
                == board["life_stages"]["stage_by_branch"][lesson["upper_branch"]]
            )
        trace = next(
            t
            for t in board["rule_trace"]
            if t["rule_id"] == "liuren.tanyuan_life_stages"
        )
        assert trace["result"] == board["life_stages"]


@pytest.mark.parametrize("stem", ["戊", "己", "乙", "癸"])
def test_author_explicit_difference_from_five_phase_shortcuts(stem: str) -> None:
    row = next(a for a in REFERENCE["anchors"] if a["stem"] == stem)
    assert life_stage_cycle(stem)[row["changsheng"]] == "长生"
    # The author's starts cannot be silently replaced by 水土同申/阴干同阳.
    usual_phase_start = {"戊": "申", "己": "申", "乙": "亥", "癸": "申"}[stem]
    assert life_stage_cycle(stem)[usual_phase_start] != "长生"


def test_reference_edit_does_not_turn_into_a_pass(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "reference.json"
    ref = json.loads(p.read_text())
    ref["anchors"][4]["changsheng"] = "申"
    p.write_text(json.dumps(ref, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen life-stage source changed"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("key", ["liureng_gods", "liureng_runyear", "jinkou"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_stages_and_corrected_snapshot_across_three_transports(
    key: str, project: bool, surface_calls
) -> None:
    spec = SPECS[key]
    payload = {**REN_PROTOCOL_PAYLOAD, "analysis_day": 5, "analysis_hour": 12}
    if key == "jinkou":
        payload["di_fen"] = "子"
    else:
        pass
    if key == "liureng_runyear":
        payload.update(
            birth_year=1994,
            birth_month=8,
            birth_day=23,
            birth_hour=14,
            birth_timezone="Asia/Shanghai",
            gender="女",
        )
    else:
        pass
    fields = [
        "liureng.life_stages",
        "liureng.three_transmissions",
        "liureng.month_building_element",
    ]
    params = [("response_char_limit", "0")]
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
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    else:
        pass
    http, protocol, code, cli = surface_calls(
        spec, payload, params=params, options=options, flags=flags
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    fn, args, kwargs = spec.bind(spec.request_model.model_validate(payload))
    expected = fn(*args, **kwargs)["liureng"]["life_stages"]
    assert expected["source_sha256"] == REFERENCE["source_sha256"]
    for body in bodies:
        spec.output_model.model_validate(body)
        board = body["liureng"]
        life = board["life_stages"]
        assert life["day_stem"] == "己" and life["direction"] == "逆"
        assert life["changsheng_branch"] == "酉" and life["tomb_branch"] == "丑"
        assert same_public_value(life, expected)
        assert board["month_building_element"] == "土"
        for label in ("initial", "middle", "final"):
            t = board["three_transmissions"][label]
            assert t["day_stem_life_stage"] == life["stage_by_branch"][t["branch"]]
            assert (
                t["seated_day_stem_life_stage"]
                == life["stage_by_branch"][t["earth_branch"]]
            )
        if not project and key != "jinkou":
            assert "月建十二长生所属" not in body["snapshot_text"]
            assert "日干己，逆行" in body["snapshot_text"]
        else:
            pass
    if key != "jinkou":
        assert "liureng.life_stages" in evidence_views(spec)["core"]["fields"]
    else:
        pass


@pytest.mark.parametrize(
    "payload",
    [
        {"liureng": {"life_stages": {"stage_by_branch": {"子": "土"}}}},
        {
            "liureng": {
                "three_transmissions": {"initial": {"day_stem_life_stage": "旺"}}
            }
        },
        {"liureng": {"life_stages": {"ruleset_id": "universal_all_schools"}}},
    ],
)
def test_wrong_stage_vocabulary_is_rejected_before_projection(
    payload,
    rest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reject_fault("liureng_gods", payload, rest, monkeypatch, tmp_path, capsys)


def test_invalid_stem_and_impossible_plate_rejected() -> None:
    with pytest.raises(ValueError):
        life_stage_cycle("甲子")
    with pytest.raises(ValueError):
        build_life_stages("甲", {"子": "子"})
    branches = "子丑寅卯辰巳午未申酉戌亥"
    plate = dict(zip(branches, branches))
    plate["子"], plate["丑"] = plate["丑"], plate["子"]
    with pytest.raises(ValueError, match="同一支序"):
        build_life_stages("甲", plate)


def test_sanshi_embedded_ren_uses_the_same_declared_stage_rule(surface_calls) -> None:
    spec = SPECS["sanshiunited"]
    payload = inputs(spec)
    fields = ["liureng.life_stages"]
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True, "include_snapshot_text": False},
            "response_char_limit": 0,
        },
        cli_first=False,
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        outer = body["liureng"]["life_stages"]
        assert outer["ruleset_id"] == "tanyuan_ten_stem_life_stages_v1"
