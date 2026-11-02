"""Independent literal childhood rows, conditional on a supplied natal chart."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.ziwei_childhood import childhood_limit

if TYPE_CHECKING or __package__:
    from .audit_ziwei_limits import _seed
else:
    from audit_ziwei_limits import _seed

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ziwei_independent"


def audit_childhood(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "naj_ming_childhood_v1"
    for entry in json.loads((folder / "checksums.json").read_text())["files"]:
        if (
            hashlib.sha256((folder / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Childhood source checksum mismatch: " + entry["path"])
    source = json.loads((folder / "collation.json").read_text())
    production = json.loads(
        (
            ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-childhood.json"
        ).read_text()
    )
    mismatches: list[dict[str, Any]] = []
    frozen_runtime = {
        k: v
        for k, v in source.items()
        if k not in ("title", "image_url", "image_conditions_url")
    }
    if production != frozen_runtime:
        mismatches.append(dict(case="production_source_data"))
    # Explicit modern palace order is independently frozen in the prerequisite
    # corpus. We do not derive an expected name from the production mapping.
    prerequisite = json.loads(
        (fixtures / "naj_ming_prerequisites_v1/collation.json").read_text()
    )
    raw = (fixtures / "naj_ming_prerequisites_v1/collation.json").read_bytes()
    check = json.loads(
        (fixtures / "naj_ming_prerequisites_v1/checksums.json").read_text()
    )
    digest = next(e["sha256"] for e in check["files"] if e["path"] == "collation.json")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Childhood prerequisite collation checksum mismatch")
    # Printed order runs counterclockwise; convert its declared modern aliases
    # to clockwise offsets, relative to the given chart's Ming.
    offsets = {
        name.removesuffix("宫") + "宫": (-index) % 12
        for index, name in enumerate(prerequisite["palace_order"]["modern_names"])
    }
    branches = "子丑寅卯辰巳午未申酉戌亥"
    checked = unresolved = star_joins = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for hour in branches:
            for gender in ("男", "女"):
                chart = build_ziwei_chart(
                    _seed(1984, hour=hour), gender, rule_profile=profile
                )
                ming_index = branches.index(chart["ming_gong"]["branch"])
                for row in source["ordinal_rows"]:
                    r = childhood_limit(chart, row["age"])
                    name = row["modern_palace_name"]
                    branch = branches[(ming_index + offsets[name]) % 12]
                    palace = next(
                        p for p in chart["palaces"] if p["ganzhi"][1] == branch
                    )
                    checks = {
                        "status": r["status"] == "computed_given_age_ordinal",
                        "name": r["natal_palace_name"] == name,
                        "branch": r["natal_branch"] == branch,
                        "ganzhi": r["natal_palace_ganzhi"] == palace["ganzhi"],
                        "stars": r["natal_stars_detail"] == palace["stars_detail"],
                        "age": r["given_age_ordinal"] == row["age"],
                        "not_certifying_age_boundary": r["age_boundary_rule_verified"]
                        is False,
                        "no_childhood_sihua": r["childhood_sihua_supported"] is False,
                    }
                    if not all(checks.values()):
                        mismatches.append(
                            dict(
                                case=f"{profile}/{hour}/{gender}/{row['age']}",
                                checks=checks,
                            )
                        )
                    star_joins += len(palace["stars_detail"])
                    checked += 1
                for age in [*range(7, 16), 16, 40, 100]:
                    r = childhood_limit(chart, age)
                    if (
                        r["natal_palace_name"] is not None
                        or r["natal_branch"] is not None
                        or r["natal_stars_detail"]
                        or r["status"] != "unresolved_from_source"
                    ):
                        mismatches.append(
                            dict(case=f"unresolved/{profile}/{hour}/{gender}/{age}")
                        )
                    unresolved += 1
    return {
        "method_id": source["id"],
        "independent_explicit_ordinal_cells": len(source["ordinal_rows"]),
        "conditional_chart_age_cases_checked": checked,
        "natal_star_joins_checked": star_joins,
        "unresolved_age_cases_retained": unresolved,
        "manual_source_reader_count": source["manual_reader_count"],
        "mismatches": mismatches,
        "age_boundary_certified": False,
        "pre_decade_substitution_certified": False,
        "whole_childhood_verse_acceptance_passed": False,
        "whole_book_acceptance_passed": False,
        "scope": "Six explicit age labels conditional on supplied chart and age; no extrapolated tail or childhood transformations",
    }
