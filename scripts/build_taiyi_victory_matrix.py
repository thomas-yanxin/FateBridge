"""Copy all 128 independently transcribed cells; never fill a blank from a chart."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v20"
DEST = ROOT / "src/fatebridge/data/classical/taiyi-victory-matrix-v1.json"
MANIFEST_SHA = "ce8639f43579def116d76649c4606f992808a7669d63722d8cdde001887889a4"


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("胜败钤初始清单指纹不符")
    m = json.loads(raw)
    for row in m["source_files"]:
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("胜败钤源文件指纹漂移：" + row["file"])
    for row in m["prior_source_references"]:
        if (
            hashlib.sha256((CORPUS.parent / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("胜败钤既有源文件指纹漂移：" + row["file"])
    table = json.loads((corpus / "matrix-columns.json").read_text())
    cells = table["cells"]
    if len(cells) != 128 or {
        (c["wenchang_position"], c["taiyi_number"]) for c in cells
    } != {(p, n) for p in "子丑艮寅卯辰巽巳午未坤申酉戌乾亥" for n in [1, 2, 3, 4, 6, 7, 8, 9]}:
        raise ValueError("胜败钤128格须完整保留，包括缺文、空栏和未决条件")
    return {
        "id": "jinjing_victory_matrix_columns_v1",
        "version": "1.0.0",
        "author": "FateBridge contributors",
        "classical_author": "唐·王希明",
        "source_title": "太乙金镜式经四库本卷三三门五将立成胜败钤",
        "source_urls": m["sources"],
        "source_manifest_sha256": MANIFEST_SHA,
        "column_layout": table["column_layout"],
        "editorial_policy": table["editorial_policy"],
        "cells": cells,
        "role_scope": "本表天目按卷二十六神名位对应本盘文昌；未标客主的大将、参将保留双方候选，不能据数字较合就裁为某方。",
        "method_scope": "原格只给天目与太乙；完整门盘、客目、主客指代及时间计法适用仍待裁定，门具将发不是本盘三门五将条件已全真的证明。",
        "scope": "原栏胜败只是未完成适用核验的传统引文；几何比较不认证整格、不覆盖现有条件合取、不产生本次实际胜负。",
        "classical_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    raw = (
        json.dumps(source_data(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    if args.check:
        if not DEST.exists() or DEST.read_bytes() != raw:
            raise SystemExit("胜败钤运行资料漂移")
    else:
        DEST.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
