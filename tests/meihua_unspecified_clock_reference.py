"""Preimplementation TZif-format literals, plus original failing producer rows."""

import gzip
import hashlib
import json
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "fixtures/meihua_unspecified_clock_v1"
MANIFEST_SHA256 = "b64e77d3aa4db4e39ab39625e7c17b68e82fbba621e2b7caba5593b976f768c6"
BASELINE_SHA256 = "176279d48c8992440e812a6c59b069a828a6b6e3da7b640c7eb8429bcfd38872"
sha = lambda raw: hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def load():
    raw = (FOLDER / "selection-preimplementation-manifest.json").read_bytes()
    assert sha(raw) == MANIFEST_SHA256
    for name, h in json.loads(raw)["files"].items():
        assert sha((FOLDER / name).read_bytes()) == h, name
    packet = (FOLDER / "before-clock355.json.gz").read_bytes()
    assert sha(packet) == BASELINE_SHA256
    rows = json.loads(gzip.decompress(packet))
    assert len(rows) == 355
    assert sum(row["case"]["expected_clock_resolvable"] for row in rows) == 57
    assert (
        sum(
            row["layers"]["service"].get("valid", False)
            and not row["case"]["expected_clock_resolvable"]
            for row in rows
        )
        == 144
    )
    return rows


def digest(value):
    return sha(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )
