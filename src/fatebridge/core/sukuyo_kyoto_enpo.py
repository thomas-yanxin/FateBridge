"""Selected Kyoto printed witness; no clock conversion or textual priority."""

from __future__ import annotations

from typing import Any

from fatebridge.core.sukuyo_printed_special import KYOTO_ENPO_SOURCE
from fatebridge.core.sukuyo_sources import load_source


def kyoto_enpo_clock_reference() -> dict[str, Any]:
    source = load_source(KYOTO_ENPO_SOURCE)
    bundle = source.data
    return {
        "witness": bundle["witness"],
        "edition": bundle["edition"],
        "source_reference": bundle["source_reference"],
        "source_bundle_sha256": source.sha256,
        **bundle["clock_reference"],
    }
