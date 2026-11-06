"""Canonical JSON digests for internal integrity and research commitments."""

import hashlib
import json


def digest(value: object) -> str:
    """Hash canonical UTF-8 JSON, rejecting non-finite numbers."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
