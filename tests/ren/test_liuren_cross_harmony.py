"""Independent crossed-Liuhe answers, named exclusions, and real transports."""

import copy
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.metaphysics.liureng_cross_harmony import (
    cross_harmony,
    cross_harmony_trace,
)
from fatebridge.core.output_chinese import Liuren
from fatebridge.core.output_liuren_cross_harmony import LiurenCrossHarmony
from fatebridge.core.output_ren_anchors import require_complete_ren_anchors
from scripts.ren.audit_liuren_cross_harmony import (
    CORPUS,
    expected_facts,
    reference,
    sha,
)
from tests.ren.test_liuren_ordered_patterns import raw
from tests.support.transports import AS_OF, SPECS, business, native, rest, surface_calls

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


def test_complete_frozen_answers_and_source_exception():
    rows = DATA["reference"]["contexts"]
    actual = []
    for row in rows:
        value = cross_harmony(row["day_ganzhi"], row["sky_by_earth"])
        expected = expected_facts(row)
        assert {k: value[k] for k in expected} == expected
        LiurenCrossHarmony.model_validate(value)
        actual.append(value)
    assert len(rows) == 720
    assert sum(r["both_cross_pairs"] for r in actual) == 60
    assert sum(r["matched"] for r in actual) == 55
    assert {
        r["day_ganzhi"] for r in actual if r["both_cross_pairs"] and not r["matched"]
    } == {"甲寅", "庚申", "丁未", "己未", "癸丑"}


def test_tanyuan_original_example_requires_both_crossed_pairs():
    value = cross_harmony("癸酉", sky(3))
    assert value["matched"] is True
    assert [(p["left_branch"], p["right_branch"]) for p in value["cross_pairs"]] == [
        ("辰", "酉"),
        ("子", "丑"),
    ]
    # The upper pair alone is not the crossed criterion.
    assert value["stem_upper"] + value["branch_upper"] == "辰子"
    assert cross_harmony("癸酉", sky(2))["matched"] is False


@pytest.mark.parametrize("day", ["甲寅", "庚申", "丁未", "己未", "癸丑"])
def test_shared_anchor_facts_remain_true_but_named_pattern_is_excluded(day):
    rows = [
        r
        for r in DATA["reference"]["contexts"]
        if r["day_ganzhi"] == day and r["both_cross_pairs"]
    ]
    assert len(rows) == 1
    value = cross_harmony(day, rows[0]["sky_by_earth"])
    assert all(p["liuhe"] for p in value["cross_pairs"])
    assert value["distinct_anchors"] is False and value["matched"] is False
    assert value["exclusion_reason"] == "干支同宫（八专五日）"


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
def test_invalid_or_noncyclic_inputs_cannot_manufacture_a_match(day, mapping):
    with pytest.raises(ValueError):
        cross_harmony(day, mapping)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "phase_as_house",
        "wrong_upper",
        "reverse_pairs",
        "omit_pair",
        "numeric_bool",
        "false_certificate",
        "wrong_pair",
        "wrong_match",
    ],
)
def test_contract_rejects_invented_present_facts(fault):
    value = cross_harmony("癸酉", sky(3))
    if fault == "source":
        value["source_sha256"] = "invented"
    elif fault == "phase_as_house":
        value["day_stem_house"] = "亥"
    elif fault == "wrong_upper":
        value["branch_upper"] = "丑"
    elif fault == "reverse_pairs":
        value["cross_pairs"].reverse()
    elif fault == "omit_pair":
        value["cross_pairs"].pop()
    elif fault == "numeric_bool":
        value["matched"] = 1
    elif fault == "false_certificate":
        value["complete_classical_conformance"] = 0
    elif fault == "wrong_pair":
        value["cross_pairs"][1]["right_branch"] = "寅"
    else:
        value["matched"] = False
    with pytest.raises(ValidationError):
        LiurenCrossHarmony.model_validate(value)


@pytest.mark.parametrize(
    "value",
    [
        {"both_cross_pairs": True, "distinct_anchors": True, "matched": False},
        {"cross_pairs": [{"liuhe": False}, {}], "both_cross_pairs": True},
        {"day_ganzhi": "甲寅", "matched": True},
        {"day_ganzhi": "癸酉", "day_stem_house": "亥"},
    ],
)
def test_sparse_sufficient_facts_cannot_contradict_their_conclusion(value):
    with pytest.raises(ValidationError):
        LiurenCrossHarmony.model_validate(value)


def test_sparse_result_remains_a_projection_without_fabricated_siblings():
    value = LiurenCrossHarmony.model_validate({"matched": True})
    assert value.model_dump(exclude_unset=True) == {"matched": True}
    LiurenCrossHarmony.model_validate(
        {
            "cross_pairs": [
                {"id": "stem_upper_to_day_branch"},
                {"id": "branch_upper_to_stem_house"},
            ]
        }
    )
    board = {
        "calendar_policy": {"effective_day_ganzhi": "癸酉"},
        "twelve_board": [
            {"earth_branch": e, "sky_branch": s} for e, s in sky(3).items()
        ],
        "cross_harmony": {"matched": False},
    }
    with pytest.raises(ValidationError):
        Liuren.model_validate(board)


@pytest.mark.parametrize("fault", ["bytes", "coordinated_rehash", "extra", "missing"])
def test_frozen_source_cannot_be_rewritten_or_narrowed(tmp_path, fault):
    folder = tmp_path / "source"
    shutil.copytree(CORPUS, folder)
    path = folder / "reference.json"
    if fault in ("bytes", "coordinated_rehash"):
        path.write_text(path.read_text() + " ")
        if fault == "coordinated_rehash":
            freeze = json.loads((folder / "freeze.json").read_text())
            freeze["files"][path.name] = sha(path)
            (folder / "freeze.json").write_text(json.dumps(freeze))
    elif fault == "extra":
        (folder / "remove-five-negative-cases.json").write_text("{}")
    else:
        path.unlink()
    with pytest.raises(ValueError, match="Frozen cross-harmony"):
        reference(folder)


@pytest.fixture(scope="module")
def results():
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
        "numeric_bool",
    ],
)
def test_full_output_checks_actual_day_board_and_unique_trace(results, key, fault):
    value = copy.deepcopy(results[key])
    board = value["liureng"]
    trace = next(
        t for t in board["rule_trace"] if t.get("rule_id") == "liuren.cross_harmony"
    )
    if fault in ("missing", "old_version"):
        board.pop("cross_harmony")
        if fault == "old_version":
            board["ruleset"]["version"] = "0.0.0"
    elif fault == "foreign_consistent":
        day = "甲子" if board["cross_harmony"]["day_ganzhi"] != "甲子" else "乙丑"
        fake = cross_harmony(day, board["cross_harmony"]["sky_by_earth"])
        board["cross_harmony"] = fake
        trace.update(cross_harmony_trace(fake))
    elif fault == "trace":
        board["rule_trace"].remove(trace)
    elif fault == "duplicate":
        board["rule_trace"].append(copy.deepcopy(trace))
    else:
        board["cross_harmony"]["matched"] = int(board["cross_harmony"]["matched"])
    with pytest.raises(ValueError):
        require_complete_ren_anchors(key, value)


@pytest.mark.parametrize(
    "key", ["liureng_gods", "liureng_runyear", "jinkou", "sanshiunited"]
)
@pytest.mark.parametrize("project", [False, True])
def test_real_rest_native_mcp_cli_preserve_same_new_facts(key, project, surface_calls):
    spec = SPECS[key]
    path = "liureng.cross_harmony"
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
    http, protocol, code, cli = surface_calls(
        spec,
        PAYLOADS[key],
        params=params,
        options=options,
        flags=flags,
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        own = body["liureng"]["cross_harmony"]
        assert len(own["cross_pairs"]) == 2
        assert own["source_kind"] == "frozen_primary_transcription_not_scan_collated"


@pytest.mark.parametrize("project", [False, True])
def test_broken_condition_is_rejected_before_projection_on_every_port(
    project, monkeypatch, surface_calls
):
    key = "liureng_gods"
    spec = SPECS[key]
    value = raw(key)
    value["liureng"]["cross_harmony"]["matched"] = not value["liureng"][
        "cross_harmony"
    ]["matched"]
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
    http, protocol, code, cli = surface_calls(
        spec,
        PAYLOADS[key],
        params=params,
        options=options,
        flags=flags,
        cli_first=False,
    )
    assert http.status_code == 500 and protocol.is_error and code != 0
