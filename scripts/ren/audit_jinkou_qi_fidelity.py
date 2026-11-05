"""Independent monthly/day-generation tables and exact prior-business replay."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_qi_fidelity_v1"
PIN = "4211a08851cb39d3093dc2750818dac1a90050a9bb348a9028bdc35106e889ef"
BEFORE_PIN = "9c09b7a0fa82077a8c667383baf3c9645a424975e4bf3440f80644dc101d4e1f"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != PIN:
        raise ValueError("Frozen qi reference identity changed")
    manifest = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(manifest) | {"freeze.json"}:
        raise ValueError("Frozen qi reference inventory changed")
    for name, digest in manifest.items():
        if sha(corpus / name) != digest:
            raise ValueError("Frozen qi reference bytes changed: " + name)
    data = json.loads((corpus / "reference.json").read_text())
    if (
        sha(ROOT / "tests/fixtures/jinkou_month_building_v1/source.pdf")
        != data["source_sha256"]
    ):
        raise ValueError("Frozen qi original PDF changed")
    return data


def audit() -> dict[str, Any]:
    data = reference()
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        ROOT / "pyproject.toml",
        ROOT / "uv.lock",
        Path(__file__),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    from fatebridge.core.metaphysics.jinkou_qi import (
        build_jinkou_qi,
        day_qi_facts,
        month_qi_facts,
    )

    monthly_failures, daily_failures, combined_failures = [], [], []
    for expected in data["month_matrix"]:
        actual = month_qi_facts(
            expected["month_building_branch"], expected["jiangshen_branch"]
        )
        if actual != expected:
            monthly_failures.append(dict(expected=expected, actual=actual))
    for expected in data["day_matrix"]:
        actual = day_qi_facts(expected["day_branch"], expected["jiangshen_branch"])
        want = {k: v for k, v in expected.items() if k != "jiangshen_branch"}
        if actual != want:
            daily_failures.append(dict(expected=want, actual=actual))
    count = 0
    for monthly in data["month_matrix"]:
        for daily in data["day_matrix"]:
            if daily["jiangshen_branch"] != monthly["jiangshen_branch"]:
                continue
            expected = dict(
                monthly, **{k: v for k, v in daily.items() if k != "jiangshen_branch"}
            )
            expected["basis"] = (
                f"月建{monthly['month_building_branch']}、将神{monthly['jiangshen_branch']}相距{monthly['month_offset']}支，所选月建条文：{monthly['month_qi_label'] or '未分类'}；"
                f"日支{daily['day_branch']}属{daily['day_element']}，{'生' if daily['day_generates_general'] else '未生'}将神{daily['jiangshen_element']}。"
            )
            rows = [
                dict(label="人元", content="甲", element="木"),
                dict(label="贵神", content="丑", element="土"),
                dict(
                    label="将神",
                    content=monthly["jiangshen_branch"],
                    element=daily["jiangshen_element"],
                ),
                dict(label="地分", content="寅", element="木"),
            ]
            actual = build_jinkou_qi(
                rows,
                month_branch=monthly["month_building_branch"],
                day_branch=daily["day_branch"],
            )
            actual = {k: actual[k] for k in expected}
            if actual != expected:
                combined_failures.append(dict(expected=expected, actual=actual))
            count += 1
    if before != {str(p.relative_to(ROOT)): sha(p) for p in paths}:
        raise ValueError("Source changed during qi-fidelity audit")
    return dict(
        reference_pin=PIN,
        month_matrix_count=len(data["month_matrix"]),
        day_matrix_count=len(data["day_matrix"]),
        combined_count=count,
        month_failures=monthly_failures,
        day_failures=daily_failures,
        combined_failures=combined_failures,
        finite_facts_passed=not (
            monthly_failures or daily_failures or combined_failures
        ),
        implementation_sha256=before,
        implementation_unchanged=True,
        daily_five_states_adjudicated=False,
        comprehensive_use_adjudicated=False,
        classical_acceptance_passed=False,
        new_models=0,
        new_independent_real_events=0,
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full-conformance", action="store_true")
    options = parser.parse_args()
    result = audit()
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if options.output:
        with options.output.open("x") as stream:
            stream.write(content)
    else:
        print(content, end="")
    return (
        0
        if result["finite_facts_passed"]
        and result["legacy"].get("passed", True)
        and not options.require_full_conformance
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
