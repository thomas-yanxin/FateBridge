"""A directly inspected later print, separate from Taisho and its apparatus."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_wakita_special_days.json"
KYOTO_ENPO_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_kyoto_enpo_selected.json"
)
NTU_YONGLE_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_ntu_yongle130_selected.json"
)


def printed_lower_comparison(
    mansion: str | None,
    weekday: int,
    primary_labels: list[str],
    *,
    source_path: Path = SOURCE,
) -> dict[str, Any]:
    loaded = load_source(source_path)
    return _printed_comparison(
        loaded.data, loaded.sha256, mansion, weekday, primary_labels
    )


def ntu_yongle_comparisons(
    mansion: str | None, weekday: int, primary_labels: list[str]
) -> list[dict[str, Any]]:
    """The named Chinese print's two volumes retain their own tables."""
    loaded = load_source(NTU_YONGLE_SOURCE)
    return [
        _printed_comparison(bundle, loaded.sha256, mansion, weekday, primary_labels)
        for bundle in loaded.data["witnesses"]
    ]


def _printed_comparison(
    bundle: dict[str, Any],
    digest: str,
    mansion: str | None,
    weekday: int,
    primary_labels: list[str],
) -> dict[str, Any]:
    rows = [r for r in bundle["rows"] if r["weekday_index"] == weekday]
    matched = [r for r in rows if mansion is not None and r["mansion"] == mansion]
    unresolved = [r for r in rows if r["mansion"] is None]
    labels = [r["label"] for r in matched]
    complete = mansion is not None and not unresolved
    return {
        "witness": bundle["witness"],
        "volume": bundle["volume"],
        "edition": bundle["edition"],
        **(
            {"display_name": bundle["display_name"]} if "display_name" in bundle else {}
        ),
        "matched_labels": labels,
        "matched_rows": deepcopy(matched),
        "rows_for_weekday": deepcopy(rows),
        "unresolved_rows": deepcopy(unresolved),
        "labels_complete_for_selected_day": complete,
        "applied_to_primary": False,
        "disagrees_with_primary": labels != primary_labels if complete else None,
        "source_reference": {
            **deepcopy(bundle["source_reference"]),
            "source_bundle_sha256": digest,
        },
    }
