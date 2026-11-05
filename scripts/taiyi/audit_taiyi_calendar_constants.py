"""Audit frozen original-edition calendar constants without installing a profile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.validation.taiyi_calendar import audit_calendar_constants

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v26"
FROZEN_SHA256 = "b8717e3e25b4018da3b047505fad396d44de316bd3567918b750a2c0b418dcc7"
RELATIONS = {
    "month_fraction",
    "year_day_denominator",
    "half_hour_day_scale",
    "annual_residue",
    "two_solstice_intervals",
    "double_hour_fraction",
    "next_qi_increment",
    "literal_leap_step_cycle",
}


def verify_sources(corpus: Path = CORPUS) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen_bytes = (corpus / "initial-freeze.json").read_bytes()
    if hashlib.sha256(frozen_bytes).hexdigest() != FROZEN_SHA256:
        raise ValueError("Initial Taiyi calendar source freeze changed")
    frozen = json.loads(frozen_bytes)
    if not frozen["before_implementation"] or frozen["dated_cases"] != 0:
        raise ValueError("Calendar evidence scope changed")
    for name, digest in frozen["files"].items():
        if Path(name).name != name:
            raise ValueError("Source filename must stay inside corpus")
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Calendar source fingerprint changed: {name}")
    readings = json.loads((corpus / "readings.json").read_text())
    expected = json.loads((corpus / "expected-relations.json").read_text())
    if set(readings["editions"]) != {"siku", "ncl_ming"}:
        raise ValueError("Both original editions must remain")
    if any(set(expected[name]) != RELATIONS for name in readings["editions"]):
        raise ValueError("All eight diagnostic relations must remain per edition")
    return readings, expected


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    readings, expected = verify_sources(corpus)
    result = audit_calendar_constants(readings["editions"])
    observed = {
        name: {r["id"]: r["status"] for r in edition["relations"]}
        for name, edition in result["editions"].items()
    }
    regression = all(observed[name] == expected[name] for name in observed)
    regression = regression and result["counts"] == expected["expected_total"]
    result.update(
        source_freeze_sha256=FROZEN_SHA256,
        source_readings_sha256=hashlib.sha256(
            (corpus / "readings.json").read_bytes()
        ).hexdigest(),
        expected_relations_sha256=hashlib.sha256(
            (corpus / "expected-relations.json").read_bytes()
        ).hexdigest(),
        required_relations=16,
        software_preserves_frozen_diagnostic_expectations=regression,
        sources={
            name: {k: v for k, v in edition.items() if k != "readings"}
            for name, edition in readings["editions"].items()
        },
        outstanding=[
            "次氣小餘／秒的原字分組與算式、辰法小分之也的數值語義。",
            "固定閏差單步解讀不能閉合；無中氣與提前置閏的完整規則仍需他本裁定。",
            "四庫殘缺全數、常數不相容與兩版本取捨沒有據自洽自動校定。",
            "完整原典積年、日辰與加時錨點及獨立有日期歷表尚未接通。",
            "現代節氣適配未由本報告變成完整古歷，其他太乙原典分歧與總目標保持。",
        ],
        requirement_scope="16個常數相容性關係，不是16個古歷時刻或原典課例；測試綠色只核對審計保留全部差異。",
    )
    return result
