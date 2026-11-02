"""Current knowledge responses retain every pre-repair leaf and source claim."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def baseline():
    path = (
        Path(__file__).parent
        / "fixtures/architecture_refactor_v1/knowledge-before-manifest.json"
    )
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "c41efad308c5774fe5baa13f5511c2d046706e4134e5517e3b0e5f3b46f5a73d"
    )
    data = json.loads(raw)
    assert len(data["reads"]) == 93
    return data


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def assert_read_matches_before_repair(category, key, value):
    assert digest(value) == baseline()["reads"][category + "/" + key]
