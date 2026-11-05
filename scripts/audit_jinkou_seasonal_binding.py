"""Keep the original seasonal cells and report contradictory output acceptance."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_seasonal_binding_v1"
FREEZE_SHA256 = "1f93b7c22918887615917657da0a6e1a9a4ddbac72b519f0724b59fc303aadd5"


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = corpus / "freeze.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != FREEZE_SHA256:
        raise ValueError("Frozen seasonal reference manifest changed")
    hashes = json.loads(manifest.read_text())
    if {p.name for p in corpus.iterdir()} != set(hashes) | {"freeze.json"}:
        raise ValueError("Frozen seasonal reference inventory changed")
    for name, digest in hashes.items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen seasonal reference changed")
    return json.loads((corpus / "reference.json").read_text())


def corrupt(body: dict[str, Any], fault: str) -> dict[str, Any]:
    result = copy.deepcopy(body)
    board = result["jinkou"]
    if fault.startswith("annual_"):
        board = board["year_fate"]["course"]
    if fault.endswith("forged_basis") or fault == "sparse_basis":
        board["overview"]["power_basis"] = "按地分定季节；旺衰等于现实成功率100%"
    elif fault.endswith("missing_basis"):
        del board["overview"]["power_basis"]
    elif fault.endswith("null_basis"):
        board["overview"]["power_basis"] = None
    elif fault.startswith("sparse_"):
        if fault == "sparse_invalid_month":
            board["qi_evidence"]["month_building_branch"] = "不是地支"
        else:
            board["rows"][0][fault.removeprefix("sparse_")] = "错误旺衰"
    else:
        raise ValueError(f"Unknown fault: {fault}")
    if fault.startswith("sparse_"):
        field = fault.removeprefix("sparse_")
        return {
            "overview": (
                {"power_basis": board["overview"]["power_basis"]}
                if field == "basis"
                else {}
            ),
            "qi_evidence": {
                "month_building_branch": board["qi_evidence"]["month_building_branch"]
            },
            "rows": [
                {
                    "label": row["label"],
                    "content": row["content"],
                    **({field: row[field]} if field in row else {}),
                }
                for row in board["rows"]
            ],
        }
    return result


def audit() -> dict[str, Any]:
    from fatebridge.application.execution import OutputContractError, validate_output
    from fatebridge.core.metaphysics.common import status_against_anchor
    from fatebridge.core.output_chinese import JinkouCourse
    from tests.test_agentic_nested_outputs import REST_POST_CASES, SPECS

    ref = reference()
    cells = []
    for season, states in ref["seasons"].items():
        anchor = ref["elements"][states.index("旺")]
        for element, expected in zip(ref["elements"], states):
            actual = status_against_anchor(anchor, element)
            cells.append(
                dict(
                    season=season,
                    element=element,
                    expected=expected,
                    actual=actual,
                    matched=actual == expected,
                )
            )
    spec = SPECS["jinkou"]
    payload = {
        **REST_POST_CASES[spec.rest_path](),
        "birth_year_ganzhi": "甲子",
        "year_fate_age": 43,
        "gender": "男",
    }
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    body = fn(*args, **kw)
    faults = [
        name
        for name in json.loads((CORPUS / "protocol.json").read_text())["faults"]
        if name != "sparse_power"
    ]
    results = []
    for fault in faults:
        bad = corrupt(body, fault)
        try:
            if fault.startswith("sparse_"):
                JinkouCourse.model_validate(bad)
            else:
                validate_output(spec, bad)
            rejected = False
        except (ValueError, OutputContractError):
            rejected = True
        results.append(dict(id=fault, rejected=rejected))
    return dict(
        source_url=ref["source_url"],
        source_sha256=ref["source_sha256"],
        pdf_pages=ref["pdf_pages"],
        cells=cells,
        cell_count=len(cells),
        cell_matched_count=sum(c["matched"] for c in cells),
        faults=results,
        fault_count=len(results),
        rejected_count=sum(f["rejected"] for f in results),
        whole_month_classical_acceptance=False,
        daily_five_states_adjudicated=False,
        comprehensive_use_adjudicated=False,
        real_world_efficacy="not_tested",
        new_independent_model_processes=0,
        goal_complete=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    raise SystemExit(
        0
        if report["cell_matched_count"] == 25 and report["rejected_count"] == 10
        else 1
    )
