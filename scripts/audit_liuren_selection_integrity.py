"""Frozen printed harm counts and whole-domain selection consistency evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/liuren_selection_integrity_v1"
PIN = "af726ad1fc1b8fe6e30e7370872a845282804527640dc035207dfc4bde9edeb7"
ERRATUM = ROOT / "tests/fixtures/liuren_selection_erratum_v1"
ERRATUM_PIN = "3dcd414123d240a409f0d24fba743e34974e57e5013e1ab3a22c7c1789e121f7"


def reference() -> dict[str, Any]:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != PIN:
        raise ValueError("Frozen nine-method reference manifest changed")
    manifest = json.loads((CORPUS / "freeze.json").read_text())
    if {p.name for p in CORPUS.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen nine-method source inventory changed")
    for name, digest in manifest.items():
        if hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen nine-method source changed")
    return json.loads((CORPUS / "reference.json").read_text())


def resolved_reference() -> dict[str, Any]:
    """Apply one disclosed post-observation transcription erratum; retain raw."""
    raw = reference()
    if (
        hashlib.sha256((ERRATUM / "freeze.json").read_bytes()).hexdigest()
        != ERRATUM_PIN
    ):
        raise ValueError("Source erratum manifest changed")
    manifest = json.loads((ERRATUM / "freeze.json").read_text())
    if {p.name for p in ERRATUM.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Source erratum inventory changed")
    for name, digest in manifest.items():
        if hashlib.sha256((ERRATUM / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source erratum evidence changed")
    erratum = json.loads((ERRATUM / "erratum.json").read_text())
    assert erratum["original_freeze_sha256"] == PIN
    assert erratum["source_sha256"] == raw["source_sha256"]
    assert (
        erratum["original_reference_sha256"]
        == hashlib.sha256((CORPUS / "reference.json").read_bytes()).hexdigest()
    )
    assert erratum["case"] == "H05" and erratum["field"] == "depths.4"
    assert erratum["original_value"] == 5 and erratum["corrected_value"] == 6
    case = next(c for c in raw["cases"] if c["id"] == "H05")
    assert case["depths"]["4"] == 5
    case["depths"]["4"] = 6
    raw["post_observation_erratum"] = erratum
    return raw


def observe(day: str, gan_upper: str) -> dict[str, Any]:
    from fatebridge.core.metaphysics.liureng import build_liureng_board
    from scripts.audit_ren_classical import make_seed

    branches = "子丑寅卯辰巳午未申酉戌亥"
    houses = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅辰巳未巳未申戌亥丑"))
    offset = (branches.index(gan_upper) - branches.index(houses[day[0]])) % 12
    return build_liureng_board(
        make_seed(dict(day=day, hour="子", month="寅")),
        month_general_override=branches[offset],
    )


def board_in(body: dict[str, Any], key: str) -> dict[str, Any]:
    # The legacy 三式 root shares this object with subresults. deepcopy keeps
    # the alias; mutating it does not create a merely cross-copy mismatch.
    return body["liureng"]


def corrupt(body: dict[str, Any], key: str, fault: str) -> dict[str, Any]:
    value = copy.deepcopy(body)
    board = board_in(value, key)
    traces = board["rule_trace"]

    def trace(rule: str) -> dict[str, Any]:
        return next(t for t in traces if t["rule_id"] == rule)

    if fault == "harm_depth":
        item = trace("liuren.harm_depth")["result"]
        item[next(iter(item))] += 100
    elif fault == "named_label":
        board["classification"]["labels"] = ["元首"]
        board["classification"]["detail"] = "元首"
    elif fault == "selected_lesson":
        board["meta"]["selected_lesson_index"] = 1
    elif fault == "lesson_relation":
        board["four_lessons"][0]["upper_lower_relation"] = "比和"
    elif fault == "lesson_upper":
        row = board["four_lessons"][0]
        row["upper_branch"] = "子" if row["upper_branch"] != "子" else "丑"
    elif fault == "use_candidate":
        board["four_lessons"][0]["use_candidate"] = True
    elif fault == "result_trace":
        trace("liuren.transmissions.result")["result"]["source_lesson"] = 1
    elif fault == "candidate_trace":
        trace("liuren.direct_or_remote_candidates")["result"]["lessons"] = []
    elif fault == "polarity_trace":
        trace("liuren.polarity")["result"]["preferred_lessons"] = []
    elif fault == "missing_selection_trace":
        traces.remove(trace("liuren.harm_depth"))
    elif fault == "duplicate_selection_trace":
        traces.append(copy.deepcopy(trace("liuren.harm_depth")))
    elif fault == "missing_classification":
        del board["classification"]
    elif fault == "null_selected_lesson":
        board["meta"]["selected_lesson_index"] = None
    elif fault == "classification_basis":
        board["classification"]["basis"] = "因为神将六合便直接取元首；无需比较四课贼克"
    elif fault == "invented_source_note":
        board["classification"]["source_note"] = {"annotation": "原书已全面认证"}
    elif fault.startswith("harm_path_"):
        row = trace("liuren.harm_paths")["result"]["candidates"][0]
        item = row["steps"][0]["contributions"][0]
        if fault == "harm_path_count":
            row["harm_count"] += 100
        elif fault == "harm_path_station":
            row["steps"][0]["earth_branch"] = "丑"
        elif fault == "harm_path_element":
            item["element"] = "金" if item["element"] != "金" else "木"
        elif fault == "harm_path_token":
            item["token"] = "假"
        elif fault == "harm_path_flag":
            item["counts_as_harm"] = not item["counts_as_harm"]
        elif fault == "harm_path_extra":
            row["source_certified_prediction_accuracy"] = "100%"
        else:
            raise ValueError(fault)
    else:
        raise ValueError(fault)
    return value


def audit() -> dict[str, Any]:
    raw_ref = reference()
    ref = resolved_reference()
    printed = []
    for case in ref["cases"]:
        board = observe(case["day"], case["gan_upper"])
        counts = next(
            t["result"]
            for t in board["rule_trace"]
            if t["rule_id"] == "liuren.harm_depth"
        )
        branches = [
            board["three_transmissions"][p]["branch"]
            for p in ("initial", "middle", "final")
        ]
        printed.append(
            dict(
                id=case["id"],
                actual_depths=counts,
                expected_depths=case["depths"],
                raw_frozen_depths=next(
                    c["depths"] for c in raw_ref["cases"] if c["id"] == case["id"]
                ),
                transmissions=branches,
                expected_transmissions=case["transmissions"],
                matched=counts == case["depths"] and branches == case["transmissions"],
            )
        )
    return dict(
        source_url=ref["source_url"],
        source_sha256=ref["source_sha256"],
        printed_cases=printed,
        printed_count=len(printed),
        printed_matched_count=sum(c["matched"] for c in printed),
        raw_frozen_matched_count=sum(
            c["actual_depths"] == c["raw_frozen_depths"]
            and c["transmissions"] == c["expected_transmissions"]
            for c in printed
        ),
        post_observation_erratum=ref["post_observation_erratum"],
        terminal_inclusion_adjudicated=False,
        printed_aggregate_conflict_preserved=ref["terminal_probe"],
        aggregate_source_counts=ref["aggregate_source_counts"],
        old_naming_disagreements_removed=False,
        whole_book_conformance=False,
        new_independent_model_processes=0,
        goal_complete=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    raise SystemExit(0 if result["printed_matched_count"] == 6 else 1)
