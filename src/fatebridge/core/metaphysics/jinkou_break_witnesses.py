"""Additional textual witnesses, without adjudicating author intent or effects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ASSET = Path(__file__).resolve().parents[2] / "data/jinkou_break_pair_witnesses.json"
ASSET_SHA256 = "5f1a6ed20f265be4761d17ae32c71e5dfbda09ff72889d507772c06179e3cc8a"


def break_pair_witnesses() -> dict[str, Any]:
    data = ASSET.read_bytes()
    if hashlib.sha256(data).hexdigest() != ASSET_SHA256:
        raise ValueError("破支见证资料字节与固定目读不一致")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("破支见证资料须为对象")
    return result
