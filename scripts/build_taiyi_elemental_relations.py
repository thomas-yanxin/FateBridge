"""Build the separately frozen sixteen-spirit element fragment, never a chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v19"
DEST = ROOT / "src/fatebridge/data/classical/taiyi-elemental-relations-v1.json"
MANIFEST_SHA = "24ad1335ed9f09a5f1ba83993199e56dca132e09f08989824ad27847d3f65810"


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("二目五行初始清单指纹不符")
    manifest = json.loads(raw)
    for row in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("二目五行源材料指纹不符：" + row["file"])
    for row in manifest["prior_source_references"]:
        if (
            hashlib.sha256((CORPUS.parent / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("既有二目源材料指纹不符：" + row["file"])
    spirits = json.loads((corpus / "spirit-elements.json").read_text())
    cases = json.loads((corpus / "worked-cases.json").read_text())["cases"]
    truth = json.loads((corpus / "synthetic-truth.json").read_text())["rows"]
    extracts = (corpus / "source-extracts.txt").read_text()
    normalize = lambda text: re.sub(r"[\s\u200b]", "", text)
    if len(spirits) != 16 or {s["position"] for s in spirits} != set(
        "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
    ):
        raise ValueError("十六神须完整保留，不能删未决项")
    if len(cases) != 4 or not all(
        normalize(c["quote"]) in normalize(extracts) for c in cases
    ):
        raise ValueError("四条原文例须完整保留且逐字可追溯")
    if len(truth) != 25 or {(r["main"], r["guest"]) for r in truth} != {
        (a, b) for a in "木火土金水" for b in "木火土金水"
    }:
        raise ValueError("25个合成五行关系须完整保留")
    return {
        "id": "taojin_eyes_wuxing_fragment_v1",
        "version": "1.0.0",
        "author": "FateBridge contributors",
        "classical_author": "王希明；淘金歌图书集成所录本作者未据本段裁定",
        "source_title": "金镜卷四推主客相关；图书集成所录淘金歌定胜负",
        "source_urls": manifest["sources"],
        "source_manifest_sha256": MANIFEST_SHA,
        "spirit_elements": spirits,
        "worked_examples": cases,
        "role_scope": "本盘文昌属主、始击属客；金镜卷二在地/在天角色补核卷四本段地目/天目，不能把卷三表头天目一词全局固定为一方。",
        "method_scope": "卷四明言日計納音；此组件仅按淘金歌明列的二目十六神五行比较，不替换成六十甲子日柱纳音，不认证完整日计纳音或其他计法适用。",
        "interpretation_scope": "原断仅作有条件传统片段；不并入空间同宫关、五将三项或总体胜负；金土相生原例的和解不推广成所有相生必和解；主客为盘内角色，不自动对应用户或对方。",
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (
        json.dumps(source_data(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    if args.check:
        if not DEST.exists() or DEST.read_bytes() != raw:
            raise SystemExit("二目五行运行资料漂移")
    else:
        DEST.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
