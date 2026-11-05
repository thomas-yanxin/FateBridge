"""Audit every frozen numerical/position observation in the Key day example."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_day import key_day_numeric_board

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v7"
REQUIRED_IDS = frozenset(
    "counter ju taiyi palace_day wenchang jishen shiji main_prose guest main_general main_vice guest_general guest_vice heshen_prose dingmu set_count set_general set_vice duty_gate gate_day emperor earth heaven_time flying_bird heaven_venerable five_elements eight_winds_prose five_winds three_winds ordinal_palace_prose main_chart heshen_chart eight_winds_chart taiyi_ordinal_chart".split()
)


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    path = corpus / "manifest.json"
    manifest = json.loads(path.read_text())
    required_files = {
        "day-worked.json",
        "day-source.txt",
        "key-page39.jpg",
        "key-page40.jpg",
        "key-page41.jpg",
        "key-page42.jpg",
        "key-page43.jpg",
        "key-page43-hi.jpg",
    }
    if {s["file"] for s in manifest["source_files"]} != required_files:
        raise ValueError("日计全部冻结材料不得删减")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("日计来源指纹不符：" + item["file"])
    case = json.loads((corpus / "day-worked.json").read_text())
    rows = case["observations"]
    if (
        len(rows) != 34
        or {r["id"] for r in rows} != REQUIRED_IDS
        or manifest["observation_count"] != 34
    ):
        raise ValueError("日计34观察必须全部保留，包括课式异数和未决宫位")
    if case["input"] != {"accumulation": 44, "yin": False, "ruler_branch": "未"}:
        raise ValueError("不得更换丁未44日独立输入以匹配算法")
    board = key_day_numeric_board(44, "未", False)
    matches, differences, unknown = [], [], []
    for row in rows:
        actual: Any = board
        for part in row["result_path"].split("."):
            actual = actual[part]
        observation = {**row, "computed_value": actual}
        if actual is None:
            unknown.append(observation)
        elif actual != row["expected"]:
            differences.append(observation)
        else:
            matches.append(observation)
    return {
        "completion_claim": False,
        "corpus_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "required_observations": 34,
        "evaluated_observations": 34 - len(unknown),
        "matching_observations": len(matches),
        "disagreements": differences,
        "unadjudicated": unknown,
        "count_policy": "一条课例的34原文观察，正文与课式异数分别保留；重复的结果路径不是独立样本。不混入周期遍历或现代日期测试来提高原典匹配率。",
        "source_example_acceptance_passed": not differences and not unknown,
        "ancient_date_conversion_validated": False,
        "full_judgment_validated": False,
        "whole_book_conformance": "not_established",
        "real_world_efficacy": "not_tested",
        "implementation_sha256": {
            name: hashlib.sha256(
                (ROOT / "src/fatebridge/core/metaphysics" / name).read_bytes()
            ).hexdigest()
            for name in (
                "taiyi_day.py",
                "taiyi_ten_jing.py",
                "taiyi_year.py",
                "taiyi_gates.py",
            )
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if report["source_example_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
