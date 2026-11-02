"""Package the independently transcribed volume-five table without calculating it."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/taiyi_jinjing_v3/four-spirit-cases.json"
TARGET = ROOT / "src/fatebridge/data/classical/taiyi-jinjing-vol5-v1.json"


def render() -> str:
    raw = SOURCE.read_bytes()
    data = json.loads(raw)
    if [r["year_index"] for r in data["rows"]] != list(range(1, 61)):
        raise ValueError("卷五原表必须保留全部60行")
    if len(data["columns"]) != 12 or any(
        set(r["expected"]) != set(data["columns"]) for r in data["rows"]
    ):
        raise ValueError("卷五每行必须保留12列")
    packaged = {
        "schema_version": 1,
        "source": "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷05#四神三元五紀立成",
        "source_transcription_sha256": hashlib.sha256(raw).hexdigest(),
        "method": "manual_table_transcription; packaged_without_domain_calculation",
        "columns": data["columns"],
        "rows": data["rows"],
    }
    return json.dumps(packaged, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != rendered:
            print("Packaged Taiyi volume-five reference is stale")
            return 1
        print("Packaged Taiyi volume-five reference matches frozen transcription")
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(rendered)
        print("Updated " + str(TARGET.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
