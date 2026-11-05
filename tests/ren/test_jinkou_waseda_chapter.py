"""The second witness is a bounded, incomplete chapter, not 64 clean answers."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.application.execution import OutputContractError, validate_output
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_waseda_chapter_v1"
PIN = "bed79fa873f4f806a7dc4d0dc6c290fc54012e5ac92bfc3b364adad4f3417d05"
SPEC = SPECS["jinkou"]
PAYLOAD = dict(
    analysis_year=2026,
    analysis_month=4,
    analysis_day=4,
    analysis_hour=21,
    analysis_minute=18,
    analysis_second=37,
    analysis_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    is_diurnal=False,
    guiren_profile="tanyuan_xieji_v1",
    di_fen="酉",
)


def reference(corpus=CORPUS):
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(corpus / "freeze.json") == PIN
    freeze = json.loads((corpus / "freeze.json").read_text())
    assert {p.name for p in corpus.iterdir()} == set(freeze["files"]) | {"freeze.json"}
    assert all(sha(corpus / n) == d for n, d in freeze["files"].items())
    return json.loads((corpus / "inventory.json").read_text())


def calculate(annual=False):
    payload = dict(PAYLOAD)
    if annual:
        payload.update(birth_year_ganzhi="甲午", year_fate_age=20, gender="男")
    fn, args, kw = SPEC.bind(SPEC.request_model.model_validate(payload))
    return fn(*args, **kw)


def witness(board):
    return next(
        w
        for w in board["definition_evidence"]["witnesses"]
        if w["id"] == "waseda_book6"
    )


@pytest.mark.parametrize("annual", [False, True])
def test_full_chapter_inventory_is_delivered_without_adjudicating_the_six(annual):
    ref = reference()
    result = calculate(annual)
    boards = [result["jinkou"]]
    if annual:
        boards.append(result["jinkou"]["year_fate"]["course"])
    for board in boards:
        w = witness(board)
        assert "chapter_inventory" in w, "Full chapter evidence has not reached results"
        inventory = w["chapter_inventory"]
        assert w["full_scan_sha256"] == ref["source_sha256"]
        assert w["full_scan_url"] == ref["full_scan_url"]
        assert inventory["headings"] == ref["entries"]
        assert inventory["observed_heading_occurrences"] == len(ref["entries"]) == 53
        assert (
            inventory["unique_raw_headings"]
            == len({r["raw_heading"] for r in ref["entries"]})
            == 52
        )
        assert inventory["duplicate_raw_headings"] == ["鎖課"]
        assert inventory["direct_observations"] == ref["direct_observations"]
        assert (
            inventory["raw_inventory_sha256"]
            == hashlib.sha256((CORPUS / "inventory.json").read_bytes()).hexdigest()
        )
        assert inventory["whole_volume_transcription_complete"] is False
        assert inventory["classical_predicates_adjudicated"] == 0
        assert board["patterns"]["evaluation_counts"]["unresolved"] == 6
        assert all(
            e["adjudicated_match"] is None
            for e in board["definition_evidence"]["entries"]
        )
    validate_output(SPEC, result)


@pytest.mark.parametrize("annual", [False, True])
@pytest.mark.parametrize("fault", ["count", "duplicate", "hash", "missing"])
def test_false_chapter_claims_are_rejected_for_main_and_annual_courses(fault, annual):
    result = json.loads(json.dumps(calculate(annual)))
    board = result["jinkou"]["year_fate"]["course"] if annual else result["jinkou"]
    w = witness(board)
    if fault == "count":
        w["chapter_inventory"]["observed_heading_occurrences"] = 64
    elif fault == "duplicate":
        w["chapter_inventory"]["headings"][12]["raw_heading"] = "刪除重複"
    elif fault == "hash":
        w["full_scan_sha256"] = "0" * 64
    else:
        del w["chapter_inventory"]
    with pytest.raises(OutputContractError):
        validate_output(SPEC, result)


def test_trace_keeps_its_existing_summary_without_inventing_a_second_inventory():
    board = calculate()["jinkou"]
    trace = next(
        t
        for t in board["rule_trace"]
        if t["rule_id"] == "jinkou.unresolved_definition_witnesses"
    )
    assert trace["result"] == {
        "unadjudicated_ids": ["P52", "P53", "P56", "P57", "P58", "P59"],
        "adjudicated_predicate": None,
        "complete_classical_conformance": False,
    }
    assert "chapter_inventory" in witness(board)


@pytest.mark.parametrize("annual", [False, True])
@pytest.mark.parametrize("project", [False, True])
def test_chapter_source_and_nulls_survive_all_three_ports(
    annual, project, surface_calls
):
    payload = dict(PAYLOAD)
    if annual:
        payload.update(birth_year_ganzhi="甲午", year_fate_age=20, gender="男")
    fields = [
        "jinkou.definition_evidence.witnesses",
        "jinkou.definition_evidence.entries",
        "jinkou.patterns.evaluation_counts",
    ]
    if annual:
        fields.append("jinkou.year_fate.course.definition_evidence.witnesses")
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, opts = ["--response-char-limit", "0"], {}
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
        opts.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, mcp, code, cli = surface_calls(
        SPEC, payload, params=params, options=opts, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not mcp.is_error and code == 0
    assert business(http.json()) == business(mcp.structured_content) == business(cli)
    for body in [http.json(), mcp.structured_content, cli]:
        w = witness(body["jinkou"])
        assert w["chapter_inventory"]["observed_heading_occurrences"] == 53
        assert body["jinkou"]["patterns"]["evaluation_counts"]["unresolved"] == 6
