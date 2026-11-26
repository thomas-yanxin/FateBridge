"""Versioned author attribution, including explicitly unimplemented references."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


@lru_cache(maxsize=1)
def bundle() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (
                Path(__file__).parents[2] / "data/fengshui/workstation-authored-v1.json"
            ).read_text(encoding="utf-8")
        ),
    )


def provenance(key: str) -> dict[str, Any]:
    data = bundle()
    record = deepcopy(data["rulesets"][key])
    record["sources"] = [
        dict(source_id=s, **deepcopy(data["sources"][s])) for s in record["source_ids"]
    ]
    record["bundle_version"] = data["bundle_version"]
    return cast(dict[str, Any], record)


def disagreement(key: str) -> dict[str, Any]:
    return cast(dict[str, Any], deepcopy(bundle()["disagreements"][key]))


def desktop_reference() -> dict[str, Any]:
    result = deepcopy(bundle()["non_btb_desktop_reference"])
    result["sources"] = [
        dict(source_id=s, **deepcopy(bundle()["sources"][s]))
        for s in result["source_ids"]
    ]
    return cast(dict[str, Any], result)
