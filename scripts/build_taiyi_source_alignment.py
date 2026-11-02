"""Materialize independently frozen core-table readings; never run a chart."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from audit_taiyi_native_columns import CORRECTION_SHA as NATIVE_CORRECTION_SHA
    from audit_taiyi_native_columns import MANIFEST_SHA as NATIVE_MANIFEST_SHA
    from audit_taiyi_native_columns import source_readings
elif __package__:
    from .audit_taiyi_native_columns import CORRECTION_SHA as NATIVE_CORRECTION_SHA
    from .audit_taiyi_native_columns import MANIFEST_SHA as NATIVE_MANIFEST_SHA
    from .audit_taiyi_native_columns import source_readings
else:
    from audit_taiyi_native_columns import CORRECTION_SHA as NATIVE_CORRECTION_SHA
    from audit_taiyi_native_columns import MANIFEST_SHA as NATIVE_MANIFEST_SHA
    from audit_taiyi_native_columns import source_readings

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v18"
DEST = ROOT / "src/fatebridge/data/classical/taiyi-jinjing-source-alignment-v1.json"
MANIFEST_SHA = "5f8d272c55d567c1cb127daa4fb3a3f97f9094b98b389392b9b5ba178df5c9d3"
SUPPLEMENT_SHA = "b0c835bbe34457bdfdf093b3fb0dc9cc10f2cc59859d93df492cd187784e9088"
CORRECTION_SHA = "52efcdb8ea9a17470cc7218e3f9cfa47a766087c7a069d82ec162d9049479865"
COLLATION_SHA = "4711cec76085817188df2b61e3cf124baaa0653244a74e9f676f125a3bfad006"


def source_data(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest_path = corpus / "manifest.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != MANIFEST_SHA:
        raise ValueError("原位置矩阵清单指纹不符")
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("原典位置材料指纹不符：" + row["file"])
    for row in manifest["prior_source_references"]:
        if (
            hashlib.sha256((CORPUS.parent / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("此前原典材料指纹不符：" + row["file"])
    for name, expected_hash in [
        ("supplement-manifest.json", SUPPLEMENT_SHA),
        ("correction-manifest.json", CORRECTION_SHA),
        ("transcription-collation-manifest.json", COLLATION_SHA),
    ]:
        path = corpus / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("补证/订正清单指纹不符")
        extra = json.loads(path.read_text())
        if extra["original_manifest_sha256"] != MANIFEST_SHA:
            raise ValueError("初录引用指纹不符")
        for item in extra["source_files"]:
            if (
                hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
                != item["sha256"]
            ):
                raise ValueError("补证/订正原文指纹不符")
    normal = json.loads((corpus / "name-normalization.json").read_text())
    correction = json.loads((corpus / "proof-quote-correction.json").read_text())
    quotes = [
        correction["corrected_quote"] if q == correction["original_quote"] else q
        for q in normal["proof_quotes"]
    ]
    proof = (CORPUS.parent / "taiyi_jinjing_v1/vol02.txt").read_text()
    if not correction["mapping_unchanged"] or not all(q in proof for q in quotes):
        raise ValueError("缺少逐字名表证明")
    raw = json.loads((corpus / "raw-position-rows.json").read_text())
    collation = json.loads((corpus / "transcription-collation.json").read_text())
    collated = {r["id"]: r for r in collation["independent_source_rows"]}
    transcription = (CORPUS.parent / "taiyi_jinjing_v1/vol03.txt").read_text()
    transcription = transcription[
        transcription.index("陽局天目地目計神主客大小將立成") :
    ]
    yang, yin = transcription.split("隂局天目地目計神主客大小將立成", 1)
    yin = yin.split("五子元積年立成法")[0]
    if len(collated) != 144:
        raise ValueError("逐字校读须保留完整144行")
    aliases = normal["map"]
    checks = json.loads((corpus / "facsimile-readings.json").read_text())
    if {(r["yin"], r["ju"]) for r in raw} != {
        (yin, n) for yin in (False, True) for n in range(1, 73)
    } or len(raw) != 144:
        raise ValueError("须保留完整阴阳144局四位置和两算")
    count_sources = {
        False: json.loads((CORPUS.parent / "taiyi_jinjing_v1/cases.json").read_text()),
        True: json.loads(
            (CORPUS.parent / "taiyi_jinjing_v2/yin-cases.json").read_text()
        ),
    }
    native = {r["id"]: r for r in source_readings()["rows"]}
    rows = []
    for row in raw:
        reading = collated[row["id"]]
        excerpt = (yin if row["yin"] else yang)[
            reading["source_start"] : reading["source_end"]
        ]
        if excerpt != reading["source_excerpt"] or any(
            reading["observed"][k] not in excerpt
            for k in ("wenchang_literal", "shiji_literal", "jishen_literal")
        ):
            raise ValueError("逐字校读缺少同一冻结转录的原句证明")
        if reading["observed"]["taiyi_number"] != row["taiyi_number"]:
            raise ValueError("不得默改初录太乙宫数")
        expected = count_sources[row["yin"]][row["ju"] - 1]["expected"]
        if expected != {f: row[f] for f in ("main_count", "guest_count")}:
            raise ValueError("不允许改变此前288项两算原值")
        initial = {
            k: row[k] for k in ("wenchang_literal", "shiji_literal", "jishen_literal")
        }
        literal = {k: reading["observed"][k] for k in initial}
        selected = dict(literal)
        selected_checks = [dict(c) for c in checks if c["id"] == row["id"]]
        for check in selected_checks:
            if check["id"] == "yin-59":
                check.update(
                    text_reading=literal[check["field"]],
                    initial_manual_reading=initial[check["field"]],
                    status="initial_manual_entry_differs_from_source_and_facsimile",
                )
        for check in selected_checks:
            if selected[check["field"]] != check["text_reading"]:
                raise ValueError("原转录与书影记录对应不符")
            if check["selected_reading"] == "facsimile":
                selected[check["field"]] = check["facsimile_reading"]
        positions = {
            "taiyi_number": row["taiyi_number"],
            "wenchang_palace": aliases[selected["wenchang_literal"]],
            "shiji": aliases[selected["shiji_literal"]],
            "jishen": selected["jishen_literal"].replace("夘", "卯"),
        }
        if positions["jishen"] not in "子丑寅卯辰巳午未申酉戌亥":
            raise ValueError("原无效干字不能默认变成地支")
        if (
            type(row["yin"]) is not bool
            or type(row["ju"]) is not int
            or row["taiyi_number"] not in {1, 2, 3, 4, 6, 7, 8, 9}
        ):
            raise ValueError("原局身份与太乙宫数不符")
        facsimile = native[row["id"]]
        if facsimile["positions"] != positions or facsimile["table_counts"] != expected:
            raise ValueError(
                "完整书影语义核读与此前所选来源不同，须独立裁定，不默认覆盖"
            )
        rows.append(
            {
                "id": row["id"],
                "yin": row["yin"],
                "ju": row["ju"],
                "positions": positions,
                "table_counts": expected,
                "selected_literals": selected,
                "transcription_literals": literal,
                "initial_manual_literals": initial,
                "initial_manual_literal_differences": reading["differences"],
                "facsimile_checks": selected_checks,
                "facsimile_semantic_collation": {
                    "page": facsimile["page"],
                    "columns_from_right": facsimile["columns_from_right"],
                    "fields": [*positions, *expected],
                },
                "evidence_level": "full_selected_columns_native_facsimile_semantic_collation",
            }
        )
    return {
        "id": "jinjing_core_table_alignment_v1",
        "version": "1.1.0",
        "author": "FateBridge contributors",
        "classical_author": "王希明编录，四库本卷二/卷三",
        "source_title": "太乙金鏡式經·四庫全書本卷三立成表、卷二通则",
        "facsimile_source": "https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu",
        "source": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03",
        "count_rule_source": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02#推太乙運式法",
        "source_manifest_sha256": MANIFEST_SHA,
        "transcription_collation_manifest_sha256": COLLATION_SHA,
        "facsimile_collation_manifest_sha256": NATIVE_MANIFEST_SHA,
        "facsimile_correction_manifest_sha256": NATIVE_CORRECTION_SHA,
        "scope": "144局四位置和两算已按原生书影核读语义，异体神名按声明索引；不认证逐字字形、日期历法、四将全盘或全书。初录/订正、旧转录与书影并存，通则重算不自动裁定原表异数。",
        "rows": rows,
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
            raise SystemExit("太乙原表位置资料漂移，请从冻结来源生成")
    else:
        DEST.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
