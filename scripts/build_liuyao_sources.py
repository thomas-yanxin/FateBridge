"""Derive the runtime source manifest from independently frozen source bytes."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/liuyao-zengshan-sources.json"
OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-sources.json"
DEPTH_SOURCE = ROOT / "tests/fixtures/liuyao-zengshan-depth-v2.json"
DEPTH_OUTPUT = ROOT / "src/fatebridge/data/classical/liuyao-depth-v2.json"


def build():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = {}
    for chapter in source["chapters"]:
        number = chapter["title"].split("/")[1]
        records[number] = chapter
    for number in (27, 28, 29):
        records[str(number)] = source["main"]
    manifest = {}
    for number, record in records.items():
        if (
            hashlib.sha256(record["wikitext"].encode()).hexdigest()
            != record["wikitext_sha256"]
        ):
            raise ValueError(f"Source bytes changed: {number}")
        manifest[number] = {k: v for k, v in record.items() if k != "wikitext"}
    return {
        "ruleset_id": "zengshan_structural_v1",
        "sources_by_chapter": manifest,
        "corrections": ["第四章转录辰在內/辰在外按八卦结构读作艮；保留原始转录供复核"],
        "scope": "指定转录本的结构层参考；未作全书影印校勘或预测效力认证",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    depth = json.loads(DEPTH_SOURCE.read_text(encoding="utf-8"))
    records = {}
    for row in depth["chapters"]:
        if (
            hashlib.sha256(row["wikitext"].encode()).hexdigest()
            != row["wikitext_sha256"]
        ):
            raise ValueError(f"Depth source bytes changed: {row['title']}")
        records[row["title"].split("/")[1]] = {
            k: v for k, v in row.items() if k != "wikitext"
        }
    structural = build()
    for number in ("19", "28", "29"):
        records[number] = structural["sources_by_chapter"][number]
    depth_manifest = {
        "ruleset_id": "zengshan_conditional_v2",
        "ruleset_version": "2.1.0",
        "sources_by_chapter": records,
        "scope": "指定转录本的旺相、动静、用神与应期条件；条件匹配不是现实效力认证",
        "textual_issues": [
            "第15又章春季段金火土休囚为转录错字；1925书影PDF59明确金水土，原始转录保留",
            "第10章忌神有力段退神为转录错误；1925书影PDF53明确化进神，不据旧错字制作有效性表",
            "第26又1章未整列火四位，1925书影PDF97同样未整列；火长生寅及火墓戌有据，其余未补齐",
            "第19章动化合称化扶，第9章午化未例与第26又3章又列合待冲；保留两种条件表述，合绊标记不是普遍失效裁定",
        ],
    }
    for path, value in ((OUTPUT, structural), (DEPTH_OUTPUT, depth_manifest)):
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Liuyao source manifest drift: {path.name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    print("Liuyao source revisions and byte hashes verified")


if __name__ == "__main__":
    main()
