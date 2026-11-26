"""Render the frozen transcription's variant notes, retaining both readings."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

_VARIANT = re.compile(r"\{\{另\|([^{}|=<>\[\]]+)\|([^{}|=<>\[\]]+)\}\}")
_UNRESOLVED = ("{{", "}}", "[[", "]]", "<", ">", "-{", "}-")


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("meihua/text-reference-wikisource-v1.json")
        .read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_wikisource_variant_inline_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown Meihua transcription rendering policy")
    return profile


def render_yaoci_text(raw: str) -> dict[str, Any]:
    """A display transformation, without choosing a variant or changing a cast."""
    profile = _profile()
    pieces = []
    remainder = []
    variants: list[dict[str, Any]] = []
    offset = display_length = 0
    for match in _VARIANT.finditer(raw):
        preceding = raw[offset : match.start()]
        pieces.append(preceding)
        remainder.append(preceding)
        display_length += len(preceding)
        main, alternative = match.groups()
        rendered = main + "〔一作「" + alternative + "」〕"
        variants.append(
            {
                "raw_start": match.start(),
                "raw_end": match.end(),
                "raw_template": match.group(),
                "main_reading": main,
                "alternative_reading": alternative,
                "display_start": display_length,
                "display_end": display_length + len(rendered),
            }
        )
        pieces.append(rendered)
        display_length += len(rendered)
        offset = match.end()
    pieces.append(raw[offset:])
    remainder.append(raw[offset:])
    unresolved = any(marker in "".join(remainder) for marker in _UNRESOLVED)
    if unresolved:
        for variant in variants:
            variant["display_start"] = variant["display_end"] = None
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "template_source_url": profile["source"]["url"],
        "template_wikitext_sha256": profile["source"]["wikitext_sha256"],
        "raw_text": raw,
        "display_text": None if unresolved else "".join(pieces),
        "status": (
            "unresolved_markup" if unresolved else "rendered_literal_transcription"
        ),
        "offset_unit": "unicode_code_points_zero_based_half_open",
        "variants": variants,
        "critical_edition_adjudicated": False,
    }
