"""Keep all annual ten-essence observations and the unchanged full day case."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fatebridge.core.metaphysics.taiyi_ten_jing import key_ten_jing
from scripts.taiyi.audit_taiyi_day import audit as day_audit

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v9"
REQUIRED_IDS = {
    k + suffix
    for k in (
        "emperor",
        "earth",
        "heaven_time",
        "heaven_venerable",
        "flying_bird",
        "five_elements",
        "eight_winds",
        "five_winds",
        "three_winds",
        "taiyi_ordinal",
    )
    for suffix in ("_phase", "_location")
} | {"five_elements_next_year", "five_elements_second_year"}


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    required_files = {
        "key-page30-hi.jpg",
        "key-page33-hi.jpg",
        "key-page34-hi.jpg",
        "key-page41-hi.jpg",
        "key-page42-hi.jpg",
        "annual-ten-essences.json",
        "adjudication-notes.txt",
        "external-rule-references.json",
    }
    if {r["file"] for r in manifest["source_files"]} != required_files:
        raise ValueError("十精补证须保留完整年例与有冲突的日例原图")
    if {r["file"] for r in manifest["prior_source_references"]} != {
        "../taiyi_jinjing_v7/day-worked.json",
        "../taiyi_jinjing_v7/manifest.json",
    }:
        raise ValueError("V7日例34观察的原材料不得变更或删除")
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("十精补证指纹不符：" + item["file"])
    case = json.loads((corpus / "annual-ten-essences.json").read_text())
    rows = case["observations"]
    if (
        len(rows) != 22
        or {r["id"] for r in rows} != REQUIRED_IDS
        or manifest["annual_observation_count"] != 22
    ):
        raise ValueError("年度十精22观察包含天尊差异、三风未载终宫，不得择优删除")
    if case["input"] != {"accumulation": 10155478, "yin": False}:
        raise ValueError("原例完整积数不可用有利相位替换")
    matches, disagreements, unadjudicated = [], [], []
    for row in rows:
        board = key_ten_jing(
            case["input"]["accumulation"] + row.get("counter_offset", 0), False
        )
        actual: Any = board
        for part in row["result_path"].split("."):
            actual = actual[part]
        observation = {**row, "computed_value": actual}
        if (
            row["source_status"] != "stated"
            or row["expected"] is None
            or actual is None
        ):
            unadjudicated.append(observation)
        elif actual != row["expected"]:
            disagreements.append(observation)
        else:
            matches.append(observation)
    day = day_audit(corpus.parent / "taiyi_jinjing_v7")
    return {
        "completion_claim": False,
        "corpus_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "annual_cross_period_reference": {
            "required_observations": 22,
            "evaluated_observations": 22 - len(unadjudicated),
            "matching_observations": len(matches),
            "disagreements": disagreements,
            "unadjudicated": unadjudicated,
            "source_example_acceptance_passed": not disagreements and not unadjudicated,
            "scope": case["scope"],
        },
        "unchanged_complete_day_case": day,
        "adopted_rule": "天时寅起十二支，由通则与年度余10在亥补证；日例坤不改写且转为明确不符。",
        "source_example_acceptance_passed": not disagreements
        and not unadjudicated
        and day["source_example_acceptance_passed"],
        "count_policy": "年度22观察与日例34观察分别计数；年度的同序余数/终位不是22个独立案例，未载终位不计通过。保留年例天尊方向差异，不冒认四计全同。",
        "whole_book_conformance": "not_established",
        "complete_ancient_calendar": False,
        "real_world_efficacy": "not_tested",
    }
