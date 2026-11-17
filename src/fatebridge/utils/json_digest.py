"""Canonical JSON digests for internal integrity and research commitments."""

import hashlib
import json


def canonical_bytes(value: object) -> bytes:
    """Encode canonical UTF-8 JSON, rejecting non-finite numbers."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: object) -> str:
    """Hash canonical UTF-8 JSON, rejecting non-finite numbers."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
