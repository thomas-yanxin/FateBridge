"""Package two frozen, disagreeing Jinjing noble tables without choosing one."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_dangshi_noble_v40"
FREEZE = "05d2c3b1b75dce1c8261225c2d0b3822c59966d9da229ea6f5852a5c9d3790c2"
OUTPUT = ROOT / "src/fatebridge/data/classical/taiyi-dangshi-nobles-v1.json"


def build() -> bytes:
    if hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest() != FREEZE:
        raise ValueError("Dangshi noble source freeze changed")
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for base, key in ((CORPUS, "files"), (ROOT, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Dangshi noble source changed: {name}")
    reading = json.loads((CORPUS / "readings.json").read_text())
    tables = []
    for edition in reading["editions"]:
        rows = edition["rows"]
        if [r["stem"] for r in rows] != list("甲乙丙丁戊己庚辛壬癸"):
            raise ValueError("Complete ten-stem source table required")
        if any(
            r[k] not in "子丑寅卯辰巳午未申酉戌亥"
            for r in rows
            for k in ("morning_branch", "evening_branch")
        ):
            raise ValueError("Valid source branch required")
        tables.append(
            {
                **{k: edition[k] for k in ("id", "edition", "url", "page", "rows")},
                "facsimile_sha256": frozen["files"][
                    ("siku" if "siku" in edition["id"] else "ming")
                    + f"-native-page{edition['page']}.png"
                ],
            }
        )
    result = {
        "id": "jinjing_dangshi_noble_sources_v1",
        "version": "1.0.0",
        "author": "FateBridge contributors; Codex image reading, no independent human review",
        "source_freeze_sha256": FREEZE,
        "tables": tables,
        "scope": "朝暮贵人本位二十项逐版本对照；朝暮边界、顺逆布将、四维寄支与完整合参断法未由此裁定。",
    }
    return (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            parser.exit(1, "Packaged Dangshi noble tables are stale\n")
    else:
        OUTPUT.write_bytes(expected)
    print(hashlib.sha256(expected).hexdigest())
